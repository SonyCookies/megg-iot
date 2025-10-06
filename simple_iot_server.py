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
from modules.calibration import CalibrationRouter

# Load environment variables
load_dotenv()

class MEGGIoTServer:
    def __init__(self):
        self.arduino = None
        self.connected_clients = set()
        self.calibration_router: CalibrationRouter | None = None
        
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
                self.arduino = serial.Serial(
                    port=port,
                    baudrate=115200,
                    timeout=1,
                    write_timeout=1,
                    dsrdtr=False,  # Disable DTR to prevent auto-reset
                    rtscts=False   # Disable RTS/CTS
                )
                await asyncio.sleep(2)  # Wait for Arduino to initialize
                
                # Clear any startup data in buffers
                self.arduino.reset_input_buffer()
                self.arduino.reset_output_buffer()
                
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
            # Clear any pending data in buffer BEFORE sending command
            self.arduino.reset_input_buffer()
            self.arduino.reset_output_buffer()
            await asyncio.sleep(0.2)  # Increased delay after clearing buffers
            
            # Send command
            print(f"🔧 Sending command: {command}")
            self.arduino.write(f"{command}\n".encode())
            self.arduino.flush()  # Ensure command is sent immediately
            await asyncio.sleep(0.5)  # Increased wait for Arduino to process
            
            # Read response
            response_lines = []
            timeout = 0
            max_timeout = 150 if "CALIBRATE" in command else 30  # 15s for calibration, 3s for status
            
            while timeout < max_timeout:
                if self.arduino.in_waiting > 0:
                    line = self.arduino.readline().decode().strip()
                    if line:
                        response_lines.append(line)
                        print(f"📨 Arduino: {line}")

                        # Stream calibration progress to clients in real-time
                        if command.startswith("CALIBRATE_"):
                            # Component name is after CALIBRATE_
                            comp = command.split()[0].replace("CALIBRATE_", "")
                            payload = {
                                "type": "calibration_progress",
                                "component": comp,
                                "message": line,
                                "timestamp": datetime.now().isoformat(),
                            }
                            await self.broadcast_to_clients(payload)
                        
                        # For STATUS command, stop after seeing the closing line
                        if command == "STATUS" and "===================" in line and len(response_lines) > 5:
                            break
                        
                        # Check for completion
                        if "CALIBRATION_COMPLETE" in line:
                            break
                        if "ERROR" in line:
                            break
                else:
                    await asyncio.sleep(0.1)
                    timeout += 1
                    
                    # For STATUS, if we have data and no more coming, break
                    if command == "STATUS" and len(response_lines) > 5 and timeout > 5:
                        break
            
            return {
                "success": True,
                "response": response_lines,
                "message": response_lines[-1] if response_lines else "No response"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_weight_reading(self):
        """Get current weight reading from HX711 sensor"""
        print("🔍 get_weight_reading() called")
        if not self.arduino:
            print("❌ Arduino not connected")
            return {
                "type": "weightReading",
                "success": False,
                "error": "Arduino not connected"
            }
        
        try:
            # Send STATUS command to get weight reading
            result = await self.send_arduino_command("STATUS")
            print(f"🔍 STATUS result: success={result.get('success')}")
            
            if result.get("success"):
                response_lines = result.get("response", [])
                print(f"🔍 Response lines: {response_lines}")
                
                # Check if HX711 is calibrated
                is_calibrated = any("HX711 Calibrated: YES" in line for line in response_lines)
                print(f"🔍 HX711 calibrated: {is_calibrated}")
                
                if not is_calibrated:
                    return {
                        "type": "weightReading",
                        "success": False,
                        "error": "HX711 not calibrated"
                    }
                
                # Parse weight from response
                for line in response_lines:
                    if "HX711 Reading:" in line:
                        print(f"🔍 Found weight line: {line}")
                        # Extract weight value (format: "HX711 Reading: 23.45 g")
                        parts = line.split(":")
                        if len(parts) >= 2:
                            weight_str = parts[1].strip().replace("g", "").strip()
                            print(f"🔍 Parsed weight string: '{weight_str}'")
                            try:
                                weight = float(weight_str)
                                print(f"✅ Successfully parsed weight: {weight}")
                                return {
                                    "type": "weightReading",
                                    "success": True,
                                    "weight": weight,
                                    "unit": "g",
                                    "timestamp": datetime.now().isoformat()
                                }
                            except ValueError as e:
                                print(f"❌ ValueError parsing weight: {e}")
                                pass
                
                # If we couldn't parse weight, return error
                print("❌ Could not parse weight from response")
                return {
                    "type": "weightReading",
                    "success": False,
                    "error": "Could not parse weight from Arduino response"
                }
            else:
                print(f"❌ STATUS command failed: {result.get('error')}")
                return {
                    "type": "weightReading",
                    "success": False,
                    "error": result.get("error", "Failed to get weight")
                }
        except Exception as e:
            print(f"❌ Exception in get_weight_reading: {e}")
            return {
                "type": "weightReading",
                "success": False,
                "error": str(e)
            }
    
    async def handle_calibration(self, component, weight=None):
        """Handle calibration request via router"""
        if self.calibration_router is None:
            self.calibration_router = CalibrationRouter(self.send_arduino_command)
        result = await self.calibration_router.calibrate_component(component, weight)
        # Broadcast in standard envelope
        payload = {
            "type": "calibration_result",
            **result,
        }
        await self.broadcast_to_clients(payload)
        return payload
    
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
    
    async def handle_client(self, websocket):
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
                        weight = data.get("weight")  # Optional weight parameter for HX711
                        if component in ["UNO", "HX711", "NEMA23", "SG90", "MG996R"]:
                            await self.handle_calibration(component, weight)
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
                    
                    elif data.get("type") == "get_weight":
                        # Get current weight reading from HX711
                        weight_result = await self.get_weight_reading()
                        print(f"📤 Sending weight result: {weight_result}")
                        await websocket.send(json.dumps(weight_result))
                    
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
