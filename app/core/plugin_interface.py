
from core.backend import ApiBackend
from core.flow import Flow

class PluginInterface:
    def __init__(self, api: ApiBackend, flow: Flow):
        self.protocol = "BLE"
        self.devices = {}
        self.active = False
        raise NotImplementedError("Plugins must implement the '__init__' method.")
    
    def execute(self) -> None:
        raise NotImplementedError("Plugins must implement the 'execute' method.")
    
    def associate_flow_node(self, device=None) -> None:
        raise NotImplementedError("Plugins must implement the 'associate_flow_node' method.")
    
    def display_devices(self) -> None:
        raise NotImplementedError("Plugins must implement the 'display_devices' method.")
    
    class SearchableDeviceInterface:
        def __init__(self):
            self.protocol = ""
            self.scan_filter_method = ""
            self.scan_filter = ""

    class DeviceInterface:
        def __init__(self):
            self.manufacturer = ""
            self.ip = ""
            self.mac_address = ""
            self.serial_no = ""
            self.model_no = ""
            self.device_name = ""
            self.com_protocol = ""
            self.firmware = ""
            self.device_description = ""


        

    