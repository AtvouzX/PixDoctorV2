"""
PixDoctorV2 - Main Vehicle Summary & Live Telemetry HUD View.
High-contrast nostalgic avionics dashboard showing Attitude, Depth,
Power Rails, Flight Modes, and Arming controls for ArduSub 4.7.1.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any

from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    COLOR_INVERT_BG,
    COLOR_INVERT_FG,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
    FONT_LARGE_NUM,
)
from gui.widgets.mono_widgets import RetroCard, MetricCard, RetroPill
from gui.widgets.attitude_indicator import AttitudeIndicator
from core.ardusub_defs import FLIGHT_MODES
from core.mavlink_manager import MavlinkManager


class SummaryView(tk.Frame):
    """Primary telemetry and vehicle overview screen."""

    def __init__(self, parent, mav_mgr: MavlinkManager, **kwargs):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.mav_mgr = mav_mgr

        self._build_ui()

    def _build_ui(self):
        # Top Header Bar for Summary
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 6))

        title_lbl = tk.Label(
            top_bar,
            text="[ VEHICLE TELEMETRY & FLIGHT CONTROL HUD ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        )
        title_lbl.pack(side=tk.LEFT)

        # Main Layout Grid: Left (Attitude HUD + Mode/Arming), Right (Metrics + Health)
        grid_frame = tk.Frame(self, bg=COLOR_BG)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # ================= LEFT COLUMN: ATTITUDE & CONTROL =================
        left_col = tk.Frame(grid_frame, bg=COLOR_BG, width=320)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 8))

        # 1. Attitude Horizon HUD Card
        att_card = RetroCard(left_col, title="Artificial Horizon & Heading")
        att_card.pack(fill=tk.X, pady=(0, 8))

        self.attitude_hud = AttitudeIndicator(att_card.body, width=300, height=220)
        self.attitude_hud.pack(fill=tk.BOTH, expand=True)

        # 2. Flight Mode & Arming Card
        control_card = RetroCard(left_col, title="Flight Mode & Safety State")
        control_card.pack(fill=tk.X, pady=(0, 8))

        # Mode Selection Row
        mode_row = tk.Frame(control_card.body, bg=COLOR_SURFACE)
        mode_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            mode_row,
            text="ACTIVE MODE:",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        ).pack(side=tk.LEFT)

        self.mode_var = tk.StringVar(value="MANUAL")
        mode_names = [info["name"] for info in FLIGHT_MODES.values()]
        self.mode_combo = ttk.Combobox(
            mode_row,
            textvariable=self.mode_var,
            values=mode_names,
            state="readonly",
            width=14
        )
        self.mode_combo.pack(side=tk.LEFT, padx=6)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_selected)

        # Arm / Disarm Action Row
        arm_row = tk.Frame(control_card.body, bg=COLOR_SURFACE)
        arm_row.pack(fill=tk.X, pady=(4, 0))

        self.btn_arm = ttk.Button(
            arm_row,
            text="[ ARM VEHICLE ]",
            style="Invert.TButton",
            command=self._toggle_arm
        )
        self.btn_arm.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_force_arm = ttk.Button(
            arm_row,
            text="FORCE ARM",
            style="Retro.TButton",
            command=self._force_arm
        )
        self.btn_force_arm.pack(side=tk.RIGHT)

        # ================= RIGHT COLUMN: METRICS & POWER =================
        right_col = tk.Frame(grid_frame, bg=COLOR_BG)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 1. Primary Underwater Sensor Readouts
        sensor_card = RetroCard(right_col, title="Depth & Environment (Bar30 / MS5837)")
        sensor_card.pack(fill=tk.X, pady=(0, 8))

        s_grid = tk.Frame(sensor_card.body, bg=COLOR_SURFACE)
        s_grid.pack(fill=tk.X)

        self.metric_depth = MetricCard(s_grid, label="Depth (Water)", value="0.00", unit="m")
        self.metric_depth.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.metric_pressure = MetricCard(s_grid, label="Ambient Pressure", value="1.013", unit="bar")
        self.metric_pressure.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.metric_temp = MetricCard(s_grid, label="Water Temp", value="24.0", unit="°C")
        self.metric_temp.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Depth Tare Button
        tare_frame = tk.Frame(sensor_card.body, bg=COLOR_SURFACE)
        tare_frame.pack(fill=tk.X, pady=(6, 0))

        btn_tare = ttk.Button(
            tare_frame,
            text="TARE / ZERO SURFACE DEPTH",
            style="Retro.TButton",
            command=self.mav_mgr.calibrate_depth_tare
        )
        btn_tare.pack(side=tk.LEFT)

        # 2. Power Rails & Brownout Protection
        power_card = RetroCard(right_col, title="Power System & STM32 Rail Monitor")
        power_card.pack(fill=tk.X, pady=(0, 8))

        p_grid = tk.Frame(power_card.body, bg=COLOR_SURFACE)
        p_grid.pack(fill=tk.X)

        self.metric_batt_v = MetricCard(p_grid, label="Main Battery", value="0.0", unit="V")
        self.metric_batt_v.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.metric_batt_a = MetricCard(p_grid, label="Current Draw", value="0.0", unit="A")
        self.metric_batt_a.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        self.metric_vcc = MetricCard(p_grid, label="5V MCU VCC Rail", value="5.05", unit="V")
        self.metric_vcc.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 3. Status Text & Leak Watchdog Card
        status_card = RetroCard(right_col, title="System Messages & Failsafe Watchdog")
        status_card.pack(fill=tk.BOTH, expand=True)

        self.leak_alert_banner = tk.Label(
            status_card.body,
            text="[ LEAK DETECTOR: NORMAL - NO WATER INTRUSION ]",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD,
            pady=4
        )
        self.leak_alert_banner.pack(fill=tk.X, pady=(0, 6))

        self.lbl_statustext = tk.Label(
            status_card.body,
            text="Pixhawk 2.4.8 Standby. Waiting for commands...",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_BODY,
            anchor="w",
            wraplength=450,
            justify="left"
        )
        self.lbl_statustext.pack(fill=tk.BOTH, expand=True)

    def _toggle_arm(self):
        curr_armed = self.mav_mgr.state.armed
        if not curr_armed:
            if messagebox.askyesno(
                "Confirm Arming",
                "WARNING: Pixhawk motors will be energized!\n\nEnsure thrusters are clear of personnel and tether before arming.\n\nProceed to ARM?",
                icon="warning"
            ):
                self.mav_mgr.arm(True)
        else:
            self.mav_mgr.arm(False)

    def _force_arm(self):
        if messagebox.askyesno(
            "Force Arm Warning",
            "CAUTION: Force Arming bypasses all pre-flight safety checks!\n\nAre you absolutely sure you want to FORCE ARM?",
            icon="warning"
        ):
            self.mav_mgr.arm(True, force=True)

    def _on_mode_selected(self, event=None):
        sel_name = self.mode_var.get()
        for mode_id, info in FLIGHT_MODES.items():
            if info["name"] == sel_name:
                self.mav_mgr.set_flight_mode(mode_id)
                break

    def update_telemetry(self, snap: Dict[str, Any]):
        """Called at 20Hz by main UI timer to update telemetry readouts."""
        # Update Attitude
        self.attitude_hud.update_attitude(
            roll=snap.get("roll", 0.0),
            pitch=snap.get("pitch", 0.0),
            heading=snap.get("yaw", 0.0),
            depth=snap.get("depth", 0.0)
        )

        # Update Metrics
        self.metric_depth.set_value(f"{snap.get('depth', 0.0):.2f}")
        self.metric_pressure.set_value(f"{snap.get('pressure_bar', 1.013):.3f}")
        self.metric_temp.set_value(f"{snap.get('temperature', 25.0):.1f}")

        self.metric_batt_v.set_value(f"{snap.get('battery_voltage', 0.0):.1f}")
        self.metric_batt_a.set_value(f"{snap.get('battery_current', 0.0):.1f}")
        self.metric_vcc.set_value(f"{snap.get('vcc_voltage', 5.05):.2f}")

        # Flight Mode Sync
        mode_name = snap.get("flight_mode_name", "MANUAL")
        if self.mode_var.get() != mode_name and not self.mode_combo.focus_get() == self.mode_combo:
            self.mode_var.set(mode_name)

        # Arm Button State
        armed = snap.get("armed", False)
        if armed:
            self.btn_arm.config(text="[ DISARM VEHICLE ]", style="Retro.TButton")
        else:
            self.btn_arm.config(text="[ ARM VEHICLE ]", style="Invert.TButton")

        # Status text
        st = snap.get("statustext", "Standby")
        self.lbl_statustext.config(text=st)

        # Leak watchdog
        if snap.get("leak", False):
            self.leak_alert_banner.config(
                text="[ ! ! ! CRITICAL LEAK DETECTED ! ! ! ]",
                bg=COLOR_INVERT_BG,
                fg=COLOR_INVERT_FG
            )
        else:
            self.leak_alert_banner.config(
                text="[ LEAK DETECTOR: NORMAL - HULL SEALED ]",
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE
            )
