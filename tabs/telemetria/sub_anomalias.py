"""
tabs/telemetria/sub_anomalias.py
Sub-aba 9 — Detecção de Anomalias.
GPS parado com ignição ON, variações de voltagem, velocidades impossíveis,
alertas do período cruzados com telemetria.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import calc_anomalias, calc_alertas

_COLS_ANOM   = ("Tipo", "Descrição", "Data/Hora", "Lat", "Lon")
_WIDTHS_ANOM = (180, 320, 145, 110, 110)

_COLS_ALERT  = ("Descrição", "Data", "Veículo", "Status")
_WIDTHS_ALERT = (200, 145, 100, 90)


class AnomaliasMixin:

    def _build_anomalias(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 🔍 Anomalias ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._ankpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("anom",    "ANOMALIAS DETECT.",  C["danger"]),
            ("alertas", "ALERTAS PERÍODO",    C["warn"]),
            ("abertos", "ALERTAS ABERTOS",    C["orange"]),
            ("fechados","ALERTAS FECHADOS",   C["success"]),
        ]:
            self._ankpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        content = tk.Frame(f, bg=C["bg"])
        content.pack(fill="both", expand=True)

        # Esquerda — anomalias de telemetria
        left = tk.Frame(content, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)

        lbl(left, "Anomalias Detectadas na Telemetria", 10, True,
            C["danger"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TAnom", C["danger"])
        inner_l = tk.Frame(left, bg=C["bg"])
        inner_l.pack(fill="both", expand=True)
        self._tree_anom = ttk.Treeview(
            inner_l, columns=_COLS_ANOM, show="headings",
            style="TAnom.Treeview", height=12,
        )
        for c, w in zip(_COLS_ANOM, _WIDTHS_ANOM):
            self._tree_anom.heading(c, text=c, anchor="w")
            self._tree_anom.column(c, width=w, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(inner_l, orient="vertical", command=self._tree_anom.yview)
        self._tree_anom.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_anom.pack(fill="both", expand=True)
        mk_export_btn(left, self._tree_anom).pack(anchor="e", padx=8, pady=4)

        # Direita — alertas da API
        right = tk.Frame(content, bg=C["bg"])
        right.pack(side="right", fill="both", expand=True, padx=(4, 0))

        lbl(right, "Alertas do Período (/alerts/period)", 10, True,
            C["warn"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TAlert", C["warn"])
        inner_r = tk.Frame(right, bg=C["bg"])
        inner_r.pack(fill="both", expand=True)
        self._tree_alert = ttk.Treeview(
            inner_r, columns=_COLS_ALERT, show="headings",
            style="TAlert.Treeview", height=12,
        )
        for c, w in zip(_COLS_ALERT, _WIDTHS_ALERT):
            self._tree_alert.heading(c, text=c, anchor="w")
            self._tree_alert.column(c, width=w, anchor="w", stretch=True)
        vsb2 = ttk.Scrollbar(inner_r, orient="vertical", command=self._tree_alert.yview)
        self._tree_alert.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self._tree_alert.pack(fill="both", expand=True)
        mk_export_btn(right, self._tree_alert).pack(anchor="e", padx=8, pady=4)

        # Painel por tipo de alerta
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(4, 0))
        lbl(f, "Alertas por Tipo", 10, True, C["accent"]).pack(
            anchor="w", padx=14, pady=(6, 4))
        self._alert_tipo_frame = tk.Frame(f, bg=C["bg"])
        self._alert_tipo_frame.pack(fill="x", padx=14, pady=(0, 8))

        register_theme_listener(lambda: (
            apply_treeview_style("TAnom",  C["danger"]),
            apply_treeview_style("TAlert", C["warn"]),
        ))

    def _render_anomalias(self, points: list[dict], alerts: list[dict]):
        # Anomalias de telemetria
        anomalias = calc_anomalias(points)
        for r in self._tree_anom.get_children():
            self._tree_anom.delete(r)
        for a in anomalias:
            tag = "crit" if a["tipo"] == "VELOCIDADE_IMPOSSIVEL" else "warn"
            self._tree_anom.insert("", "end", tags=(tag,), values=(
                a["tipo"], a["descricao"], a["data"],
                f"{a['lat']:.4f}", f"{a['lon']:.4f}",
            ))
        self._tree_anom.tag_configure("crit", foreground=C["danger"])
        self._tree_anom.tag_configure("warn", foreground=C["warn"])

        # Alertas da API
        m = calc_alertas(alerts)
        self._ankpis["anom"].config(   text=str(len(anomalias)))
        self._ankpis["alertas"].config(text=str(m["total"]))
        self._ankpis["abertos"].config(text=str(m["abertos"]))
        self._ankpis["fechados"].config(text=str(m["fechados"]))

        for r in self._tree_alert.get_children():
            self._tree_alert.delete(r)
        for a in alerts:
            baixado = a.get("ras_eal_baixado", 0)
            status  = "✔ Fechado" if baixado else "⚠ Aberto"
            tag     = "fechado" if baixado else "aberto"
            self._tree_alert.insert("", "end", tags=(tag,), values=(
                a.get("ras_eal_descricao", "—"),
                a.get("ras_eal_data_alerta", "—"),
                str(a.get("ras_eal_id_veiculo", "—")),
                status,
            ))
        self._tree_alert.tag_configure("aberto",  foreground=C["warn"])
        self._tree_alert.tag_configure("fechado", foreground=C["success"])

        # Por tipo de alerta
        for w in self._alert_tipo_frame.winfo_children():
            w.destroy()
        total_alerts = m["total"] or 1
        for tipo, cnt in list(m["por_tipo"].items())[:10]:
            pct = cnt / total_alerts * 100
            row = tk.Frame(self._alert_tipo_frame, bg=C["bg"])
            row.pack(fill="x", pady=2)
            lbl(row, f"{tipo}:", 9, col=C["text_mid"], width=22).pack(side="left")
            bg = tk.Frame(row, bg=C["surface3"], height=14, width=240)
            bg.pack(side="left", padx=6)
            bg.pack_propagate(False)
            tk.Frame(bg, bg=C["warn"],
                     width=max(2, int(240 * pct / 100)), height=14).place(x=0, y=0)
            lbl(row, f"{cnt}  ({pct:.1f}%)", 9, col=C["warn"]).pack(side="left")