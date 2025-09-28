# websocket_server.py - Main WebSocket Server with Modular Structure

import asyncio
import json
import websockets
from typing import Dict, Any
from simple_config import HOST, PORT
from modules import SystemManager

class WebSocketServer:
    def __init__(self):
        self.server = None
        self.running = False
        self.system_manager = SystemManager()
    
    async def start_server(self):
        """Start WebSocket server"""
        try:
            self.server = await websockets.serve(
                self.handle_client,
                HOST,
                PORT
            )
            self.running = True
            self.system_manager.set_server_running(True)
            
            # Initialize Arduino connection
            await self.system_manager.initialize_arduino()
            
            print(f"🌐 MEGG IoT WebSocket Server started on ws://{HOST}:{PORT}")
            print(f"📡 Server running on: ws://localhost:{PORT}")
            print("🚀 Ready for client connections!")
            print("💡 Modular backend with real Arduino calibration support")
            
            return True
        except Exception as e:
            print(f"❌ Failed to start WebSocket server: {e}")
            return False
    
    async def handle_client(self, websocket, path):
        """Handle new WebSocket client connection"""
        self.system_manager.add_client(websocket)
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        
        try:
            # Send welcome message
            await self.system_manager.send_welcome_message(websocket)
            
            # Send current system status
            await self.system_manager.send_system_status(websocket)
            
            # Keep connection alive and handle messages
            async for message in websocket:
                await self.handle_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 Client disconnected: {client_ip}")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
        finally:
            self.system_manager.remove_client(websocket)
    
    async def handle_message(self, websocket, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            print(f"📨 Received: {message_type} from client")
            
            if message_type == "ping":
                await self.system_manager.send_to_client(websocket, {
                    "type": "pong",
                    "timestamp": self.system_manager._serialize_message({"timestamp": "now"})
                })
                
            elif message_type == "calibration_request":
                await self.system_manager.handle_calibration_request(websocket, data)
                
            elif message_type == "work_process":
                await self.system_manager.handle_work_process_request(websocket, data)
                
            elif message_type == "get_status":
                await self.system_manager.send_system_status(websocket)
                
            else:
                await self.system_manager.send_to_client(websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": self.system_manager._serialize_message({"timestamp": "now"})
                })
                
        except json.JSONDecodeError:
            await self.system_manager.send_to_client(websocket, {
                "type": "error",
                "message": "Invalid JSON format",
                "timestamp": self.system_manager._serialize_message({"timestamp": "now"})
            })
        except Exception as e:
            print(f"❌ Error handling message: {e}")
            await self.system_manager.send_to_client(websocket, {
                "type": "error",
                "message": f"Server error: {str(e)}",
                "timestamp": self.system_manager._serialize_message({"timestamp": "now"})
            })
    
    async def stop_server(self):
        """Stop WebSocket server"""
        self.running = False
        self.system_manager.set_server_running(False)
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        print("🔌 WebSocket server stopped")

# Global WebSocket server instance
websocket_server = WebSocketServer()