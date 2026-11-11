"""
PixDoctorV2 - Dual-Engine Native Windows Wireless Gamepad & XInput Manager.
Supports both Cable Mode (XInput 1.4/1.3 slots 0..3) and Wireless / Bluetooth Mode
(DirectInput / WinMM joyGetPosEx) without requiring any external pip dependencies.
Includes full axis calibration, zero-tare center drift compensation, exponential
response curves, and customizable button action mapping with persistence.
"""

import os
import sys
import time
import json
import copy
import ctypes
import threading
from typing import Dict, Any, List, Optional, Callable

# ==================== XINPUT DEFINITIONS ====================
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad", XINPUT_GAMEPAD),
    ]

# XInput Button Bitmasks
XINPUT_GAMEPAD_DPAD_UP        = 0x0001
XINPUT_GAMEPAD_DPAD_DOWN      = 0x0002
XINPUT_GAMEPAD_DPAD_LEFT      = 0x0004
XINPUT_GAMEPAD_DPAD_RIGHT     = 0x0008
XINPUT_GAMEPAD_START          = 0x0010
XINPUT_GAMEPAD_BACK           = 0x0020
XINPUT_GAMEPAD_LEFT_THUMB     = 0x0040
XINPUT_GAMEPAD_RIGHT_THUMB    = 0x0080
XINPUT_GAMEPAD_LEFT_SHOULDER  = 0x0100
XINPUT_GAMEPAD_RIGHT_SHOULDER = 0x0200
XINPUT_GAMEPAD_A              = 0x1000
XINPUT_GAMEPAD_B              = 0x2000
XINPUT_GAMEPAD_X              = 0x4000
XINPUT_GAMEPAD_Y              = 0x8000

# ==================== WINMM DEFINITIONS ====================
class JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("dwXpos", ctypes.c_ulong),
        ("dwYpos", ctypes.c_ulong),
        ("dwZpos", ctypes.c_ulong),
        ("dwRpos", ctypes.c_ulong),
        ("dwUpos", ctypes.c_ulong),
        ("dwVpos", ctypes.c_ulong),
        ("dwButtons", ctypes.c_ulong),
        ("dwButtonNumber", ctypes.c_ulong),
        ("dwPOV", ctypes.c_ulong),
        ("dwReserved1", ctypes.c_ulong),
        ("dwReserved2", ctypes.c_ulong),
    ]

JOY_RETURNALL = 0x000000FF

# ==================== ROV ACTION DEFINITIONS ====================
GAMEPAD_ACTIONS: Dict[str, str] = {
    "TOGGLE_ARM": "Toggle Arm / Disarm Safety State",
    "DISARM": "Emergency Disarm & Kill Thrusters",
    "CYCLE_MODE": "Cycle Flight Mode (Manual / Hold / Stab)",
    "MODE_MANUAL": "Set Flight Mode: MANUAL",
    "MODE_ALT_HOLD": "Set Flight Mode: ALT_HOLD (Depth Hold)",
    "MODE_STABILIZE": "Set Flight Mode: STABILIZE",
    "CAMERA_TILT_UP": "Camera Tilt Up (+5°)",
    "CAMERA_TILT_DOWN": "Camera Tilt Down (-5°)",
    "CAMERA_TILT_CENTER": "Camera Tilt Center (0°)",
    "LIGHTS_CYCLE": "Cycle Lumen Lights (0/25/50/100%)",
    "LIGHTS_OFF": "Lumen Lights Off (0%)",
    "CLAW_GRAB": "Close Claw / Grab Object (Torpedosub BTS7960)",
    "CLAW_RELEASE": "Open Claw / Release (Torpedosub BTS7960)",
    "CLAW_STOP": "Stop Claw Motion (Torpedosub BTS7960)",
    "GAIN_INCREASE": "Increase Gain Preset (+25%)",
    "GAIN_DECREASE": "Decrease Gain Preset (-25%)",
    "NONE": "Unmapped / No Action",
}

DEFAULT_BUTTON_MAPPINGS: Dict[str, str] = {
    "btn_start": "TOGGLE_ARM",
    "btn_back": "CYCLE_MODE",
    "btn_a": "DISARM",
    "btn_b": "CLAW_GRAB",
    "btn_x": "CAMERA_TILT_DOWN",
    "btn_y": "CAMERA_TILT_UP",
    "btn_lb": "LIGHTS_OFF",
    "btn_rb": "LIGHTS_CYCLE",
    "btn_l3": "CLAW_RELEASE",
    "btn_r3": "CLAW_STOP",
    "dpad_up": "GAIN_INCREASE",
    "dpad_down": "GAIN_DECREASE",
    "dpad_left": "MODE_MANUAL",
    "dpad_right": "MODE_ALT_HOLD",
}

# Wireless / Bluetooth Gamepad Mapping Profiles for WinMM / DirectInput
WIRELESS_PROFILES: Dict[str, str] = {
    "XBOX_BT": "Xbox Wireless / Bluetooth (Default)",
    "GENERIC_DINPUT": "Generic DirectInput (Logitech/8BitDo/2.4G)",
    "PLAYSTATION": "PlayStation (DualShock / DualSense)",
    "LEGACY_1TO1": "Direct 1:1 Bit Mapping",
}


class GamepadState:
    """Thread-safe snapshot of gamepad axes, triggers, calibration, and button mappings."""

    def __init__(self):
        self.lock = threading.RLock()
        self.connected: bool = False
        self.controller_name: str = "Disconnected"
        self.backend: str = "None"
        self.wireless_profile: str = "XBOX_BT"
        self.last_pressed_raw_btn: int = 0
        self.last_update_time: float = 0.0

        # Raw Axes before calibration (-32768..32767)
        self.raw_lx: int = 0
        self.raw_ly: int = 0
        self.raw_rx: int = 0
        self.raw_ry: int = 0

        # Calibrated Normalized Axes (-1000 to +1000)
        self.axis_lx: int = 0      # Left Stick X (Yaw / Turn)
        self.axis_ly: int = 0      # Left Stick Y (Throttle / Depth)
        self.axis_rx: int = 0      # Right Stick X (Lateral Strafe)
        self.axis_ry: int = 0      # Right Stick Y (Forward / Reverse)

        # Triggers (0 to 1000)
        self.trigger_lt: int = 0   # Left Trigger
        self.trigger_rt: int = 0   # Right Trigger

        # Buttons (Boolean states)
        self.btn_a: bool = False
        self.btn_b: bool = False
        self.btn_x: bool = False
        self.btn_y: bool = False
        self.btn_lb: bool = False
        self.btn_rb: bool = False
        self.btn_back: bool = False
        self.btn_start: bool = False
        self.btn_l3: bool = False
        self.btn_r3: bool = False
        self.dpad_up: bool = False
        self.dpad_down: bool = False
        self.dpad_left: bool = False
        self.dpad_right: bool = False

        # Raw bitmask for MAVLink MANUAL_CONTROL
        self.buttons_bitmask: int = 0

        # Gain multiplier (0.25, 0.50, 0.75, 1.0)
        self.gain: float = 0.50

        # Calibration parameters
        self.deadzone_pct: float = 0.10
        self.expo: float = 0.0
        self.invert_lx: bool = False
        self.invert_ly: bool = False
        self.invert_rx: bool = False
        self.invert_ry: bool = False

        # Zero-tare center offsets
        self.center_offset_lx: int = 0
        self.center_offset_ly: int = 0
        self.center_offset_rx: int = 0
        self.center_offset_ry: int = 0

        # Button action mappings
        self.button_mappings: Dict[str, str] = dict(DEFAULT_BUTTON_MAPPINGS)
        self.last_pressed_button: Optional[str] = None

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "connected": self.connected,
                "controller_name": self.controller_name,
                "backend": self.backend,
                "last_update_time": self.last_update_time,
                "raw_lx": self.raw_lx,
                "raw_ly": self.raw_ly,
                "raw_rx": self.raw_rx,
                "raw_ry": self.raw_ry,
                "axis_lx": self.axis_lx,
                "axis_ly": self.axis_ly,
                "axis_rx": self.axis_rx,
                "axis_ry": self.axis_ry,
                "trigger_lt": self.trigger_lt,
                "trigger_rt": self.trigger_rt,
                "btn_a": self.btn_a,
                "btn_b": self.btn_b,
                "btn_x": self.btn_x,
                "btn_y": self.btn_y,
                "btn_lb": self.btn_lb,
                "btn_rb": self.btn_rb,
                "btn_back": self.btn_back,
                "btn_start": self.btn_start,
                "btn_l3": self.btn_l3,
                "btn_r3": self.btn_r3,
                "dpad_up": self.dpad_up,
                "dpad_down": self.dpad_down,
                "dpad_left": self.dpad_left,
                "dpad_right": self.dpad_right,
                "buttons_bitmask": self.buttons_bitmask,
                "wireless_profile": self.wireless_profile,
                "last_pressed_raw_btn": self.last_pressed_raw_btn,
                "gain": self.gain,
                "deadzone_pct": self.deadzone_pct,
                "expo": self.expo,
                "invert_lx": self.invert_lx,
                "invert_ly": self.invert_ly,
                "invert_rx": self.invert_rx,
                "invert_ry": self.invert_ry,
                "center_offset_lx": self.center_offset_lx,
                "center_offset_ly": self.center_offset_ly,
                "center_offset_rx": self.center_offset_rx,
                "center_offset_ry": self.center_offset_ry,
                "button_mappings": dict(self.button_mappings),
                "last_pressed_button": self.last_pressed_button,
            }


class GamepadManager:
    """
    Multithreaded controller engine supporting:
    1. XInput (Xbox / Cable Mode) slots 0..3
    2. WinMM (Wireless / Bluetooth / DirectInput Gamepads)
    3. Live Calibration, Zero-Tare Offset, Exponential Smoothing, and Button Remapping
    """

    def __init__(
        self,
        action_callback: Optional[Callable[[str, Any], None]] = None,
        config_file: Optional[str] = None,
        preferred_name: str = "Xbox",
        device_index: int = 0,
    ):
        self.state = GamepadState()
        self.action_callback = action_callback
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

        # SDL (Linux/Jetson) device selection. Windows keeps XInput/WinMM.
        self.preferred_name = preferred_name
        self.device_index = device_index
        self._sdl_joystick = None
        self._sdl_name = ""

        # Load XInput DLL
        self._xinput = None
        for dll_name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                self._xinput = ctypes.windll.LoadLibrary(dll_name)
                self._xinput.XInputGetState.argtypes = [ctypes.c_ulong, ctypes.POINTER(XINPUT_STATE)]
                self._xinput.XInputGetState.restype = ctypes.c_ulong
                break
            except Exception:
                continue

        # Load WinMM DLL
        self._winmm = None
        if sys.platform == "win32":
            try:
                self._winmm = ctypes.windll.winmm
                self._winmm.joyGetPosEx.argtypes = [ctypes.c_uint, ctypes.POINTER(JOYINFOEX)]
                self._winmm.joyGetPosEx.restype = ctypes.c_uint
                self._winmm.joyGetNumDevs.argtypes = []
                self._winmm.joyGetNumDevs.restype = ctypes.c_uint
            except Exception:
                pass

        # Previous button states for edge detection
        self._prev_buttons: Dict[str, bool] = {}

        # Multi-profile holders & saved snapshot
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self._saved_profiles: Dict[str, Dict[str, Any]] = {}
        self.active_profile_name: str = "Default"
        self._saved_active_profile: str = "Default"
        self._profile_callbacks: List[Callable[[str], None]] = []
        self._change_callbacks: List[Callable[[], None]] = []

        # Config file path for persistent settings
        default_cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gamepad_config.json")
        self._config_file = config_file or default_cfg
        self.load_config()

    def start(self):
        """Start polling worker thread."""
        if not self.running:
            self.running = True
            target = self._polling_loop if sys.platform == "win32" else self._polling_loop_sdl
            self._thread = threading.Thread(target=target, daemon=True, name="GamepadWorker")
            self._thread.start()

    def stop(self):
        """Stop polling worker thread."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
        self._close_sdl_joystick()

    def _sync_active_profile_dict(self):
        """Update in-memory profile dict from current state without writing to disk."""
        if self.active_profile_name in self.profiles:
            self.profiles[self.active_profile_name] = self._export_current_state_to_dict()

    def _notify_changed(self):
        """Notify change listeners (e.g. for dirty status indicator)."""
        for cb in self._change_callbacks:
            try:
                cb()
            except Exception:
                pass

    def register_change_callback(self, cb: Callable[[], None]):
        if cb not in self._change_callbacks:
            self._change_callbacks.append(cb)

    def unregister_change_callback(self, cb: Callable[[], None]):
        if cb in self._change_callbacks:
            self._change_callbacks.remove(cb)

    def set_gain(self, gain: float):
        """Set pilot thrust gain multiplier (0.1 to 1.0). Live responsive update."""
        with self.state.lock:
            self.state.gain = max(0.1, min(1.0, gain))
            self._sync_active_profile_dict()
        self._notify_changed()

    def set_deadzone(self, pct: float):
        """Set joystick deadzone fraction (0.00 to 0.40). Live responsive update."""
        with self.state.lock:
            self.state.deadzone_pct = max(0.0, min(0.40, pct))
            self._sync_active_profile_dict()
        self._notify_changed()

    def set_expo(self, expo: float):
        """Set exponential response curve factor (0.0 to 0.80). Live responsive update."""
        with self.state.lock:
            self.state.expo = max(0.0, min(0.80, expo))
            self._sync_active_profile_dict()
        self._notify_changed()

    def set_inversion(self, axis: str, inverted: bool):
        """Invert specified axis ('lx', 'ly', 'rx', 'ry'). Live responsive update."""
        with self.state.lock:
            if axis == "lx": self.state.invert_lx = inverted
            elif axis == "ly": self.state.invert_ly = inverted
            elif axis == "rx": self.state.invert_rx = inverted
            elif axis == "ry": self.state.invert_ry = inverted
            self._sync_active_profile_dict()
        self._notify_changed()

    def calibrate_centers(self):
        """Zero-tare current stick positions as center offsets to eliminate stick drift."""
        with self.state.lock:
            self.state.center_offset_lx = self.state.raw_lx
            self.state.center_offset_ly = self.state.raw_ly
            self.state.center_offset_rx = self.state.raw_rx
            self.state.center_offset_ry = self.state.raw_ry
            self._sync_active_profile_dict()
        self._notify_changed()

    def reset_calibration(self):
        """Reset zero offsets, deadzone, expo, and inversions to defaults."""
        with self.state.lock:
            self.state.center_offset_lx = 0
            self.state.center_offset_ly = 0
            self.state.center_offset_rx = 0
            self.state.center_offset_ry = 0
            self.state.deadzone_pct = 0.10
            self.state.expo = 0.0
            self.state.invert_lx = False
            self.state.invert_ly = False
            self.state.invert_rx = False
            self.state.invert_ry = False
            self._sync_active_profile_dict()
        self._notify_changed()

    def set_wireless_profile(self, profile_key: str):
        """Set active wireless/DirectInput button profile (e.g. XBOX_BT, GENERIC_DINPUT, PLAYSTATION)."""
        if profile_key in WIRELESS_PROFILES:
            with self.state.lock:
                self.state.wireless_profile = profile_key
                self._sync_active_profile_dict()
            self._notify_changed()

    def set_button_mapping(self, btn_name: str, action_id: str):
        """Assign an action to a button."""
        with self.state.lock:
            self.state.button_mappings[btn_name] = action_id
            self._sync_active_profile_dict()
        self._notify_changed()

    def reset_mappings_to_default(self):
        """Reset all button mappings to standard ArduSub assignments."""
        with self.state.lock:
            self.state.button_mappings = dict(DEFAULT_BUTTON_MAPPINGS)
            self._sync_active_profile_dict()
        self._notify_changed()

    def register_profile_callback(self, cb: Callable[[str], None]):
        if cb not in self._profile_callbacks:
            self._profile_callbacks.append(cb)

    def unregister_profile_callback(self, cb: Callable[[str], None]):
        if cb in self._profile_callbacks:
            self._profile_callbacks.remove(cb)

    def _notify_profile_changed(self):
        for cb in self._profile_callbacks:
            try:
                cb(self.active_profile_name)
            except Exception:
                pass

    def get_profile_names(self) -> List[str]:
        with self.state.lock:
            return list(self.profiles.keys()) if self.profiles else ["Default"]

    def get_active_profile_name(self) -> str:
        with self.state.lock:
            return self.active_profile_name

    def is_dirty(self) -> bool:
        """Returns True if in-memory active profile or profile list differs from saved disk snapshot."""
        with self.state.lock:
            if not self._saved_profiles:
                return False
            if self.active_profile_name not in self._saved_profiles:
                return True
            curr = self._export_current_state_to_dict()
            saved = self._saved_profiles.get(self.active_profile_name, {})
            if curr != saved:
                return True
            if self.active_profile_name != self._saved_active_profile:
                return True
            if set(self.profiles.keys()) != set(self._saved_profiles.keys()):
                return True
            return False

    def reload_saved(self) -> bool:
        """Discard in-memory modifications and reload the last saved profile configuration from snapshot."""
        with self.state.lock:
            if not self._saved_profiles or self.active_profile_name not in self._saved_profiles:
                return False
            saved_data = copy.deepcopy(self._saved_profiles[self.active_profile_name])
            self.profiles[self.active_profile_name] = copy.deepcopy(saved_data)
            self._apply_dict_to_state(saved_data)
        self._notify_profile_changed()
        self._notify_changed()
        return True

    def revert_to_saved(self) -> bool:
        """Alias for reload_saved()."""
        return self.reload_saved()

    def _export_current_state_to_dict(self) -> Dict[str, Any]:
        """Convert current self.state into a profile dictionary."""
        return {
            "wireless_profile": self.state.wireless_profile,
            "gain": round(float(self.state.gain), 2),
            "deadzone_pct": round(float(self.state.deadzone_pct), 2),
            "expo": round(float(self.state.expo), 2),
            "invert_lx": bool(self.state.invert_lx),
            "invert_ly": bool(self.state.invert_ly),
            "invert_rx": bool(self.state.invert_rx),
            "invert_ry": bool(self.state.invert_ry),
            "center_offset_lx": int(self.state.center_offset_lx),
            "center_offset_ly": int(self.state.center_offset_ly),
            "center_offset_rx": int(self.state.center_offset_rx),
            "center_offset_ry": int(self.state.center_offset_ry),
            "button_mappings": dict(self.state.button_mappings),
        }

    def _apply_dict_to_state(self, p_data: Dict[str, Any]):
        """Apply a profile dictionary into self.state."""
        self.state.wireless_profile = p_data.get("wireless_profile", "PLAYSTATION")
        self.state.gain = float(p_data.get("gain", 0.50))
        self.state.deadzone_pct = float(p_data.get("deadzone_pct", 0.10))
        self.state.expo = float(p_data.get("expo", 0.0))
        self.state.invert_lx = bool(p_data.get("invert_lx", False))
        self.state.invert_ly = bool(p_data.get("invert_ly", False))
        self.state.invert_rx = bool(p_data.get("invert_rx", False))
        self.state.invert_ry = bool(p_data.get("invert_ry", False))
        self.state.center_offset_lx = int(p_data.get("center_offset_lx", 0))
        self.state.center_offset_ly = int(p_data.get("center_offset_ly", 0))
        self.state.center_offset_rx = int(p_data.get("center_offset_rx", 0))
        self.state.center_offset_ry = int(p_data.get("center_offset_ry", 0))
        loaded_map = p_data.get("button_mappings", {})
        for k, v in loaded_map.items():
            if k in self.state.button_mappings:
                self.state.button_mappings[k] = v

    def set_active_profile(self, profile_name: str, notify: bool = True, save: bool = True) -> bool:
        """Switch active profile and load its values into state."""
        with self.state.lock:
            if profile_name not in self.profiles:
                return False
            self.active_profile_name = profile_name
            self._apply_dict_to_state(self.profiles[profile_name])
        if save:
            self.save_config()
        if notify:
            self._notify_profile_changed()
        self._notify_changed()
        return True

    def create_profile(self, profile_name: str, copy_from_active: bool = True, save: bool = True) -> bool:
        """Create a new profile and make it active."""
        clean_name = profile_name.strip()
        if not clean_name:
            return False
        with self.state.lock:
            if copy_from_active:
                self.profiles[clean_name] = self._export_current_state_to_dict()
            else:
                self.profiles[clean_name] = {
                    "wireless_profile": "PLAYSTATION",
                    "gain": 0.50,
                    "deadzone_pct": 0.10,
                    "expo": 0.0,
                    "invert_lx": False,
                    "invert_ly": False,
                    "invert_rx": False,
                    "invert_ry": False,
                    "center_offset_lx": 0,
                    "center_offset_ly": 0,
                    "center_offset_rx": 0,
                    "center_offset_ry": 0,
                    "button_mappings": dict(DEFAULT_BUTTON_MAPPINGS),
                }
            self.active_profile_name = clean_name
            self._apply_dict_to_state(self.profiles[clean_name])
        if save:
            self.save_config()
        self._notify_profile_changed()
        self._notify_changed()
        return True

    def delete_profile(self, profile_name: str, save: bool = True) -> bool:
        """Delete profile (cannot delete if it is the only profile)."""
        with self.state.lock:
            if len(self.profiles) <= 1:
                return False
            if profile_name not in self.profiles:
                return False
            del self.profiles[profile_name]
            if self.active_profile_name == profile_name:
                self.active_profile_name = list(self.profiles.keys())[0]
                self._apply_dict_to_state(self.profiles[self.active_profile_name])
        if save:
            self.save_config()
        self._notify_profile_changed()
        self._notify_changed()
        return True

    def save_config(self) -> bool:
        """Persist multi-profile calibration & button mappings to JSON file atomically."""
        try:
            with self.state.lock:
                # Update current active profile in dict
                if not self.profiles:
                    self.profiles = {"Default": self._export_current_state_to_dict()}
                    self.active_profile_name = "Default"
                else:
                    self.profiles[self.active_profile_name] = self._export_current_state_to_dict()

                data = {
                    "active_profile": self.active_profile_name,
                    "profiles": self.profiles
                }
                # Update saved snapshot
                self._saved_profiles = copy.deepcopy(self.profiles)
                self._saved_active_profile = self.active_profile_name

            # Atomic file write
            tmp_file = f"{self._config_file}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if os.path.exists(self._config_file):
                os.replace(tmp_file, self._config_file)
            else:
                os.rename(tmp_file, self._config_file)

            self._notify_changed()
            return True
        except Exception:
            return False

    def load_config(self) -> bool:
        """Load multi-profile calibration & mappings from JSON file if available."""
        if not os.path.exists(self._config_file):
            with self.state.lock:
                self.profiles = {"Default": self._export_current_state_to_dict()}
                self.active_profile_name = "Default"
            self.save_config()
            return True

        try:
            with open(self._config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self.state.lock:
                if "profiles" in data and isinstance(data["profiles"], dict) and data["profiles"]:
                    # Modern Multi-Profile Format
                    self.profiles = data["profiles"]
                    act = data.get("active_profile", "")
                    if act in self.profiles:
                        self.active_profile_name = act
                    else:
                        self.active_profile_name = list(self.profiles.keys())[0]
                else:
                    # Legacy Flat Single-Profile Format -> Migrate seamlessly
                    single_prof = {
                        "wireless_profile": data.get("wireless_profile", "PLAYSTATION"),
                        "gain": float(data.get("gain", 0.50)),
                        "deadzone_pct": float(data.get("deadzone_pct", 0.10)),
                        "expo": float(data.get("expo", 0.0)),
                        "invert_lx": bool(data.get("invert_lx", False)),
                        "invert_ly": bool(data.get("invert_ly", False)),
                        "invert_rx": bool(data.get("invert_rx", False)),
                        "invert_ry": bool(data.get("invert_ry", False)),
                        "center_offset_lx": int(data.get("center_offset_lx", 0)),
                        "center_offset_ly": int(data.get("center_offset_ly", 0)),
                        "center_offset_rx": int(data.get("center_offset_rx", 0)),
                        "center_offset_ry": int(data.get("center_offset_ry", 0)),
                        "button_mappings": data.get("button_mappings", dict(DEFAULT_BUTTON_MAPPINGS)),
                    }
                    self.profiles = {"Default": single_prof}
                    self.active_profile_name = "Default"

                self._apply_dict_to_state(self.profiles[self.active_profile_name])
                self._saved_profiles = copy.deepcopy(self.profiles)
                self._saved_active_profile = self.active_profile_name

            # Re-save in new multi-profile format if it was legacy
            if "profiles" not in data:
                self.save_config()
            self._notify_changed()
            return True
        except Exception:
            # Backup corrupted file and initialize defaults
            try:
                bak_path = f"{self._config_file}.bak"
                if os.path.exists(self._config_file):
                    os.replace(self._config_file, bak_path)
            except Exception:
                pass
            with self.state.lock:
                self.profiles = {"Default": self._export_current_state_to_dict()}
                self.active_profile_name = "Default"
            self.save_config()
            return False

    # ------------------------------------------------------- SDL backend
    def _close_sdl_joystick(self):
        if self._sdl_joystick is not None:
            try:
                self._sdl_joystick.quit()
            except Exception:
                pass
        self._sdl_joystick = None
        self._sdl_name = ""

    def _open_sdl_joystick(self):
        """Pick the preferred controller by name, then index, then first."""
        pygame = getattr(self, "_pygame", None)
        if pygame is None:
            return None
        devices = []
        for index in range(pygame.joystick.get_count()):
            try:
                joystick = pygame.joystick.Joystick(index)
                joystick.init()
                devices.append(joystick)
            except Exception:
                continue
        if not devices:
            return None
        chosen = None
        wanted = self.preferred_name.strip().lower()
        if wanted:
            for joystick in devices:
                if wanted in joystick.get_name().lower():
                    chosen = joystick
                    break
        if chosen is None:
            if 0 <= self.device_index < len(devices):
                chosen = devices[self.device_index]
            else:
                chosen = devices[0]
        for joystick in devices:
            if joystick is not chosen:
                try:
                    joystick.quit()
                except Exception:
                    pass
        self._sdl_joystick = chosen
        self._sdl_name = chosen.get_name()
        return chosen

    def _polling_loop_sdl(self):
        """SDL/pygame polling loop used on Linux (Jetson) and other hosts."""
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        try:
            import pygame
            if not pygame.display.get_init():
                pygame.display.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            self._pygame = pygame
        except Exception:
            self._mark_disconnected()
            return

        last_scan = 0.0
        while self.running:
            try:
                pygame.event.pump()
                if self._sdl_joystick is None:
                    now = time.monotonic()
                    if now - last_scan >= 1.0:
                        last_scan = now
                        self._open_sdl_joystick()
                    if self._sdl_joystick is None:
                        self._mark_disconnected()
                        time.sleep(0.02)
                        continue
                self._parse_sdl(self._sdl_joystick)
            except Exception:
                self._close_sdl_joystick()
                self._mark_disconnected()
                time.sleep(0.1)
            time.sleep(0.02)

    def _parse_sdl(self, joystick):
        """Read one SDL joystick sample into the shared GamepadState."""
        name = joystick.get_name()
        axes = [
            float(joystick.get_axis(i)) for i in range(joystick.get_numaxes())
        ]
        def axis(index: int) -> float:
            return axes[index] if len(axes) > index else 0.0

        # SDL GameController layout (Linux/Xbox): 0 LX, 1 LY, 2 RX, 3 RY,
        # 4 LT, 5 RT, 6 LT (some pads), 8/9 = RY/LY for the Windows driver.
        # Triggers idle at -1, so a 4/5 index is only a trigger when the pad
        # reports more than 6 axes. Otherwise the triggers live on 8/9.
        raw_lx = int(axis(0) * 32767)
        # SDL reports stick up as -1; invert so UP is positive like XInput.
        raw_ly = int(-axis(1) * 32767)
        raw_rx = int(axis(2) * 32767)
        ry_index = 9 if len(axes) > 9 else 3
        raw_ry = int(-axis(ry_index) * 32767)
        if len(axes) > 5:
            lt = int(max(0.0, min(1.0, (axis(4) + 1.0) / 2.0)) * 1000)
            rt = int(max(0.0, min(1.0, (axis(5) + 1.0) / 2.0)) * 1000)
        else:
            # No trigger axes reported: report both triggers released.
            lt = rt = 0

        with self.state.lock:
            dz = self.state.deadzone_pct
            expo = self.state.expo
            inv_lx = self.state.invert_lx
            inv_ly = self.state.invert_ly
            inv_rx = self.state.invert_rx
            inv_ry = self.state.invert_ry
            off_lx = self.state.center_offset_lx
            off_ly = self.state.center_offset_ly
            off_rx = self.state.center_offset_rx
            off_ry = self.state.center_offset_ry
            profile = self.state.wireless_profile

        lx = self._normalize_stick_calibrated(raw_lx, off_lx, inv_lx, dz, expo)
        ly = self._normalize_stick_calibrated(raw_ly, off_ly, inv_ly, dz, expo)
        rx = self._normalize_stick_calibrated(raw_rx, off_rx, inv_rx, dz, expo)
        ry = self._normalize_stick_calibrated(raw_ry, off_ry, inv_ry, dz, expo)

        pressed = [
            bool(joystick.get_button(i)) for i in range(joystick.get_numbuttons())
        ]

        def button(index: int) -> bool:
            return index < len(pressed) and pressed[index]

        lowered = name.lower()
        ps_hint = any(
            hint in lowered
            for hint in ("playstation", "ps4", "ps5", "dualshock", "dualsense", "wireless controller")
        )
        if ps_hint:
            playstation = True
        elif "xbox" in lowered or "xinput" in lowered:
            playstation = False
        else:
            playstation = profile == "PLAYSTATION"
        if playstation:
            btn_states = {
                "btn_a": button(0),   # Cross
                "btn_b": button(1),   # Circle
                "btn_x": button(2),   # Square
                "btn_y": button(3),   # Triangle
                "btn_lb": button(4),
                "btn_rb": button(5),
                "btn_back": button(8),  # Share
                "btn_start": button(9),  # Options
                "btn_l3": button(10),
                "btn_r3": button(11),
            }
        else:
            # SDL GameController order: A B X Y LB RB BACK START L3 R3.
            # Some Linux drivers report DPAD_UP/DOWN/LEFT/RIGHT as buttons 11-14,
            # so only treat the hat as authoritative when the pad has a hat.
            btn_states = {
                "btn_a": button(0),
                "btn_b": button(1),
                "btn_x": button(2),
                "btn_y": button(3),
                "btn_lb": button(4),
                "btn_rb": button(5),
                "btn_back": button(6),
                "btn_start": button(7),
                "btn_l3": button(8),
                "btn_r3": button(9),
            }

        dp_up = dp_down = dp_left = dp_right = False
        if joystick.get_numhats() > 0:
            hat_x, hat_y = joystick.get_hat(0)
            dp_up = hat_y > 0
            dp_down = hat_y < 0
            dp_left = hat_x < 0
            dp_right = hat_x > 0
        # Drivers that report no hat expose the d-pad as buttons 11-14.
        dp_up = dp_up or button(11)
        dp_down = dp_down or button(12)
        dp_left = dp_left or button(13)
        dp_right = dp_right or button(14)
        btn_states.update({
            "dpad_up": dp_up,
            "dpad_down": dp_down,
            "dpad_left": dp_left,
            "dpad_right": dp_right,
        })

        ardusub_mask = 0
        for bit, key in enumerate((
            "btn_a", "btn_b", "btn_x", "btn_y", "btn_lb", "btn_rb",
            "btn_back", "btn_start", "btn_l3", "btn_r3",
            "dpad_up", "dpad_down", "dpad_left", "dpad_right",
        )):
            if btn_states[key]:
                ardusub_mask |= (1 << bit)

        self._check_button_edges(btn_states)
        with self.state.lock:
            self.state.connected = True
            self.state.controller_name = name
            self.state.backend = "SDL (Linux/Gamepad)"
            self.state.last_update_time = time.time()
            self.state.raw_lx = raw_lx
            self.state.raw_ly = raw_ly
            self.state.raw_rx = raw_rx
            self.state.raw_ry = raw_ry
            self.state.axis_lx = lx
            self.state.axis_ly = ly
            self.state.axis_rx = rx
            self.state.axis_ry = ry
            self.state.trigger_lt = lt
            self.state.trigger_rt = rt
            for key, value in btn_states.items():
                setattr(self.state, key, value)
            self.state.buttons_bitmask = ardusub_mask

    def _normalize_stick_calibrated(
        self,
        raw_val: int,
        center_offset: int,
        invert: bool,
        deadzone_pct: float,
        expo: float
    ) -> int:
        """
        Normalize 16-bit signed joystick value with center zero-tare drift offset,
        deadzone scaling, progressive expo curve, and polarity inversion.
        Returns scaled value in [-1000, 1000].
        """
        # Subtract zero-tare center offset
        val = raw_val - center_offset
        val = max(-32768, min(32767, val))

        # Deadzone threshold
        dz = int(deadzone_pct * 32767)
        if abs(val) < dz:
            return 0

        # Scale past deadzone
        sign = 1 if val > 0 else -1
        mag = abs(val) - dz
        max_mag = 32767 - dz
        norm_float = mag / max_mag  # 0.0 to 1.0

        # Apply Expo curve: (1 - expo) * x + expo * (x^3)
        if expo > 0:
            norm_float = (1.0 - expo) * norm_float + expo * (norm_float ** 3)

        scaled = int(norm_float * 1000) * sign
        scaled = max(-1000, min(1000, scaled))

        if invert:
            scaled = -scaled

        return scaled

    def _normalize_winmm_raw(self, raw_unsigned: int) -> int:
        """Convert WinMM 16-bit unsigned (0..65535, center 32767) to signed [-32768, 32767]."""
        return max(-32768, min(32767, raw_unsigned - 32767))

    def _mark_disconnected(self):
        with self.state.lock:
            if self.state.connected:
                self.state.connected = False
                self.state.controller_name = "Disconnected"
                self.state.backend = "None"
                self._reset_inputs()

    def _polling_loop(self):
        """50Hz polling loop with active-device caching, safe dwSize initialization, and cooldown scan protection."""
        xinput_state = XINPUT_STATE()
        winmm_info = JOYINFOEX()

        active_backend: Optional[str] = None  # 'xinput' or 'winmm'
        active_slot: Optional[int] = None
        last_scan_time: float = 0.0

        while self.running:
            try:
                now = time.time()

                if active_backend == "xinput" and active_slot is not None and self._xinput:
                    try:
                        res = self._xinput.XInputGetState(active_slot, ctypes.byref(xinput_state))
                    except (Exception, OSError):
                        res = -1

                    if res == 0:
                        try:
                            self._parse_xinput(xinput_state.Gamepad, active_slot)
                        except Exception:
                            pass
                    else:
                        # Controller disconnected
                        active_backend = None
                        active_slot = None
                        last_scan_time = now + 0.5  # 500ms teardown cooldown
                        self._mark_disconnected()

                elif active_backend == "winmm" and active_slot is not None and self._winmm:
                    winmm_info.dwSize = ctypes.sizeof(JOYINFOEX)
                    winmm_info.dwFlags = JOY_RETURNALL
                    try:
                        res = self._winmm.joyGetPosEx(active_slot, ctypes.byref(winmm_info))
                    except (Exception, OSError):
                        res = -1

                    if res == 0:
                        try:
                            self._parse_winmm(winmm_info, active_slot)
                        except Exception:
                            pass
                    else:
                        # Controller disconnected / turned off
                        active_backend = None
                        active_slot = None
                        last_scan_time = now + 0.5  # 500ms teardown cooldown
                        self._mark_disconnected()

                else:
                    # Disconnected: only scan periodically (2Hz / 500ms interval) to prevent teardown hammering
                    if now - last_scan_time >= 0.5:
                        last_scan_time = now
                        found = False

                        # 1. Check XInput slots 0..3
                        if self._xinput:
                            for slot in range(4):
                                try:
                                    res = self._xinput.XInputGetState(slot, ctypes.byref(xinput_state))
                                except (Exception, OSError):
                                    res = -1
                                if res == 0:
                                    active_backend = "xinput"
                                    active_slot = slot
                                    try:
                                        self._parse_xinput(xinput_state.Gamepad, slot)
                                    except Exception:
                                        pass
                                    found = True
                                    break

                        # 2. Check WinMM devices
                        if not found and self._winmm:
                            try:
                                num_devs = min(self._winmm.joyGetNumDevs(), 16)
                            except (Exception, OSError):
                                num_devs = 0

                            for jid in range(num_devs):
                                winmm_info.dwSize = ctypes.sizeof(JOYINFOEX)
                                winmm_info.dwFlags = JOY_RETURNALL
                                try:
                                    res = self._winmm.joyGetPosEx(jid, ctypes.byref(winmm_info))
                                except (Exception, OSError):
                                    res = -1

                                if res == 0:
                                    active_backend = "winmm"
                                    active_slot = jid
                                    try:
                                        self._parse_winmm(winmm_info, jid)
                                    except Exception:
                                        pass
                                    found = True
                                    break

                        if not found:
                            self._mark_disconnected()

            except Exception:
                pass

            time.sleep(0.02)  # 50 Hz

    def _parse_xinput(self, pad: XINPUT_GAMEPAD, slot: int):
        """Process XInput gamepad data with calibration."""
        raw_lx = pad.sThumbLX
        raw_ly = pad.sThumbLY
        raw_rx = pad.sThumbRX
        raw_ry = pad.sThumbRY

        # Read current calibration settings
        with self.state.lock:
            dz = self.state.deadzone_pct
            expo = self.state.expo
            inv_lx = self.state.invert_lx
            inv_ly = self.state.invert_ly
            inv_rx = self.state.invert_rx
            inv_ry = self.state.invert_ry
            off_lx = self.state.center_offset_lx
            off_ly = self.state.center_offset_ly
            off_rx = self.state.center_offset_rx
            off_ry = self.state.center_offset_ry

        lx = self._normalize_stick_calibrated(raw_lx, off_lx, inv_lx, dz, expo)
        ly = self._normalize_stick_calibrated(raw_ly, off_ly, inv_ly, dz, expo)
        rx = self._normalize_stick_calibrated(raw_rx, off_rx, inv_rx, dz, expo)
        ry = self._normalize_stick_calibrated(raw_ry, off_ry, inv_ry, dz, expo)

        lt = int((max(0, pad.bLeftTrigger - 30) / (255 - 30)) * 1000) if pad.bLeftTrigger > 30 else 0
        rt = int((max(0, pad.bRightTrigger - 30) / (255 - 30)) * 1000) if pad.bRightTrigger > 30 else 0

        b = pad.wButtons
        btn_states = {
            "btn_a": bool(b & XINPUT_GAMEPAD_A),
            "btn_b": bool(b & XINPUT_GAMEPAD_B),
            "btn_x": bool(b & XINPUT_GAMEPAD_X),
            "btn_y": bool(b & XINPUT_GAMEPAD_Y),
            "btn_lb": bool(b & XINPUT_GAMEPAD_LEFT_SHOULDER),
            "btn_rb": bool(b & XINPUT_GAMEPAD_RIGHT_SHOULDER),
            "btn_back": bool(b & XINPUT_GAMEPAD_BACK),
            "btn_start": bool(b & XINPUT_GAMEPAD_START),
            "btn_l3": bool(b & XINPUT_GAMEPAD_LEFT_THUMB),
            "btn_r3": bool(b & XINPUT_GAMEPAD_RIGHT_THUMB),
            "dpad_up": bool(b & XINPUT_GAMEPAD_DPAD_UP),
            "dpad_down": bool(b & XINPUT_GAMEPAD_DPAD_DOWN),
            "dpad_left": bool(b & XINPUT_GAMEPAD_DPAD_LEFT),
            "dpad_right": bool(b & XINPUT_GAMEPAD_DPAD_RIGHT),
        }

        # Construct normalized ArduSub MANUAL_CONTROL buttons bitmask:
        # bit 0: A, bit 1: B, bit 2: X, bit 3: Y, bit 4: LB, bit 5: RB, bit 6: Back, bit 7: Start,
        # bit 8: L3, bit 9: R3, bit 10: D-Up, bit 11: D-Down, bit 12: D-Left, bit 13: D-Right
        ardusub_mask = 0
        if btn_states["btn_a"]: ardusub_mask |= (1 << 0)
        if btn_states["btn_b"]: ardusub_mask |= (1 << 1)
        if btn_states["btn_x"]: ardusub_mask |= (1 << 2)
        if btn_states["btn_y"]: ardusub_mask |= (1 << 3)
        if btn_states["btn_lb"]: ardusub_mask |= (1 << 4)
        if btn_states["btn_rb"]: ardusub_mask |= (1 << 5)
        if btn_states["btn_back"]: ardusub_mask |= (1 << 6)
        if btn_states["btn_start"]: ardusub_mask |= (1 << 7)
        if btn_states["btn_l3"]: ardusub_mask |= (1 << 8)
        if btn_states["btn_r3"]: ardusub_mask |= (1 << 9)
        if btn_states["dpad_up"]: ardusub_mask |= (1 << 10)
        if btn_states["dpad_down"]: ardusub_mask |= (1 << 11)
        if btn_states["dpad_left"]: ardusub_mask |= (1 << 12)
        if btn_states["dpad_right"]: ardusub_mask |= (1 << 13)

        self._check_button_edges(btn_states)

        with self.state.lock:
            self.state.connected = True
            self.state.controller_name = f"Xbox Controller (Slot {slot})"
            self.state.backend = "XInput (Cable/USB)"
            self.state.last_update_time = time.time()
            self.state.raw_lx = raw_lx
            self.state.raw_ly = raw_ly
            self.state.raw_rx = raw_rx
            self.state.raw_ry = raw_ry
            self.state.axis_lx = lx
            self.state.axis_ly = ly
            self.state.axis_rx = rx
            self.state.axis_ry = ry
            self.state.trigger_lt = lt
            self.state.trigger_rt = rt
            for k, v in btn_states.items():
                setattr(self.state, k, v)
            self.state.buttons_bitmask = ardusub_mask

    def _parse_winmm(self, info: JOYINFOEX, jid: int):
        """Process WinMM wireless / Bluetooth / DirectInput joystick data with calibration."""
        raw_lx = self._normalize_winmm_raw(info.dwXpos)
        raw_ly = -self._normalize_winmm_raw(info.dwYpos)  # Invert so UP is positive
        raw_rx = self._normalize_winmm_raw(info.dwZpos)
        raw_ry = -self._normalize_winmm_raw(info.dwRpos)

        with self.state.lock:
            dz = self.state.deadzone_pct
            expo = self.state.expo
            inv_lx = self.state.invert_lx
            inv_ly = self.state.invert_ly
            inv_rx = self.state.invert_rx
            inv_ry = self.state.invert_ry
            off_lx = self.state.center_offset_lx
            off_ly = self.state.center_offset_ly
            off_rx = self.state.center_offset_rx
            off_ry = self.state.center_offset_ry
            profile = self.state.wireless_profile

        lx = self._normalize_stick_calibrated(raw_lx, off_lx, inv_lx, dz, expo)
        ly = self._normalize_stick_calibrated(raw_ly, off_ly, inv_ly, dz, expo)
        rx = self._normalize_stick_calibrated(raw_rx, off_rx, inv_rx, dz, expo)
        ry = self._normalize_stick_calibrated(raw_ry, off_ry, inv_ry, dz, expo)

        # Triggers
        lt = 0
        rt = 0
        if info.dwUpos > 0:
            lt = int((info.dwUpos / 65535.0) * 1000)
        if info.dwVpos > 0:
            rt = int((info.dwVpos / 65535.0) * 1000)

        # POV Hat / D-Pad (dwPOV in 1/100 of degree; 65535 = centered)
        pov = info.dwPOV
        dp_up = False
        dp_right = False
        dp_down = False
        dp_left = False
        if pov != 65535 and pov <= 36000:
            dp_up = (pov >= 31500 or pov <= 4500)
            dp_right = (pov >= 4500 and pov <= 13500)
            dp_down = (pov >= 13500 and pov <= 22500)
            dp_left = (pov >= 22500 and pov <= 31500)

        # Buttons (bits 0..31)
        b = info.dwButtons

        # Track the lowest raw button index pressed (1-indexed for pilot display)
        raw_btn_num = 0
        if b > 0:
            for i in range(32):
                if b & (1 << i):
                    raw_btn_num = i + 1
                    break

        # Decode buttons according to active wireless gamepad profile
        if profile == "XBOX_BT":
            # Windows Bluetooth HID Driver mapping for Xbox Series / One controllers:
            # Btn 1 (bit 0): A
            # Btn 2 (bit 1): B
            # Btn 3 or 4 (bit 2 or 3): X (varies between firmware builds)
            # Btn 5 (bit 4): Y
            # Btn 7 (bit 6): LB
            # Btn 8 (bit 7): RB
            # Btn 11 (bit 10): Back / View
            # Btn 12 (bit 11): Start / Menu
            # Btn 14 (bit 13): Left Thumb Click (L3)
            # Btn 15 (bit 14): Right Thumb Click (R3)
            btn_states = {
                "btn_a": bool(b & (1 << 0)),
                "btn_b": bool(b & (1 << 1)),
                "btn_x": bool(b & ((1 << 2) | (1 << 3))),
                "btn_y": bool(b & (1 << 4)),
                "btn_lb": bool(b & (1 << 6)),
                "btn_rb": bool(b & (1 << 7)),
                "btn_back": bool(b & (1 << 10)),
                "btn_start": bool(b & (1 << 11)),
                "btn_l3": bool(b & (1 << 13)),
                "btn_r3": bool(b & (1 << 14)),
                "dpad_up": dp_up,
                "dpad_down": dp_down,
                "dpad_left": dp_left,
                "dpad_right": dp_right,
            }
        elif profile == "GENERIC_DINPUT":
            # Generic DirectInput / Logitech / 8BitDo D-Input mode:
            # Btn 1 (bit 0): X
            # Btn 2 (bit 1): A
            # Btn 3 (bit 2): B
            # Btn 4 (bit 3): Y
            # Btn 5 (bit 4): LB
            # Btn 6 (bit 5): RB
            # Btn 9 (bit 8): Back / Select
            # Btn 10 (bit 9): Start
            # Btn 11 (bit 10): L3
            # Btn 12 (bit 11): R3
            btn_states = {
                "btn_a": bool(b & (1 << 1)),
                "btn_b": bool(b & (1 << 2)),
                "btn_x": bool(b & (1 << 0)),
                "btn_y": bool(b & (1 << 3)),
                "btn_lb": bool(b & (1 << 4)),
                "btn_rb": bool(b & (1 << 5)),
                "btn_back": bool(b & (1 << 8)),
                "btn_start": bool(b & (1 << 9)),
                "btn_l3": bool(b & (1 << 10)),
                "btn_r3": bool(b & (1 << 11)),
                "dpad_up": dp_up,
                "dpad_down": dp_down,
                "dpad_left": dp_left,
                "dpad_right": dp_right,
            }
        elif profile == "PLAYSTATION":
            # PlayStation DualShock 4 / DualSense DirectInput:
            # Btn 1 (bit 0): Square (X)
            # Btn 2 (bit 1): Cross (A)
            # Btn 3 (bit 2): Circle (B)
            # Btn 4 (bit 3): Triangle (Y)
            # Btn 5 (bit 4): L1 (LB)
            # Btn 6 (bit 5): R1 (RB)
            # Btn 9 (bit 8): Share / Create (Back)
            # Btn 10 (bit 9): Options (Start)
            # Btn 11 (bit 10): L3
            # Btn 12 (bit 11): R3
            btn_states = {
                "btn_a": bool(b & (1 << 1)),
                "btn_b": bool(b & (1 << 2)),
                "btn_x": bool(b & (1 << 0)),
                "btn_y": bool(b & (1 << 3)),
                "btn_lb": bool(b & (1 << 4)),
                "btn_rb": bool(b & (1 << 5)),
                "btn_back": bool(b & (1 << 8)),
                "btn_start": bool(b & (1 << 9)),
                "btn_l3": bool(b & (1 << 10)),
                "btn_r3": bool(b & (1 << 11)),
                "dpad_up": dp_up,
                "dpad_down": dp_down,
                "dpad_left": dp_left,
                "dpad_right": dp_right,
            }
        else:
            # LEGACY_1TO1: Direct bit-to-button order (bits 0..9)
            btn_states = {
                "btn_a": bool(b & (1 << 0)),
                "btn_b": bool(b & (1 << 1)),
                "btn_x": bool(b & (1 << 2)),
                "btn_y": bool(b & (1 << 3)),
                "btn_lb": bool(b & (1 << 4)),
                "btn_rb": bool(b & (1 << 5)),
                "btn_back": bool(b & (1 << 6)),
                "btn_start": bool(b & (1 << 7)),
                "btn_l3": bool(b & (1 << 8)),
                "btn_r3": bool(b & (1 << 9)),
                "dpad_up": dp_up,
                "dpad_down": dp_down,
                "dpad_left": dp_left,
                "dpad_right": dp_right,
            }

        # Normalized ArduSub MANUAL_CONTROL buttons bitmask
        ardusub_mask = 0
        if btn_states["btn_a"]: ardusub_mask |= (1 << 0)
        if btn_states["btn_b"]: ardusub_mask |= (1 << 1)
        if btn_states["btn_x"]: ardusub_mask |= (1 << 2)
        if btn_states["btn_y"]: ardusub_mask |= (1 << 3)
        if btn_states["btn_lb"]: ardusub_mask |= (1 << 4)
        if btn_states["btn_rb"]: ardusub_mask |= (1 << 5)
        if btn_states["btn_back"]: ardusub_mask |= (1 << 6)
        if btn_states["btn_start"]: ardusub_mask |= (1 << 7)
        if btn_states["btn_l3"]: ardusub_mask |= (1 << 8)
        if btn_states["btn_r3"]: ardusub_mask |= (1 << 9)
        if btn_states["dpad_up"]: ardusub_mask |= (1 << 10)
        if btn_states["dpad_down"]: ardusub_mask |= (1 << 11)
        if btn_states["dpad_left"]: ardusub_mask |= (1 << 12)
        if btn_states["dpad_right"]: ardusub_mask |= (1 << 13)

        self._check_button_edges(btn_states)

        with self.state.lock:
            self.state.connected = True
            profile_name = WIRELESS_PROFILES.get(profile, profile)
            self.state.controller_name = f"Wireless Controller #{jid} [{profile}]"
            self.state.backend = "WinMM (Wireless/BT)"
            self.state.last_update_time = time.time()
            self.state.last_pressed_raw_btn = raw_btn_num
            self.state.raw_lx = raw_lx
            self.state.raw_ly = raw_ly
            self.state.raw_rx = raw_rx
            self.state.raw_ry = raw_ry
            self.state.axis_lx = lx
            self.state.axis_ly = ly
            self.state.axis_rx = rx
            self.state.axis_ry = ry
            self.state.trigger_lt = lt
            self.state.trigger_rt = rt
            for k, v in btn_states.items():
                setattr(self.state, k, v)
            self.state.buttons_bitmask = ardusub_mask

    def _check_button_edges(self, btn_states: Dict[str, bool]):
        for name, current in btn_states.items():
            prev = self._prev_buttons.get(name, False)
            if current and not prev:
                with self.state.lock:
                    self.state.last_pressed_button = name
                self._handle_button_press(name)
        self._prev_buttons = btn_states

    def _handle_button_press(self, btn_name: str):
        if not self.action_callback:
            return

        with self.state.lock:
            action_id = self.state.button_mappings.get(btn_name, "NONE")

        if action_id and action_id != "NONE":
            try:
                self.action_callback(action_id, None)
            except Exception:
                pass

    def _reset_inputs(self):
        self.state.raw_lx = 0
        self.state.raw_ly = 0
        self.state.raw_rx = 0
        self.state.raw_ry = 0
        self.state.axis_lx = 0
        self.state.axis_ly = 0
        self.state.axis_rx = 0
        self.state.axis_ry = 0
        self.state.trigger_lt = 0
        self.state.trigger_rt = 0
        self.state.btn_a = False
        self.state.btn_b = False
        self.state.btn_x = False
        self.state.btn_y = False
        self.state.btn_lb = False
        self.state.btn_rb = False
        self.state.btn_back = False
        self.state.btn_start = False
        self.state.btn_l3 = False
        self.state.btn_r3 = False
        self.state.dpad_up = False
        self.state.dpad_down = False
        self.state.dpad_left = False
        self.state.dpad_right = False
        self.state.buttons_bitmask = 0
        self.state.last_pressed_raw_btn = 0
        self.state.last_pressed_button = None
        self._prev_buttons.clear()
