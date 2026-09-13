"""
core/config.py
Centraliza constantes da aplicação e re-exporta credenciais.
Altere apenas este arquivo para mudar configurações globais.
"""

from .credencials import API_KEY, SECRET_KEY, BASE_URL, AUTH

# ── Configurações de comportamento ────────────────────────────────────────────

# Timeout padrão para requisições HTTP (segundos)
HTTP_TIMEOUT: int = 30

# Intervalo do auto-refresh no dashboard (ms)
DASHBOARD_REFRESH_MS: int = 30_000

# Limite de velocidade padrão para alertas (km/h)
DEFAULT_SPEED_LIMIT: int = 80

# Consumo ocioso estimado (litros/hora)
IDLE_FUEL_L_PER_H: float = 0.5

# Fuso horário Brasil (horas offset UTC)
TZ_OFFSET_BR: int = -3

# Número máximo de pontos retornados por paginação
DEFAULT_PAGE_SIZE: int = 50

# ── Re-exporta credenciais para uso interno ───────────────────────────────────
__all__ = [
    "API_KEY", "SECRET_KEY", "BASE_URL", "AUTH",
    "HTTP_TIMEOUT", "DASHBOARD_REFRESH_MS", "DEFAULT_SPEED_LIMIT",
    "IDLE_FUEL_L_PER_H", "TZ_OFFSET_BR", "DEFAULT_PAGE_SIZE",
]