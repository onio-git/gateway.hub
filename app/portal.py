#!/usr/bin/env python3

import os
import subprocess
import threading
import time
from flask import Flask, render_template_string, request, redirect
import logging
import signal
import atexit
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Hardcoded SSID and password for the hotspot
HOTSPOT_SSID = "ONiO Smarthub RPi"
HOTSPOT_PASSWORD = "onio.com"

# Event to signal script termination
stop_event = threading.Event()

# Global variable to store scanned networks
networks = []

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
        # Scan for Wi-Fi networks before deactivating Wi-Fi
        global networks
        networks = scan_wifi_networks()
        logger.info(f"Found {len(networks)} Wi-Fi networks.")

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

@app.route('/generate_204')
@app.route('/hotspot-detect.html')
@app.route('/library/test/success.html')
@app.route('/success.txt')
@app.route('/ncsi.txt')
@app.route('/connecttest.txt')
@app.route('/redirect')
@app.route('/canonical.html')
@app.route('/hotspotdetect.html')
def captive_portal_redirect():
    logger.info(f"Redirecting to captive portal for {request.path}")
    # Redirect to the local captive portal page (Flask server's root)
    return redirect('/', code=302)

@app.route('/fwlink/')
def windows_captive_portal():
    logger.info("Redirecting to captive portal for /fwlink/")
    return redirect('/', code=302)

@app.route('/cancel', methods=['GET', 'POST'])
def cancel():
    logger.info("Cancel requested by user.")
    global stop_event
    stop_event.set()
    return 'Hotspot has been terminated.'

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.route('/', methods=['GET', 'POST'])
def index():
    logger.info("Serving captive portal page...")
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
        return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Wi-Fi Configuration</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background-color: #f2f2f2;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        width: 100vw;
                        margin: 0;
                    }
                    .container {
                        background-color: #fff;
                        padding: 20px 30px;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                        width: 80vw;
                        height: 80vh;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                    }
                    h1 {
                        text-align: center;
                        margin-bottom: 24px;
                        color: #333;
                        font-size: 3rem;
                    }
                    label {
                        display: block;
                        margin-bottom: 8px;
                        color: #555;
                        font-size: 1.5rem;
                    }
                    select, input[type="password"] {
                        width: 100%;
                        padding: 12px;
                        margin-bottom: 16px;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                        box-sizing: border-box;
                        font-size: 1.5rem;
                    }
                    .button-group {
                        display: flex;
                        gap: 10px;
                    }
                    input[type="submit"], button {
                        width: calc(50% - 5px);
                        background-color: #4CAF50;
                        color: white;
                        padding: 15px 20px;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 1.75rem;
                    }
                    input[type="submit"]:hover {
                        background-color: #45a049;
                    }
                    button {
                        background-color: #f44336;
                    }
                    button:hover {
                        background-color: #e53935;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Connect to Wi-Fi</h1>
                    <form method="post">
                        <label for="ssid">Select Network:</label>
                        <select name="ssid" id="ssid" required>
                            {% for ssid, signal_strength in networks %}
                                <option value="{{ ssid }}">{{ ssid }} ({{ signal_strength }} dBm)</option>
                            {% endfor %}
                        </select>
                        <label for="password">Password:</label>
                        <input type="password" name="password" id="password">
                        <div class="button-group">
                            <input type="submit" value="Connect">
                            <button type="submit" formaction="/cancel">Cancel</button>
                        </div>
                    </form>
                </div>
            </body>
            </html>
        ''', networks=networks)

def scan_wifi_networks(min_signal_strength=-70):
    """Scans for available Wi-Fi networks and returns a list of unique networks with signal strength above the specified threshold."""
    try:
        result = subprocess.run(['iwlist', 'wlan0', 'scan'], capture_output=True, text=True)
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
                essid = essid_line.split(':')[1].strip().strip('"')

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
    except Exception as e:
        logger.error(f"Failed to scan Wi-Fi networks: {e}")
        return []

def connect_to_wifi(ssid, password):
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
            # Signal to stop the script
            stop_event.set()
            return

        logger.error(f"Failed to connect to {ssid}")
    except Exception as e:
        logger.error(f"Failed to connect to Wi-Fi: {e}")

def run_server():
    """Run the Flask server using Waitress."""
    from waitress import serve
    serve(app, host='0.0.0.0', port=8080)

def cleanup():
    """Cleanup function to tear down the hotspot on exit."""
    logger.info("Cleaning up before exit...")
    teardown_hotspot()

if __name__ == '__main__':
    # Register cleanup function
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))

    try:
        logger.info("Setting up the hotspot...")
        setup_hotspot()
        server_thread = threading.Thread(target=run_server)
        server_thread.daemon = True  # Allows the program to exit even if thread is running
        server_thread.start()

        # Wait for stop_event to be set or timeout
        stop_event.wait(timeout=300)  # Wait up to 300 seconds (5 minutes)

        logger.info("Timeout reached or stop event set. Exiting...")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        cleanup()
        sys.exit(0)
