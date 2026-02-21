"""
tabs/dashboard.py
Aba 1 — Dashboard em tempo real da frota.
"""

import re
import threading
import tkinter as tk
from tkinter import ttk
from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, auto_refresh_register
from core import get_all_events, safe_int, safe_float, safe_str
from widgets import lbl, ent, btn, mk_tree, mk_export_btn


class TabDashboard(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._data: list = []
        self._build()
        auto_refresh_register("dashboard", self.refresh)
        register_theme_listener(self._reapply_tags)

    def _reapply_tags(self):
        self.tree.tag_configure("on",  background=C["surface2"])
        self.tree.tag_configure("off", background=C["surface3"])

    def _build(self):
        sf = tk.Frame(self, bg=C["surface"])
        sf.pack(fill="x")
        self.s_total = self._stat(sf, "VEÍCULOS",    "—", C["blue"])
        self.s_on    = self._stat(sf, "IGN ON",      "—", C["green"])
        self.s_off   = self._stat(sf, "IGN OFF",     "—", C["text_mid"])
        self.s_nogps = self._stat(sf, "SEM GPS",     "—", C["danger"])
        self.s_vmax  = self._stat(sf, "MAIS RÁPIDO", "—", C["yellow"])
        self.s_upd   = self._stat(sf, "ATUALIZADO",  "—", C["text_dim"])
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        ctrl = tk.Frame(self, bg=C["bg"])
        ctrl.pack(fill="x", padx=10, pady=6)
        btn(ctrl, "⟳  ATUALIZAR", self.refresh, C["accent"]).pack(side="left")

        self.auto = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Auto 30s", variable=self.auto,
                       bg=C["bg"], fg=C["text_mid"], activebackground=C["bg"],
                       selectcolor=C["surface3"],
                       font=("Helvetica Neue", 9)).pack(side="left", padx=8)

        self.se = ent(ctrl, w=24)
        self.se.pack(side="left", padx=(20, 4), ipady=4)
        self.se.insert(0, "Filtrar placa / motorista...")
        self.se.bind("<FocusIn>",    lambda e: self._clr())
        self.se.bind("<KeyRelease>", lambda e: self._filter())
        btn(ctrl, "LIMPAR", self._clear_f, C["surface3"], C["text"]).pack(side="left", padx=4)

        cols = ("Placa","Veículo","Motorista","Cliente","Ign.","Vel. km/h",
                "GPS","Satél.","Bat.%","Volt.","Última GPS")
        ws   = (80, 130, 130, 130, 70, 80, 70, 60, 60, 70, 150)
        self.tree = mk_tree(self, cols, ws, "Dash", C["accent"], 18)
        self._reapply_tags()

        mk_export_btn(ctrl, self.tree).pack(side="right", padx=4)
        self.after(300,   self.refresh)
        self.after(30000, self._loop)

    def _stat(self, parent, label, val, col):
        f = tk.Frame(parent, bg=C["surface"])
        f.pack(side="left", padx=18, pady=8)
        tk.Label(f, text=label, bg=C["surface"], fg=C["text_dim"],
                 font=("Helvetica Neue", 7, "bold")).pack()
        lb = tk.Label(f, text=val, bg=C["surface"], fg=col,
                      font=("Helvetica Neue", 14, "bold"))
        lb.pack()
        return lb

    def _clr(self):
        if self.se.get() == "Filtrar placa / motorista...":
            self.se.delete(0, "end")

    def _filter(self):
        q = re.sub(r"[^A-Z0-9]", "", self.se.get().upper())
        for r in self.tree.get_children(): self.tree.delete(r)
        for ev in self._data:
            if not q \
               or q in re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_vei_placa", "")).upper()) \
               or q in re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_mot_nome",  "")).upper()):
                self._row(ev)

    def _clear_f(self):
        self.se.delete(0, "end")
        self.se.insert(0, "Filtrar placa / motorista...")
        self._render(self._data)

    def _row(self, ev):
        ign = safe_int(ev.get("ras_eve_ignicao", 0))
        self.tree.insert("", "end", values=(
            safe_str(ev.get("ras_vei_placa")),   safe_str(ev.get("ras_vei_veiculo")),
            safe_str(ev.get("ras_mot_nome")),     safe_str(ev.get("ras_cli_desc")),
            "🟢 ON" if ign else "⚫ OFF",
            safe_int(ev.get("ras_eve_velocidade", 0)),
            "✓ OK" if safe_int(ev.get("ras_eve_gps_status", 0)) else "✗ FALHA",
            safe_int(ev.get("ras_eve_satelites", 0)),
            f"{safe_int(ev.get('ras_eve_porc_bat_backup', 100))}%",
            f"{safe_float(ev.get('ras_eve_voltagem', 0)):.1f}V",
            safe_str(ev.get("ras_eve_data_gps")),
        ), tags=("on" if ign else "off",))

    def _render(self, data):
        for r in self.tree.get_children(): self.tree.delete(r)
        on = off = no_gps = 0; vmax = 0
        for ev in data:
            ign = safe_int(ev.get("ras_eve_ignicao", 0))
            gps = safe_int(ev.get("ras_eve_gps_status", 0))
            vel = safe_int(ev.get("ras_eve_velocidade", 0))
            if ign: on  += 1
            else:   off += 1
            if not gps: no_gps += 1
            vmax = max(vmax, vel)
            self._row(ev)
        self.s_total.config(text=str(len(data)))
        self.s_on.config(   text=str(on))
        self.s_off.config(  text=str(off))
        self.s_nogps.config(text=str(no_gps))
        self.s_vmax.config( text=f"{vmax} km/h")
        self.s_upd.config(  text=now_str())

    def refresh(self):
        def task():
            d = get_all_events(); self._data = d; self._render(d)
        threading.Thread(target=task, daemon=True).start()

    def _loop(self):
        if self.auto.get(): self.refresh()
        self.after(30000, self._loop)