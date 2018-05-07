import ncs
from wrapper.handlers import BaseNsoService


class ServiceRsvpte(BaseNsoService):
    service_name = "rsvpte"

    def op_create(self, user_info, root):
        pass

    def op_delete(self, user_info, root):
        pass


class ServiceLoopback(BaseNsoService):
    service_name = "loopback"

    def op_create(self, user_info, root):
        self.log.info('Running op_create')
        dev = root.ncs__services.loopback__loopback.loopback__device.create(self.service_args.device_name)
        dev.loopback__description = self.service_args.description
        dev.loopback__loopback_id = self.service_args.loopback_id

    def op_delete(self, user_info, root):
        self.log.info('Running op_delete')
        del root.ncs__services.loopback__loopback.loopback__device[self.service_args.device_name]
