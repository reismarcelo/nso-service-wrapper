import ncs
import os
import json
from enum import Enum
from wrapper.exceptions import SBError, NBJsonError


class Flags(object):
    # TODO: In 4.6, these flags are already present. Replace with an import:
    # from _ncs.maapi import (COMMIT_NCS_SYNC_COMMIT_QUEUE, NCS_COMMIT_QUEUE_COMPLETED, NCS_COMMIT_QUEUE_NONE,
    #                         NCS_COMMIT_QUEUE_TIMEOUT)
    COMMIT_NCS_SYNC_COMMIT_QUEUE = 512
    NCS_COMMIT_QUEUE_COMPLETED = 2
    NCS_COMMIT_QUEUE_NONE = 0
    NCS_COMMIT_QUEUE_TIMEOUT = 3


class SvcOp(Enum):
    CREATE = 'create'
    MODIFY = 'modify'
    DELETE = 'delete'

    @property
    def op_method(self):
        return dict(zip(SvcOp, ['op_create', 'op_modify', 'op_delete']))[self]


class ServiceArgs(object):
    """
    Encapsulates all parameters of a service, which is then passed to the service handler in order to perform the
    different service operations (create, modify, delete). These parameters are loaded from a database in JSON format.

    All locally defined attributes start with '_' in order to avoid collision with the loaded JSON parameters.
    """
    _mandatory_args = [
        'operation_type',
    ]
    # Whether to commit via commit-queue or not
    _COMMIT_QUEUE = True
    # Timeout -1 means infinity, which is bounded by action_set_timeout
    _COMMIT_QUEUE_SYNC_TIMEOUT = 60

    def __init__(self, service_name, operation_id):
        self._service_name = service_name
        self._operation_id = operation_id

        try:
            service_dict = self._load()
        except KeyError as e:
            raise NBJsonError('No service record found for {}'.format(e))

        for field in ServiceArgs._mandatory_args:
            if field not in service_dict:
                raise NBJsonError('A mandatory service parameter is missing: {}'.format(field))
        for key in service_dict.keys():
            if key.startswith('_'):
                raise NBJsonError('Service arguments cannot start with "_": {}'.format(key))

        # Service variables used internally by wrapper start with '_'
        self._operation_type = SvcOp(service_dict['operation_type'])
        self._validate = ServiceArgs._boolean_val(service_dict.get('validate', 'false'))

        self.__dict__.update(service_dict)

    def _template_vars(self):
        """
        Returns a dictionary containing ServiceArgs attributes that can be used inside templates. These are attributes
        with name not starting with '_' and of one of the supported types (inside templates): str, int, boolean, float,
        or None.
        :return: dictionary of <attribute name>: <attribute value>
        """
        def valid_template_type(value):
            return (
                isinstance(value, str) or
                isinstance(value, int) or
                isinstance(value, float) or
                value is None
            )

        return {k: v for k, v in self.__dict__.items() if not k.startswith('_') and valid_template_type(v)}

    def _load(self):
        """
        Retrieve service parameters from database, using _service_reference as key.
        :return: dictionary containing service parameters
        """
        with open(os.path.join('service-info.json')) as f:
            return json.load(f)[self._service_reference]

    @property
    def _service_reference(self):
        return '{}-{}'.format(self._service_name, self._operation_id)

    @staticmethod
    def _boolean_val(value):
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)


class BaseNsoService(object):
    """
    Provides a generic implementation of service operations using NSO config templates. Templates are looked-up in the
    templates folder with filenames in the format '<service name>-<operation type>'.
    An instance of this class is a callable, which executes the proper handler method (op_create, op_modify or
    op_delete) according to the operation type.

    When service instantiation require more logic than a config template can provide, custom handler methods can be
    written by subclassing BaseNsoService and overriding op_create, op_modify and op_delete as needed.
    """
    def __init__(self, service_args, logger):
        """
        Initialization of BaseNsoService
        :param service_args: ServiceArgs instance containing the service parameters
        :param logger: logger object
        """
        self.service_args = service_args
        self.log = logger

    def __call__(self, user_info):
        """
        Initiate a write transaction towards NSO, perform the proper NSO service operation diffs and commit (or
        commit dry-run)

        :param user_info: a UserInfo object
        :return: commit dry-run output or None (in case of regular commits)
        """
        self.log.info('Service: {}, op-id: {}, op-type: {}'.format(self.service_args._service_name,
                                                                   self.service_args._operation_id,
                                                                   self.service_args._operation_type.value))

        return_value = None
        with ncs.maapi.single_write_trans(user_info.username, "system") as write_t:
            root = ncs.maagic.get_root(write_t)

            # Calls op_create, op_modify or op_delete according to the _operation_type
            getattr(self, self.service_args._operation_type.op_method)(user_info, root)

            if self.service_args._validate:
                self.log.info('Commit dry-run')

                # TODO: This dry-run method is deprecated. Need to update once running NSO 4.6 or later
                dry_run_input = root.services.commit_dry_run.get_input()
                dry_run_input.outformat = "native"
                dry_run_output = root.services.commit_dry_run(dry_run_input)
                return_value = json.dumps({device.name: device.data for device in dry_run_output.native.device})

                # With NSO 4.6 or later we should use this method instead
                # return_value = write_t.apply_with_result(flags=_ncs.maapi.COMMIT_NCS_DRY_RUN_CLI)
            else:
                self.log.info('Commit start')
                if ServiceArgs._COMMIT_QUEUE:
                    write_t.apply(flags=Flags.COMMIT_NCS_SYNC_COMMIT_QUEUE)
                    # Parse commit-queue result
                    q_id, q_status = write_t.commit_queue_result(timeout=ServiceArgs._COMMIT_QUEUE_SYNC_TIMEOUT)
                    if q_status not in {Flags.NCS_COMMIT_QUEUE_COMPLETED, Flags.NCS_COMMIT_QUEUE_NONE}:
                        if q_status == Flags.NCS_COMMIT_QUEUE_TIMEOUT:
                            err_msg = 'Timeout waiting for commit-queue item to complete: {}'.format(q_id)
                        else:
                            err_msg = 'Commit-queue item failed with status code ({})'.format(q_status)

                        raise SBError(err_msg)
                else:
                    write_t.apply()

                self.log.info('Commit complete')

        return return_value

    def template_name(self, operation_type):
        """
        Returns the name of the template for this service and operation type

        :param operation_type: SvcOp
        :return: Template name as string
        """
        return '{}-{}'.format(self.service_args._service_name, operation_type.value)

    def op_create(self, user_info, root):
        """
        Default handler for create operation.

        :param user_info: a UserInfo object
        :param root: root node (maagic.Node)
        :return: None
        """
        template = self.template_name(SvcOp.CREATE)
        self.log.info('Default op_create, applying template: {}'.format(template))
        # Context is set to root.services because maagic.Root object cannot be used as a context node in Template
        apply_template(template, root.services, self.service_args._template_vars())

    def op_modify(self, user_info, root):
        """
        Default handler for modify operation. Just calls op_create.

        :param user_info: a UserInfo object
        :param root: root node (maagic.Node)
        :return: None
        """
        self.log.info('Default op_modify')
        self.op_create(user_info, root)

    def op_delete(self, user_info, root):
        """
        Default handler for delete operation.

        :param user_info: a UserInfo object
        :param root: root node (maagic.Node)
        :return: None
        """
        template = self.template_name(SvcOp.DELETE)
        self.log.info('Default op_delete, applying template: {}'.format(template))
        # Context is set to root.services because maagic.Root object cannot be used as a context node in Template
        apply_template(template, root.services, self.service_args._template_vars())


def apply_template(template_name, context, var_dict=None, none_value=''):
    """
    Facilitate applying templates by setting template variables via an optional dictionary

    By default, if a dictionary item has value None it is converted to an empty string. In the template,
    'when' statements can be used to prevent rendering of a template block if the variable is an empty string.

    :param template_name: Name of the template file
    :param context: Context in which the template is rendered
    :param var_dict: Optional dictionary containing additional variables to be passed to the template
    :param none_value: Optional, defines the replacement for variables with None values. Default is an empty string.
    """
    template = ncs.template.Template(context)
    t_vars = ncs.template.Variables()

    if var_dict is not None:
        for name, value in var_dict.items():
            t_vars.add(name, value or none_value)

    template.apply(template_name, t_vars)