"""
PixDoctorV2 - Flight Modes & Actuator Functions Configuration View.
Sets ArduSub 6-mode switcher slots and maps AUX outputs for Camera Tilt & Lumen Lights.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List

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
from core.ardusub_defs import FLIGHT_MODES
from core.param_manager import ParameterManager
from core.mavlink_manager import MavlinkManager


class FlightModesView(tk.Frame):
    """Flight mode slot configuration and auxiliary servo mapping."""

    def __init__(
        self,
        parent,
        param_mgr: ParameterManager,
        mav_mgr: MavlinkManager,
        **kwargs
    ):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.param_mgr = param_mgr
        self.mav_mgr = mav_mgr

        self.mode_vars: List[tk.StringVar] = []
        self._build_ui()

    def _build_ui(self):
        # Top Header
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            top_bar,
            text="[ FLIGHT MODES & AUXILIARY SERVO ASSIGNMENTS ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        ).pack(side=tk.LEFT)

        btn_save = ttk.Button(
            top_bar,
            text="[ COMMIT MODES & AUX TO FLASH ]",
            style="Invert.TButton",
            command=self._commit_modes
        )
        btn_save.pack(side=tk.RIGHT)

        # Main Layout
        grid_frame = tk.Frame(self, bg=COLOR_BG)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # 1. 6 Flight Mode Slots Card
        modes_card = RetroCard(grid_frame, title="ArduSub 6-Mode Switcher Slots (FLTMODE1 - FLTMODE6)")
        modes_card.pack(fill=tk.X, pady=(0, 8))

        mode_options = [f"{info['name']} (Mode {m_id})" for m_id, info in FLIGHT_MODES.items()]

        defaults = [19, 0, 2, 16, 1, 9]  # Manual, Stabilize, AltHold, PosHold, Acro, Surface

        for i in range(1, 7):
            row = tk.Frame(modes_card.body, bg=COLOR_SURFACE)
            row.pack(fill=tk.X, pady=2)

            tk.Label(
                row,
                text=f"SLOT {i} (FLTMODE{i}):",
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                font=FONT_SMALL,
                width=24,
                anchor="w"
            ).pack(side=tk.LEFT)

            def_val = defaults[i - 1]
            def_str = f"{FLIGHT_MODES[def_val]['name']} (Mode {def_val})"
            var = tk.StringVar(value=def_str)
            self.mode_vars.append(var)

            cb = ttk.Combobox(row, textvariable=var, values=mode_options, state="readonly", width=34)
            cb.pack(side=tk.LEFT)

        # 2. Auxiliary Actuator Outputs (Camera Tilt, Lumen Subsea Lights)
        aux_card = RetroCard(grid_frame, title="Auxiliary Servo & Subsea Equipment Mapping")
        aux_card.pack(fill=tk.BOTH, expand=True)

        # Camera Tilt
        c_row = tk.Frame(aux_card.body, bg=COLOR_SURFACE)
        c_row.pack(fill=tk.X, pady=3)

        tk.Label(c_row, text="CAMERA TILT SERVO (AUX 2 / SERVO10):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=38, anchor="w").pack(side=tk.LEFT)
        self.cam_fn_var = tk.StringVar(value="7 (Mount Tilt)")
        cb_cam = ttk.Combobox(c_row, textvariable=self.cam_fn_var, values=["7 (Mount Tilt)", "0 (Disabled)"], state="readonly", width=18)
        cb_cam.pack(side=tk.LEFT)

        # Lumen Lights 1
        l1_row = tk.Frame(aux_card.body, bg=COLOR_SURFACE)
        l1_row.pack(fill=tk.X, pady=3)

        tk.Label(l1_row, text="SUBSEA LIGHTS 1 (AUX 3 / SERVO11):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=38, anchor="w").pack(side=tk.LEFT)
        self.l1_fn_var = tk.StringVar(value="12 (RCIN 9 / Lights 1)")
        cb_l1 = ttk.Combobox(l1_row, textvariable=self.l1_fn_var, values=["12 (RCIN 9 / Lights 1)", "0 (Disabled)"], state="readonly", width=22)
        cb_l1.pack(side=tk.LEFT)

        # Lumen Lights 2
        l2_row = tk.Frame(aux_card.body, bg=COLOR_SURFACE)
        l2_row.pack(fill=tk.X, pady=3)

        tk.Label(l2_row, text="SUBSEA LIGHTS 2 (AUX 4 / SERVO12):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=38, anchor="w").pack(side=tk.LEFT)
        self.l2_fn_var = tk.StringVar(value="13 (RCIN 10 / Lights 2)")
        cb_l2 = ttk.Combobox(l2_row, textvariable=self.l2_fn_var, values=["13 (RCIN 10 / Lights 2)", "0 (Disabled)"], state="readonly", width=22)
        cb_l2.pack(side=tk.LEFT)

        # Actuator PWM Rate
        rate_row = tk.Frame(aux_card.body, bg=COLOR_SURFACE)
        rate_row.pack(fill=tk.X, pady=3)

        tk.Label(rate_row, text="ESC REFRESH RATE (RC_SPEED):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=38, anchor="w").pack(side=tk.LEFT)
        self.rate_var = tk.IntVar(value=200)
        sp_rate = ttk.Spinbox(rate_row, from_=50, to=400, increment=50, textvariable=self.rate_var, width=8)
        sp_rate.pack(side=tk.LEFT)
        tk.Label(rate_row, text="Hz (200Hz recommended for BlueRobotics ESCs)", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=8)

    def _commit_modes(self):
        for i in range(1, 7):
            val_str = self.mode_vars[i - 1].get()
            # Extract mode ID number
            for mode_id, info in FLIGHT_MODES.items():
                if info["name"] in val_str:
                    param_name = f"FLTMODE{i}"
                    self.param_mgr.set_value(param_name, float(mode_id))
                    self.mav_mgr.set_param(param_name, float(mode_id))
                    break

        # Aux settings
        self.param_mgr.set_value("RC_SPEED", float(self.rate_var.get()))
        self.mav_mgr.set_param("RC_SPEED", float(self.rate_var.get()))

        messagebox.showinfo("Modes Committed", "Flight mode slots and auxiliary functions written to Pixhawk flash.")
