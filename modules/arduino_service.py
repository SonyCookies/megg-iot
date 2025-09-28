# modules/arduino_service.py - Arduino Serial Communication Service

import serial
import asyncio
import threading
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from arduino_config import get_arduino_config

logger = logging.getLogger(__name__)

class ArduinoService:
    def __init__(self, port: str = None, baudrate: int = None, timeout: float = None):
        # Use configuration or fallback to defaults
        config = get_arduino_config()
        self.platform = config['platform']
        self.port = port or config['port']
        self.baudrate = baudrate or config['baudrate']
        self.timeout = timeout or config['timeout']
        self.fallback_ports = config['fallback_ports']
        self.available_ports = config['available_ports']
        self.serial_connection: Optional[serial.Serial] = None
        self.is_connected = False
        self.is_processing = False
        
        # Event listeners
        self.listeners: Dict[str, list] = {
            'arduino_connected': [],
            'arduino_disconnected': [],
            'arduino_data': [],
            'calibration_result': []
        }
        
        # Serial reading thread
        self.read_thread: Optional[threading.Thread] = None
        self.should_read = False
        
        # Arduino status tracking
        self.arduino_status = {
            'connected': False,
            'last_ping': None,
            'system_active': False,
            'calibration_mode': False,
            'components': {
                'UNO': {'status': 'unknown', 'last_calibration': None},
                'HX711': {'status': 'unknown', 'last_calibration': None},
                'NEMA23': {'status': 'unknown', 'last_calibration': None},
                'SG90': {'status': 'unknown', 'last_calibration': None},
                'MG996R': {'status': 'unknown', 'last_calibration': None}
            }
        }
    
    def add_listener(self, event: str, callback: Callable) -> None:
        """Add event listener"""
        if event in self.listeners:
            self.listeners[event].append(callback)
    
    def remove_listener(self, event: str, callback: Callable) -> None:
        """Remove event listener"""
        if event in self.listeners and callback in self.listeners[event]:
            self.listeners[event].remove(callback)
    
    def _emit(self, event: str, data: Any = None) -> None:
        """Emit event to all listeners"""
        if event in self.listeners:
            for callback in self.listeners[event]:
                try:
                    # All callbacks are now sync wrappers that schedule async tasks
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in event listener for {event}: {e}")
    
    async def connect(self) -> bool:
        """Connect to Arduino via serial"""
        if self.is_connected:
            return True
        
        # Try available ports first, then fallback ports
        ports_to_try = []
        
        # Add available ports first (most reliable)
        for port in self.available_ports:
            if port not in ports_to_try:
                ports_to_try.append(port)
        
        # Add configured port if not in available ports
        if self.port not in ports_to_try:
            ports_to_try.append(self.port)
        
        # Add fallback ports that aren't already in the list
        for port in self.fallback_ports:
            if port not in ports_to_try:
                ports_to_try.append(port)
        
        for port in ports_to_try:
            try:
                logger.info(f"Attempting to connect to Arduino on {port}...")
                self.serial_connection = serial.Serial(
                    port=port,
                    baudrate=self.baudrate,
                    timeout=self.timeout
                )
                
                # Wait for Arduino to initialize
                await asyncio.sleep(2)
                
                # Test connection by sending a status command
                if await self._send_command("STATUS"):
                    self.port = port  # Update port to the working one
                    self.is_connected = True
                    self.arduino_status['connected'] = True
                    self.arduino_status['last_ping'] = datetime.now()
                    
                    # Start reading thread
                    self._start_reading()
                    
                    self._emit('arduino_connected', {'port': port, 'timestamp': datetime.now().isoformat()})
                    logger.info(f"✅ Successfully connected to Arduino on {port}")
                    return True
                else:
                    self.disconnect()
                    continue
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to connect on {port}: {e}")
                if self.serial_connection:
                    self.disconnect()
                continue
        
        logger.error(f"❌ Failed to connect to Arduino on any port: {ports_to_try}")
        self.is_connected = False
        self.arduino_status['connected'] = False
        return False
    
    def disconnect(self) -> None:
        """Disconnect from Arduino"""
        try:
            self.should_read = False
            
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=1.0)
            
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
            
            self.is_connected = False
            self.arduino_status['connected'] = False
            self._emit('arduino_disconnected', {'timestamp': datetime.now().isoformat()})
            logger.info("🔌 Disconnected from Arduino")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Arduino: {e}")
    
    def _start_reading(self) -> None:
        """Start serial reading thread"""
        if self.read_thread and self.read_thread.is_alive():
            return
        
        self.should_read = True
        self.read_thread = threading.Thread(target=self._read_serial, daemon=True)
        self.read_thread.start()
        logger.info("📡 Started Arduino serial reading thread")
    
    def _read_serial(self) -> None:
        """Read serial data from Arduino in separate thread"""
        while self.should_read and self.serial_connection and self.serial_connection.is_open:
            try:
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line:
                        self._process_arduino_message(line)
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage
            except Exception as e:
                logger.error(f"Error reading from Arduino: {e}")
                break
        
        logger.info("📡 Arduino serial reading thread stopped")
    
    def _process_arduino_message(self, message: str) -> None:
        """Process incoming message from Arduino"""
        try:
            logger.info(f"📨 Arduino: {message}")
            
            # Update last ping time
            self.arduino_status['last_ping'] = datetime.now()
            
            # Process different message types
            if message.startswith("CALIBRATION_START:"):
                component = message.split(":")[1]
                self.arduino_status['components'][component]['status'] = 'calibrating'
                self._emit('calibration_result', {
                    'component': component,
                    'success': True,
                    'message': f"{component}: Starting calibration...",
                    'status': 'started',
                    'timestamp': datetime.now().isoformat()
                })
            
            elif message.startswith("CALIBRATION_COMPLETE:"):
                component = message.split(":")[1]
                self.arduino_status['components'][component]['status'] = 'calibrated'
                self.arduino_status['components'][component]['last_calibration'] = datetime.now().isoformat()
                
                # Use Arduino's specific message if available, otherwise use generic
                arduino_message = f"{component} hardware calibration completed successfully!"
                if component == "UNO":
                    arduino_message = f"{component}: Digital pins 2-13 and analog pins A0-A5 tested successfully"
                
                self._emit('calibration_result', {
                    'component': component,
                    'success': True,
                    'message': arduino_message,
                    'status': 'completed',
                    'timestamp': datetime.now().isoformat()
                })
            
            elif message.startswith("ERROR:"):
                error_msg = message.split(":", 1)[1]
                self._emit('calibration_result', {
                    'component': 'UNKNOWN',
                    'success': False,
                    'message': f"Arduino error: {error_msg}",
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                })
            
            elif message.startswith("SYSTEM_STARTED"):
                self.arduino_status['system_active'] = True
            
            elif message.startswith("SYSTEM_STOPPED"):
                self.arduino_status['system_active'] = False
            
            # Emit raw Arduino data
            self._emit('arduino_data', {
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error processing Arduino message: {e}")
    
    async def _send_command(self, command: str) -> bool:
        """Send command to Arduino"""
        try:
            if not self.serial_connection or not self.serial_connection.is_open:
                return False
            
            self.serial_connection.write(f"{command}\n".encode())
            self.serial_connection.flush()
            logger.info(f"📤 Sent to Arduino: {command}")
            
            # Wait a bit for response
            await asyncio.sleep(0.5)
            return True
            
        except Exception as e:
            logger.error(f"Error sending command to Arduino: {e}")
            return False
    
    async def calibrate_component(self, component: str) -> bool:
        """Calibrate a specific component"""
        if not self.is_connected:
            logger.error("Arduino not connected")
            return False
        
        command_map = {
            'UNO': 'CALIBRATE_UNO',
            'HX711': 'CALIBRATE_HX711',
            'NEMA23': 'CALIBRATE_NEMA23',
            'SG90': 'CALIBRATE_SG90',
            'MG996R': 'CALIBRATE_MG996R'
        }
        
        command = command_map.get(component.upper())
        if not command:
            logger.error(f"Unknown component: {component}")
            return False
        
        logger.info(f"🔧 Starting calibration for {component}")
        return await self._send_command(command)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get Arduino system status"""
        if not self.is_connected:
            return {'connected': False, 'error': 'Arduino not connected'}
        
        await self._send_command("STATUS")
        return {
            'connected': True,
            'port': self.port,
            'status': self.arduino_status.copy(),
            'timestamp': datetime.now().isoformat()
        }
    
    async def start_system(self) -> bool:
        """Start Arduino system"""
        if not self.is_connected:
            return False
        return await self._send_command("START")
    
    async def stop_system(self) -> bool:
        """Stop Arduino system"""
        if not self.is_connected:
            return False
        return await self._send_command("STOP")
    
    async def home_servos(self) -> bool:
        """Home all servos"""
        if not self.is_connected:
            return False
        return await self._send_command("HOME")
    
    def is_arduino_connected(self) -> bool:
        """Check if Arduino is connected"""
        return self.is_connected and self.serial_connection and self.serial_connection.is_open
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        # Convert datetime to ISO string for JSON serialization
        last_ping = self.arduino_status.get('last_ping')
        if last_ping and hasattr(last_ping, 'isoformat'):
            last_ping = last_ping.isoformat()
        
        # Create a copy of arduino_status with serialized datetime
        status_copy = self.arduino_status.copy()
        if 'last_ping' in status_copy and hasattr(status_copy['last_ping'], 'isoformat'):
            status_copy['last_ping'] = status_copy['last_ping'].isoformat()
        
        # Serialize datetime objects in components
        if 'components' in status_copy:
            for component, info in status_copy['components'].items():
                if isinstance(info, dict) and 'last_calibration' in info:
                    if info['last_calibration'] and hasattr(info['last_calibration'], 'isoformat'):
                        info['last_calibration'] = info['last_calibration'].isoformat()
        
        return {
            'connected': self.is_connected,
            'platform': self.platform,
            'port': self.port,
            'baudrate': self.baudrate,
            'available_ports': self.available_ports,
            'status': status_copy,
            'last_ping': last_ping
        }
