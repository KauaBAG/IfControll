"""
cronologia/_helpers.py
Redirecionador de compatibilidade — todo o código foi consolidado em:
  • widgets/primitives.py  → lbl, ent, btn, btn2, txtbox, write,
                             make_scrollable, apply_treeview_style
  • widgets/helpers.py     → fmt_dt, fmt_date, to_api_dt, to_api_date,
                             now_ui, safe

Não adicione lógica aqui. Importe diretamente dos módulos acima em
código novo.
"""

# ── UI primitivos ─────────────────────────────────────────────────────────────
from widgets.primitives import (
    lbl,
    ent,
    btn,
    txtbox,
    write,
    make_scrollable,
    apply_treeview_style,
)

# ── Utilitários de data e string ──────────────────────────────────────────────
from widgets.helpers import (
    fmt_dt,
    fmt_date,
    to_api_dt,
    to_api_date,
    now_ui,
    safe,
)

__all__ = [
    "lbl", "ent", "btn", "btn2", "txtbox", "write",
    "make_scrollable", "apply_treeview_style",
    "fmt_dt", "fmt_date", "to_api_dt", "to_api_date", "now_ui", "safe",
]
