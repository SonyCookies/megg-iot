# simple_config.py

import os
from dotenv import load_dotenv

load_dotenv()

# WebSocket Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8765"))

# API Configuration
API_VERSION = "1.0.0"
API_NAME = "MEGG IoT WebSocket API"

# Hardware Components (for API responses)
HARDWARE_COMPONENTS = {
    "UNO": {
        "name": "Arduino UNO",
        "description": "Main microcontroller",
        "status": "available"
    },
    "HX711": {
        "name": "HX711 Load Cell",
        "description": "Weight sensor",
        "status": "available"
    },
    "NEMA23": {
        "name": "NEMA 23 Stepper Motor",
        "description": "Main positioning motor",
        "status": "available"
    },
    "SG90": {
        "name": "SG90 Servo Motor",
        "description": "Loading servo motor",
        "status": "available"
    },
    "MG996R": {
        "name": "MG996R Servo Motor",
        "description": "Gripping servo motor",
        "status": "available"
    }
}

# Message Types
MESSAGE_TYPES = {
    "PING": "ping",
    "PONG": "pong",
    "CALIBRATION_REQUEST": "calibration_request",
    "CALIBRATION_RESPONSE": "calibration_response",
    "CALIBRATION_RESULT": "calibration_result",
    "SYSTEM_STATUS": "system_status",
    "COMPONENTS_INFO": "components_info",
    "CUSTOM_ACTION": "custom_action",
    "CUSTOM_ACTION_RESPONSE": "custom_action_response",
    "RESET_CALIBRATION": "reset_calibration",
    "RESET_RESPONSE": "reset_response",
    "SYSTEM_UPDATE": "system_update",
    "ERROR": "error",
    "CONNECTION": "connection"
}

