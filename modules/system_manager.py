# modules/system_manager.py - System Management and Coordination

import asyncio
import queue
import threading
from typing import Dict, Any, Set
from datetime import datetime
from .calibration import CalibrationManager
from .work_process import WorkProcessManager, ProcessStatus
from .arduino_service import ArduinoService

class SystemManager:
    def __init__(self):
        self.calibration_manager = CalibrationManager()
        self.work_process_manager = WorkProcessManager()
        self.arduino_service = ArduinoService()
        self.connected_clients: Set[Any] = set()
        self.server_running = False
        
        # System configuration
        self.system_config = {
            "version": "1.0.0",
            "api_type": "WebSocket API",
            "supported_components": self.calibration_manager.get_supported_components(),
            "max_concurrent_calibrations": 2
        }
        
        # Event queue for thread-safe communication
        self.event_queue = queue.Queue()
        self.event_processor_running = False
        
        # Set up Arduino event listeners
        self._setup_arduino_listeners()
    
    def _setup_arduino_listeners(self) -> None:
        """Set up Arduino service event listeners"""
        # Store callbacks to be called from the main event loop
        self.arduino_service.add_listener('arduino_connected', self._on_arduino_connected_sync)
        self.arduino_service.add_listener('arduino_disconnected', self._on_arduino_disconnected_sync)
        self.arduino_service.add_listener('calibration_result', self._on_arduino_calibration_result_sync)
        self.arduino_service.add_listener('arduino_data', self._on_arduino_data_sync)
    
    def _on_arduino_connected_sync(self, data: Any) -> None:
        """Queue Arduino connected event for processing"""
        self.event_queue.put(('arduino_connected', data))
    
    def _on_arduino_disconnected_sync(self, data: Any) -> None:
        """Queue Arduino disconnected event for processing"""
        self.event_queue.put(('arduino_disconnected', data))
    
    def _on_arduino_calibration_result_sync(self, data: Any) -> None:
        """Queue Arduino calibration result event for processing"""
        self.event_queue.put(('calibration_result', data))
    
    def _on_arduino_data_sync(self, data: Any) -> None:
        """Queue Arduino data event for processing"""
        self.event_queue.put(('arduino_data', data))
    
    async def initialize_arduino(self) -> None:
        """Initialize Arduino connection"""
        try:
            print("🔌 Initializing Arduino connection...")
            success = await self.arduino_service.connect()
            if success:
                print("✅ Arduino connected successfully")
                # Start event processor
                self.event_processor_running = True
                asyncio.create_task(self._process_events())
            else:
                print("⚠️ Arduino connection failed, using simulation mode")
        except Exception as e:
            print(f"❌ Arduino initialization error: {e}")
    
    async def _process_events(self) -> None:
        """Process queued events from Arduino service"""
        while self.event_processor_running:
            try:
                # Check for events with a short timeout
                event_type, data = self.event_queue.get(timeout=0.1)
                
                if event_type == 'arduino_connected':
                    await self._on_arduino_connected(data)
                elif event_type == 'arduino_disconnected':
                    await self._on_arduino_disconnected(data)
                elif event_type == 'calibration_result':
                    await self._on_arduino_calibration_result(data)
                elif event_type == 'arduino_data':
                    await self._on_arduino_data(data)
                    
            except queue.Empty:
                # No events to process, continue
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"❌ Error processing event: {e}")
                await asyncio.sleep(0.01)
    
    async def _on_arduino_connected(self, data: Any) -> None:
        """Handle Arduino connected event"""
        print(f"🔌 Arduino connected: {data}")
        await self.broadcast({
            "type": "arduino_status",
            "connected": True,
            "message": "Arduino connected successfully",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _on_arduino_disconnected(self, data: Any) -> None:
        """Handle Arduino disconnected event"""
        print(f"🔌 Arduino disconnected: {data}")
        await self.broadcast({
            "type": "arduino_status",
            "connected": False,
            "message": "Arduino disconnected",
            "timestamp": datetime.now().isoformat()
        })
    
    async def _on_arduino_calibration_result(self, data: Any) -> None:
        """Handle Arduino calibration result"""
        print(f"🔧 Arduino calibration result: {data}")
        
        # Update work process manager
        if 'component' in data:
            self.work_process_manager.update_component_status(data['component'], data.get('success', False))
        
        # Broadcast to all clients
        await self.broadcast({
            "type": "calibration_result",
            **data
        })
    
    async def _on_arduino_data(self, data: Any) -> None:
        """Handle Arduino data"""
        # Optionally broadcast Arduino data to clients
        await self.broadcast({
            "type": "arduino_data",
            **data
        })
    
    def add_client(self, websocket) -> None:
        """Add a connected client"""
        self.connected_clients.add(websocket)
        print(f"🔌 Client connected (Total: {len(self.connected_clients)})")
    
    def remove_client(self, websocket) -> None:
        """Remove a disconnected client"""
        self.connected_clients.discard(websocket)
        print(f"🔌 Client disconnected (Remaining: {len(self.connected_clients)})")
    
    def set_server_running(self, running: bool) -> None:
        """Set server running state"""
        self.server_running = running
        if not running:
            self.event_processor_running = False
    
    async def send_to_client(self, websocket, data: Dict[str, Any]) -> None:
        """Send data to a specific client"""
        try:
            await websocket.send(self._serialize_message(data))
        except Exception as e:
            print(f"❌ Failed to send data to client: {e}")
    
    async def broadcast(self, data: Dict[str, Any]) -> None:
        """Broadcast data to all connected clients"""
        if not self.connected_clients:
            return
        
        message = self._serialize_message(data)
        disconnected_clients = set()
        
        for websocket in self.connected_clients:
            try:
                await websocket.send(message)
            except Exception as e:
                print(f"❌ Failed to broadcast to client: {e}")
                disconnected_clients.add(websocket)
        
        # Remove disconnected clients
        self.connected_clients -= disconnected_clients
    
    def _serialize_message(self, data: Dict[str, Any]) -> str:
        """Serialize message data to JSON"""
        import json
        return json.dumps(data)
    
    async def handle_calibration_request(self, websocket, data: Dict[str, Any]) -> None:
        """Handle calibration request from client"""
        component = data.get("component")
        if not component:
            await self.send_to_client(websocket, {
                "type": "calibration_result",
                "success": False,
                "component": "unknown",
                "message": "Component not specified",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Check if component is already calibrating
        if self.calibration_manager.is_calibrating(component):
            await self.send_to_client(websocket, {
                "type": "calibration_result",
                "success": False,
                "component": component,
                "message": f"{component} is already calibrating",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        print(f"🔧 Calibration request for {component}")
        
        # Try real Arduino calibration - NO SIMULATION FALLBACK
        arduino_connected = self.arduino_service.is_arduino_connected()
        print(f"🔍 Arduino connection check: {arduino_connected}")
        # Don't print async status here to avoid blocking
        
        if arduino_connected:
            print(f"🔌 Using real Arduino calibration for {component}")
            success = await self.arduino_service.calibrate_component(component)
            
            if success:
                # Wait for Arduino response via event listener
                # The Arduino service will emit calibration_result events
                return
            else:
                await self.send_to_client(websocket, {
                    "type": "calibration_result",
                    "success": False,
                    "component": component,
                    "message": f"Failed to send calibration command to Arduino",
                    "timestamp": datetime.now().isoformat()
                })
                return
        else:
            # Arduino not connected - send error immediately
            print(f"❌ Arduino not connected - calibration failed for {component}")
            await self.send_to_client(websocket, {
                "type": "calibration_result",
                "success": False,
                "component": component,
                "message": f"Arduino not connected - cannot calibrate {component}. Please check Arduino connection.",
                "timestamp": datetime.now().isoformat()
            })
            return
    
    async def handle_work_process_request(self, websocket, data: Dict[str, Any]) -> None:
        """Handle work process request from client"""
        action = data.get("action")
        
        if action == "start_batch":
            batch_id = data.get("batch_id", f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
            egg_count = data.get("egg_count", 10)
            
            result = self.work_process_manager.start_batch(batch_id, egg_count)
            
            if result["success"]:
                # Start the work process simulation
                async def send_callback(message_data: Dict[str, Any]) -> None:
                    await self.broadcast(message_data)  # Broadcast to all clients
                
                # Run work process in background
                asyncio.create_task(
                    self.work_process_manager.execute_work_process(send_callback)
                )
            
            await self.send_to_client(websocket, {
                "type": "work_process_response",
                "action": "start_batch",
                **result,
                "timestamp": datetime.now().isoformat()
            })
        
        elif action == "stop_processing":
            result = self.work_process_manager.stop_processing()
            await self.send_to_client(websocket, {
                "type": "work_process_response",
                "action": "stop_processing",
                **result,
                "timestamp": datetime.now().isoformat()
            })
        
        elif action == "reset_process":
            self.work_process_manager.reset_process()
            await self.send_to_client(websocket, {
                "type": "work_process_response",
                "action": "reset_process",
                "success": True,
                "message": "Process reset successfully",
                "timestamp": datetime.now().isoformat()
            })
        
        elif action == "get_status":
            status = self.work_process_manager.get_process_status()
            await self.send_to_client(websocket, {
                "type": "work_process_status",
                **status,
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            await self.send_to_client(websocket, {
                "type": "work_process_response",
                "action": action,
                "success": False,
                "message": f"Unknown work process action: {action}",
                "timestamp": datetime.now().isoformat()
            })
    
    async def send_system_status(self, websocket) -> None:
        """Send comprehensive system status to client"""
        try:
            print("📊 Sending system status...")
            arduino_info = self.arduino_service.get_connection_info()
            print(f"📊 Arduino info: {arduino_info}")
            
            await self.send_to_client(websocket, {
                "type": "system_status",
                "server": {
                    "connected_clients": len(self.connected_clients),
                    "running": self.server_running,
                    "api_type": self.system_config["api_type"],
                    "version": self.system_config["version"]
                },
                "calibrations": self.calibration_manager.get_calibration_status(),
                "work_process": self.work_process_manager.get_process_status(),
                "arduino": arduino_info,
                "components": {
                    "supported": self.system_config["supported_components"],
                    "status": self.work_process_manager.component_status
                },
                "timestamp": datetime.now().isoformat()
            })
            print("✅ System status sent successfully")
        except Exception as e:
            print(f"❌ Error sending system status: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_welcome_message(self, websocket) -> None:
        """Send welcome message to new client"""
        await self.send_to_client(websocket, {
            "type": "connection",
            "message": "Connected to MEGG IoT Backend API",
            "server_info": {
                "version": self.system_config["version"],
                "api_type": self.system_config["api_type"],
                "components": self.system_config["supported_components"]
            },
            "capabilities": {
                "calibration": "Hardware component calibration simulation",
                "work_process": "Egg processing workflow simulation",
                "real_time_updates": "Live progress and status updates"
            },
            "timestamp": datetime.now().isoformat()
        })
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        return {
            "server": {
                "running": self.server_running,
                "connected_clients": len(self.connected_clients),
                "version": self.system_config["version"]
            },
            "calibrations": self.calibration_manager.get_calibration_status(),
            "work_process": self.work_process_manager.get_process_status(),
            "arduino": self.arduino_service.get_connection_info(),
            "components": self.work_process_manager.component_status
        }

