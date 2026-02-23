"""
tabs/custos.py
Aba 12 — Centro de Custos e Gestão de Frota:
  - Custo por Veículo (período)
  - Ranking por Motorista
  - Análise de Trajeto (rota detalhada + paradas)
  - Jornada do Motorista (HOS - Hours of Service)
  - Relatório de Ajudante/Passageiro
  - Eficiência de Frota (comparativo de veículos)
  - Conformidade (velocidade, ociosidade, alertas)
  - Configuração de Parâmetros
"""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt

from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, ts
from core import (
    get_all_events, find_vehicle, extract_list, api_get, api_put,
    safe_int, safe_float, safe_str, haversine, hms,
)
from widgets.alert_colors import _ac
from widgets import (
    lbl, ent, btn, sec, txtbox, write, loading, ok, err,
    mk_export_btn, interval_row, FilterableTree,
)


# ── Helpers internos ──────────────────────────────────────────────────────────

def _parse_dt(s: str):
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            pass
    return None


def _ts(dt: datetime) -> str:
    return str(int(dt.timestamp()))


def _hms(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fetch_events(vid: int, ini: datetime, fim: datetime) -> list:
    raw = api_get(
        f"/events/interval/id/{vid}/begin/{_ts(ini)}/end/{_ts(fim)}"
    ).get("data", [])
    return extract_list(raw)


def _process_events(evs: list):
    """Processa lista de eventos e retorna métricas consolidadas."""
    km = 0.0
    t_on = t_off = t_ocio = 0.0
    vmax = 0
    velocidades = []
    paradas = []           # [(inicio_dt, fim_dt, lat, lon, duracao_s)]
    trechos = []           # [(dt, lat, lon, vel, ign)]
    prev = None
    parada_inicio = None
    parada_lat = parada_lon = None

    for ev in evs:
        vel = abs(safe_int(ev.get("ras_eve_velocidade", 0)))
        ign = safe_int(ev.get("ras_eve_ignicao", 0))
        lat = ev.get("ras_eve_latitude")
        lon = ev.get("ras_eve_longitude")
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            lat = lon = None

        dt = _parse_dt(ev.get("ras_eve_data_gps", ""))

        if dt and lat is not None:
            trechos.append((dt, lat, lon, vel, ign))

        if prev and dt and prev[0]:
            s = max(0, (dt - prev[0]).total_seconds())
            if prev[4]:   # ignição ON
                t_on += s
                if prev[3] == 0:  # parado com ignição
                    t_ocio += s
            else:
                t_off += s

        if prev and prev[1] is not None and lat is not None:
            try:
                d = haversine(prev[1], prev[2], lat, lon)
                km += d
            except Exception:
                pass

        # Detecção de paradas (vel=0 por mais de 2 min)
        if vel == 0 and ign and lat is not None:
            if parada_inicio is None:
                parada_inicio = dt
                parada_lat = lat
                parada_lon = lon
        else:
            if parada_inicio is not None and dt and parada_inicio:
                dur = (dt - parada_inicio).total_seconds()
                if dur >= 120:
                    paradas.append((parada_inicio, dt, parada_lat, parada_lon, dur))
            parada_inicio = None

        vmax = max(vmax, vel)
        if vel > 0:
            velocidades.append(vel)

        prev = (dt, lat, lon, vel, ign)

    vmed = sum(velocidades) / len(velocidades) if velocidades else 0
    excessos = sum(1 for v in velocidades if v > 80)

    return {
        "km": km,
        "t_on": t_on,
        "t_off": t_off,
        "t_ocio": t_ocio,
        "vmax": vmax,
        "vmed": vmed,
        "excessos_80": excessos,
        "paradas": paradas,
        "trechos": trechos,
        "n_eventos": len(evs),
    }


# ═══════════════════════════════════════════════════════════════════════════════
class TabCustos(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._params = {
            "preco_comb":   6.20,
            "consumo_km_l": 10.0,
            "custo_h_mot":  25.0,
            "custo_h_ajud": 18.0,
            "custo_manut":  0.08,
            "vel_limite":   80,
            "pen_excesso":  10.0,
            "ocioso_l_h":   0.5,
        }
        self._build()

    def _p(self, key):
        return self._params.get(key, 0)

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_custo_veiculo(nb)
        self._tab_trajeto(nb)
        self._tab_jornada(nb)
        self._tab_ajudante(nb)
        self._tab_eficiencia(nb)
        self._tab_conformidade(nb)
        self._tab_ranking(nb)
        self._tab_parametros(nb)

    # ── helpers de UI ──────────────────────────────────────────────────────────
    def _veiculo_row(self, parent):
        lbl(parent, "Veículo (placa/nome):", 9, col=C["text_mid"]).pack(anchor="w", pady=(0, 2))
        e = ent(parent); e.pack(fill="x", ipady=5)
        return e

    def _motorista_row(self, parent):
        lbl(parent, "Motorista (nome):", 9, col=C["text_mid"]).pack(anchor="w", pady=(0, 2))
        e = ent(parent); e.pack(fill="x", ipady=5)
        return e

    # ══════════════════════════════════════════════════════════════════════════
    # 1. CUSTO POR VEÍCULO
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_custo_veiculo(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  💰 Custo/Veículo  ")
        ph = tk.Frame(f, bg=C["bg"]); ph.pack(fill="x", padx=8, pady=6)
        e_v = self._veiculo_row(ph)
        ei, ef = interval_row(ph)

        rp = tk.Frame(ph, bg=C["bg"]); rp.pack(fill="x", pady=4)
        lbl(rp, "R$/L:", 9, col=C["text_mid"]).pack(side="left")
        e_pr = ent(rp, w=7); e_pr.pack(side="left", padx=2, ipady=3); e_pr.insert(0, "6.20")
        lbl(rp, " km/L:", 9, col=C["text_mid"]).pack(side="left")
        e_co = ent(rp, w=7); e_co.pack(side="left", padx=2, ipady=3); e_co.insert(0, "10.0")
        lbl(rp, " R$/h mot.:", 9, col=C["text_mid"]).pack(side="left")
        e_mo = ent(rp, w=7); e_mo.pack(side="left", padx=2, ipady=3); e_mo.insert(0, "25.0")
        lbl(rp, " R$/h ajud.:", 9, col=C["text_mid"]).pack(side="left")
        e_aj = ent(rp, w=7); e_aj.pack(side="left", padx=2, ipady=3); e_aj.insert(0, "18.0")
        lbl(rp, " R$/km manut.:", 9, col=C["text_mid"]).pack(side="left")
        e_ma = ent(rp, w=7); e_ma.pack(side="left", padx=2, ipady=3); e_ma.insert(0, "0.08")

        _, res = txtbox(f, 20); _.pack(fill="both", expand=True, padx=8, pady=4)

        def calcular():
            q = e_v.get().strip()
            if not q: return
            loading(res)
            def task():
                entry = find_vehicle(q)
                if not entry:
                    err(res, "Veículo não encontrado."); return
                vid = safe_int(entry.get("ras_vei_id", 0))
                try:
                    ini = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                    preco = float(e_pr.get()); cons = float(e_co.get())
                    custo_h = float(e_mo.get()); custo_aj = float(e_aj.get())
                    custo_km_m = float(e_ma.get())
                except Exception:
                    write(res, "⚠ Parâmetros inválidos.", C["warn"]); return

                evs = _fetch_events(vid, ini, fim)
                if not evs:
                    write(res, "ℹ Nenhum evento no período.", C["text_mid"]); return

                m = _process_events(evs)
                km = m["km"]; t_on = m["t_on"]; t_ocio = m["t_ocio"]
                h_on = t_on / 3600

                litros     = km / cons if cons > 0 else 0
                c_comb     = litros * preco
                c_mot      = h_on * custo_h
                c_aj       = h_on * custo_aj
                c_manut    = km * custo_km_m
                c_ocio     = (t_ocio / 3600) * self._p("ocioso_l_h") * preco
                pen_exces  = m["excessos_80"] * self._p("pen_excesso")
                c_total    = c_comb + c_mot + c_aj + c_manut + c_ocio + pen_exces
                c_km       = c_total / km if km > 0 else 0

                lines = [
                    "=" * 60,
                    f"  RELATÓRIO DE CUSTOS — {entry.get('ras_vei_placa','—')}",
                    f"  {entry.get('ras_vei_veiculo','—')}",
                    f"  Motorista : {entry.get('ras_mot_nome','—')}",
                    f"  Período   : {ini:%d/%m/%Y %H:%M} → {fim:%d/%m/%Y %H:%M}",
                    "",
                    "  ─── Desempenho ──────────────────────────────────────",
                    f"    Distância percorrida    : {km:>10.2f} km",
                    f"    Velocidade máxima       : {m['vmax']:>10} km/h",
                    f"    Velocidade média        : {m['vmed']:>10.1f} km/h",
                    f"    Excessos de velocidade  : {m['excessos_80']:>10}  (>80km/h)",
                    f"    Nº de paradas detectadas: {len(m['paradas']):>10}",
                    f"    Tempo ignição ON        : {_hms(t_on):>13}",
                    f"    Tempo ocioso (ign. ON)  : {_hms(t_ocio):>13}",
                    f"    Tempo ignição OFF       : {_hms(m['t_off']):>13}",
                    "",
                    "  ─── Estimativa de Custos ───────────────────────────",
                    f"    Litros consumidos       : {litros:>10.1f} L",
                    f"    Custo combustível       : R$ {c_comb:>9.2f}",
                    f"    Custo motorista         : R$ {c_mot:>9.2f}  ({h_on:.1f}h × R${custo_h:.2f})",
                    f"    Custo ajudante          : R$ {c_aj:>9.2f}  ({h_on:.1f}h × R${custo_aj:.2f})",
                    f"    Custo manutenção        : R$ {c_manut:>9.2f}  ({km:.1f}km × R${custo_km_m:.3f})",
                    f"    Custo ociosidade        : R$ {c_ocio:>9.2f}",
                    f"    Penalidades excesso vel.: R$ {pen_exces:>9.2f}  ({m['excessos_80']} ocorr.)",
                    f"  {'─'*52}",
                    f"    CUSTO TOTAL ESTIMADO    : R$ {c_total:>9.2f}",
                    f"    Custo por km            : R$ {c_km:>9.2f}/km",
                    "",
                    "  ─── Parâmetros Utilizados ──────────────────────────",
                    f"    Combustível    : R$ {preco:.2f}/L  |  Consumo: {cons:.1f} km/L",
                    f"    Motorista      : R$ {custo_h:.2f}/h  |  Ajudante: R$ {custo_aj:.2f}/h",
                    f"    Manutenção     : R$ {custo_km_m:.3f}/km",
                    "=" * 60,
                ]
                write(res, "\n".join(lines))
            threading.Thread(target=task, daemon=True).start()

        btn(ph, "💰 CALCULAR CUSTOS", calcular, C["success"]).pack(pady=(6, 0))
        mk_export_btn(ph, res, is_text=True).pack(pady=(4, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # 2. ANÁLISE DE TRAJETO
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_trajeto(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  🗺 Trajeto  ")
        ph = tk.Frame(f, bg=C["bg"]); ph.pack(fill="x", padx=8, pady=6)
        e_v = self._veiculo_row(ph)
        ei, ef = interval_row(ph)

        rp = tk.Frame(ph, bg=C["bg"]); rp.pack(fill="x", pady=2)
        lbl(rp, "Parada mínima (min):", 9, col=C["text_mid"]).pack(side="left")
        e_pm = ent(rp, w=6); e_pm.pack(side="left", padx=4, ipady=3); e_pm.insert(0, "5")
        lbl(rp, "  Vel. excesso (km/h):", 9, col=C["text_mid"]).pack(side="left")
        e_vel = ent(rp, w=6); e_vel.pack(side="left", padx=4, ipady=3); e_vel.insert(0, "80")

        _, res = txtbox(f, 22); _.pack(fill="both", expand=True, padx=8, pady=4)

        def analisar():
            q = e_v.get().strip()
            if not q: return
            loading(res)
            def task():
                entry = find_vehicle(q)
                if not entry:
                    err(res, "Veículo não encontrado."); return
                vid = safe_int(entry.get("ras_vei_id", 0))
                try:
                    ini = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                    min_parada = float(e_pm.get()) * 60
                    vel_lim = float(e_vel.get())
                except Exception:
                    write(res, "⚠ Parâmetros inválidos.", C["warn"]); return

                evs = _fetch_events(vid, ini, fim)
                if not evs:
                    write(res, "ℹ Nenhum evento.", C["text_mid"]); return

                # Processa trechos e paradas com limite customizado
                km = 0.0; paradas = []; trechos_mov = []
                t_on = t_ocio = 0.0
                vmax = 0; velocidades = []
                parada_inicio = parada_lat = parada_lon = None
                prev = None

                for ev in evs:
                    vel  = abs(safe_int(ev.get("ras_eve_velocidade", 0)))
                    ign  = safe_int(ev.get("ras_eve_ignicao", 0))
                    dt   = _parse_dt(ev.get("ras_eve_data_gps", ""))
                    try:
                        lat = float(ev.get("ras_eve_latitude"))
                        lon = float(ev.get("ras_eve_longitude"))
                    except Exception:
                        lat = lon = None

                    if prev and dt and prev[0] and lat is not None:
                        s = max(0, (dt - prev[0]).total_seconds())
                        if prev[4]: t_on += s
                        if prev[4] and prev[3] == 0: t_ocio += s
                        if prev[1] is not None:
                            try: km += haversine(prev[1], prev[2], lat, lon)
                            except Exception: pass

                    vmax = max(vmax, vel)
                    if vel > 0: velocidades.append(vel)

                    if vel == 0 and ign and lat is not None:
                        if parada_inicio is None:
                            parada_inicio = dt; parada_lat = lat; parada_lon = lon
                    else:
                        if parada_inicio and dt:
                            dur = (dt - parada_inicio).total_seconds()
                            if dur >= min_parada:
                                paradas.append((parada_inicio, dt, parada_lat, parada_lon, dur))
                        parada_inicio = None

                    if vel > 0 and lat is not None:
                        trechos_mov.append((dt, lat, lon, vel))

                    prev = (dt, lat, lon, vel, ign)

                excessos = [(dt, lat, lon, v) for dt, lat, lon, v in trechos_mov if v > vel_lim]
                vmed = sum(velocidades) / len(velocidades) if velocidades else 0

                lines = [
                    "=" * 62,
                    f"  ANÁLISE DE TRAJETO — {entry.get('ras_vei_placa','—')}",
                    f"  {entry.get('ras_vei_veiculo','—')}  |  Motorista: {entry.get('ras_mot_nome','—')}",
                    f"  Período: {ini:%d/%m/%Y %H:%M} → {fim:%d/%m/%Y %H:%M}",
                    "",
                    "  ─── Resumo do Percurso ────────────────────────────",
                    f"    Distância total     : {km:>10.2f} km",
                    f"    Velocidade máxima   : {vmax:>10} km/h",
                    f"    Velocidade média    : {vmed:>10.1f} km/h",
                    f"    Pontos de movimento : {len(trechos_mov):>10}",
                    f"    Eventos totais      : {len(evs):>10}",
                    f"    Tempo ignição ON    : {_hms(t_on):>13}",
                    f"    Tempo ocioso        : {_hms(t_ocio):>13}",
                    "",
                    f"  ─── Paradas Detectadas (≥{int(min_parada//60)} min) ──────────────",
                ]

                if paradas:
                    for i, (p0, p1, plat, plon, dur) in enumerate(paradas, 1):
                        p0s = p0.strftime("%H:%M:%S") if p0 else "—"
                        p1s = p1.strftime("%H:%M:%S") if p1 else "—"
                        coord = f"({plat:.4f},{plon:.4f})" if plat else "—"
                        lines.append(
                            f"    #{i:>2}  {p0s} → {p1s}  dur:{_hms(dur)}  {coord}"
                        )
                else:
                    lines.append("    Nenhuma parada significativa detectada.")

                lines += [
                    "",
                    f"  ─── Excessos de Velocidade (>{int(vel_lim)} km/h) ─────────────",
                ]
                if excessos:
                    lines.append(f"    Total: {len(excessos)} ocorrências")
                    for dt_e, lat_e, lon_e, v_e in excessos[:20]:
                        ts_e = dt_e.strftime("%H:%M:%S") if dt_e else "—"
                        coord = f"({lat_e:.4f},{lon_e:.4f})" if lat_e else "—"
                        lines.append(f"    {ts_e}  {v_e:>4} km/h  {coord}")
                    if len(excessos) > 20:
                        lines.append(f"    ... e mais {len(excessos)-20} ocorrências.")
                else:
                    lines.append("    ✓ Nenhum excesso de velocidade registrado.")

                lines.append("=" * 62)
                write(res, "\n".join(lines))
            threading.Thread(target=task, daemon=True).start()

        btn(ph, "🗺 ANALISAR TRAJETO", analisar, C["accent"]).pack(pady=(6, 0))
        mk_export_btn(ph, res, is_text=True).pack(pady=(4, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # 3. JORNADA DO MOTORISTA (HOS)
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_jornada(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ⏱ Jornada  ")
        ph = tk.Frame(f, bg=C["bg"]); ph.pack(fill="x", padx=8, pady=6)
        e_v = self._veiculo_row(ph)
        ei, ef = interval_row(ph)

        rp = tk.Frame(ph, bg=C["bg"]); rp.pack(fill="x", pady=2)
        lbl(rp, "Limite jornada (h):", 9, col=C["text_mid"]).pack(side="left")
        e_lj = ent(rp, w=5); e_lj.pack(side="left", padx=4, ipady=3); e_lj.insert(0, "8")
        lbl(rp, "  Intervalo mínimo (min):", 9, col=C["text_mid"]).pack(side="left")
        e_iv = ent(rp, w=5); e_iv.pack(side="left", padx=4, ipady=3); e_iv.insert(0, "30")
        lbl(rp, "  Folga mín. entre turnos (h):", 9, col=C["text_mid"]).pack(side="left")
        e_fo = ent(rp, w=5); e_fo.pack(side="left", padx=4, ipady=3); e_fo.insert(0, "11")

        _, res = txtbox(f, 22); _.pack(fill="both", expand=True, padx=8, pady=4)

        def jornada():
            q = e_v.get().strip()
            if not q: return
            loading(res)
            def task():
                entry = find_vehicle(q)
                if not entry:
                    err(res, "Veículo não encontrado."); return
                vid = safe_int(entry.get("ras_vei_id", 0))
                try:
                    ini  = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim  = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                    lim_h  = float(e_lj.get())
                    iv_min = float(e_iv.get()) * 60
                    fo_min = float(e_fo.get()) * 3600
                except Exception:
                    write(res, "⚠ Parâmetros inválidos.", C["warn"]); return

                evs = _fetch_events(vid, ini, fim)
                if not evs:
                    write(res, "ℹ Nenhum evento.", C["text_mid"]); return

                # Agrupa por turnos (separados por OFF ≥ folga)
                turnos = []
                turno_atual = []
                prev_dt = None

                for ev in evs:
                    dt = _parse_dt(ev.get("ras_eve_data_gps", ""))
                    if dt is None: continue
                    ign = safe_int(ev.get("ras_eve_ignicao", 0))

                    if prev_dt and (dt - prev_dt).total_seconds() >= fo_min:
                        if turno_atual: turnos.append(turno_atual)
                        turno_atual = []

                    turno_atual.append((dt, ign, ev))
                    prev_dt = dt

                if turno_atual: turnos.append(turno_atual)

                lines = [
                    "=" * 62,
                    f"  JORNADA DE TRABALHO — {entry.get('ras_vei_placa','—')}",
                    f"  Motorista: {entry.get('ras_mot_nome','—')}",
                    f"  Período  : {ini:%d/%m/%Y %H:%M} → {fim:%d/%m/%Y %H:%M}",
                    f"  Limite de jornada: {lim_h:.0f}h  |  Intervalo mín: {iv_min//60:.0f}min  |  Folga: {fo_min//3600:.0f}h",
                    "",
                ]

                total_on = total_km = 0.0
                alertas = []

                for i, turno in enumerate(turnos, 1):
                    if not turno: continue
                    dt0 = turno[0][0]; dt1 = turno[-1][0]
                    dur = (dt1 - dt0).total_seconds() if dt0 and dt1 else 0
                    t_on = t_ocio = km_t = 0.0
                    vmax_t = 0; prev = None

                    for dt, ign, ev in turno:
                        vel = abs(safe_int(ev.get("ras_eve_velocidade", 0)))
                        try:
                            lat = float(ev.get("ras_eve_latitude"))
                            lon = float(ev.get("ras_eve_longitude"))
                        except Exception:
                            lat = lon = None
                        if prev and prev[0]:
                            s = max(0, (dt - prev[0]).total_seconds())
                            if prev[1]: t_on += s
                            if prev[1] and prev[3] == 0: t_ocio += s
                        if prev and prev[2] is not None and lat is not None:
                            try: km_t += haversine(prev[2], prev[3], lat, lon)
                            except Exception: pass
                        vmax_t = max(vmax_t, vel)
                        prev = (dt, ign, lat, lon)

                    total_on += t_on; total_km += km_t
                    h_on = t_on / 3600
                    status = "⚠ EXCEDIDO" if h_on > lim_h else "✓ OK"
                    if h_on > lim_h: alertas.append(f"Turno {i}: jornada excedida ({h_on:.1f}h > {lim_h:.0f}h)")

                    lines += [
                        f"  ─── Turno #{i}  [{status}] ─────────────────────────",
                        f"    Início     : {dt0:%d/%m/%Y %H:%M:%S}" if dt0 else "    Início: —",
                        f"    Término    : {dt1:%d/%m/%Y %H:%M:%S}" if dt1 else "    Término: —",
                        f"    Duração    : {_hms(dur)}",
                        f"    T. ign. ON : {_hms(t_on)}  ({h_on:.2f}h)",
                        f"    Ociosidade : {_hms(t_ocio)}  ({t_ocio/3600:.2f}h)",
                        f"    Distância  : {km_t:.2f} km",
                        f"    Vel. máx.  : {vmax_t} km/h",
                        "",
                    ]

                lines += [
                    "  ─── Consolidado ────────────────────────────────────",
                    f"    Total de turnos : {len(turnos)}",
                    f"    Total ign. ON   : {_hms(total_on)}  ({total_on/3600:.2f}h)",
                    f"    Total km        : {total_km:.2f} km",
                ]

                if alertas:
                    lines += ["", "  ─── ⚠ ALERTAS ────────────────────────────────────"]
                    for a in alertas: lines.append(f"    ! {a}")

                lines.append("=" * 62)
                write(res, "\n".join(lines))
            threading.Thread(target=task, daemon=True).start()

        btn(ph, "⏱ ANALISAR JORNADA", jornada, C["warn"]).pack(pady=(6, 0))
        mk_export_btn(ph, res, is_text=True).pack(pady=(4, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # 4. RELATÓRIO DE AJUDANTE / PASSAGEIRO
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_ajudante(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  👥 Ajudante  ")
        ph = tk.Frame(f, bg=C["bg"]); ph.pack(fill="x", padx=8, pady=6)

        lbl(ph, "Selecione o ajudante ou passageiro:", 9, col=C["text_mid"]).pack(anchor="w")
        cb_frame = tk.Frame(ph, bg=C["bg"]); cb_frame.pack(fill="x", pady=4)
        cb_var = tk.StringVar()
        cb = ttk.Combobox(cb_frame, textvariable=cb_var, state="readonly", width=40)
        cb.pack(side="left", padx=(0, 8))

        lbl(ph, "Veículo (placa/nome, opcional):", 9, col=C["text_mid"]).pack(anchor="w", pady=(4, 2))
        e_v = ent(ph); e_v.pack(fill="x", ipady=4)
        ei, ef = interval_row(ph)

        rp = tk.Frame(ph, bg=C["bg"]); rp.pack(fill="x", pady=2)
        lbl(rp, "R$/h ajudante:", 9, col=C["text_mid"]).pack(side="left")
        e_aj = ent(rp, w=7); e_aj.pack(side="left", padx=4, ipady=3); e_aj.insert(0, "18.0")

        _passageiros_cache = {}

        def carregar_passageiros():
            def task():
                from core import get_passengers_all
                pas = get_passengers_all()
                _passageiros_cache.clear()
                for p in pas:
                    nome = safe_str(p.get("ras_pas_nome"), "—")
                    pid  = safe_str(p.get("ras_pas_id"), "")
                    _passageiros_cache[f"{nome} (ID:{pid})"] = p
                vals = list(_passageiros_cache.keys()) or ["(nenhum encontrado)"]
                cb["values"] = vals
                if vals: cb.set(vals[0])
            threading.Thread(target=task, daemon=True).start()

        btn(cb_frame, "🔄 Carregar", carregar_passageiros, C["accent"]).pack(side="left")

        _, res = txtbox(f, 18); _.pack(fill="both", expand=True, padx=8, pady=4)

        def relatorio():
            sel = cb_var.get()
            if not sel or sel not in _passageiros_cache:
                write(res, "⚠ Selecione um ajudante.", C["warn"]); return
            pas = _passageiros_cache[sel]
            loading(res)
            def task():
                try:
                    ini = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                    custo_aj = float(e_aj.get())
                except Exception:
                    write(res, "⚠ Parâmetros inválidos.", C["warn"]); return

                evs_all = get_all_events()
                # Se informado veículo, filtra
                q_v = e_v.get().strip()
                rfid = safe_str(pas.get("ras_pas_rfid"), "")
                horas_est = (fim - ini).total_seconds() / 3600
                custo_t = horas_est * custo_aj

                lines = [
                    "=" * 60,
                    f"  RELATÓRIO DE AJUDANTE",
                    f"  Nome    : {pas.get('ras_pas_nome','—')}",
                    f"  RFID    : {rfid or '—'}",
                    f"  Empresa : {pas.get('ras_pas_empresa','—')}",
                    f"  Setor   : {pas.get('ras_pas_setor','—')}",
                    f"  Cargo   : {pas.get('ras_pas_cargo','—')}",
                    f"  Período : {ini:%d/%m/%Y %H:%M} → {fim:%d/%m/%Y %H:%M}",
                    "",
                    "  ─── Estimativa de Custo ───────────────────────────",
                    f"    Horas no período  : {horas_est:>8.2f} h",
                    f"    Custo/hora        : R$ {custo_aj:>8.2f}",
                    f"    CUSTO ESTIMADO    : R$ {custo_t:>8.2f}",
                    "",
                    "  ─── Veículos no Período (eventos atuais) ──────────",
                ]

                veiculos_assoc = set()
                for ev in evs_all:
                    veiculos_assoc.add(
                        f"  {ev.get('ras_vei_placa','—')} — {ev.get('ras_vei_veiculo','—')} "
                        f"[Mot: {ev.get('ras_mot_nome','—')}]"
                    )

                if q_v:
                    entry = find_vehicle(q_v)
                    if entry:
                        lines.append(
                            f"    {entry.get('ras_vei_placa','—')} — {entry.get('ras_vei_veiculo','—')}"
                        )
                    else:
                        lines.append("    Veículo não encontrado.")
                else:
                    lines.append("    (Sem filtro de veículo — associação via RFID quando disponível)")

                lines += [
                    "",
                    "  ─── Cadastro ───────────────────────────────────────",
                    f"    Cadastrado em: {pas.get('ras_pas_data_cadastro','—')}",
                    f"    Cliente ID   : {pas.get('ras_pas_id_cli','—')}",
                    "=" * 60,
                ]
                write(res, "\n".join(lines))
            threading.Thread(target=task, daemon=True).start()

        btn(ph, "👥 GERAR RELATÓRIO", relatorio, C["success"]).pack(pady=(6, 0))
        mk_export_btn(ph, res, is_text=True).pack(pady=(4, 0))
        self.after(600, carregar_passageiros)

    # ══════════════════════════════════════════════════════════════════════════
    # 5. EFICIÊNCIA DE FROTA (comparativo)
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_eficiencia(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  📊 Eficiência  ")
        ph = tk.Frame(f, bg=C["bg"]); ph.pack(fill="x", padx=8, pady=6)

        lbl(ph, "Análise comparativa de TODOS os veículos (última posição):", 9, col=C["text_mid"]).pack(anchor="w")
        lb = lbl(ph, "", col=C["text_dim"]); lb.pack(anchor="w", pady=2)

        cols = ("Veículo", "Placa", "Motorista", "Vel.Atual", "Ignição", "Satélites", "Bat.(%)", "Última GPS")
        widths = (130, 90, 150, 80, 70, 80, 70, 140)
        ft = FilterableTree(f, cols, widths, "EficienciaFrota", C["accent"], 14)
        self._ft_efic = ft

        def _tags():
            ft.tag_configure("on",  background=_ac("al1"))
            ft.tag_configure("off", background=C["surface2"])
            ft.tag_configure("mov", background=_ac("al2"))
        _tags(); register_theme_listener(_tags)

        def carregar():
            lb.config(text="⏳ Carregando...")
            def task():
                evs = get_all_events()
                rows = []
                for ev in evs:
                    ign = safe_int(ev.get("ras_eve_ignicao", 0))
                    vel = abs(safe_int(ev.get("ras_eve_velocidade", 0)))
                    bat = safe_int(ev.get("ras_eve_porc_bat_backup", 0))
                    sat = safe_int(ev.get("ras_ras_sinal_gps", 0))
                    dgps = ev.get("ras_eve_data_gps", "—")
                    placa = safe_str(ev.get("ras_vei_placa"), "—")
                    veic  = safe_str(ev.get("ras_vei_veiculo"), "—")
                    mot   = safe_str(ev.get("ras_mot_nome"), "—")
                    v_str = f"{vel} km/h" if vel > 0 else "Parado"
                    i_str = "ON" if ign else "OFF"
                    tag = "mov" if vel > 0 else ("on" if ign else "off")
                    rows.append(((veic, placa, mot, v_str, i_str, sat, f"{bat}%", dgps), tag))
                ft.load(rows)
                lb.config(text=f"{len(evs)} veículos | {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        btn(ph, "🔄 ATUALIZAR", carregar, C["accent"]).pack(side="left", pady=4)
        mk_export_btn(ph, ft.tree).pack(side="left", padx=8)
        self.after(500, carregar)

    # ══════════════════════════════════════════════════════════════════════════
    # 6. CONFORMIDADE
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_conformidade(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ✅ Conformidade  ")
        ph = tk.Frame(f, bg=C["bg"]); ph.pack(fill="x", padx=8, pady=6)
        e_v = self._veiculo_row(ph)
        ei, ef = interval_row(ph)

        rp = tk.Frame(ph, bg=C["bg"]); rp.pack(fill="x", pady=2)
        lbl(rp, "Vel. limite (km/h):", 9, col=C["text_mid"]).pack(side="left")
        e_vl = ent(rp, w=6); e_vl.pack(side="left", padx=4, ipady=3); e_vl.insert(0, "80")
        lbl(rp, "  Ociosidade máx. (h):", 9, col=C["text_mid"]).pack(side="left")
        e_oc = ent(rp, w=6); e_oc.pack(side="left", padx=4, ipady=3); e_oc.insert(0, "1.0")
        lbl(rp, "  Jornada máx. (h):", 9, col=C["text_mid"]).pack(side="left")
        e_jm = ent(rp, w=6); e_jm.pack(side="left", padx=4, ipady=3); e_jm.insert(0, "8.0")

        _, res = txtbox(f, 22); _.pack(fill="both", expand=True, padx=8, pady=4)

        def verificar():
            q = e_v.get().strip()
            if not q: return
            loading(res)
            def task():
                entry = find_vehicle(q)
                if not entry:
                    err(res, "Veículo não encontrado."); return
                vid = safe_int(entry.get("ras_vei_id", 0))
                try:
                    ini   = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim   = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                    v_lim = float(e_vl.get())
                    oc_max = float(e_oc.get()) * 3600
                    jorn_max = float(e_jm.get()) * 3600
                except Exception:
                    write(res, "⚠ Parâmetros inválidos.", C["warn"]); return

                evs = _fetch_events(vid, ini, fim)
                if not evs:
                    write(res, "ℹ Nenhum evento.", C["text_mid"]); return

                m = _process_events(evs)
                infrações = []

                if m["excessos_80"] > 0 and v_lim <= 80:
                    infrações.append(
                        f"⚠ VELOCIDADE: {m['excessos_80']} ocorrências acima de {int(v_lim)} km/h"
                    )
                if m["t_ocio"] > oc_max:
                    infrações.append(
                        f"⚠ OCIOSIDADE: {_hms(m['t_ocio'])} (limite: {_hms(oc_max)})"
                    )
                if m["t_on"] > jorn_max:
                    infrações.append(
                        f"⚠ JORNADA: {_hms(m['t_on'])} ign. ON (limite: {_hms(jorn_max)})"
                    )

                status_geral = "✅ CONFORME" if not infrações else f"❌ NÃO CONFORME ({len(infrações)} infração(ões))"

                # Score de conformidade (0-100)
                score = 100
                score -= min(50, m["excessos_80"] * 5)
                score -= 20 if m["t_ocio"] > oc_max else 0
                score -= 30 if m["t_on"] > jorn_max else 0
                score = max(0, score)

                lines = [
                    "=" * 60,
                    f"  RELATÓRIO DE CONFORMIDADE — {entry.get('ras_vei_placa','—')}",
                    f"  {entry.get('ras_vei_veiculo','—')}  |  Motorista: {entry.get('ras_mot_nome','—')}",
                    f"  Período: {ini:%d/%m/%Y %H:%M} → {fim:%d/%m/%Y %H:%M}",
                    "",
                    f"  STATUS GERAL : {status_geral}",
                    f"  SCORE        : {score}/100",
                    "",
                    "  ─── Indicadores ────────────────────────────────────",
                    f"    Distância          : {m['km']:>10.2f} km",
                    f"    Vel. máxima        : {m['vmax']:>10} km/h  {'⚠' if m['vmax'] > v_lim else '✓'}",
                    f"    Vel. média         : {m['vmed']:>10.1f} km/h",
                    f"    Excessos vel.      : {m['excessos_80']:>10}  {'⚠' if m['excessos_80'] > 0 else '✓'}",
                    f"    Tempo jornada ON   : {_hms(m['t_on']):>13}  {'⚠' if m['t_on'] > jorn_max else '✓'}",
                    f"    Tempo ocioso       : {_hms(m['t_ocio']):>13}  {'⚠' if m['t_ocio'] > oc_max else '✓'}",
                    f"    Nº paradas         : {len(m['paradas']):>10}",
                    "",
                    "  ─── Limites Configurados ───────────────────────────",
                    f"    Velocidade máx.    : {int(v_lim)} km/h",
                    f"    Ociosidade máx.    : {_hms(oc_max)}",
                    f"    Jornada máx.       : {_hms(jorn_max)}",
                ]

                if infrações:
                    lines += ["", "  ─── ⚠ INFRAÇÕES DETECTADAS ────────────────────────"]
                    for inf in infrações: lines.append(f"    {inf}")
                else:
                    lines += ["", "  ─── ✅ NENHUMA INFRAÇÃO DETECTADA ─────────────────"]

                lines.append("=" * 60)
                write(res, "\n".join(lines))
            threading.Thread(target=task, daemon=True).start()

        btn(ph, "✅ VERIFICAR CONFORMIDADE", verificar, C["success"]).pack(pady=(6, 0))
        mk_export_btn(ph, res, is_text=True).pack(pady=(4, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # 7. RANKING POR MOTORISTA
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_ranking(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  📋 Ranking  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)

        lbl(c, "Custo/km R$:", 9, col=C["text_mid"]).pack(side="left")
        e_c = ent(c, w=7); e_c.pack(side="left", padx=4, ipady=4); e_c.insert(0, "0.62")
        lbl(c, "  Pen./excesso R$:", 9, col=C["text_mid"]).pack(side="left")
        e_p = ent(c, w=7); e_p.pack(side="left", padx=4, ipady=4); e_p.insert(0, "10.0")
        lbl(c, "  Vel. lim. km/h:", 9, col=C["text_mid"]).pack(side="left")
        e_vl = ent(c, w=6); e_vl.pack(side="left", padx=4, ipady=4); e_vl.insert(0, "80")
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")

        ft = FilterableTree(
            f,
            ("Pos.", "Motorista", "Veículos", "Vel.Máx", "Vel.Méd",
             "Excessos", "Paradas", "Custo Est.", "Penalidade", "Total", "Score"),
            (40, 160, 60, 80, 80, 70, 60, 100, 100, 100, 60),
            "CustoRk", C["success"], 14,
        )
        self._ft_custo_rank = ft

        def _tags():
            ft.tag_configure("caro",  background=_ac("al3"))
            ft.tag_configure("medio", background=_ac("al2"))
            ft.tag_configure("ok",    background=C["surface2"])
        _tags(); register_theme_listener(_tags)

        def ranking():
            try:
                cpm = float(e_c.get()); pen = float(e_p.get()); vlim = float(e_vl.get())
            except Exception:
                cpm = 0.62; pen = 10.0; vlim = 80.0
            lb.config(text="⏳...")
            def task():
                data = get_all_events(); mots = {}
                for ev in data:
                    nm = safe_str(ev.get("ras_mot_nome"), "Desconhecido")
                    vel = abs(safe_int(ev.get("ras_eve_velocidade", 0)))
                    pl  = safe_str(ev.get("ras_vei_placa"))
                    ign = safe_int(ev.get("ras_eve_ignicao", 0))
                    if nm not in mots:
                        mots[nm] = {"veics": set(), "vels": [], "ignitions": [], "paradas": 0}
                    mots[nm]["veics"].add(pl)
                    mots[nm]["vels"].append(vel)
                    mots[nm]["ignitions"].append(ign)

                rows = []
                for nm, d in mots.items():
                    vs = d["vels"]
                    vmx = max(vs) if vs else 0
                    vmd = sum(vs) / len(vs) if vs else 0
                    exc = sum(1 for v in vs if v > vlim)
                    custo_est = len(vs) * 0.1 * cpm
                    pen_t = exc * pen
                    total_c = custo_est + pen_t
                    # Score: começa em 100, perde por excesso e ociosidade
                    score = max(0, 100 - exc * 5 - (d["paradas"] * 2))
                    rows.append((
                        (
                            "—", nm, len(d["veics"]),
                            f"{vmx} km/h", f"{vmd:.1f} km/h",
                            exc, d["paradas"],
                            f"R$ {custo_est:.2f}", f"R$ {pen_t:.2f}",
                            f"R$ {total_c:.2f}", f"{score}",
                        ),
                        "caro" if total_c > 200 else ("medio" if total_c > 100 else "ok"),
                    ))

                rows.sort(key=lambda x: -float(x[0][9].replace("R$ ", "")))
                medals = ["🥇", "🥈", "🥉"]
                for i in range(len(rows)):
                    vals, tag = rows[i]
                    rows[i] = ((medals[i] if i < 3 else f"#{i+1}",) + vals[1:], tag)

                ft.load(rows)
                lb.config(text=f"{len(mots)} motoristas | {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "📋 CALCULAR", ranking, C["success"]).pack(side="left", padx=8)
        mk_export_btn(c, ft.tree).pack(side="left", padx=4)
        self.after(400, ranking)

    # ══════════════════════════════════════════════════════════════════════════
    # 8. PARÂMETROS
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_parametros(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ⚙ Parâmetros  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b, "CONFIGURAÇÃO GLOBAL DE PARÂMETROS", C["success"])
        lbl(b, "Estes valores são usados como padrão nos cálculos de custo e conformidade.", 9,
            col=C["text_mid"]).pack(anchor="w", pady=(0, 10))

        params = [
            ("preco_comb",   "Preço médio combustível (R$/L)",             "6.20"),
            ("consumo_km_l", "Consumo médio frota (km/L)",                  "10.0"),
            ("custo_h_mot",  "Custo horário motorista (R$/h)",              "25.0"),
            ("custo_h_ajud", "Custo horário ajudante (R$/h)",               "18.0"),
            ("custo_manut",  "Custo manutenção (R$/km)",                    "0.08"),
            ("vel_limite",   "Velocidade limite padrão (km/h)",             "80"),
            ("pen_excesso",  "Penalidade por excesso de vel. (R$/ocorr.)",  "10.0"),
            ("ocioso_l_h",   "Consumo em ocioso (L/h)",                     "0.5"),
        ]
        entries = {}
        for key, lab, default in params:
            r = tk.Frame(b, bg=C["bg"]); r.pack(fill="x", pady=3)
            lbl(r, f"{lab}:", 9, col=C["text_mid"], width=42).pack(side="left", anchor="w")
            e = ent(r, w=12); e.pack(side="left", ipady=4); e.insert(0, default)
            entries[key] = e

        def salvar():
            for key, e in entries.items():
                try:
                    self._params[key] = float(e.get())
                except Exception:
                    pass
            lbl(b, "✓ Parâmetros salvos na sessão.", 9, col=C["success"]).pack(anchor="w")

        btn(b, "💾 SALVAR PARÂMETROS NA SESSÃO", salvar, C["success"]).pack(pady=10)
        lbl(b,
            "\nℹ  Estes parâmetros são locais a esta sessão e propagados para todas as abas.\n"
            "   Configure conforme sua realidade operacional.",
            8, col=C["text_dim"]).pack(anchor="w", pady=4)