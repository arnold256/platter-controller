# Configuration settings for Platter Controller

# Server settings
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False

# Queue settings
TIMEOUT_SECONDS = 120  # 2 minutes

# Motor GPIO pins (Pi Zero 2 W)
MOTOR_PINS = {
    1: {
        'speed': 18,      # Hardware PWM capable
        'brake': 23,
        'direction': 24
    },
    2: {
        'speed': 13,      # Hardware PWM capable
        'brake': 25,
        'direction': 8
    },
    3: {
        'speed': 12,      # Hardware PWM capable
        'brake': 16,
        'direction': 7
    }
}

# PWM settings
PWM_FREQUENCY = 1000  # Hz
PWM_RANGE = 255       # 8-bit control
