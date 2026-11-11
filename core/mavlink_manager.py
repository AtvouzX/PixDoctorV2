"""
PixDoctorV2 - Multithreaded MAVLink Telemetry and Command Engine.
Handles serial (USB/TELEM), UDP network links, heartbeat watchdog,
telemetry parsing (ATTITUDE, SYS_STATUS, SERVO_OUTPUT_RAW, VFR_HUD),
and bidirectional parameter and command dispatching.
"""

import time
import threading
from typing import Dict, Any, List, Optional, Callable
from pymavlink import mavutil

from core.ardusub_defs import (
    FLIGHT_MODES,
    MAV_CMD_DO_MOTOR_TEST,
    MAV_CMD_PREFLIGHT_CALIBRATION,
    MAV_CMD_DO_START_MAG_CAL,
    MAV_CMD_COMPONENT_ARM_DISARM,
)
from core.claw import ClawStatus, parse_statustext

# Telemetry streams requested when the link comes up (message id, Hz).
STREAMS = (
    (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 10.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 5.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS, 1.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS, 1.0),
    (mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT, 1.0),
)


class VehicleState:
    """Thread-safe snapshot of vehicle telemetry and link health."""

    def __init__(self):
        self.lock = threading.RLock()
        self.connected: bool = False
        self.link_type: str = "DISCONNECTED"
        self.port: str = ""
        self.baudrate: int = 115200

        # Identification
        self.firmware_name: str = "ArduSub 4.7.1"
        self.autopilot_name: str = "Pixhawk 2.4.8 (FMUv2)"
        self.target_system: int = 1
        self.target_component: int = 1

        # Link Statistics
        self.last_heartbeat_time: float = 0.0
        self.heartbeat_timeout: float = 3.0
        self.packet_count: int = 0
        self.message_rate_hz: float = 0.0

        # Vehicle Status
        self.armed: bool = False
        self.custom_mode: int = 19  # MANUAL default
        self.flight_mode_name: str = "MANUAL"

        # Sensor Telemetry
        self.roll_deg: float = 0.0
        self.pitch_deg: float = 0.0
        self.yaw_deg: float = 0.0
        self.depth_m: float = 0.0
        self.pressure_bar: float = 1.013
        self.temperature_c: float = 25.0

        # Power System
        self.vcc_voltage: float = 5.05    # Pixhawk 5V MCU rail
        self.battery_voltage: float = 0.0 # Main battery pack
        self.battery_current: float = 0.0 # Amps
        self.battery_pct: int = 100

        # Safety & Leak
        self.leak_detected: bool = False
        self.last_statustext: str = "System Ready"

        # Actuator Outputs (MAIN 1..8 in microseconds)
        self.servo_raw: List[int] = [1500] * 8
        # Torpedosub BTS7960 claw (state comes from STATUSTEXT only)
        self.claw = ClawStatus()

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "connected": self.connected,
                "link_type": self.link_type,
                "port": self.port,
                "baudrate": self.baudrate,
                "firmware": self.firmware_name,
                "autopilot": self.autopilot_name,
                "armed": self.armed,
                "flight_mode": self.custom_mode,
                "flight_mode_name": self.flight_mode_name,
                "roll": self.roll_deg,
                "pitch": self.pitch_deg,
                "yaw": self.yaw_deg,
                "depth": self.depth_m,
                "pressure_bar": self.pressure_bar,
                "temperature": self.temperature_c,
                "vcc_voltage": self.vcc_voltage,
                "battery_voltage": self.battery_voltage,
                "battery_current": self.battery_current,
                "battery_pct": self.battery_pct,
                "leak": self.leak_detected,
                "statustext": self.last_statustext,
                "servo_raw": list(self.servo_raw),
                "packet_rate_hz": self.message_rate_hz,
                "claw_state": self.claw.state,
                "claw_detail": self.claw.detail,
                "claw_fault": self.claw.fault,
                "claw_unavailable": self.claw.unavailable,
                "claw_current_ma": self.claw.current_ma,
            }


class MavlinkManager:
    """Multithreaded MAVLink connection and protocol coordinator."""

    def __init__(
        self,
        log_callback: Optional[Callable[[str, str], None]] = None,
        param_callback: Optional[Callable[[str, float, int], None]] = None,
    ):
        self.state = VehicleState()
        self.log_callback = log_callback
        self.param_callback = param_callback

        self.mav_conn: Optional[Any] = None
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None
        # GCS heartbeat period; config.toml [link] heartbeat_hz overrides it.
        self.heartbeat_interval: float = 1.0

        # Motor Test Streaming Engine (QGroundControl-style 20Hz stream to prevent ArduSub timeout disarm)
        self._motor_stream_active: bool = False
        self._motor_stream_ch: int = 1
        self._motor_stream_pwm: int = 1500
        self._motor_stream_lock = threading.Lock()
        self._motor_stream_thread: Optional[threading.Thread] = None

        self._packets_since_rate_calc = 0
        self._last_rate_time = time.time()

    def log(self, text: str, severity: str = "INFO"):
        if self.log_callback:
            self.log_callback(text, severity)

    def is_connected(self) -> bool:
        with self.state.lock:
            return self.state.connected

    def connect(
        self,
        port_or_conn_str: str,
        baudrate: int = 115200,
        source_system: int = 255,
        source_component: int = 191,
    ) -> bool:
        """Connect to Pixhawk via serial port, mavlink-router UDP or SITL."""
        self.disconnect()

        # Physical serial or UDP
        try:
            actual_target = port_or_conn_str.split(" ")[0].strip()
            self.log(f"[MAVLink] Opening connection to {actual_target} @ {baudrate} baud...", "INFO")

            # mavutil connection
            if actual_target.startswith(("udpin:", "udpout:", "udpbcast:", "udp:")):
                self.mav_conn = mavutil.mavlink_connection(
                    actual_target,
                    source_system=source_system,
                    source_component=source_component,
                )
                link_type = "UDP"
            else:
                self.mav_conn = mavutil.mavlink_connection(
                    actual_target,
                    baud=baudrate,
                    autoreconnect=True,
                    timeout=1.0,
                    source_system=source_system,
                    source_component=source_component,
                )
                link_type = "SERIAL"

            with self.state.lock:
                self.state.port = actual_target
                self.state.baudrate = baudrate
                self.state.link_type = link_type

            self.running = True
            self._thread = threading.Thread(target=self._reader_worker, daemon=True, name="MavlinkReaderWorker")
            self._thread.start()
            self._motor_stream_thread = threading.Thread(target=self._motor_stream_loop, daemon=True, name="MavlinkMotorStream")
            self._motor_stream_thread.start()
            return True

        except Exception as e:
            self.log(f"[MAVLink] Connection error on {port_or_conn_str}: {e}", "ERROR")
            self.disconnect()
            return False

    def disconnect(self):
        """Disconnect and stop threads."""
        self.running = False
        self._motor_stream_active = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

        if self._motor_stream_thread and self._motor_stream_thread.is_alive():
            self._motor_stream_thread.join(timeout=0.3)
        self._motor_stream_thread = None

        if self.mav_conn:
            try:
                self.mav_conn.close()
            except Exception:
                pass
            self.mav_conn = None

        with self.state.lock:
            self.state.connected = False
            self.state.link_type = "DISCONNECTED"

    def arm(self, arm_state: bool, force: bool = False):
        """Send arm / disarm command."""
        if not self.mav_conn:
            return

        param2 = 21196 if force else 0  # Magic number to force arm
        self.mav_conn.mav.command_long_send(
            self.state.target_system,
            self.state.target_component,
            MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1 if arm_state else 0,
            param2,
            0, 0, 0, 0, 0
        )
        action_str = "FORCE ARM" if (arm_state and force) else ("ARM" if arm_state else "DISARM")
        self.log(f"[MAVLink] Sent {action_str} command to Pixhawk", "INFO")

    def set_flight_mode(self, mode_id: int):
        """Set ArduSub custom flight mode."""
        if not self.mav_conn:
            return

        # ArduSub uses custom_mode with base_mode MAV_MODE_FLAG_CUSTOM_MODE_ENABLED (1)
        self.mav_conn.mav.set_mode_send(
            self.state.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        mode_info = FLIGHT_MODES.get(mode_id, {}).get("name", str(mode_id))
        self.log(f"[MAVLink] Switching Flight Mode to {mode_info}", "INFO")

    def set_safety_switch(self, safety_off: bool = True):
        """Disarm the hardware safety switch so PWM rails are energized (solid LED)."""
        if not self.mav_conn:
            return
        try:
            # Command 176: MAV_CMD_DO_SET_SAFETY (param1: 0 = safety off / active outputs)
            self.mav_conn.mav.command_long_send(
                self.state.target_system,
                self.state.target_component,
                176,  # MAV_CMD_DO_SET_SAFETY
                0,
                0 if safety_off else 1,
                0, 0, 0, 0, 0, 0
            )
        except Exception:
            pass

    def _motor_stream_loop(self):
        """
        QGroundControl-style 20Hz continuous motor test streamer.
        ArduSub's verify_motor_test() failsafe requires MAV_CMD_DO_MOTOR_TEST packets
        at >= 2Hz (every 500ms). If the GCS sends only one packet, ArduSub disarms after 500ms.
        Streaming at 20Hz (every 50ms) with MOTOR_TEST_ORDER_BOARD (2) keeps the watchdog fed
        and allows seamless motor testing without disarming.
        """
        last_safety_time = 0.0
        while self.running:
            if self._motor_stream_active and self.mav_conn and self.state.connected:
                now = time.time()
                if now - last_safety_time > 1.5:
                    self.set_safety_switch(True)
                    last_safety_time = now

                with self._motor_stream_lock:
                    ch = self._motor_stream_ch
                    pwm = self._motor_stream_pwm

                try:
                    # MAV_CMD_DO_MOTOR_TEST (Command 209)
                    # param1: 0-based motor instance (0 = M1, 1 = M2, 2 = M3, 3 = M4)
                    # ArduSub's Sub::handle_do_motor_test passes param1 directly to
                    # AP_MotorsMatrix::output_test_num(output_channel, pwm) which is 0-indexed!
                    motor_0_based = max(0, ch - 1)
                    self.mav_conn.mav.command_long_send(
                        self.state.target_system,
                        self.state.target_component,
                        209,  # MAV_CMD_DO_MOTOR_TEST
                        0,
                        motor_0_based,
                        1,    # MOTOR_TEST_THROTTLE_PWM
                        pwm,
                        0,    # timeout
                        1,    # motor count
                        2,    # MOTOR_TEST_ORDER_BOARD (2) -> ArduSub strictly requires this!
                        0
                    )
                except Exception:
                    pass

                time.sleep(0.05)  # 20 Hz = 50ms interval, identical to QGroundControl
            else:
                time.sleep(0.05)

    def start_motor_stream(self, channel_1_based: int, pwm_us: int):
        """Start or update continuous 20Hz motor test stream for a specific motor."""
        idx = channel_1_based - 1
        if 0 <= idx < 8:
            with self.state.lock:
                self.state.servo_raw[idx] = pwm_us

        self.set_safety_switch(True)
        with self._motor_stream_lock:
            self._motor_stream_ch = channel_1_based
            self._motor_stream_pwm = pwm_us
            self._motor_stream_active = True

    def stop_motor_stream(self):
        """Stop motor test stream cleanly and reset active motor to neutral 1500µs."""
        with self._motor_stream_lock:
            ch = self._motor_stream_ch
            self._motor_stream_active = False

        if self.mav_conn and self.state.connected:
            try:
                # Send neutral 1500 with 0 timeout to stop immediately (0-based motor index)
                motor_0_based = max(0, ch - 1)
                self.mav_conn.mav.command_long_send(
                    self.state.target_system,
                    self.state.target_component,
                    209,  # MAV_CMD_DO_MOTOR_TEST
                    0,
                    motor_0_based,
                    1,    # MOTOR_TEST_THROTTLE_PWM
                    1500,
                    0,    # 0 timeout = stop
                    1,    # motor count
                    2,    # MOTOR_TEST_ORDER_BOARD
                    0
                )
            except Exception:
                pass

    def set_servo_override(self, channel_1_based: int, pwm_us: int, timeout_sec: float = 3.0):
        """
        Directly command a specific motor output (1 to 8) or aux channel (9 to 14).
        For motors 1..8: starts continuous 20Hz stream so ArduSub never disarms.
        """
        idx = channel_1_based - 1
        if 0 <= idx < 8:
            with self.state.lock:
                self.state.servo_raw[idx] = pwm_us

        if not self.mav_conn:
            return

        try:
            self.set_safety_switch(safety_off=True)

            if 1 <= channel_1_based <= 8:
                self.start_motor_stream(channel_1_based, pwm_us)
            else:
                # Aux / Servo channels 9-14
                self.mav_conn.mav.command_long_send(
                    self.state.target_system,
                    self.state.target_component,
                    183,  # MAV_CMD_DO_SET_SERVO
                    0,
                    channel_1_based,
                    pwm_us,
                    0, 0, 0, 0, 0
                )
        except Exception as e:
            self.log(f"[MAVLink] Motor override error on M{channel_1_based}: {e}", "WARN")

    def release_servo_overrides(self):
        """Release all manual PWM overrides and return motors to neutral."""
        self.stop_motor_stream()
        with self.state.lock:
            self.state.servo_raw = [1500] * 8

        if not self.mav_conn:
            return

        try:
            for ch in range(1, 9):
                self.mav_conn.mav.command_long_send(
                    self.state.target_system,
                    self.state.target_component,
                    209,  # MAV_CMD_DO_MOTOR_TEST
                    0,
                    ch - 1,    # 0-based motor instance (0 = M1, 1 = M2, ...)
                    1,         # MOTOR_TEST_THROTTLE_PWM
                    1500,
                    0,         # 0 timeout = stop
                    1,
                    2,         # MOTOR_TEST_ORDER_BOARD
                    0
                )
                self.mav_conn.mav.command_long_send(
                    self.state.target_system,
                    self.state.target_component,
                    183,  # MAV_CMD_DO_SET_SERVO
                    0,
                    ch,
                    1500,
                    0, 0, 0, 0, 0
                )
        except Exception:
            pass

    def send_motor_test(self, motor_instance_1_based: int, throttle_pct: float, timeout_sec: float = 2.0):
        """
        Send timed motor test pulse using 20Hz continuous streaming to prevent ArduSub timeout.
        """
        target_pwm = int(1500 + (throttle_pct * 4.0))
        target_pwm = max(1000, min(2000, target_pwm))

        def _timed_worker():
            self.start_motor_stream(motor_instance_1_based, target_pwm)
            time.sleep(timeout_sec)
            self.start_motor_stream(motor_instance_1_based, 1500)
            time.sleep(0.3)
            self.stop_motor_stream()

        threading.Thread(target=_timed_worker, daemon=True, name=f"MotorPulse_M{motor_instance_1_based}").start()
        self.log(f"[MAVLink] Timed Motor Test M{motor_instance_1_based} @ {throttle_pct:.0f}% for {timeout_sec:.1f}s (20Hz Stream)", "INFO")

    def calibrate_depth_tare(self):
        """Zero / Tare Bar30 / MS5837 pressure sensor at current water surface."""
        if not self.mav_conn:
            return
        # MAV_CMD_PREFLIGHT_CALIBRATION with param3 = 1 (Barometer tare)
        self.mav_conn.mav.command_long_send(
            self.state.target_system,
            self.state.target_component,
            MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
            0, 0, 1.0, 0, 0, 0, 0
        )
        self.log("[MAVLink] Sent Depth Sensor Zero/Tare calibration command", "INFO")

    def calibrate_accel_level(self):
        """Calibrate accelerometer level orientation."""
        if not self.mav_conn:
            return
        # MAV_CMD_PREFLIGHT_CALIBRATION with param5 = 1 (Level)
        self.mav_conn.mav.command_long_send(
            self.state.target_system,
            self.state.target_component,
            MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
            0, 0, 0, 0, 1.0, 0, 0
        )
        self.log("[MAVLink] Sent Accelerometer 1-Step Level calibration command", "INFO")

    def calibrate_compass(self):
        """Trigger onboard compass calibration."""
        if not self.mav_conn:
            return
        self.mav_conn.mav.command_long_send(
            self.state.target_system,
            self.state.target_component,
            MAV_CMD_DO_START_MAG_CAL,
            0,
            0, 0, 1, 0, 0, 0, 0
        )
        self.log("[MAVLink] Triggered Onboard Compass Calibration", "INFO")

    def control_gripper(self, grab: bool):
        """
        Send MAV_CMD_DO_GRIPPER command to open/release or close/grab the claw.
        grab=True: GRIPPER_ACTION_GRAB (1)
        grab=False: GRIPPER_ACTION_RELEASE (0)
        """
        if not self.mav_conn:
            return
        from core.ardusub_defs import MAV_CMD_DO_GRIPPER, GRIPPER_ACTION_GRAB, GRIPPER_ACTION_RELEASE
        action = GRIPPER_ACTION_GRAB if grab else GRIPPER_ACTION_RELEASE
        self.mav_conn.mav.command_long_send(
            self.state.target_system,
            self.state.target_component,
            MAV_CMD_DO_GRIPPER,
            0,
            1,  # Gripper instance
            action,
            0, 0, 0, 0, 0
        )
        action_name = "GRAB" if grab else "RELEASE"
        self.log(f"[MAVLink] Sent Gripper command: {action_name}", "INFO")

    def send_manual_control(self, x: int, y: int, z: int, r: int, buttons: int):
        """
        Send flight control commands to Pixhawk.
        x: Forward/Reverse (-1000..1000)
        y: Lateral Strafe (-1000..1000)
        z: Depth/Throttle (-1000..1000, 0 neutral)
        r: Yaw Heading (-1000..1000)
        buttons: uint16 bitmask
        """
        if not self.mav_conn:
            return

        def clamp(value: int) -> int:
            return max(-1000, min(1000, int(value)))

        # In ArduSub MANUAL_CONTROL, z is 0-1000 with 500 being neutral depth
        scaled_z = max(0, min(1000, int((clamp(z) + 1000) / 2)))
        try:
            self.mav_conn.mav.manual_control_send(
                self.state.target_system,
                clamp(x), clamp(y), scaled_z, clamp(r), int(buttons) & 0xFFFF
            )
        except Exception:
            pass

    def request_param(self, param_name: str):
        """Ask the vehicle for a single parameter value."""
        if not self.mav_conn:
            return
        try:
            self.mav_conn.mav.param_request_read_send(
                self.state.target_system,
                self.state.target_component,
                param_name.encode("ascii")[:16],
                -1,
            )
        except Exception:
            pass

    def set_message_interval(self, message_id: int, hz: float):
        """Request a telemetry stream rate with MAV_CMD_SET_MESSAGE_INTERVAL."""
        if not self.mav_conn:
            return
        interval_us = int(1_000_000 / hz) if hz > 0 else -1
        try:
            self.mav_conn.mav.command_long_send(
                self.state.target_system,
                self.state.target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                float(message_id),
                float(interval_us),
                0.0, 0.0, 0.0, 0.0, 0.0,
            )
        except Exception:
            pass

    def request_streams(self):
        """Ask for the streams used by the HUD and control view."""
        for message_id, hz in STREAMS:
            self.set_message_interval(message_id, hz)

    def request_param_list(self):
        """Request entire parameter list from Pixhawk."""
        if not self.mav_conn:
            return
        self.mav_conn.mav.param_request_list_send(
            self.state.target_system,
            self.state.target_component
        )
        self.log("[MAVLink] Requesting parameter list from Pixhawk...", "INFO")

    def set_param(self, param_name: str, value: float):
        """Commit a single parameter to Pixhawk flash."""
        if not self.mav_conn:
            return
        self.mav_conn.mav.param_set_send(
            self.state.target_system,
            self.state.target_component,
            param_name.encode("utf-8")[:16],
            float(value),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        self.log(f"[MAVLink] Param Set: {param_name} = {value}", "INFO")

    def _reader_worker(self):
        """Non-blocking MAVLink message reading and dispatch thread."""
        last_hb_send = 0.0

        while self.running and self.mav_conn:
            try:
                # 1. Read message with short timeout
                msg = self.mav_conn.recv_match(blocking=True, timeout=0.05)

                # Send GCS heartbeat periodically to maintain link
                now = time.time()
                if now - last_hb_send >= self.heartbeat_interval:
                    try:
                        self.mav_conn.mav.heartbeat_send(
                            mavutil.mavlink.MAV_TYPE_GCS,
                            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                            0, 0, 0
                        )
                        last_hb_send = now
                    except Exception:
                        pass

                if not msg:
                    # Check if port died in pymavlink
                    if self.mav_conn and getattr(self.mav_conn, "dead", False):
                        with self.state.lock:
                            if self.state.connected:
                                self.state.connected = False
                                self.state.claw.reset("link lost")
                                self.log("[MAVLink] Serial port connection died", "WARN")
                        time.sleep(0.5)
                        continue

                # Heartbeat watchdog runs even while other telemetry arrives.
                if (
                    self.state.connected
                    and now - self.state.last_heartbeat_time > self.state.heartbeat_timeout
                ):
                    with self.state.lock:
                        if self.state.connected:
                            self.state.connected = False
                            self.state.claw.reset("link lost")
                            self.log("[MAVLink] Heartbeat lost - vehicle offline", "WARN")
                if not msg:
                    continue

                self._process_mavlink_msg(msg)

            except Exception as e:
                if self.running:
                    self.log(f"[MAVLink] Read loop exception: {e}", "WARN")
                    time.sleep(0.1)

    def _process_mavlink_msg(self, msg):
        """Process decoded MAVLink packet."""
        msg_type = msg.get_type()
        now = time.time()

        with self.state.lock:
            self.state.packet_count += 1
            self._packets_since_rate_calc += 1
            dt = now - self._last_rate_time
            if dt >= 1.0:
                self.state.message_rate_hz = self._packets_since_rate_calc / dt
                self._packets_since_rate_calc = 0
                self._last_rate_time = now

        if msg_type == "HEARTBEAT":
            # Ignore GCS / MAVLink-router heartbeats; only the autopilot counts.
            if msg.type == mavutil.mavlink.MAV_TYPE_GCS:
                return
            if msg.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                return
            # Autopilot heartbeat
            link_up = False
            with self.state.lock:
                link_up = not self.state.connected
                self.state.connected = True
                self.state.last_heartbeat_time = now
                self.state.target_system = msg.get_srcSystem()
                self.state.target_component = msg.get_srcComponent()

                # Base mode & arming
                base_mode = msg.base_mode
                self.state.armed = bool(base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

                # Custom mode
                self.state.custom_mode = msg.custom_mode
                mode_def = FLIGHT_MODES.get(msg.custom_mode)
                self.state.flight_mode_name = mode_def["name"] if mode_def else f"MODE_{msg.custom_mode}"
            if link_up:
                self.log("[MAVLink] Autopilot heartbeat received, link up", "INFO")
                self.request_streams()

        elif msg_type == "ATTITUDE":
            import math
            with self.state.lock:
                self.state.roll_deg = round(math.degrees(msg.roll), 1)
                self.state.pitch_deg = round(math.degrees(msg.pitch), 1)
                self.state.yaw_deg = round(math.degrees(msg.yaw) % 360.0, 1)

        elif msg_type == "VFR_HUD":
            # Barometric altitude / depth
            with self.state.lock:
                # In ArduSub, alt is negative depth
                self.state.depth_m = max(0.0, round(-msg.alt, 2)) if msg.alt < 0 else round(msg.alt, 2)

        elif msg_type in ("SCALED_PRESSURE", "SCALED_PRESSURE2"):
            # Bar30 / MS5837 pressure sensor
            with self.state.lock:
                self.state.pressure_bar = round(msg.press_abs / 1000.0, 3)
                self.state.temperature_c = round(msg.temperature / 100.0, 1)

        elif msg_type == "SYS_STATUS":
            with self.state.lock:
                self.state.battery_voltage = round(msg.voltage_battery / 1000.0, 2)
                self.state.battery_current = round(msg.current_battery / 100.0, 1)
                self.state.battery_pct = msg.battery_remaining
                # Check sensor health for leak
                sensors_health = msg.onboard_control_sensors_health
                # MAV_SYS_STATUS_SENSOR_PROXIMITY or custom leak flag

        elif msg_type == "SERVO_OUTPUT_RAW":
            with self.state.lock:
                self.state.servo_raw = [
                    msg.servo1_raw, msg.servo2_raw, msg.servo3_raw, msg.servo4_raw,
                    msg.servo5_raw, msg.servo6_raw, msg.servo7_raw, msg.servo8_raw
                ]

        elif msg_type == "STATUSTEXT":
            text = msg.text
            if isinstance(text, bytes):
                text = text.decode(errors="replace")
            text = text.rstrip("\x00")
            with self.state.lock:
                self.state.last_statustext = text
                if "LEAK" in text.upper():
                    self.state.leak_detected = True
                parse_statustext(text, self.state.claw)
            self.log(f"[Pixhawk] {text}", "WARN" if "ERROR" in text.upper() or "FAIL" in text.upper() else "INFO")

        elif msg_type == "PARAM_VALUE":
            param_id = msg.param_id
            if isinstance(param_id, bytes):
                param_id = param_id.decode(errors="replace")
            param_id = param_id.rstrip("\x00")
            param_value = msg.param_value
            param_type = msg.param_type
            if param_id == "GRIP_DC_CURR":
                with self.state.lock:
                    self.state.claw.current_ma = int(param_value)
            if self.param_callback:
                self.param_callback(param_id, param_value, param_type)


