# PixDoctorV2

Configuration and diagnostics tool for Pixhawk 2.4.8 running ArduSub 4.7.1, with real-time PWM pulse verification via an external MCU probe (Arduino Nano 33 IoT or ESP32) and native gamepad control.

## Quick Start

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Launch application:
```bash
python main.py
```

Auto-detect will connect to connected Pixhawk and MCU probe serial ports.

## Hardware Wiring (SimpleROV-4)

Connect Pixhawk servo signal pins to your probe MCU:

| Channel | Pixhawk Pin | Nano 33 IoT Pin | ESP32 Pin | Function |
| :--- | :--- | :--- | :--- | :--- |
| Thruster 1 | MAIN 1 (S) | D2 | GPIO 13 | Port Horizontal Motor |
| Thruster 2 | MAIN 2 (S) | D3 | GPIO 14 | Starboard Horizontal Motor |
| Thruster 3 | MAIN 3 (S) | D4 | GPIO 27 | Vertical Front Motor |
| Thruster 4 | MAIN 4 (S) | D5 | GPIO 26 | Vertical Back Motor |
| Camera Tilt | AUX 2 (S) | D11 | GPIO 21 | Tilt Servo |
| Lights | AUX 3 (S) | D12 | GPIO 19 | Lumen Subsea Lights |
| Leak Sensor | AUX 6 (S) | - | - | Internal Leak Probe (LEAK1_PIN=55) |
| Common GND | Pixhawk (-) | GND | GND | Shared Ground (Mandatory) |

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

## Flashing Probe MCU

Both firmware projects are located in the `mcu/` directory:

- Arduino Nano 33 IoT:
```bash
cd mcu/PixDoctorNano
pio run -t upload
```

- ESP32 DevKit V1:
```bash
cd mcu/PixDoctorESP32
pio run -t upload
```

## Repository Structure

```
PixDoctorV2/
├── core/                  # MAVLink, Gamepad, Probe, and parameter drivers
├── gui/                   # Monochrome retro Tkinter GUI and views
├── mcu/
│   ├── PixDoctorNano/     # Arduino Nano 33 IoT probe firmware (PlatformIO)
│   └── PixDoctorESP32/    # ESP32 probe firmware (PlatformIO)
├── tests/                 # Automated test suite
├── main.py                # Desktop app entry point
├── requirements.txt       # Python dependencies
├── LICENSE                # MIT License
└── README.md
```

## License

MIT License.
