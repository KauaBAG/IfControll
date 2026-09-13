"""
tabs/telemetria/sub_percurso.py
Sub-aba 1 — Relatório de Percurso.
Mostra todos os pontos coletados no período com KPIs de distância/velocidade.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import calc_percurso
from core.models import safe_int, safe_float, safe_str

_COLS   = ("Data/Hora", "Velocidade", "Ignição", "GPS", "Satélites",
           "Voltagem", "Bateria %", "Latitude", "Longitude")
_WIDTHS = (145, 90, 75, 65, 80, 80, 75, 120, 120)


class PercursoMixin:

    def _build_percurso(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📍 Percurso ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._pkpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("dist",   "DISTÂNCIA",   C["blue"]),
            ("dur",    "DURAÇÃO",     C["text_mid"]),
            ("vmed",   "VEL MÉDIA",   C["accent"]),
            ("vmax",   "VEL MÁXIMA",  C["danger"]),
            ("pontos", "PONTOS",      C["text_dim"]),
            ("inicio", "INÍCIO",      C["text_dim"]),
            ("fim",    "FIM",         C["text_dim"]),
        ]:
            self._pkpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Treeview
        apply_treeview_style("TPerc", C["blue"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        self._tree_perc = ttk.Treeview(
            inner, columns=_COLS, show="headings",
            style="TPerc.Treeview", height=20,
        )
        for c, w in zip(_COLS, _WIDTHS):
            self._tree_perc.heading(c, text=c, anchor="w")
            self._tree_perc.column(c, width=w, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(inner, orient="vertical",  command=self._tree_perc.yview)
        hsb = ttk.Scrollbar(inner, orient="horizontal", command=self._tree_perc.xview)
        self._tree_perc.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree_perc.pack(fill="both", expand=True)

        ctrl = tk.Frame(f, bg=C["bg"])
        ctrl.pack(fill="x", padx=8, pady=4)
        mk_export_btn(ctrl, self._tree_perc).pack(side="right")

        register_theme_listener(lambda: apply_treeview_style("TPerc", C["blue"]))

    def _render_percurso(self, points: list[dict]):
        for r in self._tree_perc.get_children():
            self._tree_perc.delete(r)

        for p in points:
            ign = safe_int(p.get("ras_eve_ignicao", 0))
            gps = safe_int(p.get("ras_eve_gps_status", 0))
            self._tree_perc.insert("", "end", tags=("on" if ign else "off",), values=(
                safe_str(p.get("ras_eve_data_gps")),
                f"{safe_int(p.get('ras_eve_velocidade', 0))} km/h",
                "🟢 ON" if ign else "⚫ OFF",
                "✓" if gps else "✗",
                safe_int(p.get("ras_eve_satelites", 0)),
                f"{safe_float(p.get('ras_eve_voltagem', 0)):.1f}V",
                f"{safe_int(p.get('ras_eve_porc_bat_backup', 100))}%",
                safe_str(p.get("ras_eve_latitude")),
                safe_str(p.get("ras_eve_longitude")),
            ))

        self._tree_perc.tag_configure("on",  background=C["surface2"])
        self._tree_perc.tag_configure("off", background=C["surface3"])

        m = calc_percurso(points)
        if m:
            self._pkpis["dist"].config(  text=f"{m['dist_km']} km")
            self._pkpis["dur"].config(   text=f"{m['duracao_min']:.0f} min")
            self._pkpis["vmed"].config(  text=f"{m['vel_media']} km/h")
            self._pkpis["vmax"].config(  text=f"{m['vel_max']} km/h")
            self._pkpis["pontos"].config(text=str(m["n_pontos"]))
            self._pkpis["inicio"].config(text=m["inicio"])
            self._pkpis["fim"].config(   text=m["fim"])
