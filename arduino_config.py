# arduino_config.py - Arduino Configuration Settings

import os
import platform
import glob
from typing import List

def detect_platform() -> str:
    """Detect the current platform"""
    system = platform.system().lower()
    if system == 'linux':
        # Check if running on Raspberry Pi
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                if 'raspberry pi' in cpuinfo or 'bcm' in cpuinfo:
                    return 'raspberry_pi'
        except:
            pass
        return 'linux'
    return system

PLATFORM = detect_platform()

# Arduino connection settings
if PLATFORM == 'raspberry_pi':
    ARDUINO_PORT = os.getenv('ARDUINO_PORT', '/dev/ttyUSB0')  # Default for Pi
elif PLATFORM == 'linux':
    ARDUINO_PORT = os.getenv('ARDUINO_PORT', '/dev/ttyUSB0')  # Default for Linux
elif PLATFORM == 'darwin':  # macOS
    ARDUINO_PORT = os.getenv('ARDUINO_PORT', '/dev/cu.usbserial-0001')
else:  # Windows
    ARDUINO_PORT = os.getenv('ARDUINO_PORT', 'COM3')

ARDUINO_BAUDRATE = int(os.getenv('ARDUINO_BAUDRATE', '9600'))
ARDUINO_TIMEOUT = float(os.getenv('ARDUINO_TIMEOUT', '1.0'))

# Platform-specific fallback ports
if PLATFORM == 'raspberry_pi':
    ARDUINO_FALLBACK_PORTS = [
        '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2',
        '/dev/serial/by-id/*', '/dev/serial/by-path/*'
    ]
elif PLATFORM == 'linux':
    ARDUINO_FALLBACK_PORTS = [
        '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2'
    ]
elif PLATFORM == 'darwin':  # macOS
    ARDUINO_FALLBACK_PORTS = [
        '/dev/cu.usbserial-*', '/dev/cu.usbmodem*',
        '/dev/cu.usbserial-0001', '/dev/cu.usbserial-0002'
    ]
else:  # Windows
    ARDUINO_FALLBACK_PORTS = [
        'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'COM10'
    ]

# Arduino command timeout (seconds)
COMMAND_TIMEOUT = 5.0

# Serial communication settings
SERIAL_READ_TIMEOUT = 1.0
SERIAL_WRITE_TIMEOUT = 1.0

def get_available_serial_ports() -> List[str]:
    """Get list of available serial ports for the current platform"""
    ports = []
    
    if PLATFORM == 'raspberry_pi' or PLATFORM == 'linux':
        # Check standard Linux serial ports
        for pattern in ['/dev/ttyUSB*', '/dev/ttyACM*']:
            ports.extend(glob.glob(pattern))
        
        # Check symlinked serial ports (more reliable)
        try:
            for pattern in ['/dev/serial/by-id/*', '/dev/serial/by-path/*']:
                ports.extend(glob.glob(pattern))
        except:
            pass
            
    elif PLATFORM == 'darwin':  # macOS
        for pattern in ['/dev/cu.usbserial*', '/dev/cu.usbmodem*']:
            ports.extend(glob.glob(pattern))
            
    elif PLATFORM == 'windows':
        import serial.tools.list_ports
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]
        except:
            ports = ['COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8']
    
    return sorted(ports)

def get_arduino_config() -> dict:
    """Get Arduino configuration"""
    available_ports = get_available_serial_ports()
    
    return {
        'platform': PLATFORM,
        'port': ARDUINO_PORT,
        'baudrate': ARDUINO_BAUDRATE,
        'timeout': ARDUINO_TIMEOUT,
        'fallback_ports': ARDUINO_FALLBACK_PORTS,
        'available_ports': available_ports,
        'command_timeout': COMMAND_TIMEOUT,
        'serial_read_timeout': SERIAL_READ_TIMEOUT,
        'serial_write_timeout': SERIAL_WRITE_TIMEOUT
    }
