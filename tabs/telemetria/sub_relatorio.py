"""
tabs/telemetria/sub_relatorio.py
Sub-aba 11 — Relatório Completo (exportação CSV/TXT).
Consolida TODOS os KPIs em um único relatório exportável.
Botão para salvar CSV pronto para BI ou impressão.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os
from datetime import datetime

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, btn, apply_treeview_style
from ._calc import (
    calc_percurso, calc_velocidade, calc_ociosidade,
    calc_motor, calc_risco, calc_consumo, calc_temperatura,
    calc_anomalias, calc_cercas, calc_alertas,
)

_COLS = ("Categoria", "Métrica", "Valor", "Observação")
_WIDTHS = (160, 260, 160, 260)


class RelatorioMixin:

    def _build_relatorio(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📋 Relatório ")

        # Cabeçalho
        hdr = tk.Frame(f, bg=C["surface3"])
        hdr.pack(fill="x")
        lbl(hdr, "📋  RELATÓRIO COMPLETO DE TELEMETRIA", 11, True, C["accent"],
            bg=C["surface3"]).pack(side="left", padx=14, pady=10)
        self._rel_periodo_lbl = lbl(hdr, "Selecione um veículo e clique em Buscar",
                                     9, col=C["text_dim"], bg=C["surface3"])
        self._rel_periodo_lbl.pack(side="left", padx=20)

        # Botões
        btn_bar = tk.Frame(f, bg=C["surface2"])
        btn_bar.pack(fill="x", padx=12, pady=8)
        btn(btn_bar, "💾  EXPORTAR CSV",  self._exportar_csv,
            C["accent"], px=14, py=6).pack(side="left", padx=6)
        btn(btn_bar, "📄  EXPORTAR TXT",  self._exportar_txt,
            C["blue"], px=14, py=6).pack(side="left", padx=6)
        lbl(btn_bar, "Formatos prontos para BI, Excel ou impressão.",
            8, col=C["text_dim"], bg=C["surface2"]).pack(side="left", padx=12)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Treeview completa
        apply_treeview_style("TRel", C["accent"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        self._tree_rel = ttk.Treeview(
            inner, columns=_COLS, show="headings",
            style="TRel.Treeview", height=24,
        )
        for c, w in zip(_COLS, _WIDTHS):
            self._tree_rel.heading(c, text=c, anchor="w")
            self._tree_rel.column(c, width=w, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(inner, orient="vertical",  command=self._tree_rel.yview)
        hsb = ttk.Scrollbar(inner, orient="horizontal", command=self._tree_rel.xview)
        self._tree_rel.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree_rel.pack(fill="both", expand=True)

        self._rel_rows: list[tuple] = []   # cache para exportação

        register_theme_listener(lambda: apply_treeview_style("TRel", C["accent"]))

    # ── Render ──────────────────────────────────────────────────────────────

    def _render_relatorio(
        self, points: list[dict], vei_meta: dict,
        fences: list[dict], alerts: list[dict],
        limite_vel: int = 80,
    ):
        perc  = calc_percurso(points)
        vel   = calc_velocidade(points, limite_vel)
        ocio  = calc_ociosidade(points)
        mot   = calc_motor(points)
        risk  = calc_risco(perc, vel, ocio, mot, points, limite_vel)
        cons  = calc_consumo(perc, ocio,
                             consumo_real_km_l=float(vei_meta.get("ras_vei_consumo") or 0))
        temp  = calc_temperatura(points)
        cercas_m = calc_cercas(fences)
        alerts_m = calc_alertas(alerts)
        anom  = calc_anomalias(points)

        placa = vei_meta.get("ras_vei_placa", "—")
        nome  = vei_meta.get("ras_vei_veiculo", "—")
        cli   = vei_meta.get("ras_cli_desc", "—")

        self._rel_periodo_lbl.config(
            text=f"{placa} — {nome}  |  {perc.get('inicio','—')} → {perc.get('fim','—')}"
        )

        rows: list[tuple[str, str, str, str]] = []

        def add(cat, metrica, valor, obs=""):
            rows.append((cat, metrica, str(valor), obs))

        # Identificação
        add("Veículo", "Placa",          placa)
        add("Veículo", "Descrição",      nome)
        add("Veículo", "Cliente",        cli)
        add("Veículo", "Combustível ID", vei_meta.get("ras_vei_combustivel", "—"))
        add("Veículo", "Consumo cadastrado", f"{vei_meta.get('ras_vei_consumo','—')} km/L")
        add("Veículo", "Limite vel. cadastrado",
            f"{vei_meta.get('ras_vei_velocidade_limite','—')} km/h")

        # Percurso
        add("Percurso", "Distância",        f"{perc.get('dist_km','—')} km")
        add("Percurso", "Duração",          f"{perc.get('duracao_min','—')} min")
        add("Percurso", "Pontos coletados", perc.get("n_pontos", "—"))
        add("Percurso", "Início",           perc.get("inicio", "—"))
        add("Percurso", "Fim",              perc.get("fim", "—"))

        # Velocidade
        add("Velocidade", "Vel. máxima",        f"{perc.get('vel_max','—')} km/h")
        add("Velocidade", "Vel. média",         f"{perc.get('vel_media','—')} km/h")
        add("Velocidade", "% acima limite",     f"{vel.get('pct_acima_limite','—')}%",
            f"limite = {limite_vel} km/h")
        add("Velocidade", "Eventos de excesso", len(vel.get("picos", [])))
        add("Velocidade", "Acelerações bruscas",vel.get("aceleracoes_bruscas", 0))

        # Motor
        add("Motor", "Tempo ligado",    f"{mot.get('ligado_h','—')} h")
        add("Motor", "Tempo desligado", f"{mot.get('desligado_h','—')} h")
        add("Motor", "Ciclos ignição",  mot.get("ciclos_ignicao", "—"))
        add("Motor", "Voltagem média",  f"{mot.get('volt_media','—')} V")
        add("Motor", "Voltagem mínima", f"{mot.get('volt_min','—')} V",
            "⚠ crítico se < 11.5V" if mot.get("volt_min", 12) < 11.5 else "")
        add("Motor", "Voltagem máxima", f"{mot.get('volt_max','—')} V")
        add("Motor", "Bateria média",   f"{mot.get('bat_media','—')} %")

        # Ociosidade
        add("Ociosidade", "Tempo ocioso", f"{ocio.get('ocioso_h','—')} h")
        add("Ociosidade", "Nº períodos",  ocio.get("n_periodos", "—"))
        add("Ociosidade", "Combustível perdido no ócio",
            f"{ocio.get('consumo_l','—')} L")

        # Consumo
        add("Consumo", "Litros em movimento",   f"{cons.get('l_movimento','—')} L")
        add("Consumo", "Litros em ócio",        f"{cons.get('l_ocio','—')} L")
        add("Consumo", "Total de combustível",  f"{cons.get('l_total','—')} L")
        add("Consumo", "Custo estimado",        f"R$ {cons.get('custo_brl','—')}")
        add("Consumo", "Custo por km",          f"R$ {cons.get('custo_km','—')}")
        add("Consumo", "Consumo usado (km/L)",  cons.get("km_l_usado", "—"))

        # Temperatura
        if temp.get("disponivel"):
            for canal in ("digital_1", "analog_1", "analog_2"):
                st = temp.get(canal)
                if st:
                    add("Temperatura", f"{canal} — mín", f"{st['min']}°C")
                    add("Temperatura", f"{canal} — máx", f"{st['max']}°C",
                        "⚠ alta" if st["max"] > 100 else "")
                    add("Temperatura", f"{canal} — média", f"{st['media']}°C")

        # Cercas
        add("Cercas", "Total de visitas", cercas_m.get("total_visitas", 0))
        add("Cercas", "Cercas ativas",    len(cercas_m.get("cercas", [])))

        # Alertas
        add("Alertas", "Total",   alerts_m.get("total", 0))
        add("Alertas", "Abertos", alerts_m.get("abertos", 0))
        add("Alertas", "Fechados",alerts_m.get("fechados", 0))

        # Anomalias
        add("Anomalias", "Detectadas", len(anom))
        for a in anom[:5]:
            add("Anomalias", a["tipo"], a["descricao"][:60], a["data"])

        # Risco
        add("Score Risco", "Pontuação",  f"{risk.get('score','—')}/100")
        add("Score Risco", "Nível",      risk.get("nivel", "—"))
        for det in risk.get("detalhes", []):
            add("Score Risco", "Detalhe", det[:80])

        # Popula treeview
        for r in self._tree_rel.get_children():
            self._tree_rel.delete(r)
        for row in rows:
            tag = "cat" if row[0] != (rows[rows.index(row) - 1][0]
                                       if rows.index(row) > 0 else "") else ""
            self._tree_rel.insert("", "end", values=row)

        self._rel_rows = rows

    # ── Exportação ──────────────────────────────────────────────────────────

    def _exportar_csv(self):
        if not self._rel_rows:
            messagebox.showinfo("Sem dados", "Gere um relatório antes de exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            initialfile=f"telemetria_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["Categoria", "Métrica", "Valor", "Observação"])
                w.writerows(self._rel_rows)
            messagebox.showinfo("Exportado", f"CSV salvo em:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _exportar_txt(self):
        if not self._rel_rows:
            messagebox.showinfo("Sem dados", "Gere um relatório antes de exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
            initialfile=f"telemetria_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        )
        if not path:
            return
        try:
            lines = [
                "=" * 70,
                "  RELATÓRIO DE TELEMETRIA — FULLTRACK",
                f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                "=" * 70, "",
            ]
            cur_cat = ""
            for cat, metrica, valor, obs in self._rel_rows:
                if cat != cur_cat:
                    lines.append(f"\n[ {cat.upper()} ]")
                    cur_cat = cat
                obs_str = f"  ({obs})" if obs else ""
                lines.append(f"  {metrica:<40} {valor}{obs_str}")
            lines += ["", "=" * 70]
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            messagebox.showinfo("Exportado", f"TXT salvo em:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro", str(e))