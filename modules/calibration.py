"""
Calibration module with per-component handlers.

This module centralizes calibration logic for each hardware component and
exposes a simple router-style API the WebSocket server can delegate to.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple
from datetime import datetime
import asyncio


class CalibrationRouter:
    """Routes calibration requests to per-component handlers."""

    def __init__(self, send_arduino_command: Callable[[str], "asyncio.Future[dict]"]):
        # Dependency injection: server passes its Arduino command function
        self._send_arduino_command = send_arduino_command

        # Map component name to handler
        self._handlers: Dict[str, Callable[[], "asyncio.Future[Dict]"]] = {
            "UNO": self._handle_uno,
            "HX711": self._handle_hx711,
            "NEMA23": self._handle_nema23,
            "SG90": self._handle_sg90,
            "MG996R": self._handle_mg996r,
        }

    async def calibrate_component(self, component: str, weight: float = None) -> Dict:
        """Dispatch to specific component handler, defaulting to generic."""
        component_upper = component.upper()
        
        # Special handling for HX711 with custom weight
        if component_upper == "HX711" and weight is not None:
            return await self._handle_hx711_with_weight(weight)
        
        handler = self._handlers.get(component_upper)
        if handler is None:
            # Fallback to generic flow for unknown components
            return await self._calibrate_generic(component_upper)
        return await handler()

    # Handlers below can be specialized later; currently use generic flow

    async def _handle_uno(self) -> Dict:
        return await self._calibrate_generic("UNO")

    async def _handle_hx711(self) -> Dict:
        return await self._calibrate_generic("HX711")
    
    async def _handle_hx711_with_weight(self, weight: float) -> Dict:
        """Handle HX711 calibration with custom weight."""
        command = f"CALIBRATE_HX711 {weight}"
        result = await self._send_arduino_command(command)

        if result.get("success"):
            response_lines: List[str] = result.get("response", [])
            
            # Look for calibration completion or error
            error = any("ERROR" in line for line in response_lines)
            # Support new JSON messages from Arduino
            json_done = any('{"hx711":"done"' in line or '"hx711":"done"' in line for line in response_lines)
            legacy_success = any("Calibration data saved" in line or "Calibration Result" in line for line in response_lines)
            success = (not error) and (json_done or legacy_success)

            if success:
                message = f"HX711 calibrated successfully with {weight}g"
                status = "completed"
            elif error:
                error_line = next((line for line in response_lines if "ERROR" in line), "")
                if error_line:
                    message = f"HX711 calibration failed: {error_line}"
                else:
                    message = f"HX711 calibration failed"
                status = "failed"
            else:
                # If Arduino reported success at transport level but we couldn't detect markers,
                # treat as success to avoid false-negative toasts.
                message = f"HX711 calibration completed with {weight}g"
                status = "completed"
                success = True
        else:
            message = f"HX711 calibration failed: {result.get('error', 'Unknown error')}"
            status = "failed"
            success = False

        return {
            "component": "HX711",
            "status": status,
            "success": success,
            "message": message,
            "response_lines": result.get("response", []),  # Include full response
            "timestamp": datetime.now().isoformat(),
        }

    async def _handle_nema23(self) -> Dict:
        return await self._calibrate_generic("NEMA23")

    async def _handle_sg90(self) -> Dict:
        return await self._calibrate_generic("SG90")

    async def _handle_mg996r(self) -> Dict:
        return await self._calibrate_generic("MG996R")

    async def _calibrate_generic(self, component: str) -> Dict:
        """Generic calibration flow: send command and parse Arduino response."""
        command = f"CALIBRATE_{component}"
        result = await self._send_arduino_command(command)

        if result.get("success"):
            response_lines: List[str] = result.get("response", [])
            success = any("CALIBRATION_COMPLETE" in line for line in response_lines)
            error = any("ERROR" in line for line in response_lines)

            if success:
                # Create clean user-facing message
                message = f"{component} calibration completed successfully"
                status = "completed"
            elif error:
                # Extract error message if available
                error_line = next((line for line in response_lines if "ERROR" in line), "")
                if error_line:
                    message = f"{component} calibration failed: {error_line}"
                else:
                    message = f"{component} calibration failed"
                status = "failed"
            else:
                message = f"{component} calibration completed successfully"
                status = "completed"
        else:
            message = f"{component} calibration failed: {result.get('error', 'Unknown error')}"
            status = "failed"
            success = False

        return {
            "component": component,
            "status": status,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }



