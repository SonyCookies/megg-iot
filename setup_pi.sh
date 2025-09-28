#!/bin/bash
# setup_pi.sh - Raspberry Pi Setup Script for MEGG IoT Backend

echo "🚀 Setting up MEGG IoT Backend on Raspberry Pi..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
echo "🐍 Installing Python dependencies..."
sudo apt install python3 python3-pip python3-venv git -y

# Install Python packages
echo "📚 Installing Python packages..."
pip3 install websockets pyserial python-dotenv

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/megg-iot-backend.service > /dev/null <<EOF
[Unit]
Description=MEGG IoT Backend WebSocket Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/MEGG-FINAL/iot-backend
ExecStart=/usr/bin/python3 websocket_server.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/home/pi/MEGG-FINAL/iot-backend

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "🔄 Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable megg-iot-backend.service

# Set permissions
echo "🔐 Setting permissions..."
sudo chmod +x /home/pi/MEGG-FINAL/iot-backend/websocket_server.py

echo "✅ Setup complete!"
echo "🔧 To start the service: sudo systemctl start megg-iot-backend"
echo "📊 To check status: sudo systemctl status megg-iot-backend"
echo "📝 To view logs: sudo journalctl -u megg-iot-backend -f"