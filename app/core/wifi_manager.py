

import subprocess
import json
import time
import platform
import logging
from config.config import ConfigSettings
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs

class WifiManager:
    def __init__(self, interface=None):
        self.interface = interface
        self.connected = False
        self.ssid = None
        self.password = None
        self.config = ConfigSettings()
        
        if platform.system() == "Linux":
            if "armv" in platform.machine():
                # Raspberry Pi (assuming 'wlan0' interface) requires network-manager to be installed.
                self.is_rpi = True
                if not self.interface:
                    raise ValueError("Interface must be provided for Raspberry Pi.")
            else:
                # Linux PC
                self.is_rpi = False
                self.interface = "wlp2s0" if not self.interface else self.interface
        else:
            raise ValueError("Unsupported operating system.")
    

    def scan_wifi_networks(self):        
        try:
            if not self.is_rpi:
                output = subprocess.check_output(["nmcli", "-t", "-f", "BSSID,SIGNAL", "dev", "wifi"]).decode("utf-8")
                networks = []
                for line in output.splitlines():
                    line = line.replace("\\", "")
                    bssid, signal = line.rsplit(":", 1)
                    networks.append({"macAddress": bssid, "signalStrength": (-1)*int(signal)})
            else:
                output = subprocess.check_output(["iwlist", self.interface, "scan"]).decode("utf-8")
                networks = []
                for line in output.split("\n"):
                    if "Address" in line:
                        mac_address = line.split(":")[-1].strip()
                    elif "Signal level" in line:
                        signal_strength = int(line.split("=")[-1].split(" ")[0])
                        networks.append({"macAddress": mac_address, "signalStrength": signal_strength})
            
            json_output = {"wifiAccessPoints": networks}
            return json_output
    
        except subprocess.CalledProcessError:
            logging.error("Error scanning Wi-Fi networks on interface: {0}", self.interface)
            return None
    

    def connect(self, ssid, password, max_attempts=5):
        if not self.is_rpi:
            logging.info("Assuming Wi-Fi network connectivity on PC.")
            return
        
        attempt = 1
        while attempt <= max_attempts:
            try:
                # Disconnect from any previous connection
                self.disconnect()
                
                # Connect to the specified Wi-Fi network
                subprocess.check_call(["nmcli", "device", "wifi", "connect", ssid, "password", password])
                
                self.connected = True
                self.ssid = ssid
                self.password = password
                logging.info("Connected to Wi-Fi network: {0}", ssid)
                return
            
            except subprocess.CalledProcessError:
                logging.erro( "Error connecting to Wi-Fi network: {0}. Attempt {1}/{2}", ssid, attempt, max_attempts)
                attempt += 1
                time.sleep(5)  # Wait for 5 seconds before the next attempt
        
        logging.warning("Failed to connect to Wi-Fi network after {0} attempts. Starting Wi-Fi hotspot...", max_attempts)
        self.start_hotspot()
    

    def disconnect(self):
        if not self.is_rpi:
            # Assume network connectivity on PC
            logging.info("Disconnecting from Wi-Fi networks is not supported on PC.")
            return
        
        if self.connected:
            try:
                # Disconnect from the current Wi-Fi network
                subprocess.check_call(["nmcli", "device", "disconnect", self.interface])
                
                self.connected = False
                self.ssid = None
                self.password = None
                logging.info("Disconnected from Wi-Fi network.")
            
            except subprocess.CalledProcessError:
                logging.erro( "Error disconnecting from Wi-Fi network.")


    class CaptivePortalHandler(SimpleHTTPRequestHandler):
        def __init__(self, wifi_manager, *args, **kwargs):
            self.wifi_manager = wifi_manager
            super().__init__(*args, **kwargs)
            self.html_configure_head = "<!DOCTYPE html><html lang='en'><head><meta name='viewport' content='width=device-width, initial-scale=1'><style>body, html {height: 100%;margin: 0;}.geometric-bg {background-color: #1a202c; /* Dark background color */height: 100%;display: flex;justify-content: center;align-items: center;overflow: hidden;position: relative;}.shape {position: absolute;background-color: rgba(255, 255, 255, 0.1); /* Subtle shape color */border-radius: 15%;}.shape.large {width: 300px;height: 300px;top: 20%;left: 10%;}.shape.medium {width: 200px;height: 200px;bottom: 30%;right: 15%;}.shape.small {width: 100px;height: 100px;bottom: 20%;left: 40%;}.form-container {position: relative;display: flex;justify-content: center;align-items: center;flex-direction: column;z-index: 1; /* Ensures form appears above background */max-width: 300px;padding: 20px;background-color: rgba(255, 255, 255, 0.8); /* Semi-transparent white */border-radius: 10px;box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);}form {display: flex;flex-direction: column;align-items: center;padding: 10px;}input[type='text'], input[type='password'] {width: 90%; /* Full width of the container */margin-bottom: 15px;padding: 10px;border: 1px solid #ddd; /* Light grey border */border-radius: 5px;}input[type='submit'] {padding: 10px 20px;color: white;background-color: #fd9001; /* Bootstrap primary color */border: none;border-radius: 5px;cursor: pointer;width: 100%;}input[type='submit']:hover {background-color: #b86800; /* Darker on hover */}</style></head><body><div class='geometric-bg'><div class='shape large'></div><div class='shape medium'></div><div class='shape small'></div><div class='form-container'><div class='logo'><svg width='127' height='34' fill='black' ><g clip-path='url(#clip0)' fill='#000'><path d='M30.012 17.64c0 8.983-5.71 16.396-15.006 16.396C5.6 34.036 0 26.586 0 17.64S5.636 1.242 14.97 1.242c9.332 0 15.042 7.486 15.042 16.397zM14.969 29.544c6.771 0 9.516-5.953 9.516-11.906S21.703 5.734 14.933 5.734c-6.771 0-9.48 5.989-9.48 11.905 0 5.916 2.818 11.906 9.516 11.906zM40.588 1.972l14.31 23.044h.074V1.972h5.234V33.27h-5.783L40.149 10.262h-.146V33.27h-5.197V1.972h5.782zm30.561 0V6.72h-5.014V1.972h5.014zm0 8.655V33.27h-5.014V10.627h5.014zm34.55 7.013c0 8.983-5.71 16.396-15.006 16.396-9.406 0-15.005-7.45-15.005-16.397S81.36 1.242 90.692 1.242c9.333 0 15.006 7.486 15.006 16.397zM90.657 29.544c6.77 0 9.516-5.953 9.516-11.906s-2.819-11.905-9.59-11.905c-6.77 0-9.479 5.989-9.479 11.905 0 5.916 2.855 11.906 9.553 11.906zM127 9.568c0 5.332-3.953 9.568-9.37 9.568-5.49 0-9.442-4.126-9.442-9.568C108.188 4.2 112.177 0 117.63 0S127 4.236 127 9.568zm-9.37 7.888c4.465 0 7.32-3.615 7.32-7.888s-2.855-7.888-7.356-7.888c-4.502 0-7.357 3.615-7.357 7.888 0 4.346 2.818 7.888 7.393 7.888zm.476-13c2.525 0 3.77.949 3.77 3.03 0 1.754-.989 2.703-2.782 2.886l2.965 4.638h-1.977l-2.745-4.529h-1.647v4.529h-1.756V4.419l4.172.036zm-.329 4.564c1.866 0 2.342-.547 2.342-1.643 0-.986-.732-1.424-2.196-1.424h-2.233v3.104l2.087-.037z'/></g><defs><clipPath id='clip0'><path fill='#fff' d='M0 0h127v34H0z'/></clipPath></defs></svg></div>"
            self.html_configure_foot = "</div></body></html>"
            self.html_configure_form = "<form method='POST' action='/configure_complete'><input type='text' id='ssid' name='ssid' placeholder='Wifi SSID'><input type='password' id='wpa' name='wpa' placeholder='Wifi Password'><input type='submit' value='Connect'></form>"
            self.html_configure_complete = f"<h1>Configuration Complete</h1><p>Configuration complete. The hub will now reboot.</p><p>RID: {self.config.get('settings', 'hub_serial_hash')}</p>"
        
        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(bytes(self.html_configure_head + self.html_configure_form + self.html_configure_foot, "utf-8"))
            else:
                super().do_GET()
        
        def do_POST(self):
            if self.path == "/configure_complete":
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length).decode("utf-8")
                fields = parse_qs(post_data)
                ssid = fields['ssid'][0]
                password = fields['wpa'][0]
                
                self.wifi_manager.connect(ssid, password)
                
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(bytes(self.html_configure_head + self.html_configure_complete + self.html_configure_foot, "utf-8"))
            else:
                self.send_error(404)


    def start_hotspot(self):
        if not self.is_rpi:
            logging.info("Starting Wi-Fi hotspot is not supported on PC.")
            return     
        try:
            # Stop any existing hotspot
            subprocess.call(["systemctl", "stop", "hostapd"])
            subprocess.call(["systemctl", "stop", "dnsmasq"])
            
            # Configure hotspot settings
            with open("/etc/hostapd/hostapd.conf", "w") as f:
                f.write("interface={0}\n".format(self.interface))
                f.write("ssid=ONiO Smart Hub\n")
                f.write("hw_mode=g\n")
                f.write("channel=7\n")
                f.write("auth_algs=1\n")
                f.write("wpa=0\n")  # Disable password protection
            
            # Configure DHCP settings
            with open("/etc/dnsmasq.conf", "w") as f:
                f.write("interface={0}\n".format(self.interface))
                f.write("dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h\n")
                f.write("address=/#/192.168.4.1\n")  # Redirect all requests to the captive portal
            
            # Start hotspot
            subprocess.check_call(["systemctl", "start", "hostapd"])
            subprocess.check_call(["systemctl", "start", "dnsmasq"])
            
            logging.info("Wi-Fi hotspot 'ONiO Smart Hub' started. Connect to it using your phone.")
            
            # Start the HTTP server to handle the captive portal
            httpd = HTTPServer(("", 80), lambda *args, **kwargs: self.CaptivePortalHandler(self, *args, **kwargs))
            httpd.serve_forever()
        
        except subprocess.CalledProcessError:
            logging.error("Error starting Wi-Fi hotspot.")

        

