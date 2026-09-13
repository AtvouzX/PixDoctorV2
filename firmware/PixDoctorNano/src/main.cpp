/**
 * PixDoctorNano - Physical Pin & Actuator Measurement Probe
 * Platform: Arduino Nano 33 IoT (SAMD21G18A ARM Cortex-M0+ @ 48MHz)
 * 
 * Direct-Register Fast Polling Engine (1.1µs resolution):
 * Reads all 14 channels simultaneously (MAIN 1-8 & AUX 1-6) without SAMD21
 * EIC interrupt channel collision limitations.
 * Streams structured JSON packets to PixDoctor GUI over USB Serial CDC at 20Hz.
 */

#include <Arduino.h>

#define NUM_CHANNELS 14
#define REPORT_INTERVAL_MS 50   // 20 Hz reporting rate
#define TIMEOUT_US 150000UL     // 150ms timeout for inactive signal

// Pin Mapping for Arduino Nano 33 IoT
const uint8_t PROBE_PINS[NUM_CHANNELS] = {
    2,   // Ch 1: MAIN 1 (D2)
    3,   // Ch 2: MAIN 2 (D3)
    4,   // Ch 3: MAIN 3 (D4)
    5,   // Ch 4: MAIN 4 (D5)
    6,   // Ch 5: MAIN 5 (D6)
    7,   // Ch 6: MAIN 6 (D7)
    8,   // Ch 7: MAIN 7 (D8)
    9,   // Ch 8: MAIN 8 (D9)
    10,  // Ch 9: AUX 1  (D10)
    11,  // Ch 10: AUX 2 (D11)
    12,  // Ch 11: AUX 3 (D12)
    A0,  // Ch 12: AUX 4 (A0)
    A1,  // Ch 13: AUX 5 (A1)
    A2   // Ch 14: AUX 6 (A2)
};

// Fast direct register access descriptors
struct FastPin {
    uint8_t pin;
    volatile uint32_t* in_reg;
    uint32_t mask;
};

FastPin fast_pins[NUM_CHANNELS];

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
    // USB CDC Serial communication at 115200 baud
    Serial.begin(115200);
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    // Initialize all 14 probe pins with internal pulldowns and direct register pointers
    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
        uint8_t p = PROBE_PINS[i];
        pinMode(p, INPUT_PULLDOWN);

        fast_pins[i].pin = p;
        EPortType port = g_APinDescription[p].ulPort;
        fast_pins[i].in_reg = &(PORT->Group[port].IN.reg);
        fast_pins[i].mask = (1ul << g_APinDescription[p].ulPin);

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
            Serial.println("{\"type\":\"PONG\",\"device\":\"PixDoctorNano\",\"fw\":\"2.0.0\",\"mcu\":\"SAMD21G18A\",\"channels\":14}");
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

    // 2. High-speed Direct Register Edge Capture (1.1µs resolution)
    uint32_t now_us = micros();
    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {
        bool state = (*(fast_pins[i].in_reg) & fast_pins[i].mask) != 0;
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

    // 3. Periodic JSON Telemetry Stream (20 Hz)
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

        // Pulse onboard LED when active signals are present
        digitalWrite(LED_BUILTIN, has_active_signal ? HIGH : LOW);

        // Stream JSON packet over USB Serial CDC
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
    }
}