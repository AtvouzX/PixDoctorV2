#!/usr/bin/env bash
# Diagnose why the Jetson cannot reach the Pixhawk, for both wirings.
# Read-only: changes nothing. Run it on the Jetson.
#
#   ./deploy/diagnose_link.sh                 # direct USB and router
#   ./deploy/diagnose_link.sh --device /dev/ttyACM1
#   ./deploy/diagnose_link.sh --router 192.168.1.50

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEVICE=""
ROUTER_HOST=""
PYTHON_BIN="$(command -v python3 || true)"
if [ -z "$PYTHON_BIN" ] || ! "$PYTHON_BIN" -c 'import sys' >/dev/null 2>&1; then
    PYTHON_BIN=""
fi

while [ $# -gt 0 ]; do
    case "$1" in
        --device) DEVICE="${2:?--device needs a path}"; shift 2 ;;
        --router) ROUTER_HOST="${2:?--router needs the Pi address}"; shift 2 ;;
        -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

ok()   { echo "  [ok]   $*"; }
bad()  { echo "  [fail] $*"; }
info() { echo "  [info] $*"; }

echo "== 1. Kernel sees a serial device"
PORTS="$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true)"
if [ -z "$PORTS" ]; then
    bad "no /dev/ttyACM* or /dev/ttyUSB* - Pixhawk cable, power or USB port problem"
else
    for port in $PORTS; do
        ok "$port -> $(readlink -f "$port")"
    done
    if [ -n "$DEVICE" ] && ! [ -e "$DEVICE" ]; then
        bad "$DEVICE requested but missing"
    fi
fi
if [ -n "$DEVICE" ]; then
    info "$(dmesg 2>/dev/null | grep -iE 'cdc_acm|ttyACM|ch341|ftdi' | tail -n 3 || echo 'dmesg not readable')"
fi

echo
echo "== 2. Another process owns the port (expected when using the Pi router)"
for port in $PORTS; do
    holder="$(sudo -n lsof "$port" 2>/dev/null | tail -n +2 || true)"
    if [ -n "$holder" ]; then
        # lsof without sudo only shows own processes; try /proc scan as fallback
        info "$port held by:"
        echo "$holder" | sed 's/^/         /'
    fi
done
if command -v fuser >/dev/null 2>&1; then
    for port in $PORTS; do
        owner="$(fuser "$port" 2>/dev/null || true)"
        [ -n "$owner" ] && info "$port open by pid(s): $owner"
    done
fi
if pgrep -a mavlink-routerd >/dev/null 2>&1; then
    bad "mavlink-routerd runs on THIS host; for the Pi router it must run on the Pi"
fi

echo
echo "== 3. Serial permissions"
if id -nG | tr ' ' '\n' | grep -qx dialout; then
    ok "user is in dialout"
else
    bad "user is not in dialout - sudo usermod -aG dialout \$USER, then log out and in"
fi
for port in $PORTS; do
    info "$port mode $(stat -c '%A %U:%G' "$port" 2>/dev/null)"
done

echo
echo "== 4. ModemManager (grabs ACM ports on Ubuntu images)"
if systemctl is-active --quiet ModemManager 2>/dev/null; then
    bad "ModemManager is active and will fight for /dev/ttyACM*"
    info "fix: sudo systemctl disable --now ModemManager"
else
    ok "ModemManager inactive or absent"
fi

echo
echo "== 5. brltty (Ubuntu grabs CH340/FTDI adapters)"
if systemctl is-active --quiet brltty 2>/dev/null; then
    bad "brltty is active - sudo systemctl disable --now brltty"
fi

echo
echo "== 6. Heartbeat over the serial device"
if [ -n "$PYTHON_BIN" ]; then
    for port in ${DEVICE:-$PORTS}; do
        "$PYTHON_BIN" - "$port" <<'EOF'
import sys
try:
    from pymavlink import mavutil
except ImportError:
    print("  [fail] pymavlink missing - pip install -r requirements.txt")
    raise SystemExit(0)
port = sys.argv[1]
try:
    conn = mavutil.mavlink_connection(port, baud=115200, timeout=0.5)
except Exception as exc:
    print(f"  [fail] {port}: cannot open: {exc}")
    raise SystemExit(0)
for baud in (115200, 57600, 921600):
    try:
        conn.set_baudrate(baud)
    except Exception:
        pass
    hb = conn.wait_heartbeat(timeout=4)
    if hb is not None:
        print(f"  [ok]   {port} @ {baud}: heartbeat sys={hb.get_srcSystem()} comp={hb.get_srcComponent()}")
        print(f"  [info] set this rate: [link] baudrate = {baud}")
        conn.close()
        raise SystemExit(0)
    print(f"  [fail] {port} @ {baud}: no heartbeat in 4 s")
conn.close()
EOF
    done
else
    bad "python3 not found"
fi

echo
echo "== 7. Router path (default UDP 14550)"
if [ -n "$ROUTER_HOST" ]; then
    if ping -c 2 -W 2 "$ROUTER_HOST" >/dev/null 2>&1; then
        ok "Pi $ROUTER_HOST answers ping"
    else
        bad "Pi $ROUTER_HOST does not answer ping - network or address wrong"
    fi
fi
if command -v ss >/dev/null 2>&1; then
    if ss -lun | grep -q ':14550'; then
        ok "a local UDP listener exists on 14550 (a second GCS copy may own it)"
    else
        info "no local UDP listener on 14550 yet - the GUI opens it at launch"
    fi
fi
if [ -n "$PYTHON_BIN" ]; then
    "$PYTHON_BIN" - <<'EOF'
try:
    from pymavlink import mavutil
except ImportError:
    print("  [fail] pymavlink missing")
    raise SystemExit(0)
conn = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
hb = conn.wait_heartbeat(timeout=4)
if hb is None:
    print("  [fail] udpin:0.0.0.0:14550: no heartbeat in 4 s (router down, wrong port, or cable on the Pi)")
else:
    print(f"  [ok]   udpin:0.0.0.0:14550: heartbeat sys={hb.get_srcSystem()} comp={hb.get_srcComponent()}")
conn.close()
EOF
fi

echo
echo "== 8. Current PixDoctorV2 link setting"
if [ -f "$REPO_DIR/config.toml" ]; then
    "$PYTHON_BIN" - "$REPO_DIR/config.toml" 2>/dev/null <<'EOF'
import sys
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from pathlib import Path
link = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("link", {})
print(f"  endpoint = {link.get('endpoint')}")
if str(link.get("endpoint", "")).startswith("/dev/"):
    print(f"  baudrate = {link.get('baudrate')} (serial)")
    print("  mode: direct USB - Pixhawk must not be plugged into the Pi")
else:
    print("  mode: router/UDP - Pixhawk must be cabled to the Pi, router running")
EOF
else
    info "config.toml missing; the GUI writes defaults on first launch"
fi
echo
echo "Send the output of this script with any bug report."