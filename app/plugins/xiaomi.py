import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from config.config import ConfigSettings as config
from core.flow import Flow
import asyncio
from bleak import BleakClient
from datetime import datetime
import time

# Xiaomi service and characteristic UUIDs
SERVIDE_UUID = "00001204-0000-1000-8000-00805f9b34fb"
ACCESS_CHAR_UUID = "00001a00-0000-1000-8000-00805f9b34fb"
READ_DATA_UUID = "00001a01-0000-1000-8000-00805f9b34fb"
READ_BATTERY_UUID = "00001a02-0000-1000-8000-00805f9b34fb"


# class name must match the file name
class xiaomi(PluginInterface):
    def __init__(self, api: ApiBackend, flow: Flow):
        self.protocol = "BLE"
        self.devices = {}
        self.active = False
        self.api = api
        self.flow = flow
        self.config = config()

    def associate_flow_node(self, device):
        pass

    def execute(self) -> None:
        if self.active: # prevent multiple instances of the plugin from running at the same time
            return
        self.active = True
        for _, device in self.devices.items():
            data = asyncio.run(device.connect_and_read())
            if not data:
                logging.error(f"Failed to read data from {device.mac_address} - {device.device_name}")
                continue
            jsn_data = {
                "devid": device.mac_address,
                "gtwid": self.config.get('settings', 'hub_serial_no'),
                "gtwtime": datetime.now(tz=None).isoformat(),
                "orgid": 111111,
                "primary": {
                    "type": "raw",
                    "value": [
                        round(data['temperature'], 2),
                        round(data['moisture'], 2),
                        round(data['energy'], 2),
                        round(data['brightness'], 2),
                        round(data['conductivity'], 2)
                    ]
                }
            }
            self.api.send_collected_data(jsn_data)
        self.active = False

    def display_devices(self) -> None:
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")

    class SearchableDevice(PluginInterface.SearchableDeviceInterface):
        def __init__(self):
            self.protocol = "BLE"
            self.scan_filter_method = "uuid"
            self.scan_filter = "0000fe95-0000-1000-8000-00805f9b34fb"

    class Device(PluginInterface.DeviceInterface):
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
            self.data = {}

        async def connect_and_read(self):
            
            try:
                async with BleakClient(self.mac_address) as client:
                    logging.info(f"Connected to {self.mac_address} - {self.device_name}")

                    # Write to access characteristic
                    await client.write_gatt_char(ACCESS_CHAR_UUID, bytearray([0xA0, 0x1F]))

                    # Read data characteristic
                    data = await client.read_gatt_char(READ_DATA_UUID)
                    self.data['temperature'] = int.from_bytes(data[0:2], byteorder='little') / 10.0
                    self.data['brightness'] = int.from_bytes(data[3:7], byteorder='little')
                    self.data['moisture'] = data[7]
                    self.data['conductivity'] = int.from_bytes(data[8:10], byteorder='little')

                    # Read battery characteristic
                    battery = await client.read_gatt_char(READ_BATTERY_UUID)
                    self.data['energy'] = battery[0]
                    self.firmware = battery[2:7].decode('utf-8')

                    self.print_data()
            except KeyboardInterrupt:
                return None
            except Exception as e:
                logging.error(f"Error reading data from {self.mac_address} - {self.device_name}: {e}")
            finally:
                logging.info(f"Disconnected from {self.mac_address} - {self.device_name}")
                return self.data


        def print_data(self):
            print("Xiaomi Device Data:")
            print(f"  Temperature: {self.data['temperature']} °C")
            print(f"  Brightness: {self.data['brightness']} lux")
            print(f"  Moisture: {self.data['moisture']} %")
            print(f"  Conductivity: {self.data['conductivity']} µS/cm")
            print(f"  Battery: {self.data['energy']}%")
            

