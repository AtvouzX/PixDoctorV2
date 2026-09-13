"""
PixDoctorV2 - Motor Allocation Matrix & Flight Stick Configuration UI.
Provides an interactive graphical matrix to configure:
1. Which motor is turned on for Forward, Lateral, Depth, Yaw.
2. Motor spin direction inversion (MOT_x_DIRECTION) with 1100 vs 1900 probe parity.
3. Turning stick assignment (swap Left Stick X vs Right Stick X).
4. Live verification of stick commands vs motor outputs vs logic probe readings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    COLOR_TEXT_FAINT,
    COLOR_INVERT_BG,
    COLOR_INVERT_FG,
    FONT_TITLE,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
)
from gui.widgets.mono_widgets import RetroCard
from core.motor_matrix_manager import MotorMatrixManager, DEFAULT_PRESETS, STICK_MODES
from core.mavlink_manager import MavlinkManager
from core.nano_probe_manager import NanoProbeManager
from core.param_manager import ParameterManager
from core.gamepad_manager import GamepadManager


class MotorMatrixDialog(tk.Toplevel):
    """Configuration Dialog for defining motor participation, directions, and stick steering."""

    def __init__(
        self,
        parent,
        mav_mgr: Optional[MavlinkManager] = None,
        nano_mgr: Optional[NanoProbeManager] = None,
        param_mgr: Optional[ParameterManager] = None,
        gamepad_mgr: Optional[GamepadManager] = None,
        **kwargs
    ):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.title("PixDoctorV2 - Motor Allocation Matrix & Stick Configuration")
        self.geometry("960x720")
        self.minsize(880, 640)
        self.transient(parent)

        self.matrix_mgr = MotorMatrixManager.get_instance()
        self.mav_mgr = mav_mgr
        self.nano_mgr = nano_mgr
        self.param_mgr = param_mgr
        self.gamepad_mgr = gamepad_mgr

        # Local state holders
        self.preset_var = tk.StringVar(value=self.matrix_mgr.active_preset_name)
        self.stick_mode_var = tk.StringVar(value=self.matrix_mgr.stick_mode_key)

        # Matrix cells: axis -> motor_num (1..8) -> tk.StringVar
        self.cell_vars: Dict[str, Dict[int, tk.StringVar]] = {}
        # Direction vars: motor_num (1..8) -> tk.IntVar (1 or -1)
        self.dir_vars: Dict[int, tk.IntVar] = {}

        self._running = True
        self._build_ui()
        self._sync_ui_from_manager()
        self._start_live_telemetry_loop()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self._running = False
        self.destroy()

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self, bg=COLOR_SURFACE, padx=14, pady=8, highlightbackground=COLOR_BORDER, highlightthickness=1)
        header.pack(fill=tk.X, padx=10, pady=(10, 6))

        tk.Label(
            header,
            text="[ THRUSTER ALLOCATION MATRIX & FLIGHT STICK SETUP ]",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_TITLE
        ).pack(side=tk.LEFT)

        # Quick Preset Selector
        preset_frame = tk.Frame(header, bg=COLOR_SURFACE)
        preset_frame.pack(side=tk.RIGHT)

        tk.Label(preset_frame, text="PRESET:", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 6))
        preset_names = list(DEFAULT_PRESETS.keys()) + ["Custom"]
        self.cb_preset = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=preset_names,
            state="readonly",
            width=28
        )
        self.cb_preset.pack(side=tk.LEFT, padx=(0, 6))
        self.cb_preset.bind("<<ComboboxSelected>>", self._on_preset_selected)

        # Main scrollable or two-column body
        body = tk.Frame(self, bg=COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        # 1. Top Section: Interactive Matrix Grid
        matrix_card = RetroCard(body, title="Thruster Participation Matrix (Motion Axis -> Motor Multiplier)")
        matrix_card.pack(fill=tk.X, pady=(0, 6))

        self._build_matrix_grid(matrix_card.body)

        # 2. Middle Section: Two side-by-side cards (Left: Motor Direction Parity, Right: Turning Stick Setup)
        mid_row = tk.Frame(body, bg=COLOR_BG)
        mid_row.pack(fill=tk.X, pady=(0, 6))

        # Left Card: Motor Direction Inversion (MOT_x_DIRECTION)
        dir_card = RetroCard(mid_row, title="Motor Direction & Probe Sync (MOT_x_DIRECTION)")
        dir_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        self._build_directions_card(dir_card.body)

        # Right Card: Stick Mode & Turning Assignment
        stick_card = RetroCard(mid_row, title="Flight Stick Steering (Yaw vs Lateral Mapping)")
        stick_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        self._build_stick_mode_card(stick_card.body)

        # 3. Bottom Section: Live Monitor & Action Buttons
        bot_card = RetroCard(body, title="Live Flight Control & Logic Probe Sync Monitor")
        bot_card.pack(fill=tk.X, pady=(0, 6))
        self._build_live_monitor(bot_card.body)

        # Bottom Action Strip
        act_strip = tk.Frame(self, bg=COLOR_BG)
        act_strip.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            act_strip,
            text="[ SAVE & APPLY TO FLIGHT CONTROLLER ]",
            style="Invert.TButton",
            command=self._apply_and_save
        ).pack(side=tk.RIGHT, padx=(6, 0))

        ttk.Button(
            act_strip,
            text="REVERT TO SAVED",
            style="Retro.TButton",
            command=self._revert
        ).pack(side=tk.RIGHT, padx=6)

        self.lbl_status = tk.Label(
            act_strip,
            text="Ready. Adjust matrix or swap turning stick as desired.",
            bg=COLOR_BG,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        )
        self.lbl_status.pack(side=tk.LEFT)

    def _build_matrix_grid(self, parent: tk.Frame):
        container = tk.Frame(parent, bg=COLOR_SURFACE, padx=6, pady=4)
        container.pack(fill=tk.X)

        # Headers: Axis / Name, M1, M2, M3, M4, M5, M6, M7, M8
        headers = ["MOTION AXIS", "M1 (Port)", "M2 (Stbd)", "M3 (Vert1)", "M4 (Vert2)", "M5 (Aux)", "M6 (Aux)", "M7 (Aux)", "M8 (Aux)"]
        header_frame = tk.Frame(container, bg=COLOR_SURFACE)
        header_frame.pack(fill=tk.X, pady=2)

        for col_idx, h in enumerate(headers):
            w = 18 if col_idx == 0 else 9
            tk.Label(
                header_frame,
                text=h,
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE if col_idx == 0 else COLOR_TEXT_DIM,
                font=FONT_SMALL,
                width=w,
                anchor="w" if col_idx == 0 else "center"
            ).pack(side=tk.LEFT, padx=1)

        # Rows for Forward, Lateral, Depth, Yaw
        axes = [
            ("fwd",   "FORWARD / REVERSE"),
            ("lat",   "LATERAL (STRAFE)"),
            ("depth", "DEPTH (THROTTLE)"),
            ("yaw",   "YAW (TURNING)"),
        ]

        options = ["+1.0", "-1.0", "0.0", "+0.7", "-0.7"]

        for axis_key, axis_label in axes:
            self.cell_vars[axis_key] = {}
            row_frame = tk.Frame(container, bg=COLOR_SURFACE)
            row_frame.pack(fill=tk.X, pady=2)

            tk.Label(
                row_frame,
                text=axis_label,
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                font=FONT_BODY_BOLD,
                width=18,
                anchor="w"
            ).pack(side=tk.LEFT, padx=1)

            for m_idx in range(1, 9):
                var = tk.StringVar(value="0.0")
                self.cell_vars[axis_key][m_idx] = var
                cb = ttk.Combobox(
                    row_frame,
                    textvariable=var,
                    values=options,
                    width=7,
                    state="readonly"
                )
                cb.pack(side=tk.LEFT, padx=3)
                cb.bind("<<ComboboxSelected>>", self._on_cell_changed)

        # Quick Yaw Polarity Differential Flip Bar
        flip_bar = tk.Frame(container, bg=COLOR_SURFACE)
        flip_bar.pack(fill=tk.X, pady=(6, 2))

        ttk.Button(
            flip_bar,
            text="[ ↔ FLIP YAW DIFFERENTIAL ]",
            style="Invert.TButton",
            command=self._flip_yaw_differential
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            flip_bar,
            text="Inverts left/right turning differential without affecting forward/reverse thrust.",
            bg=COLOR_SURFACE,
            fg="#38bdf8",
            font=FONT_SMALL
        ).pack(side=tk.LEFT)

    def _build_directions_card(self, parent: tk.Frame):
        container = tk.Frame(parent, bg=COLOR_SURFACE, padx=6, pady=4)
        container.pack(fill=tk.BOTH, expand=True)

        note_box = tk.Label(
            container,
            text="* If probe reads 1100µs when commanding 1900µs (e.g. M3/M4 Depth), set direction to [REV -1].\n"
                 "  This syncs Pixhawk electrical output and logic probe directly with the HUD.",
            bg=COLOR_SURFACE,
            fg="#38bdf8",
            font=FONT_SMALL,
            justify=tk.LEFT,
            wraplength=420
        )
        note_box.pack(fill=tk.X, pady=(0, 6))

        grid = tk.Frame(container, bg=COLOR_SURFACE)
        grid.pack(fill=tk.X)

        self.dir_btn_widgets: Dict[int, ttk.Button] = {}

        for i in range(1, 9):
            col = (i - 1) % 4
            row = (i - 1) // 4
            if col == 0:
                row_f = tk.Frame(grid, bg=COLOR_SURFACE)
                row_f.pack(fill=tk.X, pady=2)

            self.dir_vars[i] = tk.IntVar(value=1)
            f = tk.Frame(row_f, bg=COLOR_SURFACE)
            f.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

            tk.Label(f, text=f"M{i}:", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT)
            btn = ttk.Button(
                f,
                text="[NORM +1]",
                style="Retro.TButton",
                width=9,
                command=lambda idx=i: self._toggle_motor_dir(idx)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.dir_btn_widgets[i] = btn

    def _build_stick_mode_card(self, parent: tk.Frame):
        container = tk.Frame(parent, bg=COLOR_SURFACE, padx=6, pady=4)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            container,
            text="TURNING / YAW STEERING STICK:",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        ).pack(anchor="w", pady=(0, 2))

        # Radio options for quick stick assignment
        modes = [
            ("STANDARD_ROV", "Standard Submarine: Turn on Left Stick X (Depth & Yaw on Left Stick)"),
            ("FPS_CAR", "FPS Game / Car: Turn on Right Stick X (Forward & Yaw on Right Stick)"),
            ("RIGHT_ONLY_HORIZ", "Single-Stick Horizontal: Turn on Right Stick X, Lateral Disabled (SimpleROV-4)")
        ]

        for m_key, m_desc in modes:
            rb = tk.Radiobutton(
                container,
                text=m_desc,
                variable=self.stick_mode_var,
                value=m_key,
                command=self._on_stick_mode_changed,
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                selectcolor=COLOR_BG,
                activebackground=COLOR_SURFACE,
                activeforeground=COLOR_TEXT_WHITE,
                font=FONT_SMALL,
                justify=tk.LEFT
            )
            rb.pack(anchor="w", pady=1)

        # Quick 1-click swap button
        swap_frame = tk.Frame(container, bg=COLOR_SURFACE)
        swap_frame.pack(fill=tk.X, pady=(6, 2))

        ttk.Button(
            swap_frame,
            text="[ ↔ SWAP TURNING STICK: LEFT <-> RIGHT ]",
            style="Invert.TButton",
            command=self._swap_turning_stick
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_stick_info = tk.Label(
            swap_frame,
            text="Current Yaw: Left Stick X | Current Lateral: Right Stick X",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        )
        self.lbl_stick_info.pack(side=tk.LEFT)

    def _build_live_monitor(self, parent: tk.Frame):
        container = tk.Frame(parent, bg=COLOR_SURFACE, padx=6, pady=4)
        container.pack(fill=tk.X)

        # Gamepad readouts
        self.lbl_pad_readout = tk.Label(
            container,
            text="PILOT STICKS -> Fwd: +0 | Lat: +0 | Depth: +0 | Yaw: +0 | Gain: 50%",
            bg=COLOR_SURFACE,
            fg="#00ff88",
            font=FONT_BODY_BOLD,
            anchor="w"
        )
        self.lbl_pad_readout.pack(fill=tk.X, pady=(0, 4))

        # Live motor comparison strip
        self.lbl_motors_readout = tk.Label(
            container,
            text="MOTOR OUTPUTS (Cmd vs Probe) -> M1: 1500 (P:--) | M2: 1500 (P:--) | M3: 1500 (P:--) | M4: 1500 (P:--)",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_SMALL,
            anchor="w"
        )
        self.lbl_motors_readout.pack(fill=tk.X)

    def _sync_ui_from_manager(self):
        snap = self.matrix_mgr.get_snapshot()
        self.preset_var.set(snap["active_preset"])
        self.stick_mode_var.set(snap["stick_mode"])

        matrix = snap["matrix"]
        for axis, row in matrix.items():
            if axis in self.cell_vars:
                for m_idx, weight in row.items():
                    val_str = f"{weight:+.1f}" if weight != 0 else "0.0"
                    if m_idx in self.cell_vars[axis]:
                        self.cell_vars[axis][m_idx].set(val_str)

        dirs = snap["motor_directions"]
        for m_idx, d_val in dirs.items():
            if m_idx in self.dir_vars:
                self.dir_vars[m_idx].set(d_val)
                self._update_dir_button_appearance(m_idx, d_val)

        self._update_stick_info_label()

    def _update_dir_button_appearance(self, m_idx: int, d_val: int):
        btn = self.dir_btn_widgets.get(m_idx)
        if btn:
            if d_val == -1:
                btn.config(text="[REV -1]", style="Invert.TButton")
            else:
                btn.config(text="[NORM +1]", style="Retro.TButton")

    def _toggle_motor_dir(self, m_idx: int):
        curr = self.dir_vars[m_idx].get()
        new_val = -1 if curr == 1 else 1
        self.dir_vars[m_idx].set(new_val)
        self._update_dir_button_appearance(m_idx, new_val)
        self.matrix_mgr.set_motor_direction(m_idx, new_val, notify=True)

        # Update Pixhawk parameter MOT_x_DIRECTION
        param_name = f"MOT_{m_idx}_DIRECTION"
        if self.param_mgr:
            self.param_mgr.set_value(param_name, float(new_val))
        if self.mav_mgr and self.mav_mgr.is_connected():
            self.mav_mgr.set_param(param_name, float(new_val))

        self.lbl_status.config(
            text=f"Updated Motor {m_idx} direction to {'REVERSED (-1)' if new_val == -1 else 'NORMAL (+1)'}.",
            fg="#00ff88"
        )

    def _on_cell_changed(self, event=None):
        self.preset_var.set("Custom")
        for axis, row in self.cell_vars.items():
            for m_idx, var in row.items():
                try:
                    w = float(var.get())
                    self.matrix_mgr.set_matrix_weight(axis, m_idx, w, notify=False)
                except ValueError:
                    pass
        self.matrix_mgr.save_to_file()
        self.lbl_status.config(text="Custom thruster weights updated.", fg=COLOR_TEXT_WHITE)

    def _on_preset_selected(self, event=None):
        name = self.preset_var.get()
        if name in DEFAULT_PRESETS:
            self.matrix_mgr.apply_preset(name, notify=True)
            self._sync_ui_from_manager()
            # Also sync Pixhawk parameters
            if self.mav_mgr and self.mav_mgr.is_connected():
                for m_idx, d_val in self.matrix_mgr.motor_directions.items():
                    p_name = f"MOT_{m_idx}_DIRECTION"
                    if self.param_mgr:
                        self.param_mgr.set_value(p_name, float(d_val))
                    self.mav_mgr.set_param(p_name, float(d_val))
            self.lbl_status.config(text=f"Loaded preset: {name}", fg="#00ff88")

    def _on_stick_mode_changed(self):
        m_key = self.stick_mode_var.get()
        self.matrix_mgr.set_stick_mode(m_key, notify=True)
        self._update_stick_info_label()
        self.lbl_status.config(text=f"Stick steering mode updated to: {STICK_MODES[m_key]['name']}", fg="#00ff88")

    def _swap_turning_stick(self):
        self.matrix_mgr.swap_turning_stick()
        self.stick_mode_var.set(self.matrix_mgr.stick_mode_key)
        self._update_stick_info_label()
        self.lbl_status.config(text=f"Swapped turning stick to {self.matrix_mgr.axis_mappings['yaw']}!", fg="#00ff88")

    def _flip_yaw_differential(self):
        """Inverts the sign of all active yaw matrix weights."""
        self.matrix_mgr.invert_yaw_differential(notify=True)
        # Refresh cell comboboxes for yaw row
        for m_idx in range(1, 9):
            w = self.matrix_mgr.matrix["yaw"].get(m_idx, 0.0)
            if m_idx in self.cell_vars["yaw"]:
                self.cell_vars["yaw"][m_idx].set(f"{w:+.1f}" if abs(w) > 0.001 else "0.0")
        self.preset_var.set("Custom")
        self.lbl_status.config(text="Yaw differential polarity inverted! (Forward thrust preserved)", fg="#00ff88")

    def _update_stick_info_label(self):
        yaw_ch = self.matrix_mgr.axis_mappings.get("yaw", "axis_lx")
        lat_ch = self.matrix_mgr.axis_mappings.get("lat", "axis_rx")
        yaw_str = "Right Stick X" if yaw_ch == "axis_rx" else ("Left Stick X" if yaw_ch == "axis_lx" else yaw_ch)
        lat_str = "Right Stick X" if lat_ch == "axis_rx" else ("Left Stick X" if lat_ch == "axis_lx" else ("Disabled" if lat_ch == "none" else lat_ch))
        self.lbl_stick_info.config(text=f"Current Yaw: {yaw_str} | Current Lateral: {lat_str}")

    def _apply_and_save(self):
        # Save matrix
        for axis, row in self.cell_vars.items():
            for m_idx, var in row.items():
                try:
                    w = float(var.get())
                    self.matrix_mgr.set_matrix_weight(axis, m_idx, w, notify=False)
                except ValueError:
                    pass

        # Save directions
        for m_idx, var in self.dir_vars.items():
            self.matrix_mgr.set_motor_direction(m_idx, var.get(), notify=False)

        self.matrix_mgr.save_to_file()

        # Commit to Pixhawk parameters
        if self.mav_mgr and self.mav_mgr.is_connected():
            for m_idx, d_val in self.matrix_mgr.motor_directions.items():
                p_name = f"MOT_{m_idx}_DIRECTION"
                if self.param_mgr:
                    self.param_mgr.set_value(p_name, float(d_val))
                self.mav_mgr.set_param(p_name, float(d_val))
            msg = "Saved configuration and synced MOT_x_DIRECTION parameters to Pixhawk!"
        else:
            msg = "Saved configuration locally. Connect to Pixhawk to upload parameters."

        self.lbl_status.config(text=msg, fg="#00ff88")
        messagebox.showinfo("Configuration Saved", msg, parent=self)

    def _revert(self):
        self.matrix_mgr.load_from_file()
        self._sync_ui_from_manager()
        self.lbl_status.config(text="Reverted all changes to saved file.", fg=COLOR_TEXT_WHITE)

    def _start_live_telemetry_loop(self):
        if not self._running:
            return

        # Fetch gamepad snapshot
        pad_snap = self.gamepad_mgr.state.get_snapshot() if self.gamepad_mgr else None
        cmds = self.matrix_mgr.extract_gamepad_commands(pad_snap)
        gain_pct = int((pad_snap.get("gain", 0.50) if pad_snap else 0.50) * 100)

        fwd, lat, depth, yaw = cmds["fwd"], cmds["lat"], cmds["depth"], cmds["yaw"]
        self.lbl_pad_readout.config(
            text=f"PILOT STICKS -> Fwd: {fwd:+4d} | Lat: {lat:+4d} | Depth: {depth:+4d} | Yaw: {yaw:+4d} | Gain: {gain_pct}%"
        )

        # Compute calculated PWMs
        calc_pwms = self.matrix_mgr.compute_motor_pwms(fwd, lat, depth, yaw, armed=True)

        # Fetch measured probe PWMs
        meas_pwms = self.nano_mgr.state.measured_pwm if self.nano_mgr else [0] * 8
        valids = self.nano_mgr.state.signal_valid if self.nano_mgr else [False] * 8

        # Build comparison string for M1..M4
        parts = []
        for i in range(4):
            c_pwm = calc_pwms[i]
            is_v = valids[i] if i < len(valids) else False
            p_pwm = meas_pwms[i] if (is_v and i < len(meas_pwms)) else 0
            p_str = f"{p_pwm}" if is_v else "--"
            delta = (p_pwm - c_pwm) if is_v else 0
            flag = " [SYNC!]" if (is_v and abs(delta) <= 25) else (" [INV?]" if (is_v and abs(p_pwm + c_pwm - 3000) <= 50) else "")
            parts.append(f"M{i+1}: {c_pwm} (P:{p_str}{flag})")

        self.lbl_motors_readout.config(
            text="MOTOR OUTPUTS (Cmd vs Probe) -> " + " | ".join(parts)
        )

        self.after(50, self._start_live_telemetry_loop)
