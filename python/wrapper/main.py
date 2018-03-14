# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.dp import Action
from _ncs.dp import action_set_timeout
import os
import json


# ---------------------------------------------
# ACTIONS
# ---------------------------------------------
class WrapperAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output):
        self.log.info('Action: {}'.format(name))
        action_set_timeout(uinfo, 240)

        self.log.info('Document-id: ', input.document_id)

        try:
            service_info = ServiceInfo(input.document_id)
            with ncs.maapi.single_write_trans(uinfo.username, "system") as write_t:
                root = ncs.maagic.get_root(write_t)

                if service_info.operation == "create" or service_info.operation == "update":
                    dev = root.ncs__services.loopback__loopback.loopback__device.create(service_info.device_name)
                    dev.loopback__description = service_info.description
                    dev.loopback__loopback_id = service_info.loopback_id
                elif service_info.operation == "delete":
                    del root.ncs__services.loopback__loopback.loopback__device[service_info.device_name]
                else:
                    raise KeyError('Unknown service operation: {}'.format(service_info.operation))

                write_t.apply()
                output.success = "Service call completed successfully"

        except Exception as e:
            output.failure = "An error occurred: {}".format(e)


# ---------------------------------------------
# UTILS
# ---------------------------------------------
class ServiceInfo(object):
    def __init__(self, document_id):
        self._db_file = os.path.join('service-info.json')
        service_dict = self._load()[document_id]

        self.__dict__.update(service_dict)

    def _load(self):
        with open(self._db_file) as f:
            return json.load(f)


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
