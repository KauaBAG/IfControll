"""
tabs/telemetria/sub_resumo.py
Sub-aba 8 — Resumo Geral.
KPIs consolidados, mapa de calor por hora do dia e tabela exportável completa.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import (calc_percurso, calc_velocidade, calc_ociosidade,
                    calc_motor, calc_risco, calc_consumo, calc_heatmap_hora)

_COLS_EXP   = ("Métrica", "Valor")
_WIDTHS_EXP = (280, 200)


class ResumoMixin:

    def _build_resumo(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📊 Resumo ")

        # Header do veículo
        veh_bar = tk.Frame(f, bg=C["surface3"])
        veh_bar.pack(fill="x")
        self._resumo_veh_lbl = lbl(
            veh_bar,
            "Selecione um veículo e período para gerar o resumo",
            10, True, C["text_mid"], bg=C["surface3"]
        )
        self._resumo_veh_lbl.pack(side="left", padx=14, pady=8)
        self._resumo_score_lbl = lbl(
            veh_bar, "Score: —", 10, True, C["accent"], bg=C["surface3"]
        )
        self._resumo_score_lbl.pack(side="right", padx=14)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Grade de KPIs (4 colunas, 3 linhas)
        self._resumo_grid = tk.Frame(f, bg=C["bg"])
        self._resumo_grid.pack(fill="x", padx=12, pady=10)
        self._rskpis: dict[str, tk.Label] = {}

        defs = [
            ("dist",    "KM PERCORRIDOS",   C["blue"]),
            ("dur",     "DURAÇÃO",          C["text_mid"]),
            ("vmax",    "VEL MÁXIMA",       C["danger"]),
            ("vmed",    "VEL MÉDIA",        C["accent"]),
            ("ocio_h",  "HORAS OCIOSAS",    C["warn"]),
            ("l_total", "COMBUSTÍVEL EST.", C["orange"]),
            ("custo",   "CUSTO EST.",       C["success"]),
            ("score",   "SCORE RISCO",      C["danger"]),
            ("ligado",  "TEMPO LIGADO",     C["success"]),
            ("ciclos",  "CICLOS IGN.",      C["accent"]),
            ("volt",    "VOLT MÉDIA",       C["blue"]),
            ("bat",     "BATERIA MÉDIA",    C["text_mid"]),
        ]
        row_fr = None
        for i, (key, title, col) in enumerate(defs):
            if i % 4 == 0:
                row_fr = tk.Frame(self._resumo_grid, bg=C["bg"])
                row_fr.pack(fill="x")
            self._rskpis[key] = self._tele_kpi(row_fr, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(4, 0))

        # Mapa de calor por hora
        lbl(f, "Atividade por Hora do Dia", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(10, 6))

        heat_wrap = tk.Frame(f, bg=C["bg"])
        heat_wrap.pack(fill="x", padx=14, pady=(0, 8))
        self._heat_cells: dict[int, tk.Frame]  = {}
        self._heat_cnts:  dict[int, tk.Label]  = {}
        for h in range(24):
            col_f = tk.Frame(heat_wrap, bg=C["bg"])
            col_f.pack(side="left", padx=1)
            lbl(col_f, f"{h:02d}", 7, col=C["text_dim"]).pack()
            cell = tk.Frame(col_f, bg=C["surface3"], width=28, height=50)
            cell.pack()
            cell.pack_propagate(False)
            cnt_lbl = tk.Label(cell, text="",
                               bg=C["surface3"], fg=C["text_dim"],
                               font=("Helvetica Neue", 6))
            cnt_lbl.pack(expand=True)
            self._heat_cells[h] = cell
            self._heat_cnts[h]  = cnt_lbl

        # Tabela de exportação
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(4, 0))
        lbl(f, "Exportar Resumo Completo", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TResumExp", C["accent"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="x", padx=12)
        self._tree_resum = ttk.Treeview(
            inner, columns=_COLS_EXP, show="headings",
            style="TResumExp.Treeview", height=8,
        )
        for c, w in zip(_COLS_EXP, _WIDTHS_EXP):
            self._tree_resum.heading(c, text=c, anchor="w")
            self._tree_resum.column(c, width=w, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._tree_resum.yview)
        self._tree_resum.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_resum.pack(fill="x", expand=True)
        mk_export_btn(f, self._tree_resum).pack(anchor="e", padx=12, pady=6)

        register_theme_listener(lambda: apply_treeview_style("TResumExp", C["accent"]))

    def _render_resumo(self, points: list[dict], vei_meta: dict, limite_vel: int = 80):
        perc = calc_percurso(points)
        vel  = calc_velocidade(points, limite_vel)
        ocio = calc_ociosidade(points)
        mot  = calc_motor(points)
        risk = calc_risco(perc, vel, ocio, mot, points)
        cons = calc_consumo(perc, ocio)
        heat = calc_heatmap_hora(points)

        placa = vei_meta.get("ras_vei_placa", "—")
        nome  = vei_meta.get("ras_vei_veiculo", "—")
        self._resumo_veh_lbl.config(text=f"{placa} — {nome}")

        score = risk["score"]
        cor   = C["success"] if score < 20 else (C["warn"] if score < 50 else C["danger"])
        self._resumo_score_lbl.config(text=f"Score de Risco: {score}/100", fg=cor)

        # KPIs
        self._rskpis["dist"].config(   text=f"{perc.get('dist_km','—')} km")
        self._rskpis["dur"].config(    text=f"{perc.get('duracao_min','—')} min")
        self._rskpis["vmax"].config(   text=f"{perc.get('vel_max','—')} km/h")
        self._rskpis["vmed"].config(   text=f"{perc.get('vel_media','—')} km/h")
        self._rskpis["ocio_h"].config( text=f"{ocio.get('ocioso_h','—')} h")
        self._rskpis["l_total"].config(text=f"{cons.get('l_total','—')} L")
        self._rskpis["custo"].config(  text=f"R$ {cons.get('custo_brl','—')}")
        self._rskpis["score"].config(  text=str(score), fg=cor)
        self._rskpis["ligado"].config( text=f"{mot.get('ligado_h','—')} h")
        self._rskpis["ciclos"].config( text=str(mot.get("ciclos_ignicao","—")))
        self._rskpis["volt"].config(   text=f"{mot.get('volt_media','—')} V")
        self._rskpis["bat"].config(    text=f"{mot.get('bat_media','—')} %")

        # Mapa de calor
        max_cnt = max(heat.values()) or 1
        for h, cnt in heat.items():
            cell = self._heat_cells[h]
            lbl_w = self._heat_cnts[h]
            intensity = cnt / max_cnt
            bar_col = (C["text_dim"] if intensity < 0.25 else
                       C["accent2"]  if intensity < 0.6  else C["accent"])
            h_px = max(4, int(50 * intensity))
            for w in cell.winfo_children():
                w.destroy()
            bar = tk.Frame(cell, bg=bar_col, width=28, height=h_px)
            bar.place(relx=0, rely=1, anchor="sw", relwidth=1)
            tk.Label(cell, text=str(cnt) if cnt else "",
                     bg=C["surface3"], fg=C["text_dim"],
                     font=("Helvetica Neue", 6)).place(relx=0.5, y=1, anchor="n")

        # Tabela de exportação
        for r in self._tree_resum.get_children():
            self._tree_resum.delete(r)
        rows = [
            ("Placa",              placa),
            ("Veículo",            nome),
            ("Cliente",            vei_meta.get("ras_cli_desc", "—")),
            ("Período início",     perc.get("inicio", "—")),
            ("Período fim",        perc.get("fim", "—")),
            ("Distância total",    f"{perc.get('dist_km','—')} km"),
            ("Duração",            f"{perc.get('duracao_min','—')} min"),
            ("Pontos coletados",   str(perc.get("n_pontos", "—"))),
            ("Velocidade máxima",  f"{perc.get('vel_max','—')} km/h"),
            ("Velocidade média",   f"{perc.get('vel_media','—')} km/h"),
            ("Tempo ligado",       f"{mot.get('ligado_h','—')} h"),
            ("Tempo desligado",    f"{mot.get('desligado_h','—')} h"),
            ("Ciclos de ignição",  str(mot.get("ciclos_ignicao","—"))),
            ("Voltagem média",     f"{mot.get('volt_media','—')} V"),
            ("Voltagem mínima",    f"{mot.get('volt_min','—')} V"),
            ("Bateria média",      f"{mot.get('bat_media','—')} %"),
            ("Tempo ocioso",       f"{ocio.get('ocioso_h','—')} h"),
            ("Combustível ócio",   f"{ocio.get('consumo_l','—')} L"),
            ("Combustível mov.",   f"{cons.get('l_movimento','—')} L"),
            ("Combustível total",  f"{cons.get('l_total','—')} L"),
            ("Custo estimado",     f"R$ {cons.get('custo_brl','—')}"),
            ("% acima vel. limite",f"{vel.get('pct_acima_limite','—')}%"),
            ("Score de risco",     f"{score}/100"),
            ("Nível de risco",     risk.get("nivel", "—")),
        ]
        for metrica, valor in rows:
            self._tree_resum.insert("", "end", values=(metrica, valor))
