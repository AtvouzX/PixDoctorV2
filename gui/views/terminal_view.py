"""
PixDoctorV2 - Raw MAVLink & Nano Probe Serial Inspector View.
Displays real-time communication log stream, link health metrics,
and allows injecting raw probe commands (e.g. PING, RESET, RATE).
"""

import time
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
from core.mavlink_manager import MavlinkManager
from core.nano_probe_manager import NanoProbeManager


class TerminalView(tk.Frame):
    """Real-time console inspector and command terminal."""

    def __init__(
        self,
        parent,
        mav_mgr: MavlinkManager,
        nano_mgr: NanoProbeManager,
        **kwargs
    ):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.mav_mgr = mav_mgr
        self.nano_mgr = nano_mgr
        self.autoscroll = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        # Top Header & Controls
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            top_bar,
            text="[ SERIAL TELEMETRY & LOG TERMINAL ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        ).pack(side=tk.LEFT)

        btn_box = tk.Frame(top_bar, bg=COLOR_BG)
        btn_box.pack(side=tk.RIGHT)

        tk.Checkbutton(
            btn_box,
            text="AUTOSCROLL",
            variable=self.autoscroll,
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            selectcolor=COLOR_SURFACE,
            activebackground=COLOR_BG,
            activeforeground=COLOR_TEXT_WHITE,
            font=FONT_SMALL
        ).pack(side=tk.LEFT, padx=6)

        ttk.Button(btn_box, text="CLEAR LOG", style="Retro.TButton", command=self.clear_log).pack(side=tk.LEFT, padx=3)

        # Log Text Box
        log_frame = tk.Frame(self, bg=COLOR_SURFACE, highlightbackground=COLOR_BORDER, highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        self.txt_log = tk.Text(
            log_frame,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_SMALL,
            wrap="none",
            bd=0,
            padx=8,
            pady=8
        )
        scrollbar_y = ttk.Scrollbar(log_frame, orient="vertical", command=self.txt_log.yview)
        scrollbar_x = ttk.Scrollbar(log_frame, orient="horizontal", command=self.txt_log.xview)
        self.txt_log.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Command Injector Row
        cmd_row = tk.Frame(self, bg=COLOR_SURFACE, padx=10, pady=6, highlightbackground=COLOR_BORDER, highlightthickness=1)
        cmd_row.pack(fill=tk.X, padx=12, pady=(0, 10))

        tk.Label(cmd_row, text="PROBE COMMAND (ESP32 / NANO):", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 6))
        self.cmd_var = tk.StringVar()
        self.ent_cmd = ttk.Entry(cmd_row, textvariable=self.cmd_var, width=28)
        self.ent_cmd.bind("<Return>", lambda e: self._send_probe_cmd())
        self.ent_cmd.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(cmd_row, text="[ SEND ]", style="Retro.TButton", command=self._send_probe_cmd).pack(side=tk.LEFT, padx=(0, 10))

        # Quick Preset Buttons
        ttk.Button(cmd_row, text="PING", style="Retro.TButton", command=lambda: self.nano_mgr.send_command("PING")).pack(side=tk.LEFT, padx=2)
        ttk.Button(cmd_row, text="STATUS", style="Retro.TButton", command=lambda: self.nano_mgr.send_command("STATUS")).pack(side=tk.LEFT, padx=2)
        ttk.Button(cmd_row, text="RATE 20", style="Retro.TButton", command=lambda: self.nano_mgr.send_command("RATE 20")).pack(side=tk.LEFT, padx=2)
        ttk.Button(cmd_row, text="RESET", style="Retro.TButton", command=lambda: self.nano_mgr.send_command("RESET")).pack(side=tk.LEFT, padx=2)

    def _send_probe_cmd(self):
        cmd = self.cmd_var.get().strip()
        if cmd:
            self.nano_mgr.send_command(cmd)
            self.append_log(f"[SEND -> PROBE] {cmd}", "INFO")
            self.cmd_var.set("")

    def append_log(self, text: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {text}\n"

        self.txt_log.insert(tk.END, line)
        if self.autoscroll.get():
            self.txt_log.see(tk.END)

    def clear_log(self):
        self.txt_log.delete("1.0", tk.END)
