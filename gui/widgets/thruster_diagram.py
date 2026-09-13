"""
PixDoctorV2 - Vehicle Thruster Frame Geometry Visualizer.
Schematic drawing of SimpleROV-4, SimpleROV-3, and BlueROV2 thrusters
with live output status and interactive test targeting.
"""

import tkinter as tk
from typing import Dict, Any, List, Optional, Callable
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
from core.ardusub_defs import FRAMES


class ThrusterDiagram(tk.Canvas):
    """Visualizes ROV frame thruster layout with real-time test animations."""

    def __init__(
        self,
        parent,
        frame_id: int = 6,
        on_thruster_click: Optional[Callable[[int], None]] = None,
        width: int = 340,
        height: int = 280,
        **kwargs
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=COLOR_BG,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            **kwargs
        )
        self.frame_id = frame_id
        self.on_thruster_click = on_thruster_click
        self.active_test_thruster: Optional[int] = None
        self.motor_pwms: List[int] = [1500] * 8
        self.motor_reversed: List[bool] = [False] * 8

        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._handle_click)

    def set_frame(self, frame_id: int):
        self.frame_id = frame_id
        self.redraw()

    def set_active_test(self, thruster_idx: Optional[int]):
        self.active_test_thruster = thruster_idx
        self.redraw()

    def update_pwms(self, pwms: List[int], reversed_flags: List[bool] = None):
        self.motor_pwms = list(pwms[:8])
        if reversed_flags:
            self.motor_reversed = list(reversed_flags[:8])
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 20 or h <= 20:
            return

        cx = w / 2.0
        cy = h / 2.0

        frame_data = FRAMES.get(self.frame_id, FRAMES[6])
        thrusters = frame_data.get("thrusters", [])

        # 1. Draw ROV Hull Outline (Monochrome classic chassis)
        hull_w = min(w, h) * 0.46
        hull_h = min(w, h) * 0.65
        x0 = cx - hull_w / 2
        y0 = cy - hull_h / 2
        x1 = cx + hull_w / 2
        y1 = cy + hull_h / 2

        # Main Chassis Frame
        self.create_rectangle(x0, y0, x1, y1, outline=COLOR_BORDER_LIGHT, width=2, fill=COLOR_SURFACE)

        # Forward Direction Pointer Arrow (Bow)
        bow_y = y0 + 15
        self.create_polygon(
            cx - 12, bow_y,
            cx + 12, bow_y,
            cx, bow_y - 12,
            outline=COLOR_TEXT_WHITE,
            fill=COLOR_TEXT_WHITE
        )
        self.create_text(cx, bow_y + 12, text="BOW (FORWARD)", fill=COLOR_TEXT_DIM, font=FONT_SMALL)

        # Frame Title Label
        self.create_text(
            cx, h - 14,
            text=f"[ {frame_data['name'].upper()} ]",
            fill=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )

        # 2. Draw Thrusters
        for t in thrusters:
            t_num = t["num"]
            pos_x, pos_y = t["pos"]  # Normalized (-1 to 1)

            # Map to canvas coordinates
            tx = cx + (pos_x * (hull_w * 0.75))
            ty = cy - (pos_y * (hull_h * 0.70))

            is_testing = (self.active_test_thruster == t_num)
            is_rev = self.motor_reversed[t_num - 1] if t_num <= len(self.motor_reversed) else False
            current_pwm = self.motor_pwms[t_num - 1] if t_num <= len(self.motor_pwms) else 1500

            # Thruster Box size
            box_r = 18

            # Highlight if actively testing
            if is_testing:
                box_bg = COLOR_INVERT_BG
                box_fg = COLOR_INVERT_FG
                box_border = COLOR_INVERT_BG
            else:
                box_bg = COLOR_SURFACE
                box_fg = COLOR_TEXT_WHITE
                box_border = COLOR_TEXT_WHITE if abs(current_pwm - 1500) > 30 else COLOR_BORDER_LIGHT

            # Thruster Outer Enclosure
            self.create_rectangle(
                tx - box_r, ty - box_r,
                tx + box_r, ty + box_r,
                fill=box_bg,
                outline=box_border,
                width=2,
                tags=(f"thruster_{t_num}", "thruster")
            )

            # Thruster Number
            self.create_text(
                tx, ty - 2,
                text=f"M{t_num}",
                fill=box_fg,
                font=FONT_BODY_BOLD,
                tags=(f"thruster_{t_num}", "thruster")
            )

            # Direction or Reverse Indicator
            sub_text = "REV" if is_rev else ("V" if "Vertical" in t["role"] else "H")
            self.create_text(
                tx, ty + 9,
                text=sub_text,
                fill=box_fg if is_testing else COLOR_TEXT_DIM,
                font=FONT_SMALL,
                tags=(f"thruster_{t_num}", "thruster")
            )

            # Draw PWM label below thruster
            if abs(current_pwm - 1500) > 10:
                self.create_text(
                    tx, ty + box_r + 10,
                    text=f"{current_pwm}µs",
                    fill=COLOR_TEXT_WHITE,
                    font=FONT_SMALL
                )

    def _handle_click(self, event):
        """Detect click on thruster box to trigger test."""
        if not self.on_thruster_click:
            return

        items = self.find_overlapping(event.x - 2, event.y - 2, event.x + 2, event.y + 2)
        for item in items:
            tags = self.gettags(item)
            for tag in tags:
                if tag.startswith("thruster_"):
                    try:
                        t_num = int(tag.split("_")[1])
                        self.on_thruster_click(t_num)
                        return
                    except ValueError:
                        pass
