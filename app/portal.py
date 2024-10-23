#!/usr/bin/env python3

import os
import subprocess
import threading
import time
from flask import Flask, request, redirect, render_template
from config.config import ConfigSettings as config
import logging
import signal
import atexit
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='/opt/gateway.hub/app/templates')


# Hardcoded SSID and password for the hotspot
HOTSPOT_SSID = "ONiO Smarthub RPi"
HOTSPOT_PASSWORD = "onio.com"


# Event to signal script termination
stop_event = threading.Event()

# Global variable to store scanned networks
networks = []

def get_hardware_id() -> str:
    # 1. Try to get the CPU serial number (specific to Raspberry Pi)
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.readlines()
        for line in cpuinfo:
            if line.startswith('Serial'):
                serial = line.strip().split(':')[1].strip()
                if serial != '0000000000000000':
                    return serial
    except Exception as e:
        pass  # Proceed to the next method if this fails

    # 2. Try to get the DMI system UUID (works on many Linux systems)
    try:
        uuid_path = '/sys/class/dmi/id/product_uuid'
        if os.path.exists(uuid_path):
            with open(uuid_path, 'r') as f:
                system_uuid = f.read().strip()
            if system_uuid:
                return system_uuid
    except Exception as e:
        pass  # Proceed to the next method if this fails

    # If all methods fail
    return None





def run_command(command):
    """Runs a shell command and returns the output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command '{' '.join(command)}' failed with error code {e.returncode}: {e.stderr.strip()}")
        return None


def setup_hotspot():
    """Set up the hotspot using NetworkManager."""
    try:
        global serial_number
        serial_number = get_hardware_id().capitalize() # Using hardware ID as serial number
        if serial_number == None:
            serial_number = serial_number if serial_number != '' else config().get('settings', 'hub_serial_no')
            logging.error("Failed to get hardware ID - using default serial number: " + serial_number)

        # Deactivate any active Wi-Fi connections
        logger.info("Deactivating active Wi-Fi connections...")
        active_connections = run_command(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'])
        if active_connections:
            for line in active_connections.splitlines():
                name, conn_type, device = line.split(':')
                if conn_type == 'wifi' and device == 'wlan0':
                    logger.info(f"Deactivating Wi-Fi connection '{name}' on '{device}'...")
                    run_command(['nmcli', 'connection', 'down', name])

        # Delete existing hotspot connection if it exists
        existing_connections = run_command(['nmcli', '-t', '-f', 'NAME', 'connection', 'show'])
        if HOTSPOT_SSID in existing_connections:
            logger.info(f"Deleting existing hotspot connection '{HOTSPOT_SSID}'...")
            run_command(['nmcli', 'connection', 'delete', HOTSPOT_SSID])

        # Create the hotspot connection
        logger.info("Creating hotspot using NetworkManager...")
        run_command([
            'nmcli', 'connection', 'add', 'type', 'wifi', 'ifname', 'wlan0',
            'con-name', HOTSPOT_SSID, 'autoconnect', 'no', 'ssid', HOTSPOT_SSID
        ])
        run_command([
            'nmcli', 'connection', 'modify', HOTSPOT_SSID,
            '802-11-wireless.mode', 'ap',
            '802-11-wireless.band', 'bg',
            'ipv4.method', 'manual',
            'ipv4.addresses', '192.168.4.1/24',
            'ipv4.never-default', 'yes',
            'ipv4.ignore-auto-dns', 'yes'
        ])
        run_command([
            'nmcli', 'connection', 'modify', HOTSPOT_SSID,
            'wifi-sec.key-mgmt', 'wpa-psk',
            'wifi-sec.psk', HOTSPOT_PASSWORD
        ])

        # Activate the hotspot
        logger.info("Activating the hotspot...")
        run_command(['nmcli', 'connection', 'up', HOTSPOT_SSID])

        # Wait for the hotspot to fully activate
        time.sleep(5)

        # Get the IP address of wlan0
        ip_output = run_command(['ip', '-4', 'addr', 'show', 'wlan0'])
        logger.info(f"wlan0 IP address:\n{ip_output}")

        return True
    except Exception as e:
        logger.error(f"Failed to set up hotspot: {e}")
        return False


def teardown_hotspot():
    """Tear down the hotspot and restore the Wi-Fi connection."""
    try:
        logger.info("Tearing down the hotspot...")

        # Deactivate the hotspot
        run_command(['nmcli', 'connection', 'down', HOTSPOT_SSID])

        # Reactivate Wi-Fi
        logger.info("Reactivating Wi-Fi...")
        run_command(['nmcli', 'radio', 'wifi', 'on'])

    except Exception as e:
        logger.error(f"Failed to teardown hotspot: {e}")


def cleanup():
    """Cleanup function to tear down the hotspot on exit."""
    logger.info("Cleaning up before exit...")
    teardown_hotspot()

def signal_handler(sig, frame):
    logger.info(f"Signal {sig} received. Setting stop event.")
    stop_event.set()
    

if __name__ == '__main__':
    # Register cleanup function
    serial_number = get_hardware_id().capitalize()  # Using hardware ID as serial number
    if serial_number is None:
        serial_number = config().get('settings', 'hub_serial_no')
        logging.error("Failed to get hardware ID - using default serial number: " + serial_number)

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Setting up the hotspot...")
        setup_hotspot()

        logger.info("Entering main loop. Waiting for stop event...")
        while not stop_event.is_set():
            time.sleep(1)  # Sleep briefly to allow signal handling

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        cleanup()
        logger.info("Portal.py has exited.")
