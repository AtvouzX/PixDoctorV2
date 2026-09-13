"""
PixDoctorV2 - Comprehensive Automated Component Verification Test.
Tests core definitions, parameter manager, Nano probe protocol,
XInput gamepad engine, and Tkinter GUI loading.
"""

import os
import sys
import time
import json
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ardusub_defs import FRAMES, DEFAULT_FRAME_ID, FLIGHT_MODES, KEY_PARAMETERS
from core.param_manager import ParameterManager
from core.nano_probe_manager import NanoProbeManager
from core.gamepad_manager import GamepadManager
from core.mavlink_manager import MavlinkManager


class TestPixDoctorV2Core(unittest.TestCase):

    def test_frames_definition(self):
        """Verify SimpleROV-4 is the default frame and all frames are defined."""
        self.assertEqual(DEFAULT_FRAME_ID, 6)
        self.assertIn(6, FRAMES)
        simplerov4 = FRAMES[6]
        self.assertEqual(simplerov4["code"], "SimpleROV_4")
        self.assertEqual(len(simplerov4["thrusters"]), 4)

        # Verify all frames are present
        for fid in (1, 2, 3, 4, 5, 6, 7, 8):
            self.assertIn(fid, FRAMES)

    def test_flight_modes(self):
        """Verify essential ArduSub 4.7.1 flight modes."""
        self.assertIn(19, FLIGHT_MODES)  # MANUAL
        self.assertIn(0, FLIGHT_MODES)   # STABILIZE
        self.assertIn(2, FLIGHT_MODES)   # ALT_HOLD (Depth Hold)
        self.assertEqual(FLIGHT_MODES[19]["name"], "MANUAL")
        self.assertEqual(FLIGHT_MODES[2]["name"], "ALT_HOLD")

    def test_param_manager(self):
        """Verify parameter cache, dirty tracking, and export/import."""
        pm = ParameterManager()
        self.assertEqual(pm.get_value("FRAME_CONFIG"), 6.0)

        # Modify parameter
        pm.set_value("MOT_1_DIRECTION", -1.0)
        dirty = pm.get_dirty_params()
        self.assertEqual(len(dirty), 1)
        self.assertEqual(dirty[0].name, "MOT_1_DIRECTION")

        # Export test
        test_file = os.path.join(PROJECT_ROOT, "test_params.param")
        success = pm.export_to_file(test_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(test_file))

        # Import test into clean manager
        pm2 = ParameterManager()
        count = pm2.import_from_file(test_file)
        self.assertGreater(count, 0)
        self.assertEqual(pm2.get_value("MOT_1_DIRECTION"), -1.0)

        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)

    def test_nano_probe_json_parser(self):
        """Verify PixDoctorNano probe protocol decoder."""
        npm = NanoProbeManager()
        # Feed sample probe json packet
        sample_pkt = {
            "type": "PROBE_DATA",
            "t": 12345,
            "pwm": [1520, 1480, 1600, 1500, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "hz": [50.1, 50.0, 50.2, 50.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "valid": [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        }
        npm._process_line(json.dumps(sample_pkt))
        snap = npm.state.get_snapshot()

        self.assertEqual(snap["measured_pwm"][0], 1520)
        self.assertEqual(snap["measured_pwm"][1], 1480)
        self.assertEqual(snap["measured_pwm"][2], 1600)
        self.assertTrue(snap["signal_valid"][0])
        self.assertFalse(snap["signal_valid"][4])

        # Test closed-loop error delta
        npm.set_commanded_pwm(1, 1500)
        snap = npm.state.get_snapshot()
        self.assertEqual(snap["error_delta_us"][0], 20)  # 1520 - 1500 = +20us

    def test_gamepad_manager(self):
        """Verify XInput and WinMM controller manager initialization."""
        gm = GamepadManager()
        snap = gm.state.get_snapshot()
        self.assertIn("axis_lx", snap)
        self.assertIn("btn_a", snap)
        self.assertEqual(snap["gain"], 0.50)

        # Gain change
        gm.set_gain(0.75)
        self.assertEqual(gm.state.gain, 0.75)

    def test_mock_sim_engine(self):
        """Verify offline simulation engine generates packets when activated."""
        received = []
        mm = MavlinkManager()
        mm.connect("MOCK")
        time.sleep(0.3)
        snap = mm.state.get_snapshot()
        self.assertTrue(snap["connected"])
        self.assertTrue(snap["is_sim"])
        self.assertIn("ArduSub", snap["firmware"])
        mm.disconnect()

    def test_motor_test_streamer(self):
        """Verify QGC-style 20Hz continuous motor test streamer."""
        mm = MavlinkManager()
        mm.start_motor_stream(1, 1650)
        self.assertTrue(mm._motor_stream_active)
        self.assertEqual(mm._motor_stream_ch, 1)
        self.assertEqual(mm._motor_stream_pwm, 1650)

        # Update motor stream
        mm.start_motor_stream(2, 1400)
        self.assertEqual(mm._motor_stream_ch, 2)
        self.assertEqual(mm._motor_stream_pwm, 1400)

        # Stop motor stream
        mm.stop_motor_stream()
        self.assertFalse(mm._motor_stream_active)

    def test_gamepad_calibration_and_mapping(self):
        """Verify stick calibration, zero-tare, deadzone, expo, and button remapping."""
        gm = GamepadManager()
        
        # Deadzone test
        # Raw 1000 with 10% deadzone (~3276) should return 0
        norm_zero = gm._normalize_stick_calibrated(raw_val=1000, center_offset=0, invert=False, deadzone_pct=0.10, expo=0.0)
        self.assertEqual(norm_zero, 0)

        # Raw full throw 32767 should scale to 1000
        norm_full = gm._normalize_stick_calibrated(raw_val=32767, center_offset=0, invert=False, deadzone_pct=0.10, expo=0.0)
        self.assertEqual(norm_full, 1000)

        # Inversion test
        norm_inv = gm._normalize_stick_calibrated(raw_val=32767, center_offset=0, invert=True, deadzone_pct=0.10, expo=0.0)
        self.assertEqual(norm_inv, -1000)

        # Center zero-tare test: simulated stick drift of +5000
        gm.state.raw_lx = 5000
        gm.calibrate_centers()
        self.assertEqual(gm.state.center_offset_lx, 5000)
        # Now raw 5000 minus offset 5000 should be 0
        norm_tared = gm._normalize_stick_calibrated(raw_val=5000, center_offset=gm.state.center_offset_lx, invert=False, deadzone_pct=0.10, expo=0.0)
        self.assertEqual(norm_tared, 0)

        # Button mapping test
        gm.set_button_mapping("btn_a", "CAMERA_TILT_UP")
        self.assertEqual(gm.state.button_mappings["btn_a"], "CAMERA_TILT_UP")
        
        gm.reset_mappings_to_default()
        self.assertEqual(gm.state.button_mappings["btn_a"], "DISARM")


if __name__ == "__main__":
    unittest.main()

