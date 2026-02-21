"""
widgets/helpers.py
Helpers compostos que combinam primitivos para casos de uso comuns.
Os widgets gerados aqui herdam o suporte a tema via primitives.py.
"""

import tkinter as tk
from datetime import datetime
from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import fmt_hours_ago
from .primitives import lbl, ent, btn
from .tree import export_tree, export_text


def interval_row(parent):
    """Linha com dois campos de data (Início / Fim). Retorna (entry_inicio, entry_fim)."""
    r = tk.Frame(parent, bg=C["bg"])
    r.pack(fill="x", pady=3)

    lbl(r, "Início:", 9, col=C["text_mid"]).pack(side="left", anchor="w", padx=(0, 4))
    ei = ent(r, w=18)
    ei.pack(side="left", padx=(0, 16), ipady=4)
    ei.insert(0, fmt_hours_ago(8))

    lbl(r, "Fim:", 9, col=C["text_mid"]).pack(side="left")
    ef = ent(r, w=18)
    ef.pack(side="left", ipady=4)
    ef.insert(0, datetime.now().strftime("%d/%m/%Y %H:%M"))

    # O frame da linha precisa de recoloração própria pois não passa por lbl()
    def recolor():
        try:
            r.config(bg=C["bg"])
        except Exception:
            pass

    register_theme_listener(recolor)
    return ei, ef


def mk_export_btn(parent, tree_or_text, is_text: bool = False) -> tk.Label:
    """Cria botão de exportação padronizado para Treeview ou Text widget."""
    def do_export():
        if is_text:
            export_text(tree_or_text)
        else:
            export_tree(tree_or_text)
    return btn(parent, "📥 EXPORTAR CSV", do_export, C["surface3"], C["accent"], px=10, py=5)