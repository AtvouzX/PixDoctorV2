"""
PixDoctorV2 - Flight-control engine tests (ported from eltorpedo).

Covers config loading, stick shaping, claw button pulses, claw STATUSTEXT
parsing and the gamepad-loss failsafe without touching real hardware.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.claw import ClawStatus, config_errors, parse_statustext
from core.rov_config import (
    LinkConfig,
    ControlConfig,
    ClawConfig,
    load_rov_config,
)
from core.rov_control import RovControl, claw_mask, shape_axes


class _SnapshotState:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def get_snapshot(self):
        return dict(self._snapshot)


class FakeMav:
    def __init__(self, connected=True, armed=False):
        self.state = _SnapshotState({"connected": connected, "armed": armed})
        self.sent = []
        self.arms = []
        self.params = []

    def send_manual_control(self, x, y, z, r, buttons=0):
        self.sent.append((x, y, z, r, buttons))

    def arm(self, value):
        self.arms.append(value)
        self.state._snapshot["armed"] = value

    def request_param(self, name):
        self.params.append(name)


class FakeGamepad:
    def __init__(self, connected=True, **axes):
        self.state = _SnapshotState({"connected": connected, **axes})


def _control(mav, pad, enabled=True, disarm_s=1.0):
    return RovControl(
        LinkConfig(gamepad_disarm_s=disarm_s),
        ControlConfig(enabled=enabled),
        ClawConfig(),
        mav,
        pad,
    )


class TestRovConfig(unittest.TestCase):
    def test_missing_file_generates_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.toml")
            cfg = load_rov_config(path)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(cfg.link.endpoint, "udpin:0.0.0.0:14550")
            self.assertFalse(cfg.control.enabled)
            self.assertEqual(cfg.claw.required["GRIP_TYPE"], 3)

    def test_overrides_are_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.toml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "[link]\n"
                    'endpoint = "udpout:10.0.0.2:14550"\n'
                    "control_hz = 30\n"
                    "auto_connect = false\n"
                    "[claw]\n"
                    "press_ms = 250\n"
                    "close_bit = 3\n"
                )
            cfg = load_rov_config(path)
            self.assertEqual(cfg.link.endpoint, "udpout:10.0.0.2:14550")
            self.assertEqual(cfg.link.control_hz, 30.0)
            self.assertFalse(cfg.link.auto_connect)
            self.assertEqual(cfg.claw.press_ms, 250)
            self.assertEqual(cfg.claw.close_bit, 3)


class TestAxisShaping(unittest.TestCase):
    def test_maps_sticks_and_gain(self):
        pad = {
            "axis_ry": 1000,   # forward
            "axis_rx": -1000,  # lateral
            "axis_ly": 500,    # throttle up
            "axis_lx": 0,      # yaw
            "gain": 0.5,
        }
        self.assertEqual(shape_axes(pad, pad["gain"]), (500, -500, 250, 0))

    def test_clamps_and_survives_garbage(self):
        pad = {"axis_ry": 5000, "axis_rx": None, "axis_ly": "bad", "gain": 2.0}
        self.assertEqual(shape_axes(pad), (1000, 0, 0, 0))


class TestClawPulse(unittest.TestCase):
    def test_mask_expires(self):
        pending = {0: 10.0, 2: 20.0}
        self.assertEqual(claw_mask(pending, 9.0), 0b101)
        self.assertEqual(claw_mask(pending, 15.0), 0b100)
        self.assertEqual(claw_mask(pending, 25.0), 0)
        self.assertEqual(pending, {})

    def test_press_requires_link(self):
        mav = FakeMav(connected=False)
        control = _control(mav, FakeGamepad())
        self.assertFalse(control.press_claw("close"))
        self.assertEqual(mav.sent, [])


class FakeJoystick:
    """Minimal SDL joystick: both sticks pushed up, A and D-pad up pressed."""

    def __init__(self, name="Xbox Controller"):
        self._name = name
        self._axes = [0.0, -1.0, 0.0, -1.0, -1.0, -1.0]
        self._buttons = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def get_name(self):
        return self._name

    def get_numaxes(self):
        return len(self._axes)

    def get_axis(self, index):
        return self._axes[index]

    def get_numbuttons(self):
        return len(self._buttons)

    def get_button(self, index):
        return self._buttons[index]

    def get_numhats(self):
        return 1

    def get_hat(self, index):
        return (0, 1)


class TestSdlMapping(unittest.TestCase):
    def test_sdl_up_is_positive_and_buttons_map(self):
        from core.gamepad_manager import GamepadManager

        manager = GamepadManager()
        manager._parse_sdl(FakeJoystick())
        snapshot = manager.state.get_snapshot()
        self.assertTrue(snapshot["connected"])
        self.assertEqual(snapshot["backend"], "SDL (Linux/Gamepad)")
        self.assertGreater(snapshot["axis_ly"], 900)
        self.assertGreater(snapshot["axis_ry"], 900)
        self.assertEqual(snapshot["axis_lx"], 0)
        self.assertTrue(snapshot["btn_a"])
        self.assertTrue(snapshot["dpad_up"])


class TestClawStatus(unittest.TestCase):
    def test_parses_firmware_messages(self):
        status = ClawStatus()
        self.assertTrue(parse_statustext("Claw: closing", status))
        self.assertEqual(status.state, "CLOSING")
        parse_statustext("Claw: object grasped, holding", status)
        self.assertEqual(status.state, "HOLDING")
        parse_statustext("Claw: object grasped", status)
        self.assertEqual(status.state, "GRABBED")
        parse_statustext("Claw: obstacle detected", status)
        self.assertEqual(status.state, "FAULT")
        self.assertTrue(status.fault)
        parse_statustext("Claw: fault - overcurrent while holding", status)
        self.assertEqual(status.state, "FAULT")
        self.assertTrue(status.fault)
        parse_statustext("Claw: INA219 not found", status)
        self.assertEqual(status.state, "UNAVAILABLE")

    def test_ignores_other_messages(self):
        status = ClawStatus()
        self.assertFalse(parse_statustext("EKF3 IMU0 started", status))
        self.assertEqual(status.state, "UNKNOWN")

    def test_config_errors(self):
        required = {"GRIP_ENABLE": 1, "GRIP_TYPE": 3}
        self.assertEqual(config_errors({"GRIP_ENABLE": 1, "GRIP_TYPE": 3}, required), [])
        self.assertEqual(
            config_errors({"GRIP_ENABLE": 1}, required),
            ["GRIP_TYPE not read"],
        )
        self.assertEqual(
            config_errors({"GRIP_ENABLE": 0, "GRIP_TYPE": 3}, required),
            ["GRIP_ENABLE=0, need 1"],
        )


class TestControlLoop(unittest.TestCase):
    def test_disabled_sends_nothing(self):
        mav = FakeMav()
        control = _control(mav, FakeGamepad(axis_ly=500), enabled=False)
        control._step(1.0)
        self.assertEqual(mav.sent, [])

    def test_enabled_streams_sticks(self):
        mav = FakeMav()
        pad = FakeGamepad(axis_ry=400, axis_rx=-200, axis_ly=100, axis_lx=50, gain=1.0)
        control = _control(mav, pad)
        control._step(1.0)
        self.assertEqual(mav.sent, [(400, -200, 100, 50, 0)])

    def test_gamepad_loss_disarms_after_timeout(self):
        mav = FakeMav(armed=True)
        control = _control(mav, FakeGamepad(connected=False), enabled=True, disarm_s=1.0)
        control._step(100.0)
        self.assertEqual(mav.sent[-1], (0, 0, 0, 0, 0))
        self.assertEqual(mav.arms, [])
        control._step(100.5)
        self.assertEqual(mav.arms, [])
        control._step(101.1)
        self.assertEqual(mav.arms, [False])

    def test_claw_pulse_travels_in_button_mask(self):
        import time

        mav = FakeMav()
        control = _control(mav, FakeGamepad(), enabled=False)
        self.assertTrue(control.press_claw("open"))
        now = time.monotonic()
        control._step(now)
        self.assertEqual(mav.sent[-1], (0, 0, 0, 0, 0b10))
        control._step(now + 1.0)
        self.assertEqual(len(mav.sent), 1)


class TestSwitchLink(unittest.TestCase):
    def _script(self):
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "deploy"))
        import switch_link

        return switch_link

    def test_direct_and_back_keep_comments(self):
        switch_link = self._script()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.toml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("# header comment\n\n[link]\n# keep me\n"
                             'endpoint = "udpin:0.0.0.0:14550"\n'
                             "auto_connect = true\ncontrol_hz = 20\n\n[control]\n"
                             "enabled = false\n")

            switch_link.switch(Path(path), "/dev/ttyACM0")
            self.assertEqual(switch_link.read_endpoint(Path(path)), "/dev/ttyACM0")
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("# header comment", text)
            self.assertIn("# keep me", text)
            self.assertNotIn("udpin", text)
            self.assertEqual(load_rov_config(Path(path)).link.endpoint, "/dev/ttyACM0")

            switch_link.switch(Path(path), switch_link.ROUTER_ENDPOINT)
            self.assertEqual(
                switch_link.read_endpoint(Path(path)), "udpin:0.0.0.0:14550"
            )
            self.assertIn("[control]", text)
            self.assertEqual(text.count("[link]"), 1)


if __name__ == "__main__":
    unittest.main()
