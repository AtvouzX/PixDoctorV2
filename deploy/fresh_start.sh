#!/usr/bin/env bash
# Reset generated config and runtime state, keeping the code untouched.
#
#   ./deploy/fresh_start.sh            # generated config back to defaults
#   ./deploy/fresh_start.sh --calib    # also drop gamepad calibration + matrix layout
#   ./deploy/fresh_start.sh --all      # config, calibration, logs, caches
#   ./deploy/fresh_start.sh --dry-run  # print what would change
#
# Never deletes firmware parameter values on the vehicle. Use
# deploy/simplerov4.parm or the Params view for those.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CALIB=0
LOGS=0
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --calib) CALIB=1; shift ;;
        --all) CALIB=1; LOGS=1; shift ;;
        --dry-run) DRY=1; shift ;;
        -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

remove() {
    for target in "$@"; do
        if [ -e "$target" ] || [ -L "$target" ]; then
            if [ "$DRY" -eq 1 ]; then
                echo "  would remove $target"
            else
                rm -rf "$target"
                echo "  removed $target"
            fi
        fi
    done
}

echo "== Generated config"
remove "$REPO_DIR/config.toml"
echo "  config.toml is rewritten with commented defaults on next launch"

if [ "$CALIB" -eq 1 ]; then
    echo "== Gamepad calibration and matrix layout"
    remove "$REPO_DIR/gamepad_config.json" "$REPO_DIR/gamepad_config.json.bak" \
           "$REPO_DIR/motor_matrix_config.json"
    echo "  defaults return on next launch (recalibrate sticks, re-pick the frame)"
fi

if [ "$LOGS" -eq 1 ]; then
    echo "== Logs and caches"
    remove "$REPO_DIR/pixdoctorv2_error.log"
    find "$REPO_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null
    find "$REPO_DIR" -name '*.pyc' -delete 2>/dev/null
    echo "  caches cleared"
fi

echo
echo "== Verify"
if [ "$DRY" -eq 0 ]; then
    PYTHON_BIN="$(command -v python3 || true)"
    if [ -n "$PYTHON_BIN" ]; then
        (cd "$REPO_DIR" && "$PYTHON_BIN" -m pytest tests -q 2>&1 | tail -n 3)
    fi
fi

echo
echo "== Git state (code must stay untouched)"
(cd "$REPO_DIR" && git status --short -- . ':(exclude)config.toml' 2>/dev/null | head -n 20) \
    || echo "  not a git checkout"

echo
echo "Next: python3 main.py"
echo "Then: ./deploy/setup_jetson.sh --direct --baudrate 57600   (or --router)"