#iot-backend/simplle_iot_server.py


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
            # Extend timeouts for long-running flows
            if command.startswith("START"):
                max_timeout = 1200  # ~120s for full cycle
            elif command.strip() == "STOP":
                max_timeout = 300   # ~30s to ensure we read STOP_ACK
            elif "CALIBRATE" in command:
                max_timeout = 150   # ~15s
            else:
                max_timeout = 60    # ~6s for other commands
            
            last_weight = None
            while timeout < max_timeout:
                if self.arduino.in_waiting > 0:
                    line = self.arduino.readline().decode().strip()
                    if line:
                        response_lines.append(line)
                        print(f"📨 Arduino: {line}")

                        # Stream sorting progress to clients for visibility during START
                        if command.startswith("START"):
                            await self.broadcast_to_clients({
                                "type": "sorting_progress",
                                "message": line,
                                "timestamp": datetime.now().isoformat(),
                            })

                            # Parse measurement and classification to emit egg_processed
                            try:
                                if line.startswith("HX711: Weight measured:"):
                                    # e.g., "HX711: Weight measured: 47.12 g"
                                    parts = line.split(":")[-1].strip().split(" ")
                                    if parts:
                                        last_weight = float(parts[0])
                                elif "classified as" in line and line.startswith("SORT: Egg ("):
                                    # e.g., "SORT: Egg (47.12g) classified as MEDIUM"
                                    size = line.split("classified as")[-1].strip()
                                    payload = {
                                        "type": "egg_processed",
                                        "weight": last_weight,
                                        "size": size,
                                        "accountId": (self.current_configuration or {}).get("accountId"),
                                        "batchId": (self.current_configuration or {}).get("batchId") or ((self.current_configuration or {}).get("currentBatch") or {}).get("id"),
                                        "timestamp": datetime.now().isoformat(),
                                    }
                                    await self.broadcast_to_clients(payload)
                            except Exception as _:
                                pass

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
                        # End markers for long-running flows
                        if command.strip() == "STOP" and ("STOP_ACK" in line or "SYSTEM_STOPPED" in line):
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

    async def start_sorting_process(self):
        """Start the physical sorting process by sending START (with ranges if present) in background."""
        # Preconditions
        if not self.arduino:
            return {"success": False, "error": "Arduino not connected"}
        cfg = getattr(self, 'current_configuration', None)
        if not cfg or not isinstance(cfg, dict) or not cfg.get('configurations'):
            return {"success": False, "error": "No configuration provided"}

        # Build START command with ranges if possible
        cmd = "START"
        try:
            ranges = cfg['configurations'].get('eggSizeRanges') or cfg['configurations'].get('egg_ranges')
            if ranges:
                s_min = float(ranges['small']['min'])
                s_max = float(ranges['small']['max'])
                m_min = float(ranges['medium']['min'])
                m_max = float(ranges['medium']['max'])
                l_min = float(ranges['large']['min'])
                l_max = float(ranges['large']['max'])
                cmd = f"START {s_min} {s_max} {m_min} {m_max} {l_min} {l_max}"
        except Exception as e:
            # If parsing fails, fallback to plain START and proceed
            print(f"⚠️ Failed to build ranges for START: {e}. Falling back to 'START'.")

        # Send a unique marker to Arduino logs for clarity, then run long-running command in background
        try:
            self.arduino.write(b"CMD:START_SORTING\n")
            self.arduino.flush()
        except Exception as e:
            print(f"⚠️ Failed to write START marker to Arduino: {e}")

        # Run long-running command in background and immediately acknowledge
        asyncio.create_task(
            self._execute_long_running_command_and_broadcast_result(cmd, "sorting_result")
        )
        return {
            "success": True,
            "message": "Sorting process initiated. Waiting for hardware completion signal."
        }

    async def stop_sorting_process(self):
        """Send STOP to hardware in background and return immediate ack."""
        if not self.arduino:
            return {"success": False, "error": "Arduino not connected"}

        # Send a unique marker to Arduino logs for clarity, then run STOP in background
        try:
            self.arduino.write(b"CMD:STOP_SORTING\n")
            self.arduino.flush()
        except Exception as e:
            print(f"⚠️ Failed to write STOP marker to Arduino: {e}")

        # Run STOP in background
        asyncio.create_task(
            self._execute_long_running_command_and_broadcast_result("STOP", "sorting_stop_result")
        )
        return {
            "success": True,
            "message": "Stop request sent to hardware."
        }
    
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

    async def _execute_long_running_command_and_broadcast_result(self, command: str, result_type: str):
        """Execute a long-running Arduino command and broadcast the final result to all clients."""
        try:
            result = await self.send_arduino_command(command)
            payload = {
                "type": result_type,
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "error": result.get("error")
            }
        except Exception as e:
            payload = {
                "type": result_type,
                "success": False,
                "error": str(e)
            }
        await self.broadcast_to_clients(payload)
    
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

                    elif data.get("type") == "set_configuration":
                        # Accept and store user configuration (egg size ranges, metadata)
                        cfg = data.get("configurations")
                        account_id = data.get("accountId") or data.get("account_id")
                        metadata = data.get("metadata") or {}
                        uid = data.get("uid")
                        if not account_id or not cfg:
                            await websocket.send(json.dumps({
                                "type": "configuration_result",
                                "success": False,
                                "error": "Missing accountId or configurations"
                            }))
                        else:
                            # Store configuration in memory for the session
                            self.current_configuration = {
                                "accountId": str(account_id),
                                "configurations": cfg,
                                "metadata": metadata,
                                "uid": uid,
                                "receivedAt": datetime.now().isoformat()
                            }
                            print(f"✅ Configuration stored for {account_id}: {self.current_configuration}")
                            await websocket.send(json.dumps({
                                "type": "configuration_result",
                                "success": True,
                                "accountId": account_id
                            }))

                    elif data.get("type") == "send_command":
                        # Forward a raw command string to Arduino and return response
                        cmd = str(data.get("command", "")).strip()
                        if not cmd:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Missing 'command' field for send_command"
                            }))
                        elif not self.arduino:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Arduino not connected"
                            }))
                        else:
                            result = await self.send_arduino_command(cmd)
                            # Echo back a structured result
                            await websocket.send(json.dumps({
                                "type": "command_result",
                                "command": cmd,
                                **result
                            }))

                    elif data.get("type") == "start_sorting":
                        # Start sorting using current configuration (if available)
                        res = await self.start_sorting_process()
                        await websocket.send(json.dumps({
                            "type": "sorting_result",
                            **res
                        }))

                    elif data.get("type") == "stop_sorting":
                        # Stop sorting (non-blocking)
                        res = await self.stop_sorting_process()
                        await websocket.send(json.dumps({
                            "type": "sorting_stop_result",
                            **res
                        }))

                    elif data.get("command") in ("start_sorting", "stop_sorting"):
                        # Support structured client command payloads
                        cmd = data.get("command")
                        if cmd == "start_sorting":
                            res = await self.start_sorting_process()
                            await websocket.send(json.dumps({
                                "type": "sorting_result",
                                **res
                            }))
                        elif cmd == "stop_sorting":
                            res = await self.stop_sorting_process()
                            await websocket.send(json.dumps({
                                "type": "sorting_stop_result",
                                **res
                            }))
                    
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
            print("🔧 Available commands: calibration_request, get_status, get_weight, set_configuration, send_command, start_sorting, stop_sorting, client_command(start_sorting|stop_sorting)")
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
