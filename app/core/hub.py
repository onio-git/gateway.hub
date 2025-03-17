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
import json
from core.mpire_flow import ConfigurableWorkflow
from core.mpire_flow_manager import FlowManager
from concurrent.futures import ThreadPoolExecutor


def _check_type(type_event: str) -> str:
    match type_event:
        case "when":
            type = "Event"
        case "then":
            type = "Action"
        case _:
            type = "Action"
    return type


def _outputs_connection(next_type_output: str, next_node_id: str) -> dict:
    output_connection = {}
    match next_type_output:
        case "Event":
            output_connection.update(
                {"node": next_node_id, "output": "event_name"}
            )
        case "Action":
            output_connection.update(
                {"node": next_node_id, "output": "previous_data"}
            )
    return output_connection


def _flow_etl(flow_json: dict) -> dict:
    ordered_flow = {k: flow_json["flow"][k] for k in sorted(flow_json["flow"].keys(), key=int)}

    logging.info(f"Main Flow: {ordered_flow}")
    new_drawflow = {
        "drawflow": {
            "Home": {
                "data": {}
            }
        }
    }
    for node_id, node_data in ordered_flow.items():
        node_id_int = int(node_id)
        next_node_id = str(node_id_int + 1)
        # logging.info(f"Node ID: {node_id} và Node Data: {node_data}")
        metadata = {}

        outputs = {}
        outputs_data = node_data.get("outputs", {})
        outputs_connections = []
        for output_key, output in outputs_data.items():
            connections = output.get("connections", [])
            for connection in connections:
                next_node = connection.get("node")
                if next_node:
                    # Kiểm tra xem node đó có tồn tại trong dict không
                    if next_node in ordered_flow:
                        next_item = ordered_flow[next_node]
                        if 'type' in next_item['data']:
                            next_item_type = _check_type(next_item['data']['type'])
                        else:
                            next_item_type = "Event"
                        next_item_connection = _outputs_connection(next_item_type, next_node)
                        # logging.info(f"Next item type: {next_item_type}, output connection: {next_item_connection}")
                        outputs_connections.append(next_item_connection)
        outputs.update({
            "success": {
                "connections": outputs_connections
            }
        })

        match node_data['data']['node']:
            case "clock-event":
                metadata.update({
                    "plugin_module": "plugins.system.time_scheduler",
                    "plugin_function": "wait_for_time",
                    "scheduled_time": node_data['data']['time']
                })
            case "delay" | "loop-event":
                metadata.update({
                    "plugin_module": "plugins.system.time_repeat",
                    "plugin_function": "repeat_event",
                    "interval": node_data['data']['value']
                })
            case "turn-on" | "turn-off":
                if node_data['data']['node'] == "turn-on":
                    plugin_function = "turn_on_light"
                    value = 1
                else:
                    plugin_function = "turn_off_light"
                    value = 0
                metadata.update({
                    "plugin_module": "plugins.philiphue.light",
                    "plugin_function": plugin_function,
                    "attributes": [
                        {
                            "uuid": "932c32bd-0002-47a2-835a-a8d455b859dd",
                            "value": value
                        }
                    ],
                })
            case "color":
                logging.info(node_data['data'])
                metadata.update({
                    "plugin_module": "plugins.philiphue.light",
                    "plugin_function": "change_color_and_brightness",
                    "attributes": [
                        {
                            "uuid": "932c32bd-0005-47a2-835a-a8d455b859dd",
                            "value": node_data['data']['color_picker']
                        },
                        {
                            "uuid": "932c32bd-0003-47a2-835a-a8d455b859dd",
                            "value": node_data['data']['brightness']
                        }
                    ],
                })
            case "dimmer":
                metadata.update({
                    "plugin_module": "plugins.philiphue.light",
                    "plugin_function": "change_brightness",
                    "attributes": [
                        {
                            "uuid": "932c32bd-0003-47a2-835a-a8d455b859dd",
                            "value": node_data['data']['brightness']
                        }
                    ],
                })
            case _:
                metadata.update({
                    "plugin_module": "plugins.system.time_repeat",
                    "plugin_function": "repeat_event",
                    "interval": 10
                })

        if 'type' in node_data['data']:
            type = _check_type(node_data['data']['type'])
        else:
            type = "Event"

        if 'mac_address' in node_data['data']:
            metadata["mac_address"] = node_data['data']['mac_address']

        new_drawflow["drawflow"]["Home"]["data"][node_id] = {
            "id": node_id,
            "name": f"Light {node_id}",
            "type": type,
            "metadata": metadata,
            "outputs": outputs
        }

    # logging.info(f"New Drawflow: {new_drawflow}")
    return new_drawflow


class Hub:
    def __init__(self, serial_no):
        self.config = ConfigSettings()
        self.cloud_logger = CloudLogger()
        self.plugin_dir = "plugins"
        self.plugins = []

        self.serial = serial_no
        self.serial_hash = md5(self.serial.encode()).hexdigest()  # Hash the serial number for security

        self.api = ApiBackend()
        self.ble = BLEManager()
        # self.flow = Flow()
        self.flow = None
        self.flow_manager = []

        self.command = ""
        self.meta_data = ""

        # Load plugins
        # Comment out the plugins you don't want to load
        # Will later be managed by API

        # These are loaded from the plugins.txt file. And can be managed by commands from the server
        # self.load_plugin("null") # Sensor emulator plugin
        # self.load_plugin("onio_ble") # ONiO BLE plugin
        # self.load_plugin("philips_hue") # Philips hue experimental plugin
        # self.load_plugin("null") # Sensor emulator plugin
        # self.load_plugin("onio_ble") # ONiO BLE plugin
        # self.load_plugin("philips_hue")  # Philips hue experimental plugin

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

        flow_json = self.api.get_flow()
        # new_drawflow = _flow_etl(flow_json)
        # self.flow = ConfigurableWorkflow(new_drawflow)
        # thread_flow = threading.Thread(target=flow.evaluate_loop, name="Test")
        # self.flow_manager.append({
        #     "flow": new_drawflow,
        #     "thread": thread_flow
        # })
        logging.info(f"Danh sach Flow: {self.flow_manager}")
        # if self.flow.set_flow(self.api.get_flow()):
        #     logging.info("Successfully retrieved flow")

        logging.info("Startup complete... Beginning main routine\n")
        self.cloud_logger.add_log_line("SYSTEM", "Startup complete... Beginning main routine")
        return True

    def loop(self, auto_collect, period=5):

        # Initial scan
        self.scan_for_devices()
        get_flow_delay = 0
        logging.info("Before Main loop")
        logging.info(f"Danh sach Flow: {self.flow_manager}")
        # self.flow.evaluate_loop()
        # thread_flow = threading.Thread(target=self.flow.evaluate_loop, name="Test")
        # logging.info(f"Thread flow {thread_flow}")
        # thread_flow.start()
        # task_event = threading.Event()
        # task_event.set()
        # for flow in self.flow_manager:
        #     flow['thread'].start()
        while True:
            try:
                logging.info("Main loop")
                if self.command == "rebooting":
                    logging.info("Rebooting...")
                    self.shutdown()

                elif self.command == "scan_devices":
                    self.scan_for_devices()

                    if not self.api.post_scan_results(self.plugins):
                        logging.error("Failed to post scan results")

                    logging.info("Scan complete... Returning to main routine\n")



                elif self.command == "execute-flow":
                    logging.info("Execute something")
                    logging.info(f"Command: {self.command} and meta_data: {self.meta_data}")
                    self.execute_plugins()

                elif self.command == "":
                    # if auto_collect:
                    logging.debug("Automatically executing plugins")
                    self.execute_plugins()
                    pass

                # elif self.command.startswith("load_plugin"):
                #     plugin_name = self.command.split(":")[1]
                #     self.load_plugin(plugin_name)
                #
                # elif self.command.startswith("unload_plugin"):
                #     plugin_name = self.command.split(":")[1]
                #     for plugin in self.plugins:
                #         if plugin.__class__.__name__ == plugin_name:
                #             self.plugins.remove(plugin)
                #             logging.info("Plugin unloaded: " + plugin_name)
                #             break

                self.command = ""
                time.sleep(period)

                (self.command, self.meta_data) = self.api.ping_server(self.serial_hash,
                                                                      self.cloud_logger.format_logs_to_json())

                # Get flow every 50 cycles. This should be replaced by
                # a command from the server whenever a new flow is activated
                if get_flow_delay > 3:
                    flow_json = self.api.get_flow()
                    # new_drawflow = _flow_etl(flow_json)
                    # self.flow = ConfigurableWorkflow(new_drawflow)
                    # self.flow_manager.clear()
                    # self.flow_manager.append(flow)
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
