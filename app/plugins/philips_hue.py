import logging
from core.plugin_interface import PluginInterface
from core.backend import ApiBackend
from bleak import BleakClient
import asyncio

# Philips Hue Play Light Bar
LIGHT_CHARACTERISTIC = "932c32bd-0002-47a2-835a-a8d455b859dd"
BRIGHTNESS_CHARACTERISTIC = "932c32bd-0003-47a2-835a-a8d455b859dd"
TEMPERATURE_CHARACTERISTIC = "932c32bd-0004-47a2-835a-a8d455b859dd"
COLOR_CHARACTERISTIC = "932c32bd-0005-47a2-835a-a8d455b859dd"
COMBINED_CHARACTERISTIC = "932c32bd-0007-47a2-835a-a8d455b859dd"
FIRMWARE_CHARACTERISTIC = "00002a28-0000-1000-8000-00805f9b34fb"


def color_by_name(name: str) -> bytearray:
    name = name.lower()
    if name == "white":
        return bytearray([0x30, 0x50, 0x30, 0x54])
    elif name == "warm yellow":
        return bytearray([0x30, 0x6a, 0x30, 0x6d])
    elif name == "orange":
        return bytearray([0x30, 0x7e, 0x30, 0x70])
    elif name == "red":
        return bytearray([0x9E, 0xB0, 0xF3, 0x4E])
    elif name == "pink":
        return bytearray([0x30, 0x65, 0x30, 0x1F])
    elif name == "purple":
        return bytearray([0x30, 0x5d, 0x30, 0x38])
    elif name == "blue":
        return bytearray([0x37, 0x27, 0x3F, 0x0C])
    elif name == "cyan":
        return bytearray([0x30, 0x38, 0x30, 0x4e])
    elif name == "turqoise":
        return bytearray([0x3f, 0x45, 0x33, 0x5B])
    elif name == "green":
        return bytearray([0xA7, 0x4D, 0xE4, 0x98])
    elif name == "yellowgreen":
        return bytearray([0x30, 0x38, 0x30, 0x4e])
    else:
        return bytearray([0x30, 0x50, 0x30, 0x54])


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

    class SearchableDevice:
        def __init__(self):
            self.protocol = "BLE"
            self.scan_filter_method = "uuid"
            self.scan_filter = "0000fe0f-0000-1000-8000-00805f9b34fb"

    class Device:
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

        async def introspect(self, client) -> None:
            for s in client.services:
                print(f"service: {s.uuid}")
                for c in s.characteristics:
                    try:
                        val = await client.read_gatt_char(c.uuid)

                        print(f"  characteristic: {c.uuid}: {[hex(byte) for byte in val] if type(val)== bytearray else val}")
                    except Exception as e:
                        print(f"  characteristic: {c.uuid}: {e}")


        async def connect_and_read(self):
            try:
                async with BleakClient(self.mac_address) as client:
                    
                    logging.info(f"Connected to {self.mac_address} - {self.device_name}")
                    # await self.introspect(client)

                    # Pairing
                    paired = await client.pair(protection_level=2)
                    logging.debug(f"Paired: {paired}")

                    # Perform operations
                    await self.turn_light_off(client)
                    await asyncio.sleep(2.0)
                    await self.turn_light_on(client)
                    await asyncio.sleep(2.0)
                    await self.set_brightness(client, 100)
                    await self.set_color(client, color_by_name("white"))
                    await asyncio.sleep(2.0)
                    await self.set_color(client, color_by_name("red"))
                    await asyncio.sleep(2.0)
                    state = await self.read_light_state(client)
                    print(state)
                    await asyncio.sleep(5.0)
                    return state

            except Exception as e:
                logging.error(f"Error: {e}")

        async def read_light_state(self, client):
            logging.info("Reading Light State...")

            if self.firmware == "":
                firmware = await client.read_gatt_char(FIRMWARE_CHARACTERISTIC)
                self.firmware = ''.join([chr(byte) for byte in firmware])
                logging.info(f"Firmware: {self.firmware}")
            
            # Read light state
            state = await client.read_gatt_char(LIGHT_CHARACTERISTIC)
            self.state["light_is_on"] = bool(state[0])
            # Read brightness
            brightness = await client.read_gatt_char(BRIGHTNESS_CHARACTERISTIC)
            self.state["brightness"] = int(brightness[0])
            # Read temperature
            temperature = await client.read_gatt_char(TEMPERATURE_CHARACTERISTIC)
            self.state["temperature"] = int.from_bytes(temperature, byteorder='big')
            # Read color
            color = await client.read_gatt_char(COLOR_CHARACTERISTIC)
            self.state["color"] = [hex(byte) for byte in color]

            return self.state

        async def turn_light_off(self, client):
            logging.info("Turning Light off...")
            await client.write_gatt_char(LIGHT_CHARACTERISTIC, b"\x00", response=True)

        async def turn_light_on(self, client):
            logging.info("Turning Light on...")
            await client.write_gatt_char(LIGHT_CHARACTERISTIC, b"\x01", response=True)

        async def set_color(self, client, color):
            logging.info(f"Setting color to [{', '.join(f'0x{byte:02x}' for byte in color)}] ...")
            await client.write_gatt_char(COLOR_CHARACTERISTIC, color, response=True)

        async def set_brightness(self, client, brightness):
            logging.info(f"Setting brightness to {brightness} % ...")
            # Brightness range: 0-100 - converts to 1-254
            brightness = int((brightness / 100) * 254)
            await client.write_gatt_char(BRIGHTNESS_CHARACTERISTIC, bytearray([brightness]), response=True)
