

import time
import threading
import importlib
import subprocess
import os
import logging
import asyncio
from hashlib import md5
from config.config import ConfigSettings
from core.ble import BLEManager
from core.backend import ApiBackend
from core.flow import Flow
from log.log import CloudLogger

class Hub:
    def __init__(self, serial_no):
        self.config = ConfigSettings()
        self.cloud_logger = CloudLogger()
        self.plugin_dir = "plugins"
        self.plugins = []

        self.serial = serial_no
        self.serial_hash = md5(self.serial.encode()).hexdigest() # Hash the serial number for security
        
        self.api = ApiBackend()
        self.ble = BLEManager()
        self.flow = Flow()
        
        self.command = ""
        

        # Load plugins
        # Comment out the plugins you don't want to load
        # Will later be managed by API 


        # These are loaded from the plugins.txt file. And can be managed by commands from the server
        # self.load_plugin("null") # Sensor emulator plugin 
        # self.load_plugin("onio_ble") # ONiO BLE plugin
        # self.load_plugin("philips_hue") # Philips hue experimental plugin 
        # self.load_plugin("xiaomi") # Xiaomi experimental plugin
        # self.load_plugin("sonos") # Sonos plugin
        # self.load_plugin("flic") # Flic plugin (no work)

    def startup(self):
        self.get_plugins_from_file()


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
        self.cloud_logger.add_log_line("SYSTEM", "Startup complete... Beginning main routine")
        return True
    

    def loop(self, auto_collect, period=5):

        # Initial scan
        self.scan_for_devices()
        get_flow_delay = 0

        while True:
            try:                
                if self.command == "rebooting":
                    logging.info("Rebooting...")
                    self.shutdown()

                elif self.command == "scan_devices":
                    self.scan_for_devices()


                    if not self.api.post_scan_results(self.plugins):
                        logging.error("Failed to post scan results")

                    logging.info("Scan complete... Returning to main routine\n")

                    

                elif self.command == "":
                    # if auto_collect:
                    logging.debug("Automatically executing plugins")
                    self.execute_plugins()
                    pass

                elif self.command.startswith("load_plugin"):
                    plugin_name = self.command.split(":")[1]
                    self.load_plugin(plugin_name)

                elif self.command.startswith("unload_plugin"):
                    plugin_name = self.command.split(":")[1]
                    for plugin in self.plugins:
                        if plugin.__class__.__name__ == plugin_name:
                            self.plugins.remove(plugin)
                            logging.info("Plugin unloaded: " + plugin_name)
                            break

                
                self.command = ""
                time.sleep(period)
                self.command = self.api.ping_server(self.serial_hash, self.cloud_logger.format_logs_to_json())

                # Get flow every 50 cycles. This should be replaced by
                # a command from the server whenever a new flow is activated
                if get_flow_delay > 50:
                    if self.flow.set_flow(self.api.get_flow()):
                        logging.info("Successfully retrieved flow")
                    get_flow_delay = 0
                else:
                    get_flow_delay += 1
                


            except KeyboardInterrupt:
                logging.warning("Keyboard Interrupt")
                break
        
        return
            
        

    def shutdown(self):
        logging.info("Shutting down...")
        subprocess.run(['sudo', 'reboot'])
        pass


    def display_devices(self):
        for plugin in self.plugin_manager.plugins:
            plugin.display_devices()


    def load_plugin(self, plugin_name):
        # Write plugin name as a new line in the plugins.txt file if the plugin is not already in the file
        with open("plugins.txt", "r") as f:
            if plugin_name not in f.read():
                with open("plugins.txt", "a") as f:
                    f.write(plugin_name)
                    f.write("\n")
        try:
            module = importlib.import_module(f"{self.plugin_dir}.{plugin_name}")
            if not hasattr(module, plugin_name):
                logging.error(f"Plugin not found: {plugin_name}")
                return
            plugin_class = getattr(module, plugin_name)
            plugin = plugin_class(api=self.api, flow=self.flow)
            self.plugins.append(plugin)
        except ModuleNotFoundError:
            logging.error(f"Plugin not found: {plugin_name}")
            return
        logging.info("Plugin loaded: " + str(plugin.__class__.__name__))


    def unload_plugin(self, plugin_name):
        for plugin in self.plugins:
            if plugin.__class__.__name__ == plugin_name:
                self.plugins.remove(plugin)
                logging.info("Plugin unloaded: " + plugin_name)
                # Remove plugin name from plugins.txt
                with open("plugins.txt", "r") as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if line == plugin_name:
                            lines.pop(i)
                            break
                
                with open("plugins.txt", "w") as f:
                    f.writelines(lines)
                return
            

    def get_plugins_from_file(self):
        with open("plugins.txt", "r") as f:
            plugins = f.readlines()
            for plugin in plugins:
                if plugin.startswith("#"):
                    continue
                self.load_plugin(plugin.strip())
        return


    def scan_for_devices(self):
        for plugin in self.plugins:
            if plugin.protocol == 'BLE':
                asyncio.run(self.ble.discover(plugin, timeout=5))
                
            elif plugin.protocol == 'WiFi':
                plugin.discover()
                

            elif plugin.protocol == 'Zigbee':
                pass
            elif plugin.protocol == 'Zwave':
                pass


    def execute_plugins(self):
        for plugin in self.plugins:
            if plugin.active:
                continue
            thread = threading.Thread(target=plugin.execute)
            thread.start()
