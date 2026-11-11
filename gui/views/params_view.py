"""
PixDoctorV2 - Searchable Full Parameter Tree & File Manager View.
Supports searching, grouping, batch writing to Pixhawk flash,
and exporting / importing standard ArduPilot .param files.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, Optional

from gui.theme import (
    COLOR_BG,
    COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_BORDER_LIGHT,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_DIM,
    FONT_HEADER,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
)
from gui.widgets.mono_widgets import RetroCard, grab_when_viewable
from core.param_manager import ParameterManager, ParameterItem
from core.mavlink_manager import MavlinkManager


class ParamsView(tk.Frame):
    """Full parameter configuration table and persistence manager."""

    def __init__(
        self,
        parent,
        param_mgr: ParameterManager,
        mav_mgr: MavlinkManager,
        **kwargs
    ):
        super().__init__(parent, bg=COLOR_BG, **kwargs)
        self.param_mgr = param_mgr
        self.mav_mgr = mav_mgr

        self._build_ui()
        self.refresh_table()

    def _build_ui(self):
        # Top Header & Action Toolbar
        top_bar = tk.Frame(self, bg=COLOR_BG)
        top_bar.pack(fill=tk.X, padx=12, pady=(10, 6))

        tk.Label(
            top_bar,
            text="[ FULL PARAMETER TREE & PERSISTENCE ]",
            bg=COLOR_BG,
            fg=COLOR_TEXT_WHITE,
            font=FONT_HEADER
        ).pack(side=tk.LEFT)

        # Action Buttons on Right
        btn_box = tk.Frame(top_bar, bg=COLOR_BG)
        btn_box.pack(side=tk.RIGHT)

        ttk.Button(btn_box, text="REFRESH FROM PIXHAWK", style="Retro.TButton", command=self._request_refresh).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_box, text="LOAD .PARAM FILE", style="Retro.TButton", command=self._load_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_box, text="EXPORT .PARAM FILE", style="Retro.TButton", command=self._export_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_box, text="[ WRITE TO FLASH ]", style="Invert.TButton", command=self._write_params).pack(side=tk.LEFT, padx=3)

        # Filter & Search Bar Row
        filter_bar = tk.Frame(self, bg=COLOR_SURFACE, padx=10, pady=6, highlightbackground=COLOR_BORDER, highlightthickness=1)
        filter_bar.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(filter_bar, text="SEARCH:", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_table())
        self.ent_search = ttk.Entry(filter_bar, textvariable=self.search_var, width=24)
        self.ent_search.pack(side=tk.LEFT, padx=(0, 16))

        tk.Label(filter_bar, text="GROUP:", bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 4))
        self.group_var = tk.StringVar(value="All")
        groups = ["All", "Frame & Motors", "Safety & Failsafe", "Flight Modes", "Actuators & RC", "General"]
        self.cb_group = ttk.Combobox(filter_bar, textvariable=self.group_var, values=groups, state="readonly", width=18)
        self.cb_group.pack(side=tk.LEFT)
        self.cb_group.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        # Table & Scrollbar Container
        table_frame = tk.Frame(self, bg=COLOR_SURFACE, highlightbackground=COLOR_BORDER, highlightthickness=1)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        columns = ("name", "value", "modified", "group", "desc")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("name", text="PARAMETER", anchor="w")
        self.tree.heading("value", text="CURRENT VALUE", anchor="center")
        self.tree.heading("modified", text="STATUS", anchor="center")
        self.tree.heading("group", text="GROUP", anchor="w")
        self.tree.heading("desc", text="DESCRIPTION", anchor="w")

        self.tree.column("name", width=180, stretch=False)
        self.tree.column("value", width=120, stretch=False, anchor="center")
        self.tree.column("modified", width=100, stretch=False, anchor="center")
        self.tree.column("group", width=140, stretch=False)
        self.tree.column("desc", width=400, stretch=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)

    def refresh_table(self):
        """Populate Treeview with matching parameters."""
        query = self.search_var.get()
        group = self.group_var.get()
        items = self.param_mgr.filter_params(query=query, group=group)

        self.tree.delete(*self.tree.get_children())
        for p in items:
            val_str = f"{int(p.value)}" if p.value.is_integer() else f"{p.value:.4f}"
            mod_str = "[MODIFIED]" if p.dirty else "SYNCED"
            self.tree.insert(
                "",
                tk.END,
                iid=p.name,
                values=(p.name, val_str, mod_str, p.group, p.desc)
            )

    def _on_double_click(self, event):
        """Open inline value edit dialog."""
        selected = self.tree.selection()
        if not selected:
            return
        param_name = selected[0]
        p = self.param_mgr.get_param(param_name)
        if not p:
            return

        self._show_edit_dialog(p)

    def _show_edit_dialog(self, param: ParameterItem):
        win = tk.Toplevel(self)
        win.title(f"Edit Parameter: {param.name}")
        win.geometry("420x300")
        win.config(bg=COLOR_BG)
        win.resizable(False, False)
        win.transient(self)
        grab_when_viewable(win)

        card = RetroCard(win, title=f"Set Value: {param.name}")
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tk.Label(card.body, text=param.desc, bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=FONT_SMALL, wraplength=340, justify="left").pack(anchor="w", pady=(0, 8))

        row = tk.Frame(card.body, bg=COLOR_SURFACE)
        row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(row, text="VALUE:", bg=COLOR_SURFACE, fg=COLOR_TEXT_WHITE, font=FONT_BODY_BOLD).pack(side=tk.LEFT, padx=(0, 6))
        val_entry = ttk.Entry(row, width=16)
        val_str = f"{int(param.value)}" if param.value.is_integer() else f"{param.value}"
        val_entry.insert(0, val_str)
        val_entry.pack(side=tk.LEFT)
        val_entry.focus_set()

        def _save():
            try:
                new_v = float(val_entry.get())
                self.param_mgr.set_value(param.name, new_v)
                self.refresh_table()
                win.destroy()
            except ValueError:
                messagebox.showerror("Invalid Value", "Please enter a valid numeric value.")

        btn_row = tk.Frame(card.body, bg=COLOR_SURFACE)
        btn_row.pack(fill=tk.X)

        ttk.Button(btn_row, text="[ SAVE ]", style="Invert.TButton", command=_save).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="CANCEL", style="Retro.TButton", command=win.destroy).pack(side=tk.LEFT)
        val_entry.bind("<Return>", lambda event: _save())
        win.bind("<Escape>", lambda event: win.destroy())

    def _request_refresh(self):
        self.mav_mgr.request_param_list()
        messagebox.showinfo("Param Request", "Requested full parameter list from Pixhawk. Receiving in background...")

    def _write_params(self):
        dirty = self.param_mgr.get_dirty_params()
        if not dirty:
            messagebox.showinfo("No Changes", "All parameters are already in sync with Pixhawk.")
            return

        if messagebox.askyesno(
            "Confirm Flash Write",
            f"Write {len(dirty)} modified parameters to Pixhawk EEPROM?",
            icon="question"
        ):
            for p in dirty:
                self.mav_mgr.set_param(p.name, p.value)
                p.commit()
            self.refresh_table()
            messagebox.showinfo("Success", f"{len(dirty)} parameters written to Pixhawk.")

    def _export_file(self):
        f = filedialog.asksaveasfilename(
            defaultextension=".param",
            filetypes=[("ArduPilot Parameter Files", "*.param"), ("All Files", "*.*")]
        )
        if f:
            if self.param_mgr.export_to_file(f):
                messagebox.showinfo("Export Successful", f"Parameters exported to:\n{f}")
            else:
                messagebox.showerror("Export Failed", "Failed to write parameter file.")

    def _load_file(self):
        f = filedialog.askopenfilename(
            filetypes=[("ArduPilot Parameter Files", "*.param;*.txt"), ("All Files", "*.*")]
        )
        if f:
            count = self.param_mgr.import_from_file(f)
            self.refresh_table()
            messagebox.showinfo("Import Successful", f"Imported {count} parameters from:\n{f}\nReview and click [WRITE TO FLASH] to commit.")
