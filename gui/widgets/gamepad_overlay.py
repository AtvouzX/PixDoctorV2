"""
PixDoctorV2 - Nostalgic Wireless Gamepad & XInput Controller Visualizer.
Renders stick crosshairs, trigger gauges, and button activity in real-time.
"""

import tkinter as tk
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
    FONT_BODY_BOLD,
    FONT_SMALL,
)


class GamepadOverlay(tk.Frame):
    """Visualizes live joystick axes and button states for wireless controllers."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLOR_SURFACE, **kwargs)

        # Header
        hdr = tk.Frame(self, bg=COLOR_SURFACE)
        hdr.pack(fill=tk.X, pady=(0, 6))

        self.lbl_title = tk.Label(
            hdr,
            text="[ GAMEPAD / XINPUT STATUS: SEARCHING... ]",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_HEADER,
            anchor="w"
        )
        self.lbl_title.pack(side=tk.LEFT)

        self.lbl_gain = tk.Label(
            hdr,
            text="GAIN: 50%",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD,
            anchor="e"
        )
        self.lbl_gain.pack(side=tk.RIGHT)

        # Canvas for Sticks, Triggers, and Buttons
        self.canvas = tk.Canvas(
            self,
            bg=COLOR_BG,
            height=140,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.lx = 0
        self.ly = 0
        self.rx = 0
        self.ry = 0
        self.lt = 0
        self.rt = 0
        self.connected = False
        self.buttons = {}

        self.canvas.bind("<Configure>", lambda e: self.redraw())

    def update_gamepad_state(self, state_dict: dict):
        self.connected = state_dict.get("connected", False)
        name = state_dict.get("controller_name", "Disconnected")
        backend = state_dict.get("backend", "None")

        if self.connected:
            self.lbl_title.config(
                text=f"[ {name.upper()} ({backend}): ACTIVE ]",
                fg=COLOR_TEXT_WHITE
            )
        else:
            self.lbl_title.config(
                text="[ CONTROLLER: DISCONNECTED / WIRELESS STANDBY ]",
                fg=COLOR_TEXT_DIM
            )

        gain_pct = int(state_dict.get("gain", 0.5) * 100)
        self.lbl_gain.config(text=f"PILOT GAIN: {gain_pct}%")

        self.lx = state_dict.get("axis_lx", 0)
        self.ly = state_dict.get("axis_ly", 0)
        self.rx = state_dict.get("axis_rx", 0)
        self.ry = state_dict.get("axis_ry", 0)
        self.lt = state_dict.get("trigger_lt", 0)
        self.rt = state_dict.get("trigger_rt", 0)
        self.buttons = {k: v for k, v in state_dict.items() if k.startswith("btn_") or k.startswith("dpad_")}

        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 40 or h <= 40:
            return

        # 1. Left Stick (Depth / Yaw)
        ls_cx = w * 0.22
        ls_cy = h * 0.52
        r = 36
        self.canvas.create_oval(ls_cx - r, ls_cy - r, ls_cx + r, ls_cy + r, outline=COLOR_BORDER_LIGHT, width=1)
        self.canvas.create_line(ls_cx - r, ls_cy, ls_cx + r, ls_cy, fill=COLOR_BORDER, width=1)
        self.canvas.create_line(ls_cx, ls_cy - r, ls_cx, ls_cy + r, fill=COLOR_BORDER, width=1)

        # Crosshair point
        px = ls_cx + (self.lx / 1000.0) * (r - 6)
        py = ls_cy - (self.ly / 1000.0) * (r - 6)
        stick_fill = COLOR_INVERT_BG if self.connected else COLOR_BORDER_LIGHT
        self.canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill=stick_fill, outline="")
        self.canvas.create_text(ls_cx, ls_cy + r + 10, text="LEFT (YAW / DEPTH)", fill=COLOR_TEXT_DIM, font=FONT_SMALL)

        # 2. Right Stick (Forward / Strafe)
        rs_cx = w * 0.78
        rs_cy = h * 0.52
        self.canvas.create_oval(rs_cx - r, rs_cy - r, rs_cx + r, rs_cy + r, outline=COLOR_BORDER_LIGHT, width=1)
        self.canvas.create_line(rs_cx - r, rs_cy, rs_cx + r, rs_cy, fill=COLOR_BORDER, width=1)
        self.canvas.create_line(rs_cx, rs_cy - r, rs_cx, rs_cy + r, fill=COLOR_BORDER, width=1)

        rpx = rs_cx + (self.rx / 1000.0) * (r - 6)
        rpy = rs_cy - (self.ry / 1000.0) * (r - 6)
        self.canvas.create_oval(rpx - 5, rpy - 5, rpx + 5, rpy + 5, fill=stick_fill, outline="")
        self.canvas.create_text(rs_cx, rs_cy + r + 10, text="RIGHT (FWD / LATERAL)", fill=COLOR_TEXT_DIM, font=FONT_SMALL)

        # 3. Center Control Buttons (A, B, X, Y, Start, Back)
        mid_x = w * 0.50
        buttons_layout = [
            ("X", -36, -10, self.buttons.get("btn_x", False)),
            ("Y", 0, -28, self.buttons.get("btn_y", False)),
            ("B", 36, -10, self.buttons.get("btn_b", False)),
            ("A", 0, 8, self.buttons.get("btn_a", False)),
            ("START", 24, 38, self.buttons.get("btn_start", False)),
            ("BACK", -24, 38, self.buttons.get("btn_back", False)),
        ]

        for label, dx, dy, active in buttons_layout:
            bx = mid_x + dx
            by = h * 0.45 + dy
            bw = 24 if len(label) <= 1 else 36
            bh = 18
            bg_col = COLOR_INVERT_BG if active else COLOR_SURFACE
            fg_col = COLOR_INVERT_FG if active else COLOR_TEXT_WHITE
            b_outline = COLOR_TEXT_WHITE if active else COLOR_BORDER

            self.canvas.create_rectangle(bx - bw/2, by - bh/2, bx + bw/2, by + bh/2, fill=bg_col, outline=b_outline)
            self.canvas.create_text(bx, by, text=label, fill=fg_col, font=FONT_SMALL)
