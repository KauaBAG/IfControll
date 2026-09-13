"""
tabs/telemetria/_api.py
"""

from datetime import datetime
import requests


def to_ts(dt_str: str) -> int:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return int(datetime.strptime(dt_str.strip(), fmt).timestamp())
        except ValueError:
            continue
    return int(datetime.now().timestamp())


def _api_get_direct(path: str, params: dict | None = None, timeout: int = 30) -> dict:
    from core.credencials import BASE_URL, AUTH
    from core.api import _fix_dates
    url = f"{BASE_URL}{path}"
    p   = {**AUTH, **(params or {})}
    try:
        r    = requests.get(url, params=p, timeout=timeout)
        data = r.json()
        _fix_dates(data)
        return data
    except Exception as e:
        return {"status": False, "error": str(e)}


def _extract(resp) -> list[dict]:
    from core.api import extract_list
    if isinstance(resp, dict):
        # /telemetry/vehicle retorna data.[].log[] — desaninha
        raw = resp.get("data", [])
        if isinstance(raw, list):
            # Verifica se é lista de objetos com "log" (formato telemetry/vehicle)
            if raw and isinstance(raw[0], dict) and "log" in raw[0]:
                points = []
                for asset in raw:
                    meta = {k: v for k, v in asset.items() if k != "log"}
                    for entry in (asset.get("log") or []):
                        points.append({**meta, **entry})
                return points
        return extract_list(raw)
    return extract_list(resp)


def _parse_tel_float(val) -> float:
    """Converte '422.880,00' ou '0,00' para float."""
    if val is None or val == "-":
        return 0.0
    try:
        return float(str(val).replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def normalize_telemetry_point(p: dict) -> dict:
    """
    Normaliza um ponto do /telemetry/vehicle para o mesmo formato
    usado pelo resto do sistema, adicionando aliases ras_* para
    compatibilidade com as funções de cálculo existentes.
    """
    lat, lon = 0.0, 0.0
    loc = p.get("lst_localizacao")
    if isinstance(loc, list) and len(loc) >= 2:
        try:
            lat, lon = float(loc[0]), float(loc[1])
        except (ValueError, TypeError):
            pass

    return {
        **p,
        # Aliases para compatibilidade com ras_eve_* usados em _calc.py
        "ras_eve_data_gps":      p.get("dt_gps", ""),
        "ras_eve_ignicao":       p.get("filg_ignicao", 0),
        "ras_eve_velocidade":    int(_parse_tel_float(p.get("velocidade", 0))),
        "ras_eve_latitude":      lat,
        "ras_eve_longitude":     lon,
        # Campos nativos do telemetry — usados pelas novas sub-abas
        "tel_rpm":               p.get("rpm", 0),
        "tel_torque":            p.get("engine_torque", 0),
        "tel_odometro":          _parse_tel_float(p.get("odometro", 0)),
        "tel_fuel_consumption":  p.get("fuel_consumption", 0),   # acumulado
        "tel_nivel_combustivel": p.get("nivel_combustivel", 0),  # %
        "tel_temperatura_motor": p.get("temperatura_motor", 0),  # °C
        "tel_posicao_borboleta": p.get("posicao_borboleta", 0),  # %
        "tel_motorista":         p.get("desc_motorista", "-"),
        # Campos opcionais (vêm como "-" quando indisponível)
        "tel_horimetro":         p.get("horimetro", "-"),
        "tel_oil_pressure":      p.get("oil_pressure", "-"),
        "tel_fuel_flow":         p.get("fuel_flow", "-"),
        "tel_turbo_pressure":    p.get("turbo_pressure", "-"),
        "tel_engine_load":       p.get("engine_load", "-"),
        "tel_fuel_economy":      p.get("current_fuel_economy", "-"),
        "tel_fuel_level_liters": p.get("fuel_level_liters", "-"),
        "tel_battery_load":      p.get("battery_load", "-"),
    }


# ── Endpoints SEM /run ────────────────────────────────────────────────────────

def get_events_interval(vei_id: int | str, begin_ts: int, end_ts: int) -> list[dict]:
    """GPS, velocidade, ignição, voltagem."""
    path = f"/events/interval/id/{vei_id}/begin/{begin_ts}/end/{end_ts}"
    return _extract(_api_get_direct(path))


def get_telemetry_vehicle(vei_id: int | str, begin_ts: int, end_ts: int) -> list[dict]:
    """
    RPM, odômetro, consumo, torque, temperatura, borboleta.
    Retorna pontos já normalizados com aliases ras_eve_* e tel_*.
    """
    path = f"/telemetry/vehicle/id/{vei_id}/begin/{begin_ts}/end/{end_ts}"
    raw  = _extract(_api_get_direct(path))
    return [normalize_telemetry_point(p) for p in raw]


def get_telemetry(vei_id: int | str, begin_ts: int, end_ts: int) -> list[dict]:
    path = f"/telemetry/vehicle/id/{vei_id}/begin/{begin_ts}/end/{end_ts}"
    return _extract(_api_get_direct(path))


def get_workingday_interval(begin_ts: int, end_ts: int,
                             driver_id: int | str | None = None) -> list[dict]:
    path   = f"/workingday/interval/initial/{begin_ts}/final/{end_ts}"
    params = {"driver": driver_id} if driver_id else None
    return _extract(_api_get_direct(path, params=params))


def merge_telemetry_into_points(points: list[dict],
                                 telemetry: list[dict]) -> list[dict]:
    """
    Enriquece pontos GPS com campos tel_* do /telemetry/vehicle.
    Join por timestamp mais próximo (tolerância 90s).
    Se não houver pontos GPS (apenas telemetry), retorna telemetry direto.
    """
    if not points:
        return telemetry
    if not telemetry:
        return points

    import bisect
    from datetime import datetime as _dt

    def _ts(raw):
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return int(_dt.strptime(str(raw).strip(), fmt).timestamp())
            except ValueError:
                continue
        return None

    tel_ts_list = []
    for t in telemetry:
        ts = _ts(str(t.get("ras_eve_data_gps", "") or t.get("dt_gps", "")))
        if ts:
            tel_ts_list.append((ts, t))
    tel_ts_list.sort(key=lambda x: x[0])
    if not tel_ts_list:
        return points

    ts_arr = [x[0] for x in tel_ts_list]
    TOLERANCE = 90

    enriched = []
    for p in points:
        ts_p = _ts(str(p.get("ras_eve_data_gps", "")))
        if ts_p is not None:
            idx  = bisect.bisect_left(ts_arr, ts_p)
            best = None
            best_diff = TOLERANCE + 1
            for ci in [idx - 1, idx]:
                if 0 <= ci < len(tel_ts_list):
                    diff = abs(tel_ts_list[ci][0] - ts_p)
                    if diff < best_diff:
                        best_diff = diff
                        best = tel_ts_list[ci][1]
            if best and best_diff <= TOLERANCE:
                merged = {**p}
                for k, v in best.items():
                    if k.startswith("tel_") and k not in merged:
                        merged[k] = v
                enriched.append(merged)
                continue
        enriched.append(p)
    return enriched


# ── Endpoints COM /run ────────────────────────────────────────────────────────

def get_vehicle_single(vei_id: int | str) -> dict:
    from core.api import api_get, extract_list
    resp  = api_get(f"/vehicles/single/id/{vei_id}")
    items = extract_list(resp.get("data", [])) if isinstance(resp, dict) else []
    return items[0] if items else {}


def get_fence_vehicle(vei_id: int | str, begin_ts: int, end_ts: int) -> list[dict]:
    from core.api import api_get
    return _extract(api_get(f"/fence/vehicle/id/{vei_id}/initial/{begin_ts}/final/{end_ts}"))


def get_alerts_period(begin_ts: int, end_ts: int) -> list[dict]:
    from core.api import api_get
    return _extract(api_get(f"/alerts/period/initial/{begin_ts}/final/{end_ts}"))


try:
    from core.config import DEFAULT_SPEED_LIMIT as DEFAULT_VEL_LIMITE
    from core.config import IDLE_FUEL_L_PER_H   as DEFAULT_CONSUMO_OCIO
except ImportError:
    DEFAULT_VEL_LIMITE   = 80
    DEFAULT_CONSUMO_OCIO = 0.5