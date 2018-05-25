from wrapper.exceptions import WrapperException
from wrapper.handlers import BaseNsoService

# _registered_services is {<service_name>: <service handler class>, ...}
_registered_services = dict()


def register(service_name):
    """
    Decorator used for registering a custom service handler class. That is, associate a service name with a custom
    service handler class. The class being decorated needs to be a subclass of BaseNsoService.

    @register("sample")
    class ServiceSample(BaseNsoService):
        def op_create(self, user_info, root):
            ...
        def op_delete(self, user_info, root):
            ...

    :param service_name: Name of the service to be associated with this custom service handler
    :return: decorator
    """
    def decorator(handler_cls):
        if service_name in _registered_services:
            raise WrapperException('Duplicate service name found: {}'.format(service_name))

        if not isinstance(handler_cls, type) or not issubclass(handler_cls, BaseNsoService):
            raise WrapperException('Attempting to register an invalid handler class: {}'.format(handler_cls))

        _registered_services[service_name] = handler_cls

        return handler_cls

    return decorator


def service_handler(service_name, service_args, logger):
    """
    Factory function that returns a service handler instance for the provided service name.
    The instance is either from a custom service handler class (subclass of BaseNsoService), or BaseNsoService itself
    when no custom handler is registered for service_name.

    :param service_name: Name of the service
    :param service_args: handlers.ServiceArgs instance containing the service parameters
    :param logger: logger object
    :return: service handler instance
    """
    return _registered_services.get(service_name, BaseNsoService)(service_args, logger)


def num_handlers():
    """
    Returns the number of registered custom service handlers
    """
    return len(_registered_services)
