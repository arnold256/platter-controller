#!/usr/bin/env bash
# Quick GPIO test using pigpio 'pigs' CLI (no Python app needed)
# Works on Raspberry Pi with pigpiod running.
# Usage examples:
#   ./gpio_pigs_test.sh init                 # set freq/range and safe defaults
#   ./gpio_pigs_test.sh spin 1 160 1 5       # Motor1 duty=160 dir=CW for 5s
#   ./gpio_pigs_test.sh brake 1 255          # Apply full brake on Motor1
#   ./gpio_pigs_test.sh stop 1               # Stop Motor1, full brake
#   ./gpio_pigs_test.sh status               # Print current duty/freq/range/levels
#   ./gpio_pigs_test.sh allstop              # Stop all motors, full brake

set -euo pipefail

# Pin map (must match config.py / motor_controller.py)
M1_SPEED=18; M1_BRAKE=23; M1_DIR=24
M2_SPEED=13; M2_BRAKE=25; M2_DIR=8
M3_SPEED=12; M3_BRAKE=16; M3_DIR=7

# Settings (keep in sync with config.py)
FREQ=1000
RANGE=255

need_pigpiod() {
  if ! pgrep -x pigpiod >/dev/null; then
    echo "Starting pigpiod..."
    sudo pigpiod
    sleep 1
  fi
}

pin_for() {
  case "$1:$2" in
    1:SPEED) echo $M1_SPEED;; 1:BRAKE) echo $M1_BRAKE;; 1:DIR) echo $M1_DIR;;
    2:SPEED) echo $M2_SPEED;; 2:BRAKE) echo $M2_BRAKE;; 2:DIR) echo $M2_DIR;;
    3:SPEED) echo $M3_SPEED;; 3:BRAKE) echo $M3_BRAKE;; 3:DIR) echo $M3_DIR;;
    *) echo ""; return 1;;
  esac
}

init_all() {
  need_pigpiod
  for m in 1 2 3; do
    s=$(pin_for $m SPEED); b=$(pin_for $m BRAKE); d=$(pin_for $m DIR)
    pigs pfs $s $FREQ; pigs prs $s $RANGE
    pigs pfs $b $FREQ; pigs prs $b $RANGE
    pigs w   $d 0
    pigs p   $s 0
    pigs p   $b $RANGE   # full brake
  done
  echo "Initialized SPEED/BRAKE PWM to ${FREQ}Hz, range ${RANGE}."
}

spin_motor() {
  local m=$1 duty=${2:-128} dir=${3:-1} secs=${4:-0}
  need_pigpiod
  s=$(pin_for $m SPEED); b=$(pin_for $m BRAKE); d=$(pin_for $m DIR)
  pigs pfs $s $FREQ; pigs prs $s $RANGE
  pigs pfs $b $FREQ; pigs prs $b $RANGE
  pigs p $b 0            # release brake
  pigs w $d $dir         # set direction
  pigs p $s $duty        # set speed
  if [[ $secs -gt 0 ]]; then
    sleep $secs
    pigs p $s 0; pigs p $b $RANGE
  fi
}

apply_brake() {
  local m=$1 duty=${2:-255}
  need_pigpiod
  b=$(pin_for $m BRAKE)
  pigs p $b $duty
}

stop_motor() {
  local m=$1
  need_pigpiod
  s=$(pin_for $m SPEED); b=$(pin_for $m BRAKE)
  pigs p $s 0
  pigs p $b $RANGE
}

all_stop() {
  for m in 1 2 3; do stop_motor $m; done
}

status_all() {
  need_pigpiod
  for m in 1 2 3; do
    s=$(pin_for $m SPEED); b=$(pin_for $m BRAKE); d=$(pin_for $m DIR)
    echo "Motor $m"
    echo -n "  SPEED duty="; pigs gdc $s; echo -n "  freq="; pigs pfg $s; echo -n "  range="; pigs prg $s; echo -n "  realrange="; pigs prr $s; echo
    echo -n "  BRAKE duty="; pigs gdc $b; echo -n "  freq="; pigs pfg $b; echo -n "  range="; pigs prg $b; echo -n "  realrange="; pigs prr $b; echo
    echo -n "  DIR level="; pigs r $d; echo
  done
}

cmd=${1:-help}
case "$cmd" in
  init) init_all;;
  spin) # args: motor duty [dir] [secs]
    [[ $# -ge 2 ]] || { echo "Usage: $0 spin <motor 1|2|3> <duty 0..255> [dir 0|1] [secs]"; exit 1; }
    spin_motor "$2" "${3:-128}" "${4:-1}" "${5:-0}";;
  brake)
    [[ $# -ge 2 ]] || { echo "Usage: $0 brake <motor 1|2|3> [duty 0..255]"; exit 1; }
    apply_brake "$2" "${3:-255}";;
  stop)
    [[ $# -ge 2 ]] || { echo "Usage: $0 stop <motor 1|2|3>"; exit 1; }
    stop_motor "$2";;
  allstop) all_stop;;
  status) status_all;;
  *)
    cat <<USAGE
Usage:
  $0 init                        # Setup freq/range and safe defaults
  $0 spin  <motor> <duty> [dir] [secs]
  $0 brake <motor> [duty]
  $0 stop  <motor>
  $0 allstop
  $0 status
USAGE
    ;;
 esac
