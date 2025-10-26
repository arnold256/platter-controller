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
import config


class MotorController:
    def __init__(self):
        # GPIO Pin assignments - can be moved to config.py if needed
        self.motors = {
            1: {'speed': 18, 'brake': 23, 'direction': 24},
            2: {'speed': 13, 'brake': 25, 'direction': 8},
            3: {'speed': 12, 'brake': 16, 'direction': 7}
        }
        
        # On Linux (Pi hardware), require real pigpio module
        if sys.platform.startswith('linux') and not _PIGPIO_AVAILABLE:
            raise Exception("pigpio Python module not found. Install with: sudo apt-get install -y python3-pigpio pigpio")

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
                    raise Exception("Failed to connect to pigpio daemon. Ensure pigpiod is enabled and running.")
            else:
                # On non-Linux dev machines, fall back to mock
                self.pi = _MockPi()

        # Log which backend is active (helps verify not using mock on hardware)
        backend = 'mock' if (not _PIGPIO_AVAILABLE or not sys.platform.startswith('linux')) else 'pigpio'
        try:
            print(f"MotorController backend: {backend}, connected={getattr(self.pi, 'connected', 'n/a')}")
        except Exception:
            pass
        
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
            
            # Speed pin uses PWM
            self.pi.set_PWM_frequency(pins['speed'], config.PWM_FREQUENCY)
            self.pi.set_PWM_range(pins['speed'], config.PWM_RANGE)
            self.pi.set_PWM_dutycycle(pins['speed'], 0)
            
            # Brake pin: digital ON/OFF only
            self.pi.set_mode(pins['brake'], pigpio.OUTPUT)
            applied = 0 if config.BRAKE_ACTIVE_LOW else 1
            self.pi.write(pins['brake'], applied)
    
    def set_motor(self, motor_id, speed, direction, brake):
        """
        Set motor parameters
        
        Args:
            motor_id: 1, 2, or 3
            speed: 0-100 (percentage) - requested speed from slider
            direction: 0 or 1
            brake: 0-100 (percentage, >= threshold means brake applied)
        
        Logic:
        - If brake is applied: set speed PWM to PWM_SPEED_MAX (full braking force), activate brake GPIO
        - If brake is released: set speed PWM to the requested speed, release brake GPIO
        """
        if motor_id not in self.motors:
            return
        
        pins = self.motors[motor_id]

        # Clamp values from UI
        speed = max(0, min(100, speed))
        brake = max(0, min(100, brake))
        direction = 1 if direction else 0

        # Helper to map a UI value 0-100 to duty in 0..PWM_RANGE
        def _map(ui_value, duty_min, duty_max):
            ui_clamped = max(0, min(100, ui_value)) / 100.0
            dmin = max(0, min(config.PWM_RANGE, duty_min))
            dmax = max(0, min(config.PWM_RANGE, duty_max))
            return int(round(dmin + (dmax - dmin) * ui_clamped))

        # Check if brake is being applied
        brake_is_applied = brake >= config.BRAKE_APPLY_THRESHOLD
        
        # Determine speed PWM based on brake state
        if brake_is_applied:
            # Brake ON: use maximum speed for strong braking
            speed_pwm = config.PWM_SPEED_MAX
            print(f"set_motor m{motor_id}: BRAKE ON, speed_pwm={speed_pwm}", flush=True)
        else:
            # Brake OFF: use the requested speed from slider
            speed_pwm = _map(speed, config.PWM_SPEED_MIN, config.PWM_SPEED_MAX)
            print(f"set_motor m{motor_id}: BRAKE OFF, speed={speed}, speed_pwm={speed_pwm}", flush=True)

        # Set direction
        self.pi.write(pins['direction'], direction)

        # Apply speed PWM FIRST
        try:
            self.pi.set_PWM_dutycycle(pins['speed'], speed_pwm)
        except Exception as e:
            print(f"GPIO error(speed) m{motor_id} pin={pins['speed']} duty={speed_pwm}: {e}", flush=True)
            raise

        # Apply brake AFTER speed PWM is set
        # Brake GPIO level: when brake is ON, we RELEASE the brake (inactive)
        # and let the PWM provide strong braking force
        if brake_is_applied:
            level = 1 if config.BRAKE_ACTIVE_LOW else 0  # RELEASE brake (inactive level)
        else:
            level = 0 if config.BRAKE_ACTIVE_LOW else 1  # APPLY brake (active level)
        
        try:
            self.pi.write(pins['brake'], level)
            print(f"  brake GPIO pin={pins['brake']} level={level}", flush=True)
        except Exception as e:
            print(f"GPIO error(brake) m{motor_id} pin={pins['brake']} level={level}: {e}", flush=True)
            raise
    
    def stop_motor(self, motor_id):
        """Stop a specific motor"""
        if motor_id not in self.motors:
            return
        
        pins = self.motors[motor_id]
        self.pi.set_PWM_dutycycle(pins['speed'], 0)
        # Apply brake (inactive when stopped)
        released = 1 if config.BRAKE_ACTIVE_LOW else 0
        self.pi.write(pins['brake'], released)
    
    def stop_all(self):
        """Stop all motors"""
        for motor_id in self.motors.keys():
            self.stop_motor(motor_id)
    
    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        try:
            self.stop_all()
        except Exception:
            pass
        finally:
            try:
                if hasattr(self.pi, 'stop'):
                    self.pi.stop()
            except Exception:
                pass
