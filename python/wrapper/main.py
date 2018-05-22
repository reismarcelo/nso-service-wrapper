# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.dp import Action
from _ncs.dp import action_set_timeout
from wrapper.handlers import ServiceArgs
from wrapper.exceptions import WrapperException
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

            service_handler = ServiceRegistry.get(input.service_name)(service_params, self.log)

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
class ServiceRegistry(object):

    _custom_handlers_module = wrapper.customhandlers

    # _registered_services is {<service_name>: <service handler class>, ...}
    _registered_services = dict()

    @classmethod
    def load_custom_handlers(cls):
        """
        Search _custom_handlers_module for service handler classes and populate _registered_services accordingly
        :return: None
        """
        def is_service_class(attr_name):
            service_cls = getattr(cls._custom_handlers_module, attr_name)
            return (
                    attr_name.startswith('Service') and
                    isinstance(service_cls, type) and
                    issubclass(service_cls, cls._custom_handlers_module.BaseNsoService)
            )

        def service_info(service_cls_name):
            service_cls = getattr(cls._custom_handlers_module, service_cls_name)
            return service_cls.service_name, service_cls

        for svc_name, svc_class in map(service_info, filter(is_service_class, dir(cls._custom_handlers_module))):
            if svc_name in cls._registered_services:
                raise WrapperException('Duplicate service handler name found: {}'.format(svc_name))
            else:
                cls._registered_services[svc_name] = svc_class

    @classmethod
    def get(cls, service_name):
        """
        Returns a service handler class for the provided service name. That is either a custom service handler class
        (subclass of BaseNsoService), or BaseNsoService itself when no custom handler is found.
        :param service_name: Name of the service
        :return: service handler class
        """
        return cls._registered_services.get(service_name, cls._custom_handlers_module.BaseNsoService)


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        self.log.info('Main RUNNING')

        # Load service handlers
        ServiceRegistry.load_custom_handlers()

        # Registration of action callbacks
        self.register_action('wrapper-action', WrapperAction)

    def teardown(self):
        self.log.info('Main FINISHED')
