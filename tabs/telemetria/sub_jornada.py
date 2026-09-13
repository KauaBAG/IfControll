"""
tabs/telemetria/sub_jornada.py
Sub-aba 10 — Jornada de Motoristas.
Cruza /workingday/interval com os dados de telemetria do veículo.
Exibe horas dirigidas, ranking e conformidade com jornada legal.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import calc_jornada

_COLS_JOR   = ("Motorista", "Horas Jornada", "Registros", "Status")
_WIDTHS_JOR = (200, 120, 90, 120)

_COLS_DET   = ("Campo", "Valor")
_WIDTHS_DET = (200, 280)


class JornadaMixin:

    def _build_jornada(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 👤 Jornada ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._jkpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("motoristas", "MOTORISTAS",     C["blue"]),
            ("total_h",    "HORAS TOTAIS",   C["accent"]),
            ("mot_nome",   "MOTORISTA ATIVO", C["text_mid"]),
        ]:
            self._jkpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        info = tk.Frame(f, bg=C["surface2"])
        info.pack(fill="x", padx=12, pady=8)
        lbl(info,
            "Dados de jornada via GET /workingday/interval — cruzado com telemetria do veículo.\n"
            "Motorista identificado pelo campo ras_mot_nome nos eventos.",
            9, col=C["text_dim"], bg=C["surface2"]).pack(padx=10, pady=6, anchor="w")

        content = tk.Frame(f, bg=C["bg"])
        content.pack(fill="both", expand=True)

        # Esquerda — ranking de motoristas
        left = tk.Frame(content, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)
        lbl(left, "Jornada por Motorista", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TJor", C["accent"])
        inner_l = tk.Frame(left, bg=C["bg"])
        inner_l.pack(fill="both", expand=True)
        self._tree_jor = ttk.Treeview(
            inner_l, columns=_COLS_JOR, show="headings",
            style="TJor.Treeview", height=16,
        )
        for c, w in zip(_COLS_JOR, _WIDTHS_JOR):
            self._tree_jor.heading(c, text=c, anchor="w")
            self._tree_jor.column(c, width=w, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(inner_l, orient="vertical", command=self._tree_jor.yview)
        self._tree_jor.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_jor.pack(fill="both", expand=True)
        mk_export_btn(left, self._tree_jor).pack(anchor="e", padx=8, pady=4)

        # Direita — motorista identificado nos eventos
        right = tk.Frame(content, bg=C["surface2"], width=320)
        right.pack(side="right", fill="y", padx=(4, 0))
        right.pack_propagate(False)

        lbl(right, "Motorista nos Eventos de Telemetria", 10, True,
            C["accent"], bg=C["surface2"]).pack(padx=10, pady=(10, 4), anchor="w")

        self._jor_driver_frame = tk.Frame(right, bg=C["surface2"])
        self._jor_driver_frame.pack(fill="x", padx=10)
        self._jor_no_driver = lbl(right,
            "Nenhum motorista identificado\nnos eventos do período.",
            9, col=C["text_dim"], bg=C["surface2"])
        self._jor_no_driver.pack(pady=20)

        register_theme_listener(lambda: apply_treeview_style("TJor", C["accent"]))

    def _render_jornada(self, points: list[dict], workingday: list[dict]):
        m = calc_jornada(workingday)

        self._jkpis["motoristas"].config(text=str(len(m["motoristas"])))
        self._jkpis["total_h"].config(   text=f"{m['total_horas']}h")

        # Motorista identificado nos eventos de telemetria
        nomes_ev = {}
        for p in points:
            nm = p.get("ras_mot_nome")
            if nm and nm not in ("PADRAO", "—", "", None):
                nomes_ev[nm] = nomes_ev.get(nm, 0) + 1
        if nomes_ev:
            nome_principal = max(nomes_ev, key=nomes_ev.get)
            self._jkpis["mot_nome"].config(text=nome_principal)
        else:
            self._jkpis["mot_nome"].config(text="Não identificado")

        # Tree de jornada
        for r in self._tree_jor.get_children():
            self._tree_jor.delete(r)

        for mot in m["motoristas"]:
            # Alerta se > 8h (jornada legal BR)
            horas = round(mot["horas"], 2)
            status = "⚠ Excesso" if horas > 8 else ("✔ Normal" if horas > 0 else "—")
            tag    = "excesso" if horas > 8 else "normal"
            self._tree_jor.insert("", "end", tags=(tag,), values=(
                mot["nome"], f"{horas}h", len(mot["registros"]), status,
            ))
        self._tree_jor.tag_configure("excesso", foreground=C["warn"])
        self._tree_jor.tag_configure("normal",  foreground=C["success"])

        # Painel direito — motoristas dos eventos
        for w in self._jor_driver_frame.winfo_children():
            w.destroy()
        if nomes_ev:
            self._jor_no_driver.pack_forget()
            for nome, cnt in sorted(nomes_ev.items(), key=lambda x: x[1], reverse=True):
                card = tk.Frame(self._jor_driver_frame, bg=C["surface3"],
                                highlightthickness=1, highlightbackground=C["border"])
                card.pack(fill="x", pady=3)
                lbl(card, nome, 9, True, C["accent"], bg=C["surface3"]).pack(
                    padx=8, pady=(6, 2), anchor="w")
                lbl(card, f"{cnt} eventos registrados", 8, col=C["text_dim"],
                    bg=C["surface3"]).pack(padx=8, pady=(0, 6), anchor="w")
        else:
            self._jor_no_driver.pack(pady=20)

        # Se sem dados de workingday
        if not workingday:
            self._tree_jor.insert("", "end", values=(
                "— Sem dados de jornada para este período —", "", "", "",
            ))