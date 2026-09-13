"""
PixDoctorV2 - Pixhawk 2.4.8 (ArduSub 4.7.1) ROV Configuration Suite
Main Launcher with DPI Awareness, Multithreading, and Error Trapping.
"""

import sys
import os
import ctypes
import traceback

# Ensure project root is in Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


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
