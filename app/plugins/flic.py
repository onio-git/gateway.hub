import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from bleak import BleakClient, BleakGATTCharacteristic
import asyncio
from plugins.flic_assistant import FlicClient, ScanWizard, ScanWizardResult

# Flic Smart Button Service UUIDs
FLIC_SERVICE_UUID = "00420000-8f59-4420-870d-84f3b617e493"
FLIC_BUTTON_CHAR_UUID = "00420001-8f59-4420-870d-84f3b617e493"
FLIC_EVENT_CHAR_UUID = "00420002-8f59-4420-870d-84f3b617e493"


class flic(PluginInterface):
    def __init__(self):
        self.protocol = "BLE"
        self.devices = {}
        self.plugin_active = False

    def execute(self, api: ApiBackend) -> None:
        if self.plugin_active:
            return
        self.plugin_active = True
        asyncio.run(self.run_devices())
        self.plugin_active = False

    async def run_devices(self):
        # self.run_flic()
        for _, device in self.devices.items():
            data = await device.connect_and_subscribe()
            if not data:
                logging.error(f"Failed to read data from {device.mac_address} - {device.device_name}")
                continue

    def display_devices(self) -> None:
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")

    class SearchableDevice(PluginInterface.SearchableDeviceInterface):
        def __init__(self): # device-name: F24206, F22854
            self.protocol = "BLE"
            self.scan_filter_method = "uuid"
            self.scan_filter = "00420000-8f59-4420-870d-84f3b617e493"
            
            


    class Device(PluginInterface.DeviceInterface):
        def __init__(self, mac_address, device_name):
            self.mac_address = mac_address
            self.device_name = device_name
            self.manufacturer = "Flic"
            self.ip = ""
            self.serial_no = ""
            self.model_no = ""
            self.com_protocol = "BLE"
            self.firmware = ""
            self.device_description = 'Flick Smart Button'

        async def introspect(self, client) -> None:
            for s in client.services:
                print(f"service: {s.uuid}")
                for c in s.characteristics:
                    try:
                        val = await client.read_gatt_char(c.uuid)

                        print(f"  characteristic: {c.uuid}: {[hex(byte) for byte in val] if type(val)== bytearray else val}")
                    except Exception as e:
                        print(f"  characteristic: {c.uuid}: {e}")


        def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
            """Simple notification handler which prints the data received."""
            logging.info("%s: %r", characteristic.description, data)


        async def connect_and_subscribe(self):
            async with BleakClient(self.mac_address) as client:                
                logging.info(f"Connected to {self.mac_address} - {self.device_name}")

            #     await self.introspect(client)

                # response = await client.start_notify(FLIC_EVENT_CHAR_UUID, self.notification_handler)
                # logging.debug(f"Subscribed to {self.mac_address} - {self.device_name}")
                # logging.debug(f"Response: {response}")
            
            return

    def run_flic(self):
        client = FlicClient("localhost")

        def on_found_private_button(scan_wizard):
            print("Found a private button. Please hold it down for 7 seconds to make it public.")

        def on_found_public_button(scan_wizard, bd_addr, name):
            print("Found public button " + bd_addr + " (" + name + "), now connecting...")

        def on_button_connected(scan_wizard, bd_addr, name):
            print("The button was connected, now verifying...")

        def on_completed(scan_wizard, result, bd_addr, name):
            print("Scan wizard completed with result " + str(result) + ".")
            if result == ScanWizardResult.WizardSuccess:
                print("Your button is now ready. The bd addr is " + bd_addr + ".")
            client.close()

        wizard = ScanWizard()
        wizard.on_found_private_button = on_found_private_button
        wizard.on_found_public_button = on_found_public_button
        wizard.on_button_connected = on_button_connected
        wizard.on_completed = on_completed
        client.add_scan_wizard(wizard)

        print("Welcome to Scan Wizard. Please press and hold down your Flic button until it connects.")

        client.handle_events()
