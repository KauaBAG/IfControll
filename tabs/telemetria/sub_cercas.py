"""
tabs/telemetria/sub_cercas.py
Sub-aba 7 — Análise de Cercas.
Usa GET /fence/vehicle para mostrar entradas, saídas e tempo de permanência
por cerca eletrônica no período consultado.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import calc_cercas

_COLS_CERCA = ("Cerca", "Entradas", "Última Entrada", "Última Saída", "Permanência")
_WIDTHS_C   = (180, 70, 145, 145, 100)

_COLS_DETALHE = ("Cerca", "Entrada", "Saída", "Permanência")
_WIDTHS_D     = (180, 145, 145, 100)


class CercasMixin:

    def _build_cercas(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 🔲 Cercas ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._fkpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("total",  "TOTAL VISITAS",  C["accent"]),
            ("cercas", "CERCAS ATIVAS",  C["blue"]),
        ]:
            self._fkpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        content = tk.Frame(f, bg=C["bg"])
        content.pack(fill="both", expand=True)

        # Esquerda: resumo por cerca
        left = tk.Frame(content, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)
        lbl(left, "Resumo por Cerca", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TCerca", C["accent"])
        inner_l = tk.Frame(left, bg=C["bg"])
        inner_l.pack(fill="both", expand=True)
        self._tree_cerca = ttk.Treeview(
            inner_l, columns=_COLS_CERCA, show="headings",
            style="TCerca.Treeview", height=14,
        )
        for c, w in zip(_COLS_CERCA, _WIDTHS_C):
            self._tree_cerca.heading(c, text=c, anchor="w")
            self._tree_cerca.column(c, width=w, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(inner_l, orient="vertical", command=self._tree_cerca.yview)
        self._tree_cerca.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_cerca.pack(fill="both", expand=True)
        mk_export_btn(left, self._tree_cerca).pack(anchor="e", padx=8, pady=4)

        # Direita: detalhe de eventos
        right = tk.Frame(content, bg=C["bg"], width=600)
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))
        lbl(right, "Eventos de Cerca (Entradas/Saídas)", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TCercaDet", C["blue"])
        inner_r = tk.Frame(right, bg=C["bg"])
        inner_r.pack(fill="both", expand=True)
        self._tree_cerca_det = ttk.Treeview(
            inner_r, columns=_COLS_DETALHE, show="headings",
            style="TCercaDet.Treeview", height=14,
        )
        for c, w in zip(_COLS_DETALHE, _WIDTHS_D):
            self._tree_cerca_det.heading(c, text=c, anchor="w")
            self._tree_cerca_det.column(c, width=w, anchor="w", stretch=True)
        vsb2 = ttk.Scrollbar(inner_r, orient="vertical",
                              command=self._tree_cerca_det.yview)
        self._tree_cerca_det.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self._tree_cerca_det.pack(fill="both", expand=True)
        mk_export_btn(right, self._tree_cerca_det).pack(anchor="e", padx=8, pady=4)

        # Mensagem de sem dados
        self._cerca_info = lbl(f, "Nenhum evento de cerca no período consultado.",
                                9, col=C["text_dim"])
        self._cerca_info.pack(anchor="w", padx=14, pady=4)

        register_theme_listener(lambda: (
            apply_treeview_style("TCerca",    C["accent"]),
            apply_treeview_style("TCercaDet", C["blue"]),
        ))

    def _render_cercas(self, fence_events: list[dict]):
        m = calc_cercas(fence_events)

        self._fkpis["total"].config( text=str(m["total_visitas"]))
        self._fkpis["cercas"].config(text=str(len(m["cercas"])))

        # Resumo
        for r in self._tree_cerca.get_children():
            self._tree_cerca.delete(r)
        for c in m["cercas"]:
            self._tree_cerca.insert("", "end", values=(
                c["nome"], c["visitas"],
                c["ultima_entrada"], c["ultima_saida"],
                c["permanencia_total"],
            ))

        # Detalhe bruto
        for r in self._tree_cerca_det.get_children():
            self._tree_cerca_det.delete(r)
        for ev in fence_events:
            self._tree_cerca_det.insert("", "end", values=(
                ev.get("ras_cer_observacao", "—"),
                ev.get("data_entrada", "—"),
                ev.get("data_saida", "—"),
                ev.get("tempo_permanencia", "—"),
            ))

        if m["total_visitas"] == 0:
            self._cerca_info.config(text="Nenhum evento de cerca no período consultado.")
            self._cerca_info.pack(anchor="w", padx=14, pady=4)
        else:
            self._cerca_info.pack_forget()
