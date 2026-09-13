"""
PixDoctorV2 - Safety & Failsafe Configuration View.
Comprehensive setup for Leak Detector pins and logic, Battery cutoff thresholds,
GCS tether communication heartbeat failsafe, and Pre-Arming safety checks.
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
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
)
from gui.widgets.mono_widgets import RetroCard
from core.ardusub_defs import LEAK_PINS
from core.param_manager import ParameterManager
from core.mavlink_manager import MavlinkManager


class SafetyView(tk.Frame):
    """Safety and failsafe parameters editor."""

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

        self._build_ui()

    def _build_ui(self):
        # Top Header
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            top_bar,
            text="[ SAFETY, FAILSAFE & LEAK DETECTOR SUITE ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        ).pack(side=tk.LEFT)

        btn_save = ttk.Button(
            top_bar,
            text="[ COMMIT SAFETY PARAMS TO FLASH ]",
            style="Invert.TButton",
            command=self._commit_safety_params
        )
        btn_save.pack(side=tk.RIGHT)

        # Main Layout
        grid_frame = tk.Frame(self, bg=COLOR_BG)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # 1. Leak Detector Hardware Pin & Logic Card
        leak_card = RetroCard(grid_frame, title="Internal Hull Leak Detector Setup")
        leak_card.pack(fill=tk.X, pady=(0, 8))

        # Leak Pin Row
        p_row = tk.Frame(leak_card.body, bg=COLOR_SURFACE)
        p_row.pack(fill=tk.X, pady=3)

        tk.Label(p_row, text="LEAK SENSOR PIN (LEAK1_PIN):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=32, anchor="w").pack(side=tk.LEFT)
        self.leak_pin_var = tk.StringVar(value="AUX 6 (Pin 55)")
        pin_options = [p["name"] for p in LEAK_PINS]
        self.cb_leak_pin = ttk.Combobox(p_row, textvariable=self.leak_pin_var, values=pin_options, state="readonly", width=18)
        self.cb_leak_pin.pack(side=tk.LEFT)

        # Leak Logic State Row
        l_row = tk.Frame(leak_card.body, bg=COLOR_SURFACE)
        l_row.pack(fill=tk.X, pady=3)

        tk.Label(l_row, text="SENSOR LOGIC (LEAK1_LOGIC):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=32, anchor="w").pack(side=tk.LEFT)
        self.leak_logic_var = tk.StringVar(value="0 (Low is Leak / Pullup)")
        self.cb_leak_logic = ttk.Combobox(
            l_row,
            textvariable=self.leak_logic_var,
            values=["0 (Low is Leak / Pullup)", "1 (High is Leak)"],
            state="readonly",
            width=24
        )
        self.cb_leak_logic.pack(side=tk.LEFT)

        # Leak Failsafe Action Row
        act_row = tk.Frame(leak_card.body, bg=COLOR_SURFACE)
        act_row.pack(fill=tk.X, pady=3)

        tk.Label(act_row, text="LEAK FAILSAFE ACTION (FS_LEAK_ENABLE):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=32, anchor="w").pack(side=tk.LEFT)
        self.leak_act_var = tk.StringVar(value="1 (Emergency Surface)")
        self.cb_leak_act = ttk.Combobox(
            act_row,
            textvariable=self.leak_act_var,
            values=["0 (Disabled / Warning Only)", "1 (Emergency Surface)", "2 (Disarm Motors)"],
            state="readonly",
            width=26
        )
        self.cb_leak_act.pack(side=tk.LEFT)

        # 2. Battery Failsafe Card
        batt_card = RetroCard(grid_frame, title="Battery Low Voltage & Capacity Protection")
        batt_card.pack(fill=tk.X, pady=(0, 8))

        # Battery Action Row
        b_act_row = tk.Frame(batt_card.body, bg=COLOR_SURFACE)
        b_act_row.pack(fill=tk.X, pady=3)

        tk.Label(b_act_row, text="BATTERY FAILSAFE (FS_BATT_ENABLE):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=32, anchor="w").pack(side=tk.LEFT)
        self.batt_act_var = tk.StringVar(value="1 (Emergency Surface)")
        self.cb_batt_act = ttk.Combobox(
            b_act_row,
            textvariable=self.batt_act_var,
            values=["0 (Disabled)", "1 (Emergency Surface)", "2 (Disarm Motors)"],
            state="readonly",
            width=26
        )
        self.cb_batt_act.pack(side=tk.LEFT)

        # Voltage Threshold
        v_row = tk.Frame(batt_card.body, bg=COLOR_SURFACE)
        v_row.pack(fill=tk.X, pady=3)

        tk.Label(v_row, text="LOW VOLTAGE LIMIT (FS_BATT_VOLT):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=32, anchor="w").pack(side=tk.LEFT)
        self.batt_volt_var = tk.DoubleVar(value=10.5)
        self.sp_batt_volt = ttk.Spinbox(v_row, from_=9.0, to=28.0, increment=0.1, textvariable=self.batt_volt_var, width=8)
        self.sp_batt_volt.pack(side=tk.LEFT)
        tk.Label(v_row, text="Volts (e.g. 10.5V for 3S, 14.0V for 4S)", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=8)

        # 3. GCS Tether Heartbeat Failsafe Card
        gcs_card = RetroCard(grid_frame, title="Tether & Ground Station Loss Failsafe")
        gcs_card.pack(fill=tk.X, pady=(0, 8))

        gcs_row = tk.Frame(gcs_card.body, bg=COLOR_SURFACE)
        gcs_row.pack(fill=tk.X, pady=3)

        tk.Label(gcs_row, text="GCS TIMEOUT ACTION (FS_GCS_ENABLE):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=32, anchor="w").pack(side=tk.LEFT)
        self.gcs_act_var = tk.StringVar(value="1 (Emergency Surface)")
        self.cb_gcs_act = ttk.Combobox(
            gcs_row,
            textvariable=self.gcs_act_var,
            values=["0 (Disabled)", "1 (Emergency Surface)", "2 (Disarm Motors)"],
            state="readonly",
            width=26
        )
        self.cb_gcs_act.pack(side=tk.LEFT)

        # 4. Pre-Arming Safety Checks Card
        arm_card = RetroCard(grid_frame, title="Pre-Arm Safety Checks (ARMING_CHECK)")
        arm_card.pack(fill=tk.BOTH, expand=True)

        self.arm_check_var = tk.IntVar(value=1)
        chk_all = tk.Radiobutton(
            arm_card.body,
            text="ENABLE ALL PRE-ARM CHECKS (Strict Flight Safety: Sensors, Compass, Voltage, Parameters)",
            variable=self.arm_check_var,
            value=1,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SURFACE,
            activeforeground=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        chk_all.pack(anchor="w", pady=2)

        chk_none = tk.Radiobutton(
            arm_card.body,
            text="DISABLE ALL CHECKS (Bench Testing Only - Bypasses all sensor and voltage checks)",
            variable=self.arm_check_var,
            value=0,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SURFACE,
            activeforeground=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        chk_none.pack(anchor="w", pady=2)

    def _commit_safety_params(self):
        # Extract Pin
        pin_sel = self.leak_pin_var.get()
        pin_val = 55
        for p in LEAK_PINS:
            if p["name"] == pin_sel:
                pin_val = p["gpio"]
                break

        # Logic
        logic_val = 0 if "0" in self.leak_logic_var.get() else 1

        # Leak Action
        leak_act = 1 if "1" in self.leak_act_var.get() else (2 if "2" in self.leak_act_var.get() else 0)

        # Batt Action
        batt_act = 1 if "1" in self.batt_act_var.get() else (2 if "2" in self.batt_act_var.get() else 0)
        batt_v = float(self.batt_volt_var.get())

        # GCS Action
        gcs_act = 1 if "1" in self.gcs_act_var.get() else (2 if "2" in self.gcs_act_var.get() else 0)

        # Arm Check
        arm_val = float(self.arm_check_var.get())

        # Update params
        to_commit = {
            "LEAK1_PIN": float(pin_val),
            "LEAK1_LOGIC": float(logic_val),
            "FS_LEAK_ENABLE": float(leak_act),
            "FS_BATT_ENABLE": float(batt_act),
            "FS_BATT_VOLT": batt_v,
            "FS_GCS_ENABLE": float(gcs_act),
            "ARMING_CHECK": arm_val,
        }

        for k, v in to_commit.items():
            self.param_mgr.set_value(k, v)
            self.mav_mgr.set_param(k, v)

        messagebox.showinfo(
            "Safety Parameters Committed",
            "Failsafe and leak detector configuration parameters successfully written to Pixhawk flash."
        )
