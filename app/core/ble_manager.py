


import logging
from bleak import BleakScanner, BleakClient

class BLEManager:
    def __init__(self):
        self.scanner = BleakScanner()
        pass
    

    async def scan_by_plugin(self, plugin, timeout=5) -> list:
        logging.info("Scanning for devices in plugin: " + plugin.__class__.__name__ + "...")
        search = plugin.SearchableDevice()

        if search.scan_filter_method == 'emulator':
            logging.info("Adding emulators:")
            new_emulator = plugin.Device()
            plugin.devices[new_emulator.mac_address] = new_emulator
            self.list_devices(plugin)
            return 

        def filter_func(result: tuple) -> bool:
            _, adv_data = result
            if search.scan_filter_method == 'device_name':
                if adv_data.local_name and search.scan_filter in adv_data.local_name:
                    return True
            elif search.scan_filter_method == 'uuid':
                if adv_data.service_uuids and any(search.scan_filter == str(uuid) for uuid in adv_data.service_uuids):
                    return True
            elif search.scan_filter_method == 'advertisement_data':
                if adv_data.manufacturer_data:
                    manufacturer_data_bytes = b''
                    for key, value in adv_data.manufacturer_data.items():
                        manufacturer_data_bytes += bytes([key & 0xFF, key >> 8]) + value
                    if search.scan_filter in manufacturer_data_bytes:
                        return True
            return False
        
        results = await self.scanner.discover(timeout=timeout, return_adv=True)
        for _, result in results.items():
            logging.debug(result)
            if filter_func(result):
                new_device = plugin.Device(result[0].address, result[0].name)
                plugin.devices[result[0].address] = new_device

        self.list_devices(plugin)
        return 


    def list_devices(self, plugin) -> None:
        for id, device in plugin.devices.items():
            logging.info(f"  {id} - {device.device_name} - {device.device_description}")



    async def connect_device(self, device) -> BleakClient:
        logging.info(f"Connecting to device: {device.device_name} ({device.mac_address})")
        client = BleakClient(device.mac_address)
        await client.connect()
        return client

