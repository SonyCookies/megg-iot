# working_server.py - Simple Working WebSocket Server

import asyncio
import json
import websockets
import os
from simple_config import HOST, PORT

async def handle_client(websocket, path):
    """Handle WebSocket client connections"""
    print(f"🔌 New client connected: {websocket.remote_address}")
    
    try:
        # Send welcome message
        await websocket.send(json.dumps({
            "type": "connection",
            "message": "Connected to MEGG IoT Backend",
            "timestamp": asyncio.get_event_loop().time()
        }))
        
        # Send system status
        await websocket.send(json.dumps({
            "type": "system_status",
            "arduino": {
                "connected": False,
                "port": "simulation",
                "baudrate": 115200,
                "running": False,
                "timestamp": asyncio.get_event_loop().time()
            },
            "server": {
                "connected_clients": 1,
                "running": True,
                "uptime": "0s"
            },
            "timestamp": asyncio.get_event_loop().time()
        }))
        
        # Handle incoming messages
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")
                
                print(f"📨 Received: {message_type}")
                
                if message_type == "ping":
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time()
                    }))
                    
                elif message_type == "calibration_request":
                    component = data.get("component", "UNO")
                    
                    # Send calibration started
                    await websocket.send(json.dumps({
                        "type": "calibration_result",
                        "component": component,
                        "status": "started",
                        "success": True,
                        "message": f"{component}: Starting calibration...",
                        "timestamp": asyncio.get_event_loop().time()
                    }))
                    
                    # Simulate calibration delay
                    await asyncio.sleep(2)
                    
                    # Send calibration completed
                    await websocket.send(json.dumps({
                        "type": "calibration_result",
                        "component": component,
                        "status": "completed",
                        "success": True,
                        "message": f"{component}: Calibration completed successfully",
                        "timestamp": asyncio.get_event_loop().time()
                    }))
                    
                elif message_type == "get_status":
                    await websocket.send(json.dumps({
                        "type": "system_status",
                        "arduino": {
                            "connected": False,
                            "port": "simulation",
                            "baudrate": 115200,
                            "running": False,
                            "timestamp": asyncio.get_event_loop().time()
                        },
                        "server": {
                            "connected_clients": 1,
                            "running": True,
                            "uptime": "0s"
                        },
                        "timestamp": asyncio.get_event_loop().time()
                    }))
                    
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
                print(f"❌ Error handling message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        print(f"🔌 Client disconnected: {websocket.remote_address}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")

async def main():
    """Main function"""
    print("🚀 Starting MEGG IoT Backend (Simple WebSocket Server)...")
    print("=" * 60)
    
    # Get host and port
    host = os.getenv("HOST", HOST)
    port = int(os.getenv("PORT", PORT))
    
    try:
        # Start WebSocket server
        server = await websockets.serve(handle_client, host, port)
        
        print(f"🌐 MEGG IoT WebSocket Server started on ws://{host}:{port}")
        print(f"📡 Server running on: ws://localhost:{port}")
        print("🚀 Ready for client connections!")
        print("💡 Simple WebSocket backend with simulation support")
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
        await server.wait_closed()
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

if __name__ == "__main__":
    asyncio.run(main())
