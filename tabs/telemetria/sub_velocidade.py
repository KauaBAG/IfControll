"""
tabs/telemetria/sub_velocidade.py
Sub-aba 2 — Análise de Velocidade.
Distribuição por faixas, barras visuais, lista de picos de excesso.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import calc_velocidade
from core.models import safe_int

_COLS_P   = ("Data/Hora", "Velocidade", "Placa", "Localização")
_WIDTHS_P = (145, 90, 90, 200)


class VelocidadeMixin:

    def _build_velocidade(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" ⚡ Velocidade ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._vkpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("vmax",   "VEL MÁXIMA",       C["danger"]),
            ("vmed",   "VEL MÉDIA",        C["accent"]),
            ("pct",    "% ACIMA LIMITE",   C["warn"]),
            ("npicos", "EVENTOS EXCESSO",  C["orange"]),
            ("limite", "LIMITE CONF.",     C["text_mid"]),
        ]:
            self._vkpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Barras de distribuição
        lbl(f, "Distribuição por Faixa de Velocidade", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(10, 4))
        self._vel_bars_frame = tk.Frame(f, bg=C["bg"])
        self._vel_bars_frame.pack(fill="x", padx=14)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Picos
        lbl(f, "Eventos de Excesso de Velocidade", 10, True,
            C["warn"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TVel", C["warn"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        self._tree_vel = ttk.Treeview(
            inner, columns=_COLS_P, show="headings",
            style="TVel.Treeview", height=10,
        )
        for c, w in zip(_COLS_P, _WIDTHS_P):
            self._tree_vel.heading(c, text=c, anchor="w")
            self._tree_vel.column(c, width=w, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._tree_vel.yview)
        self._tree_vel.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_vel.pack(fill="both", expand=True)

        mk_export_btn(f, self._tree_vel).pack(anchor="e", padx=8, pady=4)

        register_theme_listener(lambda: apply_treeview_style("TVel", C["warn"]))

    def _render_velocidade(self, points: list[dict], limite: int = 80):
        m     = calc_velocidade(points, limite)
        vels  = [safe_int(p.get("ras_eve_velocidade", 0)) for p in points]
        vpos  = [v for v in vels if v > 0]
        vmax  = max(vpos, default=0)
        vmed  = round(sum(vpos) / len(vpos), 1) if vpos else 0

        self._vkpis["vmax"].config(  text=f"{vmax} km/h")
        self._vkpis["vmed"].config(  text=f"{vmed} km/h")
        self._vkpis["pct"].config(   text=f"{m['pct_acima_limite']}%")
        self._vkpis["npicos"].config(text=str(len(m["picos"])))
        self._vkpis["limite"].config(text=f"{limite} km/h")

        # Barras
        for w in self._vel_bars_frame.winfo_children():
            w.destroy()

        cores = {
            "Parado (0)":       C["text_dim"],
            "Lento (1–40)":     C["success"],
            "Normal (41–80)":   C["accent"],
            "Acima limite":     C["warn"],
            "Perigoso (>120)":  C["danger"],
        }
        total = sum(m["distribuicao"].values()) or 1
        for nome, cnt in m["distribuicao"].items():
            pct = cnt / total * 100
            row = tk.Frame(self._vel_bars_frame, bg=C["bg"])
            row.pack(fill="x", pady=2)
            lbl(row, f"{nome}:", 9, col=C["text_mid"], width=20).pack(side="left")
            bg = tk.Frame(row, bg=C["surface3"], height=16, width=280)
            bg.pack(side="left", padx=6)
            bg.pack_propagate(False)
            fill_w = max(1, int(280 * pct / 100))
            tk.Frame(bg, bg=cores.get(nome, C["accent"]),
                     width=fill_w, height=16).place(x=0, y=0)
            lbl(row, f"{cnt:,}  ({pct:.1f}%)", 9,
                col=cores.get(nome, C["accent"])).pack(side="left")

        # Picos
        for r in self._tree_vel.get_children():
            self._tree_vel.delete(r)
        for p in m["picos"]:
            self._tree_vel.insert("", "end", values=(
                p["data"], f"{p['vel']} km/h", p["placa"],
                f"{p['lat']:.4f}, {p['lon']:.4f}",
            ))
        self._tree_vel.tag_configure("crit", background="#1a0505")
        for iid in self._tree_vel.get_children():
            raw = str(self._tree_vel.item(iid)["values"][1]).replace(" km/h", "")
            try:
                if int(raw) > 120:
                    self._tree_vel.item(iid, tags=("crit",))
            except ValueError:
                pass
