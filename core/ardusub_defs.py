"""
PixDoctorV2 - ArduSub 4.7.1 & Pixhawk 2.4.8 System Definitions
Comprehensive definitions for vehicle frames (SimpleROV-4 default),
flight modes, thruster channels, MAVLink commands, and failsafes.
"""

from typing import Dict, Any, List

# Vehicle Frame Configurations for ArduSub
# ArduSub uses parameter FRAME_CONFIG
FRAMES = {
    6: {
        "id": 6,
        "code": "SimpleROV_4",
        "name": "SimpleROV-4 (4-Thruster)",
        "description": "2 Horizontal (Port/Starboard) + 2 Vertical Thrusters. Optimal for compact inspection ROVs.",
        "thruster_count": 4,
        "thrusters": [
            {"num": 1, "name": "Port Horizontal", "role": "Horizontal Thrust (Left)", "color": "#ffffff", "pos": (-0.7, -0.4), "angle": 0},
            {"num": 2, "name": "Starboard Horizontal", "role": "Horizontal Thrust (Right)", "color": "#ffffff", "pos": (0.7, -0.4), "angle": 0},
            {"num": 3, "name": "Vertical Front/Left", "role": "Vertical Depth (Front/1)", "color": "#ffffff", "pos": (-0.4, 0.4), "angle": 90},
            {"num": 4, "name": "Vertical Back/Right", "role": "Vertical Depth (Back/2)", "color": "#ffffff", "pos": (0.4, 0.4), "angle": 90},
        ]
    },
    5: {
        "id": 5,
        "code": "SimpleROV_3",
        "name": "SimpleROV-3 (3-Thruster)",
        "description": "2 Horizontal (Port/Starboard) + 1 Central Vertical Thruster.",
        "thruster_count": 3,
        "thrusters": [
            {"num": 1, "name": "Port Horizontal", "role": "Horizontal Thrust (Left)", "color": "#ffffff", "pos": (-0.7, -0.4), "angle": 0},
            {"num": 2, "name": "Starboard Horizontal", "role": "Horizontal Thrust (Right)", "color": "#ffffff", "pos": (0.7, -0.4), "angle": 0},
            {"num": 3, "name": "Center Vertical", "role": "Vertical Depth Control", "color": "#ffffff", "pos": (0.0, 0.0), "angle": 90},
        ]
    },
    2: {
        "id": 2,
        "code": "Vectored_6",
        "name": "BlueROV2 Vectored (6-Thruster)",
        "description": "4 Vectored Horizontal (45 deg) + 2 Vertical Thrusters for full 6-DOF maneuverability.",
        "thruster_count": 6,
        "thrusters": [
            {"num": 1, "name": "Forward Port", "role": "Vectored Forward Left", "color": "#ffffff", "pos": (-0.6, 0.5), "angle": 45},
            {"num": 2, "name": "Forward Starboard", "role": "Vectored Forward Right", "color": "#ffffff", "pos": (0.6, 0.5), "angle": -45},
            {"num": 3, "name": "Aft Port", "role": "Vectored Aft Left", "color": "#ffffff", "pos": (-0.6, -0.5), "angle": -45},
            {"num": 4, "name": "Aft Starboard", "role": "Vectored Aft Right", "color": "#ffffff", "pos": (0.6, -0.5), "angle": 45},
            {"num": 5, "name": "Vertical Port", "role": "Vertical Left", "color": "#ffffff", "pos": (-0.4, 0.0), "angle": 90},
            {"num": 6, "name": "Vertical Starboard", "role": "Vertical Right", "color": "#ffffff", "pos": (0.4, 0.0), "angle": 90},
        ]
    },
    3: {
        "id": 3,
        "code": "Vectored_6DOF",
        "name": "BlueROV2 Heavy (8-Thruster)",
        "description": "4 Vectored Horizontal + 4 Vertical Thrusters with pitch & roll authority.",
        "thruster_count": 8,
        "thrusters": [
            {"num": 1, "name": "Forward Port", "role": "Vectored Fwd Left", "color": "#ffffff", "pos": (-0.6, 0.6), "angle": 45},
            {"num": 2, "name": "Forward Starboard", "role": "Vectored Fwd Right", "color": "#ffffff", "pos": (0.6, 0.6), "angle": -45},
            {"num": 3, "name": "Aft Port", "role": "Vectored Aft Left", "color": "#ffffff", "pos": (-0.6, -0.6), "angle": -45},
            {"num": 4, "name": "Aft Starboard", "role": "Vectored Aft Right", "color": "#ffffff", "pos": (0.6, -0.6), "angle": 45},
            {"num": 5, "name": "Vert Fwd Port", "role": "Vertical Fwd Left", "color": "#ffffff", "pos": (-0.4, 0.3), "angle": 90},
            {"num": 6, "name": "Vert Fwd Starboard", "role": "Vertical Fwd Right", "color": "#ffffff", "pos": (0.4, 0.3), "angle": 90},
            {"num": 7, "name": "Vert Aft Port", "role": "Vertical Aft Left", "color": "#ffffff", "pos": (-0.4, -0.3), "angle": 90},
            {"num": 8, "name": "Vert Aft Starboard", "role": "Vertical Aft Right", "color": "#ffffff", "pos": (0.4, -0.3), "angle": 90},
        ]
    },
    1: {
        "id": 1,
        "code": "BlueROV1",
        "name": "BlueROV1 (6-Thruster)",
        "description": "Original BlueROV1 layout with dual vertical and quad horizontal.",
        "thruster_count": 6,
        "thrusters": []
    },
    4: {
        "id": 4,
        "code": "Vectored_90",
        "name": "Vectored-90 Frame",
        "description": "Vectored horizontal thrusters mounted at 90-degree orthogonal angles.",
        "thruster_count": 6,
        "thrusters": []
    },
    8: {
        "id": 8,
        "code": "Vectored_6DOF_90",
        "name": "Vectored-6DOF-90 Frame",
        "description": "8-Thruster Heavy configuration with 90-degree orthogonal vector angles.",
        "thruster_count": 8,
        "thrusters": []
    },
    7: {
        "id": 7,
        "code": "Custom",
        "name": "Custom User Frame",
        "description": "Custom thruster allocation matrix configured via custom motor parameters.",
        "thruster_count": 8,
        "thrusters": []
    }
}

DEFAULT_FRAME_ID = 6  # SimpleROV-4 is the user's primary vehicle

# ArduSub 4.7.1 Flight Modes
# Mode numbers according to ArduSub custom_mode enumeration
FLIGHT_MODES: Dict[int, Dict[str, Any]] = {
    19: {
        "name": "MANUAL",
        "desc": "Direct thruster control without auto-level stabilization. Full pilot authority.",
        "color": "#ffffff",
        "badge": "[MANUAL]"
    },
    0: {
        "name": "STABILIZE",
        "desc": "Angular rate and attitude stabilization. Automatically levels pitch and roll when sticks released.",
        "color": "#ffffff",
        "badge": "[STABILIZE]"
    },
    2: {
        "name": "ALT_HOLD",
        "desc": "Depth Hold mode using MS5837 / Bar30 pressure sensor. Holds current water depth automatically.",
        "color": "#ffffff",
        "badge": "[DEPTH_HOLD]"
    },
    1: {
        "name": "ACRO",
        "desc": "Rate-based acrobatic mode. High agility with angular rate feedback.",
        "color": "#ffffff",
        "badge": "[ACRO]"
    },
    16: {
        "name": "POSHOLD",
        "desc": "Position hold mode using DVL or underwater acoustic positioning system (USBL).",
        "color": "#ffffff",
        "badge": "[POSHOLD]"
    },
    21: {
        "name": "SURFTRAK",
        "desc": "Surface tracking mode using downward looking altimeter or sonar ping.",
        "color": "#ffffff",
        "badge": "[SURFTRAK]"
    },
    3: {
        "name": "AUTO",
        "desc": "Executes pre-programmed mission waypoint script.",
        "color": "#ffffff",
        "badge": "[AUTO]"
    },
    4: {
        "name": "GUIDED",
        "desc": "Follows dynamically commanded targets from GCS / Companion computer.",
        "color": "#ffffff",
        "badge": "[GUIDED]"
    },
    9: {
        "name": "SURFACE",
        "desc": "Emergency autonomous surface ascent mode.",
        "color": "#ffffff",
        "badge": "[SURFACE]"
    }
}

# Arduino Nano 33 IoT (PixDoctorNano) Probe Physical Pin Assignments
NANO_PROBE_PINS: List[Dict[str, Any]] = [
    {"ch": 1,  "pin": "D2",  "pixhawk": "MAIN 1", "role": "Thruster 1 (Port Horiz)"},
    {"ch": 2,  "pin": "D3",  "pixhawk": "MAIN 2", "role": "Thruster 2 (Stbd Horiz)"},
    {"ch": 3,  "pin": "D4",  "pixhawk": "MAIN 3", "role": "Thruster 3 (Vert 1)"},
    {"ch": 4,  "pin": "D5",  "pixhawk": "MAIN 4", "role": "Thruster 4 (Vert 2)"},
    {"ch": 5,  "pin": "D6",  "pixhawk": "MAIN 5", "role": "Thruster 5 / Aux"},
    {"ch": 6,  "pin": "D7",  "pixhawk": "MAIN 6", "role": "Thruster 6 / Aux"},
    {"ch": 7,  "pin": "D8",  "pixhawk": "MAIN 7", "role": "Thruster 7 / Aux"},
    {"ch": 8,  "pin": "D9",  "pixhawk": "MAIN 8", "role": "Thruster 8 / Aux"},
    {"ch": 9,  "pin": "D10", "pixhawk": "AUX 1",  "role": "Aux 1 / Relay 1"},
    {"ch": 10, "pin": "D11", "pixhawk": "AUX 2",  "role": "Aux 2 / Camera Tilt"},
    {"ch": 11, "pin": "D12", "pixhawk": "AUX 3",  "role": "Aux 3 / Lumen Lights 1"},
    {"ch": 12, "pin": "A0",  "pixhawk": "AUX 4",  "role": "Aux 4 / Lumen Lights 2"},
    {"ch": 13, "pin": "A1",  "pixhawk": "AUX 5",  "role": "Aux 5 / Gripper"},
    {"ch": 14, "pin": "A2",  "pixhawk": "AUX 6",  "role": "Aux 6 / General PWM"},
]

# ESP32 DevKit V1 (PixDoctorESP32) Probe Physical Pin Assignments
ESP32_PROBE_PINS: List[Dict[str, Any]] = [
    {"ch": 1,  "pin": "GPIO 13", "pixhawk": "MAIN 1", "role": "Thruster 1 (Port Horiz)"},
    {"ch": 2,  "pin": "GPIO 14", "pixhawk": "MAIN 2", "role": "Thruster 2 (Stbd Horiz)"},
    {"ch": 3,  "pin": "GPIO 27", "pixhawk": "MAIN 3", "role": "Thruster 3 (Vert 1)"},
    {"ch": 4,  "pin": "GPIO 26", "pixhawk": "MAIN 4", "role": "Thruster 4 (Vert 2)"},
    {"ch": 5,  "pin": "GPIO 25", "pixhawk": "MAIN 5", "role": "Thruster 5 / Aux"},
    {"ch": 6,  "pin": "GPIO 33", "pixhawk": "MAIN 6", "role": "Thruster 6 / Aux"},
    {"ch": 7,  "pin": "GPIO 32", "pixhawk": "MAIN 7", "role": "Thruster 7 / Aux"},
    {"ch": 8,  "pin": "GPIO 23", "pixhawk": "MAIN 8", "role": "Thruster 8 / Aux"},
    {"ch": 9,  "pin": "GPIO 22", "pixhawk": "AUX 1",  "role": "Aux 1 / Relay 1"},
    {"ch": 10, "pin": "GPIO 21", "pixhawk": "AUX 2",  "role": "Aux 2 / Camera Tilt"},
    {"ch": 11, "pin": "GPIO 19", "pixhawk": "AUX 3",  "role": "Aux 3 / Lumen Lights 1"},
    {"ch": 12, "pin": "GPIO 18", "pixhawk": "AUX 4",  "role": "Aux 4 / Lumen Lights 2"},
    {"ch": 13, "pin": "GPIO 17", "pixhawk": "AUX 5",  "role": "Aux 5 / Gripper"},
    {"ch": 14, "pin": "GPIO 16", "pixhawk": "AUX 6",  "role": "Aux 6 / General PWM"},
]

# Pixhawk 2.4.8 Leak Detector Pin Options (AUX Pins / Virtual GPIO)
LEAK_PINS = [
    {"pin": 50, "name": "AUX 1 (Pin 50)", "gpio": 50},
    {"pin": 51, "name": "AUX 2 (Pin 51)", "gpio": 51},
    {"pin": 52, "name": "AUX 3 (Pin 52)", "gpio": 52},
    {"pin": 53, "name": "AUX 4 (Pin 53)", "gpio": 53},
    {"pin": 54, "name": "AUX 5 (Pin 54)", "gpio": 54},
    {"pin": 55, "name": "AUX 6 (Pin 55)", "gpio": 55},
]

# MAVLink Command Constants
MAV_CMD_DO_MOTOR_TEST = 209
MAV_CMD_PREFLIGHT_CALIBRATION = 241
MAV_CMD_DO_START_MAG_CAL = 42424
MAV_CMD_COMPONENT_ARM_DISARM = 400
MAV_CMD_DO_SET_SERVO = 183
MAV_CMD_DO_SET_RELAY = 181

# Standard ArduSub Parameters with Metadata for SimpleROV-4 & Pixhawk 2.4.8
KEY_PARAMETERS = {
    "FRAME_CONFIG": {
        "name": "FRAME_CONFIG",
        "default": 6,
        "min": 1,
        "max": 8,
        "desc": "Vehicle Frame Selection (6 = SimpleROV-4, 5 = SimpleROV-3, 2 = BlueROV2)",
        "group": "Frame & Motors"
    },
    "MOT_1_DIRECTION": {"name": "MOT_1_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 1 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "MOT_2_DIRECTION": {"name": "MOT_2_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 2 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "MOT_3_DIRECTION": {"name": "MOT_3_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 3 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "MOT_4_DIRECTION": {"name": "MOT_4_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 4 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "MOT_5_DIRECTION": {"name": "MOT_5_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 5 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "MOT_6_DIRECTION": {"name": "MOT_6_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 6 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "MOT_7_DIRECTION": {"name": "MOT_7_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 7 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "MOT_8_DIRECTION": {"name": "MOT_8_DIRECTION", "default": 1, "min": -1, "max": 1, "desc": "Motor 8 Rotation Direction (1=Normal, -1=Reverse)", "group": "Frame & Motors"},
    "FS_LEAK_ENABLE": {"name": "FS_LEAK_ENABLE", "default": 1, "min": 0, "max": 1, "desc": "Leak Failsafe Action (0=Disabled, 1=Surface, 2=Disarm)", "group": "Safety & Failsafe"},
    "LEAK1_PIN": {"name": "LEAK1_PIN", "default": 55, "min": -1, "max": 55, "desc": "Primary Leak Sensor GPIO Pin (e.g. 55 for AUX 6)", "group": "Safety & Failsafe"},
    "LEAK1_LOGIC": {"name": "LEAK1_LOGIC", "default": 0, "min": 0, "max": 1, "desc": "Leak Sensor Logic State (0=Low triggers leak, 1=High triggers leak)", "group": "Safety & Failsafe"},
    "FS_BATT_ENABLE": {"name": "FS_BATT_ENABLE", "default": 1, "min": 0, "max": 2, "desc": "Battery Failsafe (0=Disabled, 1=Surface, 2=Disarm)", "group": "Safety & Failsafe"},
    "FS_BATT_VOLT": {"name": "FS_BATT_VOLT", "default": 10.5, "min": 0.0, "max": 50.0, "desc": "Battery Low Voltage Failsafe Threshold (Volts)", "group": "Safety & Failsafe"},
    "FS_BATT_MAH": {"name": "FS_BATT_MAH", "default": 1000, "min": 0, "max": 50000, "desc": "Battery Remaining Capacity Failsafe Threshold (mAh)", "group": "Safety & Failsafe"},
    "FS_GCS_ENABLE": {"name": "FS_GCS_ENABLE", "default": 1, "min": 0, "max": 2, "desc": "Ground Station Heartbeat Timeout Failsafe", "group": "Safety & Failsafe"},
    "ARMING_CHECK": {"name": "ARMING_CHECK", "default": 1, "min": 0, "max": 65535, "desc": "Pre-Arm Safety Checks Bitmask (1=All enabled, 0=Disabled)", "group": "Safety & Failsafe"},
    "FLTMODE1": {"name": "FLTMODE1", "default": 19, "min": 0, "max": 25, "desc": "Flight Mode 1 (19 = MANUAL)", "group": "Flight Modes"},
    "FLTMODE2": {"name": "FLTMODE2", "default": 0, "min": 0, "max": 25, "desc": "Flight Mode 2 (0 = STABILIZE)", "group": "Flight Modes"},
    "FLTMODE3": {"name": "FLTMODE3", "default": 2, "min": 0, "max": 25, "desc": "Flight Mode 3 (2 = ALT_HOLD / Depth Hold)", "group": "Flight Modes"},
    "FLTMODE4": {"name": "FLTMODE4", "default": 16, "min": 0, "max": 25, "desc": "Flight Mode 4 (16 = POSHOLD)", "group": "Flight Modes"},
    "FLTMODE5": {"name": "FLTMODE5", "default": 1, "min": 0, "max": 25, "desc": "Flight Mode 5 (1 = ACRO)", "group": "Flight Modes"},
    "FLTMODE6": {"name": "FLTMODE6", "default": 9, "min": 0, "max": 25, "desc": "Flight Mode 6 (9 = SURFACE)", "group": "Flight Modes"},
    "RC_SPEED": {"name": "RC_SPEED", "default": 200, "min": 50, "max": 400, "desc": "Actuator Output Refresh Rate (Hz)", "group": "Actuators & RC"},
    "SERVO10_FUNCTION": {"name": "SERVO10_FUNCTION", "default": 7, "min": 0, "max": 120, "desc": "AUX 2 Function (e.g. 7 = Mount Tilt)", "group": "Actuators & RC"},
    "SERVO11_FUNCTION": {"name": "SERVO11_FUNCTION", "default": 12, "min": 0, "max": 120, "desc": "AUX 3 Function (e.g. 12 = Lumen Lights 1)", "group": "Actuators & RC"},
    "SERVO12_FUNCTION": {"name": "SERVO12_FUNCTION", "default": 13, "min": 0, "max": 120, "desc": "AUX 4 Function (e.g. 13 = Lumen Lights 2)", "group": "Actuators & RC"},
}
