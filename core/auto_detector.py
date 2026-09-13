"""
PixDoctorV2 - Hardware Auto-Detection & Auto-Connect Coordinator.
Continuously scans system USB/Serial ports in the background and automatically
establishes links to Pixhawk 2.4.8 and Arduino Nano 33 IoT (PixDoctorNano).
"""

import time
import threading
from typing import Optional, Callable
import serial.tools.list_ports

from core.mavlink_manager import MavlinkManager
from core.nano_probe_manager import NanoProbeManager


class AutoDetector:
    """Background auto-scan thread for Pixhawk and Nano 33 IoT probe."""

    def __init__(
        self,
        mav_mgr: MavlinkManager,
        nano_mgr: NanoProbeManager,
        status_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.mav_mgr = mav_mgr
        self.nano_mgr = nano_mgr
        self.status_callback = status_callback
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

        self._pixhawk_connected_port: Optional[str] = None
        self._nano_connected_port: Optional[str] = None

    def start(self):
        """Start auto-detection worker loop."""
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._scan_loop, daemon=True, name="AutoDetectorWorker")
            self._thread.start()

    def stop(self):
        """Stop auto-detection worker loop."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

    def _notify(self, msg: str, level: str = "INFO"):
        if self.status_callback:
            self.status_callback(msg, level)

    def _probe_ping_check(self, port_str: str) -> bool:
        """Quick 200ms ping to determine if an ambiguous USB port is running PixDoctor probe firmware."""
        try:
            import serial
            with serial.Serial(port_str, 115200, timeout=0.25, write_timeout=0.25) as s:
                s.write(b"PING\n")
                time.sleep(0.05)
                res = s.read(256).decode("utf-8", errors="ignore")
                if any(k in res for k in ("PROBE", "PONG", "PixDoctor", "pwm")):
                    return True
        except Exception:
            pass
        return False

    def _scan_loop(self):
        """Periodic scan every 2 seconds to detect and connect devices."""
        time.sleep(0.5)

        while self.running:
            try:
                ports = serial.tools.list_ports.comports()
                pixhawk_candidate = None
                probe_candidate = None
                ambiguous_ports = []

                for p in ports:
                    desc_upper = (p.description or "").upper()
                    hwid_upper = (p.hwid or "").upper()
                    dev = p.device
                    vid = p.vid
                    pid = p.pid

                    # Skip standard Bluetooth serial ports
                    if "BTHENUM" in hwid_upper or "BLUETOOTH" in desc_upper:
                        continue

                    # Skip ports already connected
                    if self.mav_mgr.is_connected() and dev == self._pixhawk_connected_port:
                        continue
                    if self.nano_mgr.state.connected and dev == self._nano_connected_port:
                        continue

                    # 1. Definitive Probe: Nano 33 IoT (2341:8057), Espressif Native (303A), or keyword
                    if (vid == 0x2341 and pid == 0x8057) or vid == 0x303A:
                        probe_candidate = dev
                        continue
                    elif any(tag in desc_upper for tag in ("NANO 33", "SAMD21", "ARDUINO NANO", "PIXDOCTOR", "ESP32", "ESPRESSIF")):
                        probe_candidate = dev
                        continue

                    # 2. Definitive Pixhawk: STM32 FMUv2 (0483:5740), 3DR PX4 (26AC:0011), or keywords
                    if (vid == 0x0483 and pid == 0x5740) or (vid == 0x26AC and pid == 0x0011):
                        pixhawk_candidate = dev
                        continue
                    elif any(tag in desc_upper for tag in ("PIXHAWK", "PX4", "ARDUPILOT", "STM32", "PROFICNC", "HEX")):
                        pixhawk_candidate = dev
                        continue

                    # 3. Ambiguous USB-to-UART bridges (CP210x, CH340, FTDI, generic USB Serial)
                    if (vid == 0x10C4 and pid == 0xEA60) or (vid == 0x1A86 and pid == 0x7523) or (vid == 0x0403 and pid == 0x6001):
                        ambiguous_ports.append(dev)
                    elif any(tag in desc_upper for tag in ("CP210", "SILICON LABS", "CH340", "FTDI", "USB SERIAL", "USB-SERIAL")):
                        ambiguous_ports.append(dev)
                    elif hwid_upper.startswith("USB"):
                        ambiguous_ports.append(dev)

                # Resolve ambiguous ports if needed
                for amb_dev in ambiguous_ports:
                    if amb_dev == pixhawk_candidate or amb_dev == probe_candidate:
                        continue

                    # If probe is not connected and we don't have a definitive probe candidate, test with fast ping
                    if not self.nano_mgr.state.connected and not probe_candidate:
                        if self._probe_ping_check(amb_dev):
                            probe_candidate = amb_dev
                            continue

                    # If Pixhawk is not connected and we don't have a candidate, assign
                    if not self.mav_mgr.is_connected() and not pixhawk_candidate:
                        pixhawk_candidate = amb_dev
                    elif not self.nano_mgr.state.connected and not probe_candidate:
                        probe_candidate = amb_dev

                # Auto-connect Pixhawk if disconnected
                if not self.mav_mgr.is_connected() and pixhawk_candidate and not self.mav_mgr.state.is_sim:
                    self._notify(f"[Auto-Detect] Detected Pixhawk candidate on {pixhawk_candidate}. Connecting...", "INFO")
                    success = self.mav_mgr.connect(pixhawk_candidate, baudrate=115200)
                    if not success:
                        # Fallback to TELEM baudrate 57600
                        success = self.mav_mgr.connect(pixhawk_candidate, baudrate=57600)

                    if success:
                        self._pixhawk_connected_port = pixhawk_candidate
                        self._notify(f"[Auto-Detect] Pixhawk connected on {pixhawk_candidate}", "INFO")

                # Auto-connect Probe (ESP32 or Nano) if disconnected
                if not self.nano_mgr.state.connected and probe_candidate:
                    self._notify(f"[Auto-Detect] Detected hardware probe on {probe_candidate}. Connecting...", "INFO")
                    success = self.nano_mgr.connect(probe_candidate, baudrate=115200)
                    if success:
                        self._nano_connected_port = probe_candidate
                        self._notify(f"[Auto-Detect] Hardware probe connected on {probe_candidate}", "INFO")

            except Exception as e:
                pass

            time.sleep(2.0)
