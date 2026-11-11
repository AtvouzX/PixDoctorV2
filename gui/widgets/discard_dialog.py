"""
PixDoctorV2 - Unsaved Changes Discard & Confirmation Modal Dialog.
Provides a clean, retro-styled modal dialog prompting pilots to Save, Discard,
or Cancel navigation when leaving tabs or switching profiles with unsaved edits.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    COLOR_INVERT_BG,
    COLOR_INVERT_FG,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
)
from gui.widgets.mono_widgets import RetroCard


class DiscardDialog(tk.Toplevel):
    """
    Modal dialog asking user how to handle unsaved changes:
    - 'save': Save changes and proceed
    - 'discard': Discard changes (reload last saved state) and proceed
    - 'cancel': Abort action and remain on current screen
    """

    def __init__(
        self,
        parent: tk.Misc,
        title: str = "Unsaved Changes",
        message: Optional[str] = None,
        item_name: str = "configuration",
    ):
        super().__init__(parent)
        self.title(f"PixDoctorV2 - {title}")
        self.config(bg=COLOR_BG)
        self.resizable(False, False)

        self.result: str = "cancel"

        self.transient(parent.winfo_toplevel() if parent else None)
        self.grab_set()

        self._build_ui(title, message, item_name)
        self._center_window(parent)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<Return>", lambda e: self._on_save())

        # Wait for user action
        self.wait_window(self)

    def _center_window(self, parent: tk.Misc):
        self.update_idletasks()
        w = 460
        h = 220
        if parent:
            try:
                top = parent.winfo_toplevel()
                px = top.winfo_rootx()
                py = top.winfo_rooty()
                pw = top.winfo_width()
                ph = top.winfo_height()
                x = px + max(0, (pw - w) // 2)
                y = py + max(0, (ph - h) // 2)
            except Exception:
                x = (self.winfo_screenwidth() - w) // 2
                y = (self.winfo_screenheight() - h) // 2
        else:
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self, title: str, message: Optional[str], item_name: str):
        card = RetroCard(self, title=title.upper())
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Message body
        msg_frame = tk.Frame(card.body, bg=COLOR_SURFACE)
        msg_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 12))

        default_msg = (
            f"You have unsaved changes in '{item_name}'.\n\n"
            "Would you like to save your modifications to file before leaving, "
            "or discard them to restore your last saved profile?"
        )
        display_msg = message or default_msg

        lbl_icon = tk.Label(
            msg_frame,
            text="[ ! ]",
            bg=COLOR_SURFACE,
            fg="#eab308",
            font=FONT_HEADER
        )
        lbl_icon.pack(side=tk.LEFT, anchor="n", padx=(4, 12), pady=(4, 0))

        lbl_text = tk.Label(
            msg_frame,
            text=display_msg,
            bg=COLOR_SURFACE,
            fg=COLOR_TEXT_WHITE,
            font=FONT_BODY,
            justify=tk.LEFT,
            wraplength=340
        )
        lbl_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Buttons row
        btn_row = tk.Frame(card.body, bg=COLOR_SURFACE)
        btn_row.pack(fill=tk.X, pady=(4, 0))

        btn_cancel = ttk.Button(
            btn_row,
            text="CANCEL",
            style="Retro.TButton",
            width=10,
            command=self._on_cancel
        )
        btn_cancel.pack(side=tk.RIGHT, padx=(4, 0))

        btn_discard = ttk.Button(
            btn_row,
            text="DISCARD CHANGES",
            style="Retro.TButton",
            width=17,
            command=self._on_discard
        )
        btn_discard.pack(side=tk.RIGHT, padx=(4, 0))

        btn_save = ttk.Button(
            btn_row,
            text="[ SAVE CHANGES ]",
            style="Invert.TButton",
            width=17,
            command=self._on_save
        )
        btn_save.pack(side=tk.RIGHT, padx=(0, 4))
        btn_save.focus_set()

    def _on_save(self):
        self.result = "save"
        self.destroy()

    def _on_discard(self):
        self.result = "discard"
        self.destroy()

    def _on_cancel(self):
        self.result = "cancel"
        self.destroy()


def show_discard_dialog(
    parent: tk.Misc,
    title: str = "Unsaved Changes",
    message: Optional[str] = None,
    item_name: str = "configuration",
) -> str:
    """
    Shows modal discard dialog and returns user choice:
    'save', 'discard', or 'cancel'.
    """
    dlg = DiscardDialog(parent, title=title, message=message, item_name=item_name)
    return dlg.result
