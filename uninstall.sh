#!/bin/bash
#
# Uninstall script for Platter Controller
# This script removes everything installed by deploy.sh
# Run this to completely remove the Platter Controller from your system
#

set -e

echo "=================================="
echo "Platter Controller Uninstall"
echo "=================================="
echo ""
echo "WARNING: This will remove the Platter Controller and all its components!"
echo "This includes:"
echo "  - Virtual environment and Python dependencies"
echo "  - systemd service configuration"
echo "  - pigpiod daemon (if not used by other applications)"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo "Starting uninstall process..."
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "Please do not run as root (no sudo)"
    exit 1
fi

# Stop the service if running
echo "Step 1: Stopping platter-controller service..."
if systemctl is-active --quiet platter-controller; then
    sudo systemctl stop platter-controller
    echo "✓ Service stopped"
else
    echo "✓ Service not running"
fi

# Disable the service
echo "Step 2: Disabling platter-controller service..."
if [ -f /etc/systemd/system/platter-controller.service ]; then
    sudo systemctl disable platter-controller 2>/dev/null || true
    echo "✓ Service disabled"
else
    echo "✓ Service not found"
fi

# Remove systemd service file
echo "Step 3: Removing systemd service file..."
if [ -f /etc/systemd/system/platter-controller.service ]; then
    sudo rm /etc/systemd/system/platter-controller.service
    sudo systemctl daemon-reload
    echo "✓ Service file removed"
else
    echo "✓ Service file not found"
fi

# Remove virtual environment
echo "Step 4: Removing Python virtual environment..."
if [ -d "venv" ]; then
    rm -rf venv
    echo "✓ Virtual environment removed"
else
    echo "✓ Virtual environment not found"
fi

# Remove script permissions
echo "Step 5: Removing executable permissions from scripts..."
chmod -x start.sh 2>/dev/null || true
chmod -x test_gpio.py 2>/dev/null || true
echo "✓ Script permissions removed"

# Optional: Stop pigpiod (with confirmation)
echo ""
read -p "Would you like to stop the pigpiod daemon? (yes/no): " stop_pigpio

if [ "$stop_pigpio" = "yes" ]; then
    echo "Step 6: Stopping pigpiod daemon..."
    if pgrep -x "pigpiod" > /dev/null; then
        sudo systemctl stop pigpiod
        sudo systemctl disable pigpiod
        echo "✓ pigpiod daemon stopped and disabled"
    else
        echo "✓ pigpiod daemon not running"
    fi
else
    echo "Step 6: Skipping pigpiod daemon removal"
fi

echo ""
echo "=================================="
echo "Uninstall Complete!"
echo "=================================="
echo ""
echo "The following has been removed:"
echo "  ✓ platter-controller systemd service"
echo "  ✓ Python virtual environment"
echo ""

if [ "$stop_pigpio" = "yes" ]; then
    echo "  ✓ pigpiod daemon"
fi

echo ""
echo "Note: The application files (app.py, config.py, etc.) remain in this directory."
echo "To completely remove the application, delete this directory manually."
echo ""
echo "To reinstall, run: ./deploy.sh"
echo ""
