# PixDoctorV2

Configuration and diagnostics tool for Pixhawk 2.4.8 running ArduSub 4.7.1, with real-time PWM pulse verification via an Arduino Nano 33 IoT probe (PixDoctorNano) and native gamepad control.

## Quick Start

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Launch application:
```bash
python main.py
```

Auto-detect will connect to connected Pixhawk and Arduino Nano 33 IoT serial ports.

## Hardware Wiring (SimpleROV-4)

Connect Pixhawk servo signal pins to the Arduino Nano 33 IoT:

| Channel | Pixhawk Pin | Nano 33 IoT Pin | Function |
| :--- | :--- | :--- | :--- |
| Thruster 1 | MAIN 1 (S) | D2 | Port Horizontal Motor |
| Thruster 2 | MAIN 2 (S) | D3 | Starboard Horizontal Motor |
| Thruster 3 | MAIN 3 (S) | D4 | Vertical Front Motor |
| Thruster 4 | MAIN 4 (S) | D5 | Vertical Back Motor |
| Camera Tilt | AUX 2 (S) | D11 | Tilt Servo |
| Lights | AUX 3 (S) | D12 | Lumen Subsea Lights |
| Leak Sensor | AUX 6 (S) | - | Internal Leak Probe (LEAK1_PIN=55) |
| Common GND | Pixhawk (-) | GND | Shared Ground (Mandatory) |

## Gamepad Controls

| Control | Action |
| :--- | :--- |
| Left Stick Y | Throttle / Depth (Ascend / Descend) |
| Left Stick X | Yaw (Turn Left / Right) |
| Right Stick Y | Forward / Reverse |
| Right Stick X | Lateral Strafe |
| Button START | Arm / Disarm |
| Button BACK | Cycle Mode (MANUAL / ALT_HOLD / STABILIZE) |
| Button A | Emergency Disarm |
| Button Y / X | Camera Tilt Up / Down |
| Right Bumper (RB) | Cycle Lumen Lights Brightness |
| Left Bumper (LB) | Lights Off |
| D-Pad Up / Down | Adjust Gain Preset |

## Flashing the Arduino Nano 33 IoT Probe

The firmware source is included in the `PixDoctorNano` directory in this repository.

Using PlatformIO CLI:
```bash
cd PixDoctorNano
pio run -t upload
```

Or open the `PixDoctorNano` folder in VS Code with PlatformIO, or Arduino IDE (board: Arduino NANO 33 IoT), and upload.

## Repository Structure

```
PixDoctorV2/
├── core/               # MAVLink, Gamepad, Nano probe, and parameter drivers
├── gui/                # Monochrome retro Tkinter GUI and views
├── tests/              # Automated test suite
├── PixDoctorNano/       # Arduino Nano 33 IoT probe firmware (PlatformIO)
│   ├── src/main.cpp
│   └── platformio.ini
├── main.py             # Desktop app entry point
├── requirements.txt    # Python dependencies
├── LICENSE             # MIT License
└── README.md
```

## License

MIT License.
