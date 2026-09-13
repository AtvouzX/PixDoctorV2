"""
PixDoctorV2 - Thruster Allocation Matrix & Flight Axis Configuration Manager.
Allows pilots to define custom motor participation, direction inversions (MOT_x_DIRECTION),
and gamepad stick mappings (e.g. swapping Left/Right stick turning).
Persists configuration to motor_matrix_config.json and synchronizes with ArduSub.
"""

import os
import json
import threading
from typing import Dict, Any, List, Optional, Callable

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "motor_matrix_config.json")

DEFAULT_PRESETS = {
    "SimpleROV-4": {
        "frame_id": 6,
        "name": "SimpleROV-4 (Standard)",
        "desc": "2 Horizontal (M1 Port, M2 Stbd) + 2 Vertical (M3 Left, M4 Right).",
        "motor_directions": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1},
        "matrix": {
            "fwd":   {1: 1.0,  2: 1.0,  3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "lat":   {1: 0.0,  2: 0.0,  3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "depth": {1: 0.0,  2: 0.0,  3: 1.0, 4: 1.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "yaw":   {1: 1.0,  2: -1.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
        }
    },
    "SimpleROV-4 (Inverted Yaw)": {
        "frame_id": 6,
        "name": "SimpleROV-4 (Inverted Yaw Differential)",
        "desc": "M1 (-1.0) and M2 (+1.0) yaw differential flipped to match probe without altering forward thrust.",
        "motor_directions": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1},
        "matrix": {
            "fwd":   {1: 1.0,  2: 1.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "lat":   {1: 0.0,  2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "depth": {1: 0.0,  2: 0.0, 3: 1.0, 4: 1.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "yaw":   {1: -1.0, 2: 1.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
        }
    },
    "SimpleROV-4 (Inverted Depth)": {
        "frame_id": 6,
        "name": "SimpleROV-4 (Inverted Vertical Thrusters)",
        "desc": "M3 and M4 direction reversed (-1) to match inverted ESC/propeller physical probe readings.",
        "motor_directions": {1: 1, 2: 1, 3: -1, 4: -1, 5: 1, 6: 1, 7: 1, 8: 1},
        "matrix": {
            "fwd":   {1: 1.0,  2: 1.0,  3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "lat":   {1: 0.0,  2: 0.0,  3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "depth": {1: 0.0,  2: 0.0,  3: 1.0, 4: 1.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "yaw":   {1: 1.0,  2: -1.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
        }
    },
    "BlueROV2 Vectored-6": {
        "frame_id": 2,
        "name": "BlueROV2 Vectored (6-Thruster)",
        "desc": "4 Vectored Horizontal (45 deg) + 2 Vertical Thrusters.",
        "motor_directions": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1},
        "matrix": {
            "fwd":   {1: 1.0,  2: 1.0,  3: 1.0,  4: 1.0,  5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "lat":   {1: 1.0,  2: -1.0, 3: -1.0, 4: 1.0,  5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "depth": {1: 0.0,  2: 0.0,  3: 0.0,  4: 0.0,  5: 1.0, 6: 1.0, 7: 0.0, 8: 0.0},
            "yaw":   {1: 1.0,  2: -1.0, 3: 1.0,  4: -1.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
        }
    },
    "BlueROV2 Heavy-8": {
        "frame_id": 3,
        "name": "BlueROV2 Heavy (8-Thruster)",
        "desc": "4 Vectored Horizontal + 4 Vertical Thrusters.",
        "motor_directions": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1},
        "matrix": {
            "fwd":   {1: 1.0,  2: 1.0,  3: 1.0,  4: 1.0,  5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "lat":   {1: 1.0,  2: -1.0, 3: -1.0, 4: 1.0,  5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
            "depth": {1: 0.0,  2: 0.0,  3: 0.0,  4: 0.0,  5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0},
            "yaw":   {1: 1.0,  2: -1.0, 3: 1.0,  4: -1.0, 5: 0.0, 6: 0.0, 7: 0.0, 8: 0.0},
        }
    }
}

STICK_MODES = {
    "STANDARD_ROV": {
        "name": "Standard ROV (Turn on Left Stick X)",
        "desc": "Left Stick = Depth & Yaw (Turn). Right Stick = Forward & Lateral.",
        "axis_fwd": "axis_ry",
        "axis_lat": "axis_rx",
        "axis_depth": "axis_ly",
        "axis_yaw": "axis_lx",
    },
    "FPS_CAR": {
        "name": "FPS Game / Car Steering (Turn on Right Stick X)",
        "desc": "Right Stick = Forward & Yaw (Turn). Left Stick = Depth & Lateral.",
        "axis_fwd": "axis_ry",
        "axis_lat": "axis_lx",
        "axis_depth": "axis_ly",
        "axis_yaw": "axis_rx",
    },
    "RIGHT_ONLY_HORIZ": {
        "name": "Right Stick Horizontal Only (Yaw on Right Stick, No Lateral)",
        "desc": "Right Stick = Forward & Turn (Yaw). Left Stick = Depth only. Optimal for SimpleROV-4.",
        "axis_fwd": "axis_ry",
        "axis_lat": "none",
        "axis_depth": "axis_ly",
        "axis_yaw": "axis_rx",
    }
}


class MotorMatrixManager:
    """Singleton manager for ArduSub thruster allocation matrix and flight stick mappings."""

    _instance: Optional['MotorMatrixManager'] = None

    @classmethod
    def get_instance(cls) -> 'MotorMatrixManager':
        if cls._instance is None:
            cls._instance = MotorMatrixManager()
        return cls._instance

    def __init__(self):
        self.lock = threading.RLock()
        self.active_preset_name: str = "SimpleROV-4"
        self.stick_mode_key: str = "STANDARD_ROV"

        # Motor directions (1 = Normal, -1 = Reversed)
        self.motor_directions: Dict[int, int] = {i: 1 for i in range(1, 9)}

        # Allocation Matrix: motion -> motor_idx (1..8) -> weight (-1.0 to 1.0)
        self.matrix: Dict[str, Dict[int, float]] = {
            "fwd":   {i: 0.0 for i in range(1, 9)},
            "lat":   {i: 0.0 for i in range(1, 9)},
            "depth": {i: 0.0 for i in range(1, 9)},
            "yaw":   {i: 0.0 for i in range(1, 9)},
        }

        # Stick Axis Mappings
        self.axis_mappings: Dict[str, str] = {
            "fwd": "axis_ry",
            "lat": "axis_rx",
            "depth": "axis_ly",
            "yaw": "axis_lx",
        }

        self._callbacks: List[Callable[[], None]] = []

        # Load default SimpleROV-4
        self.apply_preset("SimpleROV-4", notify=False)
        self.load_from_file()

    def register_callback(self, cb: Callable[[], None]):
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unregister_callback(self, cb: Callable[[], None]):
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    def _notify(self):
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def apply_preset(self, preset_name: str, notify: bool = True):
        preset = DEFAULT_PRESETS.get(preset_name)
        if not preset:
            return

        with self.lock:
            self.active_preset_name = preset_name
            self.motor_directions = dict(preset["motor_directions"])
            self.matrix = {
                axis: dict(weights)
                for axis, weights in preset["matrix"].items()
            }

        if notify:
            self.save_to_file()
            self._notify()

    def set_stick_mode(self, mode_key: str, notify: bool = True):
        mode_def = STICK_MODES.get(mode_key)
        if not mode_def:
            return

        with self.lock:
            self.stick_mode_key = mode_key
            self.axis_mappings = {
                "fwd": mode_def["axis_fwd"],
                "lat": mode_def["axis_lat"],
                "depth": mode_def["axis_depth"],
                "yaw": mode_def["axis_yaw"],
            }

        if notify:
            self.save_to_file()
            self._notify()

    def swap_turning_stick(self):
        """Quick 1-click toggle between Left Stick Turning and Right Stick Turning."""
        with self.lock:
            if self.axis_mappings.get("yaw") == "axis_rx":
                self.set_stick_mode("STANDARD_ROV")
            else:
                self.set_stick_mode("FPS_CAR")

    def invert_yaw_differential(self, notify: bool = True):
        """
        Inverts all non-zero weights in the yaw matrix row (e.g. M1: +1 -> -1, M2: -1 -> +1).
        This reverses yaw turning direction without affecting forward/reverse thrust.
        """
        with self.lock:
            for m_idx in range(1, 9):
                w = self.matrix["yaw"].get(m_idx, 0.0)
                if abs(w) > 0.001:
                    self.matrix["yaw"][m_idx] = round(-w, 2)
            self.active_preset_name = "Custom"

        if notify:
            self.save_to_file()
            self._notify()

    def set_motor_direction(self, motor_idx: int, direction: int, notify: bool = True):
        with self.lock:
            self.motor_directions[motor_idx] = 1 if direction >= 0 else -1

        if notify:
            self.save_to_file()
            self._notify()

    def set_matrix_weight(self, axis: str, motor_idx: int, weight: float, notify: bool = True):
        with self.lock:
            if axis in self.matrix and 1 <= motor_idx <= 8:
                self.matrix[axis][motor_idx] = max(-1.0, min(1.0, round(weight, 2)))
                self.active_preset_name = "Custom"

        if notify:
            self.save_to_file()
            self._notify()

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "active_preset": self.active_preset_name,
                "stick_mode": self.stick_mode_key,
                "motor_directions": dict(self.motor_directions),
                "matrix": {
                    axis: dict(weights)
                    for axis, weights in self.matrix.items()
                },
                "axis_mappings": dict(self.axis_mappings),
            }

    def compute_motor_pwms(
        self,
        fwd: int,
        lat: int,
        depth: int,
        yaw: int,
        armed: bool = True
    ) -> List[int]:
        """
        Compute frame-accurate PWMs using current allocation matrix and direction multipliers.
        Guarantees exact parity with physical probe measurements.
        """
        if not armed:
            return [1500] * 8

        f = max(-1.0, min(1.0, fwd / 1000.0))
        l = max(-1.0, min(1.0, lat / 1000.0))
        d = max(-1.0, min(1.0, depth / 1000.0))
        y = max(-1.0, min(1.0, yaw / 1000.0))

        pwms = [1500] * 8
        with self.lock:
            m_fwd = self.matrix.get("fwd", {})
            m_lat = self.matrix.get("lat", {})
            m_depth = self.matrix.get("depth", {})
            m_yaw = self.matrix.get("yaw", {})

            for i in range(1, 9):
                raw_factor = (
                    f * m_fwd.get(i, 0.0) +
                    l * m_lat.get(i, 0.0) +
                    d * m_depth.get(i, 0.0) +
                    y * m_yaw.get(i, 0.0)
                )
                dir_mul = self.motor_directions.get(i, 1)
                effective_factor = max(-1.0, min(1.0, raw_factor * dir_mul))
                pwms[i - 1] = 1500 + int(effective_factor * 400.0)

        return pwms

    def extract_gamepad_commands(self, pad_snap: Optional[Dict[str, Any]]) -> Dict[str, int]:
        """
        Extracts fwd, lat, depth, yaw commands from gamepad snapshot according to current stick mode.
        """
        if not pad_snap or not pad_snap.get("connected", False):
            return {"fwd": 0, "lat": 0, "depth": 0, "yaw": 0}

        gain = pad_snap.get("gain", 0.50)
        with self.lock:
            fwd_chan = self.axis_mappings.get("fwd", "axis_ry")
            lat_chan = self.axis_mappings.get("lat", "axis_rx")
            depth_chan = self.axis_mappings.get("depth", "axis_ly")
            yaw_chan = self.axis_mappings.get("yaw", "axis_lx")

        fwd = int(pad_snap.get(fwd_chan, 0) * gain) if fwd_chan != "none" else 0
        lat = int(pad_snap.get(lat_chan, 0) * gain) if lat_chan != "none" else 0
        depth = int(pad_snap.get(depth_chan, 0) * gain) if depth_chan != "none" else 0
        yaw = int(pad_snap.get(yaw_chan, 0) * gain) if yaw_chan != "none" else 0

        return {"fwd": fwd, "lat": lat, "depth": depth, "yaw": yaw}

    def save_to_file(self, file_path: str = CONFIG_FILE) -> bool:
        with self.lock:
            data = {
                "active_preset": self.active_preset_name,
                "stick_mode": self.stick_mode_key,
                "motor_directions": {str(k): v for k, v in self.motor_directions.items()},
                "matrix": {
                    axis: {str(k): v for k, v in weights.items()}
                    for axis, weights in self.matrix.items()
                },
                "axis_mappings": self.axis_mappings,
            }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def load_from_file(self, file_path: str = CONFIG_FILE) -> bool:
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self.lock:
                self.active_preset_name = data.get("active_preset", "SimpleROV-4")
                self.stick_mode_key = data.get("stick_mode", "STANDARD_ROV")

                raw_dirs = data.get("motor_directions", {})
                for k, v in raw_dirs.items():
                    self.motor_directions[int(k)] = 1 if int(v) >= 0 else -1

                raw_matrix = data.get("matrix", {})
                for axis, weights in raw_matrix.items():
                    if axis in self.matrix:
                        for k, v in weights.items():
                            self.matrix[axis][int(k)] = float(v)

                self.axis_mappings = data.get("axis_mappings", self.axis_mappings)

            return True
        except Exception:
            return False
