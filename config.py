# Configuration settings for Platter Controller

# Server settings
HOST = '0.0.0.0'
PORT = 8080
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

# UI -> PWM scaling (raw duty)
# Map UI 0-100 to an actual PWM duty window [MIN, MAX] in raw units (0..PWM_RANGE)
# Defaults: speed limited to 70% of 255 (≈178), brake full range
PWM_SPEED_MIN = 0        # raw duty (0..255)
PWM_SPEED_MAX = 178      # raw duty (70% of 255)
PWM_BRAKE_MIN = 0        # raw duty (0..255)
PWM_BRAKE_MAX = 255      # raw duty (full range)
