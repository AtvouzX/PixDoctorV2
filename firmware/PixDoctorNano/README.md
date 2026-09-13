# 🩺 PixDoctorNano — Physical Pin & Actuator Measurement Probe

**PixDoctorNano** is a high-speed, direct-register PWM pulse analyzer firmware designed for the **Arduino Nano 33 IoT** (Microchip SAMD21G18A ARM Cortex-M0+ running at 48MHz).

It acts as a physical hardware probe that taps directly into the servo output rail of a **Pixhawk 2.4.8 (FMUv2)** flight controller, providing **true closed-loop microsecond-accurate verification** of motor and auxiliary actuator signals for submersibles/ROVs running **ArduSub 4.7.1**.

---

## ⚡ Core Features

- **14-Channel Simultaneous Reading**: Reads all 8 MAIN outputs and 6 AUX channels simultaneously.
- **Direct-Register Fast Polling (1.1µs Resolution)**: Bypasses the SAMD21's External Interrupt Controller (EIC) channel collision limitations, delivering sub-microsecond pulse timing jitter-free across all 14 pins.
- **Structured 20Hz JSON Telemetry**: Emits standard JSON telemetry over native USB CDC Serial at 115200 baud, seamlessly consumed by **PixDoctorV2** or any custom ground control software.
- **Signal Health & Frequency Tracking**: Computes real-time pulse width (1000–2000µs), signal frequency (Hz), and signal validity flags per channel.
- **Bidirectional Command Shell**: Accepts runtime commands via serial (`STATUS`, `ZERO`, `CAL`, `STREAM`).

---

## 🛠️ Pinout & Wiring Guide

Connect the signal pins from the Pixhawk 2.4.8 servo rail to the Arduino Nano 33 IoT header pins:

| Channel | Pixhawk Pin | Nano 33 IoT Pin | SAMD21 Port | Role / Sub Function |
| :--- | :--- | :--- | :--- | :--- |
| **Ch 1** | **MAIN 1 (S)** | **D2** | `PA10` | Motor 1 (Port Horiz) |
| **Ch 2** | **MAIN 2 (S)** | **D3** | `PA11` | Motor 2 (Starboard Horiz) |
| **Ch 3** | **MAIN 3 (S)** | **D4** | `PA07` | Motor 3 (Vertical Front) |
| **Ch 4** | **MAIN 4 (S)** | **D5** | `PA05` | Motor 4 (Vertical Back) |
| **Ch 5** | **MAIN 5 (S)** | **D6** | `PA04` | Motor 5 (Vectored / Heavy) |
| **Ch 6** | **MAIN 6 (S)** | **D7** | `PA06` | Motor 6 (Vectored / Heavy) |
| **Ch 7** | **MAIN 7 (S)** | **D8** | `PA18` | Motor 7 (Heavy) |
| **Ch 8** | **MAIN 8 (S)** | **D9** | `PA17` | Motor 8 (Heavy) |
| **Ch 9** | **AUX 1 (S)**  | **D10**| `PA19` | Aux 1 (Gripper / Servo) |
| **Ch 10**| **AUX 2 (S)**  | **D11**| `PA16` | Aux 2 (Camera Tilt Mount) |
| **Ch 11**| **AUX 3 (S)**  | **D12**| `PA22` | Aux 3 (Lumen Subsea Lights) |
| **Ch 12**| **AUX 4 (S)**  | **A0** | `PA02` | Aux 4 / GPIO Spare |
| **Ch 13**| **AUX 5 (S)**  | **A1** | `PB02` | Aux 5 / GPIO Spare |
| **Ch 14**| **AUX 6 (S)**  | **A2** | `PB03` | Aux 6 / Leak Detector Tap |
| **GND**  | **Pixhawk (-)**| **GND** | `GND`  | **CRITICAL: Shared Common Ground** |

> [!CAUTION]
> **Common Ground Requirement**: Always connect at least one ground wire from the Pixhawk servo ground rail (-) to the Arduino Nano 33 IoT GND pin. Without common ground, pulse measurements will float and produce invalid readings.

---

## 📡 JSON Telemetry Protocol

The probe outputs structured JSON lines at 20 Hz (`REPORT_INTERVAL_MS = 50`):

```json
{
  "type": "PROBE_DATA",
  "t": 18240,
  "pwm": [1500, 1500, 1650, 1500, 0, 0, 0, 0, 1500, 1100, 0, 0, 0, 0],
  "hz": [50.1, 50.1, 50.0, 50.1, 0.0, 0.0, 0.0, 0.0, 50.0, 50.0, 0.0, 0.0, 0.0, 0.0],
  "valid": [1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0]
}
```

### Fields:
- `type`: Message discriminator (`PROBE_DATA`).
- `t`: Microcontroller uptime in milliseconds.
- `pwm`: Array of 14 pulse width values in microseconds (µs).
- `hz`: Array of 14 signal refresh rates in Hertz.
- `valid`: Array of 14 boolean integers (`1` if signal active within 150ms, `0` if inactive/disconnected).

---

## 💻 Serial Command Shell

Send any of the following newline-terminated strings over the serial port (`115200` baud):

- `STATUS` — Returns probe firmware version, chip identifier, active channel count, and loop cycle stats.
- `ZERO` — Resets peak and error tracking statistics.
- `CAL` — Performs pin noise calibration on idle channels.
- `STREAM ON` / `STREAM OFF` — Enables or pauses the 20Hz JSON stream.

---

## 🚀 Building & Flashing

### Using PlatformIO (Recommended)
1. Open the directory in VS Code with the **PlatformIO IDE** extension installed, or use the PlatformIO CLI:
   ```bash
   cd PixDoctorNano
   pio run -t upload
   ```
2. Open Serial Monitor to verify:
   ```bash
   pio device monitor -b 115200
   ```

### Using Arduino IDE
1. Open the Arduino IDE.
2. Under **Tools > Board > Boards Manager**, install **Arduino SAMD Boards (32-bits ARM Cortex-M0+)**.
3. Select **Arduino NANO 33 IoT** under **Tools > Board**.
4. Open `src/main.cpp` (or rename to `PixDoctorNano.ino`) and click **Upload**.

---

## 📄 License
MIT License. Copyright (c) 2026 Faiz / Mengkoding.
