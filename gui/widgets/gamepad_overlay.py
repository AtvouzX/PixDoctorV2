"""
PixDoctorV2 - Nostalgic Wireless Gamepad & XInput Controller Mapping Visualizer.
Renders full controller schematic, stick crosshairs, trigger gauges, active button
states, and live mapped action callouts in retro high-contrast monochrome style.
"""

import tkinter as tk
from typing import Dict, Any, Optional, Callable
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
    FONT_MONO,
)


class GamepadOverlay(tk.Frame):
    """
    Visualizes live joystick axes, triggers, and button states with mapped action callouts.
    Supports interactive clicking on buttons to select them for quick remapping.
    """

    def __init__(self, parent, on_button_selected: Optional[Callable[[str], None]] = None, **kwargs):
        super().__init__(parent, bg=COLOR_SURFACE, **kwargs)
        self.on_button_selected = on_button_selected

        # Header Strip
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
            text="PILOT GAIN: 50%",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY_BOLD,
            anchor="e"
        )
        self.lbl_gain.pack(side=tk.RIGHT)

        # Canvas for Gamepad Schematic
        self.canvas = tk.Canvas(
            self,
            bg=COLOR_BG,
            height=230,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Telemetry Bar at bottom
        self.telemetry_bar = tk.Label(
            self,
            text="MAVLINK MANUAL_CONTROL: X: +0 | Y: +0 | Z: +0 | R: +0 | BTNS: 0x0000",
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM,
            font=FONT_SMALL,
            anchor="w",
            pady=3
        )
        self.telemetry_bar.pack(fill=tk.X, pady=(4, 0))

        # State storage
        self.lx = 0
        self.ly = 0
        self.rx = 0
        self.ry = 0
        self.lt = 0
        self.rt = 0
        self.connected = False
        self.buttons: Dict[str, bool] = {}
        self.mappings: Dict[str, str] = {}
        self.selected_button: Optional[str] = None

        # Interactive click targets
        self._click_targets = []

        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<Button-1>", self._on_canvas_click)

    def update_gamepad_state(self, state_dict: Dict[str, Any]):
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
        self.mappings = state_dict.get("button_mappings", {})

        # Update telemetry bar
        gain = state_dict.get("gain", 0.5)
        tx_fwd = int(self.ry * gain)
        tx_lat = int(self.rx * gain)
        tx_depth = int(self.ly * gain)
        tx_yaw = int(self.lx * gain)
        tx_b = state_dict.get("buttons_bitmask", 0)
        self.telemetry_bar.config(
            text=f"MAVLINK MANUAL_CONTROL (20Hz): FWD(X): {tx_fwd:+4d} | LAT(Y): {tx_lat:+4d} | "
                 f"DEPTH(Z): {tx_depth:+4d} | YAW(R): {tx_yaw:+4d} | BTN: 0x{tx_b:04X}"
        )

        self.redraw()

    def set_selected_button(self, btn_name: Optional[str]):
        self.selected_button = btn_name
        self.redraw()

    def _on_canvas_click(self, event):
        x, y = event.x, event.y
        for x1, y1, x2, y2, btn_name in self._click_targets:
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.selected_button = btn_name
                if self.on_button_selected:
                    self.on_button_selected(btn_name)
                self.redraw()
                break

    def _short_action(self, action_id: str) -> str:
        """Convert long action string to concise badge label."""
        labels = {
            "TOGGLE_ARM": "ARM/DISARM",
            "DISARM": "KILL THRUST",
            "CYCLE_MODE": "NEXT MODE",
            "MODE_MANUAL": "MANUAL",
            "MODE_ALT_HOLD": "DEPTH HOLD",
            "MODE_STABILIZE": "STABILIZE",
            "CAMERA_TILT_UP": "TILT UP",
            "CAMERA_TILT_DOWN": "TILT DOWN",
            "CAMERA_TILT_CENTER": "TILT CTR",
            "LIGHTS_CYCLE": "LIGHTS +",
            "LIGHTS_OFF": "LIGHTS OFF",
            "CLAW_GRAB": "CLAW GRAB",
            "CLAW_RELEASE": "CLAW OPEN",
            "CLAW_STOP": "CLAW STOP",
            "GAIN_INCREASE": "GAIN +25%",
            "GAIN_DECREASE": "GAIN -25%",
            "NONE": "NONE",
        }
        return labels.get(action_id, action_id)

    def redraw(self):
        self.canvas.delete("all")
        self._click_targets.clear()

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 80 or h <= 80:
            return

        # Background grid watermark
        for y_line in range(20, h, 20):
            self.canvas.create_line(0, y_line, w, y_line, fill="#121216", width=1)
        for x_line in range(20, w, 20):
            self.canvas.create_line(x_line, 0, x_line, h, fill="#121216", width=1)

        stick_fill = COLOR_INVERT_BG if self.connected else COLOR_BORDER_LIGHT

        # ==================== 1. TOP SHOULDERS & TRIGGERS ====================
        # Left Trigger (LT)
        lt_w = 90
        lt_x1, lt_y1 = w * 0.16 - lt_w / 2, 10
        lt_x2, lt_y2 = lt_x1 + lt_w, lt_y1 + 14
        self.canvas.create_rectangle(lt_x1, lt_y1, lt_x2, lt_y2, outline=COLOR_BORDER, width=1)
        lt_fill_w = (self.lt / 1000.0) * lt_w
        if lt_fill_w > 0:
            self.canvas.create_rectangle(lt_x1, lt_y1, lt_x1 + lt_fill_w, lt_y2, fill=COLOR_INVERT_BG, outline="")
        self.canvas.create_text(lt_x1 + lt_w / 2, lt_y1 + 7, text=f"LT: {self.lt//10}%", fill=COLOR_TEXT_WHITE if lt_fill_w < 45 else COLOR_INVERT_FG, font=FONT_SMALL)

        # Left Bumper (LB)
        lb_act = self.buttons.get("btn_lb", False)
        lb_x, lb_y, lb_w, lb_h = w * 0.16, 36, 100, 20
        self._draw_interactive_button("btn_lb", "LB", lb_x, lb_y, lb_w, lb_h, lb_act)

        # Right Trigger (RT)
        rt_x1, rt_y1 = w * 0.84 - lt_w / 2, 10
        rt_x2, rt_y2 = rt_x1 + lt_w, rt_y1 + 14
        self.canvas.create_rectangle(rt_x1, rt_y1, rt_x2, rt_y2, outline=COLOR_BORDER, width=1)
        rt_fill_w = (self.rt / 1000.0) * lt_w
        if rt_fill_w > 0:
            self.canvas.create_rectangle(rt_x2 - rt_fill_w, rt_y1, rt_x2, rt_y2, fill=COLOR_INVERT_BG, outline="")
        self.canvas.create_text(rt_x1 + lt_w / 2, rt_y1 + 7, text=f"RT: {self.rt//10}%", fill=COLOR_TEXT_WHITE if rt_fill_w < 45 else COLOR_INVERT_FG, font=FONT_SMALL)

        # Right Bumper (RB)
        rb_act = self.buttons.get("btn_rb", False)
        rb_x, rb_y = w * 0.84, 36
        self._draw_interactive_button("btn_rb", "RB", rb_x, rb_y, lb_w, lb_h, rb_act)

        # ==================== 2. LEFT STICK (DEPTH / YAW) ====================
        ls_cx = w * 0.18
        ls_cy = h * 0.60
        r = 40
        self.canvas.create_oval(ls_cx - r, ls_cy - r, ls_cx + r, ls_cy + r, outline=COLOR_BORDER_LIGHT, width=1)
        self.canvas.create_line(ls_cx - r, ls_cy, ls_cx + r, ls_cy, fill=COLOR_BORDER, width=1)
        self.canvas.create_line(ls_cx, ls_cy - r, ls_cx, ls_cy + r, fill=COLOR_BORDER, width=1)

        # Deadzone circle watermark
        dz_r = r * 0.10
        self.canvas.create_oval(ls_cx - dz_r, ls_cy - dz_r, ls_cx + dz_r, ls_cy + dz_r, outline="#1f1f26", width=1)

        # Moving crosshair dot
        px = ls_cx + (self.lx / 1000.0) * (r - 4)
        py = ls_cy - (self.ly / 1000.0) * (r - 4)
        l3_act = self.buttons.get("btn_l3", False)
        dot_color = COLOR_TEXT_WHITE if l3_act else stick_fill
        dot_r = 7 if l3_act else 5
        self.canvas.create_oval(px - dot_r, py - dot_r, px + dot_r, py + dot_r, fill=dot_color, outline="")

        # L3 Button
        self._draw_interactive_button("btn_l3", "L3", ls_cx, ls_cy + r + 14, 36, 16, l3_act)
        self.canvas.create_text(ls_cx, ls_cy + r + 30, text=f"LX:{self.lx:+4d} | LY:{self.ly:+4d}", fill=COLOR_TEXT_DIM, font=FONT_MONO)
        self.canvas.create_text(ls_cx, ls_cy - r - 10, text="LEFT STICK (YAW / DEPTH)", fill=COLOR_TEXT_WHITE, font=FONT_SMALL)

        # ==================== 3. D-PAD ====================
        dp_cx = w * 0.36
        dp_cy = h * 0.60
        sz = 22
        # Center hub
        self.canvas.create_rectangle(dp_cx - sz/2, dp_cy - sz/2, dp_cx + sz/2, dp_cy + sz/2, fill=COLOR_SURFACE, outline=COLOR_BORDER)

        self._draw_interactive_button("dpad_up", "UP", dp_cx, dp_cy - sz, sz, sz, self.buttons.get("dpad_up", False), show_action=False)
        self._draw_interactive_button("dpad_down", "DN", dp_cx, dp_cy + sz, sz, sz, self.buttons.get("dpad_down", False), show_action=False)
        self._draw_interactive_button("dpad_left", "LT", dp_cx - sz, dp_cy, sz, sz, self.buttons.get("dpad_left", False), show_action=False)
        self._draw_interactive_button("dpad_right", "RT", dp_cx + sz, dp_cy, sz, sz, self.buttons.get("dpad_right", False), show_action=False)
        self.canvas.create_text(dp_cx, dp_cy + sz * 2 + 10, text="D-PAD", fill=COLOR_TEXT_DIM, font=FONT_SMALL)

        # ==================== 4. CENTER CONTROLS (BACK & START) ====================
        mid_x = w * 0.50
        self._draw_interactive_button("btn_back", "BACK", mid_x - 36, h * 0.44, 48, 22, self.buttons.get("btn_back", False))
        self._draw_interactive_button("btn_start", "START", mid_x + 36, h * 0.44, 48, 22, self.buttons.get("btn_start", False))

        # Center Status Emblem
        hub_text = "XINPUT" if "XInput" in self.lbl_title.cget("text") else "WINMM"
        self.canvas.create_rectangle(mid_x - 30, h * 0.62 - 10, mid_x + 30, h * 0.62 + 10, outline=COLOR_BORDER_LIGHT, fill=COLOR_SURFACE)
        self.canvas.create_text(mid_x, h * 0.62, text=hub_text, fill=COLOR_TEXT_WHITE, font=FONT_SMALL)

        # ==================== 5. FACE BUTTONS (X, Y, B, A) ====================
        face_cx = w * 0.64
        face_cy = h * 0.60
        f_sz = 24

        self._draw_interactive_button("btn_y", "Y", face_cx, face_cy - f_sz, f_sz, f_sz, self.buttons.get("btn_y", False), show_action=False)
        self._draw_interactive_button("btn_x", "X", face_cx - f_sz, face_cy, f_sz, f_sz, self.buttons.get("btn_x", False), show_action=False)
        self._draw_interactive_button("btn_b", "B", face_cx + f_sz, face_cy, f_sz, f_sz, self.buttons.get("btn_b", False), show_action=False)
        self._draw_interactive_button("btn_a", "A", face_cx, face_cy + f_sz, f_sz, f_sz, self.buttons.get("btn_a", False), show_action=False)
        self.canvas.create_text(face_cx, face_cy + f_sz * 2 + 10, text="ACTION BUTTONS", fill=COLOR_TEXT_DIM, font=FONT_SMALL)

        # ==================== 6. RIGHT STICK (FORWARD / STRAFE) ====================
        rs_cx = w * 0.82
        rs_cy = h * 0.60

        self.canvas.create_oval(rs_cx - r, rs_cy - r, rs_cx + r, rs_cy + r, outline=COLOR_BORDER_LIGHT, width=1)
        self.canvas.create_line(rs_cx - r, rs_cy, rs_cx + r, rs_cy, fill=COLOR_BORDER, width=1)
        self.canvas.create_line(rs_cx, rs_cy - r, rs_cx, rs_cy + r, fill=COLOR_BORDER, width=1)
        self.canvas.create_oval(rs_cx - dz_r, rs_cy - dz_r, rs_cx + dz_r, rs_cy + dz_r, outline="#1f1f26", width=1)

        rpx = rs_cx + (self.rx / 1000.0) * (r - 4)
        rpy = rs_cy - (self.ry / 1000.0) * (r - 4)
        r3_act = self.buttons.get("btn_r3", False)
        rdot_color = COLOR_TEXT_WHITE if r3_act else stick_fill
        rdot_r = 7 if r3_act else 5
        self.canvas.create_oval(rpx - rdot_r, rpy - rdot_r, rpx + rdot_r, rpy + rdot_r, fill=rdot_color, outline="")

        # R3 Button
        self._draw_interactive_button("btn_r3", "R3", rs_cx, rs_cy + r + 14, 36, 16, r3_act)
        self.canvas.create_text(rs_cx, rs_cy + r + 30, text=f"RX:{self.rx:+4d} | RY:{self.ry:+4d}", fill=COLOR_TEXT_DIM, font=FONT_MONO)
        self.canvas.create_text(rs_cx, rs_cy - r - 10, text="RIGHT STICK (FWD / STRAFE)", fill=COLOR_TEXT_WHITE, font=FONT_SMALL)

    def _draw_interactive_button(
        self,
        btn_key: str,
        label: str,
        cx: float,
        cy: float,
        bw: float,
        bh: float,
        active: bool,
        show_action: bool = True
    ):
        """Draw clickable button on canvas with action callout tag."""
        x1, y1 = cx - bw / 2, cy - bh / 2
        x2, y2 = cx + bw / 2, cy + bh / 2

        self._click_targets.append((x1 - 4, y1 - 4, x2 + 4, y2 + 4, btn_key))

        is_selected = (self.selected_button == btn_key)
        bg_col = COLOR_INVERT_BG if active else (COLOR_BORDER if is_selected else COLOR_SURFACE)
        fg_col = COLOR_INVERT_FG if active else COLOR_TEXT_WHITE
        outline_col = COLOR_TEXT_WHITE if (active or is_selected) else COLOR_BORDER_LIGHT
        width = 2 if is_selected else 1

        self.canvas.create_rectangle(x1, y1, x2, y2, fill=bg_col, outline=outline_col, width=width)
        self.canvas.create_text(cx, cy, text=label, fill=fg_col, font=FONT_SMALL)

        if show_action:
            action_id = self.mappings.get(btn_key, "NONE")
            short_desc = self._short_action(action_id)
            if short_desc != "NONE":
                self.canvas.create_text(cx, cy + bh/2 + 8, text=short_desc, fill=COLOR_TEXT_DIM, font=FONT_SMALL)
