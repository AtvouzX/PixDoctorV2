"""
PixDoctorV2 - Offline ArduSub 4.7.1 Virtual Telemetry & Simulator.
Disabled by default; available as a fallback when physical hardware is disconnected.
Emulates ArduSub 4.7.1 MAVLink telemetry, sensor streams, and command responses.
"""

import time
import math
import random
import threading
from typing import Dict, Any, List, Optional, Callable


class MockSimEngine:
    """Simulates an ArduSub 4.7.1 Pixhawk 2.4.8 vehicle generating realistic telemetry."""

    def __init__(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.callback = callback
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

        # Simulated state
        self.armed: bool = False
        self.flight_mode: int = 19  # MANUAL
        self.depth_m: float = 1.25
        self.roll_deg: float = 0.0
        self.pitch_deg: float = 0.0
        self.yaw_deg: float = 180.0
        self.batt_voltage: float = 15.2
        self.batt_current: float = 2.4
        self.batt_remaining_pct: int = 88
        self.temperature_c: float = 24.5
        self.water_pressure_bar: float = 1.12
        self.leak_detected: bool = False

        # 8 Motor PWMs
        self.motor_pwms: List[int] = [1500] * 8

    def start(self):
        """Start simulation worker thread."""
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._sim_loop, daemon=True, name="MockSimWorker")
            self._thread.start()

    def stop(self):
        """Stop simulation worker thread."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

    def arm(self, arm_state: bool):
        self.armed = arm_state

    def set_mode(self, mode_id: int):
        self.flight_mode = mode_id

    def set_motor_test(self, motor_idx_1_based: int, throttle_pct: float, timeout_sec: float):
        """Simulate a temporary motor test command."""
        idx = motor_idx_1_based - 1
        if 0 <= idx < 8:
            pwm_val = 1500 + int(throttle_pct * 4.0)  # e.g. 20% -> 1580us
            self.motor_pwms[idx] = pwm_val

            def _revert():
                time.sleep(timeout_sec)
                self.motor_pwms[idx] = 1500

            threading.Thread(target=_revert, daemon=True).start()

    def _sim_loop(self):
        """Generates periodic telemetry packets at 20Hz."""
        t0 = time.time()

        while self.running:
            t = time.time() - t0

            # Gentle underwater sinusoidal drift
            self.roll_deg = math.sin(t * 0.8) * 3.2
            self.pitch_deg = math.cos(t * 0.6) * 2.1
            self.yaw_deg = (180.0 + math.sin(t * 0.2) * 25.0) % 360.0

            # Depth fluctuation
            self.depth_m = max(0.0, 1.25 + math.sin(t * 0.4) * 0.15)
            self.water_pressure_bar = 1.013 + (self.depth_m * 0.098)

            # Battery gentle drain
            self.batt_voltage = max(13.8, 15.2 - (t * 0.002))
            self.batt_current = 2.4 + (3.5 if self.armed else 0.0) + random.uniform(-0.1, 0.1)

            pkt = {
                "source": "SIMULATOR",
                "firmware": "ArduSub 4.7.1 (SITL)",
                "autopilot": "Pixhawk 2.4.8 (FMUv2)",
                "connected": True,
                "armed": self.armed,
                "flight_mode": self.flight_mode,
                "roll": round(self.roll_deg, 1),
                "pitch": round(self.pitch_deg, 1),
                "yaw": round(self.yaw_deg, 1),
                "depth": round(self.depth_m, 2),
                "pressure_bar": round(self.water_pressure_bar, 3),
                "temperature": round(self.temperature_c, 1),
                "voltage": round(self.batt_voltage, 2),
                "current": round(self.batt_current, 1),
                "battery_pct": self.batt_remaining_pct,
                "leak": self.leak_detected,
                "motor_pwms": list(self.motor_pwms),
                "timestamp": time.time()
            }

            if self.callback:
                try:
                    self.callback(pkt)
                except Exception:
                    pass

            time.sleep(0.05)  # 20 Hz
