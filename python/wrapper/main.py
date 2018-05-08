# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.dp import Action
from _ncs.dp import action_set_timeout
from wrapper.handlers import ServiceArgs
import wrapper.customhandlers


# ---------------------------------------------
# ACTIONS
# ---------------------------------------------
class WrapperAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        self.log.info('Action: {}'.format(name))
        action_set_timeout(uinfo, 240)

        try:
            service_params = ServiceArgs(input.service_name, input.operation_id)

            service_handler = service_handler_cls(input.service_name)(service_params, self.log)

            result = service_handler(uinfo)

        except Exception as e:
            self.log.error('Error in {}: {}'.format(name, e))
            output.failure = "An error occurred: {}".format(e)
        else:
            action_output = ["Service call completed successfully"]
            if result is not None:
                action_output.append("{}".format(result))

            output.success = ": ".join(action_output)


# ---------------------------------------------
# UTILS
# ---------------------------------------------
def service_handler_cls(service_name, custom_handlers_module=wrapper.customhandlers):
    def is_service_class(attr_name):
        svc_class = getattr(custom_handlers_module, attr_name)
        return (
            attr_name.startswith('Service') and
            isinstance(svc_class, type) and
            issubclass(svc_class, custom_handlers_module.BaseNsoService)
        )

    def service_class_info(service_class_name):
        service_cls = getattr(custom_handlers_module, service_class_name)
        return service_cls.service_name, service_cls

    # available_services is {<service_name>: <service handler class>, ...}
    available_services = dict(map(service_class_info, filter(is_service_class, dir(custom_handlers_module))))

    return available_services.get(service_name, custom_handlers_module.BaseNsoService)


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        # The application class sets up logging for us. It is accessible
        # through 'self.log' and is a ncs.log.Log instance.
        self.log.info('Main RUNNING')

        # Registration of action callbacks
        self.register_action('wrapper-action', WrapperAction)

    def teardown(self):
        self.log.info('Main FINISHED')
