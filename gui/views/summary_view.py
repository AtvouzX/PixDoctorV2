"""
PixDoctorV2 - Futuristic Glass-Cockpit Telemetry HUD & Primary Flight Display.
Transforms the summary tab into a full-window modern futuristic HUD with 3D submersible
wireframe orientation, animated thruster vector plumes, dynamic subsea particle flow,
and tactical telemetry pods for power, environment, safety, and pilot inputs.
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
)
from gui.widgets.futuristic_hud import FuturisticHud
from gui.widgets.motor_matrix_dialog import MotorMatrixDialog
from core.ardusub_defs import FLIGHT_MODES
from core.mavlink_manager import MavlinkManager
from core.gamepad_manager import GamepadManager
from core.motor_matrix_manager import MotorMatrixManager


class SummaryView(tk.Frame):
    """Primary telemetry and vehicle overview screen in futuristic cockpit HUD format."""

    def __init__(
        self,
        parent,
        mav_mgr: MavlinkManager,
        gamepad_mgr: Optional[GamepadManager] = None,
        param_mgr: Optional[Any] = None,
        nano_mgr: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.mav_mgr = mav_mgr
        self.gamepad_mgr = gamepad_mgr
        self.param_mgr = param_mgr
        self.nano_mgr = nano_mgr
        self.matrix_mgr = MotorMatrixManager.get_instance()
        self.matrix_mgr.register_callback(self._on_matrix_updated)

        self._build_ui()

    def _build_ui(self):
        # 1. Main Full-Window Futuristic HUD Canvas
        self.hud = FuturisticHud(self)
        self.hud.pack(fill=tk.BOTH, expand=True)

        # 2. Sleek Tactical Bottom Control Bar
        bottom_bar = tk.Frame(self, bg=COLOR_SURFACE, padx=12, pady=6, highlightbackground=COLOR_BORDER, highlightthickness=1)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Left: Arm / Disarm Action (Operational Flight)
        self.btn_arm = ttk.Button(
            bottom_bar,
            text="[ ARM FC (OPERATIONAL FLIGHT) ]",
            style="Invert.TButton",
            command=self._toggle_arm
        )
        self.btn_arm.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_force_arm = ttk.Button(
            bottom_bar,
            text="FORCE ARM",
            style="Retro.TButton",
            command=self._force_arm
        )
        self.btn_force_arm.pack(side=tk.LEFT, padx=(0, 16))

        # Center-Left: Flight Mode Selector
        tk.Label(
            bottom_bar,
            text="MODE:",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_SMALL
        ).pack(side=tk.LEFT, padx=(0, 4))

        self.mode_var = tk.StringVar(value="MANUAL")
        mode_names = [info["name"] for info in FLIGHT_MODES.values()]
        self.mode_combo = ttk.Combobox(
            bottom_bar,
            textvariable=self.mode_var,
            values=mode_names,
            state="readonly",
            width=14
        )
        self.mode_combo.pack(side=tk.LEFT, padx=(0, 16))
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        # Center-Right: Surface Depth Zero-Tare
        btn_tare = ttk.Button(
            bottom_bar,
            text="TARE DEPTH",
            style="Retro.TButton",
            command=self.mav_mgr.calibrate_depth_tare
        )
        btn_tare.pack(side=tk.LEFT, padx=(0, 10))

        # Motor Matrix & Stick Setup
        btn_matrix = ttk.Button(
            bottom_bar,
            text="[ CONFIG MATRIX ]",
            style="Invert.TButton",
            command=self._open_motor_matrix_dialog
        )
        btn_matrix.pack(side=tk.LEFT, padx=(0, 10))

        # HUD / Telemetry-Only Mode Toggle
        self.btn_hud_mode = ttk.Button(
            bottom_bar,
            text="[ HUD: ON ]",
            style="Retro.TButton",
            command=self._toggle_hud_mode
        )
        self.btn_hud_mode.pack(side=tk.LEFT, padx=(0, 16))

        # Right: Live Pixhawk Status Message Strip
        self.lbl_status_strip = tk.Label(
            bottom_bar,
            text="[ SYS ]: Standby. Waiting for commands...",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL,
            anchor="e"
        )
        self.lbl_status_strip.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _toggle_arm(self):
        curr_armed = self.mav_mgr.state.armed
        if not curr_armed:
            if messagebox.askyesno(
                "Confirm Operational Arming",
                "OPERATIONAL FLIGHT ARMING:\nPixhawk flight stabilization and thrusters will be energized with full pre-arm safety checks.\n\nEnsure ROV is in water or safely cleared of all personnel and tether.\n\nProceed to ARM for Operational Flight?",
                icon="warning"
            ):
                self.mav_mgr.arm(True, force=False)
                self.mav_mgr.set_safety_switch(True)
                self.mav_mgr.set_flight_mode(19)
                self.mav_mgr.send_manual_control(0, 0, 0, 0, 0)
        else:
            self.mav_mgr.arm(False)
            self.mav_mgr.send_manual_control(0, 0, 0, 0, 0)

    def _force_arm(self):
        if messagebox.askyesno(
            "Force Arm Warning",
            "CAUTION: Force Arming bypasses all pre-flight safety checks!\n\nAre you absolutely sure you want to FORCE ARM?",
            icon="warning"
        ):
            self.mav_mgr.arm(True, force=True)
            self.mav_mgr.set_safety_switch(True)
            self.mav_mgr.set_flight_mode(19)
            self.mav_mgr.send_manual_control(0, 0, 0, 0, 0)

    def _on_mode_selected(self, event=None):
        sel_name = self.mode_var.get()
        for mode_id, info in FLIGHT_MODES.items():
            if info["name"] == sel_name:
                self.mav_mgr.set_flight_mode(mode_id)
                break

    def _open_motor_matrix_dialog(self):
        """Open graphical motor allocation matrix and stick configuration dialog."""
        MotorMatrixDialog(
            self,
            mav_mgr=self.mav_mgr,
            nano_mgr=self.nano_mgr,
            param_mgr=self.param_mgr,
            gamepad_mgr=self.gamepad_mgr
        )

    def _toggle_hud_mode(self):
        """Toggle between full jet HUD graphics and pure digital telemetry mode."""
        new_mode = not self.hud.show_hud_graphics
        self.hud.set_hud_graphics_mode(new_mode)
        if new_mode:
            self.btn_hud_mode.config(text="[ HUD: ON ]")
        else:
            self.btn_hud_mode.config(text="[ HUD: OFF (TELEM) ]")

    def update_telemetry(
        self,
        mav_snap: Dict[str, Any],
        pad_snap: Optional[Dict[str, Any]] = None,
        nano_snap: Optional[Dict[str, Any]] = None
    ):
        """Called at 20Hz by main UI timer to update HUD and stream flight controls."""
        if pad_snap is None and self.gamepad_mgr:
            pad_snap = self.gamepad_mgr.state.get_snapshot()

        if nano_snap is None and self.nano_mgr:
            nano_snap = self.nano_mgr.state.get_snapshot()

        if self.param_mgr:
            frame_id = int(self.param_mgr.get_value("FRAME_CONFIG", 6.0))
            self.hud.set_frame_id(frame_id)

        # Active flight control streaming when armed (drives motors with sticks or keeps idle mixer alive)
        if mav_snap.get("armed", False) and self.mav_mgr.is_connected():
            if pad_snap and pad_snap.get("connected", False):
                cmds = self.matrix_mgr.extract_gamepad_commands(pad_snap)
                buttons = pad_snap.get("buttons_bitmask", 0)
                self.mav_mgr.send_manual_control(
                    x=cmds.get("mav_fwd", cmds["fwd"]),
                    y=cmds.get("mav_lat", cmds["lat"]),
                    z=cmds.get("mav_depth", cmds["depth"]),
                    r=cmds.get("mav_yaw", cmds["yaw"]),
                    buttons=buttons
                )
            else:
                self.mav_mgr.send_manual_control(0, 0, 0, 0, 0)

        # Update the big futuristic HUD canvas
        self.hud.update_telemetry(mav_snap, pad_snap, nano_snap)

        # Sync Mode selector
        mode_name = mav_snap.get("flight_mode_name", "MANUAL")
        if self.mode_var.get() != mode_name and not self.mode_combo.focus_get() == self.mode_combo:
            self.mode_var.set(mode_name)

        # Sync Arm Button
        armed = mav_snap.get("armed", False)
        if armed:
            self.btn_arm.config(text="[ DISARM VEHICLE ]", style="Retro.TButton")
        else:
            self.btn_arm.config(text="[ ARM FC (OPERATIONAL FLIGHT) ]", style="Invert.TButton")

        # Sync Status message strip
        st = mav_snap.get("statustext", "Standby")
        self.lbl_status_strip.config(text=f"[ SYS ]: {st}")

    def _on_matrix_updated(self):
        """Callback triggered when motor matrix, stick mode, or frame changes."""
        new_fid = self.matrix_mgr.get_current_frame_id()
        if hasattr(self, "hud"):
            self.hud.set_frame_id(new_fid)
