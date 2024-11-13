import click
import logging
import os, sys
import signal
import time

from config.config import ConfigSettings as config
from core.hub import Hub
from log.log import setup_logging


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


@click.command()
@click.option('--log-level', type=click.Choice(['debug', 'info', 'warning', 'error', 'critical']), default='info', help='Set the log level')
@click.option('--serial-number', help='The serial number of the hub', default='')
@click.option('--auto-scan', help='Automatically scan for devices', default=False, is_flag=True)
@click.option('--auto-collect', help='Automatically collect data from emulator device', default=False, is_flag=True)
def main(log_level, serial_number, auto_scan, auto_collect):
    setup_logging(log_level)

    if serial_number == '':
        serial_number = get_hardware_id() # Using hardware ID as serial number
    if serial_number == None:
        serial_number = config().get('settings', 'hub_serial_no')
        logging.error("Failed to get hardware ID - using default serial number: " + serial_number)
    else:
        config().set('settings', 'hub_serial_no', serial_number)

    logging.info("Starting Smart Hub with serial number: " + serial_number)
    hub = Hub(serial_number)

    if auto_scan:
        hub.command = "scan_devices"

    # delay before starting the loop
    startup_delay = 3
    # ping google
    res = os.system("ping -c 1 google.com")
    if res == 0:
        startup_delay = 0
    else:
        logging.info(f"Startup delayed to allow for network connection to be established")

    while startup_delay > 0:
        logging.info(f"Starting in {startup_delay} seconds...")
        time.sleep(1)
        startup_delay -= 1

    if hub.startup():
        hub.loop(auto_collect, period=5)
    else:
        logging.error("Failed to start Smart Hub.")




    logging.info("Exiting Smart Hub... End of Program")
    # KeyboardInterrupt here
    os._exit(0)
    return


if __name__ == "__main__":
    main()



