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

    async def calibrate_component(self, component: str) -> Dict:
        """Dispatch to specific component handler, defaulting to generic."""
        component_upper = component.upper()
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
                message = next((line for line in response_lines if component in line), f"{component} calibration completed")
                status = "completed"
            elif error:
                message = next((line for line in response_lines if "ERROR" in line), f"{component} calibration failed")
                status = "failed"
            else:
                message = f"{component} calibration completed"
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



