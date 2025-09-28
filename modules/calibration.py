# modules/calibration.py - Hardware Calibration Simulation

import asyncio
import random
from typing import Dict, Any
from datetime import datetime

class CalibrationManager:
    def __init__(self):
        # Component-specific calibration messages and settings
        self.calibration_config = {
            "UNO": {
                "messages": {
                    "start": "UNO: Starting self-test and system diagnostics...",
                    "progress": "UNO: Checking GPIO pins, memory, and communication protocols...",
                    "success": "UNO calibration completed successfully! All systems nominal.",
                    "failure": "UNO calibration failed. Check power supply and connections."
                },
                "timing": {
                    "progress_delay": (1.0, 2.0),
                    "main_delay": (2.0, 3.0)
                },
                "success_rate": 0.90  # 90% success rate
            },
            "HX711": {
                "messages": {
                    "start": "HX711: Initializing load cell calibration...",
                    "progress": "HX711: Measuring zero point and calculating scale factor...",
                    "success": "HX711 load cell calibration completed successfully! Weight sensor ready.",
                    "failure": "HX711 calibration failed. Check load cell connections and stability."
                },
                "timing": {
                    "progress_delay": (1.5, 2.5),
                    "main_delay": (3.0, 4.0)
                },
                "success_rate": 0.85  # 85% success rate
            },
            "NEMA23": {
                "messages": {
                    "start": "NEMA23: Starting stepper motor homing sequence...",
                    "progress": "NEMA23: Moving to home position and setting zero reference...",
                    "success": "NEMA23 stepper motor calibration completed successfully! Positioning ready.",
                    "failure": "NEMA23 calibration failed. Check motor connections and power supply."
                },
                "timing": {
                    "progress_delay": (2.0, 3.0),
                    "main_delay": (4.0, 5.0)
                },
                "success_rate": 0.88  # 88% success rate
            },
            "SG90": {
                "messages": {
                    "start": "SG90: Calibrating servo motor range and center position...",
                    "progress": "SG90: Testing full range motion and setting home position...",
                    "success": "SG90 servo motor calibration completed successfully! Loading mechanism ready.",
                    "failure": "SG90 calibration failed. Check servo connections and mechanical binding."
                },
                "timing": {
                    "progress_delay": (1.0, 2.0),
                    "main_delay": (2.0, 3.0)
                },
                "success_rate": 0.92  # 92% success rate
            },
            "MG996R": {
                "messages": {
                    "start": "MG996R: Calibrating high-torque servo motor...",
                    "progress": "MG996R: Testing grip strength and range of motion...",
                    "success": "MG996R servo motor calibration completed successfully! Gripping mechanism ready.",
                    "failure": "MG996R calibration failed. Check servo connections and mechanical alignment."
                },
                "timing": {
                    "progress_delay": (1.5, 2.5),
                    "main_delay": (3.0, 4.0)
                },
                "success_rate": 0.87  # 87% success rate
            }
        }
        
        # Track active calibrations
        self.active_calibrations: Dict[str, bool] = {}
    
    def get_component_config(self, component: str) -> Dict[str, Any]:
        """Get calibration configuration for a specific component"""
        return self.calibration_config.get(component, {
            "messages": {
                "start": f"{component}: Starting calibration...",
                "progress": f"{component}: Calibration in progress...",
                "success": f"{component} calibration completed successfully!",
                "failure": f"{component} calibration failed. Please check connections."
            },
            "timing": {
                "progress_delay": (1.0, 2.0),
                "main_delay": (2.0, 4.0)
            },
            "success_rate": 0.85
        })
    
    def start_calibration(self, component: str) -> None:
        """Mark calibration as started"""
        self.active_calibrations[component] = True
        print(f"🔧 Started calibration for {component}")
    
    def complete_calibration(self, component: str) -> None:
        """Mark calibration as completed"""
        self.active_calibrations[component] = False
        print(f"✅ Completed calibration for {component}")
    
    def is_calibrating(self, component: str) -> bool:
        """Check if component is currently calibrating"""
        return self.active_calibrations.get(component, False)
    
    async def simulate_calibration(self, component: str, send_callback) -> Dict[str, Any]:
        """
        Simulate realistic calibration process for a component
        
        Args:
            component: Component name (UNO, HX711, NEMA23, SG90, MG996R)
            send_callback: Function to send messages to client
            
        Returns:
            Dict with calibration result
        """
        try:
            config = self.get_component_config(component)
            messages = config["messages"]
            timing = config["timing"]
            success_rate = config["success_rate"]
            
            # Mark calibration as started
            self.start_calibration(component)
            
            # Phase 1: Send start message
            await send_callback({
                "type": "calibration_result",
                "component": component,
                "success": True,
                "message": messages["start"],
                "status": "started",
                "timestamp": datetime.now().isoformat()
            })
            
            # Phase 2: Progress delay and message
            progress_delay = random.uniform(*timing["progress_delay"])
            await asyncio.sleep(progress_delay)
            
            await send_callback({
                "type": "calibration_result",
                "component": component,
                "success": True,
                "message": messages["progress"],
                "status": "progress",
                "timestamp": datetime.now().isoformat()
            })
            
            # Phase 3: Main calibration delay
            main_delay = random.uniform(*timing["main_delay"])
            await asyncio.sleep(main_delay)
            
            # Phase 4: Determine success/failure
            success = random.random() < success_rate
            
            result = {
                "type": "calibration_result",
                "component": component,
                "success": success,
                "message": messages["success"] if success else messages["failure"],
                "status": "completed" if success else "failed",
                "timestamp": datetime.now().isoformat()
            }
            
            await send_callback(result)
            
            # Mark calibration as completed
            self.complete_calibration(component)
            
            if success:
                print(f"✅ {component} calibration completed successfully")
            else:
                print(f"❌ {component} calibration failed")
            
            return result
            
        except Exception as e:
            print(f"❌ Error in calibration simulation for {component}: {e}")
            
            error_result = {
                "type": "calibration_result",
                "component": component,
                "success": False,
                "message": f"Calibration error: {str(e)}",
                "status": "error",
                "timestamp": datetime.now().isoformat()
            }
            
            await send_callback(error_result)
            self.complete_calibration(component)
            return error_result
    
    def get_calibration_status(self) -> Dict[str, bool]:
        """Get status of all calibrations"""
        return self.active_calibrations.copy()
    
    def get_supported_components(self) -> list:
        """Get list of supported components"""
        return list(self.calibration_config.keys())
    
    def reset_all_calibrations(self) -> None:
        """Reset all calibration states"""
        self.active_calibrations.clear()
        print("🔄 All calibration states reset")

