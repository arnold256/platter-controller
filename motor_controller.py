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
        
        # Track the requested speed before brake is applied (to restore after brake release)
        self.pre_brake_speed = {1: 0, 2: 0, 3: 0}
        
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

            # Brake pin: PWM or digital ON/OFF
            if config.BRAKE_IS_PWM:
                self.pi.set_PWM_frequency(pins['brake'], config.PWM_FREQUENCY)
                self.pi.set_PWM_range(pins['brake'], config.PWM_RANGE)
            else:
                self.pi.set_mode(pins['brake'], pigpio.OUTPUT)
            
            # Initialize to stopped state (speed=0, apply full brake)
            self.pi.set_PWM_dutycycle(pins['speed'], 0)
            if config.BRAKE_IS_PWM:
                self.pi.set_PWM_dutycycle(pins['brake'], 0)
            else:
                # Digital brake: apply
                applied = 0 if config.BRAKE_ACTIVE_LOW else 1
                self.pi.write(pins['brake'], applied)
    
    def set_motor(self, motor_id, speed, direction, brake):
        """
        Set motor parameters
        
        Args:
            motor_id: 1, 2, or 3
            speed: 0-100 (percentage) - the user's requested speed
            direction: 0 or 1
            brake: 0-100 (percentage, >= threshold means brake applied)
        """
        if motor_id not in self.motors:
            return
        
        pins = self.motors[motor_id]

        # Clamp values from UI
        speed = max(0, min(100, speed))
        brake = max(0, min(100, brake))
        direction = 1 if direction else 0

        # Helper to map a UI value 0-100 to duty in 0..PWM_RANGE using raw [min,max]
        def _map(ui_value, duty_min, duty_max):
            ui_clamped = max(0, min(100, ui_value)) / 100.0
            dmin = max(0, min(config.PWM_RANGE, duty_min))
            dmax = max(0, min(config.PWM_RANGE, duty_max))
            return int(round(dmin + (dmax - dmin) * ui_clamped))

        # Check if brake is being applied
        brake_is_applied = brake >= config.BRAKE_APPLY_THRESHOLD
        
        # Debug log
        print(f"set_motor m{motor_id}: speed={speed}, brake={brake}, brake_is_applied={brake_is_applied}, pre_brake_speed={self.pre_brake_speed[motor_id]}", flush=True)
        
        # When brake is NOT applied, remember the speed for later restoration
        if not brake_is_applied:
            self.pre_brake_speed[motor_id] = speed
        
        # Determine effective speed:
        # - If brake is applied: use 100% of PWM_SPEED_MAX for maximum braking force
        # - If brake is not applied: use the requested speed (which we just saved)
        if brake_is_applied:
            speed_pwm = config.PWM_SPEED_MAX  # Full PWM_SPEED_MAX (178 for 70% cap)
        else:
            effective_speed = self.pre_brake_speed[motor_id]
            speed_pwm = _map(effective_speed, config.PWM_SPEED_MIN, config.PWM_SPEED_MAX)
        
        print(f"  effective_speed={effective_speed}, speed_pwm={speed_pwm}", flush=True)
        
        # Brake value
        if config.BRAKE_IS_PWM:
            brake_pwm = _map(brake, config.PWM_BRAKE_MIN, config.PWM_BRAKE_MAX)
        else:
            brake_pwm = None

        # Set direction
        self.pi.write(pins['direction'], direction)

        # Apply speed PWM
        try:
            self.pi.set_PWM_dutycycle(pins['speed'], speed_pwm)
        except Exception as e:
            print(f"GPIO error(speed) m{motor_id} pin={pins['speed']} duty={speed_pwm}: {e}", flush=True)
            raise

        # Apply brake
        if config.BRAKE_IS_PWM:
            try:
                self.pi.set_PWM_dutycycle(pins['brake'], brake_pwm)
            except Exception as e:
                print(f"GPIO error(brake PWM) m{motor_id} pin={pins['brake']} duty={brake_pwm}: {e}", flush=True)
                raise
        else:
            # Digital brake: ON if UI >= threshold, else OFF (release)
            on = 1 if brake_is_applied else 0
            level = (0 if config.BRAKE_ACTIVE_LOW else 1) if on else (1 if config.BRAKE_ACTIVE_LOW else 0)
            try:
                self.pi.write(pins['brake'], level)
            except Exception as e:
                print(f"GPIO error(brake DIO) m{motor_id} pin={pins['brake']} level={level}: {e}", flush=True)
                raise
    
    def stop_motor(self, motor_id):
        """Stop a specific motor"""
        if motor_id not in self.motors:
            return
        
        pins = self.motors[motor_id]
        self.pi.set_PWM_dutycycle(pins['speed'], 0)
        if config.BRAKE_IS_PWM:
            self.pi.set_PWM_dutycycle(pins['brake'], 0)  # Full brake (PWM)
        else:
            applied = 0 if config.BRAKE_ACTIVE_LOW else 1
            self.pi.write(pins['brake'], applied)
    
    def stop_all(self):
        """Stop all motors"""
        for motor_id in self.motors.keys():
            self.stop_motor(motor_id)
    
    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        try:
            self.stop_all()
            # Release all pins
            for pins in self.motors.values():
                try:
                    self.pi.set_PWM_dutycycle(pins['speed'], 0)
                    self.pi.set_PWM_dutycycle(pins['brake'], 0)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            try:
                if hasattr(self.pi, 'stop'):
                    self.pi.stop()
            except Exception:
                pass
