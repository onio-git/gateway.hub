#!/usr/bin/env python3

import os
import sys
import subprocess
import threading
import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from jinja2 import Template

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Global variables
HOTSPOT_SSID = 'RaspberryPiSetup'
HOTSPOT_INTERFACE = 'wlan0'
HOTSPOT_IP = '192.168.4.1'
DHCP_RANGE = '192.168.4.2,192.168.4.20,255.255.255.0,24h'

class CaptivePortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        logging.info(f"Received GET request for {self.path}")
        if self.path == '/' or self.path.startswith('/?'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            # Render the HTML form
            html_content = render_template('wifi_form.html', ssid_list=scan_wifi_networks())
            self.wfile.write(html_content.encode('utf-8'))
        else:
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()

    def do_POST(self):
        logging.info(f"Received POST request for {self.path}")
        if self.path == '/configure':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            fields = parse_qs(post_data)

            ssid = fields.get('ssid', [''])[0]
            password = fields.get('password', [''])[0]

            if ssid:
                # Save Wi-Fi credentials
                write_wifi_credentials(ssid, password)

                # Respond to the client
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

                html_content = render_template('configuration_complete.html')
                self.wfile.write(html_content.encode('utf-8'))

                # Stop the server after responding
                threading.Thread(target=shutdown_server, args=(self.server,)).start()

                # Attempt to connect to the new Wi-Fi network
                threading.Thread(target=attempt_wifi_connection).start()
            else:
                # Missing SSID, redirect back to form
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

def scan_wifi_networks():
    """Scans for available Wi-Fi networks and returns a list of SSIDs."""
    logging.info("Scanning for Wi-Fi networks...")
    try:
        output = subprocess.check_output(['sudo', 'iwlist', HOTSPOT_INTERFACE, 'scan'], stderr=subprocess.STDOUT).decode('utf-8')
        ssids = set()
        for line in output.split('\n'):
            line = line.strip()
            if "ESSID:" in line:
                ssid = line.split(':', 1)[1].strip('"')
                if ssid:
                    ssids.add(ssid)
        logging.info(f"Found networks: {ssids}")
        return sorted(ssids)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error scanning Wi-Fi networks: {e}")
        return []

def write_wifi_credentials(ssid, password):
    """Writes Wi-Fi credentials to wpa_supplicant.conf."""
    logging.info(f"Writing Wi-Fi credentials for SSID: {ssid}")
    wpa_supplicant_conf = f"""
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    psk="{password}"
}}
"""
    try:
        with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as f:
            f.write(wpa_supplicant_conf)
        logging.info("Wi-Fi credentials written successfully.")
    except Exception as e:
        logging.error(f"Error writing Wi-Fi credentials: {e}")

def attempt_wifi_connection():
    """Attempts to connect to the Wi-Fi network and restarts the system services."""
    logging.info("Attempting to connect to the new Wi-Fi network...")
    time.sleep(5)  # Wait for the client to receive the response
    stop_hotspot()
    # Restart networking services
    subprocess.call(['sudo', 'systemctl', 'daemon-reload'])
    subprocess.call(['sudo', 'systemctl', 'restart', 'dhcpcd'])
    subprocess.call(['sudo', 'wpa_cli', '-i', HOTSPOT_INTERFACE, 'reconfigure'])
    # Wait and check connection status
    time.sleep(10)
    if check_internet_connection():
        logging.info("Connected to the Wi-Fi network successfully.")
        # Optionally, reboot the Pi
        # subprocess.call(['sudo', 'reboot'])
    else:
        logging.warning("Failed to connect to the Wi-Fi network. Restarting hotspot...")
        start_hotspot()

def check_internet_connection():
    """Checks if the Pi has an active internet connection."""
    try:
        subprocess.check_call(['ping', '-c', '3', '8.8.8.8'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def start_hotspot():
    """Configures and starts the Wi-Fi hotspot."""
    logging.info("Starting Wi-Fi hotspot...")
    # Configure dhcpcd.conf
    dhcpcd_conf = f"""
interface {HOTSPOT_INTERFACE}
static ip_address={HOTSPOT_IP}/24
nohook wpa_supplicant
"""
    with open('/etc/dhcpcd.conf', 'a') as f:
        f.write(dhcpcd_conf)

    # Configure dnsmasq.conf
    dnsmasq_conf = f"""
interface={HOTSPOT_INTERFACE}
dhcp-range={DHCP_RANGE}
"""
    with open('/etc/dnsmasq.conf', 'w') as f:
        f.write(dnsmasq_conf)

    # Configure hostapd.conf
    hostapd_conf = f"""
interface={HOTSPOT_INTERFACE}
driver=nl80211
ssid={HOTSPOT_SSID}
hw_mode=g
channel=7
wmm_enabled=0
auth_algs=1
ignore_broadcast_ssid=0
"""
    with open('/etc/hostapd/hostapd.conf', 'w') as f:
        f.write(hostapd_conf)

    # Update /etc/default/hostapd
    with open('/etc/default/hostapd', 'w') as f:
        f.write('DAEMON_CONF="/etc/hostapd/hostapd.conf"')

    # Enable IP forwarding
    subprocess.call(['sudo', 'sh', '-c', 'echo 1 > /proc/sys/net/ipv4/ip_forward'])

    # Configure iptables
    subprocess.call(['sudo', 'iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'eth0', '-j', 'MASQUERADE'])
    subprocess.call(['sudo', 'iptables', '-A', 'FORWARD', '-i', HOTSPOT_INTERFACE, '-o', 'eth0', '-j', 'ACCEPT'])
    subprocess.call(['sudo', 'iptables', '-t', 'nat', '-A', 'PREROUTING', '-p', 'tcp', '--dport', '80', '-j', 'DNAT', '--to-destination', HOTSPOT_IP])

    # Save iptables rules
    subprocess.call(['sudo', 'netfilter-persistent', 'save'])

    # Restart services
    subprocess.call(['sudo', 'systemctl', 'restart', 'dhcpcd'])
    subprocess.call(['sudo', 'systemctl', 'restart', 'hostapd'])
    subprocess.call(['sudo', 'systemctl', 'restart', 'dnsmasq'])

    # Start the captive portal server
    server_address = (HOTSPOT_IP, 80)
    httpd = HTTPServer(server_address, CaptivePortalHandler)
    logging.info(f"Captive portal started on {HOTSPOT_IP}:80")
    httpd.serve_forever()

def stop_hotspot():
    """Stops the Wi-Fi hotspot and restores network settings."""
    logging.info("Stopping Wi-Fi hotspot...")
    # Remove configurations from dhcpcd.conf
    with open('/etc/dhcpcd.conf', 'r') as f:
        lines = f.readlines()
    with open('/etc/dhcpcd.conf', 'w') as f:
        for line in lines:
            if line.strip() and not line.startswith(f'interface {HOTSPOT_INTERFACE}'):
                f.write(line)

    # Flush iptables rules
    subprocess.call(['sudo', 'iptables', '-F'])
    subprocess.call(['sudo', 'iptables', '-t', 'nat', '-F'])
    subprocess.call(['sudo', 'netfilter-persistent', 'save'])

    # Restart services
    subprocess.call(['sudo', 'systemctl', 'restart', 'dhcpcd'])
    subprocess.call(['sudo', 'systemctl', 'stop', 'hostapd'])
    subprocess.call(['sudo', 'systemctl', 'stop', 'dnsmasq'])

def shutdown_server(server):
    """Shuts down the HTTP server."""
    time.sleep(2)  # Wait to ensure response is sent
    logging.info("Shutting down the HTTP server...")
    server.shutdown()

def render_template(template_name, **kwargs):
    """Renders an HTML template with provided variables."""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', template_name)
    with open(template_path, 'r') as f:
        template = Template(f.read())
    return template.render(**kwargs)

def main():
    try:
        if not os.geteuid() == 0:
            sys.exit("Script must be run as root. Try 'sudo python3 script_name.py'")

        # Check if already connected to Wi-Fi
        if check_internet_connection():
            logging.info("Already connected to the internet.")
            sys.exit(0)

        # Start the hotspot and captive portal
        start_hotspot()
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
        stop_hotspot()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        stop_hotspot()

if __name__ == '__main__':
    main()
