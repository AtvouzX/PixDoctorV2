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

    def _scan_loop(self):
        """Periodic scan every 2 seconds to detect and connect devices."""
        time.sleep(0.5)

        while self.running:
            try:
                ports = serial.tools.list_ports.comports()
                pixhawk_candidate = None
                nano_candidate = None

                for p in ports:
                    desc_upper = (p.description or "").upper()
                    hwid_upper = (p.hwid or "").upper()
                    dev = p.device
                    vid = p.vid
                    pid = p.pid

                    # Skip standard Bluetooth serial ports from auto-connecting as Pixhawk
                    if "BTHENUM" in hwid_upper or "BLUETOOTH" in desc_upper:
                        continue

                    # 1. Identify Probe: Arduino Nano 33 IoT (PixDoctorNano) or ESP32 (PixDoctorESP32)
                    is_probe = False
                    if vid == 0x2341 and pid == 0x8057:
                        is_probe = True
                    elif "2341" in hwid_upper and "8057" in hwid_upper:
                        is_probe = True
                    elif any(tag in desc_upper for tag in ("NANO 33", "SAMD21", "ARDUINO NANO", "PIXDOCTOR", "ESP32")):
                        is_probe = True

                    if is_probe:
                        nano_candidate = dev
                        continue

                    # 2. Identify Pixhawk 2.4.8 (FMUv2 / STM32 / USB-TTL)
                    is_pixhawk = False
                    # Standard Pixhawk / PX4 USB VID/PIDs
                    if (vid == 0x0483 and pid == 0x5740) or (vid == 0x26AC and pid == 0x0011):
                        is_pixhawk = True
                    elif ("0483" in hwid_upper and "5740" in hwid_upper) or ("26AC" in hwid_upper and "0011" in hwid_upper):
                        is_pixhawk = True
                    # Common USB-to-UART telemetry bridges (CP210x, FTDI, CH340, Prolific)
                    elif (vid == 0x10C4 and pid == 0xEA60) or (vid == 0x1A86 and pid == 0x7523) or (vid == 0x0403 and pid == 0x6001):
                        is_pixhawk = True
                    elif any(tag in desc_upper for tag in (
                        "PIXHAWK", "PX4", "ARDUPILOT", "STM32", "CP210", "SILICON LABS",
                        "CH340", "FTDI", "USB SERIAL", "USB-SERIAL", "PROFICNC", "HEX"
                    )):
                        is_pixhawk = True
                    elif hwid_upper.startswith("USB") and not is_nano:
                        # Any physical USB serial device plugged in that is not the Nano
                        is_pixhawk = True

                    if is_pixhawk and not pixhawk_candidate and dev != nano_candidate:
                        pixhawk_candidate = dev

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

                # Auto-connect Arduino Nano 33 IoT probe if disconnected
                if not self.nano_mgr.state.connected and nano_candidate:
                    self._notify(f"[Auto-Detect] Detected PixDoctorNano on {nano_candidate}. Connecting...", "INFO")
                    success = self.nano_mgr.connect(nano_candidate, baudrate=115200)
                    if success:
                        self._nano_connected_port = nano_candidate
                        self._notify(f"[Auto-Detect] PixDoctorNano probe connected on {nano_candidate}", "INFO")

            except Exception as e:
                pass

            time.sleep(2.0)
