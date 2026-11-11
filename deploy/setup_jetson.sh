#!/usr/bin/env bash
# Prepare the NVIDIA Jetson to run PixDoctorV2 and pick the MAVLink link.
# Idempotent: safe to re-run.
#
#   ./deploy/setup_jetson.sh --router            # pixhawk -> Raspberry Pi -> UDP 14550
#   ./deploy/setup_jetson.sh --direct            # pixhawk -> Jetson USB (/dev/ttyACM0)
#   ./deploy/setup_jetson.sh --direct --baudrate 57600
#   ./deploy/setup_jetson.sh --autostart         # add the desktop autostart unit
#   ./deploy/setup_jetson.sh --router --autostart
#
# Installs Python dependencies, adds the user to input + dialout, and sets the
# [link] section of config.toml through deploy/switch_link.py.
# Without --baudrate the existing [link] baudrate is kept.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODE=""
AUTOSTART=0
DEVICE=""
BAUDRATE=""

usage() {
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --router) MODE="router"; shift ;;
        --direct) MODE="direct"; shift ;;
        --device) DEVICE="${2:?--device needs a path}"; shift 2 ;;
        --baudrate) BAUDRATE="${2:?--baudrate needs a number}"; shift 2 ;;
        --autostart) AUTOSTART=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
fi
TARGET_USER="${SUDO_USER:-$(id -un)}"

echo "==> Checking host"
if ! [ -e /etc/nv_tegra_release ] && ! uname -m | grep -q aarch64; then
    echo "    WARNING: this does not look like a Jetson (no /etc/nv_tegra_release). Continuing."
fi

echo "==> Checking Python"
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "Python 3 not found. Install python3 (3.11 or newer) first." >&2
    exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "    Python < 3.11: requirements.txt installs tomli instead of tomllib."
fi
echo "    $PYTHON_BIN: $("$PYTHON_BIN" -V 2>&1)"

echo "==> Installing Python dependencies"
if [ -n "$SUDO" ] && [ ! -w "$REPO_DIR" ]; then
    $SUDO "$PYTHON_BIN" -m pip install -r "$REPO_DIR/requirements.txt"
else
    "$PYTHON_BIN" -m pip install --user -r "$REPO_DIR/requirements.txt"
fi

echo "==> Gamepad permissions (input + dialout)"
NEED_RELOGIN=0
for group in input dialout; do
    if ! id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx "$group"; then
        $SUDO usermod -aG "$group" "$TARGET_USER"
        NEED_RELOGIN=1
    fi
done

if [ -n "$MODE" ]; then
    echo "==> Setting MAVLink link: $MODE"
    if [ "$MODE" = "direct" ] && [ -z "$DEVICE" ]; then
        DEVICE="$(ls /dev/ttyACM* 2>/dev/null | head -n1 || true)"
        DEVICE="${DEVICE:-/dev/ttyACM0}"
        echo "    No --device given, using $DEVICE"
    fi
    BAUD_ARGS=""
    if [ -n "$BAUDRATE" ]; then
        BAUD_ARGS="--baudrate $BAUDRATE"
    fi
    if [ "$MODE" = "direct" ]; then
        # shellcheck disable=SC2086
        "$PYTHON_BIN" "$REPO_DIR/deploy/switch_link.py" direct --device "$DEVICE" $BAUD_ARGS
    else
        "$PYTHON_BIN" "$REPO_DIR/deploy/switch_link.py" router
    fi
fi

if [ "$AUTOSTART" -eq 1 ]; then
    echo "==> Installing desktop autostart unit"
    UNIT_TMP="$(mktemp)"
    sed -e "s|^User=.*|User=$TARGET_USER|" \
        -e "s|^WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|" \
        -e "s|^ExecStart=.*|ExecStart=$(command -v "$PYTHON_BIN") $REPO_DIR/main.py|" \
        -e "s|^Environment=XDG_RUNTIME_DIR=.*|Environment=XDG_RUNTIME_DIR=/run/user/$(id -u)|" \
        "$REPO_DIR/deploy/pixdoctor.service" > "$UNIT_TMP"
    $SUDO install -m 0644 "$UNIT_TMP" /etc/systemd/system/pixdoctor.service
    rm -f "$UNIT_TMP"
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable pixdoctor
    echo "    Enabled. Start the desktop session first, then: sudo systemctl start pixdoctor"
fi

echo
echo "==> Current link"
"$PYTHON_BIN" - "$REPO_DIR/config.toml" <<'EOF'
import sys
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
path = Path(sys.argv[1])
if path.exists():
    link = tomllib.loads(path.read_text(encoding="utf-8")).get("link", {})
    print(f"    endpoint = {link.get('endpoint')}")
    print(f"    baudrate = {link.get('baudrate')} (serial only)")
    print(f"    auto_connect = {link.get('auto_connect')}")
else:
    print("    config.toml not created yet; it is written on first launch.")
EOF

if [ "$NEED_RELOGIN" -eq 1 ]; then
    echo
    echo "Log out and back in so the input/dialout groups apply."
fi
echo
echo "Done. Launch with: $PYTHON_BIN $REPO_DIR/main.py"