"""
widgets/primitives.py
Componentes atômicos de UI: labels, entries, buttons, textboxes, scrollables,
treeview styles.
Todos dependem de theme_manager.C para cores e se registram para
recoloração automática quando o tema muda.
"""

import tkinter as tk
from tkinter import ttk
from utils.theme_manager import C, register_theme_listener

# ── Rastreamento de widgets para recoloração dinâmica ─────────────────────────
# Cada entrada: (widget_ref, fn_recolor)
_tracked: list = []


def _recolor_all():
    """Chamado pelo theme_manager ao trocar de tema. Recolore todos os widgets rastreados."""
    dead = []
    for i, (ref, fn) in enumerate(_tracked):
        try:
            ref.winfo_exists()  # levanta TclError se destruído
            fn()
        except Exception:
            dead.append(i)
    for i in reversed(dead):
        _tracked.pop(i)


register_theme_listener(_recolor_all)


def _track(widget, fn):
    """Registra widget + função de recoloração."""
    _tracked.append((widget, fn))
    return widget


# ── Cor clara (hover) ─────────────────────────────────────────────────────────

def _lt(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
    return f"#{min(255, r+28):02x}{min(255, g+28):02x}{min(255, b+28):02x}"


# ── Primitivos ────────────────────────────────────────────────────────────────

def lbl(parent, text: str = "", size: int = 10, bold: bool = False,
        col=None, bg=None, **kw) -> tk.Label:
    """Label com recoloração automática de tema."""
    col_key = None
    bg_key  = None
    for k, v in C.items():
        if v == col: col_key = k
        if v == bg:  bg_key  = k

    w = tk.Label(
        parent, text=text,
        bg=bg or C["bg"],
        fg=col or C["text"],
        font=("Helvetica Neue", size, "bold" if bold else "normal"),
        **kw,
    )

    def recolor():
        try:
            w.config(
                bg=C[bg_key]  if bg_key  else C["bg"],
                fg=C[col_key] if col_key else C["text"],
            )
        except Exception:
            pass

    _track(w, recolor)
    return w


def ent(parent, w: int = None, **kw) -> tk.Entry:
    """Entry com recoloração automática de tema."""
    e = tk.Entry(
        parent,
        bg=C["surface3"], fg=C["text"],
        insertbackground=C["accent"],
        relief="flat",
        highlightthickness=1,
        highlightbackground=C["border"],
        highlightcolor=C["accent"],
        font=("Helvetica Neue", 10),
        **kw,
    )
    if w:
        e.config(width=w)

    def recolor():
        try:
            e.config(
                bg=C["surface3"], fg=C["text"],
                insertbackground=C["accent"],
                highlightbackground=C["border"],
                highlightcolor=C["accent"],
            )
        except Exception:
            pass

    _track(e, recolor)
    return e


def btn(parent, text: str, cmd, bg=None, fg=None,
        px: int = 14, py: int = 6, w: int = None) -> tk.Label:
    """Botão (Label clicável) com hover e recoloração automática de tema."""
    col_key = None
    for k, v in C.items():
        if v == bg:
            col_key = k
            break

    def _get_col():
        return C[col_key] if col_key else (bg or C["accent"])

    b = tk.Label(
        parent, text=text,
        bg=_get_col(), fg=fg or C["bg"],
        font=("Helvetica Neue", 9, "bold"),
        padx=px, pady=py,
        cursor="hand2", relief="flat",
    )
    if w:
        b.config(width=w)

    b.bind("<Enter>",    lambda e: b.config(bg=_lt(_get_col())))
    b.bind("<Leave>",    lambda e: b.config(bg=_get_col()))
    b.bind("<Button-1>", lambda e: cmd())

    def recolor():
        try:
            b.config(bg=_get_col())
        except Exception:
            pass

    _track(b, recolor)
    return b


def btn2(parent, text: str, cmd, bg=None, fg=None) -> tk.Button:
    """
    Botão nativo tk.Button — útil quando se precisa de estado disabled,
    relief raised/groove ou integração com grid managers que não funcionam
    bem com Label clicável.
    Inclui recoloração automática de tema.
    """
    col_key = None
    for k, v in C.items():
        if v == bg:
            col_key = k
            break

    def _get_col():
        return C[col_key] if col_key else (bg or C["accent"])

    b = tk.Button(
        parent, text=text, command=cmd,
        bg=_get_col(), fg=fg or C["bg"],
        activebackground=_get_col(),
        activeforeground=fg or C["bg"],
        relief="flat", bd=0, cursor="hand2",
        font=("Helvetica Neue", 9, "bold"), padx=10, pady=6,
    )

    def recolor():
        try:
            col = _get_col()
            b.config(bg=col, activebackground=col)
        except Exception:
            pass

    _track(b, recolor)
    return b


def sec(parent, title: str, col=None):
    """Linha de seção com título e separador horizontal."""
    col_key = None
    for k, v in C.items():
        if v == col:
            col_key = k
            break

    f = tk.Frame(parent, bg=C["bg"])
    f.pack(fill="x", pady=(10, 4))

    lbl_w = tk.Label(
        f, text=title,
        bg=C["bg"], fg=col or C["accent"],
        font=("Helvetica Neue", 9, "bold"),
    )
    lbl_w.pack(side="left")

    sep = tk.Frame(f, bg=C["border"], height=1)
    sep.pack(side="left", fill="x", expand=True, padx=(6, 0), pady=6)

    def recolor():
        try:
            f.config(bg=C["bg"])
            lbl_w.config(bg=C["bg"], fg=C[col_key] if col_key else C["accent"])
            sep.config(bg=C["border"])
        except Exception:
            pass

    _track(f, recolor)


def txtbox(parent, h: int = 6):
    """
    Frame + Text widget com scrollbar lateral.
    Retorna (frame, text_widget). Ambos com recoloração automática.
    """
    fr = tk.Frame(
        parent,
        bg=C["surface2"],
        highlightthickness=1,
        highlightbackground=C["border"],
    )
    t = tk.Text(
        fr, height=h,
        bg=C["surface2"], fg=C["text"],
        insertbackground=C["accent"],
        relief="flat",
        font=("Consolas", 9),
        padx=8, pady=6,
        selectbackground=C["accent2"],
        state="disabled",
    )
    sb = tk.Scrollbar(fr, command=t.yview, bg=C["surface2"],
                      troughcolor=C["bg"], relief="flat")
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(fill="both", expand=True)

    def recolor():
        try:
            fr.config(bg=C["surface2"], highlightbackground=C["border"])
            t.config(bg=C["surface2"], fg=C["text"],
                     insertbackground=C["accent"], selectbackground=C["accent2"])
            sb.config(bg=C["surface2"], troughcolor=C["bg"])
        except Exception:
            pass

    _track(fr, recolor)
    return fr, t


def make_scrollable(parent):
    """
    Envolve um Frame pai num Canvas com scrollbar vertical e suporte a
    MouseWheel. Retorna (canvas, inner_frame) onde inner_frame é onde
    os filhos devem ser adicionados.
    """
    canvas = tk.Canvas(parent, bg=C["bg"], highlightthickness=0)
    vsb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=C["bg"])
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    inner.bind(
        "<Configure>",
        lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.bind(
        "<Configure>",
        lambda e: canvas.itemconfig(win_id, width=e.width)
    )

    def _on_wheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_wheel))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    def recolor():
        try:
            canvas.config(bg=C["bg"])
            inner.config(bg=C["bg"])
        except Exception:
            pass

    _track(canvas, recolor)
    return canvas, inner


def apply_treeview_style(name: str, hcol: str | None = None):
    """
    Aplica (ou re-aplica) um estilo ttk.Treeview nomeado.
    Deve ser chamado tanto na criação quanto no callback de recolor do tema.

    Exemplo:
        apply_treeview_style("Cron", C["accent"])
        tree = ttk.Treeview(parent, style="Cron.Treeview")
    """
    s = ttk.Style()
    s.theme_use("clam")
    s.configure(
        f"{name}.Treeview",
        background=C["surface2"], foreground=C["text"], rowheight=26,
        fieldbackground=C["surface2"], borderwidth=0, font=("Consolas", 9),
    )
    s.configure(
        f"{name}.Treeview.Heading",
        background=C["surface3"], foreground=hcol or C["accent"],
        font=("Helvetica Neue", 9, "bold"), borderwidth=0, relief="flat",
    )
    s.map(f"{name}.Treeview", background=[("selected", C["accent2"])])


# ── Escrita no Text widget ────────────────────────────────────────────────────

def write(t: tk.Text, text: str, col=None):
    """Limpa e escreve texto no Text widget (mantém state=disabled quando não edita)."""
    t.config(state="normal")
    t.delete("1.0", "end")
    t.config(fg=col or C["text"])
    t.insert("end", text)
    t.config(state="disabled")


def loading(t: tk.Text):
    """Atalho: exibe mensagem de carregamento no Text widget."""
    write(t, "⏳  Aguardando API...", C["accent"])


def err(t: tk.Text, msg: str):
    """Atalho: exibe mensagem de erro no Text widget."""
    write(t, f"✖  {msg}", C["danger"])


def ok(t: tk.Text, msg: str):
    """Atalho: exibe mensagem de sucesso no Text widget."""
    write(t, f"✔  {msg}", C["success"])