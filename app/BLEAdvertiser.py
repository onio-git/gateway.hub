#!/usr/bin/env python3

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import subprocess
import logging
import signal
import sys
import time

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('BLEAdvertiser')

logger = setup_logging()

class BLEAdvertisement(dbus.service.Object):
    def __init__(self, bus, path):
        self.path = path
        self.bus = bus
        self.is_registered = False
        
        super().__init__(bus, self.path)
        
        self.ad_type = "peripheral"
        self.local_name = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
        self.service_uuids = ['00420000-8f59-4420-870d-84f3b617e493']
        self.discoverable = True
        self.manufacturer_data = {
            0x004F: dbus.Array([dbus.Byte(0x00), dbus.Byte(0x00)], 
                              signature=dbus.Signature('y'))
        }
        
        logger.info(f"Created advertisement with path {path}")

    def update_manufacturer_data(self, wifi_on, eth_on, rssi):
        status = 0x00
        if wifi_on:
            status |= 0x80
        if eth_on:
            status |= 0x40
            
        rssi_byte = min(255, max(0, rssi + 100))
        
        self.manufacturer_data = {
            0x004F: dbus.Array([dbus.Byte(status), dbus.Byte(rssi_byte)], 
                              signature=dbus.Signature('y'))
        }

    @dbus.service.method("org.bluez.LEAdvertisement1", in_signature='', out_signature='')
    def Release(self):
        logger.info(f"Released advertisement at {self.path}")
        self.is_registered = False

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != "org.bluez.LEAdvertisement1":
            raise dbus.exceptions.InvalidArguments
            
        return {
            'Type': self.ad_type,
            'LocalName': self.local_name,
            'ServiceUUIDs': self.service_uuids,
            'ManufacturerData': dbus.Dictionary(self.manufacturer_data, signature='qv'),
            'Discoverable': dbus.Boolean(self.discoverable)
        }

def reset_bluetooth():
    """Hard reset of bluetooth adapter"""
    try:
        subprocess.run(['hciconfig', 'hci0', 'down'], check=True)
        time.sleep(1)
        subprocess.run(['hciconfig', 'hci0', 'up'], check=True)
        time.sleep(2)
        return True
    except Exception as e:
        logger.error(f"Failed to reset bluetooth adapter: {e}")
        return False

def check_network():
    try:
        wifi_connected = False
        rssi = -100
        wifi_output = subprocess.run(['iwconfig', 'wlan0'], capture_output=True, text=True).stdout
        
        if "ESSID:\"" in wifi_output:
            wifi_connected = True
            try:
                rssi = int(wifi_output.split('Signal level=')[1].split(' ')[0])
            except:
                rssi = -100
                
        eth_connected = subprocess.run(
            ['cat', '/sys/class/net/eth0/carrier'], 
            capture_output=True, 
            text=True
        ).stdout.strip() == '1'
        
        return wifi_connected, eth_connected, rssi
        
    except Exception as e:
        logger.error(f"Error checking network: {e}")
        return False, False, -100

def main():
    logger.info("Starting BLE Advertiser")
    
    # Start with a hard reset of bluetooth
    if not reset_bluetooth():
        logger.error("Failed to reset bluetooth adapter")
        sys.exit(1)
    
    DBusGMainLoop(set_as_default=True)
    mainloop = GLib.MainLoop()
    bus = dbus.SystemBus()
    
    try:
        # Get adapter
        adapter_obj = bus.get_object('org.bluez', '/org/bluez/hci0')
        adapter_props = dbus.Interface(adapter_obj, 'org.freedesktop.DBus.Properties')
        ad_manager = dbus.Interface(adapter_obj, 'org.bluez.LEAdvertisingManager1')
        
        # Power cycle through DBus
        adapter_props.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(False))
        time.sleep(1)
        adapter_props.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(True))
        time.sleep(2)
        logger.info("Bluetooth adapter powered on")
        
        # Create advertisement
        path = '/org/bluez/advertisement_hub'
        advertisement = BLEAdvertisement(bus, path)
        
    except Exception as e:
        logger.error(f"Failed to initialize Bluetooth: {e}")
        sys.exit(1)
    
    def register_advertisement():
        """Try to register the advertisement with error handling"""
        try:
            # Try to unregister first, ignore errors
            try:
                ad_manager.UnregisterAdvertisement(advertisement.path)
                advertisement.is_registered = False
                time.sleep(1)
            except:
                pass
            
            # Now try to register
            ad_manager.RegisterAdvertisement(advertisement.path, {}, timeout=5)
            advertisement.is_registered = True
            return True
        except dbus.exceptions.DBusException as e:
            err_name = e.get_dbus_name()
            if err_name == "org.bluez.Error.AlreadyExists":
                logger.error("Advertisement already exists, trying hard reset...")
                advertisement.is_registered = False
                if reset_bluetooth():
                    time.sleep(2)
                    try:
                        ad_manager.RegisterAdvertisement(advertisement.path, {}, timeout=5)
                        advertisement.is_registered = True
                        return True
                    except:
                        pass
            logger.error(f"Failed to register advertisement: this is fine...")
            return False
    
    def update_loop():
        try:
            # Get network status
            wifi_on, eth_on, rssi = check_network()
            
            # Update advertisement data
            advertisement.update_manufacturer_data(wifi_on, eth_on, rssi)
            
            # Check registration
            if not advertisement.is_registered:
                if register_advertisement():
                    logger.info(f"Advertisement registered - WiFi: {wifi_on}, Ethernet: {eth_on}, RSSI: {rssi}")
            else:
                logger.info(f"Updated status - WiFi: {wifi_on}, Ethernet: {eth_on}, RSSI: {rssi}")
            
        except Exception as e:
            logger.error(f"Error in update loop: {e}")
            advertisement.is_registered = False
            
        return True
    
    def cleanup(signum, frame):
        logger.info("Cleaning up...")
        try:
            if advertisement.is_registered:
                ad_manager.UnregisterAdvertisement(advertisement.path)
        except:
            pass
        mainloop.quit()
    
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    
    GLib.timeout_add_seconds(60, update_loop)
    update_loop()  # Initial update
    
    try:
        mainloop.run()
    except KeyboardInterrupt:
        cleanup(None, None)
    except Exception as e:
        logger.error(f"Main loop error: {e}")
        cleanup(None, None)
        sys.exit(1)

if __name__ == '__main__':
    main()