import logging
from core.plugin_interface import PluginInterface
from config.config import ConfigSettings
from datetime import datetime
from math import sin, cos, pi
from core.backend import ApiBackend
from core.ble_manager import BLEManager
import random
from hashlib import md5

class null(PluginInterface):
    def __init__(self):
        self.protocol = "BLE"
        self.devices = {}

    def execute(self, api: ApiBackend, ble_manager: BLEManager) -> None:
        for _, device in self.devices.items():
            logging.info("Executing null sensor plugin")
            device.generate_emulated_data()
            logging.debug(f"Data from {device.device_name}: {device.data}")
            try:
                jsn_data = {
                    "device_id": device.mac_address,
                    "device_name": device.device_name,
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "firmware": device.firmware,
                    "data": { # limit decimals to 2
                        "temperature": round(device.data['data']['temperature'], 2),
                        "humidity": round(device.data['data']['humidity'], 2),
                        "energy": round(device.data['data']['energy'], 2),
                        "brightness": round(device.data['data']['brightness'], 2),
                        "conductivity": round(device.data['data']['conductivity'], 2)
                    }
                }
                
                api.send_collected_data(jsn_data)
            except Exception as e:
                logging.error(f"Error sending data to API: {str(e)}")

    def display_devices(self) -> None:
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")

    class SearchableDevice:
        def __init__(self):
            self.device_description = "Thermometer Sensor (Emulator)"
            self.protocol = "BLE"
            self.model_no = "onio-0005"
            self.scan_filter_method = "emulator"
            self.scan_filter = "none"

    class Device:
        def __init__(self):
            self.config = ConfigSettings()
            self.manufacturer = "ONiO"
            self.ip = ""
            self.mac_address = self.generate_mac(self.config.get('settings', 'hub_serial_no'))
            self.serial_no = "onio-0005-001"
            self.model_no = "onio-null-emulator"
            self.device_name = "Thermolator"
            self.com_protocol = "BLE"
            self.firmware = "1.0.0"
            self.device_description = 'Thermometer Sensor (Emulator)'
            self.data = {
                "device_id": self.mac_address,
                "device_name": self.device_name,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "firmware": self.firmware,
                "data": {
                    "temperature": 23.5,
                    "humidity": 56.7,
                    "energy": 70,
                    "brightness": 200.0,
                    "conductivity": 200.0
                }
            }

        def generate_mac(self, serial_no) -> str:
            # Generate a deterministic MAC address based on the serial number
            hash_object = md5(serial_no.encode())
            hash_hex = hash_object.hexdigest()
            mac_parts = [hash_hex[i:i+2] for i in range(0, 12, 2)]
            mac_address = ':'.join(mac_parts)
            return mac_address

        def generate_emulated_data(self) -> None:
            current_time = datetime.now()

            # "cosine wave" pattern for the temperature data point based on the minutes value
            minutes = current_time.minute
            temperature = 25 + 5 * cos(2 * pi * minutes / 60) + random.uniform(-1, 1)

            # Generate a "square wave" pattern for the humidity data point based on the hours value
            hours = current_time.hour
            humidity = (50 if hours % 2 == 0 else 70) + random.uniform(1, 4)

            # Generate a "pyramid" pattern for the energy data point based on the seconds value
            seconds = current_time.second
            energy = (seconds if seconds < 30 else 60 - seconds) 

            # Generate a "sine wave" pattern for the brightness data point based on the minutes value
            minutes = current_time.minute
            brightness = 255 * (1 + sin(2 * pi * minutes / 60)) + random.uniform(0, 5)

            # Generate a "sawtooth" pattern for the conductivity data point based on the hours value
            hours = current_time.hour
            conductivity = 255 * (hours / 24) + random.uniform(0, 5)

            self.data['data']['temperature'] = temperature
            self.data['data']['humidity'] = humidity
            self.data['data']['energy'] = energy
            self.data['data']['brightness'] = brightness
            self.data['data']['conductivity'] = conductivity
            self.data['timestamp'] = current_time.strftime("%Y-%m-%dT%H:%M:%S")