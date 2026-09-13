# PixDoctorESP32

High-speed direct-register PWM pulse analyzer firmware for the ESP32 (DOIT ESP32 DEVKIT V1, Xtensa 240MHz).

It measures physical servo output signals from a Pixhawk 2.4.8 running ArduSub 4.7.1 and streams microsecond-accurate data to PixDoctorV2 over USB serial at 115200 baud.

## Pinout

| Channel | Pixhawk Pin | ESP32 Pin | Port Register | Function |
| :--- | :--- | :--- | :--- | :--- |
| Ch 1 | MAIN 1 (S) | GPIO 13 | GPIO.in | Motor 1 |
| Ch 2 | MAIN 2 (S) | GPIO 14 | GPIO.in | Motor 2 |
| Ch 3 | MAIN 3 (S) | GPIO 27 | GPIO.in | Motor 3 |
| Ch 4 | MAIN 4 (S) | GPIO 26 | GPIO.in | Motor 4 |
| Ch 5 | MAIN 5 (S) | GPIO 25 | GPIO.in | Motor 5 |
| Ch 6 | MAIN 6 (S) | GPIO 33 | GPIO.in1 | Motor 6 |
| Ch 7 | MAIN 7 (S) | GPIO 32 | GPIO.in1 | Motor 7 |
| Ch 8 | MAIN 8 (S) | GPIO 23 | GPIO.in | Motor 8 |
| Ch 9 | AUX 1 (S)  | GPIO 22 | GPIO.in | Aux 1 |
| Ch 10 | AUX 2 (S) | GPIO 21 | GPIO.in | Aux 2 / Camera Tilt |
| Ch 11 | AUX 3 (S) | GPIO 19 | GPIO.in | Aux 3 / Lights |
| Ch 12 | AUX 4 (S) | GPIO 18 | GPIO.in | Aux 4 |
| Ch 13 | AUX 5 (S) | GPIO 17 | GPIO.in | Aux 5 |
| Ch 14 | AUX 6 (S) | GPIO 16 | GPIO.in | Aux 6 |
| GND | Pixhawk (-) | GND | GND | Common Ground (Mandatory) |

## Telemetry Format

Outputs JSON lines at 20 Hz (115200 baud):

```json
{"type":"PROBE_DATA","t":18240,"pwm":[1500,1500,1650,1500,0,0,0,0,1500,1100,0,0,0,0],"hz":[50.1,50.1,50.0,50.1,0.0,0.0,0.0,0.0,50.0,50.0,0.0,0.0,0.0,0.0],"valid":[1,1,1,1,0,0,0,0,1,1,0,0,0,0]}
```

## Serial Commands

- `STATUS` - Report firmware version, CPU frequency, and heap status.
- `ZERO` / `RESET` - Reset peak and error statistics.
- `RATE <hz>` - Set report frequency (5 to 100 Hz).
- `STREAM ON` / `STREAM OFF` - Enable or pause JSON streaming.

## Flashing

Using PlatformIO:
```bash
cd mcu/PixDoctorESP32
pio run -t upload
```

Using Arduino IDE:
1. Install "esp32 by Espressif Systems" via Boards Manager.
2. Select "DOIT ESP32 DEVKIT V1".
3. Open `src/main.cpp` and click Upload.
