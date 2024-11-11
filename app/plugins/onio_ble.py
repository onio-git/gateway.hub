import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from core.flow import Flow
from bleak import BleakScanner
from datetime import datetime
import asyncio
import threading

class onio_ble(PluginInterface):
    def __init__(self, api: ApiBackend, flow: Flow):
        self.protocol = "BLE"
        self.devices = {}
        self.plugin_active = False
        self.scanner = None
        self.scan_thread = None
        self.stop_event = threading.Event()
        
        # Synchronization for BLE operations
        self.processing_lock = asyncio.Lock()
        self.scan_task = None
        
        # ONiO device types based on identifier bytes
        self.DEVICE_TYPES = {
            0xAA: "Blomsterpinne",
            0xBB: "ONiO-Accelerometer-button",
            0xCC: "ONiO-Magnetometer"
        }
        self.api = api
        self.flow = flow

    def associate_flow_node(self, device):
        pass

    def execute(self) -> None:
        """Start continuous scanning if not already active"""
        if self.plugin_active:
            return
        
        self.plugin_active = True
        self.stop_event.clear()
        self.scan_thread = threading.Thread(target=lambda: asyncio.run(self.scanning_loop()))
        self.scan_thread.start()

    async def scanning_loop(self):
        """Main scanning loop"""
        logging.info("Starting ONiO BLE scanning loop...")
        
        while not self.stop_event.is_set():
            try:
                await self.scan_cycle()
                await asyncio.sleep(0.5)  # Brief pause between cycles
            except Exception as e:
                logging.error(f"Error in scanning loop: {e}")
                await asyncio.sleep(0.5)  # Wait before retrying

        logging.info("ONiO BLE scanning loop stopped")
        self.plugin_active = False

    async def scan_cycle(self):
        """Single scan cycle with proper cleanup"""
        if self.processing_lock.locked():
            return

        async with self.processing_lock:
            try:
                self.scanner = BleakScanner(detection_callback=self.detection_callback)
                await self.scanner.start()
                await asyncio.sleep(3)  # Scan duration
                await self.scanner.stop()
                self.scanner = None
            except Exception as e:
                logging.error(f"Error in scan cycle: {e}")
                if self.scanner:
                    try:
                        await self.scanner.stop()
                    except:
                        pass
                    self.scanner = None

    async def detection_callback(self, device, advertising_data):
        """Handle detected BLE devices"""
        try:
            if not self.filter_device(advertising_data):
                return

            logging.debug(f"Found ONiO device: {device.address}")
            
            # Stop current scan before processing
            if self.scanner:
                try:
                    await self.scanner.stop()
                    self.scanner = None
                except Exception as e:
                    logging.debug(f"Error stopping scanner: {e}")

            # Process the advertisement
            await self.process_device_data(device, advertising_data)

        except Exception as e:
            logging.error(f"Error in detection callback: {e}")

    def filter_device(self, adv_data) -> bool:
        """Filter for ONiO devices"""
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
        """Process data from ONiO device"""
        async with self.processing_lock:  # Ensure exclusive access during processing
            try:
                manufacturer_data_bytes = b''
                for key, value in advertising_data.manufacturer_data.items():
                    manufacturer_data_bytes += bytes([key & 0xFF, key >> 8]) + value

                for i in range(len(manufacturer_data_bytes) - 2):
                    if (manufacturer_data_bytes[i] == 0xFE and 
                        manufacturer_data_bytes[i + 1] == 0xE5 and 
                        manufacturer_data_bytes[i + 2] in self.DEVICE_TYPES):
                        logging.info(f"Processing ONiO device data: {device.address}")
                        
                        device_type = manufacturer_data_bytes[i + 2]
                        data_payload = manufacturer_data_bytes[i + 3:]
                        
                        # Create or get device
                        device_addr = device.address
                        device_name = self.DEVICE_TYPES.get(device_type, f"Unknown-ONiO-{device_type:02x}")
                        
                        if device_addr not in self.devices:
                            self.devices[device_addr] = self.Device(device_addr, device_name)

                        # Process data based on device type
                        processed_data = {
                            'raw_data': [hex(b) for b in data_payload],
                            'rssi': advertising_data.rssi,
                            'device_type': device_name
                        }

                        if device_type == 0xAA:  # Blomsterpinne
                            if len(data_payload) >= 4:
                                processed_data.update({
                                    'humidity': data_payload[2],
                                })
                        
                        elif device_type in [0xBB, 0xCC]:  # ONiO-Knapp variants
                            if len(data_payload) >= 2:
                                z = int(data_payload[3].to_bytes(1, 'big').hex(), 16)
                                processed_data.update({
                                    'button_state': data_payload[0],
                                    # get 2s complement of the 4th byte. convert to int
                                    'z_acceleration': z if z < 128 else z - 256,
                                })

                        # Send data to flow
                        await self.flow.receive_device_data_to_flow(device_addr, processed_data)
                        
                        # Update device data
                        self.devices[device_addr].update_data(processed_data)
                        return  # Process only the first valid pattern found

            except Exception as e:
                logging.error(f"Error processing device data: {e}")
            finally:
                await asyncio.sleep(1)  # Brief pause before allowing next operation

    def stop_scanning(self):
        """Stop scanning gracefully"""
        self.stop_event.set()
        if self.scan_thread and self.scan_thread.is_alive() and self.scan_thread != threading.current_thread():
            try:
                self.scan_thread.join(timeout=2)
            except Exception as e:
                logging.error(f"Error stopping scan thread: {e}")
        self.plugin_active = False

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