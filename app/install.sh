#!/bin/bash

# Exit script on any error
set -e

# Update system packages
echo "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git

# Clone the git repository
echo "Cloning git repository..."
if [ -d "gateway.hub/.git" ]; then
    echo "Repository already exists. Pulling latest changes..."
    cd "gateway.hub"
    git pull
else
    echo "Cloning repository..."
    git clone git@github.com:jaaseru/onio-public-hub.git "gateway.hub"
fi

sudo mkdir -p /opt/gateway.hub/
sudo cp -R ~/gateway.hub/* /opt/gateway.hub/
sudo chown -R root:root /opt/gateway.hub


# Navigate to the project directory
cd /opt/gateway.hub/app

# Install Python dependencies (if applicable)
sudo apt install -y python3 python3-pip python3-flask python3-waitress python3-bleak python3-yaml \
                    network-manager dhcpcd dnsmasq iptables-persistent \
                    wireless-tools sudo net-tools

# Run any additional setup scripts
if [ -f setup.sh ]; then
    echo "Running setup script..."
    chmod +x setup.sh
    ./setup.sh
fi

# Set up scripts to run on startup using systemd
echo "Setting up startup service..."
sudo cp SmarthubManager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable SmarthubManager.service

# Reboot the system to apply changes
echo "Installation complete. Rebooting..."
sudo reboot