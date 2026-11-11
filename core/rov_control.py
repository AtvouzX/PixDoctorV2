"""
PixDoctorV2 - 20 Hz MAVLink flight-control engine.

Ported from eltorpedo. Streams MANUAL_CONTROL while FLY is enabled, carries
claw button pulses, refreshes grip parameters, and owns the failsafes:
neutral axes on gamepad loss, disarm 1 s later, neutral + disarm on exit.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from core.rov_config import ClawConfig, ControlConfig, LinkConfig

AXIS_LIMIT = 1000


def shape_axes(pad: dict, gain: float = 1.0) -> tuple[int, int, int, int]:
    """Return MANUAL_CONTROL (x, y, z, r) from a GamepadManager snapshot.

    x = forward, y = lateral, z = throttle (neutral 0, scaled to 0..1000 by
    MavlinkManager), r = yaw. gain comes from the active gamepad profile.
    """
    def axis(name: str) -> int:
        try:
            value = float(pad.get(name, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        scaled = int(round(value * max(0.0, min(1.0, float(gain)))))
        return max(-AXIS_LIMIT, min(AXIS_LIMIT, scaled))

    return (
        axis("axis_ry"),
        axis("axis_rx"),
        axis("axis_ly"),
        axis("axis_lx"),
    )


def claw_mask(pending: dict[int, float], now: float) -> int:
    """Build the MANUAL_CONTROL button mask and expire finished presses."""
    mask = 0
    for bit, expiry in list(pending.items()):
        if expiry <= now:
            del pending[bit]
        else:
            mask |= 1 << bit
    return mask


class RovControl:
    """Background flight-control loop shared by the GUI and tests."""

    def __init__(
        self,
        link: LinkConfig,
        control: ControlConfig,
        claw: ClawConfig,
        mav_mgr,
        gamepad_mgr,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.link = link
        self.claw = claw
        self.mav_mgr = mav_mgr
        self.gamepad_mgr = gamepad_mgr
        self.log_callback = log_callback

        self._lock = threading.Lock()
        self._enabled = bool(control.enabled)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pending_claw: dict[int, float] = {}
        self._neutral_until = 0.0
        self._gamepad_lost_since: Optional[float] = None
        self._gamepad_disarmed = False
        self._next_param_refresh = 0.0

    # ------------------------------------------------------------- public
    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="RovControlLoop"
        )
        self._thread.start()

    def stop(self, safe: bool = True) -> None:
        """Stop the loop; optionally send neutral axes and disarm first."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

        if not safe:
            return
        snapshot = self.mav_mgr.state.get_snapshot()
        if not snapshot["connected"]:
            return
        for _ in range(3):
            self.mav_mgr.send_manual_control(0, 0, 0, 0, 0)
            time.sleep(0.05)
        if snapshot["armed"]:
            self.mav_mgr.arm(False)
            self._log("Disarm requested (control exit)", "WARN")
            time.sleep(0.25)

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            was = self._enabled
            self._enabled = bool(enabled)
            if was and not enabled:
                # Keep neutral MANUAL_CONTROL flowing briefly so the vehicle
                # does not hold the last stick input.
                self._neutral_until = time.monotonic() + 0.5
        if enabled and not was:
            self._log("FLY control ON", "INFO")
        elif was and not enabled:
            self._log("FLY control OFF: axes neutral", "WARN")

    def press_claw(self, action: str) -> bool:
        """Queue a claw close/open/stop pulse for the next MANUAL_CONTROL."""
        bits = {
            "close": self.claw.close_bit,
            "open": self.claw.open_bit,
            "stop": self.claw.stop_bit,
        }
        if action not in bits:
            return False
        if not self.mav_mgr.state.get_snapshot()["connected"]:
            self._log("Claw: no link", "WARN")
            return False
        with self._lock:
            self._pending_claw[bits[action]] = (
                time.monotonic() + max(10, self.claw.press_ms) / 1000.0
            )
        return True

    # ------------------------------------------------------------ internal
    def _log(self, text: str, level: str = "INFO") -> None:
        if self.log_callback:
            try:
                self.log_callback(text, level)
            except Exception:
                pass

    def _run(self) -> None:
        period = 1.0 / max(1.0, self.link.control_hz)
        while self._running:
            started = time.monotonic()
            try:
                self._step(started)
            except Exception as exc:  # keep the stream alive
                self._log(f"Control loop error: {exc}", "ERROR")
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, period - elapsed))

    def _step(self, now: float) -> None:
        snapshot = self.mav_mgr.state.get_snapshot()
        if not snapshot["connected"]:
            self._gamepad_lost_since = None
            self._gamepad_disarmed = False
            with self._lock:
                self._neutral_until = 0.0
            return

        pad = self.gamepad_mgr.state.get_snapshot()
        pad_fresh = bool(pad["connected"]) and (
            not pad.get("last_update_time")
            or time.time() - pad["last_update_time"] <= self.link.gamepad_timeout_s
        )
        with self._lock:
            enabled = self._enabled
            neutral_window = now < self._neutral_until
            buttons = claw_mask(self._pending_claw, now)

        axes = (0, 0, 0, 0)
        if enabled:
            if pad_fresh:
                if self._gamepad_lost_since is not None:
                    self._log("Gamepad reconnected", "INFO")
                    self._gamepad_lost_since = None
                    self._gamepad_disarmed = False
                axes = shape_axes(pad, pad.get("gain", 1.0))
            else:
                if self._gamepad_lost_since is None:
                    self._gamepad_lost_since = now
                    self._log("Gamepad lost: axes neutral", "WARN")
                elif (
                    snapshot["armed"]
                    and not self._gamepad_disarmed
                    and now - self._gamepad_lost_since >= self.link.gamepad_disarm_s
                ):
                    self.mav_mgr.arm(False)
                    self._gamepad_disarmed = True
                    self._log("Disarm requested (gamepad lost)", "WARN")

        if not (enabled or neutral_window or buttons):
            self._refresh_params(now)
            return

        self.mav_mgr.send_manual_control(*axes, buttons)
        self._refresh_params(now)

    def _refresh_params(self, now: float) -> None:
        """Ask for grip status and missing claw params twice per second."""
        if not (self.claw.enabled and now >= self._next_param_refresh):
            return
        self._next_param_refresh = now + 2.0
        try:
            self.mav_mgr.request_param("GRIP_DC_CURR")
            for name in self.claw.required:
                self.mav_mgr.request_param(name)
        except Exception:
            pass
