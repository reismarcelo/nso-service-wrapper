import ncs
from wrapper.handlers import BaseNsoService
from wrapper.service_registry import register


@register("example")
class ServiceRsvpte(BaseNsoService):
    def op_create(self, user_info, root):
        self.log.info('Custom op_create')

    def op_delete(self, user_info, root):
        self.log.info('Custom op_delete')
