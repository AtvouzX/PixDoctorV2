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
from core.gamepad_manager import (
    GamepadManager,
    GAMEPAD_ACTIONS,
    DEFAULT_BUTTON_MAPPINGS,
    WIRELESS_PROFILES,
)
from core.mavlink_manager import MavlinkManager
from core.motor_matrix_manager import MotorMatrixManager
from gui.widgets.motor_matrix_dialog import MotorMatrixDialog


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
        self.matrix_mgr = MotorMatrixManager.get_instance()

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
        self.gamepad_mgr.register_profile_callback(lambda name: self.after(0, self._sync_controls_from_manager))
        self.gamepad_mgr.register_change_callback(lambda: self.after(0, self._update_dirty_status))
        self._update_dirty_status()

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

        ttk.Button(
            ctrl_bar,
            text="[ CONFIGURE MOTOR MATRIX & STICKS ]",
            style="Invert.TButton",
            command=self._open_motor_matrix_dialog
        ).pack(side=tk.RIGHT, padx=4)

        # 2. Profile Management Bar
        prof_bar = tk.Frame(
            self,
            bg=COLOR_SURFACE,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=10,
            pady=6
        )
        prof_bar.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(
            prof_bar,
            text="PROFILE:",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        ).pack(side=tk.LEFT, padx=(0, 4))

        self.profile_var = tk.StringVar(value=self.gamepad_mgr.get_active_profile_name())
        self.cb_profiles = ttk.Combobox(
            prof_bar,
            textvariable=self.profile_var,
            values=self.gamepad_mgr.get_profile_names(),
            state="readonly",
            width=18
        )
        self.cb_profiles.pack(side=tk.LEFT, padx=(0, 8))
        self.cb_profiles.bind("<<ComboboxSelected>>", self._on_profile_selected)

        ttk.Button(
            prof_bar,
            text="+ NEW",
            style="Invert.TButton",
            width=6,
            command=self._create_new_profile
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            prof_bar,
            text="SAVE",
            style="Invert.TButton",
            width=6,
            command=self._save_active_profile
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            prof_bar,
            text="LOAD SAVED",
            style="Retro.TButton",
            width=11,
            command=self._reload_saved_profile
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            prof_bar,
            text="DELETE",
            style="Retro.TButton",
            width=7,
            command=self._delete_active_profile
        ).pack(side=tk.LEFT, padx=2)

        # Hardware mapping preset dropdown (XBOX_BT, PLAYSTATION, GENERIC_DINPUT)
        tk.Label(
            prof_bar,
            text="DEVICE MAP:",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        ).pack(side=tk.LEFT, padx=(12, 4))

        self.wireless_var = tk.StringVar(value=self.gamepad_mgr.state.wireless_profile)
        self.cb_wireless = ttk.Combobox(
            prof_bar,
            textvariable=self.wireless_var,
            values=list(WIRELESS_PROFILES.keys()),
            state="readonly",
            width=15
        )
        self.cb_wireless.pack(side=tk.LEFT, padx=(0, 8))
        self.cb_wireless.bind("<<ComboboxSelected>>", self._on_wireless_profile_changed)

        self.lbl_profile_status = tk.Label(
            prof_bar,
            text=f"[ Profile: {self.gamepad_mgr.get_active_profile_name()} loaded ]",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        )
        self.lbl_profile_status.pack(side=tk.RIGHT, padx=6)

        # 3. Bottom Section: Split Columns (Calibration & Mapping)
        bot_split = tk.Frame(self, bg=COLOR_BG)
        bot_split.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

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
        # Wireless Profile Row
        prof_row = tk.Frame(parent, bg=COLOR_SURFACE)
        prof_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(prof_row, text="WIRELESS PROFILE:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=16, anchor="w").pack(side=tk.LEFT)
        self.profile_var = tk.StringVar(value=self.gamepad_mgr.state.wireless_profile)
        self.cb_profile = ttk.Combobox(
            prof_row,
            textvariable=self.profile_var,
            values=list(WIRELESS_PROFILES.keys()),
            state="readonly",
            width=18
        )
        self.cb_profile.pack(side=tk.LEFT, padx=(0, 8))
        self.cb_profile.bind("<<ComboboxSelected>>", self._on_wireless_profile_changed)

        self.lbl_profile_desc = tk.Label(
            prof_row,
            text=WIRELESS_PROFILES.get(self.gamepad_mgr.state.wireless_profile, ""),
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        )
        self.lbl_profile_desc.pack(side=tk.LEFT)

        # Live Button Monitor / Tester Readout
        self.lbl_btn_monitor = tk.Label(
            parent,
            text="LAST INPUT: NONE (Raw #0) -> ACTION: NONE",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_MONO,
            anchor="w"
        )
        self.lbl_btn_monitor.pack(fill=tk.X, pady=(0, 6))

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

    def _on_wireless_profile_changed(self, event=None):
        prof = self.profile_var.get()
        self.gamepad_mgr.set_wireless_profile(prof)
        desc = WIRELESS_PROFILES.get(prof, "")
        self.lbl_profile_desc.config(text=desc)

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

    def _sync_controls_from_manager(self):
        """Update all UI controls from current gamepad_mgr state."""
        self.profile_var.set(self.gamepad_mgr.get_active_profile_name())
        self.cb_profiles["values"] = self.gamepad_mgr.get_profile_names()
        self.wireless_var.set(self.gamepad_mgr.state.wireless_profile)
        self.deadzone_var.set(self.gamepad_mgr.state.deadzone_pct * 100)
        self.lbl_dz_val.config(text=f"{int(self.gamepad_mgr.state.deadzone_pct * 100)}%")
        self.expo_var.set(self.gamepad_mgr.state.expo * 100)
        self.lbl_expo_val.config(text=f"{int(self.gamepad_mgr.state.expo * 100)}%")
        self.inv_lx_var.set(self.gamepad_mgr.state.invert_lx)
        self.inv_ly_var.set(self.gamepad_mgr.state.invert_ly)
        self.inv_rx_var.set(self.gamepad_mgr.state.invert_rx)
        self.inv_ry_var.set(self.gamepad_mgr.state.invert_ry)
        self._refresh_mapping_tree()
        self.overlay.redraw()
        self._update_dirty_status()

    def _update_dirty_status(self):
        """Update profile status indicator to reflect clean vs unsaved modifications."""
        curr_name = self.gamepad_mgr.get_active_profile_name()
        if self.gamepad_mgr.is_dirty():
            self.lbl_profile_status.config(text=f"[ Profile: {curr_name} (MODIFIED) ]", fg="#eab308")
        else:
            self.lbl_profile_status.config(text=f"[ Profile: {curr_name} (Saved) ]", fg="#00ff88")

    def _on_profile_selected(self, event=None):
        target_name = self.profile_var.get()
        curr_name = self.gamepad_mgr.get_active_profile_name()
        if target_name == curr_name:
            return

        # If currently active profile has unsaved modifications, prompt pilot
        if self.gamepad_mgr.is_dirty():
            from gui.widgets.discard_dialog import show_discard_dialog
            choice = show_discard_dialog(
                self,
                title="Unsaved Profile Changes",
                message=(
                    f"You have unsaved changes in profile '{curr_name}'.\n\n"
                    f"Would you like to save changes before switching to '{target_name}', "
                    "or discard them to restore the saved profile?"
                ),
                item_name=f"Profile '{curr_name}'"
            )
            if choice == "cancel":
                self.profile_var.set(curr_name)
                return
            elif choice == "save":
                self.gamepad_mgr.save_config()
            elif choice == "discard":
                self.gamepad_mgr.reload_saved()

        if self.gamepad_mgr.set_active_profile(target_name, notify=False):
            self._sync_controls_from_manager()
            self._update_dirty_status()

    def _reload_saved_profile(self):
        """Reload the saved configuration from file for the active profile."""
        curr_name = self.gamepad_mgr.get_active_profile_name()
        if self.gamepad_mgr.reload_saved():
            self._sync_controls_from_manager()
            self._update_dirty_status()
            messagebox.showinfo("Profile Loaded", f"Reloaded saved configuration for '{curr_name}' from gamepad_config.json", parent=self)

    def is_dirty(self) -> bool:
        """Returns True if active gamepad profile has unsaved changes."""
        return self.gamepad_mgr.is_dirty()

    def confirm_leave(self) -> bool:
        """
        Called when pilot attempts to navigate away from the Gamepad / Controller tab.
        If there are unsaved modifications, prompts with DiscardDialog:
        - Save: saves active profile to disk and allows navigation (returns True)
        - Discard: reloads last saved profile from disk and allows navigation (returns True)
        - Cancel: aborts navigation and stays on Controller tab (returns False)
        """
        if not self.is_dirty():
            return True

        curr_name = self.gamepad_mgr.get_active_profile_name()
        from gui.widgets.discard_dialog import show_discard_dialog
        choice = show_discard_dialog(
            self,
            title="Unsaved Gamepad Changes",
            message=(
                f"You have unsaved changes in Gamepad profile '{curr_name}'.\n\n"
                "Would you like to save your modifications before leaving the tab, "
                "or discard them to restore your last saved profile?"
            ),
            item_name=f"Gamepad Profile '{curr_name}'"
        )
        if choice == "save":
            self.gamepad_mgr.save_config()
            self._update_dirty_status()
            return True
        elif choice == "discard":
            self.gamepad_mgr.reload_saved()
            self._sync_controls_from_manager()
            self._update_dirty_status()
            return True
        else:
            return False

    def _create_new_profile(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("New Gamepad Profile", "Enter profile name (e.g. DualShock4, XboxOne):", parent=self)
        if name:
            clean = name.strip()
            if clean:
                self.gamepad_mgr.create_profile(clean, copy_from_active=True)
                self._sync_controls_from_manager()
                self._update_dirty_status()

    def _save_active_profile(self):
        self.gamepad_mgr.save_config()
        curr_name = self.gamepad_mgr.get_active_profile_name()
        self._update_dirty_status()
        messagebox.showinfo("Profile Saved", f"Profile '{curr_name}' saved to gamepad_config.json", parent=self)

    def _delete_active_profile(self):
        curr = self.gamepad_mgr.get_active_profile_name()
        if len(self.gamepad_mgr.get_profile_names()) <= 1:
            messagebox.showwarning("Cannot Delete", "At least one profile must be retained.", parent=self)
            return
        if messagebox.askyesno("Confirm Delete", f"Delete gamepad profile '{curr}'?", parent=self):
            self.gamepad_mgr.delete_profile(curr)
            self._sync_controls_from_manager()
            self._update_dirty_status()

    def _on_wireless_profile_changed(self, event=None):
        w_prof = self.wireless_var.get()
        self.gamepad_mgr.set_wireless_profile(w_prof)
        self.overlay.redraw()
        self._update_dirty_status()

    def _save_config(self):
        self._save_active_profile()

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

        # Update live button monitor
        last_pressed = state_dict.get("last_pressed_button")
        raw_num = state_dict.get("last_pressed_raw_btn", 0)
        if last_pressed:
            mapping = state_dict.get("button_mappings", {})
            action = mapping.get(last_pressed, "NONE")
            raw_str = f"Raw #{raw_num}" if raw_num > 0 else "XInput"
            self.lbl_btn_monitor.config(
                text=f"LAST INPUT: {last_pressed.upper()} ({raw_str}) -> ACTION: {action}",
                fg=COLOR_TEXT_WHITE
            )

        if self.streaming_enabled.get() and state_dict.get("connected", False) and self.mav_mgr.is_connected():
            cmds = self.matrix_mgr.extract_gamepad_commands(state_dict)
            buttons = state_dict.get("buttons_bitmask", 0)

            self.mav_mgr.send_manual_control(
                x=cmds.get("mav_fwd", cmds["fwd"]),
                y=cmds.get("mav_lat", cmds["lat"]),
                z=cmds.get("mav_depth", cmds["depth"]),
                r=cmds.get("mav_yaw", cmds["yaw"]),
                buttons=buttons
            )

    def _open_motor_matrix_dialog(self):
        """Open graphical motor allocation matrix and stick configuration dialog."""
        MotorMatrixDialog(
            self,
            mav_mgr=self.mav_mgr,
            gamepad_mgr=self.gamepad_mgr
        )
