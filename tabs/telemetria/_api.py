"""
tabs/telemetria/_api.py
Cliente HTTP para os endpoints de telemetria e veículos.

CORREÇÃO /run:
  core.api._req() appenda "/run" em toda URL, quebrando /events/interval.
  _api_get_direct() chama requests.get diretamente, sem o /run,
  aplicando AUTH e _fix_dates() manualmente.

  Imports do core ficam DENTRO das funções para evitar circular import
  (core.api importa core.__init__ que importa tabs que importa core.api).
"""

from datetime import datetime
import requests


# ── Conversão de data UI → Unix timestamp ────────────────────────────────────

def to_ts(dt_str: str) -> int:
    """'dd/mm/aaaa HH:MM' → Unix timestamp (horário local Brasil)."""
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return int(datetime.strptime(dt_str.strip(), fmt).timestamp())
        except ValueError:
            continue
    return int(datetime.now().timestamp())


# ── Requisição direta (sem /run) ──────────────────────────────────────────────

def _api_get_direct(path: str, params: dict | None = None, timeout: int = 30) -> dict:
    """
    GET sem o /run que core.api._req() appenda automaticamente.
    Importa BASE_URL, AUTH e _fix_dates em tempo de execução para
    evitar circular import no boot.
    """
    from core.credencials import BASE_URL, AUTH
    from core.api import _fix_dates

    url = f"{BASE_URL}{path}"
    p   = {**AUTH, **(params or {})}
    try:
        r    = requests.get(url, params=p, timeout=timeout)
        print(f"\n[DIRECT] GET {url}")
        print(f"  HTTP : {r.status_code}")
        print(f"  body : {r.text[:500]}")
        data = r.json()
        _fix_dates(data)
        return data
    except Exception as e:
        print(f"[DIRECT] ERRO: {e}")
        return {"status": False, "error": str(e)}


# ── Helper de extração ────────────────────────────────────────────────────────

def _extract(resp) -> list[dict]:
    from core.api import extract_list
    if isinstance(resp, dict):
        return extract_list(resp.get("data", []))
    return extract_list(resp)


# ── Endpoints SEM /run — usam _api_get_direct ─────────────────────────────────

def get_events_interval(vei_id: int | str, begin_ts: int, end_ts: int) -> list[dict]:
    """GET /events/interval/id/:id/begin/:timestamp/end/:timestamp"""
    path = f"/events/interval/id/{vei_id}/begin/{begin_ts}/end/{end_ts}"
    return _extract(_api_get_direct(path))


def get_telemetry(vei_id: int | str, begin_ts: int, end_ts: int) -> list[dict]:
    """GET /events/telemetry/id/:id/begin/:begin/end/:end"""
    path = f"/events/telemetry/id/{vei_id}/begin/{begin_ts}/end/{end_ts}"
    return _extract(_api_get_direct(path))


def get_workingday_interval(begin_ts: int, end_ts: int,
                             driver_id: int | str | None = None) -> list[dict]:
    """GET /workingday/interval/initial/:initial/final/:final"""
    path   = f"/workingday/interval/initial/{begin_ts}/final/{end_ts}"
    params = {"driver": driver_id} if driver_id else None
    return _extract(_api_get_direct(path, params=params))


# ── Endpoints COM /run — usam api_get do core normalmente ────────────────────

def get_vehicle_single(vei_id: int | str) -> dict:
    """GET /vehicles/single/id/:id"""
    from core.api import api_get, extract_list
    resp  = api_get(f"/vehicles/single/id/{vei_id}")
    items = extract_list(resp.get("data", [])) if isinstance(resp, dict) else []
    return items[0] if items else {}


def get_fence_vehicle(vei_id: int | str, begin_ts: int, end_ts: int) -> list[dict]:
    """GET /fence/vehicle/id/:id/initial/:initial/final/:final"""
    from core.api import api_get
    path = f"/fence/vehicle/id/{vei_id}/initial/{begin_ts}/final/{end_ts}"
    return _extract(api_get(path))


def get_alerts_period(begin_ts: int, end_ts: int) -> list[dict]:
    """GET /alerts/period/initial/:initial/final/:final"""
    from core.api import api_get
    path = f"/alerts/period/initial/{begin_ts}/final/{end_ts}"
    return _extract(api_get(path))


# ── Constantes ────────────────────────────────────────────────────────────────

try:
    from core.config import DEFAULT_SPEED_LIMIT as DEFAULT_VEL_LIMITE
    from core.config import IDLE_FUEL_L_PER_H   as DEFAULT_CONSUMO_OCIO
except ImportError:
    DEFAULT_VEL_LIMITE   = 80
    DEFAULT_CONSUMO_OCIO = 0.5