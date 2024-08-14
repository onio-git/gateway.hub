import json
import requests
import time
import subprocess
import logging
from config.config import ConfigSettings



class ApiBackend():
    def __init__(self):
        self.config = ConfigSettings()
        self.api_token = ""
        self.refresh_token = ""
        self.location = {}
        pass
        

    
    
    
    def get_headers(self, include_auth_token=False):
        headers = {
            'x-app-id': self.config.get('headers', 'x_app_id'),
            'x-app-secret': self.config.get('headers', 'x_app_secret')
        }
        if include_auth_token:
            headers['Authorization'] = "Bearer " + self.api_token
        return headers


    def make_api_request(self, endpoint, json_data, headers, timeout):
        url = self.config.get('server', 'server_url') + endpoint
        response = requests.post(url, json=json_data, headers=headers, timeout=timeout)
        return json.loads(response.text)


    def get_token(self, serial_hash: str):
        json_data = {'serial_number': serial_hash}
        headers = self.get_headers()
        response_data = self.make_api_request(self.config.get('endpoints', 'auth_fetch_token_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))

        if response_data['statusCode'] == 200:
            self.refresh_token = response_data['data']['refreshToken']
            self.api_token = response_data['data']['accessToken']
            return True
        else:
            logging.error("Failed to get token from server")
            logging.debug(json_data)
            logging.debug(response_data)
            return False


    def refresh_token(self, refresh_token: str):
        json_data = {'refresh_token': refresh_token}
        headers = self.get_headers()
        response_data = self.make_api_request(self.config.get('endpoints', 'auth_refresh_token_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))

        if response_data['statusCode'] == 200:
            self.refresh_token = response_data['data']['refreshToken']
            self.api_token = response_data['data']['accessToken']
            return True
        else:
            logging.error("Failed to refresh token from server")
            logging.debug(json_data)
            logging.debug(response_data)
            return False


    def ping_server(self):
        if self.api_token == "":
            logging.error("No API token found. Cannot ping server")
            return False
        
        headers = self.get_headers(include_auth_token=True)
        json_data = {}

        response_data = self.make_api_request(self.config.get('endpoints', 'ping_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))

        if response_data['statusCode'] == 200:
            self.command = response_data['data']['command']
            if self.command != "":
                logging.info(f"Received command: {self.command}")
            return self.command
        else:
            logging.error("Failed to ping server")
            logging.debug(json_data)
            logging.debug(response_data)
            return False


    def gapi_geolocation(self, local_ap_list: json):
        gapi_url = self.config.get('server', 'gapi_url') + self.config.get('server', 'gapi_key')
        response = requests.post(gapi_url, json=local_ap_list, timeout=int(self.config.get('settings', 'http_timeout')))
        response_data = json.loads(response.text)
        if response.status_code == 200:
            self.location = response_data
            return True
        else:
            logging.error("Failed to get location from Google API")
            logging.debug(response_data)
            return False


    def set_location(self):
        if self.api_token == "":
            logging.error("No API token found. Cannot set location")
            return False

        if not self.location:
            return False

        json_data = {
            'lat': self.location['location']['lat'],
            'long': self.location['location']['lng'],
            'range_of_accuracy': self.location['accuracy']
        }
        
        headers = self.get_headers(include_auth_token=True)
        response_data = self.make_api_request(self.config.get('endpoints', 'set_location_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))
        

        if response_data['statusCode'] == 200:
            return True
        else:
            logging.error("Failed to set location with server")
            logging.debug(json_data)
            logging.debug(response_data)
            return False
        
    
    def post_scan_results(self, plugins: list):
        if self.api_token == "":
            logging.error("No API token found. Cannot post scan results")
            return False

        json_data = {
            "devices": []
        }
        for plugin in plugins:
            for device in plugin.devices.values():
                json_data['devices'].append({
                    "ip": device.ip,
                    "mac_address": device.mac_address,
                    "device_name": device.device_name,
                    "device_description": device.device_description,
                    "com_protocol": device.com_protocol,
                    "model_no": device.model_no,
                    "serial_no": device.serial_no,
                    "manufacturer": device.manufacturer,
                    "firmware": device.firmware
                })

        headers = self.get_headers(include_auth_token=True)
        response_data = self.make_api_request(self.config.get('endpoints', 'scan_data_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))
        

        if response_data['statusCode'] == 200:
            return True
        else:
            logging.error("Failed to post scan results to server")
            logging.debug(json_data)
            logging.debug(response_data)
            return False
        
    
    def send_collected_data(self, data: json):
        if self.api_token == "":
            logging.error("No API token found. Cannot send collected data")
            return False

        json_data = data
        headers = self.get_headers(include_auth_token=True)
        response_data = self.make_api_request(self.config.get('endpoints', 'send_data_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))
        

        if response_data['statusCode'] == 200:
            return True
        else:
            logging.error("Failed to send collected data to server")
            logging.debug(json_data)
            logging.debug(response_data)
            return False