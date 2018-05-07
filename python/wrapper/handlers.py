import ncs
import json
from enum import Enum


class SvcOp(Enum):
    CREATE = 'create'
    MODIFY = 'modify'
    DELETE = 'delete'

    @property
    def op_method(self):
        return dict(zip(SvcOp, ['op_create', 'op_modify', 'op_delete']))[self]


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
                self.log.info('Commit')
                write_t.apply()

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


