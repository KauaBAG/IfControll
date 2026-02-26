"""
main.py — IFControll v3.0
Ponto de entrada: janela principal, header, notebook e footer.
Toda a lógica de aba está em tabs/, UI em widgets/, API em core/.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime

from utils.theme_manager import C, mk_theme_btn, register_theme_listener, _repaint
from utils.auto_refresh_export import now_str, auto_refresh_loop, bind_global_copy, mk_refresh_controls

from tabs import TAB_REGISTRY
#from tabs.cronologia import TabCronologia


# ── Referência global ao notebook (necessária para reestilizar as abas) ───────
_nb: ttk.Notebook | None = None
_root: tk.Tk | None = None


# ═══════════════════════════════════════════════════════════════════════════════
#  JANELA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def build_window() -> tk.Tk:
    global _root
    root = tk.Tk()
    root.title("IFControll v3.0 — Fleet Intelligence Platform")
    root.configure(bg=C["bg"])
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    W, H = 1280, 800
    root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
    root.minsize(1024, 650)
    _root = root
    return root

def build_header(root: tk.Tk) -> None:
    hdr = tk.Frame(root, bg=C["surface"], height=52)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Frame(root, bg=C["accent"], height=2).pack(fill="x")

    lf = tk.Frame(hdr, bg=C["surface"])
    lf.pack(side="left", padx=20)
    tk.Label(lf, text="⬡", bg=C["surface"], fg=C["accent"],
             font=("Helvetica Neue", 22, "bold")).pack(side="left")
    tk.Label(lf, text="  IFControll", bg=C["surface"], fg=C["text"],
             font=("Helvetica Neue", 17, "bold")).pack(side="left")
    tk.Label(hdr, text="Fleet Intelligence Platform  ·  Fulltrack2 API  v3.0",
             bg=C["surface"], fg=C["text_dim"],
             font=("Helvetica Neue", 9)).pack(side="left", padx=8, pady=20)

    rf = tk.Frame(hdr, bg=C["surface"])
    rf.pack(side="right", padx=20)

    mk_theme_btn(rf, root).pack(side="right", padx=8, pady=14)
    mk_refresh_controls(rf, root).pack(side="right", padx=4, pady=14)
    tk.Label(rf, text="  LIVE  ", bg=C["success"], fg=C["bg"],
             font=("Helvetica Neue", 8, "bold"), padx=6, pady=3).pack(side="right", pady=16)

    clk = tk.Label(rf, bg=C["surface"], fg=C["text_dim"], font=("Courier New", 9))
    clk.pack(side="right", padx=12, pady=16)

    def tick():
        clk.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S"))
        root.after(1000, tick)
    tick()


def _apply_notebook_style() -> None:
    """Reaplica o estilo ttk do Notebook com as cores do tema atual."""
    st = ttk.Style()
    st.configure("M.TNotebook", background=C["bg"], borderwidth=0, tabmargins=0)
    st.configure("M.TNotebook.Tab",
                 background=C["surface"], foreground=C["text_dim"],
                 font=("Helvetica Neue", 9), padding=[10, 8], borderwidth=0)
    st.map("M.TNotebook.Tab",
           background=[("selected", C["surface2"]), ("active", C["hover"])],
           foreground=[("selected", C["accent"]),   ("active", C["text"])])


def build_notebook(root: tk.Tk) -> ttk.Notebook:
    global _nb
    _apply_notebook_style()

    nb = ttk.Notebook(root, style="M.TNotebook")
    nb.pack(fill="both", expand=True)
    _nb = nb

    for name, cls in TAB_REGISTRY:
        nb.add(cls(nb), text=name)
    return nb


def build_footer(root: tk.Tk) -> None:
    import sys
    tk.Frame(root, bg=C["border"], height=1).pack(fill="x")
    ft = tk.Frame(root, bg=C["surface"], height=24)
    ft.pack(fill="x")
    ft.pack_propagate(False)
    tk.Label(ft, text="IFControll v3.0  ·  Powered by Fulltrack2 REST API  ·  © 2025",
             bg=C["surface"], fg=C["text_dim"],
             font=("Helvetica Neue", 8)).pack(side="left", padx=16, pady=4)
    tk.Label(ft,
             text=f"Python {sys.version.split()[0]}  ·  Tkinter  ·  Ctrl+C para copiar  ·  "
                  f"Clique direito no cabeçalho para ordenar",
             bg=C["surface"], fg=C["text_dim"],
             font=("Helvetica Neue", 8)).pack(side="right", padx=16, pady=4)


# ── Listener mestre de tema ───────────────────────────────────────────────────

def _on_theme_change() -> None:
    """
    Chamado pelo theme_manager ao trocar de tema.
    1. Reaplica o estilo do Notebook (abas/tabs list).
    2. Percorre TODOS os widgets via winfo_children recursivo — inclusive
       os frames internos de cada aba do Notebook, que ficam "escondidos"
       para o _repaint normal do root.
    """
    if _root is None:
        return

    # 1. Reestiliza o próprio Notebook
    _apply_notebook_style()

    # 2. Repinta a janela raiz (header, footer, frames diretos)
    _repaint(_root)

    # 3. Percorre explicitamente cada aba do Notebook e repinta seu conteúdo
    #    (ttk.Notebook não expõe os frames das abas como filhos do root)
    if _nb is not None:
        for tab_id in _nb.tabs():
            try:
                tab_widget = _nb.nametowidget(tab_id)
                _repaint(tab_widget)
            except Exception:
                pass

    # 4. Atualiza o bg do root
    _root.configure(bg=C["bg"])


register_theme_listener(_on_theme_change)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    root = build_window()
    build_header(root)
    build_notebook(root)
    build_footer(root)

    bind_global_copy(root)
    auto_refresh_loop(root)

    root.mainloop()