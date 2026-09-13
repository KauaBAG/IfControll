"""
tabs/telemetria/sub_ociosidade.py
Sub-aba 3 — Análise de Ociosidade.
Motor ligado com velocidade = 0. Períodos, consumo desperdiçado.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import calc_ociosidade

_COLS   = ("Início", "Fim", "Duração (min)", "Localização (lat, lon)")
_WIDTHS = (145, 145, 110, 240)


class OciosidadeMixin:

    def _build_ociosidade(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 😴 Ociosidade ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._okpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("min",     "TEMPO OCIOSO",    C["warn"]),
            ("h",       "HORAS OCIOSAS",   C["orange"]),
            ("litros",  "LITROS PERDIDOS", C["danger"]),
            ("n",       "Nº PERÍODOS",     C["text_mid"]),
        ]:
            self._okpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Info
        info = tk.Frame(f, bg=C["surface2"])
        info.pack(fill="x", padx=12, pady=8)
        lbl(info,
            "Ociosidade = motor ligado (ignição ON) com velocidade 0 km/h.  "
            "Consumo estimado: 0,5 L/h em marcha lenta.",
            9, col=C["text_dim"], bg=C["surface2"]).pack(padx=10, pady=6, anchor="w")

        # Tree
        lbl(f, "Períodos Ociosos  (ordenados por maior duração)", 10, True,
            C["warn"]).pack(anchor="w", padx=14, pady=(4, 4))

        apply_treeview_style("TOcio", C["warn"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        self._tree_ocio = ttk.Treeview(
            inner, columns=_COLS, show="headings",
            style="TOcio.Treeview", height=18,
        )
        for c, w in zip(_COLS, _WIDTHS):
            self._tree_ocio.heading(c, text=c, anchor="w")
            self._tree_ocio.column(c, width=w, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._tree_ocio.yview)
        self._tree_ocio.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_ocio.pack(fill="both", expand=True)

        mk_export_btn(f, self._tree_ocio).pack(anchor="e", padx=8, pady=4)

        register_theme_listener(lambda: apply_treeview_style("TOcio", C["warn"]))

    def _render_ociosidade(self, points: list[dict]):
        consumo_l_h = getattr(self, "_ocio_consumo_l_h", 0.5)
        m = calc_ociosidade(points, consumo_l_h=consumo_l_h)

        self._okpis["min"].config(   text=f"{m['ocioso_min']} min")
        self._okpis["h"].config(     text=f"{m['ocioso_h']} h")
        self._okpis["litros"].config(text=f"{m['consumo_l']} L")
        self._okpis["n"].config(     text=str(m["n_periodos"]))

        for r in self._tree_ocio.get_children():
            self._tree_ocio.delete(r)
        for p in m["periodos"]:
            tag = "longo" if p["min"] > 30 else ("medio" if p["min"] > 10 else "")
            self._tree_ocio.insert("", "end", tags=(tag,), values=(
                p["inicio"], p["fim"], f"{p['min']} min", p["local"],
            ))
        self._tree_ocio.tag_configure("longo", background="#1a0d00")
        self._tree_ocio.tag_configure("medio", background="#1a1300")
