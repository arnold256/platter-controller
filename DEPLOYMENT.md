# Platter Controller Deployment Guide

## Overview
The deployment script (`deploy.sh`) now ensures that everything starts correctly on system reboot.

## What Gets Set Up

### 1. **System Dependencies**
- Python 3 with pip and venv
- pigpio library and daemon

### 2. **pigpiod Daemon**
- Enabled for auto-start on boot
- Started immediately during deployment
- Required by the application for GPIO control

### 3. **Python Virtual Environment**
- Created in `venv/` directory
- Contains all Python dependencies from `requirements.txt`
- Activated in the systemd service

### 4. **Systemd Service**
- Service name: `platter-controller`
- Automatically enabled on boot
- Configured with proper working directory and environment

## Deployment Process

Run the deployment script on your Raspberry Pi:

```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. ✅ Update system packages
2. ✅ Install Python and pigpio
3. ✅ Enable and start pigpiod
4. ✅ Create Python virtual environment
5. ✅ Install Python dependencies
6. ✅ Set up systemd service with correct paths
7. ✅ **Automatically enable the service for auto-start**
8. ✅ Optionally start the service immediately

## Boot Behavior

After deployment and reboot:

1. **At boot time:**
   - pigpiod daemon starts first
   - Systemd waits for pigpiod to be ready
   - platter-controller service starts automatically
   - Flask application listens on port 5000

2. **If the application crashes:**
   - Systemd automatically restarts it
   - Waits 10 seconds before retry
   - Logs captured in systemd journal

## Verification

Check that everything is working:

```bash
# Check if service is enabled
sudo systemctl is-enabled platter-controller
# Output should be: enabled

# Check current status
sudo systemctl status platter-controller

# View logs in real-time
sudo journalctl -u platter-controller -f

# Check pigpiod is running
ps aux | grep pigpiod
```

## Service Management

```bash
# Start service manually
sudo systemctl start platter-controller

# Stop service
sudo systemctl stop platter-controller

# Restart service
sudo systemctl restart platter-controller

# Disable auto-start on boot
sudo systemctl disable platter-controller

# Re-enable auto-start on boot
sudo systemctl enable platter-controller

# View recent logs
sudo journalctl -u platter-controller -n 50
```

## Access the Application

1. Find your Pi's IP address:
   ```bash
   hostname -I
   ```

2. Open in browser:
   ```
   http://<your-pi-ip>:5000
   ```

## Key Changes from Previous Version

### ✅ Deploy Script Improvements
- Now explicitly enables service with `systemctl enable`
- Properly sets both PATH and ExecStart in systemd service
- Validates pigpiod is running before proceeding
- Clearer output and status messages
- Automatically enables auto-start (no manual step needed)

### ✅ Systemd Service Improvements
- Added StandardOutput and StandardError directives for better logging
- Service waits for pigpiod dependency
- Restart policy ensures service recovers from crashes

## Uninstall

To remove all components:

```bash
chmod +x uninstall.sh
./uninstall.sh
```

This will remove the service, virtual environment, and optionally pigpiod.

## Troubleshooting

### Service won't start after reboot
```bash
# Check service status
sudo systemctl status platter-controller

# Check for errors in logs
sudo journalctl -u platter-controller -n 100

# Verify pigpiod is running
sudo systemctl status pigpiod

# Check file permissions
ls -la /etc/systemd/system/platter-controller.service
```

### Can't access web interface
- Verify service is running: `sudo systemctl status platter-controller`
- Check port 5000 is open: `sudo netstat -tlnp | grep 5000`
- Check firewall settings
- Verify Pi IP address: `hostname -I`

### pigpiod issues
```bash
# Restart pigpiod
sudo systemctl restart pigpiod

# Check status
sudo systemctl status pigpiod

# View pigpiod logs
sudo journalctl -u pigpiod -n 50
```

## File Locations on Pi

```
/home/[user]/platter_controller/          # Application directory
├── venv/                                  # Virtual environment
├── app.py                                 # Flask application
├── config.py                              # Configuration
├── motor_controller.py                    # Motor control logic
├── queue_manager.py                       # Queue management
├── requirements.txt                       # Python dependencies
├── deploy.sh                              # Deployment script
├── uninstall.sh                           # Uninstall script
├── start.sh                               # Manual start script
├── static/                                # Web assets
└── templates/                             # HTML templates

/etc/systemd/system/platter-controller.service  # Systemd service file
```
