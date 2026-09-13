"""
PixDoctorV2 - Main Application Window & Navigation Host.
Coordinates background MAVLink, Nano Probe, Gamepad, and Auto-Detection threads.
Renders nostalgic monochrome top status strip and views workspace.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports

from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    COLOR_INVERT_BG,
    COLOR_INVERT_FG,
    FONT_TITLE,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
    configure_retro_styles,
)
from gui.widgets.mono_widgets import RetroCard, MetricCard, RetroPill, PwmBar
from gui.views.summary_view import SummaryView
from gui.views.thruster_view import ThrusterView
from gui.views.controller_view import ControllerView
from gui.views.calibration_view import CalibrationView
from gui.views.safety_view import SafetyView
from gui.views.flight_modes_view import FlightModesView
from gui.views.params_view import ParamsView
from gui.views.terminal_view import TerminalView

from core.mavlink_manager import MavlinkManager
from core.nano_probe_manager import NanoProbeManager
from core.gamepad_manager import GamepadManager
from core.param_manager import ParameterManager
from core.auto_detector import AutoDetector


class PixDoctorApp(tk.Tk):
    """Main application window for PixDoctorV2."""

    def __init__(self):
        super().__init__()

        self.title("PIXDOCTOR v2.0 // PIXHAWK 2.4.8 (ARDUSUB 4.7.1) SUITE")
        self.geometry("1280x820")
        self.minsize(1024, 700)
        self.config(bg=COLOR_BG)

        # Apply global nostalgic monochrome styles
        configure_retro_styles(self)

        # 1. Initialize Core Managers
        self.param_mgr = ParameterManager()
        self.mav_mgr = MavlinkManager(
            log_callback=self._log_event,
            param_callback=self._on_param_received
        )
        self.nano_mgr = NanoProbeManager(log_callback=self._log_event)
        self.gamepad_mgr = GamepadManager(action_callback=self._on_gamepad_action)
        self._cam_tilt_pwm: int = 1500
        self._lights_pwm: int = 1100

        # 2. Auto-Detector (Default ON: scans ports and auto-connects)
        self.auto_detector = AutoDetector(
            mav_mgr=self.mav_mgr,
            nano_mgr=self.nano_mgr,
            status_callback=self._log_event
        )

        # 3. Build UI Components
        self._build_top_status_strip()
        self._build_main_body()

        # 4. Start Background Engines
        self.gamepad_mgr.start()
        self.auto_detector.start()

        # 5. Kick off 20Hz UI Telemetry Refresh Loop
        self.after(50, self._ui_telemetry_tick)

        # Window closing handler
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_top_status_strip(self):
        """Build top retro avionics status bar."""
        self.top_strip = tk.Frame(
            self,
            bg=COLOR_SURFACE,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=10,
            pady=6
        )
        self.top_strip.pack(fill=tk.X, side=tk.TOP)

        # Left: App Logo & Target Hardware
        brand_frame = tk.Frame(self.top_strip, bg=COLOR_SURFACE)
        brand_frame.pack(side=tk.LEFT)

        tk.Label(
            brand_frame,
            text="PIXDOCTOR",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_TITLE
        ).pack(side=tk.LEFT)

        tk.Label(
            brand_frame,
            text="v2.0 [ARDUSUB 4.7.1 / PIXHAWK 2.4.8]",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL,
            padx=8
        ).pack(side=tk.LEFT)

        # Right: Hardware Status Badges
        badge_frame = tk.Frame(self.top_strip, bg=COLOR_SURFACE)
        badge_frame.pack(side=tk.RIGHT)

        self.pill_pixhawk = RetroPill(badge_frame, text="PIXHAWK: AUTO-SCAN", active=False)
        self.pill_pixhawk.pack(side=tk.LEFT, padx=3)

        self.pill_nano = RetroPill(badge_frame, text="PROBE: SCAN", active=False)
        self.pill_nano.pack(side=tk.LEFT, padx=3)

        self.pill_gamepad = RetroPill(badge_frame, text="GAMEPAD: STANDBY", active=False)
        self.pill_gamepad.pack(side=tk.LEFT, padx=3)

        self.pill_arm = RetroPill(badge_frame, text="DISARMED", active=False)
        self.pill_arm.pack(side=tk.LEFT, padx=3)

        self.pill_mode = RetroPill(badge_frame, text="MANUAL", active=True)
        self.pill_mode.pack(side=tk.LEFT, padx=3)

        # Manual Link Dialog Button
        btn_conn = ttk.Button(
            badge_frame,
            text="PORTS",
            style="Retro.TButton",
            command=self._show_port_dialog
        )
        btn_conn.pack(side=tk.LEFT, padx=(6, 0))

    def _build_main_body(self):
        """Construct sidebar and workspace container."""
        self.body_frame = tk.Frame(self, bg=COLOR_BG)
        self.body_frame.pack(fill=tk.BOTH, expand=True)

        # Left Navigation Sidebar
        self.sidebar = tk.Frame(
            self.body_frame,
            bg=COLOR_SURFACE,
            width=230,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=6,
            pady=10
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Navigation Header
        tk.Label(
            self.sidebar,
            text="[ NAVIGATION MENU ]",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        ).pack(anchor="w", padx=4, pady=(0, 8))

        # View Workspace
        self.workspace = tk.Frame(self.body_frame, bg=COLOR_BG)
        self.workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Initialize Views
        self.views = {
            "summary": SummaryView(self.workspace, mav_mgr=self.mav_mgr),
            "thrusters": ThrusterView(
                self.workspace,
                mav_mgr=self.mav_mgr,
                nano_mgr=self.nano_mgr,
                param_mgr=self.param_mgr,
                gamepad_mgr=self.gamepad_mgr
            ),
            "controller": ControllerView(
                self.workspace,
                gamepad_mgr=self.gamepad_mgr,
                mav_mgr=self.mav_mgr
            ),
            "calibration": CalibrationView(self.workspace, mav_mgr=self.mav_mgr),
            "safety": SafetyView(
                self.workspace,
                param_mgr=self.param_mgr,
                mav_mgr=self.mav_mgr
            ),
            "modes": FlightModesView(
                self.workspace,
                param_mgr=self.param_mgr,
                mav_mgr=self.mav_mgr
            ),
            "params": ParamsView(
                self.workspace,
                param_mgr=self.param_mgr,
                mav_mgr=self.mav_mgr
            ),
            "terminal": TerminalView(
                self.workspace,
                mav_mgr=self.mav_mgr,
                nano_mgr=self.nano_mgr
            ),
        }

        # Build Navigation Buttons
        nav_items = [
            ("summary", "[ 01 ] SUMMARY / HUD"),
            ("thrusters", "[ 02 ] SIMPLE-ROV 4 THRUSTERS"),
            ("controller", "[ 03 ] GAMEPAD / XINPUT"),
            ("calibration", "[ 04 ] SENSOR CALIBRATION"),
            ("safety", "[ 05 ] SAFETY & FAILSAFES"),
            ("modes", "[ 06 ] FLIGHT MODES"),
            ("params", "[ 07 ] PARAMETER TREE"),
            ("terminal", "[ 08 ] SERIAL TERMINAL"),
        ]

        self.nav_buttons = {}
        for key, text in nav_items:
            btn = ttk.Button(
                self.sidebar,
                text=text,
                style="Retro.TButton",
                command=lambda k=key: self.switch_view(k)
            )
            btn.pack(fill=tk.X, pady=2)
            self.nav_buttons[key] = btn

        # Bottom Sidebar Simulator Toggle (Default OFF)
        sim_frame = tk.Frame(self.sidebar, bg=COLOR_SURFACE)
        sim_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 4))

        tk.Frame(sim_frame, bg=COLOR_BORDER, height=1).pack(fill=tk.X, pady=(0, 6))

        self.sim_active = tk.BooleanVar(value=False)
        self.chk_sim = tk.Checkbutton(
            sim_frame,
            text="OFFLINE SIMULATOR",
            variable=self.sim_active,
            command=self._toggle_sim,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SURFACE,
            activeforeground=COLOR_TEXT_WHITE,
            font=FONT_SMALL
        )
        self.chk_sim.pack(anchor="w")

        # Select Default View
        self.active_view_key = None
        self.switch_view("summary")

    def switch_view(self, view_key: str):
        """Switch workspace content to selected view."""
        if view_key not in self.views:
            return

        # Hide old view
        if self.active_view_key and self.active_view_key in self.views:
            self.views[self.active_view_key].pack_forget()
            self.nav_buttons[self.active_view_key].config(style="Retro.TButton")

        # Show new view
        self.active_view_key = view_key
        self.views[view_key].pack(fill=tk.BOTH, expand=True)
        self.nav_buttons[view_key].config(style="Invert.TButton")

    def _ui_telemetry_tick(self):
        """20Hz master telemetry dispatcher for UI responsiveness."""
        try:
            mav_snap = self.mav_mgr.state.get_snapshot()
            nano_snap = self.nano_mgr.state.get_snapshot()
            pad_snap = self.gamepad_mgr.state.get_snapshot()

            # 1. Update Top Badges
            # Pixhawk Badge
            if mav_snap["connected"]:
                p_text = f"PIXHAWK: {mav_snap['port']} ({mav_snap['packet_rate_hz']:.0f}Hz)"
                self.pill_pixhawk.set_state(active=True, text=p_text)
            else:
                self.pill_pixhawk.set_state(active=False, text="PIXHAWK: AUTO-SCAN")

            # Hardware Probe (ESP32 / Nano) Badge
            if nano_snap["connected"]:
                dev = nano_snap.get("device_info", "")
                tag = "ESP32" if "ESP32" in dev.upper() else ("NANO" if "NANO" in dev.upper() else "PROBE")
                n_text = f"{tag}: {nano_snap['port']} ({nano_snap['packet_rate_hz']:.0f}Hz)"
                self.pill_nano.set_state(active=True, text=n_text)
            else:
                self.pill_nano.set_state(active=False, text="PROBE: SCAN")

            # Gamepad Badge
            if pad_snap["connected"]:
                g_text = f"GAMEPAD: {pad_snap['backend']}"
                self.pill_gamepad.set_state(active=True, text=g_text)
            else:
                self.pill_gamepad.set_state(active=False, text="GAMEPAD: STANDBY")

            # Arm Badge
            if mav_snap["armed"]:
                self.pill_arm.set_state(active=True, text="ARMED")
            else:
                self.pill_arm.set_state(active=False, text="DISARMED")

            # Mode Badge
            self.pill_mode.set_state(active=True, text=mav_snap["flight_mode_name"])

            # 2. Dispatch to Active Views
            if self.active_view_key == "summary":
                self.views["summary"].update_telemetry(mav_snap)
            elif self.active_view_key == "thrusters":
                self.views["thrusters"].update_telemetry(mav_snap, nano_snap)
            elif self.active_view_key == "controller":
                self.views["controller"].update_gamepad_telemetry(pad_snap)
            elif self.active_view_key == "calibration":
                self.views["calibration"].update_telemetry(mav_snap)

        except Exception as e:
            pass

        # Schedule next tick in 50ms (20 Hz)
        self.after(50, self._ui_telemetry_tick)

    def _on_param_received(self, name: str, val: float, ptype: int):
        """MAVLink PARAM_VALUE received."""
        self.param_mgr.update_param(name, val, ptype)
        if self.active_view_key == "params":
            self.views["params"].refresh_table()

    def _on_gamepad_action(self, action: str, arg: any):
        """Dispatch gamepad button event to Pixhawk."""
        self._log_event(f"[GAMEPAD ACTION] Triggered: {action}", "INFO")

        if action == "TOGGLE_ARM":
            curr_armed = self.mav_mgr.state.armed
            self.mav_mgr.arm(not curr_armed)
        elif action == "DISARM":
            self.mav_mgr.arm(False)
        elif action == "CYCLE_MODE":
            curr_mode = self.mav_mgr.state.custom_mode
            # Cycle through Manual (19) -> Depth Hold (2) -> Stabilize (0)
            next_mode = 2 if curr_mode == 19 else (0 if curr_mode == 2 else 19)
            self.mav_mgr.set_flight_mode(next_mode)
        elif action == "MODE_MANUAL":
            self.mav_mgr.set_flight_mode(19)
        elif action == "MODE_ALT_HOLD":
            self.mav_mgr.set_flight_mode(2)
        elif action == "MODE_STABILIZE":
            self.mav_mgr.set_flight_mode(0)
        elif action == "GAIN_INCREASE":
            g = min(1.0, self.gamepad_mgr.state.gain + 0.25)
            self.gamepad_mgr.set_gain(g)
        elif action == "GAIN_DECREASE":
            g = max(0.25, self.gamepad_mgr.state.gain - 0.25)
            self.gamepad_mgr.set_gain(g)
        elif action == "CAMERA_TILT_UP":
            self._cam_tilt_pwm = min(1900, self._cam_tilt_pwm + 50)
            self.mav_mgr.set_servo_override(10, self._cam_tilt_pwm)
        elif action == "CAMERA_TILT_DOWN":
            self._cam_tilt_pwm = max(1100, self._cam_tilt_pwm - 50)
            self.mav_mgr.set_servo_override(10, self._cam_tilt_pwm)
        elif action == "CAMERA_TILT_CENTER":
            self._cam_tilt_pwm = 1500
            self.mav_mgr.set_servo_override(10, 1500)
        elif action == "LIGHTS_CYCLE":
            steps = [1100, 1300, 1500, 1900]
            try:
                curr_idx = steps.index(self._lights_pwm)
                self._lights_pwm = steps[(curr_idx + 1) % len(steps)]
            except ValueError:
                self._lights_pwm = 1300
            self.mav_mgr.set_servo_override(11, self._lights_pwm)
        elif action == "LIGHTS_OFF":
            self._lights_pwm = 1100
            self.mav_mgr.set_servo_override(11, 1100)

    def _toggle_sim(self):
        """Toggle offline mock simulator."""
        if self.sim_active.get():
            self.auto_detector.stop()
            self.mav_mgr.connect("MOCK")
        else:
            self.mav_mgr.disconnect()
            self.auto_detector.start()

    def _show_port_dialog(self):
        """Manual COM port and connection selector dialog."""
        win = tk.Toplevel(self)
        win.title("Connection & Port Management")
        win.geometry("520x400")
        win.config(bg=COLOR_BG)
        win.transient(self)
        win.grab_set()

        card = RetroCard(win, title="Manual Port Configuration")
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def get_ports():
            pts = []
            for p in serial.tools.list_ports.comports():
                pts.append(f"{p.device} - {p.description}")
            pts.extend(["udp:0.0.0.0:14550", "udp:192.168.2.1:14550", "udp:127.0.0.1:14550"])
            return pts

        ports = get_ports()

        # Top Refresh Button Row
        hdr_row = tk.Frame(card.body, bg=COLOR_SURFACE)
        hdr_row.pack(fill=tk.X, pady=(0, 8))

        lbl_scan_info = tk.Label(
            hdr_row,
            text=f"DETECTED {len(ports)} PORTS / ENDPOINTS",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL
        )
        lbl_scan_info.pack(side=tk.LEFT)

        def _refresh():
            new_ports = get_ports()
            cb_pix["values"] = new_ports
            cb_nano["values"] = new_ports
            lbl_scan_info.config(text=f"DETECTED {len(new_ports)} PORTS / ENDPOINTS")

        ttk.Button(hdr_row, text="REFRESH LIST", style="Retro.TButton", command=_refresh).pack(side=tk.RIGHT)

        # Pixhawk Port Row
        p_row = tk.Frame(card.body, bg=COLOR_SURFACE)
        p_row.pack(fill=tk.X, pady=4)
        tk.Label(p_row, text="PIXHAWK PORT:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=18, anchor="w").pack(side=tk.LEFT)
        pix_var = tk.StringVar(value=ports[0])
        cb_pix = ttk.Combobox(p_row, textvariable=pix_var, values=ports, width=32)
        cb_pix.pack(side=tk.LEFT)

        # Pixhawk Baud
        b_row = tk.Frame(card.body, bg=COLOR_SURFACE)
        b_row.pack(fill=tk.X, pady=4)
        tk.Label(b_row, text="PIXHAWK BAUD:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=18, anchor="w").pack(side=tk.LEFT)
        baud_var = tk.IntVar(value=115200)
        cb_baud = ttk.Combobox(b_row, textvariable=baud_var, values=[115200, 57600, 921600], width=12, state="readonly")
        cb_baud.pack(side=tk.LEFT)
        tk.Label(b_row, text="(115200 USB / 57600 TELEM)", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=6)

        # Hardware Probe (ESP32 / Nano) Port Row
        n_row = tk.Frame(card.body, bg=COLOR_SURFACE)
        n_row.pack(fill=tk.X, pady=4)
        tk.Label(n_row, text="PROBE PORT (ESP32/NANO):", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_SMALL, width=22, anchor="w").pack(side=tk.LEFT)
        nano_var = tk.StringVar(value=ports[0])
        cb_nano = ttk.Combobox(n_row, textvariable=nano_var, values=ports, width=30)
        cb_nano.pack(side=tk.LEFT)

        # Connection Status
        status_box = tk.Frame(card.body, bg=COLOR_SURFACE, pady=6)
        status_box.pack(fill=tk.X, pady=(8, 0))

        probe_status = f"ONLINE ({self.nano_mgr.state.device_info})" if self.nano_mgr.state.connected else "OFFLINE"
        lbl_cur_status = tk.Label(
            status_box,
            text=f"STATUS: Pixhawk {'ONLINE' if self.mav_mgr.is_connected() else 'OFFLINE'} | "
                 f"Probe {probe_status}",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD
        )
        lbl_cur_status.pack(anchor="w")

        def _apply():
            p_port = pix_var.get().split(" ")[0].strip()
            p_baud = int(baud_var.get())
            n_port = nano_var.get().split(" ")[0].strip()

            if p_port:
                self.mav_mgr.connect(p_port, p_baud)
            if n_port:
                self.nano_mgr.connect(n_port, 115200)
            win.destroy()

        btn_row = tk.Frame(card.body, bg=COLOR_SURFACE)
        btn_row.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(btn_row, text="[ CONNECT SELECTED ]", style="Invert.TButton", command=_apply).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="DISCONNECT ALL", style="Retro.TButton", command=lambda: [self.mav_mgr.disconnect(), self.nano_mgr.disconnect()]).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="CLOSE", style="Retro.TButton", command=win.destroy).pack(side=tk.RIGHT)

    def _log_event(self, text: str, level: str = "INFO"):
        """Append event to terminal log view."""
        if "terminal" in self.views:
            self.views["terminal"].append_log(text, level)

    def _on_closing(self):
        """Clean shutdown of all threads."""
        self.auto_detector.stop()
        self.gamepad_mgr.stop()
        self.mav_mgr.disconnect()
        self.nano_mgr.disconnect()
        self.destroy()
