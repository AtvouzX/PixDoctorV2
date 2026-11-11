"""
PixDoctorV2 - ROV flight-control configuration.

Ported from eltorpedo. config.toml holds the mavlink-router endpoint, the
20 Hz control rates, failsafe timeouts and the claw button layout. It is
generated with comments on first run; the file is the single place to change
link or claw behaviour without touching code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 on older JetPack images
    import tomli as tomllib

DEFAULT_CONFIG = """\
# PixDoctorV2 flight-control configuration.
# Regenerated with comments if deleted. Gamepad calibration lives in
# gamepad_config.json; this file covers the MAVLink link, control loop,
# failsafes and claw wiring.

[link]
# 1) Jetson via mavlink-router: udpin:0.0.0.0:14550
# 2) Jetson directly on Pixhawk USB: /dev/ttyACM0 (115200) or the COM port
#    on Windows. Serial endpoints ignore the UDP-only settings below.
# 3) Push to a remote router: udpout:192.168.1.50:14550
endpoint = "udpin:0.0.0.0:14550"
# Serial rate used only when endpoint is a serial port (/dev/ttyXXX or COMx).
# Set 57600 when SERIAL0_BAUD in the firmware is 57.
baudrate = 115200
source_system = 255
source_component = 191
control_hz = 20
heartbeat_hz = 1
link_timeout_s = 3.0
gamepad_timeout_s = 0.25
gamepad_disarm_s = 1.0
# Connect to endpoint on startup. Set false to use serial auto-detect only.
auto_connect = true

[control]
# Initial FLY toggle state. Keep false so editing parameters never spins props.
enabled = false

[claw]
# Torpedosub BTS7960 claw. Button bits in MANUAL_CONTROL map to BTN0..2:
# close_bit -> BTN0_FUNCTION=140, open_bit -> 139, stop_bit -> 141.
enabled = true
close_bit = 0
open_bit = 1
stop_bit = 2
press_ms = 150
# Refuse to arm until the firmware grip parameters match. Use the Params view
# to write them; set false on SITL where GRIP_* is absent.
require_config_for_arm = true

[claw.required]
GRIP_ENABLE = 1
GRIP_TYPE = 3
BTN0_FUNCTION = 140
BTN1_FUNCTION = 139
BTN2_FUNCTION = 141
"""

DEFAULT_CLAW_REQUIRED = {
    "GRIP_ENABLE": 1,
    "GRIP_TYPE": 3,
    "BTN0_FUNCTION": 140,
    "BTN1_FUNCTION": 139,
    "BTN2_FUNCTION": 141,
}


@dataclass(frozen=True)
class LinkConfig:
    endpoint: str = "udpin:0.0.0.0:14550"
    # Serial rate for /dev/ttyXXX or COMx endpoints. The Pixhawk ran 57600 on
    # the bench; SERIAL0_BAUD in the firmware is the authoritative value.
    baudrate: int = 115200
    source_system: int = 255
    source_component: int = 191
    control_hz: float = 20.0
    heartbeat_hz: float = 1.0
    link_timeout_s: float = 3.0
    gamepad_timeout_s: float = 0.25
    gamepad_disarm_s: float = 1.0
    auto_connect: bool = True


@dataclass(frozen=True)
class ControlConfig:
    enabled: bool = False


@dataclass(frozen=True)
class ClawConfig:
    enabled: bool = True
    close_bit: int = 0
    open_bit: int = 1
    stop_bit: int = 2
    press_ms: int = 150
    require_config_for_arm: bool = True
    required: dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_CLAW_REQUIRED)
    )


@dataclass(frozen=True)
class RovConfig:
    link: LinkConfig = field(default_factory=LinkConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    claw: ClawConfig = field(default_factory=ClawConfig)
    path: Path = field(default=Path("config.toml"), repr=False)


def default_config_path() -> Path:
    """Project-root config.toml, next to main.py."""
    return Path(__file__).resolve().parent.parent / "config.toml"


def _section(data: dict, key: str) -> dict:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def normalize_endpoint(endpoint: str) -> str:
    """Repair endpoints mangled by Git Bash path conversion or stray escapes.

    'C:/Program Files/Git/dev/ttyACM0' and '\\\\dev\\\\ttyACM0' both become
    '/dev/ttyACM0'. Anything else is returned unchanged.
    """
    value = endpoint.strip().strip("'\"")
    value = value.replace("\\", "/")
    if value.startswith(("/dev/", "/tmp/", "/etc/")):
        return value.replace("//", "/")
    for prefix in ("/dev/", "/tmp/", "/etc/"):
        index = value.find(prefix)
        if index > 0:
            return value[index:].replace("//", "/")
    return value


def load_rov_config(path: Path | None = None) -> RovConfig:
    """Load config.toml, writing a commented default when it is missing."""
    path = Path(path) if path else default_config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG, encoding="utf-8")

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    link_raw = _section(data, "link")
    link = LinkConfig(
        endpoint=normalize_endpoint(str(link_raw.get("endpoint", LinkConfig.endpoint))),
        baudrate=int(link_raw.get("baudrate", LinkConfig.baudrate)),
        source_system=int(link_raw.get("source_system", 255)),
        source_component=int(link_raw.get("source_component", 191)),
        control_hz=float(link_raw.get("control_hz", 20)),
        heartbeat_hz=float(link_raw.get("heartbeat_hz", 1)),
        link_timeout_s=float(link_raw.get("link_timeout_s", 3.0)),
        gamepad_timeout_s=float(link_raw.get("gamepad_timeout_s", 0.25)),
        gamepad_disarm_s=float(link_raw.get("gamepad_disarm_s", 1.0)),
        auto_connect=bool(link_raw.get("auto_connect", True)),
    )

    control_raw = _section(data, "control")
    control = ControlConfig(enabled=bool(control_raw.get("enabled", False)))

    claw_raw = _section(data, "claw")
    required_raw = _section(claw_raw, "required")
    required = {str(k): int(v) for k, v in required_raw.items()}
    claw = ClawConfig(
        enabled=bool(claw_raw.get("enabled", True)),
        close_bit=int(claw_raw.get("close_bit", 0)),
        open_bit=int(claw_raw.get("open_bit", 1)),
        stop_bit=int(claw_raw.get("stop_bit", 2)),
        press_ms=int(claw_raw.get("press_ms", 150)),
        require_config_for_arm=bool(claw_raw.get("require_config_for_arm", True)),
        required=required or dict(DEFAULT_CLAW_REQUIRED),
    )

    return RovConfig(link=link, control=control, claw=claw, path=path)
