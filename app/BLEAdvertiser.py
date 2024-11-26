#!/usr/bin/env python3

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import socket
import logging
import signal
import sys
import subprocess
import threading
import time
import random

class BLEAdvertisement(dbus.service.Object):
    ADVERTISEMENT_IFACE = 'org.bluez.LEAdvertisement1'
    
    def __init__(self, bus, index, manufacturer_data=None):
        self.path = f"/org/bluez/example/advertisement{index}"
        self.bus = bus
        self.ad_type = "peripheral"
        self.local_name = socket.gethostname()
        self.service_uuids = ['00420000-8f59-4420-870d-84f3b617e493']
        self.manufacturer_data = manufacturer_data or {
            0x004F: dbus.Array([dbus.Byte(0x00), dbus.Byte(0x00)], signature=dbus.Signature('y'))
        }
        self.discoverable = True
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties['Type'] = self.ad_type
        properties['LocalName'] = self.local_name
        properties['ServiceUUIDs'] = self.service_uuids
        properties['ManufacturerData'] = dbus.Dictionary(self.manufacturer_data, signature='qv')
        properties['Discoverable'] = dbus.Boolean(self.discoverable)
        return {self.ADVERTISEMENT_IFACE: properties}

    @dbus.service.method(ADVERTISEMENT_IFACE, in_signature='', out_signature='')
    def Release(self):
        logging.info(f'Released BLE Advertisement for {self.local_name}')

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != self.ADVERTISEMENT_IFACE:
            raise dbus.exceptions.InvalidArguments
        return self.get_properties()[self.ADVERTISEMENT_IFACE]

class BLEAdvertiser:
    def __init__(self):
        self._setup_logging()
        self.running = True
        self.current_advertisement = None
        self.mainloop = None
        self.bus = None
        self.adapter = None
        self.ad_manager = None
        
        # Initialize D-Bus and adapter
        try:
            self._init_dbus()
            self._setup_signal_handlers()
            self._init_adapter()
            self._wait_for_bluetooth_ready()
        except Exception as e:
            logging.error(f"Initialization error: {e}")
            sys.exit(1)

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("/var/log/smarthub-advertiser.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def _init_dbus(self):
        try:
            DBusGMainLoop(set_as_default=True)
            self.mainloop = GLib.MainLoop()
            self.bus = dbus.SystemBus()
            logging.info("D-Bus initialized successfully")
        except Exception as e:
            logging.error(f"D-Bus initialization failed: {e}")
            raise

    def _wait_for_bluetooth_ready(self):
        """Wait for bluetooth service to be fully ready"""
        max_attempts = 30
        attempt = 0
        while attempt < max_attempts:
            try:
                subprocess.check_call(['hciconfig', 'hci0', 'up'])
                # Try to get adapter properties
                props = self.adapter_props.GetAll('org.bluez.Adapter1')
                if props.get('Powered', False):
                    logging.info("Bluetooth adapter is ready")
                    return True
            except Exception:
                attempt += 1
                if attempt >= max_attempts:
                    raise Exception("Bluetooth adapter not ready after maximum attempts")
                time.sleep(1)
        return False

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

    def _init_adapter(self):
        retries = 3
        retry_delay = 2

        for attempt in range(retries):
            try:
                self.adapter_path = '/org/bluez/hci0'
                adapter_object = self.bus.get_object('org.bluez', self.adapter_path)
                self.adapter = dbus.Interface(adapter_object, 'org.bluez.Adapter1')
                self.adapter_props = dbus.Interface(adapter_object, 'org.freedesktop.DBus.Properties')
                self.ad_manager = dbus.Interface(adapter_object, 'org.bluez.LEAdvertisingManager1')
                
                # Reset adapter
                subprocess.run(['hciconfig', 'hci0', 'reset'], check=True)
                time.sleep(1)
                
                # Configure adapter
                self.adapter_props.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(True))
                time.sleep(1)
                self.adapter_props.Set('org.bluez.Adapter1', 'Discoverable', dbus.Boolean(True))
                self.adapter_props.Set('org.bluez.Adapter1', 'DiscoverableTimeout', dbus.UInt32(0))
                
                logging.info("Bluetooth adapter initialized successfully")
                return
            except Exception as e:
                if attempt < retries - 1:
                    logging.warning(f"Adapter initialization attempt {attempt + 1} failed: {e}")
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Failed to initialize Bluetooth adapter after {retries} attempts: {e}")
                    raise

    def update_network_status(self):
        try:
            # Check WiFi
            wifi_connected = False
            rssi = -100
            try:
                wifi_output = subprocess.check_output(['iwconfig', 'wlan0'], stderr=subprocess.PIPE).decode()
                if "ESSID:\"" in wifi_output:
                    wifi_connected = True
                    rssi_part = wifi_output.split('Signal level=')[1].split(' ')[0]
                    rssi = int(rssi_part)
            except Exception as e:
                logging.warning(f"Error checking WiFi: {e}")

            # Check Ethernet
            eth_connected = False
            try:
                with open('/sys/class/net/eth0/carrier', 'r') as f:
                    eth_connected = f.read().strip() == '1'
            except Exception as e:
                logging.warning(f"Error checking Ethernet: {e}")

            return wifi_connected, eth_connected, rssi
        except Exception as e:
            logging.error(f"Error in network status check: {e}")
            return False, False, -100

    def register_advertisement(self, advertisement):
        """Register advertisement with retries"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.ad_manager.RegisterAdvertisement(
                    advertisement.path,
                    {},
                    timeout=10  # Add timeout
                )
                logging.info(f"Advertisement registered successfully on attempt {attempt + 1}")
                return True
            except Exception as e:
                if attempt < max_attempts - 1:
                    logging.warning(f"Registration attempt {attempt + 1} failed: {e}")
                    time.sleep(2)
                else:
                    logging.error(f"Failed to register advertisement after {max_attempts} attempts")
                    raise
        return False

    def unregister_advertisement(self, advertisement):
        """Unregister advertisement with retries"""
        if not advertisement:
            return

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.ad_manager.UnregisterAdvertisement(advertisement.path, timeout=10)
                return True
            except Exception as e:
                if attempt < max_attempts - 1:
                    logging.warning(f"Unregister attempt {attempt + 1} failed: {e}")
                    time.sleep(2)
                else:
                    logging.error("Failed to unregister advertisement")
                    return False

    def update_advertisement_data(self):
        while self.running:
            try:
                wifi_on, eth_on, rssi = self.update_network_status()
                
                # Create status byte
                status = 0x00
                if wifi_on:
                    status |= 0x80
                if eth_on:
                    status |= 0x40
                
                rssi_byte = min(255, max(0, rssi + 100))
                
                manufacturer_data = {
                    0x004F: dbus.Array([dbus.Byte(status), dbus.Byte(rssi_byte)], 
                                     signature=dbus.Signature('y'))
                }

                # Unregister old advertisement
                if self.current_advertisement:
                    self.unregister_advertisement(self.current_advertisement)
                    time.sleep(1)  # Wait a bit between operations

                # Create and register new advertisement
                new_advertisement = BLEAdvertisement(self.bus, random.randint(0, 10000), manufacturer_data)
                if self.register_advertisement(new_advertisement):
                    self.current_advertisement = new_advertisement
                    logging.info(f"Advertisement updated - WiFi: {wifi_on}, Ethernet: {eth_on}, RSSI: {rssi}")
                
            except Exception as e:
                logging.error(f"Error in advertisement update: {e}")
                time.sleep(5)  # Wait before retrying on error
            
            # Sleep for 60 seconds
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(1)

    def handle_signal(self, signum, frame):
        logging.info(f"Received signal {signum}")
        self.cleanup()

    def cleanup(self):
        logging.info("Starting cleanup...")
        self.running = False
        
        if self.current_advertisement:
            self.unregister_advertisement(self.current_advertisement)
        
        if self.mainloop and self.mainloop.is_running():
            self.mainloop.quit()
        
        logging.info("Cleanup completed")

    def run(self):
        try:
            update_thread = threading.Thread(target=self.update_advertisement_data)
            update_thread.daemon = True
            update_thread.start()
            
            logging.info(f"Starting BLE advertisement for {socket.gethostname()}")
            self.mainloop.run()
            
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            self.cleanup()
            sys.exit(1)
        finally:
            self.cleanup()

if __name__ == "__main__":
    try:
        advertiser = BLEAdvertiser()
        advertiser.run()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)