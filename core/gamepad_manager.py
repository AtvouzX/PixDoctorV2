"""
PixDoctorV2 - Dual-Engine Native Windows Wireless Gamepad & XInput Manager.
Supports both Cable Mode (XInput 1.4/1.3 slots 0..3) and Wireless / Bluetooth Mode
(DirectInput / WinMM joyGetPosEx) without requiring any external pip dependencies.
"""

import time
import ctypes
import threading
from typing import Dict, Any, Optional, Callable

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


class GamepadState:
    """Thread-safe snapshot of gamepad axes, triggers, and buttons."""

    def __init__(self):
        self.lock = threading.RLock()
        self.connected: bool = False
        self.controller_name: str = "Disconnected"
        self.backend: str = "None"
        self.last_update_time: float = 0.0

        # Normalized Axes (-1000 to +1000)
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

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "connected": self.connected,
                "controller_name": self.controller_name,
                "backend": self.backend,
                "last_update_time": self.last_update_time,
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
                "gain": self.gain,
            }


class GamepadManager:
    """
    Multithreaded controller engine supporting:
    1. XInput (Xbox / Cable Mode) slots 0..3
    2. WinMM (Wireless / Bluetooth / DirectInput Gamepads)
    """

    def __init__(self, action_callback: Optional[Callable[[str, Any], None]] = None):
        self.state = GamepadState()
        self.action_callback = action_callback
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

        # Load XInput DLL
        self._xinput = None
        for dll_name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                self._xinput = ctypes.windll.LoadLibrary(dll_name)
                break
            except Exception:
                continue

        # Load WinMM DLL
        self._winmm = None
        try:
            self._winmm = ctypes.windll.winmm
        except Exception:
            pass

        # Previous button states for edge detection
        self._prev_buttons: Dict[str, bool] = {}

    def start(self):
        """Start polling worker thread."""
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._polling_loop, daemon=True, name="GamepadWorker")
            self._thread.start()

    def stop(self):
        """Stop polling worker thread."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

    def set_gain(self, gain: float):
        """Set pilot thrust gain multiplier (0.1 to 1.0)."""
        with self.state.lock:
            self.state.gain = max(0.1, min(1.0, gain))

    def _polling_loop(self):
        """50Hz polling loop checking XInput (0..3) first, then falling back to WinMM."""
        xinput_state = XINPUT_STATE()
        winmm_info = JOYINFOEX()
        winmm_info.dwSize = ctypes.sizeof(JOYINFOEX)
        winmm_info.dwFlags = JOY_RETURNALL

        while self.running:
            handled = False

            # 1. Try XInput on all 4 slots (0, 1, 2, 3)
            if self._xinput:
                for slot in range(4):
                    res = self._xinput.XInputGetState(slot, ctypes.byref(xinput_state))
                    if res == 0:  # ERROR_SUCCESS
                        self._parse_xinput(xinput_state.Gamepad, slot)
                        handled = True
                        break

            # 2. If no XInput device found, try WinMM (Wireless / Bluetooth / DirectInput)
            if not handled and self._winmm:
                num_devs = min(self._winmm.joyGetNumDevs(), 16)
                for jid in range(num_devs):
                    res = self._winmm.joyGetPosEx(jid, ctypes.byref(winmm_info))
                    if res == 0:  # JOYERR_NOERROR
                        self._parse_winmm(winmm_info, jid)
                        handled = True
                        break

            # 3. If neither found, mark disconnected
            if not handled:
                with self.state.lock:
                    if self.state.connected:
                        self.state.connected = False
                        self.state.controller_name = "Disconnected"
                        self.state.backend = "None"
                        self._reset_inputs()

            time.sleep(0.02)  # 50 Hz

    def _normalize_stick(self, val: int, deadzone: int = 7849) -> int:
        """Scale 16-bit signed stick value to [-1000, 1000]."""
        if abs(val) < deadzone:
            return 0
        sign = 1 if val > 0 else -1
        mag = abs(val) - deadzone
        max_mag = 32767 - deadzone
        scaled = int((mag / max_mag) * 1000) * sign
        return max(-1000, min(1000, scaled))

    def _normalize_winmm_axis(self, raw_val: int, deadzone: int = 3500) -> int:
        """
        Normalize WinMM 16-bit unsigned axis (0..65535, center 32767)
        to signed [-1000, 1000] with deadzone around 32767.
        """
        diff = raw_val - 32767
        if abs(diff) < deadzone:
            return 0
        sign = 1 if diff > 0 else -1
        mag = abs(diff) - deadzone
        max_mag = 32767 - deadzone
        scaled = int((mag / max_mag) * 1000) * sign
        return max(-1000, min(1000, scaled))

    def _parse_xinput(self, pad: XINPUT_GAMEPAD, slot: int):
        """Process XInput gamepad data."""
        lx = self._normalize_stick(pad.sThumbLX, 7849)
        ly = self._normalize_stick(pad.sThumbLY, 7849)
        rx = self._normalize_stick(pad.sThumbRX, 8689)
        ry = self._normalize_stick(pad.sThumbRY, 8689)

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

        self._check_button_edges(btn_states)

        with self.state.lock:
            self.state.connected = True
            self.state.controller_name = f"Xbox Controller (Slot {slot})"
            self.state.backend = "XInput (Cable/USB)"
            self.state.last_update_time = time.time()
            self.state.axis_lx = lx
            self.state.axis_ly = ly
            self.state.axis_rx = rx
            self.state.axis_ry = ry
            self.state.trigger_lt = lt
            self.state.trigger_rt = rt
            for k, v in btn_states.items():
                setattr(self.state, k, v)
            self.state.buttons_bitmask = b

    def _parse_winmm(self, info: JOYINFOEX, jid: int):
        """Process WinMM wireless / Bluetooth / DirectInput joystick data."""
        # Standard WinMM axis mapping for wireless gamepads:
        # X: Left Stick X
        # Y: Left Stick Y (Inverted: 0 is up, 65535 is down)
        # Z: Right Stick X (or LT/RT triggers on some gamepads)
        # R: Right Stick Y (Inverted: 0 is up, 65535 is down)
        # U, V: Additional axes
        lx = self._normalize_winmm_axis(info.dwXpos)
        ly = -self._normalize_winmm_axis(info.dwYpos)  # Invert Y so up is positive

        # Handle Right Stick
        rx = self._normalize_winmm_axis(info.dwZpos)
        ry = -self._normalize_winmm_axis(info.dwRpos)

        # Triggers
        lt = 0
        rt = 0
        if info.dwUpos > 0:
            lt = int((info.dwUpos / 65535.0) * 1000)
        if info.dwVpos > 0:
            rt = int((info.dwVpos / 65535.0) * 1000)

        # POV Hat / D-Pad (0 = North, 9000 = East, 18000 = South, 27000 = West, 65535 = Center)
        pov = info.dwPOV
        dp_up = (pov == 0 or pov == 31500 or pov == 4500)
        dp_right = (pov == 9000 or pov == 4500 or pov == 13500)
        dp_down = (pov == 18000 or pov == 13500 or pov == 22500)
        dp_left = (pov == 27000 or pov == 22500 or pov == 31500)

        # Buttons (bits 0..31)
        b = info.dwButtons
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

        self._check_button_edges(btn_states)

        with self.state.lock:
            self.state.connected = True
            self.state.controller_name = f"Wireless Controller #{jid}"
            self.state.backend = "WinMM (Wireless/BT)"
            self.state.last_update_time = time.time()
            self.state.axis_lx = lx
            self.state.axis_ly = ly
            self.state.axis_rx = rx
            self.state.axis_ry = ry
            self.state.trigger_lt = lt
            self.state.trigger_rt = rt
            for k, v in btn_states.items():
                setattr(self.state, k, v)
            self.state.buttons_bitmask = b

    def _check_button_edges(self, btn_states: Dict[str, bool]):
        for name, current in btn_states.items():
            prev = self._prev_buttons.get(name, False)
            if current and not prev:
                self._handle_button_press(name)
        self._prev_buttons = btn_states

    def _handle_button_press(self, btn_name: str):
        if not self.action_callback:
            return

        actions = {
            "btn_start": ("TOGGLE_ARM", None),
            "btn_back": ("CYCLE_MODE", None),
            "btn_a": ("DISARM", None),
            "btn_y": ("CAMERA_TILT_UP", None),
            "btn_x": ("CAMERA_TILT_DOWN", None),
            "btn_rb": ("LIGHTS_CYCLE", None),
            "btn_lb": ("LIGHTS_OFF", None),
            "dpad_up": ("GAIN_INCREASE", None),
            "dpad_down": ("GAIN_DECREASE", None),
        }

        if btn_name in actions:
            action, arg = actions[btn_name]
            try:
                self.action_callback(action, arg)
            except Exception:
                pass

    def _reset_inputs(self):
        self.state.axis_lx = 0
        self.state.axis_ly = 0
        self.state.axis_rx = 0
        self.state.axis_ry = 0
        self.state.trigger_lt = 0
        self.state.trigger_rt = 0
        self.state.buttons_bitmask = 0
