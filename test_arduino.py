#!/usr/bin/env python3
# test_arduino.py - Test Arduino communication

import serial
import serial.tools.list_ports
import time

def test_arduino_connection():
    """Test connection to Arduino"""
    print("🔍 Testing Arduino connection...")
    
    # List available ports
    ports = [str(p) for p in serial.tools.list_ports.comports()]
    print(f"📋 Available ports: {ports}")
    
    # Try to connect to Arduino
    for port in ports:
        try:
            print(f"🔌 Trying port: {port}")
            ser = serial.Serial(port, 115200, timeout=1)
            time.sleep(2)  # Give Arduino time to reset
            
            if ser.is_open:
                print(f"✅ Connected to {port}")
                
                # Test communication
                print("📤 Sending STATUS command...")
                ser.write(b"STATUS\n")
                time.sleep(0.5)
                
                if ser.in_waiting > 0:
                    response = ser.readline().decode().strip()
                    print(f"📥 Arduino response: {response}")
                    
                    # Test calibration command
                    print("📤 Sending CALIBRATE_UNO command...")
                    ser.write(b"CALIBRATE_UNO\n")
                    time.sleep(3)  # Wait for calibration to complete
                    
                    # Read all available responses
                    while ser.in_waiting > 0:
                        response = ser.readline().decode().strip()
                        if response:
                            print(f"📥 Arduino: {response}")
                
                ser.close()
                print("✅ Arduino communication test successful!")
                return True
            else:
                print(f"❌ Failed to open {port}")
                
        except Exception as e:
            print(f"❌ Error with {port}: {e}")
    
    print("❌ No Arduino found on any port")
    return False

if __name__ == "__main__":
    test_arduino_connection()


