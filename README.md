Hi! here is an install procedure for the Raspberry Pi 5 hub.

For the setup you need:
- Raspberry Pi 5
- Micro SD card
- Micro SD card reader
- USB-C power cable
- Ethernet cable
Optional extra:
- Keyboard with usb for the RPi
- External monitor + micro-HDMI cable for the RPi

1. On your PC, download the Raspberry Pi Imager Program.
2. Insert your micro-SD card into your PC.
3. In the Imager, choose OS "Ubuntu Bookworm 64 bit lite"
4. Choose storage - Pick your SD-card from the list
5. Enable advanced settings - enable ssh, choose a host name, username and password.
6. No need to configure Wifi.
7. Save the settings and write the image to the SD-card

8. Insert the SD-card into your Pi.
9. Plug in power and ethernet to your Pi.
10. After a few seconds you can try to locate your Pi on ssh
  $ ssh <username>@<hostname>.local

If this does not work, you must try to get the Pi ip-address by some other means. 
One way is to connect a monitor and keyboard to the Pi and see the assigned ip-address 
with: $ ifconfig 
then using the ssh command:
  $ ssh <username>@<local-ip-address>
  
The console may ask you to verify a cryptographic key. Press yes.

Once successfully ssh into the Pi, continue:

11. Get the install script from remote repository:
  $ wget https://raw.githubusercontent.com/onio-git/gateway.hub/refs/heads/master/app/install.sh
12. Set permissions:
  $ sudo chmod +x install.sh
13. Run the installation script:
  $ sudo ./install.sh
  
The Pi will reboot in the end. Wait a while, and ssh again.

The hub should now be active as a background service, but whithout a configured serial number
(until we can use hwid this must be configured manually)

14. See that the hub service is running:
  $ sudo systemctl status SmarthubManager.service
15. Configure the serial number:
  $ hub_config
16. Write your serial number in the indicated spot. Then save ctrl+s, and exit ctrl+x.
17. Reboot with new config:
  $ hub_reboot
18. Wait a while and ssh again. Check that the service is running again:
  $ sudo systemctl status SmarthubManager.service

Now the hub should autenticate and respond to scan commands if the serial number is properly 
registered in the backend. The hub runs emulators by default. add the devices by scanning and 
adding the results in the frontend.


To enable wifi on your hub:
1. ssh into the hub and use the capture portal feature
  $ hub_portal
2. This will start a wifi hotspot that you can connect to with a smart phone. 
   Connect to "ONiO Smarthub RPi" and use the password "onio.com". Soon a page should pop up.
   Select your local wifi from the options and input your wifi password. Press continue.
3. The hub should now use the internal NetworkManager to connect to the wifi. Test this by 
   Removing the ethernet cable and test ssh. 
4. Optionally check that the connection was successful:
  $ sudo nmcli connection show



The hub runs as a background service on startup, with the script manager.py.
To stop the service:
  $ sudo systemctl stop SmarthubManager.service
To start:
  $ sudo systemctl start SmarthubManager.service
To restart:
  $ sudo systemctl restart SmarthubManager.service

I have some aliases set up by the install.sh script:
$ hub_portal - Starts the wifi hotspot allowing to change wifi.
$ hub_logs   - Displays the logs of the SmarthubManager.service in real-time. 
               Similar to regular console output of the python hub.
$ hub config - Opens the configuration file in nano for editing.
$ hub_reboot - Reloads the systemd daemon, restarts the smart hub service, and reboots the Raspberry Pi. Needed for applying new config.
(Note that running the install script again will reset the local changes to config.)


Please ask me if you have any troubles.




















