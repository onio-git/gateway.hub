#!/usr/bin/env python3

import os
import subprocess
import threading
import time
import signal
import sys
from flask import Flask, request

# Replace 'wlan0' with your actual Wi-Fi interface name
WIFI_INTERFACE = 'wlan0'

# Check if the script is run as root
if os.geteuid() != 0:
    print("This script must be run as root!")
    sys.exit(1)

# Flask app setup
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get Wi-Fi credentials and settings from the form
        ssid = request.form.get('ssid')
        password = request.form.get('wpa')
        # Save the new Wi-Fi credentials
        save_wifi_credentials(ssid, password)
        # Signal the server to shut down
        shutdown_server()
        return "Settings saved. The Pi will now connect to the new Wi-Fi network."
    return '''
    <!DOCTYPE html><html lang='en'><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body, html {height: 100%;margin: 0;}.geometric-bg {background-color: #1a202c; /* Dark background color */height: 100%;display: flex;justify-content: center;align-items: center;overflow: hidden;position: relative;}.shape {position: absolute;background-color: rgba(255, 255, 255, 0.1); /* Subtle shape color */border-radius: 15%;}.shape.large {width: 300px;height: 300px;top: 20%;left: 10%;}.shape.medium {width: 200px;height: 200px;bottom: 30%;right: 15%;}.shape.small {width: 100px;height: 100px;bottom: 20%;left: 40%;}.form-container {position: relative;display: flex;justify-content: center;align-items: center;flex-direction: column;z-index: 1; /* Ensures form appears above background */max-width: 300px;padding: 20px;background-color: rgba(255, 255, 255, 0.8); /* Semi-transparent white */border-radius: 10px;box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);}form {display: flex;flex-direction: column;align-items: center;padding: 10px;}input[type='text'], input[type='password'] {width: 90%; /* Full width of the container */margin-bottom: 15px;padding: 10px;border: 1px solid #ddd; /* Light grey border */border-radius: 5px;}input[type='submit'] {padding: 10px 20px;color: white;background-color: #fd9001; /* Bootstrap primary color */border: none;border-radius: 5px;cursor: pointer;width: 100%;}input[type='submit']:hover {background-color: #b86800; /* Darker on hover */}</style></head><body><div class='geometric-bg'><div class='shape large'></div><div class='shape medium'></div><div class='shape small'></div><div class='form-container'><div class='logo'><svg width='127' height='34' fill='black' ><g clip-path='url(#clip0)' fill='#000'><path d='M30.012 17.64c0 8.983-5.71 16.396-15.006 16.396C5.6 34.036 0 26.586 0 17.64S5.636 1.242 14.97 1.242c9.332 0 15.042 7.486 15.042 16.397zM14.969 29.544c6.771 0 9.516-5.953 9.516-11.906S21.703 5.734 14.933 5.734c-6.771 0-9.48 5.989-9.48 11.905 0 5.916 2.818 11.906 9.516 11.906zM40.588 1.972l14.31 23.044h.074V1.972h5.234V33.27h-5.783L40.149 10.262h-.146V33.27h-5.197V1.972h5.782zm30.561 0V6.72h-5.014V1.972h5.014zm0 8.655V33.27h-5.014V10.627h5.014zm34.55 7.013c0 8.983-5.71 16.396-15.006 16.396-9.406 0-15.005-7.45-15.005-16.397S81.36 1.242 90.692 1.242c9.333 0 15.006 7.486 15.006 16.397zM90.657 29.544c6.77 0 9.516-5.953 9.516-11.906s-2.819-11.905-9.59-11.905c-6.77 0-9.479 5.989-9.479 11.905 0 5.916 2.855 11.906 9.553 11.906zM127 9.568c0 5.332-3.953 9.568-9.37 9.568-5.49 0-9.442-4.126-9.442-9.568C108.188 4.2 112.177 0 117.63 0S127 4.236 127 9.568zm-9.37 7.888c4.465 0 7.32-3.615 7.32-7.888s-2.855-7.888-7.356-7.888c-4.502 0-7.357 3.615-7.357 7.888 0 4.346 2.818 7.888 7.393 7.888zm.476-13c2.525 0 3.77.949 3.77 3.03 0 1.754-.989 2.703-2.782 2.886l2.965 4.638h-1.977l-2.745-4.529h-1.647v4.529h-1.756V4.419l4.172.036zm-.329 4.564c1.866 0 2.342-.547 2.342-1.643 0-.986-.732-1.424-2.196-1.424h-2.233v3.104l2.087-.037z'/></g><defs><clipPath id='clip0'><path fill='#fff' d='M0 0h127v34H0z'/></clipPath></defs></svg></div><form method='POST' action='/configure_complete'><input type='text' id='ssid' name='ssid' placeholder='Wifi SSID'><input type='password' id='wpa' name='wpa' placeholder='Wifi Password'><input type='submit' value='Connect'></form></div></body></html>";
    '''

def save_wifi_credentials(ssid, password):
    # Create the wpa_supplicant configuration
    wpa_supplicant_conf = f"""country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    psk="{password}"
}}
"""
    # Write the configuration to the file
    with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as f:
        f.write(wpa_supplicant_conf)
    # Restart networking services to apply new settings
    subprocess.run(['wpa_cli', '-i', WIFI_INTERFACE, 'reconfigure'])

def shutdown_server():
    # Function to stop the Flask server
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()

def start_flask_app():
    # Start the Flask app
    app.run(host='0.0.0.0', port=80)

def setup_hostapd():
    # Hostapd configuration
    hostapd_conf = f"""interface={WIFI_INTERFACE}
driver=nl80211
ssid=ONiO Smarthub (Pi)
hw_mode=g
channel=6
country_code=NO
ieee80211n=1
ieee80211d=1
ht_capab=[SHORT-GI-20]
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_passphrase=onio-hub
rsn_pairwise=CCMP
"""
    with open('/tmp/hostapd.conf', 'w') as f:
        f.write(hostapd_conf)
    
    # Start hostapd
    global hostapd_process
    hostapd_process = subprocess.Popen(['hostapd', '/tmp/hostapd.conf'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def setup_dnsmasq():
    # Dnsmasq configuration
    dnsmasq_conf = f"""interface={WIFI_INTERFACE}
bind-interfaces
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/192.168.4.1
"""
    with open('/tmp/dnsmasq.conf', 'w') as f:
        f.write(dnsmasq_conf)
    
    # Start dnsmasq
    global dnsmasq_process
    dnsmasq_process = subprocess.Popen(['dnsmasq', '-C', '/tmp/dnsmasq.conf'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def configure_network():
    # Bring down the Wi-Fi interface
    subprocess.run(['ip', 'link', 'set', WIFI_INTERFACE, 'down'])
    
    # Flush existing IP addresses
    subprocess.run(['ip', 'addr', 'flush', 'dev', WIFI_INTERFACE])
    
    # Assign the static IP
    subprocess.run(['ip', 'addr', 'add', '192.168.4.1/24', 'dev', WIFI_INTERFACE])
    
    # Bring up the Wi-Fi interface
    subprocess.run(['ip', 'link', 'set', WIFI_INTERFACE, 'up'])
    
    # Enable IP forwarding
    subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'])
    
    # Set up iptables rules
    subprocess.run(['iptables', '-t', 'nat', '-A', 'PREROUTING', '-i', WIFI_INTERFACE,
                    '-p', 'tcp', '--dport', '80', '-j', 'DNAT', '--to-destination', '192.168.4.1:80'])
    subprocess.run(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-j', 'MASQUERADE'])
    subprocess.run(['iptables', '-A', 'FORWARD', '-i', WIFI_INTERFACE, '-j', 'ACCEPT'])


def cleanup():
    # Bring down Wi-Fi interface
    subprocess.run(['ip', 'link', 'set', WIFI_INTERFACE, 'down'])

    # Disable IP forwarding
    subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=0'])

    # Flush iptables rules
    subprocess.run(['iptables', '-t', 'nat', '-F'])
    subprocess.run(['iptables', '-F'])

    # Kill hostapd and dnsmasq processes
    if hostapd_process:
        hostapd_process.terminate()
    if dnsmasq_process:
        dnsmasq_process.terminate()

def main():
    global hostapd_process, dnsmasq_process
    hostapd_process = None
    dnsmasq_process = None
    try:
        print("Configuring network...")
        configure_network()
        print("Setting up hostapd...")
        setup_hostapd()
        time.sleep(2)  # Give hostapd time to start
        if hostapd_process.poll() is not None:
            stderr = hostapd_process.stderr.read().decode()
            print(f"hostapd failed to start:\n{stderr}")
            return
        print("Setting up dnsmasq...")
        setup_dnsmasq()
        time.sleep(2)  # Give dnsmasq time to start
        if dnsmasq_process.poll() is not None:
            stderr = dnsmasq_process.stderr.read().decode()
            print(f"dnsmasq failed to start:\n{stderr}")
            return
        print("Starting Flask server...")
        # Start Flask app in a separate thread
        flask_thread = threading.Thread(target=start_flask_app)
        flask_thread.start()
        print("Setup complete. Connect to the 'Pi_AP' network to configure Wi-Fi.")
        # Wait for 5 minutes or until settings are saved
        start_time = time.time()
        while time.time() - start_time < 300 and flask_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        print("Cleaning up...")
        cleanup()
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
