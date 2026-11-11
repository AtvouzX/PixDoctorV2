"""
PixDoctorV2 - ArduSub 4.7.1 Parameter Management & Persistence Engine.
Stores parameter cache, tracks modifications, validates boundaries,
and supports standard ArduPilot .param file export and import.
"""

import os
import time
import threading
from typing import Dict, Any, List, Optional
from core.ardusub_defs import KEY_PARAMETERS


class ParameterItem:
    """Represents a single ArduSub onboard configuration parameter."""

    def __init__(self, name: str, value: float, param_type: int = 0):
        self.name: str = name
        self.value: float = value
        self.param_type: int = param_type
        self.original_value: float = value
        self.dirty: bool = False

        # Metadata lookup
        meta = KEY_PARAMETERS.get(name, {})
        self.desc: str = meta.get("desc", "Standard ArduSub onboard parameter")
        self.group: str = meta.get("group", "General")
        self.min_val: Optional[float] = meta.get("min", None)
        self.max_val: Optional[float] = meta.get("max", None)

    def set_value(self, new_val: float):
        self.value = new_val
        self.dirty = abs(self.value - self.original_value) > 1e-5

    def commit(self):
        self.original_value = self.value
        self.dirty = False

    def revert(self):
        self.value = self.original_value
        self.dirty = False


class ParameterManager:
    """In-memory cache and file I/O for Pixhawk parameters."""

    def __init__(self):
        self._params: Dict[str, ParameterItem] = {}
        self._lock = threading.RLock()
        # Names reported by the vehicle (pre-populated defaults are not proof).
        self.received = set()
        # Pre-populate known key parameters with default values
        for name, meta in KEY_PARAMETERS.items():
            self._params[name] = ParameterItem(name, float(meta["default"]))

    def update_param(self, name: str, value: float, param_type: int = 0):
        """Update or insert a parameter received from MAVLink PARAM_VALUE."""
        name = name.strip()
        with self._lock:
            self.received.add(name)
            if name in self._params:
                p = self._params[name]
                p.original_value = value
                p.value = value
                p.dirty = False
                p.param_type = param_type
            else:
                self._params[name] = ParameterItem(name, value, param_type)

    def get_param(self, name: str, default: Optional[float] = None) -> Optional[ParameterItem]:
        return self._params.get(name, None)

    def get_value(self, name: str, default: float = 0.0) -> float:
        p = self._params.get(name)
        return p.value if p else default

    def set_value(self, name: str, value: float):
        if name in self._params:
            self._params[name].set_value(value)
        else:
            p = ParameterItem(name, value)
            p.dirty = True
            self._params[name] = p

    def get_all(self) -> Dict[str, ParameterItem]:
        with self._lock:
            return dict(self._params)

    def get_received_values(self) -> Dict[str, float]:
        """Values the vehicle actually reported (excludes local defaults)."""
        with self._lock:
            return {
                name: self._params[name].value
                for name in self.received
                if name in self._params
            }

    def get_dirty_params(self) -> List[ParameterItem]:
        return [p for p in self._params.values() if p.dirty]

    def filter_params(self, query: str = "", group: str = "All") -> List[ParameterItem]:
        """Search parameters by name/description and filter by category."""
        query = query.upper().strip()
        results = []
        for p in sorted(self._params.values(), key=lambda x: x.name):
            if group != "All" and p.group != group:
                continue
            if not query or query in p.name.upper() or query in p.desc.upper():
                results.append(p)
        return results

    def export_to_file(self, file_path: str) -> bool:
        """Export parameters to standard ArduPilot .param format."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# PixDoctorV2 ArduSub 4.7.1 Parameter File\n")
                f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total Parameters: {len(self._params)}\n#\n")
                for name in sorted(self._params.keys()):
                    val = self._params[name].value
                    # Format as int if whole number
                    val_str = f"{int(val)}" if val.is_integer() else f"{val:.6f}"
                    f.write(f"{name},{val_str}\n")
            return True
        except Exception:
            return False

    def import_from_file(self, file_path: str) -> int:
        """Import parameters from .param file. Returns number of updated params."""
        if not os.path.exists(file_path):
            return 0
        count = 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(",")
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        try:
                            val = float(parts[1].strip())
                            self.set_value(name, val)
                            count += 1
                        except ValueError:
                            pass
            return count
        except Exception:
            return 0
