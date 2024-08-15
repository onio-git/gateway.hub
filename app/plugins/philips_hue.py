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

def convert_rgb(rgb):
    scale = 0xFF
    adjusted = [max(1, chan) for chan in rgb]
    total = sum(adjusted)
    adjusted = [int(round(chan / total * scale)) for chan in adjusted]

    # Unknown, Red, Blue, Green
    return bytearray([0x1, adjusted[0], adjusted[2], adjusted[1]])


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


        async def connect_and_read(self):
            try:
                async with BleakClient(self.mac_address) as client:
                    logging.info(f"Connected to {self.mac_address} - {self.device_name}")

                    # Pairing
                    paired = await client.pair(protection_level=2)
                    logging.debug(f"Paired: {paired}")

                    # Perform operations
                    await self.turn_light_off(client)
                    await asyncio.sleep(2.0)
                    await self.turn_light_on(client)
                    await asyncio.sleep(2.0)
                    await self.set_brightness(client, 100)
                    await asyncio.sleep(2.0)
                    await self.set_color(client, [255, 0, 0])
                    await asyncio.sleep(2.0)
                    await self.set_color(client, [0, 255, 0])
                    await asyncio.sleep(2.0)
                    await self.set_color(client, [0, 0, 255])
                    await asyncio.sleep(2.0)
                    state = await self.read_light_state(client)
                    print(state)
                    await asyncio.sleep(5.0)
                    return state

            except Exception as e:
                logging.error(f"Error: {e}")

        async def read_light_state(self, client):
            logging.info("Reading Light State...")
            
            # Read light state
            state = await client.read_gatt_char(LIGHT_CHARACTERISTIC)
            await asyncio.sleep(1.0)
            print(f"Light State: {state}")
            self.state["light_is_on"] = bool(state[0])
            
            # Read brightness
            brightness = await client.read_gatt_char(BRIGHTNESS_CHARACTERISTIC)
            await asyncio.sleep(1.0)
            print(f"Brightness: {brightness}")
            self.state["brightness"] = int(brightness[0])
            
            # Read temperature
            temperature = await client.read_gatt_char(TEMPERATURE_CHARACTERISTIC)
            await asyncio.sleep(1.0)
            print(f"Temperature: {temperature}")
            self.state["temperature"] = int.from_bytes(temperature, byteorder='big')
            
            # Read color
            color = await client.read_gatt_char(COLOR_CHARACTERISTIC)
            await asyncio.sleep(1.0)
            print(f"Color: {color}")
            color_hex = color.hex()
            color_value = int.from_bytes(color, byteorder='little')
            print(f"Color (hex): {color_hex}")
            print(f"Color (int): {color_value}")
            self.state["color"] = color_value
            
            return self.state

        async def turn_light_off(self, client):
            logging.info("Turning Light off...")
            await client.write_gatt_char(LIGHT_CHARACTERISTIC, b"\x00", response=True)

        async def turn_light_on(self, client):
            logging.info("Turning Light on...")
            await client.write_gatt_char(LIGHT_CHARACTERISTIC, b"\x01", response=True)

        async def set_color(self, client, color):
            logging.info(f"Setting color to {color} - {convert_rgb(color)}...")
            await client.write_gatt_char(COLOR_CHARACTERISTIC, convert_rgb(color), response=True)

        async def set_brightness(self, client, brightness):
            logging.info(f"Setting brightness to {brightness} % ...")
            # Brightness range: 0-100 - converts to 1-254
            brightness = int((brightness / 100) * 254)
            await client.write_gatt_char(BRIGHTNESS_CHARACTERISTIC, bytearray([brightness]), response=True)
