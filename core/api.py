"""
core/api.py
Camada de acesso à API Fulltrack2.
Todos os endpoints, helpers de extração e buscas ficam aqui.
"""

import re
import requests
from .credencials import BASE_URL, AUTH
from .models import safe_int, safe_str


# ── Requisição base ───────────────────────────────────────────────────────────

def _req(method: str, path: str, params=None, body=None, timeout: int = 30):
    url = f"{BASE_URL}{path}/run"
    p   = {**AUTH, **(params or {})}
    try:
        if method == "GET":
            r = requests.get(url, params=p, timeout=timeout)
        elif method == "POST":
            r = requests.post(url, json={**(body or {}), **AUTH}, params=AUTH, timeout=timeout)
        elif method == "PUT":
            r = requests.put(url, json={**(body or {}), **AUTH}, params=AUTH, timeout=timeout)
        elif method == "DEL":
            r = requests.delete(url, params=p, timeout=timeout)
        else:
            return {}, 0
        return r.json(), r.status_code
    except Exception as e:
        return {"status": False, "error": str(e)}, 0


def api_get(path: str, params=None):
    d, _ = _req("GET", path, params=params)
    return d


def api_post(path: str, body: dict):
    return _req("POST", path, body=body)


def api_put(path: str, body: dict):
    return _req("PUT", path, body=body)


def api_del(path: str):
    return _req("DEL", path)


# ── Extração de listas ────────────────────────────────────────────────────────

def extract_list(d) -> list:
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        if "data" in d:
            v = d["data"]
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                for k in ("eventos", "data"):
                    if k in v and isinstance(v[k], list):
                        return v[k]
        for v in d.values():
            if isinstance(v, list) and v:
                return v
    return []


# ── Endpoints de listagem ─────────────────────────────────────────────────────

def get_all_events() -> list:
    return extract_list(api_get("/events/all").get("data", []))


def get_vehicles_all() -> list:
    return extract_list(api_get("/vehicles/all").get("data", []))


def get_alerts_all() -> list:
    return extract_list(api_get("/alerts/all").get("data", []))


def get_clients_all() -> list:
    return extract_list(api_get("/clients/all").get("data", []))


def get_trackers_all() -> list:
    return extract_list(api_get("/trackers/all").get("data", []))


def get_passengers_all() -> list:
    return extract_list(api_get("/passenger/all").get("data", []))


def get_alert_types() -> list:
    return extract_list(api_get("/alerts/types").get("data", []))


def get_fences_all() -> list:
    resp = api_get("/fence/all")
    msg  = resp.get("message", [])
    if isinstance(msg, list) and msg and isinstance(msg[0], list):
        return msg[0]
    return extract_list(resp)


# ── Busca de veículo por placa / nome ─────────────────────────────────────────

def find_vehicle(q: str) -> dict | None:
    """Busca um evento pelo campo placa ou nome do veículo (case-insensitive)."""
    nq = re.sub(r"[^A-Z0-9]", "", q.upper())
    for ev in get_all_events():
        if re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_vei_placa", "")).upper()) == nq:
            return ev
        if nq in re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_vei_veiculo", "")).upper()):
            return ev
    return None