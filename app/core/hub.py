

import time
import threading
import importlib
import os
import logging
import asyncio
from hashlib import md5
from config.config import ConfigSettings
from core.wifi import WifiManager
from core.ble import BLEManager
from core.backend import ApiBackend
from core.flow import Flow

class Hub:
    def __init__(self, ssid, password, serial_no):
        self.config = ConfigSettings()
        self.plugin_dir = "plugins"
        self.plugins = []

        self.serial = serial_no
        self.serial_hash = md5(self.serial.encode()).hexdigest() # Hash the serial number for security
        
        self.wifi = WifiManager()
        self.api = ApiBackend()
        self.ble = BLEManager()
        self.flow = Flow()
        
        # Get wifi credentials from config file if not provided by cli
        self.ssid = ssid if ssid != '' else self.config.get('settings', 'wifi_ssid')
        self.password = password if password != '' else self.config.get('settings', 'wifi_password')
        self.command = ""
        
        self.load_plugin("null") # Sensor emulator plugin 
        # self.load_plugin("philips_hue") # Philips hue experimental plugin 
        # self.load_plugin("xiaomi") # Xiaomi experimental plugin
        # self.load_plugin("flic") # Flic plugin

    def startup(self):
        # Connect to wifi
        # deal with wifi AP to get wifi credentials

        if not self.wifi.connected:
            self.wifi.connect(self.ssid, self.password)
        
        # Disable this to avoid unnecessary geolocation requests and costs.
        # local_ap_list = self.wifi.scan_wifi_networks()
        # if local_ap_list is not None:
        #     if self.api.gapi_geolocation(local_ap_list):
        #         logging.info("Successfully geolocated with Google API")
        #     else:
        #         logging.error("Failed to get location from Google API")

            
        if self.api.get_token(self.serial_hash): 
            logging.info("Successfully retrieved token from server")

        if self.api.set_location(): 
            logging.info("Successfully updated hub location")

        if self.flow.set_flow(self.api.get_flow()):
            logging.info("Successfully retrieved flow")

        logging.info("Startup complete... Beginning main routine\n")
        return True
    

    def loop(self, auto_collect, period=5):
            
        while True:
            try:                
                if self.command == "rebooting":
                    logging.info("Rebooting...")
                    self.shutdown()
                    self.startup()

                elif self.command == "scan_devices":
                    for plugin in self.plugins:
                        if plugin.protocol == 'BLE':
                            asyncio.run(self.ble.scan_by_plugin(plugin, timeout=10))
                            
                        elif plugin.protocol == 'WiFi':
                            pass
                        elif plugin.protocol == 'Zigbee':
                            pass
                        elif plugin.protocol == 'Zwave':
                            pass


                    if not self.api.post_scan_results(self.plugins):
                        logging.error("Failed to post scan results")

                    logging.info("Scan complete... Returning to main routine\n")
                    

                elif self.command == "":
                    # if auto_collect:
                    logging.debug("Automatically executing plugins")
                    self.execute_plugins()
                
                self.command = ""
                time.sleep(period)
                self.command = self.api.ping_server()
                


            except KeyboardInterrupt:
                logging.warning("Keyboard Interrupt")
                break
        
        return
            
        

    def shutdown(self):
        # Disconnect from wifi
        # Disconnect from bluetooth
        # Disconnect from server
        pass


    def display_devices(self):
        for plugin in self.plugin_manager.plugins:
            plugin.display_devices()


    def load_plugin(self, plugin_name):
        module = importlib.import_module(f"{self.plugin_dir}.{plugin_name}")
        if not hasattr(module, plugin_name):
            logging.error(f"Plugin not found: {plugin_name}")
            return
        plugin_class = getattr(module, plugin_name)
        plugin = plugin_class()
        self.plugins.append(plugin)
        logging.info("Plugin loaded: " + str(plugin.__class__.__name__))



    def execute_plugins(self):
        for plugin in self.plugins:
            thread = threading.Thread(target=plugin.execute, args=(self.api,))
            thread.start()
