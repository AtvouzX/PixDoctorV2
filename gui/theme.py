"""
PixDoctorV2 - Nostalgic Monochrome Design System & Tkinter Styles.
Classic retro-avionics & engineering console aesthetic:
Simple, sharp, high-contrast, pure monochrome with zero clutter.
"""

import tkinter as tk
from tkinter import ttk

# Nostalgic Monochrome Palette
COLOR_BG = "#0a0a0c"            # Deep obsidian console background
COLOR_SURFACE = "#121215"       # Card / panel surface
COLOR_SURFACE_HOVER = "#1c1c21" # Hovered panel state
COLOR_BORDER = "#2b2b32"        # Tactile perimeter border
COLOR_BORDER_LIGHT = "#42424c"  # Highlighted active border

COLOR_TEXT_WHITE = "#ffffff"    # Pure primary white
COLOR_TEXT_DIM = "#a1a1aa"      # Muted silver / zinc secondary
COLOR_TEXT_FAINT = "#63636c"    # Disabled / faint text

COLOR_INVERT_BG = "#ffffff"     # Inverted badge / active background
COLOR_INVERT_FG = "#000000"     # Inverted badge / active text

# Standard Monospace Fonts for Nostalgic Engineering Feel
FONT_TITLE = ("Consolas", 13, "bold")
FONT_HEADER = ("Consolas", 11, "bold")
FONT_BODY = ("Consolas", 10, "normal")
FONT_BODY_BOLD = ("Consolas", 10, "bold")
FONT_SMALL = ("Consolas", 9, "normal")
FONT_LARGE_NUM = ("Consolas", 20, "bold")
FONT_HUGE_NUM = ("Consolas", 28, "bold")


def configure_retro_styles(root: tk.Tk):
    """Apply global ttk styling for nostalgic monochrome appearance."""
    style = ttk.Style(root)
    style.theme_use("clam")

    # Global Frame and Label styling
    style.configure(
        "TFrame",
        background=COLOR_BG
    )
    style.configure(
        "Surface.TFrame",
        background=COLOR_SURFACE,
        relief="solid",
        borderwidth=1
    )
    style.configure(
        "TLabel",
        background=COLOR_BG,
        foreground=COLOR_TEXT_WHITE,
        font=FONT_BODY
    )
    style.configure(
        "Header.TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT_WHITE,
        font=FONT_HEADER
    )
    style.configure(
        "Dim.TLabel",
        background=COLOR_BG,
        foreground=COLOR_TEXT_DIM,
        font=FONT_SMALL
    )

    # Retro Monochrome Button
    style.configure(
        "Retro.TButton",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT_WHITE,
        font=FONT_BODY_BOLD,
        borderwidth=1,
        bordercolor=COLOR_BORDER,
        focusthickness=0,
        padding=(10, 5)
    )
    style.map(
        "Retro.TButton",
        background=[("active", COLOR_INVERT_BG), ("pressed", COLOR_TEXT_DIM)],
        foreground=[("active", COLOR_INVERT_FG), ("pressed", COLOR_INVERT_FG)],
        bordercolor=[("active", COLOR_TEXT_WHITE)]
    )

    # Inverted High-Contrast Primary Button
    style.configure(
        "Invert.TButton",
        background=COLOR_INVERT_BG,
        foreground=COLOR_INVERT_FG,
        font=FONT_BODY_BOLD,
        borderwidth=1,
        padding=(12, 6)
    )
    style.map(
        "Invert.TButton",
        background=[("active", COLOR_TEXT_DIM)],
        foreground=[("active", COLOR_INVERT_FG)]
    )

    # Combobox styling
    style.configure(
        "TCombobox",
        fieldbackground=COLOR_SURFACE,
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT_WHITE,
        bordercolor=COLOR_BORDER,
        arrowcolor=COLOR_TEXT_WHITE,
        font=FONT_BODY
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLOR_SURFACE)],
        foreground=[("readonly", COLOR_TEXT_WHITE)]
    )

    # Entry Box styling
    style.configure(
        "TEntry",
        fieldbackground=COLOR_SURFACE,
        foreground=COLOR_TEXT_WHITE,
        bordercolor=COLOR_BORDER,
        font=FONT_BODY
    )

    # Treeview / Parameter Table styling
    style.configure(
        "Treeview",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT_WHITE,
        fieldbackground=COLOR_SURFACE,
        bordercolor=COLOR_BORDER,
        borderwidth=1,
        font=FONT_BODY,
        rowheight=24
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_BORDER_LIGHT)],
        foreground=[("selected", COLOR_TEXT_WHITE)]
    )
    style.configure(
        "Treeview.Heading",
        background=COLOR_BG,
        foreground=COLOR_TEXT_WHITE,
        font=FONT_BODY_BOLD,
        relief="flat",
        bordercolor=COLOR_BORDER
    )

    # Scrollbars
    style.configure(
        "Vertical.TScrollbar",
        background=COLOR_SURFACE,
        troughcolor=COLOR_BG,
        bordercolor=COLOR_BG,
        arrowcolor=COLOR_TEXT_WHITE,
        relief="flat"
    )
