import logging
from core.plugin_interface import PluginInterface
from config.config import ConfigSettings as config
from datetime import datetime
from math import sin, cos, pi
from core.backend import ApiBackend
from core.flow import Flow
import random
from hashlib import md5
import yaml
import os
import time

from typing import Dict, Any
import threading
from queue import Queue, Empty

class null(PluginInterface):
    def __init__(self, api: ApiBackend, flow: Flow):
        self.protocol = "BLE"
        self.devices = {}
        self.config = config()
        self.api = api
        self.flow = flow
        self.active = False

        self.device_queue = Queue()
        self.workers = []

        # Read the sensor configuration file path from the main config
        config_file_path = self.config.get('settings', 'sensor_config_file')

        # Load sensor configurations from the YAML file
        with open(config_file_path, 'r') as f:
            sensor_configs = yaml.safe_load(f)

        for sensor_info in sensor_configs['sensors']:
            device = self.Device(sensor_info)
            self.devices[device.mac_address] = device

    def associate_flow_node(self, device):
        pass

    # Old execute method without queue-based processing
    # def execute(self) -> None:
    #     if not self.active:
    #         logging.info("Starting null plugin")
    #         self.active = True
    #         while True:
    #             for _, device in self.devices.items():
    #                 current_time = datetime.now()
    #                 if device.last_execution_time is None or \
    #                 (current_time - device.last_execution_time).total_seconds() >= device.interval:
    #                     device.generate_emulated_data()
    #                     device.last_execution_time = current_time
    #                     logging.debug(f"Data from {device.device_name}: {device.data}")
    #                     try:
    #                         jsn_data = {
    #                             "devid": device.mac_address,
    #                             "gtwid": self.config.get('settings', 'hub_serial_no'),
    #                             "gtwtime": current_time.strftime("%Y-%m-%dT%H:%M:%S"),
    #                             "orgid": 111111,
    #                             "primary": {
    #                                 "type": "raw",
    #                                 "value": [
    #                                     round(device.data['data']['temperature'], 2),
    #                                     round(device.data['data']['humidity'], 2),
    #                                     round(device.data['data']['energy'], 2),
    #                                     round(device.data['data']['brightness'], 2),
    #                                     round(device.data['data']['conductivity'], 2)
    #                                 ]
    #                             }
    #                         }
    #                         self.api.send_collected_data(jsn_data)
    #                     except Exception as e:
    #                         logging.error(f"Error sending data to API: {str(e)}")
    #             time.sleep(1)

    def queue_worker(self, queue: Queue) -> None:
        """Worker thread that processes devices from the queue"""
        while self.active:
            try:
                device, current_time = queue.get(timeout=1.0)
                
                try:
                    device.generate_emulated_data()
                    device.last_execution_time = current_time
                    
                    jsn_data = self.prepare_json_data(device, current_time)
                    
                    self.api.send_collected_data(jsn_data)
                    logging.debug(f"Data from {device.device_name}: {device.data}")
                    
                except Exception as e:
                    logging.error(f"Error processing device {device.device_name}: {str(e)}")
                
                finally:
                    queue.task_done()
                    
            except Empty:
                continue

            except Exception as e:
                logging.error(f"Worker thread error: {str(e)}")
                time.sleep(1)  # Prevent tight loop in case of repeated errors


    # New execute method with queue-based processing
    def execute(self) -> None:
        """Main execution loop using queue-based processing"""
        if not self.active:
            logging.info("Starting null plugin with queue-based processing")
            self.active = True
            
            # Create worker threads
            num_workers = min(4, len(self.devices))
            self.workers = []
            
            # Start worker threads
            for i in range(num_workers):
                worker = threading.Thread(
                    target=self.queue_worker,
                    args=(self.device_queue,),
                    name=f"DeviceWorker-{i}"
                )
                worker.daemon = True
                worker.start()
                self.workers.append(worker)
            
            logging.info(f"Started {num_workers} worker threads")
            
            # Main loop
            try:
                while self.active:
                    current_time = datetime.now(tz=None)
                    
                    # Add devices that need processing to the queue
                    for device in self.devices.values():
                        if device.last_execution_time is None or \
                        (current_time - device.last_execution_time).total_seconds() >= device.interval:
                            self.device_queue.put((device, current_time))
                    
                    time.sleep(1)
                    
            except Exception as e:
                logging.error(f"Main loop error: {str(e)}")
                self.active = False
                
            finally:
                # Cleanup when stopping
                self.stop()


    def stop(self) -> None:
        """Stop the plugin and clean up resources"""
        logging.info("Stopping null plugin")
        self.active = False
        
        # Wait for queue to be empty
        self.device_queue.join()
        
        # Stop worker threads
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=5.0)
        
        self.workers = []
        logging.info("Null plugin stopped")


    def prepare_json_data(self, device: Any, current_time: datetime) -> Dict:
        return {
            "devid": device.mac_address,
            "gtwid": self.config.get('settings', 'hub_serial_no'),
            "gtwtime": current_time.isoformat(),
            "orgid": 111111,
            "primary": {
                "type": "raw",
                "value": [
                    round(device.data['data']['temperature'], 2),
                    round(device.data['data']['humidity'], 2),
                    round(device.data['data']['energy'], 2),
                    round(device.data['data']['brightness'], 2),
                    round(device.data['data']['conductivity'], 2)
                ]
            }
        }


    def display_devices(self) -> None:
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")


    class SearchableDevice(PluginInterface.SearchableDeviceInterface):
        def __init__(self):
            self.protocol = "BLE"
            self.scan_filter_method = "emulator"
            self.scan_filter = "none"


    class Device(PluginInterface.DeviceInterface):
        def __init__(self, sensor_info):
            self.config = config()
            self.manufacturer = "ONiO"
            self.ip = ""
            self.mac_address = sensor_info['address']
            self.serial_no = sensor_info['serial_no']
            self.model_no = sensor_info['model_no']
            self.device_name = sensor_info['name']
            self.com_protocol = "BLE"
            self.firmware = sensor_info.get('firmware', "1.0.0")
            self.device_description = sensor_info['description']
            self.interval = sensor_info.get('interval', 10)
            self.last_execution_time = None

            # Data patterns
            self.data_patterns = sensor_info.get('data', {})
            self.data_point_types = list(self.data_patterns.keys())

            self.data = {
                "device_id": self.mac_address,
                "device_name": self.device_name,
                "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "firmware": self.firmware,
                "data": {
                    "temperature": 0,
                    "humidity": 0,
                    "energy": 0,
                    "brightness": 0,
                    "conductivity": 0
                }
            }


        def generate_emulated_data(self) -> None:
            current_time = datetime.now()
            for data_point, data_info in self.data_patterns.items():
                pattern = data_info['pattern']
                params = data_info['params']
                value = self.generate_value(pattern, params, current_time)
                self.data['data'][data_point] = value
            self.data['timestamp'] = current_time.strftime("%Y-%m-%dT%H:%M:%S")


        def generate_value(self, pattern, params, current_time):
            time_unit = params.get('time_unit', 'seconds')
            noise = params.get('noise', 0)

            # Convert time to appropriate units
            if time_unit == 'seconds':
                time_value = current_time.timestamp()
            elif time_unit == 'minutes':
                time_value = current_time.timestamp() / 60
            elif time_unit == 'hours':
                time_value = current_time.timestamp() / 3600
            else:
                time_value = current_time.timestamp()

            if pattern == 'sinus':
                offset = params.get('offset', 0)
                amplitude = params.get('amplitude', 1)
                period = params.get('period', 1)
                value = offset + amplitude * sin(2 * pi * time_value / period)
            elif pattern == 'cosine':
                offset = params.get('offset', 0)
                amplitude = params.get('amplitude', 1)
                period = params.get('period', 1)
                value = offset + amplitude * cos(2 * pi * time_value / period)
            elif pattern == 'square':
                min_value = params.get('min_value', 0)
                max_value = params.get('max_value', 1)
                period = params.get('period', 1)
                cycle = int(time_value / (period / 2)) % 2
                value = max_value if cycle == 0 else min_value
            elif pattern == 'sawtooth':
                min_value = params.get('min_value', 0)
                max_value = params.get('max_value', 1)
                period = params.get('period', 1)
                fraction = (time_value % period) / period
                value = min_value + (max_value - min_value) * fraction
            elif pattern == 'pyramid':
                min_value = params.get('min_value', 0)
                max_value = params.get('max_value', 1)
                period = params.get('period', 1)
                half_period = period / 2
                time_in_period = time_value % period
                if time_in_period < half_period:
                    fraction = time_in_period / half_period
                    value = min_value + (max_value - min_value) * fraction
                else:
                    fraction = (time_in_period - half_period) / half_period
                    value = max_value - (max_value - min_value) * fraction
            else:
                value = 0  # Default value for unknown patterns

            return value
