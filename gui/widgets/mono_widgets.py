"""
PixDoctorV2 - Reusable Nostalgic Monochrome Widgets.
Simple, tactile, high-contrast UI components built with native Tkinter.
"""

import tkinter as tk
from tkinter import ttk
from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    COLOR_TEXT_FAINT,
    COLOR_INVERT_BG,
    COLOR_INVERT_FG,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
    FONT_LARGE_NUM,
)


class RetroCard(tk.Frame):
    """Bordered console box with classic bracket header [ HEADER TITLE ]."""

    def __init__(self, parent, title: str = "", **kwargs):
        super().__init__(
            parent,
            bg=COLOR_SURFACE,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            bd=0,
            **kwargs
        )
        self.title_text = title

        # Header Bar
        if title:
            self.header_frame = tk.Frame(self, bg=COLOR_SURFACE, padx=8, pady=4)
            self.header_frame.pack(fill=tk.X, side=tk.TOP)

            self.header_lbl = tk.Label(
                self.header_frame,
                text=f"[ {title.upper()} ]",
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_WHITE,
                font=FONT_HEADER,
                anchor="w"
            )
            self.header_lbl.pack(side=tk.LEFT)

            # Horizontal divider line
            self.divider = tk.Frame(self, bg=COLOR_BORDER, height=1)
            self.divider.pack(fill=tk.X, side=tk.TOP)

        # Body container
        self.body = tk.Frame(self, bg=COLOR_SURFACE, padx=10, pady=8)
        self.body.pack(fill=tk.BOTH, expand=True)


class MetricCard(tk.Frame):
    """High-contrast monospace telemetry readout block."""

    def __init__(self, parent, label: str, value: str = "--", unit: str = "", **kwargs):
        super().__init__(
            parent,
            bg=COLOR_SURFACE,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=8,
            pady=6,
            **kwargs
        )
        self.label_var = tk.StringVar(value=label.upper())
        self.value_var = tk.StringVar(value=value)
        self.unit_var = tk.StringVar(value=unit)

        self.lbl_title = tk.Label(
            self,
            textvariable=self.label_var,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL,
            anchor="w"
        )
        self.lbl_title.pack(fill=tk.X)

        val_frame = tk.Frame(self, bg=COLOR_SURFACE)
        val_frame.pack(fill=tk.X, pady=(2, 0))

        self.lbl_val = tk.Label(
            val_frame,
            textvariable=self.value_var,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_LARGE_NUM,
            anchor="w"
        )
        self.lbl_val.pack(side=tk.LEFT)

        if unit:
            self.lbl_unit = tk.Label(
                val_frame,
                textvariable=self.unit_var,
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_DIM,
                font=FONT_SMALL,
                anchor="sw",
                padx=4,
                pady=4
            )
            self.lbl_unit.pack(side=tk.LEFT)

    def set_value(self, val: str):
        self.value_var.set(val)


class RetroPill(tk.Label):
    """Tactile status pill badge with high-contrast active states."""

    def __init__(self, parent, text: str = "OFFLINE", active: bool = False, **kwargs):
        super().__init__(
            parent,
            font=FONT_BODY_BOLD,
            padx=8,
            pady=2,
            bd=1,
            relief="solid",
            **kwargs
        )
        self.set_state(active, text)

    def set_state(self, active: bool, text: str = None):
        if text:
            self.config(text=f"[ {text.upper()} ]")
        if active:
            self.config(
                bg=COLOR_INVERT_BG,
                fg=COLOR_INVERT_FG,
                highlightbackground=COLOR_TEXT_WHITE
            )
        else:
            self.config(
                bg=COLOR_SURFACE,
                fg=COLOR_TEXT_DIM,
                highlightbackground=COLOR_BORDER
            )


class PwmBar(tk.Frame):
    """
    Microsecond PWM pulse bar gauge (1000..2000µs).
    Draws center-neutral bar at 1500µs with delta comparison for Nano probe.
    """

    def __init__(self, parent, channel_name: str, **kwargs):
        super().__init__(parent, bg=COLOR_SURFACE, **kwargs)

        self.channel_name = channel_name
        self.cmd_pwm = 1500
        self.measured_pwm = 0
        self.measured_hz = 0.0
        self.is_valid = False

        # Header with channel name and values
        top_frame = tk.Frame(self, bg=COLOR_SURFACE)
        top_frame.pack(fill=tk.X, pady=(0, 2))

        self.lbl_name = tk.Label(
            top_frame,
            text=channel_name,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        self.lbl_name.pack(side=tk.LEFT)

        self.lbl_stats = tk.Label(
            top_frame,
            text="CMD:1500µs | NANO:  --µs | Δ:  --µs |  --.-Hz",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL,
            width=44,
            anchor="e"
        )
        self.lbl_stats.pack(side=tk.RIGHT)

        # Canvas gauge
        self.canvas = tk.Canvas(
            self,
            bg=COLOR_BG,
            height=14,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1
        )
        self.canvas.pack(fill=tk.X, expand=True)

        self.canvas.bind("<Configure>", lambda e: self.redraw())

    def update_readings(self, cmd_pwm: int, meas_pwm: int, meas_hz: float, valid: bool):
        self.cmd_pwm = cmd_pwm
        self.measured_pwm = meas_pwm
        self.measured_hz = meas_hz
        self.is_valid = valid

        # Format stats text with fixed column widths to eliminate visual text jitter
        if valid and meas_pwm > 0:
            delta = meas_pwm - cmd_pwm
            stats_str = f"CMD:{cmd_pwm:4d}µs | NANO:{meas_pwm:4d}µs | Δ:{delta:+4d}µs | {meas_hz:4.1f}Hz"
        else:
            stats_str = f"CMD:{cmd_pwm:4d}µs | NANO:  --µs | Δ:  --µs |  --.-Hz"
        self.lbl_stats.config(text=stats_str)
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 10:
            return

        # Neutral 1500 line
        cx = w / 2.0
        self.canvas.create_line(cx, 0, cx, h, fill=COLOR_BORDER_LIGHT, width=1)

        # Draw Commanded PWM tick
        cmd_clamped = max(1000, min(2000, self.cmd_pwm))
        cmd_x = ((cmd_clamped - 1000) / 1000.0) * w
        self.canvas.create_line(cmd_x, 0, cmd_x, h, fill=COLOR_TEXT_DIM, width=2)

        # Draw Nano Measured pulse bar
        if self.is_valid and self.measured_pwm > 0:
            meas_clamped = max(1000, min(2000, self.measured_pwm))
            meas_x = ((meas_clamped - 1000) / 1000.0) * w
            # Fill between center (1500) and current measured
            x0 = min(cx, meas_x)
            x1 = max(cx, meas_x)
            self.canvas.create_rectangle(x0, 2, x1, h - 2, fill=COLOR_TEXT_WHITE, outline="")
            self.canvas.create_line(meas_x, 0, meas_x, h, fill=COLOR_INVERT_BG, width=2)
