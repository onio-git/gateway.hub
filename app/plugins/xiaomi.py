import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from core.ble_manager import BLEManager
import asyncio


# class name must match the file name
class xiaomi(PluginInterface):
    def __init__(self):
        self.protocol = "BLE"
        self.devices = {}

    def execute(self, api: ApiBackend, ble_manager: BLEManager):
        return
        # TODO: Implement this method
        for mac, device in self.devices.items():
            client = asyncio.run(ble_manager.connect_device(device))
            

    def display_devices(self):
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")

    class SearchableDevice:
        def __init__(self):
            self.protocol = "BLE"
            self.scan_filter_method = "uuid"
            self.scan_filter = "0000fe95-0000-1000-8000-00805f9b34fb"

    class Device:
        def __init__(self, mac_address, device_name):
            self.manufacturer = "Xiaomi"
            self.ip = ""
            self.mac_address = mac_address
            self.device_name = device_name
            self.serial_no = ""
            self.model_no = "HHCCJCY01HHCC"
            self.com_protocol = "BLE"
            self.firmware = ""
            self.device_description = 'Temperature, humidity and brightness sensor'
            

