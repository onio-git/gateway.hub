#!/usr/bin/env python3

import os
import subprocess
import threading
import time
from flask import Flask, request, redirect, render_template, url_for
from config.config import ConfigSettings as config
import logging
from waitress import serve
import signal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='/opt/gateway.hub/app/templates', static_folder='/opt/gateway.hub/app/templates/static')

# Event to signal script termination
stop_event = threading.Event()


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


def run_command(command) -> str:
    """Runs a shell command and returns the output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command '{' '.join(command)}' failed with error code {e.returncode}: {e.stderr.strip()}")
        return ""


def scan_wifi_networks(min_signal_strength=-70) -> list:
    """Scans for available Wi-Fi networks and returns a list of unique networks with signal strength above the specified threshold."""
    try:
        # Run the command with a timeout of 5 seconds
        result = subprocess.run(['iwlist', 'wlan0', 'scan'], capture_output=True, text=True, timeout=5)
        networks = []
        ssid_set = set()
        cells = result.stdout.split('Cell ')
        for cell in cells:
            if 'ESSID' in cell:
                # Extract SSID
                essid_line = [line for line in cell.split('\n') if 'ESSID' in line]
                if not essid_line:
                    continue
                essid_line = essid_line[0]
                essid = essid_line.split(':', 1)[1].strip().strip('"')

                # Skip empty SSIDs
                if not essid:
                    continue

                # Extract Signal Strength
                signal_line = [line for line in cell.split('\n') if 'Signal level' in line]
                if signal_line:
                    signal_part = signal_line[0].split('Signal level=')[1]
                    # Handle different signal strength formats
                    if ' dBm' in signal_part:
                        signal_strength = int(signal_part.split(' dBm')[0])
                    else:
                        signal_strength = int(signal_part)

                    # Filter based on signal strength and duplicates
                    if signal_strength >= min_signal_strength and essid not in ssid_set:
                        networks.append((essid, signal_strength))
                        ssid_set.add(essid)

        # Sort networks by signal strength descending
        networks.sort(key=lambda x: x[1], reverse=True)
        return networks
    except subprocess.TimeoutExpired:
        logger.error("Wi-Fi scan timed out after 5 seconds.")
        return []
    except Exception as e:
        logger.error(f"Failed to scan Wi-Fi networks: {e}")
        return []


def connect_to_wifi(ssid, password) -> None:
    """Connect to the specified Wi-Fi network using NetworkManager."""
    try:
        # Sanitize inputs
        ssid_escaped = ssid.replace('"', '\\"')
        password_escaped = password.replace('"', '\\"')

        # Create a new connection profile and connect
        run_command([
            'nmcli', 'device', 'wifi', 'connect', ssid_escaped,
            'password', password_escaped
        ])

        # Set autoconnect to yes for the connection
        run_command([
            'nmcli', 'connection', 'modify', ssid_escaped,
            'connection.autoconnect', 'yes'
        ])

        # Wait for connection
        time.sleep(10)

        # Check if connected
        connected_ssid = run_command(['iwgetid', '-r'])
        if connected_ssid == ssid:
            logger.info(f"Connected successfully to {ssid}")
            return

        logger.error(f"Failed to connect to {ssid}")
    except Exception as e:
        logger.error(f"Failed to connect to Wi-Fi: {e}")


def terminate_process_by_name(process_name) -> None:
    try:
        # Get the list of PIDs matching the process name
        logging.info(f"Terminating process {process_name}...")
        pid_list = subprocess.check_output(['pgrep', '-f', process_name]).split()
        for pid in pid_list:
            # Simulate keyboard interrupt to gracefully terminate the process
            os.kill(int(pid), signal.SIGTERM)
            logging.info(f"Terminated process {process_name} with PID {pid.decode()}")
    except subprocess.CalledProcessError:
        logging.info(f"No process named {process_name} found.")


@app.route('/generate_204')
@app.route('/hotspot-detect.html')
@app.route('/library/test/success.html')
@app.route('/success.txt')
@app.route('/ncsi.txt')
@app.route('/connecttest.txt')
@app.route('/redirect')
@app.route('/canonical.html')
@app.route('/hotspotdetect.html')
@app.route('/fwlink/')
def captive_portal_redirect():
    logger.info(f"Redirecting to captive portal for {request.path}")
    # Redirect to the local captive portal page (Flask server's root)
    return redirect('/captive_portal', code=302)


@app.route('/cancel', methods=['GET', 'POST'])
def cancel():
    logger.info("Cancel requested by user.")
    # Terminate the hotspot by exiting the script called portal.py
    terminate_process_by_name('portal')
    return 'Hotspot has been terminated.'


@app.route('/captive_portal', defaults={'path': ''}, methods=['GET', 'POST'])
def captive_portal(path=''):
    networks = scan_wifi_networks()
    if request.method == 'POST':
        ssid = request.form.get('ssid')
        password = request.form.get('password')

        # Sanitize inputs
        ssid = ssid.strip()
        password = password.strip()

        # Input validation
        if not ssid or not password:
            return 'SSID and password are required.', 400

        threading.Thread(target=connect_to_wifi, args=(ssid, password)).start()
        return 'Attempting to connect to network... Please wait.'
    else:
        logger.info("Serving captive portal page...")
        return render_template("portal.html", networks=networks, serial_number=serial_number)
    


@app.route('/reboot', methods=['GET', 'POST'])
def reboot():
    logger.info("Reboot requested by user.")
    subprocess.run(['sudo', 'hub_reboot'])
    return 'Rebooting...', 200


@app.route('/hotspot_mode', methods=['GET', 'POST'])
def hotspot_mode():
    logger.info("Hotspot mode requested by user.")
    subprocess.run(['sudo', 'hub_portal'])
    return 'Hotspot mode activated...', 200



@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
def index(path = ''):
    logger.info("Request received for index page.")

    logger.info("Scanning Wi-Fi networks...")
    networks = scan_wifi_networks()

    current_ssid = run_command(['iwgetid', '-r'])
    rssi = 'N/A'
    if current_ssid:
        rssi = run_command(['iwconfig', 'wlan0']).split('Signal level=')[1].split(' dBm')[0]
    else:
        current_ssid = "No Wi-Fi"
    
    current_ethernet = "Connected" if "100 (connected)" in run_command(['nmcli', 'device', 'show', 'eth0']) else "Disconnected"
    if not current_ssid:
        current_ssid = "No Wi-Fi"

    temperature = float(run_command(['vcgencmd', 'measure_temp']).split('=')[1].split('\'')[0])
    system_voltage = run_command(['vcgencmd', 'measure_volts', 'core']).split('=')[1].split('V')[0]
    memory_usage_output = run_command(['free', '-m']).split('\n')[1]
    memory_usage = round(int(memory_usage_output.split()[2]) / int(memory_usage_output.split()[1]) * 100, 0)
    system_time = run_command(['date'])

    connection_status = run_command(['ping', '-I', 'wlan0', '-c', '1', 'google.com'])
    if connection_status:
        connection_status = "Connected"
    ip_address = run_command(['hostname', '-I'])

    logger.info("Serving index page...")

    return render_template("index.html", 
                        serial_number=serial_number, 
                        networks=networks,
                        current_ssid=current_ssid, 
                        temperature=temperature, 
                        system_voltage=system_voltage, 
                        memory_usage=memory_usage, 
                        hardware_model=hardware_model, 
                        software_version=software_version,
                        system_time=system_time,
                        current_ethernet=current_ethernet,
                        connection_status=connection_status,
                        ip_address=ip_address,
                        signal_strength=rssi
                        )


@app.route('/restart_services', methods=['GET', 'POST'])
def restart_services():
    logger.info("Restarting services requested by user.")
    subprocess.run(['systemctl', 'restart', 'SmarthubManager.service'])
    return 'Restarting services...' , 200



if __name__ == '__main__':
    serial_number = get_hardware_id().capitalize() # Using hardware ID as serial number
    if serial_number == None:
        serial_number = serial_number if serial_number != '' else config().get('settings', 'hub_serial_no')
        logging.error("Failed to get hardware ID - using default serial number: " + serial_number)

    hardware_model = run_command(['cat', '/sys/firmware/devicetree/base/model'])
    software_version = "1.0.0"

    try:
        logger.info("Starting server...")
        serve(app, host='0.0.0.0', port=80)
    except KeyboardInterrupt:
        logger.warning("Keyboard Interrupt")
        pass
