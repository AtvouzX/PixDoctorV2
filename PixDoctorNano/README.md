# PixDoctorNano

High-speed direct-register PWM pulse analyzer firmware for the Arduino Nano 33 IoT (SAMD21G18A, 48MHz).

It measures physical servo output signals from a Pixhawk 2.4.8 running ArduSub 4.7.1 and streams microsecond-accurate data to PixDoctorV2 over USB serial at 115200 baud.

## Pinout

| Channel | Pixhawk Pin | Nano 33 IoT Pin | Port | Function |
| :--- | :--- | :--- | :--- | :--- |
| Ch 1 | MAIN 1 (S) | D2 | PA10 | Motor 1 |
| Ch 2 | MAIN 2 (S) | D3 | PA11 | Motor 2 |
| Ch 3 | MAIN 3 (S) | D4 | PA07 | Motor 3 |
| Ch 4 | MAIN 4 (S) | D5 | PA05 | Motor 4 |
| Ch 5 | MAIN 5 (S) | D6 | PA04 | Motor 5 |
| Ch 6 | MAIN 6 (S) | D7 | PA06 | Motor 6 |
| Ch 7 | MAIN 7 (S) | D8 | PA18 | Motor 7 |
| Ch 8 | MAIN 8 (S) | D9 | PA17 | Motor 8 |
| Ch 9 | AUX 1 (S)  | D10| PA19 | Aux 1 |
| Ch 10 | AUX 2 (S) | D11| PA16 | Aux 2 / Camera Tilt |
| Ch 11 | AUX 3 (S) | D12| PA22 | Aux 3 / Lights |
| Ch 12 | AUX 4 (S) | A0 | PA02 | Aux 4 |
| Ch 13 | AUX 5 (S) | A1 | PB02 | Aux 5 |
| Ch 14 | AUX 6 (S) | A2 | PB03 | Aux 6 |
| GND | Pixhawk (-) | GND | GND | Common Ground (Mandatory) |

## Telemetry Format

Outputs JSON lines at 20 Hz (115200 baud):

```json
{"type":"PROBE_DATA","t":18240,"pwm":[1500,1500,1650,1500,0,0,0,0,1500,1100,0,0,0,0],"hz":[50.1,50.1,50.0,50.1,0.0,0.0,0.0,0.0,50.0,50.0,0.0,0.0,0.0,0.0],"valid":[1,1,1,1,0,0,0,0,1,1,0,0,0,0]}
```

## Serial Commands

- `STATUS` - Report firmware version and loop status.
- `ZERO` - Reset peak and error statistics.
- `CAL` - Pin noise calibration.
- `STREAM ON` / `STREAM OFF` - Enable or pause JSON streaming.

## Flashing

Using PlatformIO:
```bash
pio run -t upload
```

Using Arduino IDE:
1. Install "Arduino SAMD Boards (32-bits ARM Cortex-M0+)" via Boards Manager.
2. Select "Arduino NANO 33 IoT".
3. Open `src/main.cpp` and upload.
