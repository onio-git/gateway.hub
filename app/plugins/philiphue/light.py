import logging
import asyncio
import pexpect
from bleak import BleakClient

LIGHT_CHARACTERISTIC = "932c32bd-0002-47a2-835a-a8d455b859dd"
BRIGHTNESS_CHARACTERISTIC = "932c32bd-0003-47a2-835a-a8d455b859dd"
TEMPERATURE_CHARACTERISTIC = "932c32bd-0004-47a2-835a-a8d455b859dd"
COLOR_CHARACTERISTIC = "932c32bd-0005-47a2-835a-a8d455b859dd"
COMBINED_CHARACTERISTIC = "932c32bd-0007-47a2-835a-a8d455b859dd"
FIRMWARE_CHARACTERISTIC = "00002a28-0000-1000-8000-00805f9b34fb"


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')

    rgb_list = [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
    scale = 0xFF
    adjusted = [max(1, chan) for chan in rgb_list]
    total = sum(adjusted)
    adjusted = [int(round(chan / total * scale)) for chan in adjusted]
    return bytearray([0x1, adjusted[0], adjusted[2], adjusted[1]])


def percentage_to_brightness(percentage):
    percentage = max(0, min(percentage, 100))

    brightness_value = int((percentage * 254) / 100)
    return bytearray([brightness_value])


def turn_on_light(event, metadata):
    logging.info(f"Turning on Philips Hue light-Mac address: D9:18:8C:77:8F:F3")
    mac_address = "D9:18:8C:77:8F:F3"

    # Mô phỏng bật đèn
    async def async_write():
        await pair_and_trust(mac_address)
        async with BleakClient(mac_address) as client:
            if not client.is_connected:
                logging.error(f"Bleak failed to connect to {mac_address}")
                return None

            # self.is_connected = True
            paired = await client.pair(protection_level=0)
            logging.info(f"Paired: {paired}")
            byte_value = bytes([0])
            # await client.write_gatt_char(LIGHT_CHARACTERISTIC, b"\x00")
            if isinstance(metadata, dict):
                attributes = metadata.get("attributes", {})
                for data_attribute in attributes:
                    logging.info(f"Processing attribute: {data_attribute}")
                    characteristic_uuid = data_attribute.get("uuid", None)
                    characteristic_value = data_attribute.get("value", None)
                    if characteristic_uuid and characteristic_value is not None:
                        logging.info(f"Updating {characteristic_uuid} with {characteristic_value}")
                        if characteristic_uuid == LIGHT_CHARACTERISTIC:
                            if isinstance(characteristic_value, str):
                                byte_value = characteristic_value.encode('utf-8')
                            elif isinstance(characteristic_value, int):
                                byte_value = bytes([characteristic_value])
                        # elif characteristic_uuid == COLOR_CHARACTERISTIC:
                        #     byte_value = hex_to_rgb(characteristic_value)
                        # elif characteristic_uuid == BRIGHTNESS_CHARACTERISTIC:
                        #     byte_value = percentage_to_brightness(characteristic_value)

                        try:
                            await client.write_gatt_char(characteristic_uuid, byte_value, response=True)
                        except Exception as e:
                            logging.error(f"Failed to write characteristic: {e}")

    asyncio.run(async_write())
    return {"status": "light_on", "metadata": metadata}


def turn_off_light(event, metadata):
    logging.info(f"Turning off Philips Hue light-Mac address: D9:18:8C:77:8F:F3")
    mac_address = "D9:18:8C:77:8F:F3"

    # Mô phỏng bật đèn
    async def async_write():
        await pair_and_trust(mac_address)
        async with BleakClient(mac_address) as client:
            if not client.is_connected:
                logging.error(f"Bleak failed to connect to {mac_address}")
                return None

            # self.is_connected = True
            paired = await client.pair(protection_level=0)
            logging.info(f"Paired: {paired}")
            byte_value = bytes([0])
            if isinstance(metadata, dict):
                attributes = metadata.get("attributes", {})
                for data_attribute in attributes:
                    logging.info(f"Processing attribute: {data_attribute}")
                    characteristic_uuid = data_attribute.get("uuid", None)
                    characteristic_value = data_attribute.get("value", None)
                    if characteristic_uuid and characteristic_value is not None:
                        logging.info(f"Updating {characteristic_uuid} with {characteristic_value}")
                        if characteristic_uuid == LIGHT_CHARACTERISTIC:
                            if isinstance(characteristic_value, str):
                                byte_value = characteristic_value.encode('utf-8')
                            elif isinstance(characteristic_value, int):
                                byte_value = bytes([characteristic_value])
                        try:
                            await client.write_gatt_char(characteristic_uuid, byte_value, response=True)
                        except Exception as e:
                            logging.error(f"Failed to write characteristic: {e}")

    asyncio.run(async_write())
    return {"status": "light_on", "metadata": metadata}


def change_color_and_brightness(event, metadata):
    logging.info(f"Change color and brightness Philips Hue light-Mac address: D9:18:8C:77:8F:F3")
    mac_address = "D9:18:8C:77:8F:F3"

    async def async_write():
        await pair_and_trust(mac_address)
        async with BleakClient(mac_address) as client:
            if not client.is_connected:
                logging.error(f"Bleak failed to connect to {mac_address}")
                return None

            # self.is_connected = True
            paired = await client.pair(protection_level=0)
            logging.info(f"Paired: {paired}")
            byte_value = bytes([0])
            if isinstance(metadata, dict):
                attributes = metadata.get("attributes", {})
                for data_attribute in attributes:
                    logging.info(f"Processing attribute: {data_attribute}")
                    characteristic_uuid = data_attribute.get("uuid", None)
                    characteristic_value = data_attribute.get("value", None)
                    if characteristic_uuid and characteristic_value is not None:
                        logging.info(f"Updating {characteristic_uuid} with {characteristic_value}")
                        if characteristic_uuid == COLOR_CHARACTERISTIC:
                            byte_value = hex_to_rgb(characteristic_value)
                        elif characteristic_uuid == BRIGHTNESS_CHARACTERISTIC:
                            byte_value = percentage_to_brightness(characteristic_value)
                        try:
                            await client.write_gatt_char(characteristic_uuid, byte_value, response=True)
                        except Exception as e:
                            logging.error(f"Failed to write characteristic: {e}")

    asyncio.run(async_write())
    return {"status": "change_color_and_brightness", "metadata": metadata}


def change_brightness(event, metadata):
    logging.info(f"Change and brightness Philips Hue light-Mac address: D9:18:8C:77:8F:F3")
    mac_address = "D9:18:8C:77:8F:F3"

    async def async_write():
        await pair_and_trust(mac_address)
        async with BleakClient(mac_address) as client:
            if not client.is_connected:
                logging.error(f"Bleak failed to connect to {mac_address}")
                return None

            # self.is_connected = True
            paired = await client.pair(protection_level=0)
            logging.info(f"Paired: {paired}")
            byte_value = bytes([0])
            if isinstance(metadata, dict):
                attributes = metadata.get("attributes", {})
                for data_attribute in attributes:
                    logging.info(f"Processing attribute: {data_attribute}")
                    characteristic_uuid = data_attribute.get("uuid", None)
                    characteristic_value = data_attribute.get("value", None)
                    if characteristic_uuid and characteristic_value is not None:
                        logging.info(f"Updating {characteristic_uuid} with {characteristic_value}")
                        if characteristic_uuid == BRIGHTNESS_CHARACTERISTIC:
                            byte_value = percentage_to_brightness(characteristic_value)
                        try:
                            await client.write_gatt_char(characteristic_uuid, byte_value, response=True)
                        except Exception as e:
                            logging.error(f"Failed to write characteristic: {e}")

    asyncio.run(async_write())
    return {"status": "change_color_and_brightness", "metadata": metadata}


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
