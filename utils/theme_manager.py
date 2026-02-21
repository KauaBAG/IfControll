"""
theme_manager.py — IFControll v3.0
Gerencia o tema claro/escuro e fornece toggle global.
"""

# ─── PALETAS DE CORES ───────────────────────────────────────────────────────
DARK_THEME = {
    "bg":"#0B0D12","surface":"#12151E","surface2":"#181C29","surface3":"#1E2335",
    "border":"#232840","accent":"#00C8F8","accent2":"#6C5CE7","warn":"#FFA502",
    "danger":"#FF3B4E","success":"#00F5A0","text":"#DDE1F0","text_dim":"#58607A",
    "text_mid":"#8B93B5","hover":"#1C2138","green":"#00F5A0","blue":"#00C8F8",
    "purple":"#6C5CE7","orange":"#FF7043","yellow":"#FFA502","red":"#FF3B4E",
    "pink":"#FD79A8","mode":"dark",
}

LIGHT_THEME = {
    "bg":"#F0F2F8","surface":"#FFFFFF","surface2":"#F5F7FC","surface3":"#E8ECF5",
    "border":"#CDD2E8","accent":"#0099CC","accent2":"#5A4BD1","warn":"#E67E00",
    "danger":"#D63040","success":"#00AA70","text":"#1A1F36","text_dim":"#8892AA",
    "text_mid":"#4A5270","hover":"#E2E6F5","green":"#00AA70","blue":"#0099CC",
    "purple":"#5A4BD1","orange":"#CC5500","yellow":"#CC8800","red":"#D63040",
    "pink":"#CC5580","mode":"light",
}

C = dict(DARK_THEME)

# Conjunto dos valores de cor "neutros" (bg/surface) — usados para identificar
# labels de fundo puro vs. labels coloridos (botões)
def _neutral_bg_values():
    """Retorna o conjunto de valores de background neutros do tema atual."""
    return {C["bg"], C["surface"], C["surface2"], C["surface3"], C["border"], C["hover"]}

_theme_listeners = []

def register_theme_listener(callback):
    _theme_listeners.append(callback)

def toggle_theme():
    global C
    if C["mode"] == "dark":
        C.update(LIGHT_THEME)
    else:
        C.update(DARK_THEME)
    for cb in _theme_listeners:
        try:
            cb()
        except Exception:
            pass
    return C["mode"]

def get_theme_label():
    return "☀ CLARO" if C["mode"] == "dark" else "🌙 ESCURO"


# ─── BOTÃO DE TOGGLE ────────────────────────────────────────────────────────
def mk_theme_btn(parent, root_window):
    import tkinter as tk

    lbl_var = tk.StringVar(value=get_theme_label())

    def _toggle():
        toggle_theme()
        lbl_var.set(get_theme_label())

    b = tk.Label(
        parent, textvariable=lbl_var,
        bg=C["surface3"], fg=C["accent"],
        font=("Helvetica Neue", 9, "bold"),
        padx=10, pady=5, cursor="hand2", relief="flat",
    )
    b.bind("<Button-1>", lambda e: _toggle())

    def _refresh_btn():
        b.config(bg=C["surface3"], fg=C["accent"])
        lbl_var.set(get_theme_label())

    register_theme_listener(_refresh_btn)
    return b


# ─── REPAINT RECURSIVO ───────────────────────────────────────────────────────

# Conjunto de todas as cores de paleta possíveis (dark + light) para detectar
# se um widget tem cor de acento/semântica (botão colorido) vs. cor de fundo neutro.
_ALL_PALETTE_COLORS = set(DARK_THEME.values()) | set(LIGHT_THEME.values())
_ALL_PALETTE_COLORS.discard("dark")
_ALL_PALETTE_COLORS.discard("light")

# Cores que são "background neutro" em qualquer tema — usadas para distinguir
# labels normais de labels-botão (que têm cor de acento como bg)
_NEUTRAL_KEYS = {"bg", "surface", "surface2", "surface3", "border", "hover"}


def _is_neutral_bg(color: str) -> bool:
    """True se a cor é um fundo neutro de tema (não é acento/semântica)."""
    dark_neutrals  = {DARK_THEME[k]  for k in _NEUTRAL_KEYS}
    light_neutrals = {LIGHT_THEME[k] for k in _NEUTRAL_KEYS}
    return color in dark_neutrals or color in light_neutrals


def _find_color_key(color: str):
    """Devolve a chave de C para uma cor de paleta, ou None se não for paleta."""
    for k, v in DARK_THEME.items():
        if v == color:
            return k
    for k, v in LIGHT_THEME.items():
        if v == color:
            return k
    return None


def _repaint(widget):
    """
    Repinta recursivamente todos os widgets tk (não-ttk) com as cores
    do tema atual. Widgets não-tkinter (ttk puro) são ignorados aqui —
    eles são tratados por register_theme_listener nos módulos de widgets.

    Lógica para Label/Frame:
    - Se o bg atual É uma cor neutra de paleta → atualiza para o bg neutro equivalente do tema atual
    - Se o bg atual É uma cor de acento/semântica → mantém o acento correspondente no tema atual
    - Se o bg atual NÃO é de paleta → não toca (cor personalizada do usuário)
    """
    import tkinter as tk
    from tkinter import ttk

    # ttk widgets: só Treeview precisa de tratamento (feito em tree.py via listener)
    # Scrollbar ttk, Notebook, Combobox etc. → ignorar aqui
    if isinstance(widget, (ttk.Notebook, ttk.Combobox, ttk.Scrollbar,
                           ttk.Entry, ttk.Button, ttk.Label)):
        for child in widget.winfo_children():
            _repaint(child)
        return

    wtype = widget.winfo_class()

    try:
        if wtype == "Frame":
            cur_bg = widget.cget("bg")
            key = _find_color_key(cur_bg)
            if key and key in C:
                widget.config(bg=C[key])

        elif wtype == "Label":
            cur_bg = widget.cget("bg")
            cur_fg = widget.cget("fg")
            bg_key = _find_color_key(cur_bg)
            fg_key = _find_color_key(cur_fg)
            cfg = {}
            if bg_key and bg_key in C:
                cfg["bg"] = C[bg_key]
            if fg_key and fg_key in C:
                cfg["fg"] = C[fg_key]
            if cfg:
                widget.config(**cfg)

        elif wtype == "Entry":
            cur_bg = widget.cget("bg")
            key = _find_color_key(cur_bg)
            if key and key in C:
                widget.config(
                    bg=C["surface3"], fg=C["text"],
                    insertbackground=C["accent"],
                    highlightbackground=C["border"],
                    highlightcolor=C["accent"],
                )

        elif wtype == "Text":
            widget.config(
                bg=C["surface2"], fg=C["text"],
                insertbackground=C["accent"],
                selectbackground=C["accent2"],
            )

        elif wtype == "Canvas":
            cur_bg = widget.cget("bg")
            key = _find_color_key(cur_bg)
            if key and key in C:
                widget.config(bg=C[key])

        elif wtype == "Scrollbar":
            widget.config(bg=C["surface2"], troughcolor=C["bg"])

        elif wtype == "Checkbutton":
            widget.config(bg=C["bg"], fg=C["text"],
                          activebackground=C["bg"],
                          selectcolor=C["surface3"])

    except tk.TclError:
        pass

    # Treeview ttk — reaplica o estilo pelo nome registrado
    if isinstance(widget, ttk.Treeview):
        style = ttk.Style()
        raw = widget.cget("style")           # ex: "Dashboard.Treeview"
        sname = raw.split(".")[0] if raw else "B"
        style.configure(f"{sname}.Treeview",
                        background=C["surface2"], foreground=C["text"],
                        fieldbackground=C["surface2"])
        style.configure(f"{sname}.Treeview.Heading",
                        background=C["surface3"])
        style.map(f"{sname}.Treeview",
                  background=[("selected", C["accent2"])])

    for child in widget.winfo_children():
        _repaint(child)