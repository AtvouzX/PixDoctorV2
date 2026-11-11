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

For the Jetson + `mavlink-router` deployment, `config.toml` points the GUI at
`udpin:0.0.0.0:14550` and the 20 Hz flight-control loop. See `deploy/README.md`.
For the direct wiring, set `endpoint = "/dev/ttyACM0"` (Linux) or the `COMx`
port (Windows) instead; nothing else changes.
Stick control stays off until the `FLY` button is enabled.

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
| Button B | Claw Close / Grab |
| Button L3 | Claw Open / Release |
| Button R3 | Claw Stop |
| Button Y / X | Camera Tilt Up / Down |
| Right Bumper (RB) | Cycle Lumen Lights Brightness |
| Left Bumper (LB) | Lights Off |
| D-Pad Up / Down | Adjust Gain Preset |

## Target Deployment

- Vehicle: custom ArduSub Pixhawk 2.4.8 on the SimpleROV-4 frame (4 thrusters,
  BTS7960 claw in `torpedosub` firmware). Set `FRAME_CONFIG=5`; it is
  reboot-required.
- Host: NVIDIA Jetson with the Xbox gamepad plugged into USB.
- Link: Jetson -> Raspberry Pi 4B (`mavlink-router`) -> Pixhawk USB over UDP
  14550. `deploy/` holds the router config, both systemd units and
  `simplerov4.parm`.
- Alternative: Pixhawk USB straight into the Jetson (`/dev/ttyACM0` at
  115200). Set `[link] endpoint` to the port and skip the Pi.

## Flight Control (Jetson)

`config.toml` (generated on first run) holds the MAVLink endpoint, rates,
failsafe timings and claw bits. The default endpoint is
`udpin:0.0.0.0:14550` for `mavlink-router`.

- `FLY` in the top strip enables the 20 Hz `MANUAL_CONTROL` stream. It starts
  OFF on every launch so parameter work cannot spin thrusters.
- A GCS heartbeat is sent at `[link] heartbeat_hz` (default 1 Hz).
  Arm/disarm uses `COMMAND_LONG`, modes use `SET_MODE`.
- Gamepad lost, or no new sample for `gamepad_timeout_s`: axes go neutral at
  once, disarm follows after `gamepad_disarm_s`.
- Link lost (no autopilot heartbeat for `link_timeout_s`): no commands are
  sent; the loop resumes without arming.
- Quit while armed: neutral axes, then disarm.

Sticks are shaped by the active gamepad profile (`gain`, deadzone, expo,
inverts) before scaling to `-1000..1000`. Depth uses ArduSub's `0..1000` `z`
with 500 neutral. The raw button mask is never streamed, so A=`DISARM` cannot
also trigger a claw bit.

The BTS7960 claw uses `MANUAL_CONTROL` button bits. `BTN0_FUNCTION=140`
(close), `BTN1_FUNCTION=139` (open), `BTN2_FUNCTION=141` (stop), matching the
torpedosub firmware. Claw state comes from `Claw: ...` STATUSTEXT and current
from `GRIP_DC_CURR`; arming is refused while those grip parameters are wrong.

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
## License

MIT License.
