"""
PixDoctorV2 - Vehicle Frame Configuration & Closed-Loop Motor Test View.
Features:
1. Full ArduSub frame catalog (SimpleROV-4 default).
2. Restored Sequence Test Bench (Throttle %, Timeout, Sequence run, Emergency stop).
3. Individual microsecond sliders for each motor (1000..2000µs, direct pin override).
4. Wireless Gamepad integration (drive individual motor or frame directly with sticks).
5. Arduino Nano 33 IoT (PixDoctorNano) physical closed-loop PWM verification (zero jitter).
"""

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional

from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    COLOR_INVERT_BG,
    COLOR_INVERT_FG,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
)
from gui.widgets.mono_widgets import RetroCard, PwmBar
from gui.widgets.thruster_diagram import ThrusterDiagram
from core.ardusub_defs import FRAMES, DEFAULT_FRAME_ID, NANO_PROBE_PINS, ESP32_PROBE_PINS
from core.mavlink_manager import MavlinkManager
from core.nano_probe_manager import NanoProbeManager
from core.param_manager import ParameterManager
from core.gamepad_manager import GamepadManager
from core.motor_matrix_manager import MotorMatrixManager
from gui.widgets.motor_matrix_dialog import MotorMatrixDialog


class ThrusterView(tk.Frame):
    """Thruster geometry, direction setup, individual sliders, and closed-loop hardware testing."""

    def __init__(
        self,
        parent,
        mav_mgr: MavlinkManager,
        nano_mgr: NanoProbeManager,
        param_mgr: ParameterManager,
        gamepad_mgr: Optional[GamepadManager] = None,
        **kwargs
    ):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.mav_mgr = mav_mgr
        self.nano_mgr = nano_mgr
        self.param_mgr = param_mgr
        self.gamepad_mgr = gamepad_mgr

        self.current_frame_id = DEFAULT_FRAME_ID  # SimpleROV-4
        self.testing_motor: int = 0
        self.pwm_bars: List[PwmBar] = []

        # Individual slider controls
        self.slider_vars: List[tk.IntVar] = []
        self.slider_labels: List[tk.Label] = []
        self.slider_widgets: List[ttk.Scale] = []

        # Gamepad control mode in thruster test
        self.gamepad_thruster_active = tk.BooleanVar(value=False)
        self.gamepad_target_motor = tk.IntVar(value=1)
        self._updating_sliders = False

        self.matrix_mgr = MotorMatrixManager.get_instance()
        self.matrix_mgr.register_callback(self._on_matrix_updated)

        self._build_ui()

    def _build_ui(self):
        # Top Frame Selection & Master Control Header
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(6, 4))

        tk.Label(
            top_bar,
            text="[ VEHICLE FRAME & THRUSTER MATRIX ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        ).pack(side=tk.LEFT)

        # Frame Selector Dropdown on Right
        frame_sel_frame = tk.Frame(top_bar, bg=COLOR_BG)
        frame_sel_frame.pack(side=tk.RIGHT)

        tk.Label(
            frame_sel_frame,
            text="FRAME:",
            bg=COLOR_BG,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        ).pack(side=tk.LEFT, padx=(0, 4))

        self.frame_var = tk.StringVar(value=FRAMES[DEFAULT_FRAME_ID]["name"])
        frame_names = [f["name"] for f in FRAMES.values()]
        self.frame_combo = ttk.Combobox(
            frame_sel_frame,
            textvariable=self.frame_var,
            values=frame_names,
            state="readonly",
            width=26
        )
        self.frame_combo.pack(side=tk.LEFT)
        self.frame_combo.bind("<<ComboboxSelected>>", self._on_frame_changed)

        # ---------------- Master Output & Arm Control Strip ----------------
        control_strip = tk.Frame(
            self,
            bg=COLOR_SURFACE,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=8,
            pady=3
        )
        control_strip.pack(fill=tk.X, padx=12, pady=(0, 4))

        # Left: Arm FC Button
        self.btn_thruster_arm = ttk.Button(
            control_strip,
            text="[ ARM FC (BENCH) ]",
            style="Invert.TButton",
            command=self._toggle_arm_bench
        )
        self.btn_thruster_arm.pack(side=tk.LEFT, padx=(0, 8))

        # Gamepad Thruster Drive Toggle (Flight Input)
        chk_gamepad = tk.Checkbutton(
            control_strip,
            text="GAMEPAD FLIGHT INPUT TEST",
            variable=self.gamepad_thruster_active,
            command=self._on_gamepad_toggle,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SURFACE,
            activeforeground=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        chk_gamepad.pack(side=tk.LEFT, padx=6)

        tk.Label(
            control_strip,
            text="(Sticks = Fwd/Lat/Depth/Yaw)",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        ).pack(side=tk.LEFT, padx=(0, 4))

        self.lbl_stream_status = tk.Label(
            control_strip,
            text="[ BENCH TEST READY (20Hz WATCHDOG) ]",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        )
        self.lbl_stream_status.pack(side=tk.LEFT, padx=(8, 0))

        # Right: Quick Emergency Buttons
        ttk.Button(
            control_strip,
            text="RELEASE ALL",
            style="Retro.TButton",
            command=self._release_all
        ).pack(side=tk.RIGHT, padx=2)

        ttk.Button(
            control_strip,
            text="ALL 1500µs",
            style="Retro.TButton",
            command=self._all_neutral
        ).pack(side=tk.RIGHT, padx=2)

        ttk.Button(
            control_strip,
            text="ALL 900µs",
            style="Retro.TButton",
            command=self._all_zero
        ).pack(side=tk.RIGHT, padx=2)

        # Main Layout: Left (Chassis Diagram + Direction Reversals), Right (Sequence Bench + Individual Sliders + Nano Bars)
        grid_frame = tk.Frame(self, bg=COLOR_BG)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)

        # ================= LEFT COLUMN: CHASSIS & MOTOR REVERSE =================
        left_col = tk.Frame(grid_frame, bg=COLOR_BG, width=330)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 8))

        # 1. Frame Geometry Diagram
        diag_card = RetroCard(left_col, title="Frame Thruster Layout")
        diag_card.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.diagram = ThrusterDiagram(
            diag_card.body,
            frame_id=self.current_frame_id,
            on_thruster_click=self._on_thruster_clicked,
            width=310,
            height=250
        )
        self.diagram.pack(fill=tk.BOTH, expand=True)

        # 2. Motor Spin Direction Matrix Card
        dir_card = RetroCard(left_col, title="Spin Direction (MOT_x_DIRECTION)")
        dir_card.pack(fill=tk.X)

        self.dir_frame = tk.Frame(dir_card.body, bg=COLOR_SURFACE)
        self.dir_frame.pack(fill=tk.X)
        self._rebuild_direction_toggles()

        ttk.Button(
            dir_card.body,
            text="[ CONFIGURE MOTOR MATRIX & STICKS ]",
            style="Invert.TButton",
            command=self._open_motor_matrix_dialog
        ).pack(fill=tk.X, pady=(6, 2))

        # ================= RIGHT COLUMN: SEQUENCE TEST + INDIVIDUAL SLIDERS + CLOSED LOOP =================
        right_col = tk.Frame(grid_frame, bg=COLOR_BG)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 1. Restored Sequence & Timed Motor Test Bench Card
        seq_card = RetroCard(right_col, title="Sequence & Timed Motor Test Bench")
        seq_card.pack(fill=tk.X, pady=(0, 6))

        seq_row = tk.Frame(seq_card.body, bg=COLOR_SURFACE)
        seq_row.pack(fill=tk.X, pady=(0, 4))

        # Throttle %
        tk.Label(seq_row, text="THROTTLE %:", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT)
        self.throttle_var = tk.IntVar(value=15)
        self.spin_throttle = ttk.Spinbox(seq_row, from_=5, to=50, textvariable=self.throttle_var, width=4)
        self.spin_throttle.pack(side=tk.LEFT, padx=(4, 10))

        # Timeout seconds
        tk.Label(seq_row, text="TIMEOUT (s):", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT)
        self.duration_var = tk.DoubleVar(value=2.0)
        self.spin_duration = ttk.Spinbox(seq_row, from_=0.5, to=10.0, increment=0.5, textvariable=self.duration_var, width=4)
        self.spin_duration.pack(side=tk.LEFT, padx=(4, 12))

        # Sequence Test Button
        btn_seq = ttk.Button(
            seq_row,
            text="[ TEST ALL IN SEQUENCE ]",
            style="Invert.TButton",
            command=self._start_sequence_test
        )
        btn_seq.pack(side=tk.LEFT, padx=(0, 6))

        # Emergency Stop Button
        btn_stop = ttk.Button(
            seq_row,
            text="STOP ALL",
            style="Retro.TButton",
            command=self._all_neutral
        )
        btn_stop.pack(side=tk.RIGHT)

        # Individual Quick Test Buttons Row
        self.btn_motor_row = tk.Frame(seq_card.body, bg=COLOR_SURFACE)
        self.btn_motor_row.pack(fill=tk.X, pady=(2, 0))
        self._rebuild_motor_test_buttons()

        # 2. Individual Motor Microsecond Sliders Card
        sliders_card = RetroCard(right_col, title="Individual Motor PWM Sliders (Direct Pin Control)")
        sliders_card.pack(fill=tk.X, pady=(0, 6))

        self.sliders_container = tk.Frame(sliders_card.body, bg=COLOR_SURFACE)
        self.sliders_container.pack(fill=tk.X)
        self._rebuild_individual_sliders()

        # 3. Hardware Closed-Loop Output Gauges (ESP32 / Nano)
        bars_card = RetroCard(right_col, title="Physical Output Verification (ESP32 / Nano Probe)")
        bars_card.pack(fill=tk.BOTH, expand=True)

        self.bars_container = tk.Frame(bars_card.body, bg=COLOR_SURFACE)
        self.bars_container.pack(fill=tk.BOTH, expand=True)
        self._rebuild_pwm_bars()

    def _on_frame_changed(self, event=None):
        sel_name = self.frame_var.get()
        for f_id, f_data in FRAMES.items():
            if f_data["name"] == sel_name:
                self.current_frame_id = f_id
                self.diagram.set_frame(f_id)
                self.param_mgr.set_value("FRAME_CONFIG", float(f_id))
                self.mav_mgr.set_param("FRAME_CONFIG", float(f_id))
                self._rebuild_direction_toggles()
                self._rebuild_motor_test_buttons()
                self._rebuild_individual_sliders()
                self._rebuild_pwm_bars()
                # Update gamepad motor choices
                t_count = f_data.get("thruster_count", 4)
                self.cb_gamepad_motor["values"] = list(range(1, t_count + 1))
                break

    def _rebuild_direction_toggles(self):
        for child in self.dir_frame.winfo_children():
            child.destroy()

        frame_data = FRAMES.get(self.current_frame_id, FRAMES[6])
        thrusters = frame_data.get("thrusters", [])
        t_count = len(thrusters) if thrusters else frame_data["thruster_count"]

        for i in range(1, t_count + 1):
            row = tk.Frame(self.dir_frame, bg=COLOR_SURFACE)
            row.pack(fill=tk.X, pady=1)

            t_name = thrusters[i - 1]["name"] if i <= len(thrusters) else f"Motor {i}"
            tk.Label(
                row,
                text=f"M{i} ({t_name}):",
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                font=FONT_SMALL,
                width=24,
                anchor="w"
            ).pack(side=tk.LEFT)

            param_name = f"MOT_{i}_DIRECTION"
            cur_val = self.param_mgr.get_value(param_name, 1.0)
            is_reversed = (cur_val == -1.0)

            btn_text = "[REV]" if is_reversed else "[NORM]"
            btn_style = "Invert.TButton" if is_reversed else "Retro.TButton"

            btn = ttk.Button(
                row,
                text=btn_text,
                style=btn_style,
                width=8,
                command=lambda idx=i: self._toggle_motor_direction(idx)
            )
            btn.pack(side=tk.RIGHT)

    def _open_motor_matrix_dialog(self):
        """Open graphical motor allocation matrix and stick configuration dialog."""
        MotorMatrixDialog(
            self,
            mav_mgr=self.mav_mgr,
            nano_mgr=self.nano_mgr,
            param_mgr=self.param_mgr,
            gamepad_mgr=self.gamepad_mgr
        )

    def _on_matrix_updated(self):
        """Callback when motor matrix or directions change in dialog."""
        self._rebuild_direction_toggles()

    def _toggle_motor_direction(self, motor_idx: int):
        param_name = f"MOT_{motor_idx}_DIRECTION"
        cur_val = self.param_mgr.get_value(param_name, 1.0)
        new_val = -1.0 if cur_val == 1.0 else 1.0
        self.param_mgr.set_value(param_name, new_val)
        self.mav_mgr.set_param(param_name, new_val)
        self.matrix_mgr.set_motor_direction(motor_idx, int(new_val), notify=False)
        self._rebuild_direction_toggles()

    def _rebuild_motor_test_buttons(self):
        """Restored quick test buttons for each motor."""
        for child in self.btn_motor_row.winfo_children():
            child.destroy()

        frame_data = FRAMES.get(self.current_frame_id, FRAMES[6])
        t_count = frame_data.get("thruster_count", 4)

        for i in range(1, t_count + 1):
            btn = ttk.Button(
                self.btn_motor_row,
                text=f"TEST M{i}",
                style="Retro.TButton",
                width=8,
                command=lambda idx=i: self._test_single_motor_pulse(idx)
            )
            btn.pack(side=tk.LEFT, padx=2)

    def _test_single_motor_pulse(self, motor_idx: int):
        pct = float(self.throttle_var.get())
        dur = float(self.duration_var.get())

        self.diagram.set_active_test(motor_idx)
        # Invert or forward based on motor reverse param
        param_name = f"MOT_{motor_idx}_DIRECTION"
        is_rev = (self.param_mgr.get_value(param_name, 1.0) == -1.0)
        sign = -1.0 if is_rev else 1.0
        pwm_val = max(1000, min(2000, int(1500 + (sign * pct * 4.0))))

        idx = motor_idx - 1
        if 0 <= idx < len(self.slider_widgets):
            self.slider_widgets[idx].set(pwm_val)
            self.slider_labels[idx].config(text=f"{pwm_val}µs")

        # Start QGC-style 20Hz continuous motor test stream so ArduSub never disarms!
        self.mav_mgr.start_motor_stream(motor_idx, pwm_val)
        self.nano_mgr.set_commanded_pwm(motor_idx, pwm_val)

        def _clear():
            time.sleep(dur)
            # Smoothly transition to neutral
            self.mav_mgr.start_motor_stream(motor_idx, 1500)
            self.nano_mgr.set_commanded_pwm(motor_idx, 1500)
            if 0 <= idx < len(self.slider_widgets):
                self.slider_widgets[idx].set(1500)
                self.slider_labels[idx].config(text="1500µs")
            time.sleep(0.3)
            self.mav_mgr.stop_motor_stream()
            self.diagram.set_active_test(None)

        threading.Thread(target=_clear, daemon=True).start()

    def _start_sequence_test(self):
        """Restored sequence test running across all frame thrusters in order."""
        frame_data = FRAMES.get(self.current_frame_id, FRAMES[6])
        t_count = frame_data.get("thruster_count", 4)
        dur = float(self.duration_var.get())

        def _seq_worker():
            for i in range(1, t_count + 1):
                self._test_single_motor_pulse(i)
                time.sleep(dur + 0.5)

        threading.Thread(target=_seq_worker, daemon=True).start()

    def _rebuild_individual_sliders(self):
        """Build dedicated microsecond slider for each thruster in the current frame."""
        for child in self.sliders_container.winfo_children():
            child.destroy()

        self.slider_vars.clear()
        self.slider_labels.clear()
        self.slider_widgets.clear()

        frame_data = FRAMES.get(self.current_frame_id, FRAMES[6])
        thrusters = frame_data.get("thrusters", [])
        t_count = len(thrusters) if thrusters else frame_data["thruster_count"]

        for i in range(1, t_count + 1):
            row = tk.Frame(self.sliders_container, bg=COLOR_SURFACE)
            row.pack(fill=tk.X, pady=2)

            t_name = thrusters[i - 1]["name"] if i <= len(thrusters) else f"Motor {i}"

            # Motor Name
            tk.Label(
                row,
                text=f"M{i} ({t_name}):",
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                font=FONT_BODY_BOLD,
                width=22,
                anchor="w"
            ).pack(side=tk.LEFT)

            # Readout label
            lbl_val = tk.Label(
                row,
                text="1500µs",
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                font=FONT_SMALL,
                width=7,
                anchor="w"
            )
            lbl_val.pack(side=tk.LEFT)
            self.slider_labels.append(lbl_val)

            # Slider scale
            scale = ttk.Scale(
                row,
                from_=1000,
                to=2000,
                orient=tk.HORIZONTAL,
                value=1500,
                command=lambda val, idx=i: self._on_slider_moved(idx, val)
            )
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            self.slider_widgets.append(scale)

            # Quick Preset Buttons
            for p_val in (1100, 1500, 1900):
                p_text = "N" if p_val == 1500 else str(p_val)
                ttk.Button(
                    row,
                    text=p_text,
                    style="Retro.TButton",
                    width=4,
                    command=lambda pv=p_val, idx=i: self._set_single_motor_pwm(idx, pv)
                ).pack(side=tk.LEFT, padx=1)

    def _on_slider_moved(self, motor_idx: int, val_str: str):
        """User dragged an individual motor slider."""
        if self._updating_sliders or self.gamepad_thruster_active.get():
            return

        try:
            pwm_val = int(float(val_str))
        except ValueError:
            return

        idx = motor_idx - 1
        if 0 <= idx < len(self.slider_labels):
            self.slider_labels[idx].config(text=f"{pwm_val}µs")

        # Directly command ONLY THIS MOTOR without touching RC mixer
        self.mav_mgr.set_servo_override(motor_idx, pwm_val)
        self.nano_mgr.set_commanded_pwm(motor_idx, pwm_val)

    def _set_single_motor_pwm(self, motor_idx: int, pwm_val: int):
        """Set a single motor to an exact PWM value via preset button."""
        idx = motor_idx - 1
        if 0 <= idx < len(self.slider_widgets):
            self.slider_widgets[idx].set(pwm_val)
            self.slider_labels[idx].config(text=f"{pwm_val}µs")

        self.mav_mgr.set_servo_override(motor_idx, pwm_val)
        self.nano_mgr.set_commanded_pwm(motor_idx, pwm_val)

    def _rebuild_pwm_bars(self):
        for child in self.bars_container.winfo_children():
            child.destroy()
        self.pwm_bars.clear()

        frame_data = FRAMES.get(self.current_frame_id, FRAMES[6])
        thrusters = frame_data.get("thrusters", [])
        t_count = len(thrusters) if thrusters else frame_data["thruster_count"]

        # Fast pin mapping lookups
        nano_map = {item["ch"]: item["pin"] for item in NANO_PROBE_PINS}
        esp32_map = {item["ch"]: item["pin"] for item in ESP32_PROBE_PINS}
        dev_upper = (self.nano_mgr.state.device_info or "").upper()

        for i in range(1, t_count + 1):
            t_name = thrusters[i - 1]["name"] if i <= len(thrusters) else f"Thruster {i}"
            if "ESP32" in dev_upper:
                pin_badge = f"[{esp32_map.get(i, '')}]"
            elif "NANO" in dev_upper or "SAMD21" in dev_upper:
                pin_badge = f"[{nano_map.get(i, '')}]"
            else:
                pin_badge = f"[{esp32_map.get(i, '')} / {nano_map.get(i, '')}]"

            bar = PwmBar(self.bars_container, channel_name=f"M{i} - {t_name} {pin_badge}")
            bar.pack(fill=tk.X, pady=2)
            self.pwm_bars.append(bar)

    def _on_thruster_clicked(self, thruster_idx: int):
        """Click on diagram pulse-tests that motor for 2s at 1650µs."""
        self._test_single_motor_pulse(thruster_idx)

    def _toggle_arm_bench(self):
        curr_armed = self.mav_mgr.state.armed
        if not curr_armed:
            if messagebox.askyesno(
                "Arm FC for Bench Testing",
                "Ensure thrusters are completely clear of obstacles!\n\nProceed to ARM?",
                icon="warning"
            ):
                self.mav_mgr.set_safety_switch(True)
                self.mav_mgr.arm(True, force=True)
        else:
            self.mav_mgr.arm(False)

    def _on_gamepad_toggle(self):
        """When switching to Gamepad Flight Input, cleanly stop motor test streamer and arm if needed."""
        if self.gamepad_thruster_active.get():
            self.mav_mgr.stop_motor_stream()
            self.mav_mgr.set_flight_mode(19)  # ArduSub MANUAL mode
            self.mav_mgr.set_safety_switch(True)
            self.mav_mgr.send_manual_control(0, 0, 0, 0, 0)
        else:
            self._all_neutral()

    def _all_neutral(self):
        """Set all motor sliders to 1500µs neutral without disarming."""
        self.mav_mgr.stop_motor_stream()
        for i in range(1, len(self.slider_widgets) + 1):
            idx = i - 1
            if idx < len(self.slider_widgets):
                self.slider_widgets[idx].set(1500)
                self.slider_labels[idx].config(text="1500µs")
            self.nano_mgr.set_commanded_pwm(i, 1500)

    def _all_zero(self):
        """Kill all motors to 900µs."""
        for i in range(1, len(self.slider_widgets) + 1):
            self._set_single_motor_pwm(i, 900)

    def _release_all(self):
        """Release MAVLink servo overrides and return to neutral."""
        self.mav_mgr.release_servo_overrides()
        for i in range(1, len(self.slider_widgets) + 1):
            idx = i - 1
            if idx < len(self.slider_widgets):
                self.slider_widgets[idx].set(1500)
                self.slider_labels[idx].config(text="1500µs")
            self.nano_mgr.set_commanded_pwm(i, 1500)

    def update_telemetry(self, mav_snap: Dict[str, Any], nano_snap: Dict[str, Any]):
        """Update closed-loop readings and handle Gamepad thruster drive mode."""
        servos = mav_snap.get("servo_raw", [1500] * 8)
        meas_pwms = nano_snap.get("measured_pwm", [0] * 14)
        meas_hzs = nano_snap.get("measured_hz", [0.0] * 14)
        valids = nano_snap.get("signal_valid", [False] * 14)
        armed = mav_snap.get("armed", False)
        statustext = mav_snap.get("statustext", "").lower()

        # Update Arm Button State
        if armed:
            self.btn_thruster_arm.config(text="[ DISARM FC ]", style="Retro.TButton")
        else:
            self.btn_thruster_arm.config(text="[ ARM FC (BENCH) ]", style="Invert.TButton")

        # Update Watchdog / Cooldown Status Label
        if "cooldown" in statustext:
            self.lbl_stream_status.config(text="[ 10s COOLDOWN ACTIVE - STAND BY ]", fg=COLOR_INVERT_BG)
        elif self.gamepad_thruster_active.get():
            self.lbl_stream_status.config(text="[ GAMEPAD FLIGHT INPUT ACTIVE ]", fg=COLOR_TEXT_WHITE)
        elif self.mav_mgr._motor_stream_active:
            self.lbl_stream_status.config(
                text=f"[ 20Hz STREAMING M{self.mav_mgr._motor_stream_ch} @ {self.mav_mgr._motor_stream_pwm}µs ]",
                fg=COLOR_TEXT_WHITE
            )
        else:
            self.lbl_stream_status.config(text="[ BENCH TEST READY (20Hz WATCHDOG) ]", fg=COLOR_TEXT_DIM)

        # Handle Gamepad Thruster Driving Mode (Flight Inputs)
        if self.gamepad_thruster_active.get() and self.gamepad_mgr and self.mav_mgr.is_connected():
            g_snap = self.gamepad_mgr.state.get_snapshot()
            if g_snap.get("connected", False):
                cmds = self.matrix_mgr.extract_gamepad_commands(g_snap)
                fwd = cmds["fwd"]
                lat = cmds["lat"]
                throttle = cmds["depth"]
                yaw = cmds["yaw"]
                buttons = g_snap.get("buttons_bitmask", 0)

                # Send live flight input to Pixhawk!
                self.mav_mgr.send_manual_control(x=fwd, y=lat, z=throttle, r=yaw, buttons=buttons)

                # Update the individual slider widgets to match live PWM outputs from the flight mixer
                self._updating_sliders = True
                try:
                    for s_idx in range(len(self.slider_widgets)):
                        if s_idx < len(servos):
                            curr_pwm = servos[s_idx]
                            self.slider_widgets[s_idx].set(curr_pwm)
                            self.slider_labels[s_idx].config(text=f"{curr_pwm}µs")
                            self.nano_mgr.set_commanded_pwm(s_idx + 1, curr_pwm)
                finally:
                    self._updating_sliders = False

        # Update diagram
        self.diagram.update_pwms(servos)

        # Update PWM Bars with jitter-free fixed-width formatting
        for idx, bar in enumerate(self.pwm_bars):
            cmd_pwm = servos[idx] if idx < len(servos) else 1500
            meas_pwm = meas_pwms[idx] if idx < len(meas_pwms) else 0
            meas_hz = meas_hzs[idx] if idx < len(meas_hzs) else 0.0
            valid = valids[idx] if idx < len(valids) else False

            bar.update_readings(cmd_pwm, meas_pwm, meas_hz, valid)
