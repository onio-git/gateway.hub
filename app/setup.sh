#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Disable conflicting services 
sudo systemctl stop dhcpcd
sudo systemctl disable dhcpcd

# Ensure NetworkManager manages the interfaces
sudo tee /etc/NetworkManager/NetworkManager.conf > /dev/null << EOF
[main]
plugins=ifupdown,keyfile
[ifupdown]
managed=true
EOF

# Restart NetworkManager
sudo systemctl restart NetworkManager

# Create dnsmasq configuration for hotspot
sudo tee /etc/dnsmasq.d/hotspot.conf > /dev/null << EOF
# DHCP range for wlan0 interface
interface=wlan0
dhcp-range=192.168.4.10,192.168.4.100,12h

# Redirect all DNS queries to the hotspot's IP
address=/#/192.168.4.1

# Set the default gateway and DNS server
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
EOF

# Disable dnsmasq from starting at boot
sudo systemctl disable dnsmasq
sudo systemctl stop dnsmasq

# Create NetworkManager dispatcher script for dnsmasq
sudo tee /etc/NetworkManager/dispatcher.d/20-dnsmasq-hotspot > /dev/null << 'EOF'
#!/bin/bash

INTERFACE=$1
STATUS=$2
HOTSPOT_CONN="ONiO Smarthub RPi"

if [ "$INTERFACE" == "wlan0" ]; then
    if [ "$STATUS" == "up" ]; then
        CURRENT_CONN=$(nmcli -t -f NAME connection show --active | grep -w "$HOTSPOT_CONN")
        if [ "$CURRENT_CONN" == "$HOTSPOT_CONN" ]; then
            # Start dnsmasq
            logger "Starting dnsmasq for hotspot"
            systemctl start dnsmasq
        fi
    elif [ "$STATUS" == "down" ]; then
        # Stop dnsmasq
        logger "Stopping dnsmasq for hotspot"
        systemctl stop dnsmasq
    fi
fi
EOF

# Make the dispatcher script executable
sudo chmod +x /etc/NetworkManager/dispatcher.d/20-dnsmasq-hotspot

# Create NetworkManager dispatcher script for iptables
sudo tee /etc/NetworkManager/dispatcher.d/99-hotspot-iptables > /dev/null << 'EOF'
#!/bin/bash

INTERFACE=$1
STATUS=$2
HOTSPOT_CONN="ONiO Smarthub RPi"

if [ "$INTERFACE" == "wlan0" ]; then
    if [ "$STATUS" == "up" ]; then
        CURRENT_CONN=$(nmcli -t -f NAME connection show --active | grep -w "$HOTSPOT_CONN")
        if [ "$CURRENT_CONN" == "$HOTSPOT_CONN" ]; then
            # Flush existing rules
            iptables -t nat -F
            iptables -F

            # Allow traffic on wlan0
            iptables -A INPUT -i wlan0 -j ACCEPT
            iptables -A FORWARD -i wlan0 -j ACCEPT
            iptables -A OUTPUT -o wlan0 -j ACCEPT

            # Enable NAT
            iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE

            # Redirect all HTTP traffic to the captive portal
            iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 8080 -j REDIRECT --to-port 80

            # Save the iptables rules
            netfilter-persistent save
        fi
    elif [ "$STATUS" == "down" ]; then
        # Flush iptables rules
        iptables -t nat -F
        iptables -F
        netfilter-persistent save
    fi
fi
EOF

# Make the dispatcher script executable
sudo chmod +x /etc/NetworkManager/dispatcher.d/99-hotspot-iptables

# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Make IP forwarding persistent
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-ipforward.conf > /dev/null



echo "Installation and configuration complete."
echo "You can run the portal using: sudo python3 portal.py"
