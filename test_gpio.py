#!/usr/bin/env python3
"""
GPIO Test Script for Platter Controller
This script tests each motor's connections one at a time
"""

import pigpio
import time
import sys

# GPIO Pin assignments
MOTORS = {
    1: {'speed': 18, 'brake': 23, 'direction': 24},
    2: {'speed': 13, 'brake': 25, 'direction': 8},
    3: {'speed': 12, 'brake': 16, 'direction': 7}
}

def test_motor(pi, motor_id, pins):
    """Test a single motor"""
    print(f"\n{'='*50}")
    print(f"Testing Motor {motor_id}")
    print(f"Speed Pin: GPIO {pins['speed']}")
    print(f"Brake Pin: GPIO {pins['brake']}")
    print(f"Direction Pin: GPIO {pins['direction']}")
    print(f"{'='*50}")
    
    # Setup pins
    pi.set_mode(pins['direction'], pigpio.OUTPUT)
    pi.set_PWM_frequency(pins['speed'], 1000)
    pi.set_PWM_frequency(pins['brake'], 1000)
    pi.set_PWM_range(pins['speed'], 255)
    pi.set_PWM_range(pins['brake'], 255)
    
    print("\nTest 1: Release brake")
    pi.set_PWM_dutycycle(pins['brake'], 0)
    time.sleep(1)
    
    print("Test 2: Low speed, clockwise direction")
    pi.write(pins['direction'], 1)
    pi.set_PWM_dutycycle(pins['speed'], 64)  # 25% speed
    time.sleep(3)
    
    print("Test 3: Medium speed")
    pi.set_PWM_dutycycle(pins['speed'], 128)  # 50% speed
    time.sleep(3)
    
    print("Test 4: Change direction (counter-clockwise)")
    pi.write(pins['direction'], 0)
    time.sleep(3)
    
    print("Test 5: Stop motor")
    pi.set_PWM_dutycycle(pins['speed'], 0)
    time.sleep(1)
    
    print("Test 6: Apply brake")
    pi.set_PWM_dutycycle(pins['brake'], 255)
    time.sleep(1)
    
    print(f"\nMotor {motor_id} test complete!")

def cleanup(pi):
    """Clean up all GPIO"""
    print("\nCleaning up GPIO...")
    for pins in MOTORS.values():
        pi.set_PWM_dutycycle(pins['speed'], 0)
        pi.set_PWM_dutycycle(pins['brake'], 255)
        pi.write(pins['direction'], 0)
    pi.stop()
    print("Cleanup complete!")

def main():
    print("Platter Controller GPIO Test")
    print("="*50)
    
    # Connect to pigpio daemon
    pi = pigpio.pi()
    
    if not pi.connected:
        print("ERROR: Could not connect to pigpio daemon!")
        print("Make sure pigpiod is running: sudo pigpiod")
        sys.exit(1)
    
    print("Successfully connected to pigpio daemon")
    
    try:
        # Test each motor
        for motor_id in [1, 2, 3]:
            response = input(f"\nTest Motor {motor_id}? (y/n/q to quit): ").lower()
            
            if response == 'q':
                break
            elif response == 'y':
                test_motor(pi, motor_id, MOTORS[motor_id])
            else:
                print(f"Skipping Motor {motor_id}")
        
        print("\n" + "="*50)
        print("All tests complete!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    
    except Exception as e:
        print(f"\nERROR: {e}")
    
    finally:
        cleanup(pi)

if __name__ == "__main__":
    main()
