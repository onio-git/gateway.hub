import asyncio
from bleak import BleakClient
import logging



class XiaomiFlowerCare:
    def __init__(self, address):
        # Xiaomi service and characteristic UUIDs
        self.service_uuid = "00001204-0000-1000-8000-00805f9b34fb"
        self.access_char_uuid = "00001a00-0000-1000-8000-00805f9b34fb"
        self.read_data_uuid = "00001a01-0000-1000-8000-00805f9b34fb"
        self.read_battery_uuid = "00001a02-0000-1000-8000-00805f9b34fb"

        self.address = address
        self.client = BleakClient(address)
        self.data = {}

    async def connect_and_read(self):
        try:
            await self.client.connect()
            print(f"Connected to {self.address}")

            # Write to access characteristic
            await self.client.write_gatt_char(self.access_char_uuid, bytearray([0xA0, 0x1F]))

            # Read data characteristic
            data = await self.client.read_gatt_char(self.read_data_uuid)
            self.data['temperature'] = int.from_bytes(data[0:2], byteorder='little') / 10.0
            self.data['brightness'] = int.from_bytes(data[3:7], byteorder='little')
            self.data['moisture'] = data[7]
            self.data['conductivity'] = int.from_bytes(data[8:10], byteorder='little')

            # Read battery characteristic
            battery = await self.client.read_gatt_char(self.read_battery_uuid)
            self.data['energy'] = battery[0]
            self.data['firmware'] = battery[2:7].decode('utf-8')

            self.print_data()
        finally:
            await self.client.disconnect()
            print("Disconnected")

    def print_data(self):
        print("Xiaomi Device Data:")
        print(f"  Temperature: {self.data['temperature']} °C")
        print(f"  Brightness: {self.data['brightness']} lux")
        print(f"  Moisture: {self.data['moisture']} %")
        print(f"  Conductivity: {self.data['conductivity']} µS/cm")
        print(f"  Battery: {self.data['energy']}%")
        print(f"  Firmware: {self.data['firmware']}")

# Example usage
async def main():
    address = "5C:85:7E:B0:5C:55"  # Replace with your device's MAC address
    xiaomi_device = XiaomiFlowerCare(address)
    await xiaomi_device.connect_and_read()

# Run the main function
asyncio.run(main())