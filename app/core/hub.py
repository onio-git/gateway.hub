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


class Hub:
    def __init__(self, serial_no):
        self.config = ConfigSettings()
        self.plugin_dir = "plugins"
        self.plugins = []

        self.serial = serial_no
        self.serial_hash = md5(self.serial.encode()).hexdigest()  # Hash the serial number for security

        self.api = ApiBackend()
        self.ble = BLEManager()
        self.flow = Flow()

        self.command = ""
        self.meta_data = ""

        # Load plugins
        # Comment out the plugins you don't want to load
        # Will later be managed by API ()
        # self.load_plugin("null") # Sensor emulator plugin
        self.load_plugin("philips_hue")  # Philips hue experimental plugin
        # self.load_plugin("xiaomi") # Xiaomi experimental plugin
        # self.load_plugin("flic") # Flic plugin

    def startup(self):

        # Disable this to avoid unnecessary geolocation requests and costs.
        # local_ap_list = self.wifi.scan_wifi_networks()
        # if local_ap_list is not None:
        #     if self.api.gapi_geolocation(local_ap_list):
        #         logging.info("Successfully geolocated with Google API")
        #     else:
        #         logging.error("Failed to get location from Google API")
        logging.info("hash serial: " + self.serial_hash)
        if self.api.get_token(self.serial_hash):
            logging.info("Successfully retrieved token from server")

        if self.api.set_location():
            logging.info("Successfully updated hub location")

        if self.flow.set_flow(self.api.get_flow()):
            logging.info("Successfully retrieved flow")

        logging.info("Startup complete... Beginning main routine\n")
        return True

    def loop(self, auto_collect, period=5):

        # Initial scan
        self.scan_for_devices()

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

                # elif self.command == "turn-off":
                #     logging.info("Turn off something")
                #     self.execute_plugins()
                #     # pass
                #
                # elif self.command == "turn-on":
                #     logging.info("Turn on something")
                #     self.execute_plugins()
                #     # pass

                elif self.command == "execute-flow":
                    logging.info("Execute something")
                    self.execute_plugins()

                elif self.command == "":
                    # if auto_collect:
                    logging.debug("Automatically executing plugins")
                    self.execute_plugins()
                    pass

                self.command = ""
                time.sleep(period)
                logging.info(f"Pinging server...: {self.serial_hash}")
                logging.info("Serial number: " + self.serial)
                [self.command, self.meta_data] = self.api.ping_server(self.serial_hash)



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
        module = importlib.import_module(f"{self.plugin_dir}.{plugin_name}")
        if not hasattr(module, plugin_name):
            logging.error(f"Plugin not found: {plugin_name}")
            return
        plugin_class = getattr(module, plugin_name)
        plugin = plugin_class()
        self.plugins.append(plugin)
        logging.info("Plugin loaded: " + str(plugin.__class__.__name__))

    def scan_for_devices(self):
        for plugin in self.plugins:
            if plugin.protocol == 'BLE':
                asyncio.run(self.ble.scan_by_plugin(plugin, timeout=10))

            elif plugin.protocol == 'WiFi':
                pass
            elif plugin.protocol == 'Zigbee':
                pass
            elif plugin.protocol == 'Zwave':
                pass

    def execute_plugins(self):
        for plugin in self.plugins:
            thread = threading.Thread(target=plugin.execute, args=(self.api, self.command, self.meta_data))
            thread.start()
