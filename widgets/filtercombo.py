"""
widgets/filtercombo.py
Combobox filtrável em tempo real — substitui ttk.Combobox em qualquer lugar
do projeto que precise de busca incremental na lista.

Interface compatível com ttk.Combobox:
  - .get(), .set()
  - widget["values"] = lista   /   widget["values"]
  - evento <<ComboboxSelected>> disparado ao confirmar seleção
"""

import tkinter as tk
from utils.theme_manager import C, register_theme_listener


class FilterableCombobox(tk.Frame):
    """
    Combobox que filtra a lista de opções em tempo real conforme o usuário digita.

    Uso:
        cb = FilterableCombobox(parent, values=["Alpha", "Beta", "Gamma"], width=20)
        cb.pack()
        cb.bind("<<ComboboxSelected>>", lambda e: print(cb.get()))
    """

    def __init__(self, parent, values: list | None = None, width: int = 20,
                 state: str = "normal", font=("Helvetica Neue", 9), **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self._all_values: list[str] = list(values or [])
        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None
        self._after_id = None

        self._var = tk.StringVar()
        self._entry = tk.Entry(
            self, textvariable=self._var, width=width,
            bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"],
            relief="flat", highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["accent"],
            font=font,
            state=("readonly" if state == "readonly" else "normal"),
        )
        self._entry.pack(side="left", fill="x", expand=True, ipady=3)

        self._arrow = tk.Label(
            self, text="▾", bg=C["surface3"], fg=C["text_mid"],
            font=("Helvetica Neue", 9), cursor="hand2", padx=4,
        )
        self._arrow.pack(side="left")
        self._arrow.bind("<Button-1>", self._toggle_popup)

        self._var.trace_add("write", self._on_type)
        self._entry.bind("<Down>",     self._focus_list)
        self._entry.bind("<Return>",   self._on_entry_return)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<Button-1>", self._on_entry_click)

        # Recoloração automática de tema
        register_theme_listener(self._recolor)

    # ── Recolor ───────────────────────────────────────────────────────────────

    def _recolor(self):
        try:
            self.config(bg=C["bg"])
            self._entry.config(
                bg=C["surface3"], fg=C["text"],
                insertbackground=C["accent"],
                highlightbackground=C["border"],
                highlightcolor=C["accent"],
            )
            self._arrow.config(bg=C["surface3"], fg=C["text_mid"])
        except Exception:
            pass

    # ── API pública ───────────────────────────────────────────────────────────

    def get(self) -> str:
        return self._var.get()

    def set(self, value: str):
        self._var.set(value)

    def __getitem__(self, key):
        if key == "values":
            return self._all_values
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if key == "values":
            self._all_values = list(value)
            if self._listbox:
                self._refresh_listbox(self._filter_values(self._var.get()))
        else:
            super().__setitem__(key, value)

    def config(self, **kw):
        if "values" in kw:
            self._all_values = list(kw.pop("values"))
        if kw:
            try:
                super().config(**kw)
            except tk.TclError:
                pass

    # ── Filtro ────────────────────────────────────────────────────────────────

    def _filter_values(self, text: str) -> list[str]:
        text = text.strip().lower()
        if not text:
            return self._all_values
        return [v for v in self._all_values if text in v.lower()]

    def _on_type(self, *_):
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(120, self._update_popup)

    def _update_popup(self):
        filtered = self._filter_values(self._var.get())
        if not self._popup or not self._popup.winfo_exists():
            if filtered:
                self._open_popup(filtered)
        else:
            self._refresh_listbox(filtered)

    # ── Popup ─────────────────────────────────────────────────────────────────

    def _toggle_popup(self, _e=None):
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
        else:
            self._open_popup(self._filter_values(self._var.get()))

    def _open_popup(self, values: list[str]):
        if not values:
            return
        if self._popup and self._popup.winfo_exists():
            self._refresh_listbox(values)
            return

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.configure(bg=C["border"])

        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        h = min(220, len(values) * 22 + 4)
        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._popup.lift()

        fr = tk.Frame(self._popup, bg=C["surface2"])
        fr.pack(fill="both", expand=True, padx=1, pady=1)

        sb = tk.Scrollbar(fr, bg=C["surface3"], troughcolor=C["bg"], relief="flat")
        sb.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            fr,
            bg=C["surface2"], fg=C["text"],
            selectbackground=C["accent2"],
            activestyle="none",
            relief="flat", bd=0,
            font=("Helvetica Neue", 9),
            yscrollcommand=sb.set,
        )
        self._listbox.pack(fill="both", expand=True)
        sb.config(command=self._listbox.yview)

        self._refresh_listbox(values)
        self._listbox.bind("<ButtonRelease-1>", self._on_listbox_select)
        self._listbox.bind("<Return>",          self._on_listbox_select)
        self._listbox.bind("<Escape>",          lambda _e: self._close_popup())
        self._popup.bind("<FocusOut>",          self._on_popup_focus_out)

    def _refresh_listbox(self, values: list[str]):
        if not self._listbox:
            return
        self._listbox.delete(0, "end")
        for v in values:
            self._listbox.insert("end", v)
        if self._popup and self._popup.winfo_exists():
            w = self.winfo_width()
            h = min(220, len(values) * 22 + 4)
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            self._popup.geometry(f"{w}x{h}+{x}+{y}")

    def _close_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup   = None
        self._listbox = None

    def _on_listbox_select(self, _e=None):
        if not self._listbox:
            return
        sel = self._listbox.curselection()
        if sel:
            value = self._listbox.get(sel[0])
            self._var.set(value)
            self._close_popup()
            self.event_generate("<<ComboboxSelected>>")

    def _focus_list(self, _e=None):
        if self._popup and self._popup.winfo_exists() and self._listbox:
            self._listbox.focus_set()
            if self._listbox.size():
                self._listbox.selection_set(0)
                self._listbox.activate(0)

    def _on_entry_return(self, _e=None):
        filtered = self._filter_values(self._var.get())
        if len(filtered) == 1:
            self._var.set(filtered[0])
            self._close_popup()
            self.event_generate("<<ComboboxSelected>>")
        else:
            self._close_popup()

    def _on_focus_out(self, _e=None):
        self.after(200, self._close_popup)

    def _on_popup_focus_out(self, _e=None):
        self.after(200, self._close_popup)

    def _on_entry_click(self, _e=None):
        if self._entry.cget("state") == "readonly":
            self._toggle_popup()
