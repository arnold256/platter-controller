#!/bin/bash

# Platter Controller Startup Script

echo "Starting Platter Controller..."

# Check if pigpiod is running
if ! pgrep -x "pigpiod" > /dev/null; then
    echo "Starting pigpio daemon..."
    sudo pigpiod
    sleep 2
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the Flask application
python3 app.py
