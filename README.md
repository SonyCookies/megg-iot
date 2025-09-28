# MEGG IoT Backend

WebSocket server for MEGG egg sorting system with Arduino integration.

## Features

- Real-time WebSocket communication
- Arduino calibration support
- Component management (UNO, HX711, NEMA23, SG90, MG996R)
- Simulation mode when Arduino not connected

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python websocket_server.py
```

## Render Deployment

1. **Connect to Render:**
   - Go to [render.com](https://render.com)
   - Connect your GitHub repository
   - Select "Web Service"

2. **Configuration:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python websocket_server.py`
   - **Environment:** Python 3

3. **Environment Variables:**
   - `HOST`: `0.0.0.0`
   - `PORT`: `8765`

## Frontend Configuration

Update your frontend `.env.local`:

```bash
NEXT_PUBLIC_IOT_BACKEND_HOST=your-app.onrender.com
NEXT_PUBLIC_IOT_BACKEND_PORT=443
```

## API Endpoints

- **WebSocket:** `wss://your-app.onrender.com:443`
- **Calibration:** `calibration_request`
- **Status:** `get_status`
- **Ping:** `ping`

## Components

- **UNO:** Arduino UNO microcontroller
- **HX711:** Load cell weight sensor
- **NEMA23:** Stepper motor
- **SG90:** Servo motor
- **MG996R:** High-torque servo motor