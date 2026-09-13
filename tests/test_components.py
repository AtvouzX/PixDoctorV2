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
        """Verify XInput and WinMM controller manager initialization and gain adjustment."""
        gm = GamepadManager()
        snap = gm.state.get_snapshot()
        self.assertIn("axis_lx", snap)
        self.assertIn("btn_a", snap)
        self.assertGreaterEqual(snap["gain"], 0.1)
        self.assertLessEqual(snap["gain"], 1.0)

        # Gain change
        gm.set_gain(0.75)
        self.assertEqual(gm.state.gain, 0.75)
        gm.set_gain(0.50)
        self.assertEqual(gm.state.gain, 0.50)

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

        # Wireless profiles test
        gm.set_wireless_profile("GENERIC_DINPUT")
        self.assertEqual(gm.state.wireless_profile, "GENERIC_DINPUT")
        gm.set_wireless_profile("XBOX_BT")
        self.assertEqual(gm.state.wireless_profile, "XBOX_BT")

    def test_futuristic_hud_flight_telemetry(self):
        """Verify FuturisticHud receives telemetry and activates flight mode on armed+gamepad."""
        import tkinter as tk
        from gui.widgets.futuristic_hud import FuturisticHud

        root = tk.Tk()
        root.withdraw()
        hud = FuturisticHud(root, width=800, height=600)
        
        mav_snap = {
            "roll": 5.0,
            "pitch": -2.5,
            "yaw": 180.0,
            "depth": 1.25,
            "battery_voltage": 16.2,
            "battery_current": 5.4,
            "vcc_voltage": 5.04,
            "pressure_bar": 1.125,
            "temperature": 24.5,
            "armed": True,
            "flight_mode_name": "MANUAL",
            "leak": False,
            "statustext": "Test OK",
        }
        pad_snap = {
            "connected": True,
            "controller_name": "Xbox Controller",
            "gain": 0.50,
            "axis_ry": 800,  # Forward thrust
            "axis_rx": 0,
            "axis_ly": 400,  # Depth thrust
            "axis_lx": -200, # Yaw turn
        }

        hud.update_telemetry(mav_snap, pad_snap)
        self.assertTrue(hud.in_flight)
        self.assertEqual(hud.cmd_fwd, 400) # 800 * 0.5
        self.assertEqual(hud.depth, 1.25)
        self.assertEqual(hud.batt_v, 16.2)

        # Disarm -> should not be in_flight
        mav_snap["armed"] = False
        hud.update_telemetry(mav_snap, pad_snap)
        self.assertFalse(hud.in_flight)

        root.destroy()

    def test_thruster_synchronization_and_mixing(self):
        """Verify frame thruster mixer and zero-latency HUD animation synchronization."""
        from core.ardusub_defs import compute_thruster_pwms
        import tkinter as tk
        from gui.widgets.futuristic_hud import FuturisticHud

        # 1. SimpleROV-4 Mixer: Forward command -> M1 & M2 active, M3 & M4 neutral
        pwms_fwd = compute_thruster_pwms(frame_id=6, fwd=800, lat=0, depth=0, yaw=0, armed=True)
        self.assertGreater(pwms_fwd[0], 1700) # M1 Port Horiz
        self.assertGreater(pwms_fwd[1], 1700) # M2 Stbd Horiz
        self.assertEqual(pwms_fwd[2], 1500)   # M3 Vert Left
        self.assertEqual(pwms_fwd[3], 1500)   # M4 Vert Right

        # 2. SimpleROV-4 Mixer: Depth command -> M3 & M4 active, M1 & M2 neutral
        pwms_depth = compute_thruster_pwms(frame_id=6, fwd=0, lat=0, depth=600, yaw=0, armed=True)
        self.assertEqual(pwms_depth[0], 1500)
        self.assertEqual(pwms_depth[1], 1500)
        self.assertGreater(pwms_depth[2], 1700)
        self.assertGreater(pwms_depth[3], 1700)

        # 3. SimpleROV-4 Mixer: Disarmed -> All 1500
        pwms_disarmed = compute_thruster_pwms(frame_id=6, fwd=1000, lat=1000, depth=1000, yaw=1000, armed=False)
        self.assertEqual(pwms_disarmed, [1500] * 8)

        # 4. FuturisticHud Synchronous Activation with Gamepad
        root = tk.Tk()
        root.withdraw()
        hud = FuturisticHud(root, width=800, height=600)
        hud.set_frame_id(6)

        mav = {"armed": True, "roll": 0.0, "pitch": 0.0, "yaw": 0.0, "depth": 1.0}
        # Pilot commands Forward thrust
        pad = {"connected": True, "gain": 1.0, "axis_ry": 800, "axis_rx": 0, "axis_ly": 0, "axis_lx": 0}
        hud.update_telemetry(mav, pad)

        self.assertTrue(hud.in_flight)
        # M1 & M2 must be actively commanded (>1520), M3 & M4 must be idle (1500)
        self.assertGreater(hud.motor_cmd_pwm[0], 1700)
        self.assertGreater(hud.motor_cmd_pwm[1], 1700)
        self.assertEqual(hud.motor_cmd_pwm[2], 1500)
        self.assertEqual(hud.motor_cmd_pwm[3], 1500)

        # Pilot commands Depth Ascend
        pad_depth = {"connected": True, "gain": 1.0, "axis_ry": 0, "axis_rx": 0, "axis_ly": 700, "axis_lx": 0}
        hud.update_telemetry(mav, pad_depth)

        self.assertTrue(hud.in_flight)
        self.assertEqual(hud.motor_cmd_pwm[0], 1500)
        self.assertEqual(hud.motor_cmd_pwm[1], 1500)
        self.assertGreater(hud.motor_cmd_pwm[2], 1700)
        self.assertGreater(hud.motor_cmd_pwm[3], 1700)

        # Sticks released -> Instant return to neutral
        pad_idle = {"connected": True, "gain": 1.0, "axis_ry": 0, "axis_rx": 0, "axis_ly": 0, "axis_lx": 0}
        hud.update_telemetry(mav, pad_idle)
        self.assertFalse(hud.in_flight)
        self.assertEqual(hud.motor_cmd_pwm[:4], [1500, 1500, 1500, 1500])

        root.destroy()

    def test_motor_matrix_manager_and_dialog(self):
        """Verify MotorMatrixManager, stick mode swapping, direction parity, and dialog."""
        from core.motor_matrix_manager import MotorMatrixManager
        from gui.widgets.motor_matrix_dialog import MotorMatrixDialog
        import tkinter as tk

        mm = MotorMatrixManager.get_instance()
        # Reset to SimpleROV-4 standard
        mm.apply_preset("SimpleROV-4", notify=False)
        self.assertEqual(mm.motor_directions[3], 1)

        # 1. Forward motion test
        pwms = mm.compute_motor_pwms(fwd=800, lat=0, depth=0, yaw=0, armed=True)
        self.assertGreater(pwms[0], 1700)
        self.assertGreater(pwms[1], 1700)
        self.assertEqual(pwms[2], 1500)

        # 2. Inverted M3/M4 test (probe parity)
        # When MOT_3_DIRECTION is -1, input +800 depth produces 1180 (not 1820)
        mm.set_motor_direction(3, -1, notify=False)
        self.assertEqual(mm.motor_directions[3], -1)
        pwms_inv = mm.compute_motor_pwms(fwd=0, lat=0, depth=800, yaw=0, armed=True)
        self.assertLess(pwms_inv[2], 1300) # Inverted around 1500 -> ~1180us
        self.assertGreater(pwms_inv[3], 1700) # M4 still normal

        # 3. Stick mode turning swap test
        mm.set_stick_mode("STANDARD_ROV", notify=False)
        self.assertEqual(mm.axis_mappings["yaw"], "axis_lx") # Turn on Left Stick
        # In Standard mode: right stick horizontal does not produce yaw
        cmds = mm.extract_gamepad_commands({"connected": True, "gain": 1.0, "axis_rx": 600, "axis_lx": 0})
        self.assertEqual(cmds["yaw"], 0)
        self.assertEqual(cmds["lat"], 600)

        # Swap to FPS/Car mode (Turn on Right Stick X)
        mm.swap_turning_stick()
        self.assertEqual(mm.axis_mappings["yaw"], "axis_rx")
        cmds2 = mm.extract_gamepad_commands({"connected": True, "gain": 1.0, "axis_rx": 600, "axis_lx": 0})
        self.assertEqual(cmds2["yaw"], 600) # Right stick now produces yaw!

        # Reset back
        mm.apply_preset("SimpleROV-4", notify=False)
        mm.set_stick_mode("STANDARD_ROV", notify=False)

        # 4. Headless MotorMatrixDialog build
        root = tk.Tk()
        root.withdraw()
        dlg = MotorMatrixDialog(root)
        dlg.update()
        dlg.destroy()
        root.destroy()

    def test_yaw_differential_inversion_preserves_forward(self):
        """Verifies that inverting yaw differential flips yaw PWMs while forward thrust is 100% identical."""
        from core.motor_matrix_manager import MotorMatrixManager
        mm = MotorMatrixManager.get_instance()

        # Apply standard SimpleROV-4
        mm.apply_preset("SimpleROV-4", notify=False)
        pwms_fwd_std = mm.compute_motor_pwms(fwd=800, lat=0, depth=0, yaw=0, armed=True)
        # M1 and M2 both push forward (1820)
        self.assertGreater(pwms_fwd_std[0], 1700)
        self.assertGreater(pwms_fwd_std[1], 1700)

        # Standard yaw turning: positive yaw commands M1 > 1500, M2 < 1500
        pwms_yaw_std = mm.compute_motor_pwms(fwd=0, lat=0, depth=0, yaw=800, armed=True)
        self.assertGreater(pwms_yaw_std[0], 1500)
        self.assertLess(pwms_yaw_std[1], 1500)

        # Invert Yaw Differential
        mm.invert_yaw_differential(notify=False)

        # 1. Forward thrust MUST remain completely identical!
        pwms_fwd_inv = mm.compute_motor_pwms(fwd=800, lat=0, depth=0, yaw=0, armed=True)
        self.assertEqual(pwms_fwd_std[0], pwms_fwd_inv[0])
        self.assertEqual(pwms_fwd_std[1], pwms_fwd_inv[1])

        # 2. Yaw turning is now inverted: M1 < 1500, M2 > 1500
        pwms_yaw_inv = mm.compute_motor_pwms(fwd=0, lat=0, depth=0, yaw=800, armed=True)
        self.assertLess(pwms_yaw_inv[0], 1500)
        self.assertGreater(pwms_yaw_inv[1], 1500)

        # Reset back
        mm.apply_preset("SimpleROV-4", notify=False)

    def test_hud_lateral_capability_detection(self):
        """Verifies that FuturisticHud suppresses lateral strafe for frames without lateral thrusters."""
        import tkinter as tk
        from gui.widgets.futuristic_hud import FuturisticHud
        root = tk.Tk()
        root.withdraw()
        hud = FuturisticHud(root)

        # SimpleROV-4 has no lateral thrusters
        hud.frame_id = 6
        self.assertFalse(hud._has_lateral_capability())

        # BlueROV2 Vectored-6 has lateral thrusters
        hud.frame_id = 2
        self.assertTrue(hud._has_lateral_capability())

        hud.destroy()
        root.destroy()


if __name__ == "__main__":
    unittest.main()

