#!/usr/bin/env python3

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import socket
import logging
import signal
import sys

class BLEAdvertisement(dbus.service.Object):
    ADVERTISEMENT_IFACE = 'org.bluez.LEAdvertisement1'
    
    def __init__(self, bus, index, advertising_type="peripheral"):
        self.path = f"/org/bluez/advertising{index}"
        self.bus = bus
        self.ad_type = advertising_type
        self.local_name = socket.gethostname()
        self.service_uuids = ['00420000-8f59-4420-870d-84f3b617e493']
        self.discoverable = True
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties['Type'] = self.ad_type
        properties['LocalName'] = self.local_name
        properties['ServiceUUIDs'] = self.service_uuids
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
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("/var/log/smarthub-advertiser.log"),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Initialize D-Bus
        DBusGMainLoop(set_as_default=True)
        self.mainloop = GLib.MainLoop()
        self.bus = dbus.SystemBus()
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)
        
        # Initialize adapter
        self.init_adapter()

    def init_adapter(self):
        try:
            self.adapter_path = '/org/bluez/hci0'
            adapter_object = self.bus.get_object('org.bluez', self.adapter_path)
            self.adapter = dbus.Interface(adapter_object, 'org.bluez.Adapter1')
            self.adapter_props = dbus.Interface(adapter_object, 'org.freedesktop.DBus.Properties')
            self.ad_manager = dbus.Interface(adapter_object, 'org.bluez.LEAdvertisingManager1')
            
            # Power on and configure adapter
            self.adapter_props.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(True))
            self.adapter_props.Set('org.bluez.Adapter1', 'Discoverable', dbus.Boolean(True))
            self.adapter_props.Set('org.bluez.Adapter1', 'DiscoverableTimeout', dbus.UInt32(0))
            
            logging.info("Bluetooth adapter initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize Bluetooth adapter: {e}")
            sys.exit(1)

    def register_advertisement(self):
        try:
            self.advertisement = BLEAdvertisement(self.bus, 0)
            self.ad_manager.RegisterAdvertisement(
                self.advertisement.path,
                {},
                reply_handler=self.register_ad_cb,
                error_handler=self.register_ad_error_cb
            )
        except Exception as e:
            logging.error(f"Failed to register advertisement: {e}")
            sys.exit(1)

    def register_ad_cb(self):
        logging.info("Advertisement registered successfully")

    def register_ad_error_cb(self, error):
        logging.error(f"Failed to register advertisement: {error}")
        self.cleanup()
        sys.exit(1)

    def handle_signal(self, signum, frame):
        logging.info(f"Received signal {signum}")
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        try:
            if hasattr(self, 'advertisement'):
                self.ad_manager.UnregisterAdvertisement(self.advertisement.path)
            if hasattr(self, 'mainloop') and self.mainloop.is_running():
                self.mainloop.quit()
            logging.info("Cleanup completed successfully")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    def run(self):
        try:
            self.register_advertisement()
            logging.info(f"Starting BLE advertisement for {socket.gethostname()}")
            self.mainloop.run()
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            self.cleanup()
            sys.exit(1)

if __name__ == "__main__":
    advertiser = BLEAdvertiser()
    advertiser.run()