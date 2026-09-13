"""
cronologia/_widgets.py
Redirecionador de compatibilidade — FilterableCombobox foi movida para:
  • widgets/filtercombo.py

Não adicione lógica aqui. Importe diretamente de widgets.filtercombo
em código novo.
"""

from widgets.filtercombo import FilterableCombobox

__all__ = ["FilterableCombobox"]
