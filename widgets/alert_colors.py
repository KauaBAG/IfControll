"""
widgets/alert_colors.py
Cores de alerta que se adaptam ao tema claro/escuro.
Importe _ac() onde precisar de background de tag adaptativo.
"""
from utils.theme_manager import C

# Paleta escura
_DARK = {
    "crit":  "#1a0505",  # vermelho muito escuro
    "alto":  "#1a0d00",  # laranja escuro
    "med":   "#1a1500",  # amarelo escuro
    "warn":  "#1a1300",  # amarelo-laranja escuro
    "ok":    None,       # → C["surface2"]
    "al":    "#1a0808",  # alerta genérico escuro
    "al2":   "#1a1a2e",  # destaque azul escuro (top/medals)
    "al3":   "#150d00",  # custo alto escuro
}

# Paleta clara (pastel)
_LIGHT = {
    "crit":  "#FFD6D6",
    "alto":  "#FFE8CC",
    "med":   "#FFF9CC",
    "warn":  "#FFF0CC",
    "ok":    None,       # → C["surface2"]
    "al":    "#FFD6D6",
    "al2":   "#E8EAFF",
    "al3":   "#FFE8CC",
}

def _ac(key: str) -> str:
    """Retorna a cor de alerta adaptada ao tema atual."""
    palette = _DARK if C["mode"] == "dark" else _LIGHT
    val = palette.get(key)
    return val if val is not None else C["surface2"]