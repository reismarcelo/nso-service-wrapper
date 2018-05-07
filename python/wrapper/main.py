# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.dp import Action
from _ncs.dp import action_set_timeout
import os
import json
from wrapper.handlers import SvcOp
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
        return \
            attr_name.startswith('Service') and \
            isinstance(svc_class, type) and \
            issubclass(svc_class, custom_handlers_module.BaseNsoService)

    def service_class_info(service_class_name):
        service_cls = getattr(custom_handlers_module, service_class_name)
        return service_cls.service_name, service_cls

    # available_services is {<service_name>: <service handler class>, ...}
    available_services = dict(map(service_class_info, filter(is_service_class, dir(custom_handlers_module))))

    return available_services.get(service_name, custom_handlers_module.BaseNsoService)


class ServiceArgs(object):
    _mandatory_args = [
        'operation_type',
        'validate',
    ]

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


class WrapperException(Exception):
    pass


class NBJsonError(WrapperException):
    pass


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
