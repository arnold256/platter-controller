#!/bin/bash
#
# Quick deployment script for Platter Controller
# Run this on your Raspberry Pi Zero 2 W
#

set -e

echo "=================================="
echo "Platter Controller Quick Setup"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "Please do not run as root (no sudo)"
    exit 1
fi

# Update system
echo "Step 1: Updating system packages..."
sudo apt-get update

# Install dependencies
echo "Step 2: Installing system dependencies..."
sudo apt-get install -y python3-pip python3-venv pigpio

# Enable pigpio
echo "Step 3: Enabling pigpio daemon..."
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# Check if pigpiod is running
if pgrep -x "pigpiod" > /dev/null; then
    echo "✓ pigpiod is running"
else
    echo "✗ Failed to start pigpiod"
    exit 1
fi

# Create virtual environment
echo "Step 4: Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python packages
echo "Step 5: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Make scripts executable
echo "Step 6: Setting up executable scripts..."
chmod +x start.sh
chmod +x test_gpio.py

# Setup systemd service
echo "Step 7: Setting up systemd service..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo sed "s|/home/pi/platter_controller|$SCRIPT_DIR|g" platter-controller.service > /tmp/platter-controller.service
sudo mv /tmp/platter-controller.service /etc/systemd/system/platter-controller.service
sudo sed -i "s|User=pi|User=$USER|g" /etc/systemd/system/platter-controller.service

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "Quick Commands:"
echo "  Start manually:     ./start.sh"
echo "  Test GPIO:          python3 test_gpio.py"
echo "  Enable auto-start:  sudo systemctl enable platter-controller"
echo "  Start service:      sudo systemctl start platter-controller"
echo "  Check status:       sudo systemctl status platter-controller"
echo "  View logs:          sudo journalctl -u platter-controller -f"
echo ""
echo "To find your Pi's IP address: hostname -I"
echo "Access the web interface at: http://<your-pi-ip>:5000"
echo ""
echo "Would you like to start the service now? (y/n)"
read -r response

if [ "$response" = "y" ]; then
    sudo systemctl start platter-controller
    echo "Service started! Checking status..."
    sleep 2
    sudo systemctl status platter-controller --no-pager
    echo ""
    echo "Access at: http://$(hostname -I | awk '{print $1}'):5000"
fi
