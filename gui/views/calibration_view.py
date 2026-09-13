"""
PixDoctorV2 - Sensor & Hardware Calibration Suite for ArduSub 4.7.1.
Dedicated calibration routines for Bar30/MS5837 Depth Sensor Zero-Tare,
Accelerometer Level Calibration, and Onboard Magnetometer/Compass Cal.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any

from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
)
from gui.widgets.mono_widgets import RetroCard
from core.mavlink_manager import MavlinkManager


class CalibrationView(tk.Frame):
    """Sensor calibration workbench."""

    def __init__(self, parent, mav_mgr: MavlinkManager, **kwargs):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.mav_mgr = mav_mgr

        self._build_ui()

    def _build_ui(self):
        # Top Header
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            top_bar,
            text="[ SENSOR CALIBRATION & ZERO-TARE WORKBENCH ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        ).pack(side=tk.LEFT)

        # Main Layout
        grid_frame = tk.Frame(self, bg=COLOR_BG)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # 1. Depth & Water Pressure Sensor Tare Card
        depth_card = RetroCard(grid_frame, title="Depth Sensor Zero-Tare (Bar30 / MS5837)")
        depth_card.pack(fill=tk.X, pady=(0, 8))

        d_desc = tk.Label(
            depth_card.body,
            text="Place the ROV at the water surface before diving and click Tare to calibrate 0.00m depth reference.\n"
                 "This resets the barometric reference to compensate for atmospheric pressure changes.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_BODY,
            justify="left"
        )
        d_desc.pack(anchor="w", pady=(0, 8))

        d_btn_frame = tk.Frame(depth_card.body, bg=COLOR_SURFACE)
        d_btn_frame.pack(fill=tk.X)

        self.lbl_current_depth = tk.Label(
            d_btn_frame,
            text="CURRENT: DEPTH 0.00 m | PRESS 1.013 bar",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        self.lbl_current_depth.pack(side=tk.LEFT, padx=(0, 16))

        btn_tare = ttk.Button(
            d_btn_frame,
            text="[ TARE SURFACE DEPTH TO 0.00m ]",
            style="Invert.TButton",
            command=self._tare_depth
        )
        btn_tare.pack(side=tk.LEFT)

        # 2. Accelerometer Level Calibration Card
        accel_card = RetroCard(grid_frame, title="Accelerometer Level Calibration")
        accel_card.pack(fill=tk.X, pady=(0, 8))

        a_desc = tk.Label(
            accel_card.body,
            text="Place the vehicle on a completely flat, level surface and keep it motionless.\n"
                 "Calibrates IMU pitch and roll zero offsets so the ROV holds horizontal attitude in water.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_BODY,
            justify="left"
        )
        a_desc.pack(anchor="w", pady=(0, 8))

        a_btn_frame = tk.Frame(accel_card.body, bg=COLOR_SURFACE)
        a_btn_frame.pack(fill=tk.X)

        btn_accel = ttk.Button(
            a_btn_frame,
            text="[ CALIBRATE LEVEL ACCELEROMETER ]",
            style="Retro.TButton",
            command=self._cal_accel_level
        )
        btn_accel.pack(side=tk.LEFT)

        # 3. Magnetometer / Compass Calibration Card
        mag_card = RetroCard(grid_frame, title="Onboard Magnetometer / Compass Calibration")
        mag_card.pack(fill=tk.X, pady=(0, 8))

        m_desc = tk.Label(
            mag_card.body,
            text="Click Start and rotate the vehicle slowly across all axes (yaw, pitch, roll) in a 3D figure-8 pattern\n"
                 "away from large ferromagnetic structures to calculate hard-iron and soft-iron sphere offsets.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_BODY,
            justify="left"
        )
        m_desc.pack(anchor="w", pady=(0, 8))

        m_btn_frame = tk.Frame(mag_card.body, bg=COLOR_SURFACE)
        m_btn_frame.pack(fill=tk.X)

        btn_mag = ttk.Button(
            m_btn_frame,
            text="[ START ONBOARD COMPASS CALIBRATION ]",
            style="Retro.TButton",
            command=self._cal_compass
        )
        btn_mag.pack(side=tk.LEFT)

        # 4. Calibration Status Log
        log_card = RetroCard(grid_frame, title="Calibration Status & Feedback")
        log_card.pack(fill=tk.BOTH, expand=True)

        self.cal_status_lbl = tk.Label(
            log_card.body,
            text="All sensors operational. Ready for calibration routine.",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_BODY,
            anchor="nw",
            justify="left"
        )
        self.cal_status_lbl.pack(fill=tk.BOTH, expand=True)

    def _tare_depth(self):
        self.mav_mgr.calibrate_depth_tare()
        self.cal_status_lbl.config(
            text="Depth sensor zero-tare command dispatched to Pixhawk.\nSensor recalibrating baseline pressure...",
            fg=COLOR_TEXT_WHITE
        )

    def _cal_accel_level(self):
        if messagebox.askyesno(
            "Calibrate Accelerometer Level",
            "Ensure the ROV is completely flat and stationary.\n\nProceed?",
            icon="question"
        ):
            self.mav_mgr.calibrate_accel_level()
            self.cal_status_lbl.config(
                text="Accelerometer level calibration in progress. Keep vehicle stationary...",
                fg=COLOR_TEXT_WHITE
            )

    def _cal_compass(self):
        if messagebox.askyesno(
            "Start Compass Calibration",
            "Rotate the vehicle slowly across all axes after starting.\n\nProceed?",
            icon="question"
        ):
            self.mav_mgr.calibrate_compass()
            self.cal_status_lbl.config(
                text="Onboard Compass Calibration started!\nRotate ROV slowly in all directions...",
                fg=COLOR_TEXT_WHITE
            )

    def update_telemetry(self, snap: Dict[str, Any]):
        depth = snap.get("depth", 0.0)
        press = snap.get("pressure_bar", 1.013)
        self.lbl_current_depth.config(text=f"CURRENT: DEPTH {depth:.2f} m | PRESS {press:.3f} bar")
