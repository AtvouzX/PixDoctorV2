"""
PixDoctorV2 - Nostalgic Avionics HUD Artificial Horizon & Compass.
Renders retro vector-line pitch ladder, roll pointer, and heading tape.
"""

import math
import tkinter as tk
from gui.theme import (
    COLOR_BG,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    FONT_SMALL,
    FONT_BODY_BOLD,
)


class AttitudeIndicator(tk.Canvas):
    """Nostalgic vector-graphics HUD with pitch, roll, heading, and depth."""

    def __init__(self, parent, width: int = 260, height: int = 240, **kwargs):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=COLOR_BG,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            **kwargs
        )
        self.roll: float = 0.0
        self.pitch: float = 0.0
        self.heading: float = 0.0
        self.depth: float = 0.0

        self.bind("<Configure>", lambda e: self.redraw())

    def update_attitude(self, roll: float, pitch: float, heading: float, depth: float):
        self.roll = roll
        self.pitch = pitch
        self.heading = heading
        self.depth = depth
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 20 or h <= 20:
            return

        cx = w / 2.0
        cy = h / 2.0
        r_rad = math.radians(self.roll)
        cos_r = math.cos(r_rad)
        sin_r = math.sin(r_rad)

        # Scale factor for pitch (pixels per degree)
        pitch_scale = 2.0

        # 1. Pitch Ladder Lines
        for deg in range(-40, 50, 10):
            dy = (deg - self.pitch) * pitch_scale
            if abs(dy) > (h / 2.0) - 20:
                continue

            line_w = 40 if deg == 0 else 25
            x0 = -line_w
            x1 = line_w
            y0 = dy
            y1 = dy

            # Rotate by roll angle
            rx0 = cx + (x0 * cos_r - y0 * sin_r)
            ry0 = cy + (x0 * sin_r + y0 * cos_r)
            rx1 = cx + (x1 * cos_r - y1 * sin_r)
            ry1 = cy + (x1 * sin_r + y1 * cos_r)

            color = COLOR_TEXT_WHITE if deg == 0 else COLOR_TEXT_DIM
            width = 2 if deg == 0 else 1
            self.create_line(rx0, ry0, rx1, ry1, fill=color, width=width)

            # Degree text label for non-zero lines
            if deg != 0 and abs(dy) < (h / 2.0) - 30:
                lbl_x = cx + ((line_w + 14) * cos_r - y0 * sin_r)
                lbl_y = cy + ((line_w + 14) * sin_r + y0 * cos_r)
                self.create_text(lbl_x, lbl_y, text=f"{abs(deg)}", fill=COLOR_TEXT_DIM, font=FONT_SMALL)

        # 2. Fixed Aircraft / ROV Center Reticle
        self.create_line(cx - 30, cy, cx - 10, cy, fill=COLOR_TEXT_WHITE, width=2)
        self.create_line(cx + 10, cy, cx + 30, cy, fill=COLOR_TEXT_WHITE, width=2)
        self.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, outline=COLOR_TEXT_WHITE, width=2)

        # 3. Top Heading Compass Banner
        self.create_rectangle(cx - 50, 6, cx + 50, 24, fill=COLOR_BG, outline=COLOR_BORDER)
        hdg_str = f"HDG {int(self.heading):03d}°"
        self.create_text(cx, 15, text=hdg_str, fill=COLOR_TEXT_WHITE, font=FONT_BODY_BOLD)

        # 4. Corner Telemetry Monospace Readouts
        self.create_text(10, h - 14, text=f"R:{self.roll:+.1f}°", fill=COLOR_TEXT_DIM, font=FONT_SMALL, anchor="w")
        self.create_text(w / 2, h - 14, text=f"P:{self.pitch:+.1f}°", fill=COLOR_TEXT_DIM, font=FONT_SMALL, anchor="center")
        self.create_text(w - 10, h - 14, text=f"D:{self.depth:.2f}m", fill=COLOR_TEXT_WHITE, font=FONT_BODY_BOLD, anchor="e")
