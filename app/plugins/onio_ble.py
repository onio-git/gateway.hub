import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from bleak import BleakScanner
from datetime import datetime
import asyncio
import threading

class onio_ble(PluginInterface):
    def __init__(self):
        self.protocol = "BLE"
        self.devices = {}
        self.plugin_active = False
        self.scanner = None
        self.scan_thread = None
        self.stop_event = threading.Event()

        # ONiO device types based on identifier bytes
        self.DEVICE_TYPES = {
            0xAA: "Blomsterpinne",
            0xBB: "ONiO-Accelerometer-button",
            0xCC: "ONiO-Magnetometer"
        }

    def execute(self, api: ApiBackend) -> None:
        """Start continuous scanning if not already active"""
        if self.plugin_active:
            return
        self.plugin_active = True
        self.stop_event.clear()
        self.scan_thread = threading.Thread(target=lambda: asyncio.run(self.continuous_scan()))
        self.scan_thread.start()

    async def continuous_scan(self):
        """Continuously scan for ONiO devices"""
        logging.info("Starting continuous BLE scan for ONiO devices...")
        
        def detection_callback(device, advertising_data):
            """Callback function when a device is detected"""
            try:
                if self.filter_device(advertising_data):
                    logging.debug(f"Found ONiO device: {device.address}")
                    self.process_advertisement(device, advertising_data)
            except Exception as e:
                logging.error(f"Error in detection callback: {e}")

        try:
            self.scanner = BleakScanner(detection_callback=detection_callback)
            while not self.stop_event.is_set():
                await self.scanner.start()
                await asyncio.sleep(5)
                await self.scanner.stop()
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Error in continuous scan: {e}")
        finally:
            self.plugin_active = False
            if self.scanner:
                await self.scanner.stop()
            logging.info("Continuous BLE scan stopped")

    def filter_device(self, adv_data) -> bool:
        """Filter devices looking for FE E5 pattern in manufacturer data"""
        try:
            if adv_data.manufacturer_data:
                # Concatenate manufacturer ID and data just like in ble.py
                manufacturer_data_bytes = b''
                for key, value in adv_data.manufacturer_data.items():
                    manufacturer_data_bytes += bytes([key & 0xFF, key >> 8]) + value
                
                # Now search for pattern in complete manufacturer data
                for i in range(len(manufacturer_data_bytes) - 2):
                    if (manufacturer_data_bytes[i] == 0xFE and 
                        manufacturer_data_bytes[i + 1] == 0xE5 and 
                        manufacturer_data_bytes[i + 2] in self.DEVICE_TYPES):
                        return True
            return False
        except Exception as e:
            logging.error(f"Error in filter_device: {e}")
            return False

    def process_advertisement(self, device, advertising_data):
        """Process advertisement data from an ONiO device"""
        try:
            manufacturer_data_bytes = b''
            for key, value in advertising_data.manufacturer_data.items():
                manufacturer_data_bytes += bytes([key & 0xFF, key >> 8]) + value
            
            for i in range(len(manufacturer_data_bytes) - 2):
                if (manufacturer_data_bytes[i] == 0xFE and 
                    manufacturer_data_bytes[i + 1] == 0xE5 and 
                    manufacturer_data_bytes[i + 2] in self.DEVICE_TYPES):
                    
                    device_type = manufacturer_data_bytes[i + 2]
                    data_payload = manufacturer_data_bytes[i + 3:]
                    self.process_onio_data(device, device_type, data_payload, advertising_data.rssi)
                    return

        except Exception as e:
            logging.error(f"Error processing advertisement: {e}")

    def process_onio_data(self, device, device_type, data_payload, rssi):
        """Process ONiO device advertisement data"""
        try:
            device_addr = device.address
            device_name = self.DEVICE_TYPES.get(device_type, f"Unknown-ONiO-{device_type:02x}")

            # Create device if it doesn't exist
            if device_addr not in self.devices:
                new_device = self.Device(
                    mac_address=device_addr,
                    device_name=device_name
                )
                self.devices[device_addr] = new_device

            # Process data payload based on device type
            processed_data = {
                'raw_data': [hex(b) for b in data_payload],
                'rssi': rssi,
                'device_type': device_name
            }

            if device_type == 0xAA:  # Blomsterpinne
                if len(data_payload) >= 4:
                    processed_data.update({
                        'temperature': int.from_bytes(data_payload[0:2], byteorder='little') / 100,
                        'humidity': data_payload[2],
                        'battery': data_payload[3]
                    })
            
            elif device_type in [0xBB, 0xCC]:  # ONiO-Knapp variants
                if len(data_payload) >= 2:
                    processed_data.update({
                        'button_state': data_payload[0],
                        'battery': data_payload[1]
                    })

            # Update device data
            self.devices[device_addr].update_data(processed_data)
            logging.info(f"DATA: {device_name} ({device_addr}): {processed_data['raw_data']}")

        except Exception as e:
            logging.error(f"Error processing ONiO data: {e}")

    def stop_scanning(self):
        """Stop the continuous scanning"""
        self.stop_event.set()
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join()
        self.plugin_active = False

    def display_devices(self) -> None:
        """Display all discovered ONiO devices"""
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")
            if device.last_data:
                logging.info(f"    Last data: {device.last_data}")

    class SearchableDevice(PluginInterface.SearchableDeviceInterface):
        def __init__(self):
            self.protocol = "BLE"
            self.scan_filter_method = "advertisement_data"
            self.scan_filter = bytes([0xFE, 0xE5])

    class Device(PluginInterface.DeviceInterface):
        def __init__(self, mac_address, device_name):
            self.manufacturer = "ONiO"
            self.mac_address = mac_address
            self.ip = ""
            self.device_name = device_name
            self.device_type = "onio-device"
            self.model_no = "onio-1"
            self.serial_no = mac_address.replace(':', '')
            self.com_protocol = "BLE"
            self.firmware = "1.0.0"
            self.device_description = f'ONiO {device_name} Sensor'
            self.last_data = None
            self.last_update = None

        def update_data(self, data):
            """Update device data and timestamp"""
            self.last_data = data
            self.last_update = datetime.now()

    def __del__(self):
        """Cleanup when plugin is destroyed"""
        self.stop_scanning()