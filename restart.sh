#!/bin/bash
#
# Restart script for Platter Controller
# Use this during testing to quickly restart the service
#

echo "=================================="
echo "Platter Controller Restart"
echo "=================================="
echo ""

# Check if service exists
if ! systemctl list-unit-files | grep -q "platter-controller.service"; then
    echo "✗ Service 'platter-controller' not found"
    echo ""
    echo "Have you run deploy.sh yet?"
    exit 1
fi

echo "Restarting platter-controller service..."
echo ""

# Restart the service
sudo systemctl restart platter-controller

# Wait a moment for startup
sleep 2

# Show status
echo ""
echo "Service status:"
sudo systemctl status platter-controller --no-pager

echo ""
echo "Recent logs:"
sudo journalctl -u platter-controller -n 10 --no-pager

echo ""
echo "=================================="
echo "Access at: http://$(hostname -I | awk '{print $1}'):5000"
echo "=================================="
echo ""
echo "View live logs with: sudo journalctl -u platter-controller -f"
echo ""
