# Raspberry Pi 5 Hub Installation Guide

This guide provides step-by-step instructions to set up your Raspberry Pi 5 as a smart hub.

## Requirements

For the setup, you need:

- **Raspberry Pi 5**
- **Micro SD card**
- **Micro SD card reader**
- **USB-C power cable**
- **Ethernet cable**

**Optional extras:**

- USB keyboard for the Raspberry Pi
- External monitor and micro-HDMI cable for the Raspberry Pi

---

## Installation Steps

### 1. Prepare the SD Card

1. **Download the Raspberry Pi Imager Program** on your PC.
2. **Insert your micro-SD card** into your PC.
3. In the Imager, **choose OS**: select **"Ubuntu Bookworm 64-bit Lite"**.
4. **Choose storage**: pick your SD card from the list.
5. **Enable advanced settings**:
   - Enable **SSH**.
   - Choose a **host name**, **username**, and **password**.
6. **No need to configure Wi-Fi**.
7. **Save the settings** and **write the image** to the SD card.

### 2. Set Up the Raspberry Pi

8. **Insert the SD card** into your Raspberry Pi.
9. **Plug in power and Ethernet** to your Raspberry Pi.
10. After a few seconds, try to locate your Pi via SSH:

   ```bash
   ssh <username>@<hostname>.local
   ```

   If this does not work, you must find the Pi's IP address by other means:

   - **Option 1**: Connect a monitor and keyboard to the Pi and check the assigned IP address using:

     ```bash
     ifconfig
     ```

   - **Option 2**: Use a network scanning tool to find devices on your network.

   Then SSH into the Pi using:

   ```bash
   ssh <username>@<local-ip-address>
   ```

   The console may ask you to verify a cryptographic key. Type **yes** to continue.

### 3. Install the Hub Software

Once you have successfully SSH'd into the Pi:

11. **Download the install script from the remote repository**:

    ```bash
    wget https://raw.githubusercontent.com/onio-git/gateway.hub/refs/heads/master/app/install.sh
    ```

12. **Set the script permissions**:

    ```bash
    sudo chmod +x install.sh
    ```

13. **Run the installation script**:

    ```bash
    sudo ./install.sh
    ```

    Wait while this completes. If prompted about IP-table settings, press "yes".
    The Pi will reboot at the end. Wait a moment, then SSH into the Pi again.

### 4. Configure the Hub

The hub should now be active as a background service, but without a configured serial number (until we can use HWID, this must be configured manually).

14. **Check that the hub service is running**:

    ```bash
    sudo systemctl status SmarthubManager.service
    ```

15. **Configure the serial number**:

    ```bash
    hub_config
    ```

16. **Enter your serial number** in the indicated spot. Then save (`Ctrl+S`) and exit (`Ctrl+X`).

17. **Reboot with the new configuration**:

    ```bash
    hub_reboot
    ```

18. Wait a moment and SSH into the Pi again. **Check that the service is running**:

    ```bash
    sudo systemctl status SmarthubManager.service
    ```

Now the hub should authenticate and respond to scan commands if the serial number is properly registered in the backend. The hub runs emulators by default. Add the devices by scanning and adding the results in the frontend.

---

## Enabling Wi-Fi on Your Hub

1. **SSH into the hub** and use the captive portal feature:

   ```bash
   hub_portal
   ```

2. This will start a Wi-Fi hotspot that you can connect to with a smartphone:

   - Connect to **"ONiO Smarthub RPi"** using the password **"onio.com"**.
   - A page should pop up shortly.
   - Select your local Wi-Fi from the options and enter your Wi-Fi password.
   - Press **Continue**.

3. The hub should now use the internal NetworkManager to connect to Wi-Fi. Test this by removing the Ethernet cable and attempting to SSH into the Pi.

4. Optionally, check that the connection was successful:

   ```bash
   sudo nmcli connection show
   ```

---

## Managing the Hub Service

The hub runs as a background service on startup, using the script `manager.py`.

- **To stop the service**:

  ```bash
  sudo systemctl stop SmarthubManager.service
  ```

- **To start the service**:

  ```bash
  sudo systemctl start SmarthubManager.service
  ```

- **To restart the service**:

  ```bash
  sudo systemctl restart SmarthubManager.service
  ```

---

## Useful Aliases

The `install.sh` script sets up some aliases for convenience:

- **`hub_portal`** - Starts the Wi-Fi hotspot allowing you to change Wi-Fi settings.
- **`hub_logs`** - Displays the logs of the `SmarthubManager.service` in real-time (similar to regular console output of the Python hub).
- **`hub_config`** - Opens the configuration file in `nano` for editing.
- **`hub_reboot`** - Reloads the systemd daemon, restarts the smart hub service, and reboots the Raspberry Pi (needed for applying new config).

**Note:** Running the install script again will reset any local changes to the configuration.

---

If you have any troubles, please ask me.