# 🌊 PixDoctorV2 — Pixhawk 2.4.8 (ArduSub 4.7.1) ROV Configuration Suite

A dedicated, lightweight, multithreaded **nostalgic monochrome** configuration and hardware diagnostics suite for **Pixhawk 2.4.8 (FMUv2)** running **ArduSub 4.7.1** submersible firmware.

Integrated directly with the **Arduino Nano 33 IoT (`PixDoctorNano`)** physical logic probe for closed-loop microsecond PWM verification and native **Windows XInput / Wireless Gamepad** controller navigation.

---

## 🌟 Key Highlights

### 1. ⚙️ Focus on Pixhawk Configuration & ArduSub 4.7.1
- **Vehicle Frame Setup**: **SimpleROV-4** (4 thrusters: 2 horizontal, 2 vertical) prioritized and default, with one-click switching to **SimpleROV-3**, **BlueROV2 Vectored (6-thruster)**, **BlueROV2 Heavy (8-thruster)**, **Vectored-90**, **Vectored-6DOF-90**, **BlueROV1**, and **Custom**.
- **Motor Spin Direction**: Quick toggle between `[NORMAL]` and `[REVERSED]` (`MOT_1_DIRECTION` through `MOT_8_DIRECTION`).
- **Sensor Zero-Tare & Calibration**: Bar30 / MS5837 surface depth zero-tare, Accelerometer 1-step level calibration, and Onboard Magnetometer/Compass 3D calibration.
- **Safety & Failsafes**: Internal hull leak detector pin assignment (`LEAK1_PIN`, `LEAK1_LOGIC`), battery cutoff voltage (`FS_BATT_VOLT`), tether heartbeat failsafe (`FS_GCS_ENABLE`), and pre-arm check overrides.
- **Full Parameter Tree**: Searchable, filterable parameter list with inline editing, batch commit to EEPROM, and `.param` file import/export.

### 2. 🔌 Physical Closed-Loop Verification with Arduino Nano 33 IoT
- Directly pairs with the **PixDoctorNano** firmware flashed on an **Arduino Nano 33 IoT**.
- Captures physical output pulses on Pixhawk MAIN 1–8 and AUX 1–6 with 1.1µs resolution.
- Computes real-time Closed-Loop Error Delta ($\Delta\mu\text{s} = \text{Measured} - \text{Commanded}$) and signal frequency (Hz) to verify ESC and PWM health.

### 3. 🎮 Native Wireless Gamepad & XInput Support
- Directly communicates with Xbox, wireless gamepads, and DirectInput controllers using native Windows C-types (zero external pip packages).
- Live HUD crosshair display of Left and Right sticks, triggers, and buttons.
- Transmits 20Hz `MANUAL_CONTROL` packets directly to Pixhawk for pilot control.
- Pre-mapped actions for Arm/Disarm, Flight Modes (Manual, Depth Hold, Stabilize), Lumen lights brightness, and Camera Tilt.

### 4. ⚡ Auto-Detect & Auto-Connect
- Background port scanner queries connected USB serial devices every 2 seconds.
- Automatically connects to **Pixhawk 2.4.8** (115200 or 57600 baud) and **PixDoctorNano** (115200 baud) upon launch or hotplug.
- Offline Mock Simulator is **strictly OFF by default** and only activated manually if desired.

### 5. 🖥️ Nostalgic Simple Monochrome Aesthetic
- Pure high-contrast retro-avionics styling (`#0a0a0c` dark background, `#ffffff` text, tactile borders `#2b2b32`, monospace telemetry).
- Zero bloated browser or webview runtimes; boots instantaneously in pure Python and Tkinter.

---

## 🚀 Quick Start

### 1. Requirements
Ensure Python 3.9+ is installed with `pymavlink` and `pyserial`:
```bash
cd d:\Mengkoding\PixDoctorV2
pip install -r requirements.txt
```

### 2. Launch PixDoctorV2
```bash
python main.py
```

---

## 🛠️ SimpleROV-4 Wiring Reference

### Pixhawk 2.4.8 to Motors & Arduino Nano 33 IoT Probe

| Thruster Name | Pixhawk Output | Nano 33 IoT Pin | Role |
| :--- | :--- | :--- | :--- |
| **Thruster 1** | **MAIN 1 (S)** | **Pin D2** | Port Horizontal (Left Turn & Forward) |
| **Thruster 2** | **MAIN 2 (S)** | **Pin D3** | Starboard Horizontal (Right Turn & Forward) |
| **Thruster 3** | **MAIN 3 (S)** | **Pin D4** | Vertical Front / Left (Depth & Pitch) |
| **Thruster 4** | **MAIN 4 (S)** | **Pin D5** | Vertical Back / Right (Depth & Pitch) |
| **Camera Tilt**| **AUX 2 (S)**  | **Pin D11** | Camera Mount Tilt Servo |
| **Lumen Lights**|**AUX 3 (S)**  | **Pin D12** | Subsea LED Lights PWM |
| **Leak Sensor**| **AUX 6 (S)**  | **—**       | Primary Internal Leak Probe (`LEAK1_PIN=55`) |
| **Common GND** | **Pixhawk (-)**| **Nano GND**| **MANDATORY Common Ground** |

---

## 🎮 Gamepad Control Scheme (ArduSub ROV)

| Input | ArduSub ROV Action |
| :--- | :--- |
| **Left Stick Y** | Throttle / Depth (Ascend / Descend) |
| **Left Stick X** | Yaw (Turn Left / Right) |
| **Right Stick Y**| Forward / Reverse |
| **Right Stick X**| Lateral Strafe (Slide Left / Right) |
| **Button START** | Toggle Arm / Disarm Safety State |
| **Button BACK**  | Cycle Flight Mode (`MANUAL` -> `ALT_HOLD` -> `STABILIZE`) |
| **Button A**     | Emergency Disarm / Cut Thrusters |
| **Button Y / X** | Camera Tilt Up / Down |
| **Right Bumper (RB)** | Cycle Lumen Lights Brightness (0%, 25%, 50%, 100%) |
| **Left Bumper (LB)**  | Lights Off |
| **D-Pad Up / Down**   | Fine Gain Preset Increment / Decrement (25%, 50%, 75%, 100%) |

---

## 📂 Project Architecture

```
PixDoctorV2/
├── main.py                       # Application entry point with HiDPI and error trap
├── requirements.txt              # pymavlink and pyserial dependencies
├── README.md                     # Documentation & user manual
│
├── core/
│   ├── ardusub_defs.py           # ArduSub 4.7.1 frames, modes, commands, key parameters
│   ├── mavlink_manager.py        # Multithreaded MAVLink engine (Serial, UDP, Watchdog)
│   ├── nano_probe_manager.py     # PixDoctorNano 20Hz JSON serial stream reader
│   ├── gamepad_manager.py        # Native Windows XInput & WinMM controller driver
│   ├── auto_detector.py          # Background USB port scanner & auto-connector
│   ├── param_manager.py          # Parameter cache, dirty tracking, .param import/export
│   └── mock_sim.py               # Offline SITL simulator (default OFF)
│
├── gui/
│   ├── theme.py                  # Nostalgic monochrome palette, fonts, ttk styles
│   ├── app_window.py             # Main window, top retro status strip, navigation host
│   ├── widgets/
│   │   ├── mono_widgets.py       # RetroCard, MetricCard, RetroPill, PwmBar
│   │   ├── attitude_indicator.py # HUD pitch ladder, roll pointer, heading compass
│   │   ├── thruster_diagram.py   # SimpleROV-4 chassis & motor position schematic
│   │   └── gamepad_overlay.py    # Live stick & button crosshair monitor
│   └── views/
│       ├── summary_view.py       # Live telemetry HUD: Depth, Battery, Mode, Arm
│       ├── thruster_view.py      # SimpleROV-4 setup + PixDoctorNano closed-loop testing
│       ├── controller_view.py    # Wireless gamepad setup, gain limits, mapping
│       ├── calibration_view.py   # Depth tare, Accel level cal, Compass calibration
│       ├── safety_view.py        # Leak detector pin/logic setup, battery failsafe
│       ├── flight_modes_view.py  # 6 Flight mode slots & AUX servo assignments
│       ├── params_view.py        # Full searchable parameter editor & file manager
│       └── terminal_view.py      # Serial telemetry & Nano probe command console
│
├── firmware/
│   └── PixDoctorNano/            # Arduino Nano 33 IoT physical probe firmware (PlatformIO)
│       ├── platformio.ini        # Build config for SAMD21 (nano_33_iot)
│       ├── src/main.cpp          # 14-ch fast direct-register polling & 20Hz JSON stream
│       └── README.md             # Probe hardware setup & protocol documentation
│
├── tests/
│   └── test_components.py        # Automated test suite (7/7 tests passing)
│
├── LICENSE                       # MIT License
└── .gitignore                    # Python & PlatformIO exclusions
```

---

## ⚡ Flashing the Arduino Nano 33 IoT Probe

The firmware for the **PixDoctorNano** hardware probe is located in `firmware/PixDoctorNano/`:

```bash
cd firmware/PixDoctorNano
pio run -t upload
```

Or open `firmware/PixDoctorNano/` directly in **VS Code with PlatformIO** or the **Arduino IDE** (select board: *Arduino NANO 33 IoT*).

---

## 📄 License
MIT License. Copyright (c) 2026 Faiz / Mengkoding.
