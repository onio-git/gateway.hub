import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from bleak import BleakClient
import asyncio
import pexpect
import sys

# Configure Logging
logging.basicConfig(
    level=logging.INFO,  # Set to INFO to reduce verbosity; switch to DEBUG when needed
    format='%(asctime)s - %(levelname)s\t- %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

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

    def execute(self, api: ApiBackend, command: str = '') -> None:
        if self.plugin_active:
            return
        self.plugin_active = True
        logging.info("Philips Hue Plugin is active.")
        asyncio.run(self.run_devices())
        self.plugin_active = False

    async def run_devices(self):
        for _, device in self.devices.items():
            # Check if the device is already connected
            # async with BleakClient(device.mac_address) as client:
            #     if client.is_connected:
            #         logging.info(f"Device {device.mac_address} is already connected.")

            # If not connected, attempt to connect and read
            data = await device.connect_and_read()
            if not data:
                logging.error(f"Failed to read data from {device.mac_address} - {device.device_name}")
                continue

            else:
                logging.info(f"Data from {device.mac_address} - {device.device_name}: {data}")

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

            self.is_paired = False
            self.is_trusted = False
            self.is_connected = False

        async def connect_and_read(self):
            try:
                logging.info(f"Connecting to {self.mac_address} - {self.device_name}...")
                # Step 1: Pair and Trust the Device
                if not self.is_paired or not self.is_trusted:
                    logging.info(f"Initiating pairing and trusting with {self.mac_address} - {self.device_name}")
                    paired_and_trusted = await pair_and_trust(self.mac_address)

                    if paired_and_trusted:
                        self.is_paired = True
                        self.is_trusted = True
                    else:
                        logging.error(f"Failed to pair with {self.mac_address} - {self.device_name}")
                        return None
                else:
                    logging.info(f"Device {self.mac_address} is already paired and trusted.")

                # Step 2: Connect and Read Data using Bleak
                async with BleakClient(self.mac_address) as client:
                    # for service in client.services:
                    #     print(f"[Service] {service.uuid}: {service.description}")
                    #     for char in service.characteristics:
                    #         # print(f"  [Characteristic] {char.uuid}: {char.description}")
                    #         try:
                    #             print(f"  Characteristic UUID: {char.uuid}")
                    #             print(f"  Properties: {char.properties}")
                    #         #     if "read" in char.properties:
                    #         #         value = await client.read_gatt_char(char.uuid)
                    #         #         print(f"    Value: {value}")
                    #
                    #         except Exception as e:
                    #             print(f"    Error reading {char.uuid}: {e}")

                    if not client.is_connected:
                        logging.error(f"Bleak failed to connect to {self.mac_address} - {self.device_name}")
                        return None

                    self.is_connected = True
                    logging.info(f"Connected to {self.mac_address} - {self.device_name}")

                    # Perform operations
                    state = await self.read_light_state(client)

                    # async def toggle_light(client, current_state):
                    #     command = b'\x00' if current_state else b'\x01'  # Nếu đang bật thì tắt và ngược lại
                    #     await client.write_gatt_char(LIGHT_CHARACTERISTIC, command)
                    #     print("Đèn đã được bật" if command == b'\x01' else "Đèn đã được tắt")
                    #
                    # if state["light_is_on"]:
                    #     await toggle_light(client, True)
                    # else:
                    #     await toggle_light(client, False)

                    # await asyncio.sleep(5.0)
                    self.is_connected = False  # Reset after operations
                    return state

            except Exception as e:
                logging.error(f"Error in connect_and_read: {e}")
                return None

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


async def pair_and_trust(mac_address, retries=3, delay=5):
    """
    Automates the pairing and trusting process using bluetoothctl via pexpect.
    Retries the process up to `retries` times with `delay` seconds between attempts.
    """
    for attempt in range(1, retries + 1):
        logging.info(f"Pairing attempt {attempt} for {mac_address}")
        try:
            # Spawn bluetoothctl
            child = pexpect.spawn('bluetoothctl', encoding='utf-8', timeout=30)
            child.logfile = None  # Disable logging to stdout

            # Wait for the bluetoothctl prompt
            child.expect('#')

            # Turn on the Bluetooth adapter
            child.sendline('power on')
            child.expect('#')

            # Set up the agent
            child.sendline('agent on')
            child.expect('#')
            child.sendline('default-agent')
            child.expect('#')

            # Check if the device is already paired and trusted
            child.sendline(f'info {mac_address}')
            index = child.expect([
                f"Device {mac_address} not found",
                f"Paired: no",
                f"Paired: yes",
                pexpect.EOF,
                pexpect.TIMEOUT
            ])

            if index == 0 or index == 1:
                logging.info(f"Device {mac_address} is not paired. Proceeding to pair.")
            elif index == 2:
                logging.info(f"Device {mac_address} is already paired.")
                # Check if trusted
                child.sendline(f'info {mac_address}')
                child.expect('#')
                info_output = child.before
                if "Trusted: yes" in info_output:
                    logging.info(f"Device {mac_address} is already trusted.")
                    child.sendline('exit')
                    child.close()
                    return True
                else:
                    logging.info(f"Device {mac_address} is not trusted. Proceeding to trust.")
            else:
                logging.error(f"Unexpected response while checking info for {mac_address}")
                child.sendline('exit')
                child.close()
                return False

            # Initiate pairing only if not already paired
            child.sendline(f'pair {mac_address}')
            index = child.expect([
                'Pairing successful',
                'Device has been paired',
                'Authentication Failed',
                'Failed to pair',
                'Agent request PIN code',
                'Agent request Passkey',
                pexpect.EOF,
                pexpect.TIMEOUT
            ])

            if index in [0, 1]:
                logging.info(f"Successfully paired with {mac_address}")
            elif index in [2, 3]:
                logging.error(f"Failed to pair with {mac_address}")
                child.sendline('exit')
                child.close()
                return False
            elif index == 4:
                # Handle PIN code request if needed
                pin_code = '0000'  # Replace with the actual PIN if required
                child.sendline(pin_code)
                child.expect('#')
                logging.info(f"Sent PIN code to {mac_address}")
            elif index == 5:
                # Handle Passkey request if needed
                passkey = '123456'  # Replace with the actual Passkey if required
                child.sendline(passkey)
                child.expect('#')
                logging.info(f"Sent Passkey to {mac_address}")
            else:
                logging.error(f"Unexpected response during pairing with {mac_address}")
                child.sendline('exit')
                child.close()
                return False

            # Trust the device
            child.sendline(f'trust {mac_address}')
            index = child.expect([
                f"Changing {mac_address} trust succeeded",
                f"Device {mac_address} not available",
                pexpect.EOF,
                pexpect.TIMEOUT
            ])

            if index == 0:
                logging.info(f"Successfully trusted {mac_address}")
            else:
                logging.error(f"Failed to trust {mac_address}")
                child.sendline('exit')
                child.close()
                return False

            # Exit bluetoothctl
            child.sendline('exit')
            child.close()
            return True

        except pexpect.exceptions.EOF:
            logging.error("Unexpected EOF during pairing/trusting process.")
        except pexpect.exceptions.TIMEOUT:
            logging.error("Timeout occurred during pairing/trusting process.")
        except Exception as e:
            logging.error(f"Exception during pairing/trusting: {e}")

        logging.warning(f"Attempt {attempt} failed. Retrying in {delay} seconds...")
        await asyncio.sleep(delay)

    logging.error(f"All {retries} pairing attempts failed for {mac_address}")
    return False
