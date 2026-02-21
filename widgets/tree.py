"""
widgets/tree.py
Treeview estilizado, exportação CSV/TXT e atalhos de clipboard para árvores legadas.
Todos os estilos ttk são registrados e reaplicados automaticamente ao trocar de tema.
"""

import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from utils.theme_manager import C, register_theme_listener


# ── Registro global de estilos criados ────────────────────────────────────────
# { nome_estilo: hcol_original }  — armazenamos a chave C ou None
_style_registry: dict[str, str | None] = {}


def _reapply_all_styles():
    """Reaplicado pelo theme_manager ao trocar de tema.
    Recria todos os estilos ttk já registrados com as cores atuais."""
    for name, hcol_key in _style_registry.items():
        hcol = C[hcol_key] if hcol_key and hcol_key in C else hcol_key
        _do_apply_style(name, hcol)


register_theme_listener(_reapply_all_styles)


def _do_apply_style(name: str, hcol) -> str:
    """Aplica/atualiza o estilo ttk sem registrar novamente."""
    s = ttk.Style()
    s.theme_use("clam")
    s.configure(
        f"{name}.Treeview",
        background=C["surface2"], foreground=C["text"],
        rowheight=26, fieldbackground=C["surface2"],
        borderwidth=0, font=("Consolas", 9),
    )
    s.configure(
        f"{name}.Treeview.Heading",
        background=C["surface3"],
        foreground=hcol or C["accent"],
        font=("Helvetica Neue", 9, "bold"),
        borderwidth=0, relief="flat",
    )
    s.map(f"{name}.Treeview", background=[("selected", C["accent2"])])
    return f"{name}.Treeview"


def apply_tree_style(name: str, hcol=None) -> str:
    """Aplica o estilo ttk e o registra para recoloração automática ao trocar tema."""
    # Guarda a chave do dict C para recuperar a cor atualizada depois
    hcol_key = None
    if hcol is not None:
        for k, v in C.items():
            if v == hcol:
                hcol_key = k
                break
        if hcol_key is None:
            hcol_key = hcol  # cor literal, não chave — salva o valor mesmo
    _style_registry[name] = hcol_key
    return _do_apply_style(name, hcol)


# ── Rastreamento de frames-container de Treeviews para recolorir bg ───────────
_tree_frames: list = []  # lista de tk.Frame que envolvem Treeviews


def _recolor_tree_frames():
    dead = []
    for i, fr in enumerate(_tree_frames):
        try:
            fr.config(bg=C["bg"])
        except Exception:
            dead.append(i)
    for i in reversed(dead):
        _tree_frames.pop(i)


register_theme_listener(_recolor_tree_frames)


# ── Fábrica de Treeview ───────────────────────────────────────────────────────

def mk_tree(parent, cols, ws, sname: str = "B", hcol=None, h: int = 12) -> ttk.Treeview:
    style = apply_tree_style(sname, hcol)
    fr = tk.Frame(parent, bg=C["bg"])
    _tree_frames.append(fr)

    t = ttk.Treeview(fr, columns=cols, show="headings", style=style, height=h)
    for c, w in zip(cols, ws):
        t.heading(c, text=c, anchor="w")
        t.column(c, width=w, anchor="w", stretch=True)

    vs = ttk.Scrollbar(fr, orient="vertical",   command=t.yview)
    hs = ttk.Scrollbar(fr, orient="horizontal",  command=t.xview)
    t.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
    vs.pack(side="right",  fill="y")
    hs.pack(side="bottom", fill="x")
    t.pack(fill="both", expand=True)
    fr.pack(fill="both", expand=True)

    attach_copy(t)
    return t


# ── Exportação ────────────────────────────────────────────────────────────────

def export_tree(tree: ttk.Treeview, title: str = "Exportar CSV"):
    cols = [tree.heading(c)["text"] for c in tree["columns"]]
    rows = [tree.item(r)["values"] for r in tree.get_children()]
    if not rows:
        messagebox.showinfo("Exportar", "Nenhum dado para exportar.")
        return
    path = filedialog.asksaveasfilename(
        title=title,
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        initialfile=f"ifcontroll_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cols)
            w.writerows(rows)
        messagebox.showinfo("Exportar", f"Arquivo salvo:\n{path}")
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")


def export_text(text_widget: tk.Text, title: str = "Exportar TXT"):
    content = text_widget.get("1.0", "end").strip()
    if not content:
        messagebox.showinfo("Exportar", "Nenhum conteúdo para exportar.")
        return
    path = filedialog.asksaveasfilename(
        title=title,
        defaultextension=".txt",
        filetypes=[("Texto", "*.txt"), ("CSV", "*.csv"), ("Todos", "*.*")],
        initialfile=f"ifcontroll_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
    )
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("Exportar", f"Arquivo salvo:\n{path}")
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")


# ── Clipboard para Treeviews legados ─────────────────────────────────────────

def attach_copy(tree_widget: ttk.Treeview) -> ttk.Treeview:
    """Adiciona Ctrl+C e menu de contexto a um Treeview.
    O menu é recriado ao trocar de tema para refletir as cores corretas."""

    _menu_holder = [None]  # lista para permitir mutação em closure

    def _build_menu():
        if _menu_holder[0] is not None:
            try:
                _menu_holder[0].destroy()
            except Exception:
                pass
        m = tk.Menu(
            tree_widget, tearoff=0,
            bg=C["surface3"], fg=C["text"],
            activebackground=C["accent2"], activeforeground=C["text"],
            font=("Helvetica Neue", 9),
        )
        m.add_command(label="📋  Copiar linha selecionada", command=copy_row)
        m.add_command(label="📋  Copiar tudo (CSV)",        command=copy_all)
        m.add_separator()
        m.add_command(label="📥  Exportar CSV", command=lambda: export_tree(tree_widget))
        _menu_holder[0] = m

    def copy_row():
        sel = tree_widget.selection()
        if not sel:
            return
        lines = ["\t".join(str(v) for v in tree_widget.item(i)["values"]) for i in sel]
        tree_widget.clipboard_clear()
        tree_widget.clipboard_append("\n".join(lines))

    def copy_all():
        cols = [tree_widget.heading(c)["text"] for c in tree_widget["columns"]]
        rows = [tree_widget.item(r)["values"] for r in tree_widget.get_children()]
        lines = [";".join(str(c) for c in cols)]
        for row in rows:
            lines.append(";".join(str(v) for v in row))
        tree_widget.clipboard_clear()
        tree_widget.clipboard_append("\n".join(lines))

    def ctx(e):
        item = tree_widget.identify_row(e.y)
        if item:
            tree_widget.selection_set(item)
        try:
            _menu_holder[0].tk_popup(e.x_root, e.y_root)
        finally:
            _menu_holder[0].grab_release()

    _build_menu()
    register_theme_listener(_build_menu)

    tree_widget.bind("<Control-c>", lambda e: copy_row())
    tree_widget.bind("<Control-C>", lambda e: copy_row())
    tree_widget.bind("<Button-3>",  ctx)
    return tree_widget