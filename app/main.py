import click
import logging


from config.config import ConfigSettings as config
from core.hub import Hub
from log.log import setup_logging



@click.command()
@click.option('--ssid', help='The SSID of the wifi network to connect to', default='')
@click.option('--password', help='The password of the wifi network to connect to', default='')
@click.option('--log-level', type=click.Choice(['debug', 'info', 'warning', 'error', 'critical']), default='info', help='Set the log level')
@click.option('--serial-number', help='The serial number of the hub', default='')
@click.option('--auto-scan', help='Automatically scan for devices', default=False, is_flag=True)
@click.option('--auto-collect', help='Automatically collect data from emulator device', default=False, is_flag=True)


def main(ssid, password, log_level, serial_number, auto_scan, auto_collect):
    setup_logging(log_level)

    serial_number = serial_number if serial_number != '' else config().get('settings', 'hub_serial_no')
    logging.info("Starting Smart Hub with serial number: " + serial_number)
    hub = Hub(ssid, password, serial_number)
    
    if auto_scan:
        hub.command = "scan_devices"

    if hub.startup(): 
        hub.loop(auto_collect, period=5)
    else:
        logging.error("Failed to start Smart Hub.")




    logging.info("Exiting Smart Hub... End of Program")
    return


if __name__ == "__main__":
    main()