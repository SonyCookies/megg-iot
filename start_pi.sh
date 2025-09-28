#!/bin/bash
# start_pi.sh - Raspberry Pi Startup Script for MEGG IoT Backend

echo "🍓 Starting MEGG IoT Backend on Raspberry Pi..."

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This script is designed for Raspberry Pi"
fi

# Set environment variables for Raspberry Pi
export ARDUINO_PORT=${ARDUINO_PORT:-"/dev/ttyUSB0"}
export ARDUINO_BAUDRATE=${ARDUINO_BAUDRATE:-9600}
export IOT_BACKEND_HOST=${IOT_BACKEND_HOST:-"0.0.0.0"}
export IOT_BACKEND_PORT=${IOT_BACKEND_PORT:-8765}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if Arduino is connected
echo "🔌 Checking for Arduino connection..."
if ls /dev/ttyUSB* 1> /dev/null 2>&1 || ls /dev/ttyACM* 1> /dev/null 2>&1; then
    echo "✅ Arduino device detected"
    ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
else
    echo "⚠️  No Arduino device detected - will use simulation mode"
fi

# Set permissions for serial ports (if needed)
if [ -e "/dev/ttyUSB0" ]; then
    echo "🔐 Setting serial port permissions..."
    sudo chmod 666 /dev/ttyUSB* 2>/dev/null || true
fi
if [ -e "/dev/ttyACM0" ]; then
    sudo chmod 666 /dev/ttyACM* 2>/dev/null || true
fi

# Start the IoT backend
echo "🚀 Starting MEGG IoT Backend..."
echo "📡 Server will be available at: http://$IOT_BACKEND_HOST:$IOT_BACKEND_PORT"
echo "🔌 Arduino port: $ARDUINO_PORT"
echo "📊 Baudrate: $ARDUINO_BAUDRATE"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 simple_main.py
