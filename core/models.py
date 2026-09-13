"""
core/models.py
Funções puras: conversão de tipos, cálculos geográficos e formatação.
Sem dependências de UI ou API.
"""

import math


# ── Conversão segura de tipos ─────────────────────────────────────────────────

def safe_int(v, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(float(str(v).replace(",", ".")))
    except (ValueError, TypeError):
        return default


def safe_float(v, default: float = 0.0):
    if v is None:
        return default
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return default


def safe_str(v, default: str = "—") -> str:
    s = str(v).strip() if v is not None else ""
    return default if s in ("", "None", "null") else s


# ── Geográfico ────────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2) -> float:
    """Retorna distância em km entre dois pontos GPS."""
    try:
        R = 6371.0
        la1, lo1, la2, lo2 = (math.radians(safe_float(x)) for x in [lat1, lon1, lat2, lon2])
        dlat, dlon = la2 - la1, lo2 - lo1
        a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(max(0, min(1, a))))
    except Exception:
        return 0.0


# ── Formatação de tempo ───────────────────────────────────────────────────────

def hms(seconds: float) -> str:
    """Converte segundos em string 'HHh MMm'."""
    s = max(0, int(seconds))
    return f"{s // 3600:02d}h {(s % 3600) // 60:02d}m"