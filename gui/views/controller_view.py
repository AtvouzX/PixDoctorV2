"""
PixDoctorV2 - Comprehensive Wireless Gamepad & XInput Controller Workbench.
Provides interactive mapping visualization, physical axis calibration, zero-tare
drift compensation, exponential curve tuning, and customizable button action mapping.
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
    COLOR_INVERT_BG,
    COLOR_INVERT_FG,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
    FONT_MONO,
)
from gui.widgets.mono_widgets import RetroCard
from gui.widgets.gamepad_overlay import GamepadOverlay
from core.gamepad_manager import GamepadManager, GAMEPAD_ACTIONS, DEFAULT_BUTTON_MAPPINGS
from core.mavlink_manager import MavlinkManager


BUTTON_DISPLAY_NAMES = [
    ("btn_start", "START"),
    ("btn_back", "BACK"),
    ("btn_a", "BUTTON A"),
    ("btn_b", "BUTTON B"),
    ("btn_x", "BUTTON X"),
    ("btn_y", "BUTTON Y"),
    ("btn_lb", "LEFT BUMPER (LB)"),
    ("btn_rb", "RIGHT BUMPER (RB)"),
    ("btn_l3", "LEFT STICK CLICK (L3)"),
    ("btn_r3", "RIGHT STICK CLICK (R3)"),
    ("dpad_up", "D-PAD UP"),
    ("dpad_down", "D-PAD DOWN"),
    ("dpad_left", "D-PAD LEFT"),
    ("dpad_right", "D-PAD RIGHT"),
]


class ControllerView(tk.Frame):
    """Full-featured wireless gamepad testing, calibration, and mapping view."""

    def __init__(
        self,
        parent,
        gamepad_mgr: GamepadManager,
        mav_mgr: MavlinkManager,
        **kwargs
    ):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.gamepad_mgr = gamepad_mgr
        self.mav_mgr = mav_mgr
        self.streaming_enabled = tk.BooleanVar(value=True)

        # Calibration Tk variables
        self.deadzone_var = tk.DoubleVar(value=self.gamepad_mgr.state.deadzone_pct * 100)
        self.expo_var = tk.DoubleVar(value=self.gamepad_mgr.state.expo * 100)
        self.inv_lx_var = tk.BooleanVar(value=self.gamepad_mgr.state.invert_lx)
        self.inv_ly_var = tk.BooleanVar(value=self.gamepad_mgr.state.invert_ly)
        self.inv_rx_var = tk.BooleanVar(value=self.gamepad_mgr.state.invert_rx)
        self.inv_ry_var = tk.BooleanVar(value=self.gamepad_mgr.state.invert_ry)

        # Mapping Tk variables
        self.selected_btn_var = tk.StringVar(value="btn_start")
        self.selected_action_var = tk.StringVar(value="TOGGLE_ARM")

        self._build_ui()

    def _build_ui(self):
        # 1. Top Section: Interactive HUD Visualizer
        top_card = RetroCard(self, title="Live Controller & Mapping Visualizer")
        top_card.pack(fill=tk.X, padx=12, pady=(10, 6))

        # Visualizer Canvas
        self.overlay = GamepadOverlay(top_card.body, on_button_selected=self._on_visualizer_button_clicked)
        self.overlay.pack(fill=tk.BOTH, expand=True)

        # Control Strip below visualizer
        ctrl_bar = tk.Frame(top_card.body, bg=COLOR_SURFACE)
        ctrl_bar.pack(fill=tk.X, pady=(8, 0))

        # Stream Toggle
        chk_stream = tk.Checkbutton(
            ctrl_bar,
            text="TRANSMIT MANUAL_CONTROL (20Hz)",
            variable=self.streaming_enabled,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SURFACE,
            activeforeground=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        chk_stream.pack(side=tk.LEFT, padx=(0, 16))

        # Gain Selector Buttons
        tk.Label(ctrl_bar, text="THRUST GAIN:", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 6))
        for g_pct, g_val in [(25, 0.25), (50, 0.50), (75, 0.75), (100, 1.00)]:
            ttk.Button(
                ctrl_bar,
                text=f"{g_pct}%",
                style="Retro.TButton",
                width=5,
                command=lambda v=g_val: self.gamepad_mgr.set_gain(v)
            ).pack(side=tk.LEFT, padx=2)

        # 2. Bottom Section: Split Columns (Calibration & Mapping)
        bot_split = tk.Frame(self, bg=COLOR_BG)
        bot_split.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 10))

        # Left: Stick Calibration & Tuning Card
        cal_card = RetroCard(bot_split, title="Stick & Trigger Calibration")
        cal_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self._build_calibration_panel(cal_card.body)

        # Right: Button Mapping Workbench Card
        map_card = RetroCard(bot_split, title="Button Action Remapping Workbench")
        map_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        self._build_mapping_panel(map_card.body)

    def _build_calibration_panel(self, parent: tk.Frame):
        """Constructs calibration, zero-tare, deadzone, and expo controls."""
        # A. Zero-Tare Center Drift Section
        tare_frame = tk.Frame(parent, bg=COLOR_SURFACE)
        tare_frame.pack(fill=tk.X, pady=(0, 8))

        self.lbl_tare_status = tk.Label(
            tare_frame,
            text="CENTER OFFSETS: LX: +0 | LY: +0 | RX: +0 | RY: +0",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_MONO
        )
        self.lbl_tare_status.pack(anchor="w", pady=(0, 4))

        tare_btn_row = tk.Frame(tare_frame, bg=COLOR_SURFACE)
        tare_btn_row.pack(fill=tk.X)

        ttk.Button(
            tare_btn_row,
            text="[ ZERO-TARE STICK CENTERS ]",
            style="Invert.TButton",
            command=self._calibrate_centers
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            tare_btn_row,
            text="RESET ZERO",
            style="Retro.TButton",
            command=self._reset_centers
        ).pack(side=tk.LEFT)

        # B. Deadzone Tuning Slider
        dz_frame = tk.Frame(parent, bg=COLOR_SURFACE)
        dz_frame.pack(fill=tk.X, pady=6)

        dz_hdr = tk.Frame(dz_frame, bg=COLOR_SURFACE)
        dz_hdr.pack(fill=tk.X)
        tk.Label(dz_hdr, text="STICK DEADZONE:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL).pack(side=tk.LEFT)
        self.lbl_dz_val = tk.Label(dz_hdr, text=f"{int(self.deadzone_var.get())}%", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL)
        self.lbl_dz_val.pack(side=tk.RIGHT)

        scale_dz = ttk.Scale(
            dz_frame,
            from_=0,
            to=30,
            variable=self.deadzone_var,
            orient=tk.HORIZONTAL,
            command=self._on_deadzone_changed
        )
        scale_dz.pack(fill=tk.X, pady=2)

        # Quick preset buttons for deadzone
        preset_dz_row = tk.Frame(dz_frame, bg=COLOR_SURFACE)
        preset_dz_row.pack(fill=tk.X)
        for pct in (5, 10, 15, 20):
            ttk.Button(
                preset_dz_row,
                text=f"{pct}%",
                style="Retro.TButton",
                width=5,
                command=lambda p=pct: self._set_deadzone_preset(p)
            ).pack(side=tk.LEFT, padx=2)

        # C. Exponential Sensitivity Curve (Expo)
        expo_frame = tk.Frame(parent, bg=COLOR_SURFACE)
        expo_frame.pack(fill=tk.X, pady=6)

        expo_hdr = tk.Frame(expo_frame, bg=COLOR_SURFACE)
        expo_hdr.pack(fill=tk.X)
        tk.Label(expo_hdr, text="EXPO RESPONSE CURVE (FINE PILOTING):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL).pack(side=tk.LEFT)
        self.lbl_expo_val = tk.Label(expo_hdr, text=f"{int(self.expo_var.get())}%", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL)
        self.lbl_expo_val.pack(side=tk.RIGHT)

        scale_expo = ttk.Scale(
            expo_frame,
            from_=0,
            to=60,
            variable=self.expo_var,
            orient=tk.HORIZONTAL,
            command=self._on_expo_changed
        )
        scale_expo.pack(fill=tk.X, pady=2)

        # D. Axis Inversion Checkboxes
        inv_card = tk.Frame(parent, bg=COLOR_SURFACE)
        inv_card.pack(fill=tk.X, pady=(6, 0))
        tk.Label(inv_card, text="AXIS POLARITY INVERSION:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL).pack(anchor="w", pady=(0, 4))

        inv_grid = tk.Frame(inv_card, bg=COLOR_SURFACE)
        inv_grid.pack(fill=tk.X)

        tk.Checkbutton(
            inv_grid,
            text="INVERT YAW (LX)",
            variable=self.inv_lx_var,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            font=FONT_SMALL,
            command=lambda: self.gamepad_mgr.set_inversion("lx", self.inv_lx_var.get())
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        tk.Checkbutton(
            inv_grid,
            text="INVERT DEPTH (LY)",
            variable=self.inv_ly_var,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            font=FONT_SMALL,
            command=lambda: self.gamepad_mgr.set_inversion("ly", self.inv_ly_var.get())
        ).grid(row=0, column=1, sticky="w")

        tk.Checkbutton(
            inv_grid,
            text="INVERT STRAFE (RX)",
            variable=self.inv_rx_var,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            font=FONT_SMALL,
            command=lambda: self.gamepad_mgr.set_inversion("rx", self.inv_rx_var.get())
        ).grid(row=1, column=0, sticky="w", padx=(0, 10))

        tk.Checkbutton(
            inv_grid,
            text="INVERT FWD/REV (RY)",
            variable=self.inv_ry_var,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            font=FONT_SMALL,
            command=lambda: self.gamepad_mgr.set_inversion("ry", self.inv_ry_var.get())
        ).grid(row=1, column=1, sticky="w")

    def _build_mapping_panel(self, parent: tk.Frame):
        """Constructs button remapping editor, action dropdowns, and presets."""
        # Top Remap Row: Button Selector + Action Dropdown + Apply
        assign_box = tk.Frame(parent, bg=COLOR_SURFACE)
        assign_box.pack(fill=tk.X, pady=(0, 6))

        row1 = tk.Frame(assign_box, bg=COLOR_SURFACE)
        row1.pack(fill=tk.X, pady=2)

        tk.Label(row1, text="BUTTON:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=10, anchor="w").pack(side=tk.LEFT)
        self.cb_btn = ttk.Combobox(
            row1,
            textvariable=self.selected_btn_var,
            values=[k for k, _ in BUTTON_DISPLAY_NAMES],
            state="readonly",
            width=16
        )
        self.cb_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.cb_btn.bind("<<ComboboxSelected>>", self._on_btn_combo_selected)

        row2 = tk.Frame(assign_box, bg=COLOR_SURFACE)
        row2.pack(fill=tk.X, pady=2)

        tk.Label(row2, text="ACTION:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=10, anchor="w").pack(side=tk.LEFT)
        action_keys = list(GAMEPAD_ACTIONS.keys())
        self.cb_action = ttk.Combobox(
            row2,
            textvariable=self.selected_action_var,
            values=action_keys,
            state="readonly",
            width=22
        )
        self.cb_action.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            row2,
            text="[ ASSIGN ]",
            style="Invert.TButton",
            command=self._apply_single_mapping
        ).pack(side=tk.LEFT)

        # Mapping Table (Scrollable Treeview)
        tbl_frame = tk.Frame(parent, bg=COLOR_SURFACE)
        tbl_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        columns = ("btn", "action")
        self.tree_map = ttk.Treeview(
            tbl_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse"
        )
        self.tree_map.heading("btn", text="BUTTON")
        self.tree_map.heading("action", text="ASSIGNED ROV ACTION")
        self.tree_map.column("btn", width=110, anchor="w")
        self.tree_map.column("action", width=220, anchor="w")

        scroll = ttk.Scrollbar(tbl_frame, orient=tk.VERTICAL, command=self.tree_map.yview)
        self.tree_map.configure(yscrollcommand=scroll.set)
        self.tree_map.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_map.bind("<<TreeviewSelect>>", self._on_tree_item_selected)

        # Populate treeview
        self._refresh_mapping_tree()

        # Bottom Action Buttons
        btn_bar = tk.Frame(parent, bg=COLOR_SURFACE)
        btn_bar.pack(fill=tk.X, pady=(6, 0))

        ttk.Button(
            btn_bar,
            text="DEFAULT ARDUSUB",
            style="Retro.TButton",
            command=self._reset_mappings
        ).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(
            btn_bar,
            text="CAMERA OPERATOR",
            style="Retro.TButton",
            command=self._preset_camera_operator
        ).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(
            btn_bar,
            text="[ SAVE TO FILE ]",
            style="Retro.TButton",
            command=self._save_config
        ).pack(side=tk.RIGHT)

    def _on_visualizer_button_clicked(self, btn_name: str):
        """When user clicks a button on the visualizer canvas, select it in the editor."""
        self.selected_btn_var.set(btn_name)
        curr_action = self.gamepad_mgr.state.button_mappings.get(btn_name, "NONE")
        self.selected_action_var.set(curr_action)
        # Select in treeview
        for item in self.tree_map.get_children():
            if self.tree_map.item(item, "values")[0] == btn_name:
                self.tree_map.selection_set(item)
                self.tree_map.see(item)
                break

    def _on_btn_combo_selected(self, event=None):
        btn = self.selected_btn_var.get()
        curr_action = self.gamepad_mgr.state.button_mappings.get(btn, "NONE")
        self.selected_action_var.set(curr_action)
        self.overlay.set_selected_button(btn)

    def _on_tree_item_selected(self, event=None):
        sel = self.tree_map.selection()
        if sel:
            vals = self.tree_map.item(sel[0], "values")
            btn = vals[0]
            action = vals[1]
            self.selected_btn_var.set(btn)
            self.selected_action_var.set(action)
            self.overlay.set_selected_button(btn)

    def _apply_single_mapping(self):
        btn = self.selected_btn_var.get()
        action = self.selected_action_var.get()
        self.gamepad_mgr.set_button_mapping(btn, action)
        self._refresh_mapping_tree()
        self.overlay.redraw()

    def _refresh_mapping_tree(self):
        for item in self.tree_map.get_children():
            self.tree_map.delete(item)

        mappings = self.gamepad_mgr.state.button_mappings
        for btn_key, _ in BUTTON_DISPLAY_NAMES:
            action = mappings.get(btn_key, "NONE")
            self.tree_map.insert("", tk.END, values=(btn_key, action))

    def _reset_mappings(self):
        self.gamepad_mgr.reset_mappings_to_default()
        self._refresh_mapping_tree()
        self.overlay.redraw()

    def _preset_camera_operator(self):
        """Preset prioritizing dual camera tilt and lumen lights control."""
        cam_map = {
            "btn_start": "TOGGLE_ARM",
            "btn_back": "CYCLE_MODE",
            "btn_a": "DISARM",
            "btn_b": "CAMERA_TILT_CENTER",
            "btn_x": "CAMERA_TILT_DOWN",
            "btn_y": "CAMERA_TILT_UP",
            "btn_lb": "LIGHTS_OFF",
            "btn_rb": "LIGHTS_CYCLE",
            "btn_l3": "NONE",
            "btn_r3": "CAMERA_TILT_CENTER",
            "dpad_up": "CAMERA_TILT_UP",
            "dpad_down": "CAMERA_TILT_DOWN",
            "dpad_left": "LIGHTS_OFF",
            "dpad_right": "LIGHTS_CYCLE",
        }
        for k, v in cam_map.items():
            self.gamepad_mgr.set_button_mapping(k, v)
        self._refresh_mapping_tree()
        self.overlay.redraw()

    def _calibrate_centers(self):
        self.gamepad_mgr.calibrate_centers()
        messagebox.showinfo("Stick Calibration", "Stick centers zero-tared successfully!\nStick drift offsets recorded.")

    def _reset_centers(self):
        self.gamepad_mgr.reset_calibration()
        self.deadzone_var.set(10.0)
        self.expo_var.set(0.0)
        self.inv_lx_var.set(False)
        self.inv_ly_var.set(False)
        self.inv_rx_var.set(False)
        self.inv_ry_var.set(False)
        messagebox.showinfo("Calibration Reset", "All stick offsets and inversions reset to defaults.")

    def _set_deadzone_preset(self, pct: int):
        self.deadzone_var.set(pct)
        self.lbl_dz_val.config(text=f"{pct}%")
        self.gamepad_mgr.set_deadzone(pct / 100.0)

    def _on_deadzone_changed(self, val):
        pct = int(float(val))
        self.lbl_dz_val.config(text=f"{pct}%")
        self.gamepad_mgr.set_deadzone(pct / 100.0)

    def _on_expo_changed(self, val):
        pct = int(float(val))
        self.lbl_expo_val.config(text=f"{pct}%")
        self.gamepad_mgr.set_expo(pct / 100.0)

    def _save_config(self):
        self.gamepad_mgr.save_config()
        messagebox.showinfo("Configuration Saved", "Gamepad calibration and mappings saved to gamepad_config.json")

    def update_gamepad_telemetry(self, state_dict: Dict[str, Any]):
        """Update live visualizer and transmit MANUAL_CONTROL if enabled."""
        self.overlay.update_gamepad_state(state_dict)

        # Update live center offset display
        off_lx = state_dict.get("center_offset_lx", 0)
        off_ly = state_dict.get("center_offset_ly", 0)
        off_rx = state_dict.get("center_offset_rx", 0)
        off_ry = state_dict.get("center_offset_ry", 0)
        self.lbl_tare_status.config(
            text=f"CENTER OFFSETS: LX:{off_lx:+5d} | LY:{off_ly:+5d} | RX:{off_rx:+5d} | RY:{off_ry:+5d}"
        )

        # Auto-highlight recently pressed button in treeview if user is binding
        last_pressed = state_dict.get("last_pressed_button")
        if last_pressed and self.overlay.selected_button != last_pressed:
            # Subtle indicator
            pass

        if self.streaming_enabled.get() and state_dict.get("connected", False) and self.mav_mgr.is_connected():
            gain = state_dict.get("gain", 0.5)
            # ArduSub MANUAL_CONTROL mapping:
            # x: Forward / Reverse (-1000..1000)
            # y: Lateral Strafe (-1000..1000)
            # z: Throttle / Depth (0..1000)
            # r: Yaw Turn (-1000..1000)
            fwd = int(state_dict.get("axis_ry", 0) * gain)
            lat = int(state_dict.get("axis_rx", 0) * gain)
            throttle = int(state_dict.get("axis_ly", 0) * gain)
            yaw = int(state_dict.get("axis_lx", 0) * gain)
            buttons = state_dict.get("buttons_bitmask", 0)

            self.mav_mgr.send_manual_control(x=fwd, y=lat, z=throttle, r=yaw, buttons=buttons)
