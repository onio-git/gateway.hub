import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from bleak import BleakClient
import asyncio
import pexpect
import sys

# Philips Hue Play Light Bar UUIDs
LIGHT_CHARACTERISTIC = "932c32bd-0002-47a2-835a-a8d455b859dd"
BRIGHTNESS_CHARACTERISTIC = "932c32bd-0003-47a2-835a-a8d455b859dd"
TEMPERATURE_CHARACTERISTIC = "932c32bd-0004-47a2-835a-a8d455b859dd"
COLOR_CHARACTERISTIC = "932c32bd-0005-47a2-835a-a8d455b859dd"
COMBINED_CHARACTERISTIC = "932c32bd-0007-47a2-835a-a8d455b859dd"
FIRMWARE_CHARACTERISTIC = "00002a28-0000-1000-8000-00805f9b34fb"

def color_by_name(name: str) -> bytearray:
    name = name.lower()
    color_map = {
        "white": bytearray([0x30, 0x50, 0x30, 0x54]),
        "warm yellow": bytearray([0x30, 0x6a, 0x30, 0x6d]),
        "orange": bytearray([0x30, 0x7e, 0x30, 0x70]),
        "red": bytearray([0x9E, 0xB0, 0xF3, 0x4E]),
        "pink": bytearray([0x30, 0x65, 0x30, 0x1F]),
        "purple": bytearray([0x30, 0x5d, 0x30, 0x38]),
        "blue": bytearray([0x37, 0x27, 0x3F, 0x0C]),
        "cyan": bytearray([0x30, 0x38, 0x30, 0x4e]),
        "turquoise": bytearray([0x3f, 0x45, 0x33, 0x5B]),
        "green": bytearray([0xA7, 0x4D, 0xE4, 0x98]),
        "yellowgreen": bytearray([0x30, 0x38, 0x30, 0x4e]),
    }
    return color_map.get(name, bytearray([0x30, 0x50, 0x30, 0x54]))

class philips_hue(PluginInterface):
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
        for _, device in self.devices.items():
            data = await device.connect_and_read()
            if not data:
                logging.error(f"Failed to read data from {device.mac_address} - {device.device_name}")
                continue

    def display_devices(self) -> None:
        for id, device in self.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")

    class SearchableDevice(PluginInterface.SearchableDeviceInterface):
        def __init__(self):
            self.protocol = "BLE"
            self.scan_filter_method = "uuid"
            self.scan_filter = "0000fe0f-0000-1000-8000-00805f9b34fb"

    class Device(PluginInterface.DeviceInterface):
        def __init__(self, mac_address, device_name):
            self.mac_address = mac_address
            self.device_name = device_name
            self.manufacturer = "Philips Hue"
            self.ip = ""
            self.serial_no = ""
            self.model_no = "440400982842"
            self.com_protocol = "BLE"
            self.firmware = ""
            self.device_description = 'Philips Hue Play Light Bar'

            self.state = {
                "light_is_on": False,
                "brightness": 0,
                "temperature": 0,
                "color": 0x000000
            }

        async def connect_and_read(self):
            try:
                # Step 1: Ensure Device is Paired and Trusted
                paired = await self.is_paired()
                trusted = await self.is_trusted()

                if not paired:
                    logging.info(f"Device {self.mac_address} not paired. Initiating pairing.")
                    paired = await self.pair_device()
                    if not paired:
                        logging.error(f"Failed to pair with {self.mac_address} - {self.device_name}")
                        return None
                else:
                    logging.info(f"Device {self.mac_address} is already paired.")

                if not trusted:
                    logging.info(f"Device {self.mac_address} not trusted. Trusting device.")
                    trusted = await self.trust_device()
                    if not trusted:
                        logging.error(f"Failed to trust {self.mac_address} - {self.device_name}")
                        return None
                else:
                    logging.info(f"Device {self.mac_address} is already trusted.")

                # Step 2: Connect and Read Data using Bleak
                async with BleakClient(self.mac_address) as client:
                    if not client.is_connected:
                        logging.error(f"Bleak failed to connect to {self.mac_address} - {self.device_name}")
                        return None

                    logging.info(f"Connected to {self.mac_address} - {self.device_name}")
                    
                    # Perform operations
                    state = await self.read_light_state(client)
                    await asyncio.sleep(5.0)
                    return state

            except Exception as e:
                logging.error(f"Error in connect_and_read: {e}")
                return None

        async def is_paired(self):
            """Check if the device is already paired."""
            try:
                child = pexpect.spawn('bluetoothctl', encoding='utf-8', timeout=5)
                child.expect('#')
                child.sendline('paired-devices')
                child.expect('#')
                output = child.before
                child.sendline('exit')
                child.close()
                return self.mac_address in output
            except pexpect.exceptions.TIMEOUT:
                logging.error("Timeout while checking if device is paired.")
                return False
            except Exception as e:
                logging.error(f"Error checking paired status: {e}")
                return False

        async def is_trusted(self):
            """Check if the device is already trusted."""
            try:
                child = pexpect.spawn('bluetoothctl', encoding='utf-8', timeout=5)
                child.expect('#')
                child.sendline(f'info {self.mac_address}')
                child.expect('#')
                output = child.before
                child.sendline('exit')
                child.close()
                return "Trusted: yes" in output
            except pexpect.exceptions.TIMEOUT:
                logging.error("Timeout while checking if device is trusted.")
                return False
            except Exception as e:
                logging.error(f"Error checking trusted status: {e}")
                return False

        async def pair_device(self):
            """Pair with the device using bluetoothctl."""
            try:
                child = pexpect.spawn('bluetoothctl', encoding='utf-8', timeout=20)
                child.expect('#')
                child.sendline('agent on')
                child.expect('#')
                child.sendline('default-agent')
                child.expect('#')
                child.sendline(f'pair {self.mac_address}')
                
                # Wait for pairing confirmation
                index = child.expect([
                    'Pairing successful',
                    'Device has been paired',
                    'Failed to pair',
                    'Authentication Failed',
                    pexpect.EOF,
                    pexpect.TIMEOUT
                ])

                if index in [0, 1]:
                    logging.info(f"Successfully paired with {self.mac_address}")
                    child.sendline('exit')
                    child.close()
                    return True
                else:
                    logging.error(f"Failed to pair with {self.mac_address}")
                    child.sendline('exit')
                    child.close()
                    return False
            except pexpect.exceptions.TIMEOUT:
                logging.error("Timeout during pairing.")
                return False
            except Exception as e:
                logging.error(f"Exception during pairing: {e}")
                return False

        async def trust_device(self):
            """Trust the device using bluetoothctl."""
            try:
                child = pexpect.spawn('bluetoothctl', encoding='utf-8', timeout=10)
                child.expect('#')
                child.sendline(f'trust {self.mac_address}')
                
                # Wait for trusting confirmation
                index = child.expect([
                    f"Changing {self.mac_address} trust succeeded",
                    f"Device {self.mac_address} not available",
                    pexpect.EOF,
                    pexpect.TIMEOUT
                ])

                if index == 0:
                    logging.info(f"Successfully trusted {self.mac_address}")
                    child.sendline('exit')
                    child.close()
                    return True
                else:
                    logging.error(f"Failed to trust {self.mac_address}")
                    child.sendline('exit')
                    child.close()
                    return False
            except pexpect.exceptions.TIMEOUT:
                logging.error("Timeout during trusting.")
                return False
            except Exception as e:
                logging.error(f"Exception during trusting: {e}")
                return False

        async def read_light_state(self, client):
            logging.info("Reading Light State...")

            if self.firmware == "":
                try:
                    firmware = await client.read_gatt_char(FIRMWARE_CHARACTERISTIC)
                    self.firmware = ''.join([chr(byte) for byte in firmware])
                    logging.info(f"Firmware: {self.firmware}")
                except Exception as e:
                    logging.error(f"Failed to read firmware: {e}")

            try:
                # Read light state
                state = await client.read_gatt_char(LIGHT_CHARACTERISTIC)
                self.state["light_is_on"] = bool(state[0])
            except Exception as e:
                logging.error(f"Failed to read light state: {e}")

            try:
                # Read brightness
                brightness = await client.read_gatt_char(BRIGHTNESS_CHARACTERISTIC)
                self.state["brightness"] = int(brightness[0])
            except Exception as e:
                logging.error(f"Failed to read brightness: {e}")

            try:
                # Read temperature
                temperature = await client.read_gatt_char(TEMPERATURE_CHARACTERISTIC)
                self.state["temperature"] = int.from_bytes(temperature, byteorder='big')
            except Exception as e:
                logging.error(f"Failed to read temperature: {e}")

            try:
                # Read color
                color = await client.read_gatt_char(COLOR_CHARACTERISTIC)
                self.state["color"] = [hex(byte) for byte in color]
            except Exception as e:
                logging.error(f"Failed to read color: {e}")

            return self.state

        async def turn_light_off(self, client):
            logging.info("Turning Light off...")
            try:
                await client.write_gatt_char(LIGHT_CHARACTERISTIC, b"\x00", response=True)
            except Exception as e:
                logging.error(f"Failed to turn off light: {e}")

        async def turn_light_on(self, client):
            logging.info("Turning Light on...")
            try:
                await client.write_gatt_char(LIGHT_CHARACTERISTIC, b"\x01", response=True)
            except Exception as e:
                logging.error(f"Failed to turn on light: {e}")

        async def set_color(self, client, color):
            logging.info(f"Setting color to [{', '.join(f'0x{byte:02x}' for byte in color)}] ...")
            try:
                await client.write_gatt_char(COLOR_CHARACTERISTIC, color, response=True)
            except Exception as e:
                logging.error(f"Failed to set color: {e}")

        async def set_brightness(self, client, brightness):
            logging.info(f"Setting brightness to {brightness} % ...")
            # Brightness range: 0-100 - converts to 1-254
            brightness = int((brightness / 100) * 254)
            try:
                await client.write_gatt_char(BRIGHTNESS_CHARACTERISTIC, bytearray([brightness]), response=True)
            except Exception as e:
                logging.error(f"Failed to set brightness: {e}")
