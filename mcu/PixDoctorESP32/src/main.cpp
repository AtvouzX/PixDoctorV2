/**
 * PixDoctorESP32 - Physical Pin & Actuator Measurement Probe
 * Platform: ESP32 DevKit V1 (Xtensa dual-core 32-bit @ 240MHz)
 * 
 * Direct-Register Fast Polling Engine (<0.2us resolution):
 * Reads all 14 channels simultaneously (MAIN 1-8 and AUX 1-6) using direct
 * GPIO register access (GPIO.in / GPIO.in1.data).
 * Streams structured JSON packets to PixDoctor GUI over USB Serial at 20Hz.
 */

#include <Arduino.h>
#include <soc/gpio_struct.h>

#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

#define NUM_CHANNELS 14
#define REPORT_INTERVAL_MS 50   // 20 Hz reporting rate
#define TIMEOUT_US 150000UL     // 150ms timeout for inactive signal

// Channel to GPIO pin mapping (ESP32 DevKit V1 safe pins with internal pulldowns)
const uint8_t PROBE_PINS[NUM_CHANNELS] = {
    13,  // Ch 1:  MAIN 1 (Port Horiz)
    14,  // Ch 2:  MAIN 2 (Starboard Horiz)
    27,  // Ch 3:  MAIN 3 (Vert Front)
    26,  // Ch 4:  MAIN 4 (Vert Back)
    25,  // Ch 5:  MAIN 5 (Vectored / Heavy)
    33,  // Ch 6:  MAIN 6 (Vectored / Heavy)
    32,  // Ch 7:  MAIN 7 (Heavy)
    23,  // Ch 8:  MAIN 8 (Heavy)
    22,  // Ch 9:  AUX 1  (Gripper / Aux 1)
    21,  // Ch 10: AUX 2  (Camera Tilt)
    19,  // Ch 11: AUX 3  (Lumen Lights)
    18,  // Ch 12: AUX 4  (Aux 4)
    17,  // Ch 13: AUX 5  (Aux 5)
    16   // Ch 14: AUX 6  (Leak Detector Tap)
};

// Precomputed bitmasks for fast single-cycle register evaluation
uint32_t pin_mask_lo[NUM_CHANNELS];
uint32_t pin_mask_hi[NUM_CHANNELS];

// State transition and timing variables
bool prev_state[NUM_CHANNELS] = {false};
uint32_t rise_time[NUM_CHANNELS] = {0};
uint32_t pulse_width[NUM_CHANNELS] = {0};
uint32_t period[NUM_CHANNELS] = {0};
uint32_t last_edge[NUM_CHANNELS] = {0};

// Processed telemetry
struct ChannelReading {
    uint16_t pulse_us;
    float freq_hz;
    float duty_pct;
    bool active;
};

ChannelReading readings[NUM_CHANNELS];
uint32_t last_report_time = 0;
bool stream_enabled = true;
uint32_t report_interval = REPORT_INTERVAL_MS;

void setup() {
    // USB Serial communication at 115200 baud
    Serial.begin(115200);
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    // Initialize all 14 probe pins with internal pulldowns and fast bitmasks
    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
        uint8_t p = PROBE_PINS[i];
        pinMode(p, INPUT_PULLDOWN);

        if (p < 32) {
            pin_mask_lo[i] = (1UL << p);
            pin_mask_hi[i] = 0;
        } else {
            pin_mask_lo[i] = 0;
            pin_mask_hi[i] = (1UL << (p - 32));
        }

        prev_state[i] = false;
        rise_time[i] = 0;
        pulse_width[i] = 0;
        period[i] = 0;
        last_edge[i] = 0;

        readings[i].pulse_us = 0;
        readings[i].freq_hz = 0.0f;
        readings[i].duty_pct = 0.0f;
        readings[i].active = false;
    }
}

void processIncomingCommands() {
    while (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.length() == 0) continue;

        if (cmd.equalsIgnoreCase("PING") || cmd.equalsIgnoreCase("?")) {
            Serial.println("{\"type\":\"PONG\",\"device\":\"PixDoctorESP32\",\"fw\":\"2.0.0\",\"mcu\":\"ESP32\",\"channels\":14}");
        } else if (cmd.startsWith("RATE ")) {
            int r = cmd.substring(5).toInt();
            if (r >= 5 && r <= 100) {
                report_interval = 1000 / r;
                Serial.print("{\"type\":\"ACK\",\"rate_hz\":");
                Serial.print(r);
                Serial.println("}");
            }
        } else if (cmd.equalsIgnoreCase("START")) {
            stream_enabled = true;
            Serial.println("{\"type\":\"ACK\",\"stream\":true}");
        } else if (cmd.equalsIgnoreCase("STOP")) {
            stream_enabled = false;
            Serial.println("{\"type\":\"ACK\",\"stream\":false}");
        } else if (cmd.equalsIgnoreCase("STATUS")) {
            Serial.print("{\"type\":\"STATUS\",\"device\":\"PixDoctorESP32\",\"fw\":\"2.0.0\",\"mcu\":\"ESP32\",\"cpu_mhz\":");
            Serial.print(getCpuFrequencyMhz());
            Serial.print(",\"free_heap\":");
            Serial.print(ESP.getFreeHeap());
            Serial.print(",\"uptime_ms\":");
            Serial.print(millis());
            Serial.println("}");
        } else if (cmd.equalsIgnoreCase("RESET")) {
            for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
                rise_time[i] = 0;
                pulse_width[i] = 0;
                period[i] = 0;
                last_edge[i] = 0;
                readings[i].pulse_us = 0;
                readings[i].freq_hz = 0.0f;
                readings[i].duty_pct = 0.0f;
                readings[i].active = false;
            }
            Serial.println("{\"type\":\"ACK\",\"reset\":true}");
        }
    }
}

void loop() {
    // 1. Process host commands
    processIncomingCommands();

    // 2. High-speed Direct Register Edge Capture (<0.2us resolution)
    uint32_t gpio_lo = GPIO.in;
    uint32_t gpio_hi = GPIO.in1.data;
    uint32_t now_us = micros();

    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
        bool state = (pin_mask_lo[i] != 0) 
                     ? ((gpio_lo & pin_mask_lo[i]) != 0) 
                     : ((gpio_hi & pin_mask_hi[i]) != 0);

        if (state != prev_state[i]) {
            prev_state[i] = state;
            last_edge[i] = now_us;
            if (state) {
                // Rising Edge
                if (rise_time[i] > 0 && now_us >= rise_time[i]) {
                    period[i] = now_us - rise_time[i];
                }
                rise_time[i] = now_us;
            } else {
                // Falling Edge
                if (rise_time[i] > 0 && now_us >= rise_time[i]) {
                    uint32_t pw = now_us - rise_time[i];
                    if (pw >= 800 && pw <= 2300) { // Valid servo pulse range
                        pulse_width[i] = pw;
                    }
                }
            }
        }
    }

    // 3. Periodic JSON Telemetry Stream (20 Hz default)
    uint32_t now_ms = millis();
    if (stream_enabled && (now_ms - last_report_time >= report_interval)) {
        last_report_time = now_ms;
        bool has_active_signal = false;

        for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
            uint32_t pw = pulse_width[i];
            uint32_t per = period[i];
            uint32_t edge = last_edge[i];

            // Inactive signal timeout
            if (edge == 0 || (now_us - edge > TIMEOUT_US)) {
                readings[i].active = false;
                readings[i].pulse_us = 0;
                readings[i].freq_hz = 0.0f;
                readings[i].duty_pct = 0.0f;
            } else {
                readings[i].active = true;
                readings[i].pulse_us = (uint16_t)pw;
                if (per > 0 && per >= pw) {
                    readings[i].freq_hz = 1000000.0f / (float)per;
                    readings[i].duty_pct = ((float)pw / (float)per) * 100.0f;
                } else {
                    readings[i].freq_hz = 50.0f;
                    readings[i].duty_pct = 0.0f;
                }
                has_active_signal = true;
            }
        }

        // Status LED indicates active signals
        digitalWrite(LED_BUILTIN, has_active_signal ? HIGH : LOW);

        // Stream JSON packet over USB Serial
        Serial.print("{\"type\":\"PROBE_DATA\",\"t\":");
        Serial.print(now_ms);
        
        Serial.print(",\"pwm\":[");
        for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
            Serial.print(readings[i].pulse_us);
            if (i < NUM_CHANNELS - 1) Serial.print(",");
        }
        
        Serial.print("],\"hz\":[");
        for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
            Serial.print(readings[i].freq_hz, 1);
            if (i < NUM_CHANNELS - 1) Serial.print(",");
        }

        Serial.print("],\"valid\":[");
        for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
            Serial.print(readings[i].active ? 1 : 0);
            if (i < NUM_CHANNELS - 1) Serial.print(",");
        }
        Serial.println("]}");

        // Yield execution to RTOS system tasks
        yield();
    }
}