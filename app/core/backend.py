import json
import requests
import logging
import socket
from config.config import ConfigSettings


class ApiBackend():
    def __init__(self):
        self.config = ConfigSettings()
        self.api_token = ""
        self.refresh_token = ""
        self.location = {}
        pass
    

    def get_headers(self, include_auth_token=False) -> dict:
        headers = {
            'xid': self.config.get('headers', 'x_app_id'),
            'xsecret': self.config.get('headers', 'x_app_secret')
        }
        if include_auth_token and self.api_token:
            headers['Auth'] = "Bearer " + self.api_token
        return headers


    def make_api_request(self, endpoint, json_data, headers, timeout) -> json:
        url = self.config.get('server', 'server_url') + endpoint
        logging.debug(f"Making request to: {url}")
        try:
            if json_data == None:
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, json=json_data, headers=headers, timeout=timeout)
            try: return json.loads(response.text)
            except: return {'statusCode': response.status_code, 'data': response.text}
        except requests.RequestException as e:
            logging.error(f"Failed to make request to {url} due to {e}")
            return None


    def get_token(self, serial_hash: str) -> bool:
        json_data = {'serial_number': serial_hash}
        logging.info(f"Getting token for hub with serial hash: {serial_hash}")
        headers = self.get_headers()
        timeout = int(self.config.get('settings', 'http_timeout'))
        endpoint = self.config.get('endpoints', 'auth_fetch_token_ep')


        try:
            response_data = self.make_api_request(endpoint, json_data, headers, timeout)
        except requests.RequestException as e:
            logging.error(f"Failed to get token from server due to {e}")
            logging.debug(json_data)
            return False

        if response_data is None:
            logging.error("No response from server")
            logging.debug(json_data)
            return False

        if not isinstance(response_data, dict) or 'statusCode' not in response_data:
            logging.error("Invalid response format")
            logging.debug(response_data)
            return False

        if response_data.get('statusCode') != 200:
            logging.error(f"Failed to get token from server. Status code: {response_data.get('statusCode')}")
            logging.debug(json_data)
            logging.debug(response_data)
            return False

        data = response_data.get('data', {})
        if not isinstance(data, dict) or 'refreshToken' not in data or 'accessToken' not in data:
            logging.error("Invalid data format")
            logging.debug(response_data)
            return False

        self.refresh_token = data['refreshToken']
        self.api_token = data['accessToken']
        logging.info("Auth Token: " + self.api_token)
        return True


    def refresh_token(self, refresh_token: str) -> bool:
        json_data = {'refresh_token': refresh_token}
        headers = self.get_headers()
        response_data = self.make_api_request(self.config.get('endpoints', 'auth_refresh_token_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))

        if response_data is None:
            logging.error("Failed to refresh token from server")
            return False

        if response_data.get('statusCode') == 200:
            self.refresh_token = response_data['data']['refreshToken']
            self.api_token = response_data['data']['accessToken']
            return True
        else:
            logging.error(f"Failed to refresh token from server: {response_data.get('statusCode')}")
            logging.debug(json_data)
            logging.debug(response_data)
            return False


    def ping_server(self, serial_hash, logs) -> str:
        if self.api_token == "":
            logging.error("No API token found. Cannot ping server")
            self.get_token(serial_hash)
            return ""
        
        headers = self.get_headers(include_auth_token=True)
        json_data = logs

        response_data = self.make_api_request(self.config.get('endpoints', 'ping_ep'), json_data, headers, int(self.config.get('settings', 'http_timeout')))

        if response_data is None:
            logging.error("Failed to ping server")
            return ""

        if response_data.get('statusCode') == 200:
            self.command = response_data['data']['command']
            if self.command != "":
                logging.info(f"Received command: {self.command}")
            return self.command
        else:
            logging.error(f"Failed to ping server: {response_data.get('statusCode')}")
            if response_data.get('statusCode') == 401:
                self.get_token(serial_hash)
            logging.error(json_data)
            logging.error(response_data)
            return ""


    def gapi_geolocation(self, local_ap_list: json) -> bool:
        gapi_url = self.config.get('server', 'gapi_url') + self.config.get('server', 'gapi_key')
        response = requests.post(gapi_url, json=local_ap_list, timeout=int(self.config.get('settings', 'http_timeout')))
        response_data = json.loads(response.text)
        if response.status_code == 200:
            self.location = response_data
            return True
        else:
            logging.error(f"Failed to get location from Google API: {response_data.status_code}")
            logging.debug(response_data)
            return False


    def set_location(self) -> bool:
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
        
        if response_data is None:
            logging.error("Failed to set location with server")
            return False

        if response_data.get('statusCode') == 200:
            return True
        else:
            logging.error(f"Failed to set location with server: {response_data.get('statusCode')}")
            logging.debug(json_data)
            logging.debug(response_data)
            return False
        
    
    def post_scan_results(self, plugins: list) -> bool:
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
        
        if response_data is None:
            logging.error("Failed to post scan results to server")
            return False

        if response_data.get('statusCode') == 200:
            return True
        else:
            logging.error(f"Failed to post scan results to server: {response_data.get('statusCode')}")
            logging.debug(json_data)
            logging.debug(response_data)
            return False
        
    
    def send_collected_data(self, data: json) -> bool:
        if self.api_token == "":
            logging.error("No API token found. Cannot send collected data")
            return False
        
        logging.info(f"Sending data to API: {data}")
        headers = self.get_headers(include_auth_token=True)
        response_data = self.make_api_request(self.config.get('endpoints', 'send_data_ep'), data, headers, int(self.config.get('settings', 'http_timeout')))
        
        if response_data is None:
            logging.error("Failed to send collected data to server")
            return False

        if response_data.get('statusCode') == 200:
            return True
        else:
            logging.error("Failed to send collected data to server. status code: " + str(response_data.get('statusCode')))
            logging.debug(data)
            logging.error(response_data)
            return False
        

    def get_flow(self) -> json:
        if self.api_token == "":
            logging.error("No API token found. Cannot get flow")
            return False
        
        headers = self.get_headers(include_auth_token=True)

        response_data = self.make_api_request(self.config.get('endpoints', 'get_flow_ep') + "?flow-type=json", None, headers, int(self.config.get('settings', 'http_timeout')))

        if response_data is None:
            logging.error("Failed to get flow from server")
            return False

        if response_data['statusCode'] == 200:
            return response_data['data']
        else:
            logging.debug(response_data)
            logging.error(f"Failed to get flow from server: {response_data.get('statusCode')}")
            return False