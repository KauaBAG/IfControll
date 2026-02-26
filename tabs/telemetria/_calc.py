"""
tabs/telemetria/_calc.py
Motor de cálculo de KPIs — totalmente baseado em events/interval.

Campos disponíveis por ponto:
  ras_eve_velocidade, ras_eve_ignicao, ras_eve_voltagem, ras_eve_data_gps,
  ras_eve_latitude, ras_eve_longitude, ras_eve_satelites,
  ras_eve_porc_bat_backup, ras_eve_voltagem_backup, ras_eve_gps_status,
  sensor_temperatura { digital_1, analog_1, analog_2 },
  ras_vei_placa, ras_vei_veiculo, ras_mot_nome

Todos os cálculos são determinísticos (sem IA) e testáveis isoladamente.
"""

from __future__ import annotations
import math
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any

from core.models import safe_int, safe_float, safe_str


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

_DT_FMTS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def _parse_dt(s: Any) -> datetime | None:
    if not s:
        return None
    s = str(s).strip()
    for fmt in _DT_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _fmt_dt(dt: datetime | None) -> str:
    return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else "—"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em km entre dois pontos GPS."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _vel(p: dict) -> int:
    v = safe_int(p.get("ras_eve_velocidade", 0))
    return max(0, v)   # ignora velocidades negativas (erro de sensor)


def _ign(p: dict) -> int:
    return safe_int(p.get("ras_eve_ignicao", 0))


def _lat(p: dict) -> float:
    raw = p.get("ras_eve_latitude", 0)
    v = safe_float(raw)
    # Fulltrack às vezes retorna lat como inteiro multiplicado por 1e7
    if v and abs(v) > 1000:
        v /= 1e7
    return v


def _lon(p: dict) -> float:
    raw = p.get("ras_eve_longitude", 0)
    v = safe_float(raw)
    if v and abs(v) > 1000:
        v /= 1e7
    return v


def _dt_pairs(points: list[dict]):
    """Gera pares (p_anterior, p_atual, delta_segundos) para análise temporal."""
    prev_dt = None
    prev_p  = None
    for p in points:
        dt = _parse_dt(p.get("ras_eve_data_gps"))
        if dt and prev_dt:
            delta = (dt - prev_dt).total_seconds()
            if 0 < delta < 3600:   # ignora gaps > 1h (provavelmente sem dados)
                yield prev_p, p, delta
        prev_dt = dt
        prev_p  = p


# ─────────────────────────────────────────────────────────────────────────────
# 1. Percurso
# ─────────────────────────────────────────────────────────────────────────────

def calc_percurso(points: list[dict]) -> dict:
    """
    KPIs de percurso:
      dist_km, duracao_min, vel_media, vel_max, n_pontos, inicio, fim
    Distância calculada por haversine entre pontos consecutivos com GPS válido.
    """
    if not points:
        return {}

    vels = [_vel(p) for p in points]
    vpos = [v for v in vels if v > 0]

    dist = 0.0
    prev_lat = prev_lon = None
    for p in points:
        lat, lon = _lat(p), _lon(p)
        if lat and lon and prev_lat and prev_lon:
            d = _haversine_km(prev_lat, prev_lon, lat, lon)
            if d < 2.0:          # filtra saltos absurdos de GPS
                dist += d
        if lat and lon:
            prev_lat, prev_lon = lat, lon

    dts = [_parse_dt(p.get("ras_eve_data_gps")) for p in points]
    dts = [d for d in dts if d]
    dur_min = (max(dts) - min(dts)).total_seconds() / 60 if len(dts) >= 2 else 0

    return {
        "dist_km":     round(dist, 2),
        "duracao_min": round(dur_min, 1),
        "vel_media":   round(sum(vpos) / len(vpos), 1) if vpos else 0,
        "vel_max":     max(vpos, default=0),
        "n_pontos":    len(points),
        "inicio":      _fmt_dt(min(dts)) if dts else "—",
        "fim":         _fmt_dt(max(dts)) if dts else "—",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Velocidade
# ─────────────────────────────────────────────────────────────────────────────

def calc_velocidade(points: list[dict], limite: int = 80) -> dict:
    """
    KPIs de velocidade:
      distribuicao, pct_acima_limite, picos (lista de eventos de excesso),
      aceleracoes_bruscas (variação > 30 km/h em 1 ponto)
    """
    if not points:
        return {
            "distribuicao": {}, "pct_acima_limite": 0,
            "picos": [], "aceleracoes_bruscas": 0,
        }

    dist = {"Parado (0)": 0, "Lento (1–40)": 0,
            "Normal (41–80)": 0, "Acima limite": 0, "Perigoso (>120)": 0}
    picos: list[dict] = []
    acels = 0
    prev_vel = 0

    for p in points:
        v = _vel(p)
        # distribuição
        if v == 0:
            dist["Parado (0)"] += 1
        elif v <= 40:
            dist["Lento (1–40)"] += 1
        elif v <= limite:
            dist["Normal (41–80)"] += 1
        elif v <= 120:
            dist["Acima limite"] += 1
        else:
            dist["Perigoso (>120)"] += 1

        # excesso
        if v > limite:
            picos.append({
                "data":  safe_str(p.get("ras_eve_data_gps")),
                "vel":   v,
                "placa": safe_str(p.get("ras_vei_placa")),
                "lat":   _lat(p),
                "lon":   _lon(p),
            })

        # aceleração brusca (delta > 30 km/h entre pontos consecutivos)
        if abs(v - prev_vel) > 30 and prev_vel > 0:
            acels += 1
        prev_vel = v

    total = sum(dist.values()) or 1
    n_acima = dist["Acima limite"] + dist["Perigoso (>120)"]
    picos.sort(key=lambda x: x["vel"], reverse=True)

    return {
        "distribuicao":       dist,
        "pct_acima_limite":   round(n_acima / total * 100, 1),
        "picos":              picos[:50],
        "aceleracoes_bruscas": acels,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Ociosidade (Idling)
# ─────────────────────────────────────────────────────────────────────────────

def calc_ociosidade(points: list[dict], consumo_l_h: float = 0.5) -> dict:
    """
    Períodos com ignição ON e velocidade = 0.
    Retorna: ocioso_min, ocioso_h, consumo_l, n_periodos, periodos[]
    """
    if not points:
        return {"ocioso_min": 0, "ocioso_h": 0, "consumo_l": 0,
                "n_periodos": 0, "periodos": []}

    periodos: list[dict] = []
    in_ocio = False
    ocio_start: datetime | None = None
    ocio_lat = ocio_lon = 0.0
    total_seg = 0

    for prev_p, p, delta in _dt_pairs(points):
        ign  = _ign(p)
        vel  = _vel(p)
        is_idle = (ign == 1 and vel == 0)

        if is_idle and not in_ocio:
            in_ocio   = True
            ocio_start = _parse_dt(p.get("ras_eve_data_gps"))
            ocio_lat   = _lat(p)
            ocio_lon   = _lon(p)
        elif not is_idle and in_ocio:
            in_ocio = False
            end_dt = _parse_dt(p.get("ras_eve_data_gps"))
            if ocio_start and end_dt:
                seg = (end_dt - ocio_start).total_seconds()
                if seg >= 60:   # ignora < 1 min
                    total_seg += seg
                    periodos.append({
                        "inicio": _fmt_dt(ocio_start),
                        "fim":    _fmt_dt(end_dt),
                        "min":    round(seg / 60, 1),
                        "local":  f"{ocio_lat:.4f}, {ocio_lon:.4f}",
                    })

    periodos.sort(key=lambda x: x["min"], reverse=True)
    ocioso_h = round(total_seg / 3600, 2)
    return {
        "ocioso_min": round(total_seg / 60, 1),
        "ocioso_h":   ocioso_h,
        "consumo_l":  round(ocioso_h * consumo_l_h, 2),
        "n_periodos": len(periodos),
        "periodos":   periodos,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Motor e Bateria
# ─────────────────────────────────────────────────────────────────────────────

def calc_motor(points: list[dict]) -> dict:
    """
    Tempo de motor ligado/desligado, ciclos de ignição, voltagem e bateria.
    """
    if not points:
        return {
            "ligado_h": 0, "desligado_h": 0, "ciclos_ignicao": 0,
            "volt_media": 0, "volt_min": 0, "volt_max": 0,
            "bat_media": 0, "historico_ign": [],
        }

    seg_on = seg_off = 0
    ciclos = 0
    prev_ign = None
    historico: list[dict] = []
    volts: list[float] = []
    bats:  list[int]   = []

    for prev_p, p, delta in _dt_pairs(points):
        ign = _ign(p)

        # acumula tempo
        if ign == 1:
            seg_on  += delta
        else:
            seg_off += delta

        # detecta troca de estado → ciclo
        if prev_ign is not None and ign != prev_ign:
            ev = "🟢 LIGOU" if ign == 1 else "⚫ DESLIGOU"
            ciclos += 1 if ign == 1 else 0
            historico.append({
                "data":   safe_str(p.get("ras_eve_data_gps")),
                "evento": ev,
            })
        prev_ign = ign

        v = safe_float(p.get("ras_eve_voltagem", 0))
        if 5 < v < 30:
            volts.append(v)

        b = safe_int(p.get("ras_eve_porc_bat_backup", -1))
        if 0 <= b <= 100:
            bats.append(b)

    return {
        "ligado_h":       round(seg_on  / 3600, 2),
        "desligado_h":    round(seg_off / 3600, 2),
        "ciclos_ignicao": ciclos,
        "volt_media":     round(sum(volts) / len(volts), 2) if volts else 0,
        "volt_min":       round(min(volts), 2) if volts else 0,
        "volt_max":       round(max(volts), 2) if volts else 0,
        "bat_media":      round(sum(bats)  / len(bats),  1) if bats  else 0,
        "historico_ign":  historico[-100:],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Temperatura
# ─────────────────────────────────────────────────────────────────────────────

def calc_temperatura(points: list[dict]) -> dict:
    """
    Analisa sensor_temperatura { digital_1, analog_1, analog_2 }.
    Retorna estatísticas por canal + alertas de temperatura acima de limite.
    """
    canais: dict[str, list[float]] = {
        "digital_1": [], "analog_1": [], "analog_2": [],
    }
    LIMITE_MOTOR_C = 100.0   # °C — alerta se ultrapassar

    for p in points:
        st = p.get("sensor_temperatura") or {}
        if isinstance(st, dict):
            for canal in canais:
                v = safe_float(st.get(canal))
                if v is not None and -50 < v < 200:
                    canais[canal].append(v)

    result: dict[str, Any] = {"disponivel": False}
    alertas_temp: list[str] = []

    for canal, vals in canais.items():
        if vals:
            result["disponivel"] = True
            mx = round(max(vals), 1)
            result[canal] = {
                "min":    round(min(vals), 1),
                "max":    mx,
                "media":  round(sum(vals) / len(vals), 1),
                "n":      len(vals),
            }
            if mx > LIMITE_MOTOR_C:
                alertas_temp.append(
                    f"⚠ {canal}: temperatura máxima {mx}°C acima do limite ({LIMITE_MOTOR_C}°C)"
                )

    result["alertas"] = alertas_temp
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 6. Consumo de Combustível
# ─────────────────────────────────────────────────────────────────────────────

def calc_consumo(
    perc: dict,
    ocio: dict,
    km_l:      float = 10.0,
    ocio_l_h:  float = 0.5,
    preco_l:   float = 5.80,
    consumo_real_km_l: float = 0.0,   # ras_vei_consumo se disponível
) -> dict:
    """
    Estimativa de consumo de combustível:
      - Em movimento: dist_km / km_l
      - Em ócio:      horas_ociosas * ocio_l_h
    Se consumo_real_km_l > 0, usa o cadastrado no veículo.
    """
    km_l_efetivo = consumo_real_km_l if consumo_real_km_l > 0 else km_l
    dist_km      = perc.get("dist_km", 0) or 0
    ocioso_h     = ocio.get("ocioso_h", 0) or 0

    l_movimento  = round(dist_km / km_l_efetivo, 2) if km_l_efetivo else 0
    l_ocio       = round(ocioso_h * ocio_l_h, 2)
    l_total      = round(l_movimento + l_ocio, 2)
    custo        = round(l_total * preco_l, 2)
    custo_km     = round(custo / dist_km, 4) if dist_km > 0 else 0

    return {
        "dist_km":     dist_km,
        "l_movimento": l_movimento,
        "l_ocio":      l_ocio,
        "l_total":     l_total,
        "custo_brl":   custo,
        "custo_km":    custo_km,
        "km_l_usado":  km_l_efetivo,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. Score de Risco (Driver Score 0–100)
# ─────────────────────────────────────────────────────────────────────────────

def calc_risco(
    perc: dict,
    vel:  dict,
    ocio: dict,
    mot:  dict,
    points: list[dict],
    limite_vel: int = 80,
) -> dict:
    """
    Score de risco composto (0 = perfeito, 100 = crítico).

    Componentes e pesos:
      - % tempo acima do limite de velocidade  → até 30 pts
      - Acelerações bruscas (delta vel)         → até 15 pts
      - Horas de ociosidade excessiva           → até 15 pts
      - Voltagem mínima crítica                 → até 15 pts
      - Ciclos de ignição excessivos            → até 10 pts
      - GPS perdido (% pontos sem sinal)        → até 10 pts
      - Temperatura alta                        → até 5 pts
    """
    score = 0
    detalhes: list[str] = []

    # 1. Excesso de velocidade
    pct_vel = vel.get("pct_acima_limite", 0)
    p_vel   = min(30, round(pct_vel * 1.5))
    if p_vel:
        score += p_vel
        detalhes.append(f"🚨 Velocidade: {pct_vel}% do tempo acima de {limite_vel} km/h → +{p_vel} pts")

    # 2. Acelerações bruscas
    acels = vel.get("aceleracoes_bruscas", 0)
    p_acel = min(15, acels // 3)
    if p_acel:
        score += p_acel
        detalhes.append(f"⚡ Acelerações/freadas bruscas: {acels} eventos → +{p_acel} pts")

    # 3. Ociosidade excessiva
    ocio_h = ocio.get("ocioso_h", 0)
    if ocio_h > 0.5:
        p_ocio = min(15, round((ocio_h - 0.5) * 5))
        score += p_ocio
        detalhes.append(f"😴 Ociosidade: {ocio_h}h de motor ligado parado → +{p_ocio} pts")

    # 4. Voltagem crítica
    volt_min = mot.get("volt_min", 12)
    if 0 < volt_min < 11.5:
        p_volt = 15
        score += p_volt
        detalhes.append(f"🔋 Voltagem crítica: {volt_min}V → +{p_volt} pts")
    elif 0 < volt_min < 12.0:
        score += 5
        detalhes.append(f"🔋 Voltagem baixa: {volt_min}V → +5 pts")

    # 5. Ciclos de ignição
    ciclos = mot.get("ciclos_ignicao", 0)
    if ciclos > 30:
        p_ciclos = min(10, (ciclos - 30) // 5)
        score += p_ciclos
        detalhes.append(f"🔑 {ciclos} ciclos de ignição → +{p_ciclos} pts")

    # 6. GPS perdido
    n_total = len(points)
    n_sem_gps = sum(1 for p in points if not safe_int(p.get("ras_eve_gps_status", 1)))
    pct_gps = round(n_sem_gps / n_total * 100, 1) if n_total else 0
    if pct_gps > 20:
        p_gps = min(10, round(pct_gps / 10))
        score += p_gps
        detalhes.append(f"📡 GPS perdido em {pct_gps}% do tempo → +{p_gps} pts")

    # 7. Temperatura
    temp = calc_temperatura(points)
    if temp.get("alertas"):
        score += 5
        detalhes.append(f"🌡 Temperatura anormal detectada → +5 pts")

    score = min(100, max(0, score))

    if score < 20:
        nivel = "✅ BAIXO"
    elif score < 50:
        nivel = "⚠️  MÉDIO"
    elif score < 75:
        nivel = "🔴 ALTO"
    else:
        nivel = "💀 CRÍTICO"

    if not detalhes:
        detalhes.append("✅ Nenhuma penalidade detectada no período.")

    return {"score": score, "nivel": nivel, "detalhes": detalhes}


# ─────────────────────────────────────────────────────────────────────────────
# 8. Cercas
# ─────────────────────────────────────────────────────────────────────────────

def calc_cercas(fence_events: list[dict]) -> dict:
    """
    Consolida eventos de cerca por nome de cerca.
    Retorna total_visitas e lista de cercas com estatísticas.
    """
    if not fence_events:
        return {"total_visitas": 0, "cercas": []}

    grupos: dict[str, list[dict]] = defaultdict(list)
    for ev in fence_events:
        nome = ev.get("ras_cer_observacao") or "Sem nome"
        grupos[nome].append(ev)

    cercas: list[dict] = []
    for nome, evs in grupos.items():
        entradas = [e for e in evs if e.get("data_entrada") and e["data_entrada"] != "-"]
        saidas   = [e for e in evs if e.get("data_saida")   and e["data_saida"]   != "-"]

        # soma permanência
        total_perm_seg = 0
        for e in evs:
            tp = e.get("tempo_permanencia", "")
            if tp and tp != "-":
                try:
                    parts = str(tp).split(":")
                    if len(parts) == 3:
                        total_perm_seg += int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
                except Exception:
                    pass

        h  = total_perm_seg // 3600
        m  = (total_perm_seg % 3600) // 60
        s  = total_perm_seg % 60

        cercas.append({
            "nome":             nome,
            "visitas":          len(evs),
            "ultima_entrada":   entradas[-1]["data_entrada"] if entradas else "—",
            "ultima_saida":     saidas[-1]["data_saida"]     if saidas   else "—",
            "permanencia_total": f"{h:02d}:{m:02d}:{s:02d}",
        })

    cercas.sort(key=lambda x: x["visitas"], reverse=True)
    return {
        "total_visitas": sum(c["visitas"] for c in cercas),
        "cercas":        cercas,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. Heatmap por hora do dia
# ─────────────────────────────────────────────────────────────────────────────

def calc_heatmap_hora(points: list[dict]) -> dict[int, int]:
    """Conta pontos por hora do dia (0–23)."""
    counts = {h: 0 for h in range(24)}
    for p in points:
        dt = _parse_dt(p.get("ras_eve_data_gps"))
        if dt:
            counts[dt.hour] += 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# 10. Detecção de anomalias
# ─────────────────────────────────────────────────────────────────────────────

def calc_anomalias(points: list[dict]) -> list[dict]:
    """
    Detecta padrões suspeitos nos dados:
      - GPS parado por muito tempo com ignição ON
      - Variação de voltagem muito brusca
      - Velocidade impossível (> 250 km/h)
    Retorna lista de anomalias { tipo, descricao, data, lat, lon }
    """
    anomalias: list[dict] = []
    prev_lat = prev_lon = None
    parado_seg = 0.0

    for prev_p, p, delta in _dt_pairs(points):
        v   = _vel(p)
        ign = _ign(p)
        lat = _lat(p)
        lon = _lon(p)
        dt  = safe_str(p.get("ras_eve_data_gps"))

        # Velocidade impossível
        if v > 250:
            anomalias.append({
                "tipo": "VELOCIDADE_IMPOSSIVEL",
                "descricao": f"Velocidade {v} km/h registrada (improvável)",
                "data": dt, "lat": lat, "lon": lon,
            })

        # GPS parado c/ ignição ON por > 2h
        if ign == 1 and lat == prev_lat and lon == prev_lon:
            parado_seg += delta
            if parado_seg > 7200:
                anomalias.append({
                    "tipo": "GPS_PARADO_IGNICAO_ON",
                    "descricao": f"GPS sem movimento há {round(parado_seg/3600,1)}h com ignição ligada",
                    "data": dt, "lat": lat, "lon": lon,
                })
                parado_seg = 0   # reset para não gerar repetidamente
        else:
            parado_seg = 0

        # Variação brusca de voltagem
        vv   = safe_float(p.get("ras_eve_voltagem", 0)) or 0
        vv_p = safe_float(prev_p.get("ras_eve_voltagem", 0)) or 0
        if vv_p and abs(vv - vv_p) > 3:
            anomalias.append({
                "tipo": "VARIACAO_VOLTAGEM",
                "descricao": f"Voltagem variou {vv_p:.1f}V → {vv:.1f}V",
                "data": dt, "lat": lat, "lon": lon,
            })

        prev_lat, prev_lon = lat, lon

    return anomalias[:100]   # limita a 100


# ─────────────────────────────────────────────────────────────────────────────
# 11. Análise de Jornada (WorkingDay cross)
# ─────────────────────────────────────────────────────────────────────────────

def calc_jornada(workingday_data: list[dict]) -> dict:
    """
    Consolida dados de jornada retornados por /workingday/interval.
    Retorna métricas por motorista.
    """
    if not workingday_data:
        return {"motoristas": [], "total_horas": 0}

    by_driver: dict[str, dict] = {}
    for r in workingday_data:
        nome = r.get("ras_mot_nome") or "Não identificado"
        if nome not in by_driver:
            by_driver[nome] = {"nome": nome, "registros": [], "horas": 0.0}
        by_driver[nome]["registros"].append(r)

    for drv in by_driver.values():
        # tenta somar horas se o endpoint retornar campos de tempo
        for r in drv["registros"]:
            h = safe_float(r.get("horas_trabalhadas") or r.get("total_horas", 0))
            drv["horas"] += h

    motoristas = sorted(by_driver.values(), key=lambda x: x["horas"], reverse=True)
    return {
        "motoristas":   motoristas,
        "total_horas":  round(sum(m["horas"] for m in motoristas), 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 12. Ranking de Motoristas
# ─────────────────────────────────────────────────────────────────────────────

def calc_ranking_motoristas(
    veiculos_data: list[dict],   # lista de (vei_id, points, limite_vel)
) -> list[dict]:
    """
    Calcula score por motorista/veículo e retorna ranking.
    Cada item de veiculos_data deve ser dict com keys: placa, veiculo, points, limite_vel
    """
    ranking: list[dict] = []
    for item in veiculos_data:
        pts       = item.get("points", [])
        lim       = item.get("limite_vel", 80)
        perc      = calc_percurso(pts)
        vel       = calc_velocidade(pts, lim)
        ocio      = calc_ociosidade(pts)
        mot       = calc_motor(pts)
        risk      = calc_risco(perc, vel, ocio, mot, pts, lim)
        ranking.append({
            "placa":    item.get("placa", "—"),
            "veiculo":  item.get("veiculo", "—"),
            "score":    risk["score"],
            "nivel":    risk["nivel"],
            "dist_km":  perc.get("dist_km", 0),
            "ocio_h":   ocio.get("ocioso_h", 0),
            "vel_max":  perc.get("vel_max", 0),
        })

    ranking.sort(key=lambda x: x["score"])   # menor score = melhor
    return ranking


# ─────────────────────────────────────────────────────────────────────────────
# 13. Alertas — análise por tipo e SLA
# ─────────────────────────────────────────────────────────────────────────────

def calc_alertas(alerts: list[dict]) -> dict:
    """
    Analisa alertas: por tipo, SLA de fechamento, abertos vs fechados.
    """
    if not alerts:
        return {"total": 0, "abertos": 0, "fechados": 0, "por_tipo": {}, "sla_medio_h": 0}

    by_tipo: dict[str, int] = defaultdict(int)
    sla_list: list[float] = []
    abertos = fechados = 0

    for a in alerts:
        tipo = a.get("ras_eal_descricao", "Desconhecido")
        by_tipo[tipo] += 1
        baixado = safe_int(a.get("ras_eal_baixado", 0))
        if baixado:
            fechados += 1
        else:
            abertos += 1

    return {
        "total":       len(alerts),
        "abertos":     abertos,
        "fechados":    fechados,
        "por_tipo":    dict(sorted(by_tipo.items(), key=lambda x: x[1], reverse=True)),
        "sla_medio_h": round(sum(sla_list) / len(sla_list), 1) if sla_list else 0,
    }