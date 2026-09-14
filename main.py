"""
PixDoctorV2 - Pixhawk 2.4.8 (ArduSub 4.7.1) ROV Configuration Suite
Main Launcher with DPI Awareness, Multithreading, and Error Trapping.
"""

import sys
import os
import ctypes
import traceback
import threading
import faulthandler

# Ensure project root is in Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ERROR_LOG_PATH = os.path.join(PROJECT_ROOT, "pixdoctorv2_error.log")

# Enable faulthandler to log any C-level crashes or access violations
try:
    _crash_file = open(ERROR_LOG_PATH, "a", encoding="utf-8")
    faulthandler.enable(file=_crash_file, all_threads=True)
except Exception:
    pass

def global_excepthook(exc_type, exc_val, exc_tb):
    """Global exception hook for unhandled exceptions on main thread."""
    msg = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    try:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n[UNCAUGHT EXCEPTION]:\n{msg}\n")
    except Exception:
        pass
    print(f"[UNCAUGHT EXCEPTION]:\n{msg}", file=sys.stderr)

sys.excepthook = global_excepthook

if hasattr(threading, "excepthook"):
    def thread_excepthook(args):
        """Thread exception hook for worker threads (Gamepad, MAVLink, Probe)."""
        msg = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        try:
            with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n[UNCAUGHT THREAD EXCEPTION in {args.thread.name}]:\n{msg}\n")
        except Exception:
            pass
        print(f"[UNCAUGHT THREAD EXCEPTION in {args.thread.name}]:\n{msg}", file=sys.stderr)

    threading.excepthook = thread_excepthook


def enable_windows_hidpi():
    """Enable crisp Windows DPI scaling for high-resolution displays."""
    try:
        if sys.platform == "win32":
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    """Launch PixDoctorV2 Application."""
    enable_windows_hidpi()

    try:
        from gui.app_window import PixDoctorApp
        app = PixDoctorApp()
        app.mainloop()
    except Exception as e:
        error_msg = traceback.format_exc()
        log_file = os.path.join(PROJECT_ROOT, "pixdoctorv2_error.log")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(error_msg)
        print(f"Error launching PixDoctorV2:\n{error_msg}", file=sys.stderr)

        # Show GUI error dialog if possible
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "PixDoctorV2 Startup Error",
                f"An error occurred while launching PixDoctorV2:\n\n{e}\n\nDetails saved to:\n{log_file}"
            )
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()
