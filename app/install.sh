#!/bin/bash

# Exit script on any error
set -e

# Update system packages
echo "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Clone the git repository
echo "Cloning git repository..."
git clone git@github.com:onio-git/gateway.hub.git /home/pi/Desktop/gateway.hub

# Navigate to the project directory
cd /home/pi/Desktop/gateway.hub

# Install Python dependencies (if applicable)
sudo apt install -y python3 python3-pip python3-flask python3-waitress \
                    network-manager dnsmasq iptables-persistent \
                    wireless-tools sudo net-tools

# Run any additional setup scripts
if [ -f setup.sh ]; then
    echo "Running setup script..."
    chmod +x setup.sh
    ./setup.sh
fi

# Set up scripts to run on startup using systemd
echo "Setting up startup service..."
cd /home/pi/Desktop/gateway.hub/app
sudo cp SmarthubManager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable SmarthubManager.service

# Reboot the system to apply changes
echo "Installation complete. Rebooting..."
sudo reboot
