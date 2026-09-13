"""
PixDoctorV2 - Multithreaded Arduino Nano 33 IoT (PixDoctorNano) Probe Manager.
Handles USB CDC Serial communication at 115200 baud, decodes 20Hz JSON stream
from the 14-channel logic probe, and performs real-time closed-loop verification.
"""

import time
import json
import threading
from typing import Dict, Any, List, Optional, Callable
import serial
import serial.tools.list_ports


class NanoProbeState:
    """Thread-safe snapshot of Arduino Nano 33 IoT physical probe measurements."""

    def __init__(self):
        self.lock = threading.RLock()
        self.connected: bool = False
        self.port: str = ""
        self.baudrate: int = 115200
        self.device_info: str = "Arduino Nano 33 IoT (PixDoctorNano)"
        self.firmware_version: str = "Unknown"
        self.last_update_time: float = 0.0
        self.packet_count: int = 0
        self.packet_rate_hz: float = 0.0

        # 14 Channels: Index 0..13 (MAIN 1..8 and AUX 1..6)
        self.measured_pwm: List[int] = [0] * 14
        self.measured_hz: List[float] = [0.0] * 14
        self.signal_valid: List[bool] = [False] * 14

        # Closed-loop comparison against Pixhawk commanded outputs
        self.commanded_pwm: List[int] = [1500] * 14
        self.error_delta_us: List[int] = [0] * 14

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "connected": self.connected,
                "port": self.port,
                "baudrate": self.baudrate,
                "device_info": self.device_info,
                "firmware_version": self.firmware_version,
                "last_update_time": self.last_update_time,
                "packet_count": self.packet_count,
                "packet_rate_hz": self.packet_rate_hz,
                "measured_pwm": list(self.measured_pwm),
                "measured_hz": list(self.measured_hz),
                "signal_valid": list(self.signal_valid),
                "commanded_pwm": list(self.commanded_pwm),
                "error_delta_us": list(self.error_delta_us),
            }


class NanoProbeManager:
    """
    Multithreaded driver for PixDoctorNano probe.
    Reads 20Hz JSON stream containing 1.1µs physical PWM timing data.
    """

    def __init__(self, log_callback: Optional[Callable[[str, str], None]] = None):
        self.state = NanoProbeState()
        self.log_callback = log_callback
        self.serial_conn: Optional[serial.Serial] = None
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._last_rate_calc_time = time.time()
        self._packets_since_rate_calc = 0

    def log(self, msg: str, level: str = "INFO"):
        if self.log_callback:
            self.log_callback(msg, level)

    def set_commanded_pwm(self, channel_1_based: int, pwm_us: int):
        """Update reference commanded PWM from Pixhawk to compute live error delta."""
        idx = channel_1_based - 1
        if 0 <= idx < 14:
            with self.state.lock:
                self.state.commanded_pwm[idx] = pwm_us
                if self.state.signal_valid[idx] and self.state.measured_pwm[idx] > 0:
                    self.state.error_delta_us[idx] = self.state.measured_pwm[idx] - pwm_us

    def connect(self, port_str: str, baudrate: int = 115200) -> bool:
        """Open serial connection to Arduino Nano 33 IoT."""
        self.disconnect()
        try:
            # Extract pure port name (e.g. 'COM4') from descriptive strings
            actual_port = port_str.split(" ")[0].strip()
            self.serial_conn = serial.Serial(
                port=actual_port,
                baudrate=baudrate,
                timeout=0.2,
                write_timeout=0.5
            )
            # Toggle DTR for USB CDC connection
            self.serial_conn.dtr = True
            time.sleep(0.1)

            with self.state.lock:
                self.state.connected = True
                self.state.port = actual_port
                self.state.baudrate = baudrate

            self.running = True
            self._thread = threading.Thread(target=self._reader_worker, daemon=True, name="NanoProbeWorker")
            self._thread.start()

            # Query device info
            self.send_command("PING")
            self.send_command("START")
            self.log(f"[Nano Probe] Connected on {actual_port} @ {baudrate} baud", "INFO")
            return True
        except Exception as e:
            self.log(f"[Nano Probe] Connection failed on {port_str}: {e}", "ERROR")
            self.disconnect()
            return False

    def disconnect(self):
        """Safely close serial port and terminate reader thread."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

        if self.serial_conn:
            try:
                if self.serial_conn.is_open:
                    self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None

        with self.state.lock:
            self.state.connected = False
            for i in range(14):
                self.state.signal_valid[i] = False
                self.state.measured_pwm[i] = 0
                self.state.measured_hz[i] = 0.0
                self.state.error_delta_us[i] = 0

    def send_command(self, cmd: str):
        """Send plain text command (e.g. PING, RATE 20, RESET) to PixDoctorNano."""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(f"{cmd.strip()}\n".encode("utf-8"))
                self.serial_conn.flush()
            except Exception as e:
                self.log(f"[Nano Probe] Send error: {e}", "WARN")

    def _reader_worker(self):
        """Background daemon thread reading JSON frames from Nano 33 IoT."""
        buffer = ""
        while self.running and self.serial_conn and self.serial_conn.is_open:
            try:
                data = self.serial_conn.read(self.serial_conn.in_waiting or 1).decode("utf-8", errors="replace")
                if not data:
                    continue
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process_line(line)
            except Exception as e:
                if self.running:
                    self.log(f"[Nano Probe] Stream read error: {e}", "ERROR")
                    time.sleep(0.1)
                break

    def _process_line(self, line: str):
        """Parse incoming JSON packets from Nano 33 IoT probe."""
        if not line.startswith("{") or not line.endswith("}"):
            return

        try:
            pkt = json.loads(line)
            pkt_type = pkt.get("type", "")

            if pkt_type == "PROBE_DATA":
                pwms = pkt.get("pwm", [])
                hzs = pkt.get("hz", [])
                valids = pkt.get("valid", [])

                with self.state.lock:
                    self.state.packet_count += 1
                    self.state.last_update_time = time.time()

                    for i in range(min(14, len(pwms))):
                        self.state.measured_pwm[i] = int(pwms[i])
                        self.state.measured_hz[i] = float(hzs[i]) if i < len(hzs) else 0.0
                        self.state.signal_valid[i] = bool(valids[i]) if i < len(valids) else False

                        # Closed loop error delta: (Measured - Commanded)
                        if self.state.signal_valid[i] and self.state.measured_pwm[i] > 0:
                            cmd_pwm = self.state.commanded_pwm[i]
                            self.state.error_delta_us[i] = self.state.measured_pwm[i] - cmd_pwm
                        else:
                            self.state.error_delta_us[i] = 0

                    # Calculate packet rate
                    self._packets_since_rate_calc += 1
                    now = time.time()
                    dt = now - self._last_rate_calc_time
                    if dt >= 1.0:
                        self.state.packet_rate_hz = self._packets_since_rate_calc / dt
                        self._packets_since_rate_calc = 0
                        self._last_rate_calc_time = now

            elif pkt_type == "PONG":
                with self.state.lock:
                    self.state.firmware_version = pkt.get("fw", "2.0.0")
                    self.state.device_info = f"PixDoctorNano ({pkt.get('mcu', 'SAMD21')})"
                self.log(f"[Nano Probe] Identified: {self.state.device_info} FW:{self.state.firmware_version}", "INFO")

        except json.JSONDecodeError:
            pass
        except Exception as e:
            self.log(f"[Nano Probe] JSON parse error: {e}", "WARN")
