# simple_main.py - Modular WebSocket IoT Backend

import asyncio
import signal
import sys
from websocket_server import websocket_server

class SimpleMEGGIoTBackend:
    def __init__(self):
        self.running = False
        
    async def start(self):
        """Start the simple IoT backend server"""
        print("🚀 Starting MEGG IoT Backend (Simple WebSocket API)...")
        print("=" * 60)
        
        try:
            # Start WebSocket server
            success = await websocket_server.start_server()
            if not success:
                print("❌ Failed to start WebSocket server")
                return False
            
            self.running = True
            print("✅ MEGG IoT Backend started successfully!")
            print("=" * 60)
            print("📡 WebSocket Server: ws://localhost:8765")
            print("🌐 Public URL: Use ngrok or similar to expose online")
            print("=" * 60)
            print("💡 Available API Commands:")
            print("   - calibration_request: Start component calibration")
            print("   - work_process: Start/stop/reset work processes")
            print("   - get_status: Get system status")
            print("   - ping/pong: Health check")
            print("=" * 60)
            print("🔧 Supported Components: UNO, HX711, NEMA23, SG90, MG996R")
            print("=" * 60)
            print("Press Ctrl+C to stop the server")
            
            # Keep server running
            await self._keep_alive()
            
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
        except Exception as e:
            print(f"❌ Server error: {e}")
        finally:
            await self.shutdown()
    
    async def _keep_alive(self):
        """Keep the server running until interrupted"""
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    
    async def shutdown(self):
        """Graceful shutdown"""
        print("🛑 Shutting down MEGG IoT Backend...")
        self.running = False
        await websocket_server.stop_server()
        print("✅ Shutdown complete")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.running = False

async def main():
    """Main entry point"""
    backend = SimpleMEGGIoTBackend()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, backend.signal_handler)
    signal.signal(signal.SIGTERM, backend.signal_handler)
    
    # Start the backend
    await backend.start()

if __name__ == "__main__":
    try:
        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
