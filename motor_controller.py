import atexit


# Always define a minimal mock so we can fall back even if real pigpio imports
class _MockPi:
    OUTPUT = 1

    def __init__(self):
        self.connected = True

    # Pin/Mode APIs
    def set_mode(self, *args, **kwargs):
        pass

    def write(self, *args, **kwargs):
        pass

    # PWM APIs
    def set_PWM_frequency(self, *args, **kwargs):
        pass

    def set_PWM_range(self, *args, **kwargs):
        pass

    def set_PWM_dutycycle(self, *args, **kwargs):
        pass

    def stop(self):
        pass

try:
    import pigpio  # type: ignore
    _PIGPIO_AVAILABLE = True
except Exception:  # ImportError or runtime errors on non-Pi
    _PIGPIO_AVAILABLE = False

    class pigpio:  # minimal shim to match usage
        OUTPUT = 1

        @staticmethod
        def pi():
            return _MockPi()

import sys
import time


class MotorController:
    def __init__(self):
        # GPIO Pin assignments
        # Motor 1
        self.MOTOR1_SPEED = 18    # Hardware PWM
        self.MOTOR1_BRAKE = 23
        self.MOTOR1_DIR = 24
        
        # Motor 2
        self.MOTOR2_SPEED = 13    # Hardware PWM
        self.MOTOR2_BRAKE = 25
        self.MOTOR2_DIR = 8
        
        # Motor 3
        self.MOTOR3_SPEED = 12    # Hardware PWM
        self.MOTOR3_BRAKE = 16
        self.MOTOR3_DIR = 7
        
        self.motors = {
            1: {
                'speed': self.MOTOR1_SPEED,
                'brake': self.MOTOR1_BRAKE,
                'direction': self.MOTOR1_DIR
            },
            2: {
                'speed': self.MOTOR2_SPEED,
                'brake': self.MOTOR2_BRAKE,
                'direction': self.MOTOR2_DIR
            },
            3: {
                'speed': self.MOTOR3_SPEED,
                'brake': self.MOTOR3_BRAKE,
                'direction': self.MOTOR3_DIR
            }
        }
        
        # Initialize pigpio with retries (pigpiod may still be starting)
        self.pi = pigpio.pi()

        # Note: pigpio sets .connected to 1 (connected) or 0 (not connected)
        if not getattr(self.pi, 'connected', 1):
            if sys.platform.startswith('linux'):
                # Retry for up to 5 seconds
                for _ in range(10):
                    time.sleep(0.5)
                    self.pi = pigpio.pi()
                    if getattr(self.pi, 'connected', 0):
                        break
                if not getattr(self.pi, 'connected', 0):
                    raise Exception("Failed to connect to pigpio daemon")
            else:
                # On non-Linux dev machines, fall back to mock
                self.pi = _MockPi()
        
        # Setup all pins
        self._setup_pins()
        
        # Register cleanup
        atexit.register(self.cleanup)
    
    def _setup_pins(self):
        """Initialize all GPIO pins"""
        for motor_id, pins in self.motors.items():
            # Set direction pins as output
            self.pi.set_mode(pins['direction'], pigpio.OUTPUT)
            self.pi.write(pins['direction'], 0)
            
            # Set PWM frequency to 1000Hz for speed and brake
            self.pi.set_PWM_frequency(pins['speed'], 1000)
            self.pi.set_PWM_frequency(pins['brake'], 1000)
            
            # Set PWM range (0-255 for 8-bit control)
            self.pi.set_PWM_range(pins['speed'], 255)
            self.pi.set_PWM_range(pins['brake'], 255)
            
            # Initialize to stopped state
            self.pi.set_PWM_dutycycle(pins['speed'], 0)
            self.pi.set_PWM_dutycycle(pins['brake'], 255)  # Full brake
    
    def set_motor(self, motor_id, speed, direction, brake):
        """
        Set motor parameters
        
        Args:
            motor_id: 1, 2, or 3
            speed: 0-100 (percentage)
            direction: 0 or 1
            brake: 0-100 (percentage)
        """
        if motor_id not in self.motors:
            return
        
        pins = self.motors[motor_id]

        # Clamp values from UI
        speed = max(0, min(100, speed))
        brake = max(0, min(100, brake))
        direction = 1 if direction else 0

        # Map UI speed (0-100) to capped PWM duty (0-70% of 0-255)
        speed_pwm = int((speed / 100.0) * 255 * 0.70)
        # Brake remains full-range mapping (0-100 -> 0-255)
        brake_pwm = int(brake * 2.55)

        # Set direction
        self.pi.write(pins['direction'], direction)

        # Apply PWM values
        self.pi.set_PWM_dutycycle(pins['speed'], speed_pwm)
        self.pi.set_PWM_dutycycle(pins['brake'], brake_pwm)
    
    def stop_motor(self, motor_id):
        """Stop a specific motor"""
        if motor_id not in self.motors:
            return
        
        pins = self.motors[motor_id]
        self.pi.set_PWM_dutycycle(pins['speed'], 0)
        self.pi.set_PWM_dutycycle(pins['brake'], 255)  # Full brake
    
    def stop_all(self):
        """Stop all motors"""
        for motor_id in self.motors.keys():
            self.stop_motor(motor_id)
    
    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        self.stop_all()
        
        # Release all pins
        for pins in self.motors.values():
            self.pi.set_PWM_dutycycle(pins['speed'], 0)
            self.pi.set_PWM_dutycycle(pins['brake'], 0)
        
        self.pi.stop()
