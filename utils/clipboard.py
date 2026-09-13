"""
widgets/clipboard.py
Utilitários globais de clipboard para a aplicação IFControll.

Uso:
    from widgets.clipboard import bind_global_copy, copy_to_clipboard
"""

import tkinter as tk


def copy_to_clipboard(root: tk.Misc, text: str) -> None:
    """Copia texto para o clipboard do sistema."""
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()


def bind_global_copy(root: tk.Tk) -> None:
    """
    Registra Ctrl+C global na janela raiz.
    Copia o texto selecionado em qualquer Entry ou Text ativo.
    Funciona como fallback quando o widget focado não tem binding próprio.
    """
    def _copy(event=None):
        w = root.focus_get()
        if w is None:
            return
        try:
            if isinstance(w, tk.Entry):
                sel = w.selection_get()
                copy_to_clipboard(root, sel)
            elif isinstance(w, tk.Text):
                sel = w.get(tk.SEL_FIRST, tk.SEL_LAST)
                copy_to_clipboard(root, sel)
            elif hasattr(w, "selection_get"):
                # ttk.Treeview ou outros widgets com seleção
                sel = w.selection_get()
                copy_to_clipboard(root, sel)
        except (tk.TclError, AttributeError):
            pass  # Nada selecionado — ignora silenciosamente

    root.bind_all("<Control-c>", _copy, add="+")
    root.bind_all("<Control-C>", _copy, add="+")


def clipboard_get(root: tk.Misc) -> str:
    """Retorna conteúdo atual do clipboard. Retorna '' em caso de erro."""
    try:
        return root.clipboard_get()
    except tk.TclError:
        return ""


__all__ = ["bind_global_copy", "copy_to_clipboard", "clipboard_get"]