# render_server.py - Hybrid HTTP/WebSocket Server for Render

import asyncio
import json
import os
import websockets
from aiohttp import web
from aiohttp.web import Request, Response
from simple_config import HOST, PORT
from modules import SystemManager

class RenderWebSocketServer:
    def __init__(self):
        self.app = web.Application()
        self.system_manager = SystemManager()
        self.websocket_clients = set()
        
    async def health_check(self, request: Request) -> Response:
        """Health check endpoint for Render"""
        return Response(
            text=json.dumps({
                "status": "healthy",
                "service": "MEGG IoT Backend",
                "websocket_clients": len(self.websocket_clients)
            }),
            content_type="application/json"
        )
    
    async def websocket_handler(self, request: Request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Add client to set
        self.websocket_clients.add(ws)
        
        try:
            # Send welcome message
            await self.send_welcome_message(ws)
            
            # Send current system status
            await self.send_system_status(ws)
            
            # Handle messages
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    await self.handle_websocket_message(ws, msg.data)
                elif msg.type == web.WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
                    break
                    
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            # Remove client from set
            self.websocket_clients.discard(ws)
            
        return ws
    
    async def send_welcome_message(self, ws):
        """Send welcome message to client"""
        await ws.send_str(json.dumps({
            "type": "connection",
            "message": "Connected to MEGG IoT Backend",
            "timestamp": asyncio.get_event_loop().time()
        }))
    
    async def send_system_status(self, ws):
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
        await ws.send_str(json.dumps(status))
    
    async def handle_websocket_message(self, ws, message: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            print(f"📨 Received: {message_type} from client")
            
            if message_type == "ping":
                await ws.send_str(json.dumps({
                    "type": "pong",
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
            elif message_type == "calibration_request":
                await self.handle_calibration_request(ws, data)
                
            elif message_type == "get_status":
                await self.send_system_status(ws)
                
            else:
                await ws.send_str(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
        except json.JSONDecodeError:
            await ws.send_str(json.dumps({
                "type": "error",
                "message": "Invalid JSON format",
                "timestamp": asyncio.get_event_loop().time()
            }))
        except Exception as e:
            print(f"Error handling message: {e}")
            await ws.send_str(json.dumps({
                "type": "error",
                "message": f"Server error: {str(e)}",
                "timestamp": asyncio.get_event_loop().time()
            }))
    
    async def handle_calibration_request(self, ws, data):
        """Handle calibration requests"""
        component = data.get("component", "UNO")
        
        # Send calibration started response
        await ws.send_str(json.dumps({
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
        await ws.send_str(json.dumps({
            "type": "calibration_result",
            "component": component,
            "status": "completed",
            "success": True,
            "message": f"{component}: Calibration completed successfully",
            "timestamp": asyncio.get_event_loop().time()
        }))
    
    def setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get("/", self.health_check)
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/ws", self.websocket_handler)
    
    async def start_server(self):
        """Start the hybrid server"""
        self.setup_routes()
        
        # Get host and port from environment
        host = os.getenv("HOST", HOST)
        port = int(os.getenv("PORT", PORT))
        
        print(f"🌐 MEGG IoT Backend starting on {host}:{port}")
        print(f"📡 Health check: http://{host}:{port}/health")
        print(f"🔌 WebSocket: ws://{host}:{port}/ws")
        print("🚀 Ready for client connections!")
        
        # Start the server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        return True

# Global server instance
render_server = RenderWebSocketServer()

async def main():
    """Main function"""
    print("🚀 Starting MEGG IoT Backend (Render Compatible)...")
    print("=" * 60)
    
    try:
        success = await render_server.start_server()
        if not success:
            print("❌ Failed to start server")
            return
        
        print("✅ MEGG IoT Backend started successfully!")
        print("=" * 60)
        print("💡 Available endpoints:")
        print("   - Health check: /health")
        print("   - WebSocket: /ws")
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
