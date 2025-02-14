import logging
import asyncio
import pexpect
from bleak import BleakClient
from bleak.exc import BleakDBusError
import time

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

    # start_time = time.perf_counter()

    # Mô phỏng bật đèn
    async def async_write():
        client = await connect_and_pair(mac_address)
        if client:
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
    # end_time = time.perf_counter()
    # logging.info(f"Pairing and trusting took {end_time - start_time} seconds")
    return {"status": "light_on", "metadata": metadata}


def turn_off_light(event, metadata):
    logging.info(f"Turning off Philips Hue light-Mac address: D9:18:8C:77:8F:F3")
    mac_address = "D9:18:8C:77:8F:F3"

    # start_time = time.perf_counter()

    # Mô phỏng tat đèn
    async def async_write():
        client = await connect_and_pair(mac_address)
        if client:
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
    # end_time = time.perf_counter()
    # logging.info(f"Pairing and trusting took {end_time - start_time} seconds")
    return {"status": "light_on", "metadata": metadata}


def change_color_and_brightness(event, metadata):
    logging.info(f"Change color and brightness Philips Hue light-Mac address: D9:18:8C:77:8F:F3")
    mac_address = "D9:18:8C:77:8F:F3"

    async def async_write():
        client = await connect_and_pair(mac_address)
        if client:
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
        client = await connect_and_pair(mac_address)
        if client:
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

RECONNECT_DELAY = 5  # thời gian chờ giữa các lần reconnect (giây)
_reconnect_in_progress = False  # flag để đảm bảo chỉ một reconnect chạy đồng thời
async def reconnect(client: BleakClient):
    global _reconnect_in_progress
    if _reconnect_in_progress:
        return  # Nếu đã có reconnect đang chạy thì không làm gì thêm
    _reconnect_in_progress = True
    try:
        while not client.is_connected:
            try:
                logging.info(f"Đang cố gắng kết nối lại với {client.address}...")
                await client.connect()
            except BleakDBusError as e:
                err_str = str(e)
                if "Operation already in progress" in err_str or "br-connection-canceled" in err_str:
                    logging.warning("Có kết nối đang được xử lý hoặc đã bị hủy, chờ đợi...")
                else:
                    logging.error(f"Lỗi khi kết nối lại: {e}")
            # Nếu client đã kết nối, thoát vòng lặp
            if client.is_connected:
                logging.info("Kết nối lại thành công!")
                break
            logging.info(f"Chờ {RECONNECT_DELAY} giây trước khi thử lại...")
            await asyncio.sleep(RECONNECT_DELAY)
    finally:
        _reconnect_in_progress = False


def disconnected_callback(client: BleakClient):
    logging.warning(f"Đã bị ngắt kết nối với {client.address}. Bắt đầu reconnect...")
    asyncio.create_task(reconnect(client))


async def connect_and_pair(mac_address) -> BleakClient | None:
    start_time = time.perf_counter()
    client = BleakClient(mac_address, disconnected_callback=disconnected_callback)
    try:
        # Kết nối đến thiết bị
        if not client.is_connected:
            await client.connect()
            if not client.is_connected:
                logging.error(f"Failed to connect to {mac_address}.")
                return None

        # Thực hiện pairing
        paired = await client.pair(protection_level=1)
        if paired:
            logging.info("Pairing thành công!")
        else:
            logging.warning("Pairing không thành công hoặc không cần thiết.")

        # Kiểm tra lại kết nối sau khi pair
        if not client.is_connected:
            await client.connect()
            if not client.is_connected:
                logging.error(f"Failed to reconnect after pairing.")
                return None

        # Trả về client nếu thành công
        end_time = time.perf_counter()
        logging.info(f"Pairing and trusting took {end_time - start_time} seconds")
        return client

    except Exception as e:
        logging.error(f"Error: {e}")
        # Đóng kết nối nếu có lỗi
        if client.is_connected:
            await client.disconnect()
        return None
