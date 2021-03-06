# Wrapper package

Service wrapper action that receives northbound calls with service-name, operation-id parameters and create/modify/delete services based on parameters retrieved from a database using service-reference (i.e. <service-name>-<operation-id>) as key.

For services that can be instantiated using templates, the NSO config template files need to be under the templates folder. Two files need to be created: <service name>-create.xml and <service name>-delete.xml.

For services requiring additional logic, custom handlers can be provided. They need to be in a python file under wrapper/python/wrapper/customhandlers.

An example of a custom handler is provided below:

    from wrapper.handlers import BaseNsoService
    from wrapper.service_registry import register

    @register("loopback")
    class ServiceLoopback(BaseNsoService):
        def op_create(self, user_info, root):
            self.log.info('Custom op_create')
            dev = root.ncs__services.loopback__loopback.loopback__device.create(self.service_args.device_name)
            dev.loopback__description = self.service_args.description
            dev.loopback__loopback_id = self.service_args.loopback_id

        def op_delete(self, user_info, root):
            self.log.info('Custom op_delete')
            del root.ncs__services.loopback__loopback.loopback__device[self.service_args.device_name]


The database portion is implemented using a json file named service-info.json:

    {
      "loopback-100": {
        "operation_type": "create",
        "validate": "true",
        "device_name": "A3-ASR9K-R6",
        "loopback_id": 20,
        "description": "### Loopback 20 - testing 002 ###"
      },
      "loopback-101": {
        "operation_type": "create",
        "validate": "false",
        "device_name": "A3-ASR9K-R6",
        "loopback_id": 20,
        "description": "### Loopback 20 - testing 002 ###"
      },
      "loopback-102": {
        "operation_type": "delete",
        "validate": "false",
        "device_name": "A3-ASR9K-R6",
        "loopback_id": 20
      },
      "loopback-200": {
        "operation_type": "modify",
        "validate": "false",
        "device_name": "XR-0",
        "loopback_id": 1,
        "description": "### Loopback 1 - testing 333 ###"
      },
      "loopback-201": {
        "operation_type": "delete",
        "validate": "false",
        "device_name": "XR-0",
        "loopback_id": 1
      },
      "defaultloopback-300": {
        "operation_type": "modify",
        "validate": "false",
        "device_name": "XR-0",
        "loopback_id": 1,
        "description": "### Loopback 1 - testing 333 ###"
      },
      "defaultloopback-301": {
        "operation_type": "delete",
        "validate": "false",
        "device_name": "XR-0",
        "loopback_id": 1
      }
    }

