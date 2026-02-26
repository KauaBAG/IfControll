"""
core/api.py
Camada de acesso à API Fulltrack2.
Todos os endpoints, helpers de extração e buscas ficam aqui.

v3 — Correção de fuso horário:
  Todos os campos de data/hora retornados pela API Fulltrack são
  adiantados em +3h em relação ao horário de Brasília. A função
  _fix_dates() percorre recursivamente qualquer resposta (dict/list)
  e subtrai 3 horas de cada string que contenha uma data+hora válida,
  independentemente do nome do campo ou nível de aninhamento.

  BUG CORRIGIDO: a versão anterior cortava a string pelo tamanho do
  formato strptime (ex.: len('%d/%m/%Y %H:%M:%S') == 17) em vez do
  tamanho real da data (ex.: len('23/02/2026 20:42:21') == 19),
  fazendo strptime falhar silenciosamente e não corrigir nada.
  Correção: strptime recebe a string inteira, sem truncamento.
"""

import re
from datetime import datetime, timedelta

import requests

from .credencials import BASE_URL, AUTH
from .models import safe_int, safe_str


# ─────────────────────────────────────────────────────────────────────────────
# CORREÇÃO DE FUSO HORÁRIO  (−3 horas em todos os campos de data+hora)
# ─────────────────────────────────────────────────────────────────────────────

# Formatos reconhecidos como data+hora (mais específico primeiro)
_DT_FORMATS = [
    ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"),   # 23/02/2026 20:42:21
    ("%d/%m/%Y %H:%M",    "%d/%m/%Y %H:%M"),       # 23/02/2026 20:42
    ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"),   # 2026-02-23 20:42:21
    ("%Y-%m-%d %H:%M",    "%Y-%m-%d %H:%M"),       # 2026-02-23 20:42
]

# Datas puras (sem hora) — não devem ter horas subtraídas
_DATE_ONLY_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}$"      # yyyy-mm-dd
    r"|^\d{2}/\d{2}/\d{4}$"     # dd/mm/yyyy
)

_DELTA = timedelta(hours=3)


def _try_shift(value: str) -> str:
    """
    Tenta interpretar `value` como data+hora e subtrair 3 horas.
    Devolve o valor original se não reconhecer o formato ou se for
    apenas uma data sem componente horário.
    """
    v = value.strip()
    if not v:
        return value

    # Datas puras: devolve intacto
    if _DATE_ONLY_RE.match(v):
        return value

    # Tenta cada formato — strptime recebe a string COMPLETA (sem cortar)
    for fmt_in, fmt_out in _DT_FORMATS:
        try:
            dt = datetime.strptime(v, fmt_in)
            return (dt - _DELTA).strftime(fmt_out)
        except ValueError:
            continue

    return value


def _fix_dates(obj):
    """
    Percorre recursivamente dicts e listas e aplica _try_shift()
    em toda string não-vazia encontrada, em qualquer nível de
    aninhamento e em qualquer campo, sem necessidade de saber o
    nome do campo de antemão.
    Modifica in-place e retorna o objeto para uso em expressões.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                obj[k] = _try_shift(v)
            else:
                _fix_dates(v)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str):
                obj[i] = _try_shift(item)
            else:
                _fix_dates(item)
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# REQUISIÇÃO BASE
# ─────────────────────────────────────────────────────────────────────────────

def _req(method: str, path: str, params=None, body=None, timeout: int = 30):
    url = f"{BASE_URL}{path}/run"
    p   = {**AUTH, **(params or {})}
    try:
        if method == "GET":
            r = requests.get(url, params=p, timeout=timeout)
        elif method == "POST":
            r = requests.post(url, json={**(body or {}), **AUTH},
                              params=AUTH, timeout=timeout)
        elif method == "PUT":
            r = requests.put(url, json={**(body or {}), **AUTH},
                             params=AUTH, timeout=timeout)
        elif method == "DEL":
            r = requests.delete(url, params=p, timeout=timeout)
        else:
            return {}, 0

        data = r.json()
        _fix_dates(data)        # <- -3h aplicado em TODA a resposta
        return data, r.status_code

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


# ─────────────────────────────────────────────────────────────────────────────
# EXTRAÇÃO DE LISTAS
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS DE LISTAGEM
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# BUSCA DE VEÍCULO POR PLACA / NOME
# ─────────────────────────────────────────────────────────────────────────────

def find_vehicle(q: str) -> dict | None:
    """Busca um evento pelo campo placa ou nome do veículo (case-insensitive)."""
    nq = re.sub(r"[^A-Z0-9]", "", q.upper())
    for ev in get_all_events():
        if re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_vei_placa", "")).upper()) == nq:
            return ev
        if nq in re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_vei_veiculo", "")).upper()):
            return ev
    return None


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES DA ABA CRONOLOGIA
# ─────────────────────────────────────────────────────────────────────────────

"""
_api.py — Cliente HTTP para a API PHP de Cronologia.
"""

import requests
import core.credencials as _cred


def _cron_url() -> str:
    return getattr(_cred, "CRON_API_URL", "")


def _cron_key() -> str:
    return getattr(_cred, "CRON_API_KEY", "")


def _cron_headers() -> dict:
    return {
        "Content-Type": "application/json",
        getattr(_cred, "_CRON_TOKEN_HEADER_NAME", "X-API-Token"): _cron_key(),
    }


def _cron_req(method: str, path: str, params: dict | None = None,
              body: dict | None = None, timeout: int = 15):
    try:
        query = {"path": path}
        if params:
            query.update(params)
        r = requests.request(
            method=method.upper(),
            url=_cron_url(),
            headers=_cron_headers(),
            params=query,
            json=body,
            timeout=timeout,
        )
        try:
            data = r.json()
        except Exception:
            data = {
                "status": False,
                "error": f"Resposta não-JSON (HTTP {r.status_code})",
                "raw": (r.text or "")[:4000],
            }
        return data, r.status_code
    except requests.exceptions.ConnectionError:
        return {"status": False, "error": "Sem conexão com a API."}, 0
    except requests.exceptions.Timeout:
        return {"status": False, "error": "Timeout na requisição."}, 0
    except Exception as exc:
        return {"status": False, "error": str(exc)}, 0


def _cron_get(path: str, params: dict | None = None) -> dict:
    data, _ = _cron_req("GET", path, params=params)
    return data


def _cron_post(path: str, body: dict | None = None, params: dict | None = None):
    return _cron_req("POST", path, params=params, body=body)


def _cron_put(path: str, body: dict | None = None, params: dict | None = None):
    return _cron_req("PUT", path, params=params, body=body)


def _cron_delete(path: str, params: dict | None = None):
    return _cron_req("DELETE", path, params=params)