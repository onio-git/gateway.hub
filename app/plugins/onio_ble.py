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
import dbus

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
        self.SCAN_DURATION = 0.3
        self.PAUSE_DURATION = 0.1
        self.RECOVERY_DELAY = 1
        self._scan_count = 0
        self._is_cleaning = False
        self._active_scan = None
        self._dbus_reconnect_threshold = 500  # Reconnect after this many scans
        self._current_scan_count = 0
        
        self.DEVICE_TYPES = {
            0xAA: "Blomsterpinne",
            0xBB: "ONiO-Accelerometer-button",
            0xCC: "ONiO-Magnetometer"
        }
        self.api = api
        self.flow = flow


    async def reset_dbus_connection(self):
        """Reset D-Bus connection to clear pending replies"""
        logging.info("Resetting D-Bus connection...")
        try:
            if self.scanner:
                await self.cleanup_scanner()
            
            # Force disconnect from D-Bus
            bus = dbus.SystemBus()
            bus.close()
            
            # Small delay to ensure cleanup
            await asyncio.sleep(2)
            
            # Reset Bluetooth adapter
            await self.reset_bluetooth_async()
            
            self._current_scan_count = 0
            self.scan_failures = 0
            return True
        except Exception as e:
            logging.error(f"Failed to reset D-Bus connection: {e}")
            return False


    async def reset_bluetooth_async(self):
        """Asynchronous version of bluetooth reset"""
        def _reset():
            try:
                subprocess.run(['sudo', 'hciconfig', 'hci0', 'down'], check=True, stdout=subprocess.DEVNULL)
                time.sleep(1)
                subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], check=True, stdout=subprocess.DEVNULL)
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to reset Bluetooth adapter: {e}")
                return False

        return await asyncio.to_thread(_reset)


    def associate_flow_node(self, device=None):
        # Special case for ONiO BLE plugin. Associate flow nodes with device types
        for node in self.flow.flow_table:
            if node.node_name == "onio-btn-when":
                node.function = self.onio_btn_when


    def execute(self) -> None:
        if self.active:
            return
        
        self.active = True
        self.associate_flow_node()
        self.stop_event.clear()
        self.scan_thread = threading.Thread(
            target=lambda: asyncio.run(self.scanning_loop()),
            name="ONiO-BLE-Scanner"
        )
        self.scan_thread.daemon = True
        self.scan_thread.start()

    async def scanning_loop(self):
        """Main scanning loop with better resource management"""
        logging.info("Starting ONiO BLE scanning loop...")
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                if current_time - self.last_scan_time >= self.SCAN_DURATION + self.PAUSE_DURATION:
                    # Preventive D-Bus reset if needed
                    if self._current_scan_count >= self._dbus_reconnect_threshold:
                        logging.info("Performing preventive D-Bus connection reset...")
                        if await self.reset_dbus_connection():
                            self._current_scan_count = 0
                            await asyncio.sleep(1)  # Reduced sleep time
                            continue
                    
                    # Quick scan cycle with shorter timeout
                    try:
                        async with asyncio.timeout(3):  # Reduced from 10s to 3s
                            await self.scan_cycle()
                            self._current_scan_count += 1
                    except asyncio.TimeoutError:
                        logging.error("Scan cycle timeout - resetting")
                        await self.force_reset()  # New method for aggressive cleanup
                        continue
                    
                    self.last_scan_time = current_time
                
                await asyncio.sleep(self.PAUSE_DURATION)

            except asyncio.CancelledError:
                logging.info("Scan loop cancelled")
                break
            except Exception as e:
                logging.error(f"Error in scanning loop: {e}")
                self.scan_failures += 1
                
                if self.scan_failures >= self.MAX_FAILURES:
                    await self.force_reset()
                else:
                    await asyncio.sleep(self.PAUSE_DURATION)

        await self.cleanup()
        self.active = False

    async def scan_cycle(self):
        """Optimized scan cycle with better resource management"""
        if self.processing_lock.locked():
            return

        async with self.processing_lock:
            try:
                # Always ensure clean scanner state
                await self.cleanup_scanner()
                
                # Create and start scanner with timeout
                self.scanner = BleakScanner(detection_callback=self.detection_callback)
                try:
                    async with asyncio.timeout(1.0):  # Short timeout for scanner start
                        await self.scanner.start()
                except asyncio.TimeoutError:
                    logging.error("Scanner start timeout")
                    await self.cleanup_scanner()
                    return
                
                # Short scan duration
                await asyncio.sleep(self.SCAN_DURATION)
                
                # Clean stop with timeout
                await self.cleanup_scanner()
                self.scan_failures = 0
                
            except BleakError as e:
                if "LimitsExceeded" in str(e):
                    logging.error("D-Bus connection limits exceeded")
                    await self.force_reset()
                else:
                    logging.error(f"Bleak error during scan: {e}")
                    self.scan_failures += 1
                await self.cleanup_scanner()
            except Exception as e:
                logging.error(f"Error in scan cycle: {e}")
                self.scan_failures += 1
                await self.cleanup_scanner()

    async def cleanup_scanner(self):
        """More aggressive scanner cleanup"""
        if self.scanner:
            try:
                async with asyncio.timeout(1.0):  # Reduced timeout
                    await self.scanner.stop()
            except (asyncio.TimeoutError, Exception) as e:
                logging.error(f"Scanner stop error: {e}")
            finally:
                self.scanner = None

    async def force_reset(self):
        """Aggressive reset for recovery from bad states"""
        logging.info("Performing aggressive reset...")
        await self.cleanup_scanner()
        
        # Reset D-Bus
        await self.reset_dbus_connection()
        
        # Reset counters
        self.scan_failures = 0
        self._current_scan_count = 0
        self.last_scan_time = 0
        
        # Short recovery pause
        await asyncio.sleep(1)

    async def cleanup(self):
        """Clean shutdown"""
        await self.cleanup_scanner()
        if hasattr(self, 'bus') and self.bus:
            try:
                self.bus.close()
            except:
                pass
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
                logging.info("Stopping scan thread...")
                self.scan_thread.join(timeout=5.0)
            except Exception as e:
                logging.error(f"Error stopping scan thread: {e}")
        self.active = False

    def __del__(self):
        logging.info("ONiO BLE plugin object deleted")
        self.stop_scanning()


    def display_devices(self) -> None:
        """Display discovered devices"""
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")
            if device.last_data:
                logging.info(f"    Last data: {device.last_data}")


    async def onio_btn_when(self, data) -> bool:
        """ONiO Button When node function"""
        if data.get('button_state') == 1:
            logging.info("Button pressed!")
            return True
        return False






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

