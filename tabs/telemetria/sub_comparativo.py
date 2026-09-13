"""
tabs/telemetria/sub_comparativo.py
Sub-aba — Comparativo de Períodos

Permite selecionar o mesmo veículo em dois intervalos de datas
e comparar lado a lado todos os KPIs principais:
  Percurso, Velocidade, Ociosidade, Motor, Bateria, RPM, Score de Risco
"""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, ent, btn, apply_treeview_style
from core.models import safe_int, safe_float

from ._api import get_events_interval, to_ts
from ._calc import (calc_percurso, calc_velocidade, calc_ociosidade,
                    calc_motor, calc_risco)
from .sub_bateria import calc_bateria
from .sub_motor_avancado import calc_motor_avancado

_COLS_COMP = ("Métrica", "Período A", "Período B", "Δ Variação", "Tendência")
_WIDTHS_C  = (220, 130, 130, 120, 100)


def _fmt_hours_ago(h):
    now = datetime.now()
    return (now - timedelta(hours=h)).strftime("%d/%m/%Y %H:%M")


def _fmt_now():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _fetch_period(vei_id, begin_str, end_str):
    b = to_ts(begin_str)
    e = to_ts(end_str)
    if e <= b:
        return []
    # Chunking simples para o comparativo
    chunk = 3600
    pts, seen = [], set()
    cur = b
    while cur < e:
        nxt = min(cur + chunk, e)
        try:
            chunk_pts = get_events_interval(vei_id, cur, nxt)
            for p in chunk_pts:
                uid = p.get("_id") or p.get("ras_eve_data_gps") or id(p)
                if uid not in seen:
                    seen.add(uid)
                    pts.append(p)
        except Exception:
            pass
        cur = nxt
    return pts


def _build_kpis(points, limite_vel=80):
    """Extrai todos os KPIs de um conjunto de pontos."""
    if not points:
        return {}
    perc = calc_percurso(points)
    vel  = calc_velocidade(points, limite_vel)
    ocio = calc_ociosidade(points)
    mot  = calc_motor(points)
    risk = calc_risco(perc, vel, ocio, mot, points)
    bat  = calc_bateria(points)
    rpm  = calc_motor_avancado(points)

    return {
        "Distância (km)":          perc.get("dist_km", 0),
        "Duração (min)":           round(perc.get("duracao_min", 0)),
        "Vel. Média (km/h)":       perc.get("vel_media", 0),
        "Vel. Máxima (km/h)":      perc.get("vel_max", 0),
        "% Acima Limite":          vel.get("pct_acima_limite", 0),
        "Eventos Excesso Vel.":    len(vel.get("picos", [])),
        "Tempo Ocioso (h)":        ocio.get("ocioso_h", 0),
        "Ciclos Ignição":          mot.get("ciclos_ignicao", 0),
        "Tensão Média (V)":        mot.get("volt_media", 0),
        "Tensão Mínima (V)":       mot.get("volt_min", 0),
        "Score de Risco":          risk.get("score", 0),
        "RPM Médio":               rpm.get("kpis", {}).get("rpm_med", 0) if not rpm.get("sem_dados") else 0,
        "RPM Máximo":              rpm.get("kpis", {}).get("rpm_max", 0) if not rpm.get("sem_dados") else 0,
        "% Faixa Econômica RPM":   rpm.get("kpis", {}).get("pct_eco", 0) if not rpm.get("sem_dados") else 0,
        "Alertas Bateria":         bat.get("kpis", {}).get("n_alertas", 0) if not bat.get("sem_dados") else 0,
        "N° Pontos GPS":           len(points),
        # Campos exclusivos do /telemetry/vehicle
        "Odômetro (km)":           max((p.get("tel_odometro", 0) for p in points), default=0),
        "Consumo Acumulado (L)":   (max((p.get("tel_fuel_consumption", 0) for p in points), default=0) -
                                    min((p.get("tel_fuel_consumption", 0) for p in points if p.get("tel_fuel_consumption",0) > 0), default=0)),
        "Temp. Motor Média (°C)":  round(sum(p.get("tel_temperatura_motor", 0) for p in points if p.get("tel_temperatura_motor", 0) > 0) /
                                    max(1, sum(1 for p in points if p.get("tel_temperatura_motor", 0) > 0)), 1),
        "RPM Médio":               round(sum(p.get("tel_rpm", 0) for p in points if p.get("tel_rpm", 0) > 0) /
                                    max(1, sum(1 for p in points if p.get("tel_rpm", 0) > 0))),
    }


def _delta_str(a, b):
    """Calcula delta e formata com seta."""
    try:
        fa, fb = float(a), float(b)
        d = fb - fa
        if abs(d) < 0.01:
            return "0  —"
        return f"{d:+.2f}"
    except (ValueError, TypeError):
        return "—"


def _trend(metric, a, b):
    """Determina se a variação é positiva ou negativa para a métrica."""
    positivo_menor = {
        "Score de Risco", "% Acima Limite", "Eventos Excesso Vel.",
        "Tempo Ocioso (h)", "Ciclos Ignição", "Alertas Bateria",
    }
    try:
        fa, fb = float(a), float(b)
        melhorou = (fb < fa) if metric in positivo_menor else (fb > fa)
        if abs(fb - fa) < 0.01:
            return "➡️ Igual"
        return "✅ Melhorou" if melhorou else "🔴 Piorou"
    except (ValueError, TypeError):
        return "—"


class ComparativoMixin:

    def _build_comparativo(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📊 Comparativo ")

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        header = tk.Frame(f, bg=C["surface3"])
        header.pack(fill="x")
        lbl(header, "📊  COMPARATIVO DE PERÍODOS", 11, True, C["accent"],
            bg=C["surface3"]).pack(side="left", padx=14, pady=10)

        # ── Seletores dos dois períodos ────────────────────────────────────────
        sel = tk.Frame(f, bg=C["surface2"])
        sel.pack(fill="x", padx=14, pady=8)

        # Período A
        fa = tk.Frame(sel, bg=C["surface2"], highlightthickness=1, highlightbackground=C["blue"])
        fa.pack(side="left", padx=(0, 10), pady=4, ipadx=6, ipady=4)
        lbl(fa, "PERÍODO A", 9, True, C["blue"], bg=C["surface2"]).pack(anchor="w", padx=6, pady=(4, 2))
        row_a = tk.Frame(fa, bg=C["surface2"])
        row_a.pack(padx=6, pady=2)
        lbl(row_a, "Início:", 9, col=C["text_mid"], bg=C["surface2"]).pack(side="left")
        self._comp_a_ini = ent(row_a, w=15)
        self._comp_a_ini.pack(side="left", padx=4, ipady=2)
        self._comp_a_ini.insert(0, _fmt_hours_ago(336))  # 14 dias atrás
        lbl(row_a, "Fim:", 9, col=C["text_mid"], bg=C["surface2"]).pack(side="left", padx=(8, 2))
        self._comp_a_fim = ent(row_a, w=15)
        self._comp_a_fim.pack(side="left", padx=4, ipady=2)
        self._comp_a_fim.insert(0, _fmt_hours_ago(168))  # 7 dias atrás

        # Período B
        fb = tk.Frame(sel, bg=C["surface2"], highlightthickness=1, highlightbackground=C["accent"])
        fb.pack(side="left", padx=(0, 10), pady=4, ipadx=6, ipady=4)
        lbl(fb, "PERÍODO B", 9, True, C["accent"], bg=C["surface2"]).pack(anchor="w", padx=6, pady=(4, 2))
        row_b = tk.Frame(fb, bg=C["surface2"])
        row_b.pack(padx=6, pady=2)
        lbl(row_b, "Início:", 9, col=C["text_mid"], bg=C["surface2"]).pack(side="left")
        self._comp_b_ini = ent(row_b, w=15)
        self._comp_b_ini.pack(side="left", padx=4, ipady=2)
        self._comp_b_ini.insert(0, _fmt_hours_ago(168))  # 7 dias atrás
        lbl(row_b, "Fim:", 9, col=C["text_mid"], bg=C["surface2"]).pack(side="left", padx=(8, 2))
        self._comp_b_fim = ent(row_b, w=15)
        self._comp_b_fim.pack(side="left", padx=4, ipady=2)
        self._comp_b_fim.insert(0, _fmt_now())

        btn(sel, "⚡  COMPARAR", self._buscar_comparativo,
            C["accent"], px=14, py=8).pack(side="left", padx=10)

        self._comp_status = lbl(sel, "Selecione os períodos e clique em COMPARAR.",
                                 9, col=C["text_dim"], bg=C["surface2"])
        self._comp_status.pack(side="left", padx=10)

        # ── Tabela comparativa ────────────────────────────────────────────────
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        apply_treeview_style("TComp", C["accent"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True, padx=8, pady=8)
        self._tree_comp = ttk.Treeview(inner, columns=_COLS_COMP, show="headings",
                                        style="TComp.Treeview", height=20)
        for c, w in zip(_COLS_COMP, _WIDTHS_C):
            self._tree_comp.heading(c, text=c, anchor="w")
            self._tree_comp.column(c, width=w, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._tree_comp.yview)
        self._tree_comp.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_comp.pack(fill="both", expand=True)

        register_theme_listener(lambda: apply_treeview_style("TComp", C["accent"]))

    def _buscar_comparativo(self):
        key  = self._cb_vei.get()
        info = self._vei_map.get(key)
        if not info:
            self._comp_status.config(text="⚠ Selecione um veículo na barra principal.", fg=C["warn"])
            return

        vei_id = info["id"]
        a_ini  = self._comp_a_ini.get()
        a_fim  = self._comp_a_fim.get()
        b_ini  = self._comp_b_ini.get()
        b_fim  = self._comp_b_fim.get()

        self._comp_status.config(text="⏳ Buscando períodos em paralelo...", fg=C["accent"])

        def task():
            pts_a, pts_b = [], []
            def fetch_a(): nonlocal pts_a; pts_a = _fetch_period(vei_id, a_ini, a_fim)
            def fetch_b(): nonlocal pts_b; pts_b = _fetch_period(vei_id, b_ini, b_fim)
            t1 = threading.Thread(target=fetch_a, daemon=True)
            t2 = threading.Thread(target=fetch_b, daemon=True)
            t1.start(); t2.start()
            t1.join();  t2.join()
            self.after(0, lambda: self._render_comparativo(pts_a, pts_b, a_ini, a_fim, b_ini, b_fim))

        threading.Thread(target=task, daemon=True).start()

    def _render_comparativo(self, pts_a, pts_b, a_ini, a_fim, b_ini, b_fim):
        na, nb = len(pts_a), len(pts_b)
        self._comp_status.config(
            text=f"✔ Período A: {na:,} pts  |  Período B: {nb:,} pts", fg=C["success"])

        kpis_a = _build_kpis(pts_a)
        kpis_b = _build_kpis(pts_b)

        for r in self._tree_comp.get_children():
            self._tree_comp.delete(r)

        # Cabeçalho visual
        self._tree_comp.insert("", "end", tags=("header",), values=(
            "— PERÍODO —",
            f"A: {a_ini} → {a_fim}",
            f"B: {b_ini} → {b_fim}",
            "Δ B − A", ""))
        self._tree_comp.tag_configure("header", background=C["surface3"], foreground=C["accent"])

        all_metrics = list(kpis_a.keys()) if kpis_a else list(kpis_b.keys())
        for metric in all_metrics:
            va = kpis_a.get(metric, "—")
            vb = kpis_b.get(metric, "—")
            delta   = _delta_str(va, vb)
            trend   = _trend(metric, va, vb)
            tag     = ("melhor" if "Melhorou" in trend else
                       "pior"   if "Piorou"   in trend else "igual")
            self._tree_comp.insert("", "end", tags=(tag,), values=(
                metric,
                f"{va}" if va != "—" else "—",
                f"{vb}" if vb != "—" else "—",
                delta, trend,
            ))

        self._tree_comp.tag_configure("melhor", foreground=C["success"])
        self._tree_comp.tag_configure("pior",   foreground=C["danger"])
        self._tree_comp.tag_configure("igual",  foreground=C["text_mid"])