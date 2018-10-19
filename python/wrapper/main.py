# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.dp import Action
from _ncs.dp import action_set_timeout
from wrapper.handlers import ServiceArgs
from wrapper.service_registry import service_handler, num_handlers
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
            service_call = service_handler(input.service_name,
                                           ServiceArgs(input.service_name, input.operation_id),
                                           self.log)

            result = service_call(uinfo)

        except Exception as e:
            self.log.error('Error in {}: {}'.format(name, e))
            output.failure = "An error occurred: {}".format(e)
        else:
            action_output = ["Service call completed successfully"]
            if result is not None:
                action_output.append(":\n{}".format(result))

            output.success = "".join(action_output)


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        self.log.info('Main RUNNING, {} custom service handlers registered.'.format(num_handlers()))

        # Registration of action callbacks
        self.register_action('wrapper-action', WrapperAction)

    def teardown(self):
        self.log.info('Main FINISHED')
