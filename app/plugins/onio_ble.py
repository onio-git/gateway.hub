import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from core.flow import Flow
from bleak import BleakScanner, BleakError
from datetime import datetime
import asyncio
import threading
import subprocess
import time

class onio_ble(PluginInterface):
    def __init__(self, api: ApiBackend, flow: Flow):
        self.protocol = "BLE"
        self.devices = {}
        self.active = False
        self.scanner = None
        self.scan_thread = None
        self.stop_event = threading.Event()
        self.processing_lock = asyncio.Lock()
        self.last_scan_time = 0
        self.scan_failures = 0
        self.MAX_FAILURES = 3
        self.SCAN_DURATION = 1.5
        self.PAUSE_DURATION = 0.2
        self.RECOVERY_DELAY = 10
        
        self.DEVICE_TYPES = {
            0xAA: "Blomsterpinne",
            0xBB: "ONiO-Accelerometer-button",
            0xCC: "ONiO-Magnetometer"
        }
        self.api = api
        self.flow = flow

    def reset_bluetooth(self):
        try:
            logging.info("Resetting Bluetooth adapter...")
            subprocess.run(['sudo', 'hciconfig', 'hci0', 'down'], check=True)
            time.sleep(1)
            subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], check=True)
            time.sleep(2)
            self.scan_failures = 0
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to reset Bluetooth adapter: {e}")
            return False

    def execute(self) -> None:
        if self.active:
            return
        
        self.active = True
        self.stop_event.clear()
        self.scan_thread = threading.Thread(
            target=lambda: asyncio.run(self.scanning_loop()),
            name="ONiO-BLE-Scanner"
        )
        self.scan_thread.daemon = True
        self.scan_thread.start()

    async def scanning_loop(self):
        logging.info("Starting ONiO BLE scanning loop...")
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                if current_time - self.last_scan_time >= self.SCAN_DURATION + self.PAUSE_DURATION:
                    await self.scan_cycle()
                    self.last_scan_time = current_time
                
                await asyncio.sleep(self.PAUSE_DURATION)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in scanning loop: {e}")
                self.scan_failures += 1
                
                if self.scan_failures >= self.MAX_FAILURES:
                    if self.reset_bluetooth():
                        self.scan_failures = 0
                    await asyncio.sleep(self.RECOVERY_DELAY)
                else:
                    await asyncio.sleep(self.PAUSE_DURATION)

        await self.cleanup()
        self.active = False

    async def scan_cycle(self):
        if self.processing_lock.locked():
            return

        async with self.processing_lock:
            try:
                self.scanner = BleakScanner(detection_callback=self.detection_callback)
                scan_task = asyncio.create_task(self.scanner.start())
                
                try:
                    await asyncio.wait_for(scan_task, timeout=self.SCAN_DURATION * 2)
                    await asyncio.sleep(self.SCAN_DURATION)
                except asyncio.TimeoutError:
                    logging.error("Scan operation timed out")
                    raise BleakError("Scan timeout")
                finally:
                    await self.cleanup_scanner()
                
                self.scan_failures = 0
                
            except BleakError as e:
                logging.error(f"Bleak error during scan: {e}")
                self.scan_failures += 1
                await self.cleanup_scanner()
            except Exception as e:
                logging.error(f"Error in scan cycle: {e}")
                self.scan_failures += 1
                await self.cleanup_scanner()

    async def cleanup_scanner(self):
        if self.scanner:
            try:
                await self.scanner.stop()
            except Exception as e:
                logging.error(f"Error stopping scanner: {e}")
            finally:
                self.scanner = None

    async def cleanup(self):
        await self.cleanup_scanner()
        self.active = False
        self.scan_failures = 0
        self.last_scan_time = 0

    async def detection_callback(self, device, advertising_data):
        try:
            if not self.filter_device(advertising_data):
                return

            logging.debug(f"Found ONiO device: {device.address}")
            
            if self.scanner:
                try:
                    await self.scanner.stop()
                    self.scanner = None
                except Exception as e:
                    logging.debug(f"Error stopping scanner: {e}")

            await self.process_device_data(device, advertising_data)

        except Exception as e:
            logging.error(f"Error in detection callback: {e}")

    def filter_device(self, adv_data) -> bool:
        try:
            if not adv_data.manufacturer_data:
                return False

            manufacturer_data_bytes = b''
            for key, value in adv_data.manufacturer_data.items():
                manufacturer_data_bytes += bytes([key & 0xFF, key >> 8]) + value
            
            for i in range(len(manufacturer_data_bytes) - 2):
                if (manufacturer_data_bytes[i] == 0xFE and 
                    manufacturer_data_bytes[i + 1] == 0xE5 and 
                    manufacturer_data_bytes[i + 2] in self.DEVICE_TYPES):
                    return True
            return False
        except Exception as e:
            logging.error(f"Error in filter_device: {e}")
            return False

    async def process_device_data(self, device, advertising_data):
        async with self.processing_lock:
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
                        device_addr = device.address
                        device_name = self.DEVICE_TYPES.get(device_type, f"Unknown-ONiO-{device_type:02x}")
                        
                        if device_addr not in self.devices:
                            self.devices[device_addr] = self.Device(device_addr, device_name)

                        processed_data = await self.process_payload(device_type, data_payload, advertising_data)
                        
                        if processed_data:
                            await self.flow.receive_device_data_to_flow(device_addr, processed_data)
                            self.devices[device_addr].update_data(processed_data)
                        return

            except Exception as e:
                logging.error(f"Error processing device data: {e}")
            finally:
                await asyncio.sleep(1)

    async def process_payload(self, device_type, data_payload, advertising_data):
        try:
            processed_data = {
                'raw_data': [hex(b) for b in data_payload],
                'rssi': advertising_data.rssi,
                'device_type': self.DEVICE_TYPES.get(device_type)
            }

            if device_type == 0xAA and len(data_payload) >= 4:
                processed_data['humidity'] = data_payload[2]
            
            elif device_type in [0xBB, 0xCC] and len(data_payload) >= 2:
                z = int(data_payload[3].to_bytes(1, 'big').hex(), 16)
                processed_data.update({
                    'button_state': data_payload[0],
                    'z_acceleration': z if z < 128 else z - 256,
                })

            return processed_data
        except Exception as e:
            logging.error(f"Error processing payload: {e}")
            return None

    def stop_scanning(self):
        self.stop_event.set()
        if self.scan_thread and self.scan_thread.is_alive():
            try:
                self.scan_thread.join(timeout=5.0)
            except Exception as e:
                logging.error(f"Error stopping scan thread: {e}")
        self.active = False

    def __del__(self):
        self.stop_scanning()


    def display_devices(self) -> None:
        """Display discovered devices"""
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
        """Cleanup"""
        self.stop_scanning()