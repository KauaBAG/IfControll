"""
tabs/telemetria/sub_bateria.py
Análise de Bateria + Alternador + Predição de Falha
Campos reais: battery_load, filg_ignicao — sem ras_eve_voltagem no telemetry
Usa ras_eve_voltagem do /events/interval e battery_load do /telemetry/vehicle
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from core.models import safe_int, safe_float

# 12V
V12_CARGA_MIN  = 13.0
V12_CARGA_CRIT = 12.5
V12_BAT_CRIT   = 11.5
V12_BAT_DEAD   = 10.5
# 24V
V24_CARGA_MIN  = 26.5
V24_CARGA_CRIT = 25.5
V24_BAT_CRIT   = 23.0
V24_BAT_DEAD   = 21.0

VOLT_DELTA_SPIKE = 3.0

_COLS_A = ("Data/Hora", "Tensão (V)", "Carga Bat%", "Ignição", "Alerta", "Severidade")
_WIDTHS_A = (145, 90, 90, 75, 230, 90)
_COLS_D = ("Data", "V Mín", "V Máx", "V Média", "Status")
_WIDTHS_D = (100, 70, 70, 80, 170)


def _parse_dt(raw):
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(raw).strip(), fmt)
        except ValueError:
            continue
    return None


def _safe_volt(p):
    """Tenta pegar voltagem de ras_eve_voltagem ou tel_battery_load."""
    v = safe_float(p.get("ras_eve_voltagem", 0))
    if v > 5:
        return v
    # battery_load pode ser "%" ou valor bruto — ignora se string "-"
    bl = p.get("tel_battery_load", "-")
    if bl != "-":
        try:
            return float(str(bl).replace(",", "."))
        except (ValueError, TypeError):
            pass
    return 0.0


def calc_bateria(points: list[dict]) -> dict:
    volt_data = []
    for p in points:
        v   = _safe_volt(p)
        ign = safe_int(p.get("ras_eve_ignicao", 0) or p.get("filg_ignicao", 0))
        raw = p.get("ras_eve_data_gps", "") or p.get("dt_gps", "")
        dt  = _parse_dt(str(raw))
        bat_pct = safe_int(p.get("ras_eve_porc_bat_backup", -1))
        if v > 5:
            volt_data.append({"v": v, "ign": ign, "dt": dt, "raw": str(raw), "bat_pct": bat_pct})

    if not volt_data:
        return {"sem_dados": True}

    volts   = sorted(d["v"] for d in volt_data)
    mediana = volts[len(volts) // 2]
    is_24v  = mediana > 20.0
    prefix  = "24" if is_24v else "12"

    carga_min  = V24_CARGA_MIN  if is_24v else V12_CARGA_MIN
    carga_crit = V24_CARGA_CRIT if is_24v else V12_CARGA_CRIT
    bat_crit   = V24_BAT_CRIT   if is_24v else V12_BAT_CRIT

    all_v       = [d["v"] for d in volt_data]
    v_med       = round(sum(all_v) / len(all_v), 2)
    v_max       = round(max(all_v), 2)
    v_min       = round(min(all_v), 2)
    v_lig       = [d["v"] for d in volt_data if d["ign"] == 1]
    v_deslig    = [d["v"] for d in volt_data if d["ign"] == 0]
    v_med_lig   = round(sum(v_lig)    / len(v_lig),    2) if v_lig    else None
    v_med_deslig = round(sum(v_deslig) / len(v_deslig), 2) if v_deslig else None

    alertas = []
    for i, d in enumerate(volt_data):
        v, ign, raw, bat_pct = d["v"], d["ign"], d["raw"], d["bat_pct"]
        tipo = sev = None
        if ign == 1 and v < carga_crit:
            tipo = f"Alternador não gera adequadamente ({v}V, esperado >{carga_min}V)"
            sev  = "🔴 CRÍTICO" if v < bat_crit else "⚠️ ATENÇÃO"
        elif ign == 1 and v < carga_min:
            tipo = f"Carga fraca do alternador ({v}V)"
            sev  = "⚠️ ATENÇÃO"
        elif ign == 0 and v < bat_crit:
            tipo = f"Bateria crítica desligada ({v}V)"
            sev  = "🔴 CRÍTICO"
        elif i > 0 and abs(v - volt_data[i-1]["v"]) > VOLT_DELTA_SPIKE:
            d2   = v - volt_data[i-1]["v"]
            tipo = f"Pico de tensão Δ{d2:+.1f}V — possível falha de sensor"
            sev  = "⚠️ ATENÇÃO"
        if tipo:
            bat_str = f"{bat_pct}%" if bat_pct >= 0 else "—"
            alertas.append({"data": raw, "v": v, "bat_pct": bat_str,
                            "ign": "🟢 ON" if ign else "⚫ OFF",
                            "tipo": tipo, "sev": sev})
            if len(alertas) >= 200:
                break

    # Histórico diário
    por_dia = {}
    for d in volt_data:
        if d["dt"] is None:
            continue
        dia = d["dt"].strftime("%d/%m/%Y")
        if dia not in por_dia:
            por_dia[dia] = {"vs": [], "vs_lig": [], "dt": d["dt"].date()}
        por_dia[dia]["vs"].append(d["v"])
        if d["ign"] == 1:
            por_dia[dia]["vs_lig"].append(d["v"])

    dias_ord = sorted(por_dia.items(), key=lambda x: x[1]["dt"])
    dias_resumo = []
    for dia_str, dd in dias_ord:
        vs     = dd["vs"]
        vs_lig = dd["vs_lig"]
        v_min_d = round(min(vs), 2)
        v_max_d = round(max(vs), 2)
        v_med_d = round(sum(vs) / len(vs), 2)
        if vs_lig:
            v_alt  = round(sum(vs_lig) / len(vs_lig), 2)
            status = ("✅ Gerando" if v_alt >= carga_min else
                      "⚠️ Fraco"  if v_alt >= carga_crit else "🔴 Não gera")
        else:
            status = "— Sem dado ligado"
        dias_resumo.append({"dia": dia_str, "v_min": v_min_d, "v_max": v_max_d,
                            "v_med": v_med_d, "status": status, "dt": dd["dt"]})

    # Regressão linear para predição
    previsao = None
    if len(dias_resumo) >= 3:
        xs = list(range(len(dias_resumo)))
        ys = [d["v_min"] for d in dias_resumo]
        n  = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        den = sum((xs[i] - mx) ** 2 for i in range(n))
        if den > 0:
            slope = num / den
            intercept = my - slope * mx
            if slope < 0:
                taxa_dia       = round(slope, 4)
                dias_para_crit = (bat_crit - intercept) / slope
                dias_rest      = max(0, round(dias_para_crit - (n - 1)))
                ultima_data    = dias_resumo[-1]["dt"]
                data_crit      = (datetime.combine(ultima_data, datetime.min.time())
                                  + timedelta(days=dias_rest)).strftime("%d/%m/%Y")
                previsao = {
                    "taxa_dia": taxa_dia,
                    "dias_restantes": dias_rest,
                    "data_critica": data_crit,
                    "v_critico": bat_crit,
                    "confianca": "alta" if n >= 7 else "média" if n >= 3 else "baixa",
                }

    recs = []
    n_alt  = sum(1 for a in alertas if "Alternador" in a["tipo"])
    n_crit = sum(1 for a in alertas if "crítica" in a["tipo"])
    n_pico = sum(1 for a in alertas if "Pico" in a["tipo"])
    if n_alt > 5:
        recs.append(f"🔴 {n_alt} eventos com alternador fraco/inoperante. Verificar correia e regulador de tensão.")
    if n_crit > 0:
        recs.append(f"🔴 {n_crit}x bateria crítica ({bat_crit}V). Substituição recomendada.")
    if n_pico > 3:
        recs.append(f"⚠️ {n_pico} picos de tensão. Verificar regulador ou mau contato.")
    if previsao and previsao["dias_restantes"] < 30:
        recs.append(f"⏰ Bateria crítica estimada em {previsao['dias_restantes']} dias "
                    f"({previsao['data_critica']}) — taxa: {abs(previsao['taxa_dia']):.4f}V/dia.")
    if v_med_lig and v_med_lig >= carga_min:
        recs.append(f"✅ Alternador gerando normalmente em média ({v_med_lig}V ligado).")
    if not recs:
        recs.append("✅ Bateria e sistema de carga dentro dos parâmetros normais.")

    return {
        "sem_dados": False,
        "tipo_bateria": f"{prefix}V",
        "kpis": {"v_med": v_med, "v_max": v_max, "v_min": v_min,
                 "v_med_lig": v_med_lig, "v_med_deslig": v_med_deslig,
                 "n_alertas": len(alertas), "is_24v": is_24v},
        "alertas": alertas, "dias_resumo": dias_resumo,
        "previsao": previsao, "recomendacoes": recs,
        "limiares": {"carga_min": carga_min, "bat_crit": bat_crit},
    }


class BateriaMixin:

    def _build_bateria(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 🔋 Bateria ")

        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._batkpis = {}
        for key, title, col in [
            ("tipo",      "TIPO",         C["blue"]),
            ("v_med",     "TENSÃO MÉDIA", C["accent"]),
            ("v_min",     "TENSÃO MÍN.",  C["danger"]),
            ("v_max",     "TENSÃO MÁX.",  C["success"]),
            ("v_med_lig", "MÉD. LIGADO", C["accent"]),
            ("v_med_des", "MÉD. DESLIG.",C["text_mid"]),
            ("n_alertas", "ALERTAS",      C["warn"]),
        ]:
            self._batkpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        self._bat_pred_frame = tk.Frame(f, bg=C["surface3"],
                                        highlightthickness=1, highlightbackground=C["border"])
        self._bat_pred_frame.pack(fill="x", padx=14, pady=(8, 4))
        self._bat_pred_lbl = lbl(self._bat_pred_frame,
                                  "⏳ Aguardando dados para análise de tendência...",
                                  9, col=C["text_dim"], bg=C["surface3"])
        self._bat_pred_lbl.pack(padx=12, pady=8, anchor="w")

        panes = tk.Frame(f, bg=C["bg"])
        panes.pack(fill="both", expand=True)
        left  = tk.Frame(panes, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(panes, bg=C["surface2"], width=290)
        right.pack(side="right", fill="y", padx=(2, 0))
        right.pack_propagate(False)

        lbl(left, "Alertas de Bateria / Alternador", 10, True, C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))
        apply_treeview_style("TBat", C["warn"])
        inner = tk.Frame(left, bg=C["bg"])
        inner.pack(fill="both", expand=True)
        self._tree_bat = ttk.Treeview(inner, columns=_COLS_A, show="headings", style="TBat.Treeview", height=14)
        for c, w in zip(_COLS_A, _WIDTHS_A):
            self._tree_bat.heading(c, text=c, anchor="w")
            self._tree_bat.column(c, width=w, anchor="w", stretch=True)
        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._tree_bat.yview)
        self._tree_bat.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_bat.pack(fill="both", expand=True)
        mk_export_btn(left, self._tree_bat).pack(anchor="e", padx=8, pady=4)

        lbl(right, "Histórico Diário", 10, True, C["accent"], bg=C["surface2"]).pack(padx=10, pady=(10, 4), anchor="w")
        apply_treeview_style("TBatDia", C["blue"])
        inner_r = tk.Frame(right, bg=C["surface2"])
        inner_r.pack(fill="both", expand=True, padx=4)
        self._tree_bat_dia = ttk.Treeview(inner_r, columns=_COLS_D, show="headings", style="TBatDia.Treeview", height=10)
        for c, w in zip(_COLS_D, _WIDTHS_D):
            self._tree_bat_dia.heading(c, text=c, anchor="w")
            self._tree_bat_dia.column(c, width=w, anchor="w", stretch=False)
        vsb2 = ttk.Scrollbar(inner_r, orient="vertical", command=self._tree_bat_dia.yview)
        self._tree_bat_dia.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self._tree_bat_dia.pack(fill="both", expand=True)
        tk.Frame(right, bg=C["border"], height=1).pack(fill="x", pady=6)
        lbl(right, "Diagnóstico", 10, True, C["accent"], bg=C["surface2"]).pack(padx=10, pady=(0, 4), anchor="w")
        self._bat_rec_frame = tk.Frame(right, bg=C["surface2"])
        self._bat_rec_frame.pack(fill="x", padx=8, pady=(0, 8))
        self._bat_no_data = lbl(f, "Sem dados de voltagem nesta consulta.", 9, col=C["text_dim"])

        register_theme_listener(lambda: (apply_treeview_style("TBat", C["warn"]),
                                          apply_treeview_style("TBatDia", C["blue"])))

    def _render_bateria(self, points: list[dict]):
        m = calc_bateria(points)
        if m.get("sem_dados"):
            self._bat_no_data.pack(pady=30)
            return
        self._bat_no_data.pack_forget()

        k   = m["kpis"]
        lim = m["limiares"]
        self._batkpis["tipo"].config(     text=m["tipo_bateria"])
        self._batkpis["v_med"].config(    text=f"{k['v_med']}V")
        self._batkpis["v_min"].config(    text=f"{k['v_min']}V",
                                           fg=C["danger"] if k["v_min"] < lim["bat_crit"] else C["warn"])
        self._batkpis["v_max"].config(    text=f"{k['v_max']}V")
        self._batkpis["v_med_lig"].config(text=f"{k['v_med_lig']}V" if k["v_med_lig"] else "—",
                                           fg=C["success"] if k["v_med_lig"] and k["v_med_lig"] >= lim["carga_min"] else C["warn"])
        self._batkpis["v_med_des"].config(text=f"{k['v_med_deslig']}V" if k["v_med_deslig"] else "—")
        self._batkpis["n_alertas"].config(text=str(k["n_alertas"]),
                                           fg=C["danger"] if k["n_alertas"] > 10 else C["text"])

        prev = m.get("previsao")
        if prev:
            dias = prev["dias_restantes"]
            cor  = C["danger"] if dias < 14 else (C["warn"] if dias < 45 else C["success"])
            self._bat_pred_lbl.config(
                text=(f"📉 Degradação: {abs(prev['taxa_dia']):.4f}V/dia  |  "
                      f"Crítica estimada: {prev['data_critica']} (~{dias} dias)  |  "
                      f"Confiança: {prev['confianca']}"), fg=cor)
        else:
            self._bat_pred_lbl.config(
                text="✅ Sem tendência de degradação detectada no período.", fg=C["success"])

        for r in self._tree_bat.get_children():
            self._tree_bat.delete(r)
        for a in m["alertas"]:
            tag = "crit" if "CRÍTICO" in a["sev"] else "warn"
            self._tree_bat.insert("", "end", tags=(tag,), values=(
                a["data"], a["v"], a["bat_pct"], a["ign"], a["tipo"], a["sev"]))
        self._tree_bat.tag_configure("crit", foreground=C["danger"])
        self._tree_bat.tag_configure("warn", foreground=C["warn"])

        for r in self._tree_bat_dia.get_children():
            self._tree_bat_dia.delete(r)
        for d in m["dias_resumo"]:
            tag = "fail" if "Não" in d["status"] else ("warn" if "Fraco" in d["status"] else "ok")
            self._tree_bat_dia.insert("", "end", tags=(tag,), values=(
                d["dia"], d["v_min"], d["v_max"], d["v_med"], d["status"]))
        self._tree_bat_dia.tag_configure("fail", foreground=C["danger"])
        self._tree_bat_dia.tag_configure("warn", foreground=C["warn"])
        self._tree_bat_dia.tag_configure("ok",   foreground=C["success"])

        for w in self._bat_rec_frame.winfo_children():
            w.destroy()
        for rec in m["recomendacoes"]:
            card = tk.Frame(self._bat_rec_frame, bg=C["surface3"],
                            highlightthickness=1, highlightbackground=C["border"])
            card.pack(fill="x", pady=2)
            lbl(card, rec, 8, col=C["text"], bg=C["surface3"], wraplength=255).pack(padx=8, pady=5, anchor="w")