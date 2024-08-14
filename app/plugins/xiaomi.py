import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from core.ble_manager import BLEManager
import asyncio
from bleak import BleakClient


# class name must match the file name
class xiaomi(PluginInterface):
    def __init__(self):
        self.protocol = "BLE"
        self.devices = {}
        self.plugin_active = False

    def execute(self, api: ApiBackend, ble_manager: BLEManager):
        if self.plugin_active: # prevent multiple instances of the plugin from running at the same time
            return
        self.plugin_active = True
        for _, device in self.devices.items():
            asyncio.run(device.connect_and_read())
        self.plugin_active = False

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

            # Xiaomi service and characteristic UUIDs
            self.service_uuid = "00001204-0000-1000-8000-00805f9b34fb"
            self.access_char_uuid = "00001a00-0000-1000-8000-00805f9b34fb"
            self.read_data_uuid = "00001a01-0000-1000-8000-00805f9b34fb"
            self.read_battery_uuid = "00001a02-0000-1000-8000-00805f9b34fb"

            self.client = BleakClient(mac_address)
            self.data = {}

        async def connect_and_read(self):
            try:
                await self.client.connect()
                logging.info(f"Connected to {self.mac_address} - {self.device_name}")

                # Write to access characteristic
                await self.client.write_gatt_char(self.access_char_uuid, bytearray([0xA0, 0x1F]))

                # Read data characteristic
                data = await self.client.read_gatt_char(self.read_data_uuid)
                self.data['temperature'] = int.from_bytes(data[0:2], byteorder='little') / 10.0
                self.data['brightness'] = int.from_bytes(data[3:7], byteorder='little')
                self.data['moisture'] = data[7]
                self.data['conductivity'] = int.from_bytes(data[8:10], byteorder='little')

                # Read battery characteristic
                battery = await self.client.read_gatt_char(self.read_battery_uuid)
                self.data['energy'] = battery[0]
                self.firmware = battery[2:7].decode('utf-8')

                self.print_data()
            except Exception as e:
                pass
            finally:
                await self.client.disconnect()
                logging.info(f"Disconnected from {self.mac_address} - {self.device_name}")

        def print_data(self):
            print("Xiaomi Device Data:")
            print(f"  Temperature: {self.data['temperature']} °C")
            print(f"  Brightness: {self.data['brightness']} lux")
            print(f"  Moisture: {self.data['moisture']} %")
            print(f"  Conductivity: {self.data['conductivity']} µS/cm")
            print(f"  Battery: {self.data['energy']}%")
            

