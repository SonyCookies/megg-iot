#!/usr/bin/env python3
"""
MEGG IoT Backend - Simple Real Hardware Server
Connects to Arduino and handles calibration commands
"""

import asyncio
import websockets
import serial
import json
import os
import platform
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MEGGIoTServer:
    def __init__(self):
        self.arduino = None
        self.connected_clients = set()
        
        # Auto-detect ports based on operating system
        if platform.system() == "Windows":
            # Windows COM ports
            self.arduino_ports = [f"COM{i}" for i in range(1, 21)]  # COM1 to COM20
        else:
            # Linux/Mac ports
            self.arduino_ports = [
                '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
                '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2'
            ]
        
    def list_available_ports(self):
        """List all available serial ports"""
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        available_ports = []
        for port in ports:
            available_ports.append(port.device)
        return available_ports
    
    async def connect_arduino(self):
        """Connect to Arduino on available port"""
        # First, try to find Arduino by listing available ports
        available_ports = self.list_available_ports()
        print(f"🔍 Available ports: {available_ports}")
        
        # Try available ports first, then fallback to common ports (avoid duplicates)
        ports_to_try = list(dict.fromkeys(available_ports + self.arduino_ports))
        
        for port in ports_to_try:
            try:
                print(f"🔌 Trying to connect to Arduino on {port}...")
                self.arduino = serial.Serial(port, 115200, timeout=1)
                await asyncio.sleep(2)  # Wait for Arduino to initialize
                
                # Test connection
                self.arduino.write(b"STATUS\n")
                await asyncio.sleep(1)
                
                if self.arduino.in_waiting > 0:
                    response = self.arduino.readline().decode().strip()
                    print(f"✅ Arduino connected on {port}: {response}")
                    return True
                    
            except Exception as e:
                print(f"❌ Failed to connect on {port}: {e}")
                if self.arduino:
                    self.arduino.close()
                    self.arduino = None
                    
        print("❌ No Arduino found on any port")
        return False
    
    async def send_arduino_command(self, command):
        """Send command to Arduino and get response"""
        if not self.arduino:
            return {"success": False, "error": "Arduino not connected"}
            
        try:
            # Send command
            self.arduino.write(f"{command}\n".encode())
            await asyncio.sleep(0.5)
            
            # Read response
            response_lines = []
            timeout = 0
            while timeout < 50:  # 5 second timeout
                if self.arduino.in_waiting > 0:
                    line = self.arduino.readline().decode().strip()
                    if line:
                        response_lines.append(line)
                        print(f"📨 Arduino: {line}")
                        
                        # Check for completion
                        if "CALIBRATION_COMPLETE" in line:
                            break
                        if "ERROR" in line:
                            break
                else:
                    await asyncio.sleep(0.1)
                    timeout += 1
            
            return {
                "success": True,
                "response": response_lines,
                "message": response_lines[-1] if response_lines else "No response"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def handle_calibration(self, component):
        """Handle calibration request"""
        print(f"🔧 Starting {component} calibration...")
        
        # Send calibration command to Arduino
        command = f"CALIBRATE_{component}"
        result = await self.send_arduino_command(command)
        
        if result["success"]:
            # Parse Arduino response
            response_lines = result["response"]
            success = any("CALIBRATION_COMPLETE" in line for line in response_lines)
            error = any("ERROR" in line for line in response_lines)
            
            if success:
                message = next((line for line in response_lines if component in line), f"{component} calibration completed")
                status = "completed"
            elif error:
                message = next((line for line in response_lines if "ERROR" in line), f"{component} calibration failed")
                status = "failed"
            else:
                message = f"{component} calibration completed"
                status = "completed"
        else:
            message = f"{component} calibration failed: {result['error']}"
            status = "failed"
            success = False
        
        # Send result to all connected clients
        calibration_result = {
            "type": "calibration_result",
            "component": component,
            "status": status,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.broadcast_to_clients(calibration_result)
        return calibration_result
    
    async def broadcast_to_clients(self, message):
        """Send message to all connected WebSocket clients"""
        if self.connected_clients:
            message_str = json.dumps(message)
            disconnected = set()
            
            for client in self.connected_clients:
                try:
                    await client.send(message_str)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
            
            # Remove disconnected clients
            self.connected_clients -= disconnected
    
    async def handle_client(self, websocket, path):
        """Handle WebSocket client connection"""
        print(f"🔌 New client connected: {websocket.remote_address}")
        self.connected_clients.add(websocket)
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    print(f"📨 Received: {data}")
                    
                    if data.get("type") == "calibration_request":
                        component = data.get("component", "").upper()
                        if component in ["UNO", "HX711", "NEMA23", "SG90", "MG996R"]:
                            await self.handle_calibration(component)
                        else:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": f"Unknown component: {component}"
                            }))
                    
                    elif data.get("type") == "get_status":
                        status = {
                            "type": "system_status",
                            "server": {"status": "running"},
                            "arduino": {"connected": self.arduino is not None},
                            "components": {
                                "UNO": {"status": "unknown"},
                                "HX711": {"status": "unknown"},
                                "NEMA23": {"status": "unknown"},
                                "SG90": {"status": "unknown"},
                                "MG996R": {"status": "unknown"}
                            }
                        }
                        await websocket.send(json.dumps(status))
                    
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON"
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 Client disconnected: {websocket.remote_address}")
        finally:
            self.connected_clients.discard(websocket)
    
    async def start_server(self):
        """Start the WebSocket server"""
        print("🚀 Starting MEGG IoT Backend...")
        
        # Try to connect to Arduino
        arduino_connected = await self.connect_arduino()
        if not arduino_connected:
            print("⚠️ Running without Arduino - calibrations will fail")
        
        # Start WebSocket server
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', '8765'))
        
        print(f"🌐 Starting WebSocket server on {host}:{port}")
        
        async with websockets.serve(self.handle_client, host, port):
            print(f"✅ MEGG IoT Backend running on ws://{host}:{port}")
            print("🔧 Available commands: calibration_request, get_status")
            print("📱 Ready for client connections!")
            
            # Keep server running
            await asyncio.Future()

def main():
    """Main entry point"""
    server = MEGGIoTServer()
    
    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down MEGG IoT Backend...")
    except Exception as e:
        print(f"❌ Server error: {e}")

if __name__ == "__main__":
    main()
