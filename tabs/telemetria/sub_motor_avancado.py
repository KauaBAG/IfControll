"""
tabs/telemetria/sub_motor_avancado.py
RPM · Torque · Borboleta · Carga do motor — dados do /telemetry/vehicle
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from core.models import safe_int, safe_float

RPM_IDLE_MAX     = 900
RPM_OVERREV      = 4500
RPM_OPTIMAL_LOW  = 1500
RPM_OPTIMAL_HIGH = 2500
RPM_DELTA_BRUSCO = 800

_COLS_E  = ("Data/Hora", "RPM", "Vel km/h", "Torque Nm", "Borboleta%", "Evento", "Sev.")
_WIDTHS_E = (145, 65, 75, 80, 85, 190, 80)
_COLS_F  = ("Faixa RPM", "Pontos", "% Tempo", "Vel Média", "Avaliação")
_WIDTHS_F = (170, 65, 70, 80, 160)


def calc_motor_avancado(points: list[dict]) -> dict:
    rows = []
    for p in points:
        rpm   = safe_int(p.get("tel_rpm", 0))
        vel   = safe_int(p.get("ras_eve_velocidade", 0) or p.get("tel_rpm", 0) * 0)
        torq  = safe_float(p.get("tel_torque", 0))
        borb  = safe_float(p.get("tel_posicao_borboleta", 0))
        data  = str(p.get("ras_eve_data_gps", "") or p.get("dt_gps", ""))
        if rpm > 0:
            rows.append((rpm, vel, torq, borb, data))

    if not rows:
        return {"sem_dados": True}

    rpm_vals  = [r[0] for r in rows]
    vel_vals  = [r[1] for r in rows]
    torq_vals = [r[2] for r in rows]
    n = len(rpm_vals) or 1

    rpm_med  = round(sum(rpm_vals) / n)
    rpm_max  = max(rpm_vals)
    rpm_min  = min(rpm_vals)
    torq_med = round(sum(t for t in torq_vals if t > 0) / max(1, sum(1 for t in torq_vals if t > 0)), 1) if any(t > 0 for t in torq_vals) else None
    torq_max = round(max(torq_vals), 1) if torq_vals else None
    pct_eco  = round(sum(1 for r in rpm_vals if RPM_OPTIMAL_LOW <= r <= RPM_OPTIMAL_HIGH) / n * 100, 1)
    pct_over = round(sum(1 for r in rpm_vals if r > RPM_OVERREV) / n * 100, 1)

    faixas_def = [
        ("Marcha lenta (< 800)",   0,    800),
        ("Baixo (800–1500)",       800,  1500),
        ("Econômico (1500–2500)",  1500, 2500),
        ("Médio (2500–3500)",      2500, 3500),
        ("Alto (3500–4500)",       3500, 4500),
        ("Sobre-rotação (>4500)",  4500, 99999),
    ]
    faixas = []
    for nome, lo, hi in faixas_def:
        idxs = [i for i, r in enumerate(rpm_vals) if lo <= r < hi]
        nf   = len(idxs)
        pct  = round(nf / n * 100, 1)
        vmed = round(sum(vel_vals[i] for i in idxs) / nf, 1) if nf else 0
        aval = ("⚠️ Crítico" if lo >= 4500 else
                "🔴 Elevado" if lo >= 3500 else
                "✅ Ideal"   if lo == 1500 else "🔵 Normal")
        faixas.append({"nome": nome, "n": nf, "pct": pct, "vmed": vmed, "aval": aval})

    eventos = []
    for i, (rpm, vel, torq, borb, data) in enumerate(rows):
        ev = sev = None
        if rpm > RPM_OVERREV:
            ev, sev = f"Sobre-rotação — {rpm} RPM", "🔴 CRÍTICO"
        elif rpm > 2800 and 0 < vel < 30:
            ev, sev = f"Marcha longa — {rpm} RPM a {vel} km/h", "⚠️ ATENÇÃO"
        elif i > 0 and abs(rpm - rows[i-1][0]) > RPM_DELTA_BRUSCO:
            d = rpm - rows[i-1][0]
            ev, sev = f"Aceleração brusca — Δ{d:+d} RPM", "⚠️ ATENÇÃO"
        elif rpm > RPM_IDLE_MAX and vel == 0:
            ev, sev = f"Marcha lenta alta — {rpm} RPM parado", "💡 INFO"
        elif borb > 90 and vel < 20:
            ev, sev = f"Borboleta {borb:.0f}% sem velocidade", "⚠️ ATENÇÃO"
        if ev:
            eventos.append({"data": data, "rpm": rpm, "vel": vel,
                            "torque": torq, "borb": borb,
                            "evento": ev, "sev": sev})
            if len(eventos) >= 300:
                break

    recs = []
    if pct_over > 2:
        recs.append(f"🔴 {pct_over}% em sobre-rotação (>{RPM_OVERREV} RPM). Desgaste acelerado do motor.")
    if pct_eco < 40:
        recs.append(f"⚠️ Apenas {pct_eco}% na faixa econômica ({RPM_OPTIMAL_LOW}–{RPM_OPTIMAL_HIGH} RPM).")
    n_bruscos = sum(1 for e in eventos if "brusca" in e["evento"])
    if n_bruscos > 10:
        recs.append(f"⚠️ {n_bruscos} acelerações bruscas detectadas.")
    if not recs:
        recs.append("✅ RPM e torque dentro dos parâmetros normais.")

    return {
        "sem_dados": False,
        "kpis": {"rpm_med": rpm_med, "rpm_max": rpm_max, "rpm_min": rpm_min,
                 "torq_med": torq_med, "torq_max": torq_max,
                 "pct_eco": pct_eco, "pct_over": pct_over, "n_eventos": len(eventos)},
        "faixas": faixas, "eventos": eventos, "recomendacoes": recs,
    }


class MotorAvancadoMixin:

    def _build_motor_avancado(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 🔩 RPM/Torque ")

        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._rmkpis = {}
        for key, title, col in [
            ("rpm_med",   "RPM MÉDIO",    C["accent"]),
            ("rpm_max",   "RPM MÁX.",     C["danger"]),
            ("rpm_min",   "RPM MÍN.",     C["text_mid"]),
            ("torq_med",  "TORQUE MED.",  C["blue"]),
            ("torq_max",  "TORQUE MÁX.", C["warn"]),
            ("pct_eco",   "% FAIXA ECO", C["success"]),
            ("pct_over",  "% SOBREROT.", C["danger"]),
            ("n_eventos", "ANOMALIAS",   C["warn"]),
        ]:
            self._rmkpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")
        panes = tk.Frame(f, bg=C["bg"])
        panes.pack(fill="both", expand=True)
        left  = tk.Frame(panes, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(panes, bg=C["surface2"], width=310)
        right.pack(side="right", fill="y", padx=(2, 0))
        right.pack_propagate(False)

        lbl(left, "Anomalias de RPM · Torque · Borboleta", 10, True, C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))
        apply_treeview_style("TRpm", C["accent"])
        inner = tk.Frame(left, bg=C["bg"])
        inner.pack(fill="both", expand=True)
        self._tree_rpm = ttk.Treeview(inner, columns=_COLS_E, show="headings", style="TRpm.Treeview", height=14)
        for c, w in zip(_COLS_E, _WIDTHS_E):
            self._tree_rpm.heading(c, text=c, anchor="w")
            self._tree_rpm.column(c, width=w, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._tree_rpm.yview)
        self._tree_rpm.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_rpm.pack(fill="both", expand=True)
        mk_export_btn(left, self._tree_rpm).pack(anchor="e", padx=8, pady=4)

        lbl(right, "Distribuição por Faixa de RPM", 10, True, C["accent"], bg=C["surface2"]).pack(padx=10, pady=(10, 4), anchor="w")
        self._rpm_faixas_frame = tk.Frame(right, bg=C["surface2"])
        self._rpm_faixas_frame.pack(fill="x", padx=8)
        tk.Frame(right, bg=C["border"], height=1).pack(fill="x", pady=6)
        lbl(right, "Recomendações", 10, True, C["accent"], bg=C["surface2"]).pack(padx=10, pady=(0, 4), anchor="w")
        self._rpm_rec_frame = tk.Frame(right, bg=C["surface2"])
        self._rpm_rec_frame.pack(fill="x", padx=8, pady=(0, 8))
        self._rpm_no_data = lbl(f, "Sem dados de RPM nesta consulta.\n(/telemetry/vehicle não retornou dados para este período.)", 9, col=C["text_dim"])

        register_theme_listener(lambda: apply_treeview_style("TRpm", C["accent"]))

    def _render_motor_avancado(self, points: list[dict]):
        m = calc_motor_avancado(points)
        if m.get("sem_dados"):
            self._rpm_no_data.pack(pady=30)
            return
        self._rpm_no_data.pack_forget()

        k = m["kpis"]
        self._rmkpis["rpm_med"].config(  text=str(k["rpm_med"]))
        self._rmkpis["rpm_max"].config(  text=str(k["rpm_max"]))
        self._rmkpis["rpm_min"].config(  text=str(k["rpm_min"]))
        self._rmkpis["torq_med"].config( text=f"{k['torq_med']} Nm" if k["torq_med"] else "—")
        self._rmkpis["torq_max"].config( text=f"{k['torq_max']} Nm" if k["torq_max"] else "—")
        self._rmkpis["pct_eco"].config(  text=f"{k['pct_eco']}%", fg=C["success"] if k["pct_eco"] > 50 else C["warn"])
        self._rmkpis["pct_over"].config( text=f"{k['pct_over']}%", fg=C["danger"] if k["pct_over"] > 2 else C["success"])
        self._rmkpis["n_eventos"].config(text=str(k["n_eventos"]), fg=C["danger"] if k["n_eventos"] > 20 else C["text"])

        for r in self._tree_rpm.get_children():
            self._tree_rpm.delete(r)
        for ev in m["eventos"]:
            tag = "crit" if "CRÍTICO" in ev["sev"] else ("warn" if "ATENÇÃO" in ev["sev"] else "info")
            self._tree_rpm.insert("", "end", tags=(tag,), values=(
                ev["data"], ev["rpm"], ev["vel"],
                f"{ev['torque']:.1f}" if ev["torque"] else "—",
                f"{ev['borb']:.0f}%" if ev["borb"] else "—",
                ev["evento"], ev["sev"]))
        self._tree_rpm.tag_configure("crit", foreground=C["danger"])
        self._tree_rpm.tag_configure("warn", foreground=C["warn"])
        self._tree_rpm.tag_configure("info", foreground=C["blue"])

        for w in self._rpm_faixas_frame.winfo_children():
            w.destroy()
        max_pct = max((fx["pct"] for fx in m["faixas"]), default=1) or 1
        for fx in m["faixas"]:
            row = tk.Frame(self._rpm_faixas_frame, bg=C["surface2"])
            row.pack(fill="x", pady=2)
            lbl(row, fx["nome"], 8, col=C["text_mid"], bg=C["surface2"], width=22).pack(side="left")
            bg = tk.Frame(row, bg=C["surface3"], height=14, width=100)
            bg.pack(side="left", padx=4)
            bg.pack_propagate(False)
            col_bar = C["success"] if "Econômico" in fx["nome"] else (C["danger"] if "Sobre" in fx["nome"] else C["accent"])
            tk.Frame(bg, bg=col_bar, width=max(2, int(100 * fx["pct"] / max_pct)), height=14).place(x=0, y=0)
            lbl(row, f"{fx['pct']}%", 8, col=C["text_dim"], bg=C["surface2"]).pack(side="left", padx=4)

        for w in self._rpm_rec_frame.winfo_children():
            w.destroy()
        for rec in m["recomendacoes"]:
            card = tk.Frame(self._rpm_rec_frame, bg=C["surface3"], highlightthickness=1, highlightbackground=C["border"])
            card.pack(fill="x", pady=2)
            lbl(card, rec, 8, col=C["text"], bg=C["surface3"], wraplength=270).pack(padx=8, pady=5, anchor="w")