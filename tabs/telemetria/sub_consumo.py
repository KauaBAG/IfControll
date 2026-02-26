"""
tabs/telemetria/sub_consumo.py
Sub-aba 6 — Consumo Estimado de Combustível.
Parâmetros editáveis (km/L, preço/L, consumo ócio). Breakdown visual.
"""

import tkinter as tk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, ent, btn
from ._calc import calc_consumo, calc_percurso, calc_ociosidade
from core.models import safe_float


class ConsumoMixin:

    def _build_consumo(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" ⛽ Consumo ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._ckpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("dist",    "KM PERCORRIDOS",   C["blue"]),
            ("l_mov",   "L EM MOVIMENTO",   C["accent"]),
            ("l_ocio",  "L EM ÓCIO",        C["warn"]),
            ("l_total", "TOTAL (L)",         C["orange"]),
            ("custo",   "CUSTO EST. (R$)",  C["success"]),
        ]:
            self._ckpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Parâmetros
        params = tk.Frame(f, bg=C["surface2"])
        params.pack(fill="x", padx=12, pady=10)
        lbl(params, "⚙  Parâmetros de Cálculo", 10, True,
            C["accent"], bg=C["surface2"]).pack(anchor="w", padx=10, pady=(8, 4))

        row1 = tk.Frame(params, bg=C["surface2"])
        row1.pack(fill="x", padx=10, pady=4)
        lbl(row1, "Consumo (km/L):", 9, col=C["text_mid"],
            bg=C["surface2"]).pack(side="left", padx=(0, 4))
        self._e_cons_km = ent(row1, w=8)
        self._e_cons_km.pack(side="left", ipady=3)
        self._e_cons_km.insert(0, "10")

        lbl(row1, "  Preço/L (R$):", 9, col=C["text_mid"],
            bg=C["surface2"]).pack(side="left", padx=(12, 4))
        self._e_preco = ent(row1, w=8)
        self._e_preco.pack(side="left", ipady=3)
        self._e_preco.insert(0, "5.80")

        lbl(row1, "  Ócio (L/h):", 9, col=C["text_mid"],
            bg=C["surface2"]).pack(side="left", padx=(12, 4))
        self._e_ocio_lh = ent(row1, w=8)
        self._e_ocio_lh.pack(side="left", ipady=3)
        self._e_ocio_lh.insert(0, "0.5")

        btn(params, "↻  RECALCULAR", self._recalcular_consumo,
            C["accent"]).pack(anchor="e", padx=10, pady=(0, 8))

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Breakdown
        lbl(f, "Distribuição do Consumo", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(12, 6))
        self._cons_breakdown = tk.Frame(f, bg=C["bg"])
        self._cons_breakdown.pack(fill="x", padx=14)

        # Notas
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(12, 0))
        lbl(f, "ℹ  Notas", 9, True, C["text_mid"]).pack(anchor="w", padx=14, pady=(8, 2))
        lbl(f,
            "• Em movimento: Distância ÷ Consumo km/L.\n"
            "• Em ócio: Horas ociosas × Consumo L/h (padrão 0,5 L/h).\n"
            "• Valores estimados. Consumo real varia com carga, relevo e estilo de condução.\n"
            "• Configure o consumo real do veículo em Vehicles > Update.",
            9, col=C["text_dim"]).pack(anchor="w", padx=14, pady=(0, 10))

    def _recalcular_consumo(self):
        if hasattr(self, "_cached_points") and self._cached_points:
            self._render_consumo(self._cached_points)

    def _render_consumo(self, points: list[dict]):
        km_l     = safe_float(self._e_cons_km.get()) or 10.0
        preco    = safe_float(self._e_preco.get()) or 5.80
        ocio_l_h = safe_float(self._e_ocio_lh.get()) or 0.5

        # Sincroniza valor de ócio para sub_ociosidade
        self._ocio_consumo_l_h = ocio_l_h

        perc = calc_percurso(points)
        ocio = calc_ociosidade(points, consumo_l_h=ocio_l_h)
        m    = calc_consumo(perc, ocio, km_l, ocio_l_h, preco)

        self._ckpis["dist"].config(   text=f"{m['dist_km']} km")
        self._ckpis["l_mov"].config(  text=f"{m['l_movimento']} L")
        self._ckpis["l_ocio"].config( text=f"{m['l_ocio']} L")
        self._ckpis["l_total"].config(text=f"{m['l_total']} L")
        self._ckpis["custo"].config(  text=f"R$ {m['custo_brl']:.2f}")

        for w in self._cons_breakdown.winfo_children():
            w.destroy()
        total_l = m["l_total"] or 1
        for label, valor, cor in [
            ("Em movimento", m["l_movimento"], C["accent"]),
            ("Em ócio",      m["l_ocio"],      C["warn"]),
        ]:
            pct = valor / total_l * 100
            row = tk.Frame(self._cons_breakdown, bg=C["bg"])
            row.pack(fill="x", pady=3)
            lbl(row, f"{label}:", 9, col=C["text_mid"], width=14).pack(side="left")
            bg = tk.Frame(row, bg=C["surface3"], height=18, width=300)
            bg.pack(side="left", padx=6)
            bg.pack_propagate(False)
            fill_w = max(2, int(300 * pct / 100))
            tk.Frame(bg, bg=cor, width=fill_w, height=18).place(x=0, y=0)
            lbl(row, f"{valor} L  ({pct:.1f}%)", 9, col=cor).pack(side="left")
