#!/bin/bash

# Exit script on any error
set -e

# Update system packages
echo "Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git

# Clone or update the git repository
echo "Updating git repository..."

REPO_DIR="/opt/gateway.hub"

if [ -d "$REPO_DIR/.git" ]; then
    echo "Repository already exists. Are you sure you want to update it? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "Exiting..."
        exit 1
    fi
    cd "$REPO_DIR"
    git reset --hard
    git pull 
else
    echo "Cloning repository..."
    sudo mkdir -p /opt/gateway.hub
    git clone https://github.com/onio-git/gateway.hub.git "$REPO_DIR"
fi


# sudo cp -R "$HOME/gateway.hub/app/"* /opt/gateway.hub/app/
sudo chown -R root:root /opt/gateway.hub
sudo chown root:root /opt/gateway.hub/app/*.py
sudo chmod 644 /opt/gateway.hub/app/*.py


# Navigate to the project directory
cd /opt/gateway.hub/app

# Install Python dependencies (if applicable)
sudo apt install -y python3 python3-pip python3-flask python3-waitress python3-bleak python3-yaml python3-pexpect \
                    network-manager dhcpcd dnsmasq iptables-persistent \
                    wireless-tools sudo net-tools

# Run any additional setup scripts
if [ -f setup.sh ]; then
    echo "Running setup script..."
    chmod +x setup.sh
    ./setup.sh
fi

# Set up scripts to run on startup using systemd
echo "Setting up managerp service..."
sudo cp SmarthubManager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable SmarthubManager.service
sudo systemctl restart SmarthubManager.service

# Set up scripts to run on startup using systemd
echo "Setting up server service..."
sudo cp SmarthubServer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable SmarthubServer.service
sudo systemctl restart SmarthubServer.service







# Create quick commands
echo "Creating quick commands..."

# 1. hub_portal
sudo bash -c 'echo -e "#!/bin/bash\nsudo /usr/bin/python3 /opt/gateway.hub/app/portal.py" > /usr/local/bin/hub_portal'
sudo chmod +x /usr/local/bin/hub_portal

# 2. hub_config
sudo bash -c 'echo -e "#!/bin/bash\nsudo nano /opt/gateway.hub/app/config/config.ini" > /usr/local/bin/hub_config'
sudo chmod +x /usr/local/bin/hub_config

# 3. hub_reboot
sudo bash -c 'echo -e "#!/bin/bash\nsudo systemctl daemon-reload && sudo systemctl restart SmarthubManager.service && sudo reboot" > /usr/local/bin/hub_reboot'
sudo chmod +x /usr/local/bin/hub_reboot

# 4. hub_logs
sudo bash -c 'echo -e "#!/bin/bash\nsudo journalctl -u SmarthubManager.service -f" > /usr/local/bin/hub_logs'
sudo chmod +x /usr/local/bin/hub_logs

# Edit hostname
echo "Setting up hostname..."
sudo bash -c 'echo "onio-hub" > /etc/hostname'
# Edit hosts file:
sudo bash -c 'echo -e "127.0.0.1\tlocalhost
::1\t\tlocalhost ip6-localhost ip6-loopback
ff02::1\t\tip6-allnodes
ff02::2\t\tip6-allrouters

127.0.1.1\t\tonio-hub" > /etc/hosts'

# Reboot the system to apply changes
echo ""
echo "----------------------------------------"
echo "Installation complete. Rebooting the device..." 

echo "Please wait for the device to reboot and then ssh back in."
echo "You can then run the following commands to interact with the hub:"
echo "  - hub_portal:   Start the web portal"
echo "  - hub_config:   Edit the configuration file"
echo "  - hub_reboot:   Restart the hub with new configurations"
echo "  - hub_logs:     View the logs"

sleep 5
sudo reboot
