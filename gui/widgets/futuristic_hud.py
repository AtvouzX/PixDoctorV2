"""
PixDoctorV2 - Military Fighter Jet HUD & Submersible ROV Tactical Flight Display.
Renders an authentic aircraft Heads-Up Display (MIL-STD pitch ladder, roll arc,
waterline symbol, flight path marker, top heading tape, side depth tape) coupled with
a clean, frame-adaptive 2D top-down ROV schematic featuring 2D thruster ducts,
spinning propellers, dynamic thrust plumes, and live telemetry data pods.
"""

import math
import random
import tkinter as tk
from typing import Dict, Any, Optional, List, Tuple
from core.ardusub_defs import FRAMES, DEFAULT_FRAME_ID, compute_thruster_pwms
from core.motor_matrix_manager import MotorMatrixManager

# Futuristic Jet HUD Symbology Palette
COLOR_HUD_BG = "#060608"
COLOR_HUD_GRID = "#0f1118"
COLOR_CYAN = "#00f0ff"
COLOR_CYAN_DIM = "#007a99"
COLOR_GREEN = "#00ff88"
COLOR_GREEN_DIM = "#006633"
COLOR_RED = "#ff3355"
COLOR_AMBER = "#ffaa00"
COLOR_YELLOW = "#ffe600"
COLOR_WHITE = "#ffffff"
COLOR_DIM = "#71717a"
COLOR_FAINT = "#22222c"
COLOR_BORDER = "#22222c"
COLOR_BORDER_LIGHT = "#3a3a48"
COLOR_TEXT_DIM = "#71717a"
COLOR_TEXT_WHITE = "#ffffff"

FONT_HUD_TITLE = ("Consolas", 12, "bold")
FONT_HUD_BOLD = ("Consolas", 10, "bold")
FONT_HUD_REG = ("Consolas", 9, "normal")
FONT_HUD_SMALL = ("Consolas", 8, "normal")
FONT_HUD_LARGE = ("Consolas", 18, "bold")
FONT_HUD_HUGE = ("Consolas", 24, "bold")


class SubseaParticle:
    """3D subsea marine snow particle for flight flow streaks."""
    def __init__(self, w: float, h: float):
        self.reset(w, h, random_z=True)

    def reset(self, w: float, h: float, random_z: bool = False):
        self.x = random.uniform(-w, w)
        self.y = random.uniform(-h, h)
        self.z = random.uniform(40, 600) if random_z else 600.0


class FuturisticHud(tk.Canvas):
    """Unified full-window fighter jet avionics HUD & 2D ROV flight visualizer."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg=COLOR_HUD_BG,
            highlightthickness=0,
            **kwargs
        )

        # Telemetry State
        self.roll: float = 0.0
        self.pitch: float = 0.0
        self.heading: float = 0.0
        self.depth: float = 0.0
        self.vert_speed: float = 0.0
        self.pressure: float = 1.013
        self.temp: float = 24.0
        self.batt_v: float = 0.0
        self.batt_a: float = 0.0
        self.vcc_v: float = 5.05
        self.armed: bool = False
        self.mode_name: str = "MANUAL"
        self.leak_alert: bool = False
        self.statustext: str = "System Standby"
        self.packet_rate: float = 20.0

        # Gamepad / Flight Control State
        self.gamepad_connected: bool = False
        self.controller_name: str = "Disconnected"
        self.gain: float = 0.50
        self.cmd_fwd: int = 0
        self.cmd_lat: int = 0
        self.cmd_depth: int = 0
        self.cmd_yaw: int = 0
        self.in_flight: bool = False
        self.matrix_mgr = MotorMatrixManager.get_instance()

        # Telemetry vs Full HUD Graphics Toggle
        self.show_hud_graphics: bool = True

        # Physical Thruster-Derived Motion Vectors (-1.0 to +1.0)
        self.thrust_fwd: float = 0.0
        self.thrust_lat: float = 0.0
        self.thrust_depth: float = 0.0
        self.thrust_yaw: float = 0.0

        # Vehicle Frame & Motor Telemetry State
        self.frame_id: int = DEFAULT_FRAME_ID
        self.motor_cmd_pwm: List[int] = [1500] * 8
        self.motor_probe_pwm: List[int] = [0] * 8
        self.motor_probe_valid: List[bool] = [False] * 8
        self._prop_angles: Dict[int, float] = {i: 0.0 for i in range(1, 9)}

        # Animation state
        self._prev_depth: float = 0.0
        self._prop_angle: float = 0.0
        self._anim_tick: int = 0

        # Subsea particles for flow visualization
        self.particles = [SubseaParticle(800, 600) for _ in range(40)]

        self.bind("<Configure>", lambda e: self.redraw())

    def set_frame_id(self, frame_id: int):
        """Sets the active ArduSub vehicle frame."""
        if self.frame_id != frame_id:
            self.frame_id = frame_id
            self.redraw()

    def set_hud_graphics_mode(self, enabled: bool):
        """Toggle between full jet HUD avionics graphics and pure digital telemetry mode."""
        self.show_hud_graphics = bool(enabled)
        self.redraw()

    def update_telemetry(
        self,
        mav_snap: Dict[str, Any],
        pad_snap: Optional[Dict[str, Any]] = None,
        nano_snap: Optional[Dict[str, Any]] = None
    ):
        """Update live flight data from MAVLink, Gamepad, and Hardware Probe."""
        self.roll = mav_snap.get("roll", 0.0)
        self.pitch = mav_snap.get("pitch", 0.0)
        self.heading = mav_snap.get("yaw", 0.0)
        
        new_depth = mav_snap.get("depth", 0.0)
        # Compute vertical speed in m/s (20Hz loop -> dt = 0.05s)
        self.vert_speed = (new_depth - self._prev_depth) / 0.05 if self._prev_depth > 0 else 0.0
        self._prev_depth = new_depth
        self.depth = new_depth

        self.pressure = mav_snap.get("pressure_bar", 1.013)
        self.temp = mav_snap.get("temperature", 24.0)
        self.batt_v = mav_snap.get("battery_voltage", 0.0)
        self.batt_a = mav_snap.get("battery_current", 0.0)
        self.vcc_v = mav_snap.get("vcc_voltage", 5.05)
        self.armed = mav_snap.get("armed", False)
        self.mode_name = mav_snap.get("flight_mode_name", "MANUAL")
        self.leak_alert = mav_snap.get("leak", False)
        self.statustext = mav_snap.get("statustext", "Standby")
        self.packet_rate = mav_snap.get("packet_rate_hz", 20.0)

        # Gamepad Inputs (respects active flight stick steering mode)
        if pad_snap:
            self.gamepad_connected = pad_snap.get("connected", False)
            self.controller_name = pad_snap.get("controller_name", "Disconnected")
            self.gain = pad_snap.get("gain", 0.50)
            cmds = self.matrix_mgr.extract_gamepad_commands(pad_snap)
            self.cmd_fwd = cmds["fwd"]
            self.cmd_lat = cmds["lat"]
            self.cmd_depth = cmds["depth"]
            self.cmd_yaw = cmds["yaw"]
        else:
            self.cmd_fwd = 0
            self.cmd_lat = 0
            self.cmd_depth = 0
            self.cmd_yaw = 0

        # Stick magnitude check
        stick_magnitude = math.sqrt(self.cmd_fwd**2 + self.cmd_lat**2 + self.cmd_depth**2 + self.cmd_yaw**2)

        # 1. Update Commanded Motor Outputs (Frame-Accurate Zero-Latency Sync with Matrix & Probe Parity)
        pred_pwms = self.matrix_mgr.compute_motor_pwms(
            fwd=self.cmd_fwd,
            lat=self.cmd_lat,
            depth=self.cmd_depth,
            yaw=self.cmd_yaw,
            armed=True
        )

        servos = mav_snap.get("servo_raw") or []
        has_servos = bool(servos and any(s > 0 for s in servos))

        for i in range(8):
            if has_servos:
                # Direct authoritative telemetry parity with Tab 2 Thruster Test & MAVLink
                if i < len(servos) and servos[i] > 0:
                    self.motor_cmd_pwm[i] = int(servos[i])
                else:
                    self.motor_cmd_pwm[i] = 1500
            else:
                # Standalone fallback when servo_raw is not streamed (e.g. offline desk simulation or bench testing)
                if stick_magnitude > 40:
                    self.motor_cmd_pwm[i] = pred_pwms[i]
                else:
                    self.motor_cmd_pwm[i] = 1500

        # 2. Update Measured Motor Outputs from Logic Probe (ESP32/Nano)
        if nano_snap and nano_snap.get("connected", False):
            meas = nano_snap.get("measured_pwm", [])
            valids = nano_snap.get("signal_valid", [])
            for i in range(min(8, len(meas))):
                val = int(meas[i])
                is_v = valids[i] if i < len(valids) else (val > 800)
                self.motor_probe_pwm[i] = val
                self.motor_probe_valid[i] = is_v
        else:
            for i in range(8):
                self.motor_probe_valid[i] = False

        # 3. Calculate Normalized Thruster Outputs & Physical Motion Vectors from Thruster Data
        motor_thrusts: List[float] = []
        for i in range(8):
            # Prefer probe PWM if verified valid hardware signal, else commanded PWM
            pwm = self.motor_probe_pwm[i] if (self.motor_probe_valid[i] and self.motor_probe_pwm[i] > 800) else self.motor_cmd_pwm[i]
            diff = pwm - 1500
            if abs(diff) < 20:
                t = 0.0
            else:
                t = max(-1.0, min(1.0, diff / 400.0))
            motor_thrusts.append(t)

        # In-flight is true if armed and any motor is actively producing thrust
        max_t = max([abs(t) for t in motor_thrusts] + [0.0])
        self.in_flight = self.armed and (max_t > 0.05)

        # Project motor thrusts back through motor matrix to get true directional thrust vectors
        matrix = self.matrix_mgr.matrix
        def _calc_axis_thrust(axis_name: str) -> float:
            axis_weights = matrix.get(axis_name, {})
            weighted_sum = 0.0
            sum_abs_weights = 0.0
            for idx in range(8):
                m_num = idx + 1
                w = float(axis_weights.get(m_num, axis_weights.get(str(m_num), axis_weights.get(f"m{m_num}", 0.0))))
                if abs(w) > 0.01:
                    weighted_sum += motor_thrusts[idx] * w
                    sum_abs_weights += abs(w)
            return (weighted_sum / sum_abs_weights) if sum_abs_weights > 0.01 else 0.0

        self.thrust_fwd = max(-1.0, min(1.0, _calc_axis_thrust("fwd")))
        self.thrust_lat = max(-1.0, min(1.0, _calc_axis_thrust("lat"))) if self._has_lateral_capability() else 0.0
        self.thrust_depth = max(-1.0, min(1.0, _calc_axis_thrust("depth")))
        self.thrust_yaw = max(-1.0, min(1.0, _calc_axis_thrust("yaw")))

        # 4. Update Propeller Spin Angles per Motor (Synchronous with active PWM output)
        for i in range(8):
            pwm = self.motor_cmd_pwm[i]
            diff = pwm - 1500
            if abs(diff) > 20:
                spin = diff / 10.0
            elif self.armed:
                spin = 4.0  # Smooth idle spin when armed
            else:
                spin = 0.0
            self._prop_angles[i + 1] = (self._prop_angles[i + 1] + spin) % 360.0

        # Main ambient propeller spin angle
        if self.armed:
            spin_speed = 45.0 if self.in_flight else 15.0
            self._prop_angle = (self._prop_angle + spin_speed) % 360.0

        self._anim_tick = (self._anim_tick + 1) % 60
        self.redraw()

    def redraw(self):
        try:
            self.delete("all")
            w = self.winfo_width()
            h = self.winfo_height()
            if w <= 100 or h <= 100:
                return

            if not self.show_hud_graphics:
                self._draw_pure_telemetry_dashboard(w, h)
                return

            cx = w / 2.0
            # Jet HUD center horizon positioned slightly above midpoint for natural sightline
            cy = h * 0.38

            # 1. Subtle Cockpit Glass Background Grid & Corner Brackets
            self._draw_hud_grid_and_brackets(w, h)

            # 2. Subsea Flight Particles (Speed streaks when armed & flying)
            self._draw_particles(w, h, cx, cy)

            # 3. Authentic Fighter Jet Pitch Ladder (Positive solid, Negative dashed, with hooks)
            self._draw_jet_pitch_ladder(cx, cy, w, h)

            # 4. Aircraft Boresight / Waterline Symbol (Fixed center)
            self._draw_aircraft_waterline(cx, cy)

            # 4b. Jet Tactical Turn Rate / Yaw Slip Coordinator
            self._draw_jet_turn_rate_indicator(cx, cy)

            # 5. Jet Bank Angle Arc & Roll Pointer
            self._draw_jet_roll_arc(cx, cy)

            # 6. Dynamic Flight Path Marker (Velocity Vector Indicator)
            self._draw_flight_path_marker(cx, cy)

            # 7. Jet Horizontal Compass Tape (Top Side Center)
            self._draw_jet_compass_tape(w, cx)

            # 8. Side Vertical Tapes (Generously spaced from pods and center HUD)
            tape_top = 58.0
            tape_bot = h - 95.0
            tape_l_x = 224.0
            tape_r_x = w - 224.0
            self._draw_jet_depth_tape(tape_l_x, tape_top, tape_bot)
            self._draw_jet_thrust_tape(tape_r_x, tape_top, tape_bot)

            # 9. Tactical Corner Telemetry Pods (Classic spacious arrangement, zero overlap)
            pod_w = 195.0
            pod_h = 78.0
            # Top-Left: Power & Battery Rails
            self._draw_power_pod(18.0, 50.0, w=pod_w, h=pod_h)
            # Top-Right: Environment & Hull Health
            self._draw_environment_pod(w - pod_w - 18.0, 50.0, w=pod_w, h=pod_h)
            # Bottom-Left: Flight Safety & Attitude Status
            self._draw_flight_status_pod(18.0, h - pod_h - 18.0, w=pod_w, h=pod_h)
            # Bottom-Right: Pilot Inputs & Gain
            self._draw_pilot_pod(w - pod_w - 18.0, h - pod_h - 18.0, w=pod_w, h=pod_h)

            # 10. Clean 2D Frame ROV Representation (Zero 3D clutter, 100% 2D top-down)
            self._draw_2d_frame_rov(cx, h - 90.0, w, h)
        except Exception:
            pass

    def _has_lateral_capability(self) -> bool:
        """Returns True if the vehicle frame has physical lateral strafe thrusters."""
        if self.frame_id in (5, 6, 7):
            return False
        if self.frame_id in (1, 2, 3, 4, 8):
            return True
        lat_weights = self.matrix_mgr.matrix.get("lat", {})
        return any(abs(float(w)) > 0.05 for w in lat_weights.values())

    def _draw_hud_grid_and_brackets(self, w: float, h: float):
        """Draws subtle tactical glass cockpit perimeter lines and corner brackets."""
        bk = 24
        # Corner brackets
        self.create_line(8, 8 + bk, 8, 8, 8 + bk, 8, fill=COLOR_CYAN_DIM, width=2)
        self.create_line(w - 8 - bk, 8, w - 8, 8, w - 8, 8 + bk, fill=COLOR_CYAN_DIM, width=2)
        self.create_line(8, h - 8 - bk, 8, h - 8, 8 + bk, h - 8, fill=COLOR_CYAN_DIM, width=2)
        self.create_line(w - 8 - bk, h - 8, w - 8, h - 8, w - 8, h - 8 - bk, fill=COLOR_CYAN_DIM, width=2)

        # Faint peripheral frame
        self.create_rectangle(12, 12, w - 12, h - 12, outline=COLOR_FAINT, width=1)

    def _draw_particles(self, w: float, h: float, cx: float, cy: float):
        """
        Simulates 3D subsea marine snow / flow streaks rushing past the camera.
        Accurately responds to Forward, Depth, and Yaw turning rotation derived from Thrusters.
        Suppresses lateral strafe streaks on vehicles without lateral thrusters (e.g. SimpleROV-4).
        """
        vz = 2.0
        vx = 0.0
        vy = 0.0
        rot_yaw = 0.0

        if self.in_flight:
            vz += self.thrust_fwd * 16.0
            vx -= self.thrust_lat * 9.0
            vy -= self.thrust_depth * 9.0
            # Yaw turning sweeps particles horizontally across FOV and pivots the 3D particle field
            vx -= self.thrust_yaw * 14.0
            rot_yaw = -self.thrust_yaw * 0.032

        focal = 260.0
        cos_y = math.cos(rot_yaw) if rot_yaw != 0.0 else 1.0
        sin_y = math.sin(rot_yaw) if rot_yaw != 0.0 else 0.0

        for p in self.particles:
            p.z -= vz
            p.x += vx
            p.y += vy

            # Apply genuine 3D rotational yaw around camera center
            if rot_yaw != 0.0:
                nx = p.x * cos_y - (p.z - 300.0) * sin_y
                nz = 300.0 + p.x * sin_y + (p.z - 300.0) * cos_y
                p.x = nx
                p.z = nz

            if p.z <= 20:
                p.reset(w, h, random_z=False)
            elif p.z > 650:
                p.z = 25.0

            pz = max(15.0, p.z)
            sx = cx + (p.x * focal) / pz
            sy = cy + (p.y * focal) / pz

            if 15 <= sx <= w - 15 and 15 <= sy <= h - 15:
                depth_ratio = max(0.1, min(1.0, 1.0 - (p.z / 650.0)))
                pr = max(1, int(depth_ratio * 2.5))

                if self.in_flight and (abs(vz) > 3.5 or abs(vx) > 2.5):
                    streak_len_y = (vz / 18.0) * depth_ratio * 15.0
                    streak_len_x = (vx / 14.0) * depth_ratio * 14.0
                    streak_col = COLOR_CYAN if depth_ratio > 0.6 else COLOR_CYAN_DIM
                    self.create_line(sx, sy, sx - streak_len_x, sy - streak_len_y, fill=streak_col, width=pr)
                else:
                    col = COLOR_WHITE if depth_ratio > 0.7 else COLOR_DIM
                    self.create_oval(sx - pr, sy - pr, sx + pr, sy + pr, fill=col, outline="")

    def _draw_jet_pitch_ladder(self, cx: float, cy: float, w: float, h: float):
        """
        Draws authentic military jet pitch ladder (MIL-STD-1787B):
        - Positive pitch: Solid horizontal lines with downward 90-degree tick fins pointing toward horizon.
        - Negative pitch: Dashed horizontal lines with upward 90-degree tick fins pointing toward horizon.
        - Horizon (0°): Solid wide bar with center gap for boresight waterline.
        Clamped to |dy| <= 95 to ensure clear visibility while preventing overlap with compass tape or ROV deck.
        """
        r_rad = math.radians(self.roll)
        cos_r = math.cos(r_rad)
        sin_r = math.sin(r_rad)
        pitch_scale = 3.6

        bar_len = 72.0
        gap = 22.0  # Center gap for sightline
        tick_h = 8.0

        for deg in range(-40, 50, 10):
            dy = (deg - self.pitch) * pitch_scale
            # Strictly confine pitch ladder lines within the central attitude aperture
            if abs(dy) > 95.0:
                continue

            color = COLOR_CYAN if deg == 0 else (COLOR_GREEN if self.armed else COLOR_WHITE)

            if deg == 0:
                # 0° Main Horizon Bar (Wide with center gap)
                hz_len = 110.0
                lx0 = cx + (-hz_len * cos_r - dy * sin_r)
                ly0 = cy + (-hz_len * sin_r + dy * cos_r)
                lx1 = cx + (-gap * cos_r - dy * sin_r)
                ly1 = cy + (-gap * sin_r + dy * cos_r)
                self.create_line(lx0, ly0, lx1, ly1, fill=COLOR_CYAN, width=2)

                rx0 = cx + (gap * cos_r - dy * sin_r)
                ry0 = cy + (gap * sin_r + dy * cos_r)
                rx1 = cx + (hz_len * cos_r - dy * sin_r)
                ry1 = cy + (hz_len * sin_r + dy * cos_r)
                self.create_line(rx0, ry0, rx1, ry1, fill=COLOR_CYAN, width=2)
                continue

            fin_dir = tick_h if deg > 0 else -tick_h
            dash_opt = () if deg > 0 else (5, 3)

            x_l0, x_l1 = -bar_len, -gap
            x_r0, x_r1 = gap, bar_len

            # Left bar
            p_l0_x = cx + (x_l0 * cos_r - dy * sin_r)
            p_l0_y = cy + (x_l0 * sin_r + dy * cos_r)
            p_l1_x = cx + (x_l1 * cos_r - dy * sin_r)
            p_l1_y = cy + (x_l1 * sin_r + dy * cos_r)
            self.create_line(p_l0_x, p_l0_y, p_l1_x, p_l1_y, fill=color, width=1, dash=dash_opt)

            # Left hook fin
            f_l_x = cx + (x_l0 * cos_r - (dy + fin_dir) * sin_r)
            f_l_y = cy + (x_l0 * sin_r + (dy + fin_dir) * cos_r)
            self.create_line(p_l0_x, p_l0_y, f_l_x, f_l_y, fill=color, width=1)

            # Right bar
            p_r0_x = cx + (x_r0 * cos_r - dy * sin_r)
            p_r0_y = cy + (x_r0 * sin_r + dy * cos_r)
            p_r1_x = cx + (x_r1 * cos_r - dy * sin_r)
            p_r1_y = cy + (x_r1 * sin_r + dy * cos_r)
            self.create_line(p_r0_x, p_r0_y, p_r1_x, p_r1_y, fill=color, width=1, dash=dash_opt)

            # Right hook fin
            f_r_x = cx + (x_r1 * cos_r - (dy + fin_dir) * sin_r)
            f_r_y = cy + (x_r1 * sin_r + (dy + fin_dir) * cos_r)
            self.create_line(p_r1_x, p_r1_y, f_r_x, f_r_y, fill=color, width=1)

            # Pitch Degree Numbers
            lbl_l_x = cx + ((-bar_len - 14) * cos_r - dy * sin_r)
            lbl_l_y = cy + ((-bar_len - 14) * sin_r + dy * cos_r)
            self.create_text(lbl_l_x, lbl_l_y, text=f"{abs(deg)}", fill=COLOR_CYAN_DIM, font=FONT_HUD_REG)

            lbl_r_x = cx + ((bar_len + 14) * cos_r - dy * sin_r)
            lbl_r_y = cy + ((bar_len + 14) * sin_r + dy * cos_r)
            self.create_text(lbl_r_x, lbl_r_y, text=f"{abs(deg)}", fill=COLOR_CYAN_DIM, font=FONT_HUD_REG)

    def _draw_aircraft_waterline(self, cx: float, cy: float):
        """Draws classic fixed aircraft waterline / boresight reference symbol: ──·──."""
        self.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=COLOR_CYAN, outline="")
        self.create_line(cx - 28, cy, cx - 8, cy, fill=COLOR_CYAN, width=2)
        self.create_line(cx - 28, cy, cx - 28, cy + 6, fill=COLOR_CYAN, width=2)
        self.create_line(cx + 8, cy, cx + 28, cy, fill=COLOR_CYAN, width=2)
        self.create_line(cx + 28, cy, cx + 28, cy + 6, fill=COLOR_CYAN, width=2)

    def _draw_jet_turn_rate_indicator(self, cx: float, cy: float):
        """Draws tactical turn coordinator / yaw rate indicator below waterline."""
        bar_y = cy + 24.0
        bar_half_w = 42.0

        # Horizontal baseline
        self.create_line(cx - bar_half_w, bar_y, cx + bar_half_w, bar_y, fill=COLOR_BORDER_LIGHT, width=1)
        # Center neutral bracket [ | ]
        self.create_line(cx - 5, bar_y - 4, cx - 5, bar_y + 4, fill=COLOR_CYAN_DIM, width=1)
        self.create_line(cx + 5, bar_y - 4, cx + 5, bar_y + 4, fill=COLOR_CYAN_DIM, width=1)
        self.create_line(cx, bar_y - 3, cx, bar_y + 3, fill=COLOR_CYAN, width=1)

        # Outer limit ticks
        self.create_line(cx - bar_half_w, bar_y - 4, cx - bar_half_w, bar_y + 4, fill=COLOR_DIM, width=1)
        self.create_line(cx + bar_half_w, bar_y - 4, cx + bar_half_w, bar_y + 4, fill=COLOR_DIM, width=1)

        # Dynamic Yaw Indicator Pointer / Pip (Calculated from thruster data)
        yaw_ratio = max(-1.0, min(1.0, self.thrust_yaw))
        pip_x = cx + yaw_ratio * (bar_half_w - 4)
        pip_color = COLOR_GREEN if abs(yaw_ratio) > 0.08 else COLOR_CYAN
        self.create_polygon(
            pip_x, bar_y - 1,
            pip_x - 3.5, bar_y + 6,
            pip_x + 3.5, bar_y + 6,
            fill=pip_color, outline=""
        )

        # Digital rate badge if actively yawing
        if abs(self.thrust_yaw) > 0.05:
            turn_dir = "R ▶" if self.thrust_yaw > 0 else "◀ L"
            pct = int(abs(yaw_ratio) * 100)
            self.create_text(cx, bar_y + 14, text=f"YAW {turn_dir} {pct}%", fill=COLOR_CYAN, font=FONT_HUD_SMALL)

    def _draw_jet_roll_arc(self, cx: float, cy: float):
        """Draws fighter jet semi-circular bank angle arc with roll pointer triangle."""
        arc_r = 95.0
        angles = [0, 10, -10, 20, -20, 30, -30, 45, -45, 60, -60]
        for a in angles:
            rad = math.radians(-90 + a)
            is_major = abs(a) in (0, 30, 60)
            t_len = 8 if is_major else 4

            x0 = cx + arc_r * math.cos(rad)
            y0 = cy + arc_r * math.sin(rad)
            x1 = cx + (arc_r - t_len) * math.cos(rad)
            y1 = cy + (arc_r - t_len) * math.sin(rad)
            self.create_line(x0, y0, x1, y1, fill=COLOR_WHITE if is_major else COLOR_DIM, width=1.5 if is_major else 1)

        # Dynamic Roll Pointer Triangle
        cur_roll_rad = math.radians(-90 + self.roll)
        ptr_x = cx + (arc_r - 2) * math.cos(cur_roll_rad)
        ptr_y = cy + (arc_r - 2) * math.sin(cur_roll_rad)
        tx1 = cx + (arc_r - 11) * math.cos(cur_roll_rad - 0.05)
        ty1 = cy + (arc_r - 11) * math.sin(cur_roll_rad - 0.05)
        tx2 = cx + (arc_r - 11) * math.cos(cur_roll_rad + 0.05)
        ty2 = cy + (arc_r - 11) * math.sin(cur_roll_rad + 0.05)
        self.create_polygon(ptr_x, ptr_y, tx1, ty1, tx2, ty2, fill=COLOR_CYAN, outline="")

    def _draw_flight_path_marker(self, cx: float, cy: float):
        """Draws iconic fighter jet Flight Path Marker (Velocity Vector Indicator)."""
        if not self.armed:
            return

        fpm_dx = self.thrust_yaw * 55.0 + self.thrust_lat * 40.0
        fpm_dy = -self.thrust_depth * 40.0
        fpm_x = max(cx - 65.0, min(cx + 65.0, cx + fpm_dx))
        fpm_y = max(cy - 55.0, min(cy + 55.0, cy + fpm_dy))

        r = 6.5
        fpm_color = COLOR_GREEN if self.in_flight else COLOR_CYAN
        self.create_oval(fpm_x - r, fpm_y - r, fpm_x + r, fpm_y + r, outline=fpm_color, width=2)
        self.create_line(fpm_x - r - 8, fpm_y, fpm_x - r, fpm_y, fill=fpm_color, width=2)
        self.create_line(fpm_x + r, fpm_y, fpm_x + r + 8, fpm_y, fill=fpm_color, width=2)
        self.create_line(fpm_x, fpm_y - r - 7, fpm_x, fpm_y - r, fill=fpm_color, width=2)

    def _draw_jet_compass_tape(self, w: float, cx: float):
        """Draws prominent fighter jet horizontal heading tape across the top side center."""
        tape_y = 22
        tape_w = min(w * 0.36, 280.0)
        x1 = cx - tape_w / 2
        x2 = cx + tape_w / 2

        self.create_rectangle(x1, tape_y - 12, x2, tape_y + 12, fill=COLOR_HUD_BG, outline=COLOR_BORDER_LIGHT)
        self.create_line(cx, tape_y - 12, cx, tape_y + 12, fill=COLOR_CYAN, width=2)
        self.create_polygon(cx - 4, tape_y + 12, cx + 4, tape_y + 12, cx, tape_y + 6, fill=COLOR_CYAN, outline="")

        ppd = tape_w / 50.0
        cur_hdg = self.heading % 360.0
        cardinals = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW", 360: "N"}

        for deg in range(int(cur_hdg - 28), int(cur_hdg + 29)):
            norm_deg = deg % 360
            dx = (deg - cur_hdg) * ppd
            tick_x = cx + dx

            if x1 <= tick_x <= x2:
                if norm_deg % 10 == 0:
                    self.create_line(tick_x, tape_y - 9, tick_x, tape_y - 1, fill=COLOR_WHITE, width=1)
                    label = cardinals.get(norm_deg, f"{norm_deg//10:02d}")
                    col = COLOR_CYAN if norm_deg in (0, 90, 180, 270) else COLOR_WHITE
                    self.create_text(tick_x, tape_y + 5, text=label, fill=col, font=FONT_HUD_SMALL)
                elif norm_deg % 5 == 0:
                    self.create_line(tick_x, tape_y - 5, tick_x, tape_y - 1, fill=COLOR_DIM, width=1)

        # Digital Heading Box directly above lubber line
        hdg_box_w = 56
        self.create_rectangle(cx - hdg_box_w/2, tape_y - 20, cx + hdg_box_w/2, tape_y - 10, fill=COLOR_CYAN, outline="")
        self.create_text(cx, tape_y - 15, text=f"{int(cur_hdg):03d}°", fill=COLOR_HUD_BG, font=FONT_HUD_BOLD)

    def _draw_jet_depth_tape(self, tape_x: float, tape_top: float, tape_bot: float):
        """Draws aircraft altimeter style vertical depth tape on the left side."""
        tape_h = tape_bot - tape_top
        cy = tape_top + tape_h / 2
        self.create_line(tape_x, tape_top, tape_x, tape_bot, fill=COLOR_CYAN_DIM, width=1)

        ppm = 35.0
        cur_d = max(0.0, self.depth)
        d_val = math.floor(max(0.0, cur_d - 2.0) * 5) / 5.0

        while d_val <= cur_d + 2.0:
            dy = (cur_d - d_val) * ppm
            ty = cy + dy
            if tape_top <= ty <= tape_bot:
                is_major = abs(d_val - round(d_val)) < 0.05
                tw = 8 if is_major else 4
                self.create_line(tape_x, ty, tape_x + tw, ty, fill=COLOR_WHITE if is_major else COLOR_DIM, width=1)
                if is_major and d_val >= 0:
                    self.create_text(tape_x + tw + 12, ty, text=f"{d_val:.1f}m", fill=COLOR_CYAN_DIM, font=FONT_HUD_SMALL)
            d_val += 0.2

        # Pointer Bug
        ptr_w = 54
        ptr_h = 18
        self.create_polygon(
            tape_x, cy,
            tape_x + 6, cy - ptr_h/2,
            tape_x + ptr_w, cy - ptr_h/2,
            tape_x + ptr_w, cy + ptr_h/2,
            tape_x + 6, cy + ptr_h/2,
            fill=COLOR_CYAN,
            outline=""
        )
        self.create_text(tape_x + ptr_w/2 + 2, cy, text=f"{cur_d:.2f}m", fill=COLOR_HUD_BG, font=FONT_HUD_BOLD)
        self.create_text(tape_x, tape_top - 10, text="DEPTH", fill=COLOR_CYAN, font=FONT_HUD_SMALL, anchor="w")
        vs_str = f"V/S: {self.vert_speed:+.1f}m/s"
        self.create_text(tape_x, tape_bot + 10, text=vs_str, fill=COLOR_WHITE, font=FONT_HUD_SMALL, anchor="w")

    def _draw_jet_thrust_tape(self, tape_x: float, tape_top: float, tape_bot: float):
        """Draws aircraft throttle style vertical thrust percentage tape on the right side."""
        tape_h = tape_bot - tape_top
        self.create_line(tape_x, tape_top, tape_x, tape_bot, fill=COLOR_CYAN_DIM, width=1)

        # Thrust percentage derived from actual thruster PWM deviations (guarantees parity with active motors)
        max_dev = max(abs(pwm - 1500) for pwm in self.motor_cmd_pwm) if self.armed else 0
        thrust_pct = int(min(100.0, (max_dev / 400.0) * 100))
        for pct in range(0, 110, 10):
            ratio = pct / 100.0
            ty = tape_bot - (ratio * tape_h)
            is_major = (pct % 20 == 0)
            tw = 8 if is_major else 4
            self.create_line(tape_x - tw, ty, tape_x, ty, fill=COLOR_WHITE if is_major else COLOR_DIM, width=1)
            if is_major:
                self.create_text(tape_x - tw - 12, ty, text=f"{pct}%", fill=COLOR_TEXT_DIM, font=FONT_HUD_SMALL)

        fill_h = (thrust_pct / 100.0) * tape_h
        if fill_h > 0:
            bar_col = COLOR_GREEN if self.armed else COLOR_AMBER
            self.create_rectangle(tape_x + 2, tape_bot - fill_h, tape_x + 6, tape_bot, fill=bar_col, outline="")

        ptr_w = 48
        ptr_h = 18
        curr_y = tape_bot - (thrust_pct / 100.0) * tape_h
        self.create_polygon(
            tape_x, curr_y,
            tape_x - 6, curr_y - ptr_h/2,
            tape_x - ptr_w, curr_y - ptr_h/2,
            tape_x - ptr_w, curr_y + ptr_h/2,
            tape_x - 6, curr_y + ptr_h/2,
            fill=COLOR_CYAN if self.armed else COLOR_DIM,
            outline=""
        )
        self.create_text(tape_x - ptr_w/2 - 2, curr_y, text=f"{thrust_pct}%", fill=COLOR_HUD_BG, font=FONT_HUD_BOLD)
        self.create_text(tape_x, tape_top - 10, text="THRUST", fill=COLOR_CYAN, font=FONT_HUD_SMALL, anchor="e")

    def _draw_power_pod(self, x: float, y: float, w: float = 195.0, h: float = 78.0):
        """Top-Left Tactical Pod: Battery Voltage, Current, 4S LiPo Segments, MCU VCC."""
        self.create_rectangle(x, y, x + w, y + h, fill=COLOR_HUD_BG, outline=COLOR_BORDER_LIGHT)
        self.create_rectangle(x, y, x + w, y + 17, fill="#0d0d12", outline=COLOR_BORDER_LIGHT)
        self.create_text(x + 8, y + 8, text="[ POWER & BATTERY ]", fill=COLOR_CYAN, font=FONT_HUD_SMALL, anchor="w")

        v_col = COLOR_GREEN if self.batt_v >= 14.5 else (COLOR_AMBER if self.batt_v >= 13.8 else COLOR_RED)
        self.create_text(x + 10, y + 34, text=f"{self.batt_v:.1f}V", fill=v_col, font=FONT_HUD_LARGE, anchor="w")
        self.create_text(x + 95, y + 34, text=f"{self.batt_a:.1f}A", fill=COLOR_WHITE, font=FONT_HUD_BOLD, anchor="w")

        bar_x, bar_y, bar_w = x + 10, y + 48, 115
        self.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + 7, outline=COLOR_BORDER_LIGHT)
        pct = max(0.0, min(1.0, (self.batt_v - 13.5) / (16.8 - 13.5))) if self.batt_v > 5.0 else 0.0
        fill_w = int(pct * bar_w)
        if fill_w > 0:
            self.create_rectangle(bar_x + 1, bar_y + 1, bar_x + fill_w, bar_y + 6, fill=v_col, outline="")
        self.create_text(bar_x + bar_w + 8, bar_y + 4, text=f"{int(pct*100)}%", fill=COLOR_DIM, font=FONT_HUD_SMALL, anchor="w")

        self.create_text(x + 10, y + 66, text=f"5V:{self.vcc_v:.2f}V | LINK:{self.packet_rate:.0f}Hz", fill=COLOR_DIM, font=FONT_HUD_SMALL, anchor="w")

    def _draw_environment_pod(self, x: float, y: float, w: float = 195.0, h: float = 78.0):
        """Top-Right Tactical Pod: Pressure, Temperature, Leak Shield."""
        self.create_rectangle(x, y, x + w, y + h, fill=COLOR_HUD_BG, outline=COLOR_BORDER_LIGHT)
        self.create_rectangle(x, y, x + w, y + 17, fill="#0d0d12", outline=COLOR_BORDER_LIGHT)
        self.create_text(x + 8, y + 8, text="[ ENVIRONMENT & HULL ]", fill=COLOR_CYAN, font=FONT_HUD_SMALL, anchor="w")

        self.create_text(x + 10, y + 34, text=f"{self.pressure:.3f} bar", fill=COLOR_WHITE, font=FONT_HUD_BOLD, anchor="w")
        self.create_text(x + 115, y + 34, text=f"{self.temp:.1f}°C", fill=COLOR_CYAN, font=FONT_HUD_BOLD, anchor="w")

        alert_y = y + 50
        alert_h = 20
        if self.leak_alert:
            flash = (self._anim_tick // 15) % 2 == 0
            bg = COLOR_RED if flash else COLOR_WHITE
            fg = COLOR_WHITE if flash else COLOR_RED
            self.create_rectangle(x + 8, alert_y, x + w - 8, alert_y + alert_h, fill=bg, outline="")
            self.create_text(x + w / 2, alert_y + alert_h / 2, text="! ! CRITICAL LEAK ! !", fill=fg, font=FONT_HUD_BOLD)
        else:
            self.create_rectangle(x + 8, alert_y, x + w - 8, alert_y + alert_h, fill="#0b1612", outline=COLOR_GREEN_DIM)
            self.create_text(x + w / 2, alert_y + alert_h / 2, text="[ HULL SEALED: NOMINAL ]", fill=COLOR_GREEN, font=FONT_HUD_SMALL)

    def _draw_flight_status_pod(self, x: float, y: float, w: float = 195.0, h: float = 78.0):
        """Bottom-Left Tactical Pod: Armed State, Flight Mode, Attitude Readout."""
        self.create_rectangle(x, y, x + w, y + h, fill=COLOR_HUD_BG, outline=COLOR_BORDER_LIGHT)
        self.create_rectangle(x, y, x + w, y + 17, fill="#0d0d12", outline=COLOR_BORDER_LIGHT)
        self.create_text(x + 8, y + 8, text="[ FLIGHT SAFETY & MODE ]", fill=COLOR_CYAN, font=FONT_HUD_SMALL, anchor="w")

        arm_col = COLOR_GREEN if self.armed else COLOR_DIM
        arm_text = "[ ARMED ]" if self.armed else "[ DISARMED ]"
        self.create_text(x + 10, y + 34, text=arm_text, fill=arm_col, font=FONT_HUD_BOLD, anchor="w")
        self.create_text(x + 100, y + 34, text=f"M:{self.mode_name}", fill=COLOR_WHITE, font=FONT_HUD_BOLD, anchor="w")
        self.create_text(x + 10, y + 58, text=f"ROLL:{self.roll:+.1f}° | PITCH:{self.pitch:+.1f}°", fill=COLOR_CYAN_DIM, font=FONT_HUD_SMALL, anchor="w")

    def _draw_pilot_pod(self, x: float, y: float, w: float = 195.0, h: float = 78.0):
        """Bottom-Right Tactical Pod: Gamepad Controller, Gain, Vector Readout."""
        self.create_rectangle(x, y, x + w, y + h, fill=COLOR_HUD_BG, outline=COLOR_BORDER_LIGHT)
        self.create_rectangle(x, y, x + w, y + 17, fill="#0d0d12", outline=COLOR_BORDER_LIGHT)
        self.create_text(x + 8, y + 8, text="[ PILOT INPUTS & GAIN ]", fill=COLOR_CYAN, font=FONT_HUD_SMALL, anchor="w")

        pad_stat = "ACTIVE" if self.gamepad_connected else "STANDBY"
        pad_col = COLOR_GREEN if self.gamepad_connected else COLOR_DIM
        self.create_text(x + 10, y + 34, text=f"PAD:{pad_stat}", fill=pad_col, font=FONT_HUD_BOLD, anchor="w")
        self.create_text(x + 110, y + 34, text=f"G:{int(self.gain*100)}%", fill=COLOR_WHITE, font=FONT_HUD_BOLD, anchor="w")
        lat_str = f"L:{self.cmd_lat:+3d}" if self._has_lateral_capability() else "L:N/A"
        self.create_text(
            x + 10, y + 58,
            text=f"F:{self.cmd_fwd:+3d} {lat_str} D:{self.cmd_depth:+3d} Y:{self.cmd_yaw:+3d}",
            fill=COLOR_CYAN_DIM,
            font=FONT_HUD_SMALL,
            anchor="w"
        )

    def _draw_2d_frame_rov(self, cx: float, cy: float, w: float, h: float):
        """
        Renders clean, frame-adaptive 2D top-down ROV schematic (zero 3D clutter).
        Displays chassis silhouette, 2D thruster ducts with spinning props,
        dynamic thrust vector plumes, and live motor commanded/probe PWM.
        """
        frame_data = FRAMES.get(self.frame_id, FRAMES.get(DEFAULT_FRAME_ID, FRAMES[6]))
        thrusters = frame_data.get("thrusters", [])
        if not thrusters:
            thrusters = FRAMES[6]["thrusters"]
        frame_name = frame_data.get("name", "SimpleROV-4")

        # Tactical 2D ROV Deck Plate
        deck_w = min(360.0, max(260.0, w - 20.0)) if w < 420 else min(360.0, w * 0.36)
        deck_h = min(170.0, max(120.0, h - 30.0)) if h < 240 else 140.0
        d_x1 = cx - deck_w / 2.0
        d_x2 = cx + deck_w / 2.0
        d_y1 = cy - deck_h / 2.0 + 4.0
        d_y2 = cy + deck_h / 2.0 + 4.0

        # Deck Container
        self.create_rectangle(d_x1, d_y1, d_x2, d_y2, fill="#07090e", outline=COLOR_BORDER_LIGHT, width=1)
        self.create_rectangle(d_x1, d_y1, d_x2, d_y1 + 16, fill="#0d1117", outline=COLOR_BORDER_LIGHT, width=1)
        self.create_text(
            d_x1 + 8, d_y1 + 8,
            text=f"[ 2D ROV FRAME: {frame_name.upper()} ]",
            fill=COLOR_CYAN,
            font=FONT_HUD_SMALL,
            anchor="w"
        )

        # Center top-down position
        rov_cy = d_y1 + 16 + (d_y2 - d_y1 - 16) / 2.0

        # 1. Top-Down Chassis Silhouette
        # Main Electronics Enclosure Capsule
        tube_w = 30.0
        tube_h = 62.0
        self.create_rectangle(
            cx - tube_w/2, rov_cy - tube_h/2,
            cx + tube_w/2, rov_cy + tube_h/2,
            fill="#0c1724", outline=COLOR_CYAN_DIM, width=1.5
        )
        # Front Optical Camera Dome Arc & Lens
        dome_r = tube_w / 2.0
        self.create_arc(
            cx - dome_r, rov_cy - tube_h/2 - dome_r,
            cx + dome_r, rov_cy - tube_h/2 + dome_r,
            start=0, extent=180,
            fill="#0369a1", outline=COLOR_CYAN, width=1.5
        )
        self.create_oval(cx - 3, rov_cy - tube_h/2 - 4, cx + 3, rov_cy - tube_h/2 + 2, fill="#38bdf8", outline="")

        # Forward Direction Pointer
        self.create_text(cx, rov_cy - tube_h/2 - 11, text="▲ FWD", fill=COLOR_CYAN, font=FONT_HUD_SMALL)

        # Dynamic Yaw Turning Moment Indicators (Curved rotational arcs & arrows around ROV)
        if self.armed and abs(self.thrust_yaw) > 0.06:
            turn_is_right = (self.thrust_yaw > 0)
            arc_r = 34.0
            yaw_col = COLOR_GREEN if abs(self.thrust_yaw) > 0.25 else COLOR_CYAN
            yaw_dash = () if abs(self.thrust_yaw) > 0.40 else (4, 3)

            # Draw curved turn vector arc above bow
            if turn_is_right:
                # Bow sweeps right (Clockwise)
                self.create_arc(
                    cx - arc_r, rov_cy - tube_h/2 - 18,
                    cx + arc_r, rov_cy - tube_h/2 + 10,
                    start=45, extent=90, style="arc", outline=yaw_col, width=2, dash=yaw_dash
                )
                # Arrowhead at right tip
                ah_x = cx + arc_r * math.cos(math.radians(45))
                ah_y = (rov_cy - tube_h/2 - 4) - 14 * math.sin(math.radians(45))
                self.create_polygon(ah_x + 5, ah_y, ah_x - 3, ah_y - 4, ah_x - 3, ah_y + 4, fill=yaw_col, outline="")
                self.create_text(cx, rov_cy - tube_h/2 - 20, text="YAW CW ↻", fill=yaw_col, font=FONT_HUD_BOLD)
            else:
                # Bow sweeps left (Counter-Clockwise)
                self.create_arc(
                    cx - arc_r, rov_cy - tube_h/2 - 18,
                    cx + arc_r, rov_cy - tube_h/2 + 10,
                    start=45, extent=90, style="arc", outline=yaw_col, width=2, dash=yaw_dash
                )
                # Arrowhead at left tip
                ah_x = cx + arc_r * math.cos(math.radians(135))
                ah_y = (rov_cy - tube_h/2 - 4) - 14 * math.sin(math.radians(135))
                self.create_polygon(ah_x - 5, ah_y, ah_x + 3, ah_y - 4, ah_x + 3, ah_y + 4, fill=yaw_col, outline="")
                self.create_text(cx, rov_cy - tube_h/2 - 20, text="↺ YAW CCW", fill=yaw_col, font=FONT_HUD_BOLD)

        # HDPE Side Rails
        for side_sign in (-1, 1):
            rx = cx + side_sign * (tube_w / 2.0 + 10.0)
            self.create_line(rx, rov_cy - tube_h/2 + 6, rx, rov_cy + tube_h/2 - 6, fill="#1e293b", width=3)
            # Tie-rods to main tube
            self.create_line(cx + side_sign * (tube_w / 2.0), rov_cy - 12, rx, rov_cy - 12, fill="#334155", width=1)
            self.create_line(cx + side_sign * (tube_w / 2.0), rov_cy + 12, rx, rov_cy + 12, fill="#334155", width=1)

        # 2. Frame Thrusters (Top-Down 2D layout)
        span_x = deck_w * 0.38
        span_y = (d_y2 - d_y1 - 32) * 0.38

        for idx, t_info in enumerate(thrusters):
            num = t_info.get("num", idx + 1)
            pos = t_info.get("pos", (0.0, 0.0))
            angle = t_info.get("angle", 0)
            px, py = pos[0], pos[1]

            tx = cx + px * span_x
            ty = rov_cy - py * span_y

            cmd_pwm = self.motor_cmd_pwm[num - 1] if 0 < num <= 8 else 1500
            is_prb = self.motor_probe_valid[num - 1] if 0 < num <= 8 else False
            prb_pwm = self.motor_probe_pwm[num - 1] if (is_prb and 0 < num <= 8) else 0
            delta = (prb_pwm - cmd_pwm) if is_prb else 0
            thrust_val = (cmd_pwm - 1500) / 500.0

            # Direction and reversal checks
            is_rev_motor = (self.matrix_mgr.motor_directions.get(num, 1) == -1)

            # Color highlight based on activity (both bench test and operational flight)
            eff_fwd = (cmd_pwm > 1520) if not is_rev_motor else (cmd_pwm < 1480)
            eff_rev = (cmd_pwm < 1480) if not is_rev_motor else (cmd_pwm > 1520)
            is_active = abs(cmd_pwm - 1500) > 20

            if eff_fwd:
                t_border = COLOR_GREEN
                prop_col = COLOR_GREEN
            elif eff_rev:
                t_border = COLOR_AMBER
                prop_col = COLOR_AMBER
            elif is_active:
                t_border = COLOR_CYAN
                prop_col = COLOR_CYAN
            else:
                t_border = COLOR_CYAN_DIM if self.armed else COLOR_BORDER_LIGHT
                prop_col = COLOR_CYAN_DIM if self.armed else COLOR_DIM

            is_active_fwd = eff_fwd
            is_active_rev = eff_rev

            p_ang = math.radians(self._prop_angles.get(num, 0.0))

            if angle == 90:
                # ----------------- VERTICAL THRUSTER (Top-down circular duct) -----------------
                vr = 8.5
                # Outer duct
                self.create_oval(tx - vr, ty - vr, tx + vr, ty + vr, fill="#050811", outline=t_border, width=1.8)
                self.create_oval(tx - vr + 2.5, ty - vr + 2.5, tx + vr - 2.5, ty + vr - 2.5, outline="#181824", width=1)

                # 3-blade propeller
                blade_r = 5.0
                for b in range(3):
                    ba = p_ang + (b * 2 * math.pi / 3.0)
                    bx = tx + math.cos(ba) * blade_r
                    by = ty + math.sin(ba) * blade_r
                    self.create_line(tx, ty, bx, by, fill=prop_col, width=1.5)
                self.create_oval(tx - 2, ty - 2, tx + 2, ty + 2, fill=prop_col, outline="")

                # Depth Plume / Vector Indicators
                if is_active_fwd:  # Ascending / Upward thrust
                    self.create_polygon(tx, ty - vr - 8, tx - 4, ty - vr - 2, tx + 4, ty - vr - 2, fill=COLOR_GREEN, outline="")
                    self.create_text(tx, ty - vr - 13, text="▲ UP", fill=COLOR_GREEN, font=FONT_HUD_SMALL)
                elif is_active_rev:  # Descending / Downward thrust
                    self.create_polygon(tx, ty + vr + 8, tx - 4, ty + vr + 2, tx + 4, ty + vr + 2, fill=COLOR_AMBER, outline="")
                    self.create_text(tx, ty + vr + 13, text="▼ DN", fill=COLOR_AMBER, font=FONT_HUD_SMALL)

                t_w = vr * 2

            else:
                # ----------------- HORIZONTAL THRUSTER (Rotated according to angle) -----------------
                rad = math.radians(angle)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)
                w_half = 6.0
                h_half = 10.0

                # 4 rotated corners of duct rectangle
                c1_x = tx + (-w_half * cos_a - (-h_half) * sin_a)
                c1_y = ty + (-w_half * sin_a + (-h_half) * cos_a)
                c2_x = tx + (w_half * cos_a - (-h_half) * sin_a)
                c2_y = ty + (w_half * sin_a + (-h_half) * cos_a)
                c3_x = tx + (w_half * cos_a - h_half * sin_a)
                c3_y = ty + (w_half * sin_a + h_half * cos_a)
                c4_x = tx + (-w_half * cos_a - h_half * sin_a)
                c4_y = ty + (-w_half * sin_a + h_half * cos_a)

                self.create_polygon(c1_x, c1_y, c2_x, c2_y, c3_x, c3_y, c4_x, c4_y, fill="#050811", outline=t_border, width=1.8)

                # 3-blade propeller
                blade_r = 5.0
                for b in range(3):
                    ba = p_ang + (b * 2 * math.pi / 3.0)
                    bx = tx + math.cos(ba) * blade_r
                    by = ty + math.sin(ba) * blade_r
                    self.create_line(tx, ty, bx, by, fill=prop_col, width=1.5)
                self.create_oval(tx - 2, ty - 2, tx + 2, ty + 2, fill=prop_col, outline="")

                # Directional Plumes
                # Longitudinal axis: aft vector is (-sin(angle), cos(angle))
                axis_x = -math.sin(rad)
                axis_y = math.cos(rad)
                plume_len = min(22.0, abs(thrust_val) * 18.0 + 4.0)

                if is_active_fwd:
                    # Water ejects aft (+axis in canvas)
                    sx = tx + axis_x * h_half
                    sy = ty + axis_y * h_half
                    ex = tx + axis_x * (h_half + plume_len)
                    ey = ty + axis_y * (h_half + plume_len)
                    self.create_line(sx, sy, ex, ey, fill=COLOR_GREEN, width=2)
                    ah1_x = ex - axis_x * 4 + axis_y * 3
                    ah1_y = ey - axis_y * 4 - axis_x * 3
                    ah2_x = ex - axis_x * 4 - axis_y * 3
                    ah2_y = ey - axis_y * 4 + axis_x * 3
                    self.create_line(ex, ey, ah1_x, ah1_y, fill=COLOR_GREEN, width=1.5)
                    self.create_line(ex, ey, ah2_x, ah2_y, fill=COLOR_GREEN, width=1.5)
                elif is_active_rev:
                    # Water ejects fwd (-axis in canvas)
                    sx = tx - axis_x * h_half
                    sy = ty - axis_y * h_half
                    ex = tx - axis_x * (h_half + plume_len)
                    ey = ty - axis_y * (h_half + plume_len)
                    self.create_line(sx, sy, ex, ey, fill=COLOR_AMBER, width=2)
                    ah1_x = ex + axis_x * 4 + axis_y * 3
                    ah1_y = ey + axis_y * 4 - axis_x * 3
                    ah2_x = ex + axis_x * 4 - axis_y * 3
                    ah2_y = ey + axis_y * 4 + axis_x * 3
                    self.create_line(ex, ey, ah1_x, ah1_y, fill=COLOR_AMBER, width=1.5)
                    self.create_line(ex, ey, ah2_x, ah2_y, fill=COLOR_AMBER, width=1.5)

                t_w = 20.0

            # Motor Label & Readout text
            text_side = 1 if px >= 0 else -1
            lbl_x = tx + (text_side * (t_w / 2.0 + 5.0))
            anchor = "w" if text_side == 1 else "e"

            if is_active_fwd:
                m_col = COLOR_GREEN
            elif is_active_rev:
                m_col = COLOR_AMBER
            elif abs(cmd_pwm - 1500) > 25:
                m_col = COLOR_CYAN
            else:
                m_col = COLOR_WHITE

            rev_label = " [REV]" if is_rev_motor else ""
            self.create_text(lbl_x, ty - 5, text=f"M{num}{rev_label}:{cmd_pwm}", fill=m_col, font=FONT_HUD_SMALL, anchor=anchor)
            if is_prb:
                p_col = COLOR_AMBER if abs(delta) > 25 else COLOR_GREEN
                self.create_text(lbl_x, ty + 5, text=f"P:{prb_pwm}", fill=p_col, font=FONT_HUD_SMALL, anchor=anchor)
            else:
                self.create_text(lbl_x, ty + 5, text="P:--", fill=COLOR_DIM, font=FONT_HUD_SMALL, anchor=anchor)

    def _draw_pure_telemetry_dashboard(self, w: float, h: float):
        """
        Clean, high-visibility, lightweight digital telemetry dashboard.
        Disables fighter jet HUD graphics (pitch ladder, waterline, particles, compass tape)
        and renders a clean 3-panel avionics console with the 2D ROV thruster array monitor.
        """
        # Outer subtle frame
        self.create_rectangle(8, 8, w - 8, h - 8, outline=COLOR_BORDER_LIGHT, width=1)

        # 1. Top Avionics Header Bar (Height: 38px)
        top_y1, top_y2 = 12.0, 48.0
        self.create_rectangle(14, top_y1, w - 14, top_y2, fill="#0b101b", outline=COLOR_BORDER_LIGHT)

        # System Banner
        self.create_text(
            24, (top_y1 + top_y2) / 2.0,
            text="PIXDOCTOR DIGITAL TELEMETRY DASHBOARD",
            fill=COLOR_CYAN,
            font=FONT_HUD_TITLE,
            anchor="w"
        )

        # Mode Badge
        mode_str = f"MODE: {self.mode_name}"
        self.create_rectangle(w * 0.44 - 55, top_y1 + 5, w * 0.44 + 55, top_y2 - 5, fill="#131e33", outline=COLOR_CYAN_DIM)
        self.create_text(w * 0.44, (top_y1 + top_y2) / 2.0, text=mode_str, fill=COLOR_WHITE, font=FONT_HUD_BOLD)

        # Arm Status Badge
        arm_col = COLOR_GREEN if self.armed else COLOR_RED
        arm_text = "ARMED" if self.armed else "DISARMED"
        arm_bg = "#0c2818" if self.armed else "#2a0f14"
        self.create_rectangle(w * 0.58 - 48, top_y1 + 5, w * 0.58 + 48, top_y2 - 5, fill=arm_bg, outline=arm_col)
        self.create_text(w * 0.58, (top_y1 + top_y2) / 2.0, text=arm_text, fill=arm_col, font=FONT_HUD_BOLD)

        # Leak Status Badge
        leak_col = COLOR_RED if self.leak_alert else COLOR_GREEN
        leak_text = "LEAK ALERT!" if self.leak_alert else "LEAK: OK"
        leak_bg = "#350c12" if self.leak_alert else "#0a1e14"
        self.create_rectangle(w * 0.72 - 45, top_y1 + 5, w * 0.72 + 45, top_y2 - 5, fill=leak_bg, outline=leak_col)
        self.create_text(w * 0.72, (top_y1 + top_y2) / 2.0, text=leak_text, fill=leak_col, font=FONT_HUD_BOLD)

        # Link Rate
        self.create_text(
            w - 24, (top_y1 + top_y2) / 2.0,
            text=f"RATE: {self.packet_rate:.0f} Hz",
            fill=COLOR_DIM,
            font=FONT_HUD_REG,
            anchor="e"
        )

        # 2. Main Console Layout: 3 Columns
        # Available vertical space: y=54 to h-34
        pan_y1 = 54.0
        pan_y2 = h - 34.0
        pan_h = pan_y2 - pan_y1

        # Column widths: Left 27%, Center 46%, Right 27%
        col1_x1 = 14.0
        col1_w = max(210.0, min(280.0, w * 0.27))
        col1_x2 = col1_x1 + col1_w

        col3_w = col1_w
        col3_x2 = w - 14.0
        col3_x1 = col3_x2 - col3_w

        col2_x1 = col1_x2 + 10.0
        col2_x2 = col3_x1 - 10.0

        # ================= LEFT COLUMN: NAVIGATION & ENVIRONMENT =================
        self.create_rectangle(col1_x1, pan_y1, col1_x2, pan_y2, fill="#070a12", outline=COLOR_BORDER_LIGHT)
        self.create_rectangle(col1_x1, pan_y1, col1_x2, pan_y1 + 22, fill="#0d1424", outline=COLOR_BORDER_LIGHT)
        self.create_text(col1_x1 + 10, pan_y1 + 11, text="[ NAVIGATION & ENVIRONMENT ]", fill=COLOR_CYAN, font=FONT_HUD_BOLD, anchor="w")

        cy = pan_y1 + 35
        # Primary Depth Display (Massive digital readout)
        self.create_text(col1_x1 + 12, cy, text="DEPTH", fill=COLOR_TEXT_DIM, font=FONT_HUD_SMALL, anchor="w")
        cy += 20
        self.create_text(col1_x1 + 12, cy, text=f"{self.depth:.2f} m", fill=COLOR_CYAN, font=FONT_HUD_HUGE, anchor="w")
        cy += 26
        vs_col = COLOR_GREEN if abs(self.vert_speed) > 0.05 else COLOR_DIM
        self.create_text(col1_x1 + 12, cy, text=f"VERT SPEED: {self.vert_speed:+.2f} m/s", fill=vs_col, font=FONT_HUD_REG, anchor="w")
        cy += 18
        self.create_text(col1_x1 + 12, cy, text=f"PRESSURE:   {self.pressure:.3f} bar", fill=COLOR_WHITE, font=FONT_HUD_REG, anchor="w")
        cy += 18
        self.create_text(col1_x1 + 12, cy, text=f"TEMP:       {self.temp:.1f} °C", fill=COLOR_WHITE, font=FONT_HUD_REG, anchor="w")

        # Divider
        cy += 16
        self.create_line(col1_x1 + 10, cy, col1_x2 - 10, cy, fill=COLOR_BORDER_LIGHT)
        cy += 14

        # Attitude & Compass Section
        self.create_text(col1_x1 + 12, cy, text="ATTITUDE & HEADING", fill=COLOR_TEXT_DIM, font=FONT_HUD_SMALL, anchor="w")
        cy += 20
        cardinals = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
        c_idx = int(((self.heading + 22.5) % 360) // 45)
        card_str = cardinals[c_idx]
        self.create_text(col1_x1 + 12, cy, text=f"{int(self.heading):03d}° [{card_str}]", fill=COLOR_WHITE, font=FONT_HUD_LARGE, anchor="w")
        cy += 24
        self.create_text(col1_x1 + 12, cy, text=f"ROLL:  {self.roll:+.1f}°", fill=COLOR_CYAN, font=FONT_HUD_REG, anchor="w")
        cy += 18
        self.create_text(col1_x1 + 12, cy, text=f"PITCH: {self.pitch:+.1f}°", fill=COLOR_CYAN, font=FONT_HUD_REG, anchor="w")

        # Visual roll/pitch miniature indicator
        cy += 24
        ind_cx = (col1_x1 + col1_x2) / 2.0
        ind_w = (col1_w - 30) / 2.0
        self.create_line(ind_cx - ind_w, cy, ind_cx + ind_w, cy, fill=COLOR_BORDER_LIGHT, width=1)
        self.create_line(ind_cx, cy - 8, ind_cx, cy + 8, fill=COLOR_BORDER_LIGHT, width=1)
        rad_r = math.radians(self.roll)
        pitch_px = max(-10.0, min(10.0, self.pitch * 0.8))
        cos_r, sin_r = math.cos(rad_r), math.sin(rad_r)
        h_x1 = ind_cx - ind_w * cos_r
        h_y1 = (cy - pitch_px) - ind_w * sin_r
        h_x2 = ind_cx + ind_w * cos_r
        h_y2 = (cy - pitch_px) + ind_w * sin_r
        self.create_line(h_x1, h_y1, h_x2, h_y2, fill=COLOR_GREEN, width=2)
        self.create_oval(ind_cx - 2, cy - 2, ind_cx + 2, cy + 2, fill=COLOR_CYAN, outline="")

        # ================= CENTER COLUMN: 2D ROV & MOTOR DYNAMICS =================
        self.create_rectangle(col2_x1, pan_y1, col2_x2, pan_y2, fill="#060810", outline=COLOR_BORDER_LIGHT)
        self.create_rectangle(col2_x1, pan_y1, col2_x2, pan_y1 + 22, fill="#0d1424", outline=COLOR_BORDER_LIGHT)
        self.create_text(col2_x1 + 10, pan_y1 + 11, text="[ 2D ROV HULL & LIVE THRUST DYNAMICS ]", fill=COLOR_CYAN, font=FONT_HUD_BOLD, anchor="w")

        center_cx = (col2_x1 + col2_x2) / 2.0
        # Embed the crisp 2D ROV frame right in the center panel!
        rov_plot_cy = pan_y1 + 22 + (pan_y2 - pan_y1 - 22) / 2.0
        self._draw_2d_frame_rov(center_cx, rov_plot_cy, col2_x2 - col2_x1, pan_h)

        # ================= RIGHT COLUMN: POWER & PROPULSION =================
        self.create_rectangle(col3_x1, pan_y1, col3_x2, pan_y2, fill="#070a12", outline=COLOR_BORDER_LIGHT)
        self.create_rectangle(col3_x1, pan_y1, col3_x2, pan_y1 + 22, fill="#0d1424", outline=COLOR_BORDER_LIGHT)
        self.create_text(col3_x1 + 10, pan_y1 + 11, text="[ POWER & PROPULSION ]", fill=COLOR_CYAN, font=FONT_HUD_BOLD, anchor="w")

        ry = pan_y1 + 35
        # Battery Section
        self.create_text(col3_x1 + 12, ry, text="BATTERY SYSTEM", fill=COLOR_TEXT_DIM, font=FONT_HUD_SMALL, anchor="w")
        ry += 20
        v_col = COLOR_GREEN if self.batt_v >= 14.5 else (COLOR_AMBER if self.batt_v >= 13.8 else COLOR_RED)
        self.create_text(col3_x1 + 12, ry, text=f"{self.batt_v:.2f} V", fill=v_col, font=FONT_HUD_HUGE, anchor="w")
        ry += 24
        self.create_text(col3_x1 + 12, ry, text=f"CURRENT:  {self.batt_a:.1f} A", fill=COLOR_WHITE, font=FONT_HUD_REG, anchor="w")
        ry += 18
        self.create_text(col3_x1 + 12, ry, text=f"VCC RAIL: {self.vcc_v:.2f} V", fill=COLOR_WHITE, font=FONT_HUD_REG, anchor="w")

        # Battery Bar
        ry += 16
        b_bar_w = col3_w - 24
        self.create_rectangle(col3_x1 + 12, ry, col3_x1 + 12 + b_bar_w, ry + 6, outline=COLOR_BORDER_LIGHT)
        pct = max(0.0, min(1.0, (self.batt_v - 13.5) / (16.8 - 13.5))) if self.batt_v > 5.0 else 0.0
        if pct > 0.0:
            self.create_rectangle(col3_x1 + 13, ry + 1, col3_x1 + 12 + int(pct * b_bar_w), ry + 5, fill=v_col, outline="")
        ry += 14

        # Divider
        self.create_line(col3_x1 + 10, ry, col3_x2 - 10, ry, fill=COLOR_BORDER_LIGHT)
        ry += 14

        # Propulsion Forces / Thrust Vectors (calculated from active motors)
        self.create_text(col3_x1 + 12, ry, text="THRUST VECTORS (FROM MOTORS)", fill=COLOR_TEXT_DIM, font=FONT_HUD_SMALL, anchor="w")
        ry += 18

        vector_items = [
            ("FORWARD", self.thrust_fwd, COLOR_GREEN if self.thrust_fwd >= 0 else COLOR_AMBER),
            ("LATERAL", self.thrust_lat, COLOR_CYAN),
            ("DEPTH", self.thrust_depth, COLOR_GREEN if self.thrust_depth >= 0 else COLOR_AMBER),
            ("YAW", self.thrust_yaw, COLOR_GREEN if self.thrust_yaw >= 0 else COLOR_CYAN),
        ]

        bar_len = col3_w - 110
        for name, val, col in vector_items:
            self.create_text(col3_x1 + 12, ry, text=f"{name:7s}", fill=COLOR_WHITE, font=FONT_HUD_REG, anchor="w")
            bx1 = col3_x1 + 80
            bx2 = bx1 + bar_len
            bcx = (bx1 + bx2) / 2.0
            self.create_line(bx1, ry, bx2, ry, fill=COLOR_BORDER_LIGHT, width=1)
            self.create_line(bcx, ry - 4, bcx, ry + 4, fill=COLOR_DIM, width=1)
            val_clamp = max(-1.0, min(1.0, val))
            if abs(val_clamp) > 0.02:
                v_x = bcx + val_clamp * (bar_len / 2.0)
                self.create_line(bcx, ry, v_x, ry, fill=col, width=4)
            pct_val = int(val_clamp * 100)
            self.create_text(bx2 + 6, ry, text=f"{pct_val:+3d}%", fill=col, font=FONT_HUD_SMALL, anchor="w")
            ry += 20

        # Pilot Controller info
        ry += 6
        self.create_line(col3_x1 + 10, ry, col3_x2 - 10, ry, fill=COLOR_BORDER_LIGHT)
        ry += 14
        ctrl_col = COLOR_GREEN if self.gamepad_connected else COLOR_DIM
        self.create_text(col3_x1 + 12, ry, text=f"PILOT: {self.controller_name[:18]}", fill=ctrl_col, font=FONT_HUD_REG, anchor="w")
        ry += 16
        self.create_text(col3_x1 + 12, ry, text=f"GAIN: {int(self.gain * 100)}% | STATUS: {self.statustext[:16]}", fill=COLOR_DIM, font=FONT_HUD_SMALL, anchor="w")

        # 3. Bottom Status Strip (Height: 22px)
        bot_y1 = h - 28.0
        bot_y2 = h - 8.0
        self.create_rectangle(14, bot_y1, w - 14, bot_y2, fill="#070a12", outline=COLOR_BORDER_LIGHT)
        frame_name = self.matrix_mgr.get_frame_name(self.frame_id)
        self.create_text(
            24, (bot_y1 + bot_y2) / 2.0,
            text=f"FRAME: {frame_name.upper()} (ID {self.frame_id}) | ESC COMM PROTOCOL: PWM 1.1µs | MODE: PURE TELEMETRY",
            fill=COLOR_CYAN_DIM,
            font=FONT_HUD_SMALL,
            anchor="w"
        )
        self.create_text(
            w - 24, (bot_y1 + bot_y2) / 2.0,
            text="[ HUD GRAPHICS: DISABLED ]",
            fill=COLOR_AMBER,
            font=FONT_HUD_SMALL,
            anchor="e"
        )
