# fixed_simple_main.py - Fixed WebSocket IoT Backend

import asyncio
import signal
import sys
import websockets
import os
from simple_config import HOST, PORT
from modules import SystemManager

class FixedMEGGIoTBackend:
    def __init__(self):
        self.running = False
        self.system_manager = SystemManager()
        self.websocket_clients = set()
        
    async def handle_client(self, websocket, path):
        """Handle new WebSocket client connection"""
        self.websocket_clients.add(websocket)
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        
        try:
            # Send welcome message
            await self.send_welcome_message(websocket)
            
            # Send current system status
            await self.send_system_status(websocket)
            
            # Handle messages
            async for message in websocket:
                await self.handle_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 Client disconnected: {client_ip}")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
        finally:
            self.websocket_clients.discard(websocket)
    
    async def send_welcome_message(self, websocket):
        """Send welcome message to client"""
        await websocket.send(json.dumps({
            "type": "connection",
            "message": "Connected to MEGG IoT Backend",
            "timestamp": asyncio.get_event_loop().time()
        }))
    
    async def send_system_status(self, websocket):
        """Send system status to client"""
        status = {
            "type": "system_status",
            "arduino": {
                "connected": False,
                "port": "simulation",
                "baudrate": 115200,
                "running": False,
                "timestamp": asyncio.get_event_loop().time()
            },
            "server": {
                "connected_clients": len(self.websocket_clients),
                "running": True,
                "uptime": "0s"
            },
            "timestamp": asyncio.get_event_loop().time()
        }
        await websocket.send(json.dumps(status))
    
    async def handle_message(self, websocket, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            print(f"📨 Received: {message_type} from client")
            
            if message_type == "ping":
                await websocket.send(json.dumps({
                    "type": "pong",
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
            elif message_type == "calibration_request":
                await self.handle_calibration_request(websocket, data)
                
            elif message_type == "get_status":
                await self.send_system_status(websocket)
                
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON format",
                "timestamp": asyncio.get_event_loop().time()
            }))
        except Exception as e:
            print(f"Error handling message: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Server error: {str(e)}",
                "timestamp": asyncio.get_event_loop().time()
            }))
    
    async def handle_calibration_request(self, websocket, data):
        """Handle calibration requests"""
        component = data.get("component", "UNO")
        
        # Send calibration started response
        await websocket.send(json.dumps({
            "type": "calibration_result",
            "component": component,
            "status": "started",
            "success": True,
            "message": f"{component}: Starting calibration...",
            "timestamp": asyncio.get_event_loop().time()
        }))
        
        # Simulate calibration process
        await asyncio.sleep(2)
        
        # Send calibration completed response
        await websocket.send(json.dumps({
            "type": "calibration_result",
            "component": component,
            "status": "completed",
            "success": True,
            "message": f"{component}: Calibration completed successfully",
            "timestamp": asyncio.get_event_loop().time()
        }))
        
    async def start(self):
        """Start the fixed IoT backend server"""
        print("🚀 Starting MEGG IoT Backend (Fixed WebSocket API)...")
        print("=" * 60)
        
        try:
            # Get host and port
            host = os.getenv("HOST", HOST)
            port = int(os.getenv("PORT", PORT))
            
            # Start WebSocket server
            self.server = await websockets.serve(
                self.handle_client,
                host,
                port
            )
            self.running = True
            
            print(f"🌐 MEGG IoT WebSocket Server started on ws://{host}:{port}")
            print(f"📡 Server running on: ws://localhost:{port}")
            print("🚀 Ready for client connections!")
            print("💡 Fixed WebSocket backend with simulation support")
            
            return True
        except Exception as e:
            print(f"❌ Failed to start WebSocket server: {e}")
            return False

# Global backend instance
backend = FixedMEGGIoTBackend()

async def main():
    """Main function"""
    try:
        success = await backend.start()
        if not success:
            print("❌ Failed to start backend")
            return
        
        print("✅ MEGG IoT Backend started successfully!")
        print("=" * 60)
        print("💡 Available API Commands:")
        print("   - calibration_request: Start component calibration")
        print("   - get_status: Get system status")
        print("   - ping/pong: Health check")
        print("=" * 60)
        print("🔧 Supported Components: UNO, HX711, NEMA23, SG90, MG996R")
        print("=" * 60)
        print("Press Ctrl+C to stop the server")
        
        # Keep the server running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            print("\n🛑 Shutting down server...")
            
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

if __name__ == "__main__":
    asyncio.run(main())
