#!/usr/bin/env bash
# Configure a Raspberry Pi 4B as the MAVLink router between the Pixhawk and the
# Jetson. Idempotent: safe to re-run after changing the Pixhawk port.
#
#   sudo ./deploy/setup_pi.sh
#   sudo ./deploy/setup_pi.sh --device /dev/ttyACM1 --baud 115200
#
# Installs mavlink-router, writes /etc/mavlink-router/main.conf and enables the
# systemd service. UDP 14550 serves PixDoctorV2, UDP 14551 serves QGroundControl.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONF_SRC="$REPO_DIR/deploy/mavlink-router.conf"
UNIT_SRC="$REPO_DIR/deploy/mavlink-router.service"
CONF_DST="/etc/mavlink-router/main.conf"
UNIT_DST="/etc/systemd/system/mavlink-router.service"
RUN_USER="${SUDO_USER:-$(id -un)}"

DEVICE="/dev/ttyACM0"
BAUD="115200"

usage() {
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --device) DEVICE="${2:?--device needs a path}"; shift 2 ;;
        --baud) BAUD="${2:?--baud needs a number}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo $0 $*" >&2
    exit 1
fi

if ! [ -e "$DEVICE" ]; then
    echo "WARNING: $DEVICE does not exist yet. The router will retry once it appears."
    echo "         Connected ports: $(ls /dev/ttyACM* 2>/dev/null || echo none)"
fi

echo "==> Installing mavlink-router"
if ! command -v mavlink-routerd >/dev/null 2>&1; then
    apt-get update
    apt-get install -y mavlink-router
fi

echo "==> Writing $CONF_DST (device $DEVICE, baud $BAUD)"
install -d /etc/mavlink-router
sed -e "s|^Device = .*|Device = $DEVICE|" \
    -e "s|^Baud = .*|Baud = $BAUD|" \
    "$CONF_SRC" > "$CONF_DST"

echo "==> Installing $UNIT_DST"
install -m 0644 "$UNIT_SRC" "$UNIT_DST"

echo "==> Allowing $RUN_USER to open serial devices (dialout)"
if ! id -nG "$RUN_USER" | tr ' ' '\n' | grep -qx dialout; then
    usermod -aG dialout "$RUN_USER"
    echo "    Added. Log out and back in (or reboot) for it to take effect."
fi

echo "==> Enabling mavlink-router"
systemctl daemon-reload
systemctl enable mavlink-router
systemctl restart mavlink-router
sleep 1

echo
echo "==> Status"
systemctl --no-pager --lines=5 status mavlink-router || true
echo
echo "Listening sockets (expect UDP 14550 and 14551):"
ss -lunp | grep -E ':1455[01]' || echo "    none yet - check the Pixhawk cable and $DEVICE"

echo
echo "Done. On the Jetson: sudo ./deploy/setup_jetson.sh --router"