"""Switch config.toml [link] between router and direct-USB wiring.

Only the endpoint, baudrate and auto_connect lines are rewritten; comments and
every other setting in the file stay byte-for-byte intact.

    python3 deploy/switch_link.py router
    python3 deploy/switch_link.py direct --device /dev/ttyACM0
    python3 deploy/switch_link.py direct --device /dev/ttyACM0 --baudrate 57600
    python3 deploy/switch_link.py direct --device COM5
    python3 deploy/switch_link.py show
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.rov_config import DEFAULT_CONFIG, default_config_path  # noqa: E402

ROUTER_ENDPOINT = "udpin:0.0.0.0:14550"
LINK_END = re.compile(r"^\[(?!link\])")


def _sections(lines: list[str]) -> tuple[int, int]:
    """Return [start, end) line range of the [link] table."""
    start = next((i for i, line in enumerate(lines) if line.strip() == "[link]"), -1)
    if start < 0:
        return -1, -1
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if LINK_END.match(lines[i].strip()):
            end = i
            break
    return start, end


def _set(lines: list[str], key: str, value: str, start: int, end: int) -> list[str]:
    """Replace key inside the [link] block, or append it before the block ends."""
    pattern = re.compile(rf"^{key}\s*=")
    for i in range(start + 1, end):
        if pattern.match(lines[i].strip()):
            lines[i] = f"{key} = {value}\n"
            return lines
    insert_at = end
    while insert_at > start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, f"{key} = {value}\n")
    return lines


def _write(path: Path, lines: list[str]) -> None:
    """Write with the file's original newline style."""
    text = "".join(lines)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def switch(path: Path, endpoint: str, baudrate: int | None = None) -> str:
    """Write *endpoint* (and optional serial *baudrate*) into the config."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    with path.open("r", encoding="utf-8", newline="") as handle:
        original = handle.read()
    newline = "\r\n" if "\r\n" in original else "\n"
    lines = original.replace("\r\n", "\n").splitlines(keepends=True)
    start, end = _sections(lines)
    if start < 0:
        raise SystemExit(f"{path}: no [link] section")
    lines = _set(lines, "endpoint", f'"{endpoint}"', start, end)
    start, end = _sections(lines)
    lines = _set(lines, "auto_connect", "true", start, end)
    if baudrate:
        start, end = _sections(lines)
        lines = _set(lines, "baudrate", str(int(baudrate)), start, end)
    _write(path, [line.replace("\n", newline) for line in lines])
    return endpoint


def read_endpoint(path: Path) -> str | None:
    return _read_link(path).get("endpoint")


def _read_link(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    return tomllib.loads(path.read_text(encoding="utf-8")).get("link", {})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("router", "direct", "show"))
    parser.add_argument("--device", default="/dev/ttyACM0",
                        help="serial port or COM port for direct mode")
    parser.add_argument("--baudrate", type=int, default=None,
                        help="serial rate for direct mode (57600 or 115200);"
                             " omit to keep the current value")
    parser.add_argument("--config", default=None, help="config.toml path")
    args = parser.parse_args(argv)

    if args.mode == "direct":
        # Git Bash (MSYS) rewrites /dev/... into a Windows path; undo it.
        args.device = re.sub(r"^[A-Za-z]:[/\\]+(?=(dev|tmp|etc)[/\\])(.*)",
                             lambda m: "/" + m.group(2).replace("\\", "/"),
                             args.device)

    path = Path(args.config) if args.config else default_config_path()

    if args.mode == "show":
        print(read_endpoint(path) or "config.toml not created yet")
        if path.exists():
            link = _read_link(path)
            print(f"baudrate = {link.get('baudrate')} (serial only)")
        return 0

    endpoint = ROUTER_ENDPOINT if args.mode == "router" else args.device
    if args.mode == "direct":
        if not (endpoint.startswith("/dev/") or re.fullmatch(r"(?i)com\d+", endpoint)):
            print(f"error: --device must be /dev/ttyXXX or COMn, got {endpoint!r}",
                  file=sys.stderr)
            return 2
        if args.baudrate is not None and args.baudrate <= 0:
            print("error: --baudrate must be positive", file=sys.stderr)
            return 2
    baudrate = args.baudrate if args.mode == "direct" else None
    switch(path, endpoint, baudrate)
    print(f"{path}: endpoint = {endpoint}")
    if baudrate:
        print(f"{path}: baudrate = {baudrate}")
    if args.mode == "direct":
        print("Pixhawk must be plugged into this host only;"
              " stop mavlink-router on the Pi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())