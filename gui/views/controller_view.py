"""
PixDoctorV2 - Wireless Gamepad & XInput Controller Configuration View.
Provides live stick & button telemetry, ROV pilot gain adjustments,
button action mapping, and MAVLink MANUAL_CONTROL stream control.
"""

import tkinter as tk
from tkinter import ttk
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
from gui.widgets.gamepad_overlay import GamepadOverlay
from core.gamepad_manager import GamepadManager
from core.mavlink_manager import MavlinkManager


class ControllerView(tk.Frame):
    """Interactive wireless gamepad testing and mapping view."""

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

        self._build_ui()

    def _build_ui(self):
        # Top Header
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            top_bar,
            text="[ WIRELESS GAMEPAD & XINPUT PILOT INTERFACE ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        ).pack(side=tk.LEFT)

        # Main Grid Layout
        grid_frame = tk.Frame(self, bg=COLOR_BG)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # 1. Top Section: Real-time Gamepad Stick & Button HUD
        hud_card = RetroCard(grid_frame, title="Live Stick & Button Crosshairs")
        hud_card.pack(fill=tk.X, pady=(0, 8))

        self.overlay = GamepadOverlay(hud_card.body)
        self.overlay.pack(fill=tk.BOTH, expand=True)

        # 2. Bottom Section: Split (Left: Control Settings & Gain, Right: Button Mappings)
        bot_split = tk.Frame(grid_frame, bg=COLOR_BG)
        bot_split.pack(fill=tk.BOTH, expand=True)

        # Left: Pilot Gain & MAVLink Stream
        settings_card = RetroCard(bot_split, title="Thrust Gain & Transmission")
        settings_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Stream Toggle
        chk_stream = tk.Checkbutton(
            settings_card.body,
            text="TRANSMIT MANUAL_CONTROL TO PIXHAWK (20Hz)",
            variable=self.streaming_enabled,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SURFACE,
            activeforeground=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        chk_stream.pack(anchor="w", pady=(0, 10))

        # Gain Presets
        tk.Label(
            settings_card.body,
            text="THRUST GAIN PRESET (MAX SPEED LIMIT):",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        ).pack(anchor="w", pady=(0, 4))

        gain_btn_frame = tk.Frame(settings_card.body, bg=COLOR_SURFACE)
        gain_btn_frame.pack(fill=tk.X, pady=(0, 10))

        for g_pct, g_val in [(25, 0.25), (50, 0.50), (75, 0.75), (100, 1.00)]:
            ttk.Button(
                gain_btn_frame,
                text=f"{g_pct}%",
                style="Retro.TButton",
                width=6,
                command=lambda v=g_val: self.gamepad_mgr.set_gain(v)
            ).pack(side=tk.LEFT, padx=3)

        # Control Scheme Info
        scheme_lbl = tk.Label(
            settings_card.body,
            text="Control Scheme: Standard Submersible ROV\n"
                 "- Left Stick: Yaw Rotation & Throttle (Depth)\n"
                 "- Right Stick: Forward/Reverse & Lateral Strafe\n"
                 "- Triggers: Fine Depth Control Trim",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_BODY,
            justify="left"
        )
        scheme_lbl.pack(anchor="w", pady=(6, 0))

        # Right: Button Action Reference Table
        map_card = RetroCard(bot_split, title="ArduSub Button Action Assignments")
        map_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        mappings = [
            ("START", "Toggle Arm / Disarm Safety State"),
            ("BACK", "Cycle Flight Mode (Manual -> Depth Hold -> Stabilize)"),
            ("BUTTON A", "Emergency Disarm & Kill Throttle"),
            ("BUTTON Y", "Camera Tilt Up"),
            ("BUTTON X", "Camera Tilt Down"),
            ("RIGHT BUMPER (RB)", "Cycle Lumen Lights Brightness (0%, 25%, 50%, 100%)"),
            ("LEFT BUMPER (LB)", "Lights Off"),
            ("D-PAD UP / DOWN", "Fine Gain Increment / Decrement"),
        ]

        for btn_name, action_desc in mappings:
            row = tk.Frame(map_card.body, bg=COLOR_SURFACE)
            row.pack(fill=tk.X, pady=2)

            tk.Label(
                row,
                text=f"[{btn_name}]",
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                font=FONT_BODY_BOLD,
                width=18,
                anchor="w"
            ).pack(side=tk.LEFT)

            tk.Label(
                row,
                text=action_desc,
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_DIM,
                font=FONT_SMALL,
                anchor="w"
            ).pack(side=tk.LEFT)

    def update_gamepad_telemetry(self, state_dict: Dict[str, Any]):
        """Update live visualizer and transmit MANUAL_CONTROL if enabled."""
        self.overlay.update_gamepad_state(state_dict)

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
