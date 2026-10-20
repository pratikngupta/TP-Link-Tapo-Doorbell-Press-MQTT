#!/usr/bin/env bash
set -e

# Tapo D235 MQTT Sniffer Installer for Debian / Ubuntu
echo "=== Tapo D235 MQTT Sniffer Installer ==="

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run this installer as root (e.g. sudo bash install.sh)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "1. Installing system dependencies (python3, python3-venv, pip, mosquitto-clients)..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip mosquitto-clients

echo "2. Setting up Python virtual environment in /opt/mqtt_sniffer_env..."
if [ ! -d "/opt/mqtt_sniffer_env" ]; then
    python3 -m venv /opt/mqtt_sniffer_env
fi

/opt/mqtt_sniffer_env/bin/pip install --upgrade pip
/opt/mqtt_sniffer_env/bin/pip install -r "$SCRIPT_DIR/requirements.txt"

echo "3. Installing script to /etc/mqttsniffer/mqttsniffer.py..."
mkdir -p /etc/mqttsniffer
cp "$SCRIPT_DIR/mqttsniffer.py" /etc/mqttsniffer/mqttsniffer.py
chmod 755 /etc/mqttsniffer/mqttsniffer.py

echo "4. Setting up configuration file..."
if [ ! -f "/etc/mqttsniffer/mqttsniffer.env" ]; then
    cp "$SCRIPT_DIR/mqttsniffer.env.example" /etc/mqttsniffer/mqttsniffer.env
    chmod 600 /etc/mqttsniffer/mqttsniffer.env
    echo "Created /etc/mqttsniffer/mqttsniffer.env with default configuration."
    echo "Make sure to edit this file with your actual MQTT password!"
else
    echo "Existing /etc/mqttsniffer/mqttsniffer.env preserved."
fi

echo "5. Installing and enabling systemd service (mqtt-sniffer.service)..."
cp "$SCRIPT_DIR/mqtt-sniffer.service" /etc/systemd/system/mqtt-sniffer.service
systemctl daemon-reload
systemctl enable mqtt-sniffer.service
systemctl restart mqtt-sniffer.service

echo ""
echo "=== Installation Complete! ==="
echo "Service status:"
systemctl status mqtt-sniffer.service --no-pager || true
echo ""
echo "Useful commands:"
echo " - Edit config / password: sudo nano /etc/mqttsniffer/mqttsniffer.env"
echo " - Restart service:        sudo systemctl restart mqtt-sniffer"
echo " - View live logs:         sudo journalctl -u mqtt-sniffer -f"
