"""
theme_manager.py — IFControll v3.0
Gerencia o tema claro/escuro e fornece toggle global.
Cole este módulo no início do arquivo principal, substituindo o dict C existente.
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

# Instância global — começa com tema escuro
C = dict(DARK_THEME)

# Lista de callbacks registrados para redesenho
_theme_listeners = []

def register_theme_listener(callback):
    """Registra uma função que será chamada ao trocar de tema."""
    _theme_listeners.append(callback)

def toggle_theme():
    """Alterna entre claro e escuro, atualiza C e notifica todos os listeners."""
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


# ─── BOTÃO DE TOGGLE (cole no header da janela principal) ───────────────────
def mk_theme_btn(parent, root_window):
    """
    Cria o botão de alternância de tema.
    parent  — frame do header onde o botão será empacotado
    root_window — tk.Tk() principal, necessário para redesenhar o root
    """
    import tkinter as tk

    lbl_var = tk.StringVar(value=get_theme_label())

    def _toggle():
        mode = toggle_theme()
        lbl_var.set(get_theme_label())
        # Redesenha o root e todos os filhos recursivamente
        _repaint(root_window)

    b = tk.Label(
        parent, textvariable=lbl_var,
        bg=C["surface3"], fg=C["accent"],
        font=("Helvetica Neue", 9, "bold"),
        padx=10, pady=5, cursor="hand2", relief="flat"
    )
    b.bind("<Button-1>", lambda e: _toggle())

    def _refresh_btn():
        b.config(bg=C["surface3"], fg=C["accent"])
        lbl_var.set(get_theme_label())

    register_theme_listener(_refresh_btn)
    return b


def _repaint(widget):
    """Redesenha recursivamente todos os widgets com as cores do tema atual."""
    import tkinter as tk
    from tkinter import ttk

    wtype = widget.winfo_class()

    # Mapeamento de classes para cores
    color_map = {
        "Frame":    {"bg": C["bg"]},
        "Label":    {"bg": C["bg"], "fg": C["text"]},
        "Entry":    {"bg": C["surface3"], "fg": C["text"],
                     "insertbackground": C["accent"],
                     "highlightbackground": C["border"],
                     "highlightcolor": C["accent"]},
        "Text":     {"bg": C["surface2"], "fg": C["text"],
                     "insertbackground": C["accent"],
                     "selectbackground": C["accent2"]},
        "Canvas":   {"bg": C["surface2"]},
        "Scrollbar":{"bg": C["surface2"], "troughcolor": C["bg"]},
        "Checkbutton": {"bg": C["bg"], "fg": C["text"],
                        "activebackground": C["bg"],
                        "selectcolor": C["surface3"]},
    }

    try:
        if wtype in color_map:
            widget.config(**color_map[wtype])
    except tk.TclError:
        pass

    # ttk — reaplica estilos
    if isinstance(widget, ttk.Treeview):
        style = ttk.Style()
        sname = widget.cget("style").split(".")[0] if widget.cget("style") else "B"
        style.configure(f"{sname}.Treeview",
                        background=C["surface2"], foreground=C["text"],
                        fieldbackground=C["surface2"])
        style.configure(f"{sname}.Treeview.Heading",
                        background=C["surface3"], foreground=C["accent"])
        style.map(f"{sname}.Treeview",
                  background=[("selected", C["accent2"])])

    for child in widget.winfo_children():
        _repaint(child)
