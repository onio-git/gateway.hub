import logging
from core.plugin_interface import PluginInterface
from config.config import ConfigSettings as config
from datetime import datetime
from core.backend import ApiBackend
from core.flow import Flow
import socket
import requests
import xml.etree.ElementTree as ET
import asyncio
import threading
from urllib.parse import urlparse

class sonos(PluginInterface):
    def __init__(self, api: ApiBackend, flow: Flow):
        self.protocol = "WiFi"
        self.devices = {}
        self.config = config()
        self.api = api
        self.flow = flow
        self.active = False

        # SSDP Discovery constants
        self.MSEARCH_HOST = "239.255.255.250"
        self.MSEARCH_PORT = 1900
        self.MSEARCH_MSG = \
            'M-SEARCH * HTTP/1.1\r\n' + \
            'HOST: 239.255.255.250:1900\r\n' + \
            'MAN: "ssdp:discover"\r\n' + \
            'MX: 5\r\n' + \
            'ST: urn:schemas-upnp-org:device:ZonePlayer:1\r\n' + \
            '\r\n'
        self.DISCOVERY_TIMEOUT = 3  # seconds

        self.soap_templates = {
            'transport_info': {
                'endpoint': '/MediaRenderer/AVTransport/Control',
                'action': 'GetTransportInfo',
                'body': '''<?xml version="1.0" encoding="utf-8"?>
                    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                        <s:Body>
                            <u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                                <InstanceID>0</InstanceID>
                            </u:GetTransportInfo>
                        </s:Body>
                    </s:Envelope>''',
                'header': 'urn:schemas-upnp-org:service:AVTransport:1#GetTransportInfo'
            },
            'volume': {
                'endpoint': '/MediaRenderer/RenderingControl/Control',
                'action': 'GetVolume',
                'body': '''<?xml version="1.0" encoding="utf-8"?>
                    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                        <s:Body>
                            <u:GetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
                                <InstanceID>0</InstanceID>
                                <Channel>Master</Channel>
                            </u:GetVolume>
                        </s:Body>
                    </s:Envelope>''',
                'header': 'urn:schemas-upnp-org:service:RenderingControl:1#GetVolume'
            },
            'track_info': {
                'endpoint': '/MediaRenderer/AVTransport/Control',
                'action': 'GetPositionInfo',
                'body': '''<?xml version="1.0" encoding="utf-8"?>
                    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                        <s:Body>
                            <u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                                <InstanceID>0</InstanceID>
                            </u:GetPositionInfo>
                        </s:Body>
                    </s:Envelope>''',
                'header': 'urn:schemas-upnp-org:service:AVTransport:1#GetPositionInfo'
            }
        }


    def execute(self) -> None:
        """Start device discovery"""
        pass


    def discover(self):
        """Discover Sonos speakers using SSDP"""
        logging.info("Starting Sonos speaker discovery...")
        
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(2)
        
        try:
            # Allow reuse of address
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to any available port
            sock.bind(('', 0))
            
            # Send discovery message
            sock.sendto(self.MSEARCH_MSG.encode(), (self.MSEARCH_HOST, self.MSEARCH_PORT))
            
            # Set discovery end time
            end_time = datetime.now().timestamp() + self.DISCOVERY_TIMEOUT
            
            # Collect responses until timeout
            while datetime.now().timestamp() < end_time:
                try:
                    data, addr = sock.recvfrom(1024)
                    self.process_ssdp_response(data.decode())
                except socket.timeout:
                    continue
                
        except Exception as e:
            logging.error(f"Error during Sonos discovery: {e}")
        finally:
            sock.close()
            
        logging.info(f"Discovery complete. Found {len(self.devices)} Sonos devices")
        self.get_device_details()


    def process_ssdp_response(self, response):
        """Process SSDP response and extract device URL"""
        try:
            # Look for the LOCATION header in the response
            for line in response.split('\r\n'):
                if line.lower().startswith('location:'):
                    device_url = line.split(': ')[1].strip()
                    self.add_device_from_url(device_url)
                    break
        except Exception as e:
            logging.error(f"Error processing SSDP response: {e}")


    def add_device_from_url(self, url):
        """Add new device from discovered URL"""
        try:
            parsed_url = urlparse(url)
            ip = parsed_url.hostname
            port = parsed_url.port or 1400  # Default Sonos port

            # Create initial speaker info
            speaker_info = {
                'ip': ip,
                'name': '',
                'room_name': '',
                'model_no': '',
                'model_name': '',
                'serial_no': '',
                'udn': '',
                'master_udn': '',
                'playing': False,
                'volume': 0,
                'track': ''
            }

            # Create new device if not already exists
            if ip not in self.devices:
                self.devices[ip] = self.Device(speaker_info)

        except Exception as e:
            logging.error(f"Error adding device from URL {url}: {e}")


    def get_device_details(self):
        """Get detailed information for all discovered devices"""
        for ip, device in self.devices.items():
            try:
                # Get device description XML
                response = requests.get(device.url, timeout=5)
                if response.status_code == 200:
                    self.parse_device_description(device, response.text)
                    self.get_device_status(device)
            except Exception as e:
                logging.error(f"Error getting details for device at {ip}: {e}")

        self.display_devices()


    def parse_device_description(self, device, xml_data):
        """Parse device description XML and update device info"""
        try:
            # Use ElementTree with namespace handling
            ns = {'ns': 'urn:schemas-upnp-org:device-1-0'}
            root = ET.fromstring(xml_data)
            
            # Get the main device element
            device_elem = root.find('.//ns:device', ns)
            if device_elem is not None:
                # Extract basic device information
                device.room_name = device_elem.findtext('.//ns:roomName', '', ns)
                device.device_name = device_elem.findtext('.//ns:friendlyName', '', ns).split('-')[1] + f"({device.room_name})"
                device.model_no = device_elem.findtext('.//ns:modelNumber', '', ns)
                device.model_name = device_elem.findtext('.//ns:modelName', '', ns)
                device.serial_no = device_elem.findtext('.//ns:serialNum', '', ns)
                device.mac_address = device_elem.findtext('.//ns:MACAddress', '', ns)
                device.udn = device_elem.findtext('.//ns:UDN', '', ns).replace('uuid:', '')
                
                self.get_group_topology(device)
                
                # Additional useful information
                device.manufacturer = device_elem.findtext('.//ns:manufacturer', '', ns)
                device.software_version = device_elem.findtext('.//ns:softwareVersion', '', ns)
                device.hardware_version = device_elem.findtext('.//ns:hardwareVersion', '', ns)
                device.zone_type = device_elem.findtext('.//ns:zoneType', '', ns)
                
                # Store service endpoints for later use
                device.services = {}
                
                # Find MediaRenderer device which contains the playback services
                media_renderer = root.find('.//ns:device[ns:deviceType="urn:schemas-upnp-org:device:MediaRenderer:1"]', ns)
                if media_renderer is not None:
                    for service in media_renderer.findall('.//ns:service', ns):
                        service_type = service.findtext('ns:serviceType', '', ns)
                        control_url = service.findtext('ns:controlURL', '', ns)
                        if service_type and control_url:
                            service_name = service_type.split(':')[-2]
                            device.services[service_name] = {
                                'type': service_type,
                                'control_url': control_url,
                                'event_url': service.findtext('ns:eventSubURL', '', ns),
                                'scpd_url': service.findtext('ns:SCPDURL', '', ns)
                            }

                logging.info(f"Info: {device.device_name}")
                
                return True
                
        except ET.ParseError as e:
            logging.error(f"XML parsing error: {e}")
        except Exception as e:
            logging.error(f"Error parsing device description: {e}")
        
        return False


    def get_device_status(self, device):
        """Get current playback status, volume, and track info from the Sonos device"""
        try:
            # Get transport state (playing/paused)
            response = self.send_soap_request(device, self.soap_templates['transport_info'])
            if response:
                state = self.extract_value(response.text, 'CurrentTransportState')
                device.playing = (state == 'PLAYING')
                logging.debug(f"Transport state: {state}")

            # Get volume
            response = self.send_soap_request(device, self.soap_templates['volume'])
            if response:
                volume = self.extract_value(response.text, 'CurrentVolume')
                device.volume = int(volume) if volume else 0
                logging.debug(f"Volume: {device.volume}")

            # Get track info
            response = self.send_soap_request(device, self.soap_templates['track_info'])
            if response:
                logging.debug(f"Raw track info response: {response.text}")
                track_metadata = self.extract_value(response.text, 'TrackMetaData')
                logging.debug(f"Extracted track metadata: {track_metadata}")
                
                if track_metadata and track_metadata != 'NOT_IMPLEMENTED':
                    # Look for double-encoded XML tags
                    title = self.extract_between(track_metadata, '&lt;dc:title&gt;', '&lt;/dc:title&gt;')
                    creator = self.extract_between(track_metadata, '&lt;dc:creator&gt;', '&lt;/dc:creator&gt;')
                    
                    logging.debug(f"Extracted title: {title}, creator: {creator}")
                    
                    if title or creator:
                        device.track = f"{title} - {creator}".strip(" -")
                    else:
                        device.track = "No track info"
                else:
                    device.track = "No track info available"
                logging.debug(f"Final track info: {device.track}")

            return True

        except Exception as e:
            logging.error(f"Error getting device status: {e}")
            return False
        

    def get_group_topology(self, device):
        """Get speaker grouping information"""
        try:
            soap_body = '''<?xml version="1.0" encoding="utf-8"?>
                <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
                    <s:Body>
                        <u:GetZoneGroupState xmlns:u="urn:schemas-upnp-org:service:ZoneGroupTopology:1">
                        </u:GetZoneGroupState>
                    </s:Body>
                </s:Envelope>'''

            url = f"http://{device.ip}:1400/ZoneGroupTopology/Control"
            headers = {
                'Content-Type': 'text/xml; charset="utf-8"',
                'SOAPACTION': '"urn:schemas-upnp-org:service:GroupTopology:1#GetZoneGroupState"'
            }

            response = requests.post(url, data=soap_body, headers=headers, timeout=5)
            if response.status_code == 200:
                # Look for the coordinator info in the response
                coordinator_tag = f'Coordinator="uuid:{device.udn}"'
                if coordinator_tag in response.text:
                    device.master = True
                    device.master_udn = device.udn
                else:
                    # Extract the coordinator UDN for this device
                    search_str = f'uuid:{device.udn}'
                    start_idx = response.text.find(search_str)
                    if start_idx != -1:
                        # Look for the Coordinator attribute before this device's entry
                        coord_start = response.text.rfind('Coordinator="', 0, start_idx)
                        if coord_start != -1:
                            coord_start += len('Coordinator="')
                            coord_end = response.text.find('"', coord_start)
                            if coord_end != -1:
                                device.master_udn = response.text[coord_start:coord_end].replace('uuid:', '')
                                device.master = False

                logging.info(f"Group topology for {device.device_name}: master={device.master}, master_udn={device.master_udn}")
                return True

        except Exception as e:
            logging.error(f"Error getting group topology: {e}")
        
        # Default to device being its own master if we can't determine topology
        device.master_udn = device.udn
        device.master = True
        return False


    def send_soap_request(self, device, template):
        """Send SOAP request to Sonos device"""
        try:
            url = f"http://{device.ip}:1400{template['endpoint']}"
            headers = {
                'Content-Type': 'text/xml; charset="utf-8"',
                'SOAPACTION': f'"{template["header"]}"'
            }
            
            response = requests.post(
                url,
                data=template['body'],
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                return response
            else:
                logging.error(f"SOAP request failed with status {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            return None


    def extract_value(self, xml_text, tag):
        """Extract value from XML response"""
        try:
            # First try exact tag match
            start_tag = f"<{tag}>"
            end_tag = f"</{tag}>"
            start = xml_text.find(start_tag)
            if start != -1:
                start += len(start_tag)
                end = xml_text.find(end_tag, start)
                if end != -1:
                    return xml_text[start:end]

            # If not found, try with XML namespace
            start = xml_text.find(f"<{tag}>")
            if start != -1:
                start += len(f"<{tag}>")
                end = xml_text.find(f"</{tag}>", start)
                if end != -1:
                    return self.decode_html_entities(xml_text[start:end])

            return None

        except Exception as e:
            logging.error(f"Error extracting value for {tag}: {e}")
            return None


    def extract_between(self, text, start, end):
        """Extract text between two markers"""
        try:
            if not text:
                return ''
            s = text.find(start)
            if s == -1:
                return ''
            s += len(start)
            e = text.find(end, s)
            if e == -1:
                return ''
            return self.decode_html_entities(text[s:e])
        except Exception:
            return ''


    def decode_html_entities(self, text):
        """Decode HTML entities in text - do it twice for double-encoded entities"""
        if not text:
            return text
            
        # Do it twice to catch double-encoded entities
        for _ in range(2):
            replacements = {
                '&amp;': '&',
                '&lt;': '<',
                '&gt;': '>',
                '&quot;': '"',
                '&apos;': "'",
                '&nbsp;': ' '
            }
            
            for entity, char in replacements.items():
                text = text.replace(entity, char)
        
        return text


    def display_devices(self) -> None:
        """Display comprehensive information about discovered Sonos devices"""
        if not self.devices:
            logging.info("No Sonos devices found")
            return

        for ip, device in self.devices.items():
            logging.info("=" * 50)
            logging.info(f"Sonos Device:")
            logging.info(f"  Network:")
            logging.info(f"    IP Address: {ip}")
            logging.info(f"    MAC Address: {device.mac_address}")
            
            logging.info(f"  Device Info:")
            logging.info(f"    Name: {device.device_name}")
            logging.info(f"    Room: {device.room_name}")
            logging.info(f"    Model: {device.model_name} ({device.model_no})")
            logging.info(f"    Serial: {device.serial_no}")
            logging.info(f"    UDN: {device.udn}")
            
            logging.info(f"  System Info:")
            logging.info(f"    Software Version: {device.software_version}")
            logging.info(f"    Hardware Version: {device.hardware_version}")
            logging.info(f"    Zone Type: {device.zone_type}")
            
            logging.info(f"  Playback Status:")
            logging.info(f"    Master Device: {'Yes' if device.master else 'No'}")
            if device.master:
                logging.info(f"    Playing: {'Yes' if device.playing else 'No'}")
                logging.info(f"    Volume: {device.volume}%")
                logging.info(f"    Current Track: {device.track}")
            else:
                logging.info(f"    Master UDN: {device.master_udn}")
            
            logging.info(f"  Available Services:")
            for service_name, service_info in device.services.items():
                logging.info(f"    - {service_name}")
            
            logging.info("=" * 50)


    class SearchableDevice(PluginInterface.SearchableDeviceInterface):
        def __init__(self):
            self.protocol = "WIFI"
            self.scan_filter_method = "request"
            self.scan_filter = "sonos"


    class Device(PluginInterface.DeviceInterface):
        def __init__(self, speaker_info):
            self.config = config()
            self.manufacturer = "Sonos"
            self.com_protocol = "WiFi"
            self.ip = speaker_info['ip']
            self.url = f"http://{self.ip}:1400/xml/device_description.xml"
            self.device_name = speaker_info['name']
            self.room_name = speaker_info['room_name']
            self.model_no = speaker_info['model_no']
            self.model_name = speaker_info['model_name']
            self.serial_no = speaker_info['serial_no']
            self.udn = speaker_info['udn']
            self.master_udn = speaker_info['master_udn']
            self.master = True if self.udn == self.master_udn else False
            self.playing = speaker_info['playing']
            self.volume = speaker_info['volume']
            self.track = speaker_info['track']
            
            # Additional fields for expanded device info
            self.mac_address = ""
            self.software_version = ""
            self.firmware = ""
            self.zone_type = ""
            self.device_description = ""
            
            # Dictionary to store service endpoints
            self.services = {}