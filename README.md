# MEGG IoT Backend - Modular WebSocket Server

A structured WebSocket server for MEGG hardware calibration and work process simulation.

## Features

### 🔧 **Calibration Module**
- **Real Arduino Integration**: Direct serial communication with Arduino hardware
- **Hardware Calibration**: Actual calibration of UNO, HX711, NEMA23, SG90, MG996R components
- **Fallback Simulation**: Automatic fallback to simulation if Arduino not connected
- **Multi-Port Support**: Tries multiple COM ports automatically
- **Component-Specific Messages**: Detailed, realistic calibration messages
- **Progressive Updates**: Start → Progress → Complete/Failed messages

### ⚙️ **Work Process Module**
- **Complete Workflow Simulation**: Getting Ready → Load Eggs → Processing → Completion
- **Batch Processing**: Start/stop/reset processing batches
- **Real-time Statistics**: Track processed eggs, quality, and size categories
- **Component Integration**: Work process requires all components to be calibrated

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python simple_main.py
```

## API Commands

### Calibration
- `calibration_request`: Start component calibration (real Arduino or simulation)

### Work Process
- `work_process`: Manage work processes
  - `start_batch`: Start new processing batch
  - `stop_processing`: Stop current processing
  - `reset_process`: Reset process to idle
  - `get_status`: Get process status

### System
- `get_status`: Get comprehensive system status
- `ping/pong`: Health check

## Supported Components

- **UNO**: Arduino UNO microcontroller
- **HX711**: Load cell weight sensor
- **NEMA23**: Stepper motor
- **SG90**: Servo motor (loading)
- **MG996R**: Servo motor (gripping)

## Configuration

Edit `simple_config.py` to change host/port settings.

## WebSocket URL

`ws://localhost:8765`

## Project Structure

```
iot-backend/
├── modules/                    # Modular components
│   ├── calibration.py         # Hardware calibration simulation
│   ├── work_process.py        # Work process management
│   ├── system_manager.py      # System coordination
│   ├── arduino_service.py     # Arduino serial communication
│   └── __init__.py           # Module exports
├── websocket_server.py        # Main WebSocket server
├── simple_main.py            # Application entry point
├── simple_config.py          # Configuration
├── arduino_config.py         # Cross-platform Arduino settings
├── requirements.txt          # Dependencies
├── start_pi.sh              # Raspberry Pi startup script
├── setup_pi.sh              # Raspberry Pi setup script
├── megg-iot-backend.service # Systemd service file
└── pi_config.env            # Pi-specific configuration
```

## Arduino Setup

1. **Upload the Arduino code** to your Arduino UNO:
   ```bash
   # Use PlatformIO or Arduino IDE to upload the code from:
   # C:\Users\sonny\Documents\PlatformIO\Projects\megg-arduino-control\src\main.cpp
   ```

2. **Connect Arduino** to your computer via USB

3. **Configure port** (optional):
   ```bash
   # Windows
   set ARDUINO_PORT=COM4
   
   # Linux/Raspberry Pi
   export ARDUINO_PORT=/dev/ttyUSB0
   
   # macOS
   export ARDUINO_PORT=/dev/cu.usbserial-0001
   ```

## Raspberry Pi Setup

### Quick Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd iot-backend

# Run the automated setup
chmod +x setup_pi.sh
./setup_pi.sh

# Reboot to apply group changes
sudo reboot

# After reboot, start the service
sudo systemctl start megg-iot-backend
```

### Manual Setup
```bash
# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-serial

# Add user to dialout group
sudo usermod -a -G dialout $USER

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Run the backend
./start_pi.sh
```

### Service Management
```bash
# Start service
sudo systemctl start megg-iot-backend

# Stop service
sudo systemctl stop megg-iot-backend

# Check status
sudo systemctl status megg-iot-backend

# View logs
sudo journalctl -u megg-iot-backend -f
```

## Usage

The server automatically:
- **Connects to Arduino** via serial communication
- **Falls back to simulation** if Arduino not available
- **Provides real calibration** with detailed progress messages
- **Manages work processes** for complete egg processing workflows
- **Broadcasts real-time updates** and comprehensive system status