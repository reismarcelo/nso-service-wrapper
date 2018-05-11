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
    _mandatory_args = [
        'operation_type',
    ]
    # Whether to commit via commit-queue or not
    COMMIT_QUEUE = True
    # Timeout -1 means infinity, which is bounded by action_set_timeout
    COMMIT_QUEUE_SYNC_TIMEOUT = 60

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

        # Service variables used internally by wrapper start with _
        self._operation_type = SvcOp(service_dict['operation_type'])
        self._validate = ServiceArgs.boolean_val(service_dict.get('validate', 'false'))

        self.__dict__.update(service_dict)

    def _load(self):
        with open(os.path.join('service-info.json')) as f:
            return json.load(f)[self._service_reference]

    @property
    def _service_reference(self):
        return '{}-{}'.format(self._service_name, self._operation_id)

    @staticmethod
    def boolean_val(value):
        if isinstance(value, str):
            return value.lower() == 'true'
        return bool(value)


class BaseNsoService(object):
    service_name = None

    def __init__(self, service_args, logger):
        self.service_args = service_args
        self.log = logger

    def __call__(self, user_info):
        self.log.info('Service: {}, op-id: {}, op-type: {}'.format(self.service_args._service_name,
                                                                   self.service_args._operation_id,
                                                                   self.service_args._operation_type.value))

        return_value = None
        with ncs.maapi.single_write_trans(user_info.username, "system") as write_t:
            root = ncs.maagic.get_root(write_t)

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
                if ServiceArgs.COMMIT_QUEUE:
                    write_t.apply(flags=Flags.COMMIT_NCS_SYNC_COMMIT_QUEUE)
                    q_id, q_status = write_t.commit_queue_result(timeout=ServiceArgs.COMMIT_QUEUE_SYNC_TIMEOUT)
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

    # TODO: Implement templates
    def op_create(self, user_info, root):
        self.log.info('Running base op_create')

    def op_modify(self, user_info, root):
        self.log.info('Running base op_modify')
        self.op_create(user_info, root)

    def op_delete(self, user_info, root):
        self.log.info('Running base op_delete')

    def __str__(self):
        return self.service_name


