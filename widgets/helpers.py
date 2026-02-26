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

# ─── Formatação de datas ─────────────────────────────────────────────────────

_DT_FMTS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")
_D_FMT   = "%Y-%m-%d"


def fmt_dt(s) -> str:
    if not s or str(s) in ("None", "null", "—"):
        return "—"
    for fmt in _DT_FMTS:
        try:
            return datetime.strptime(str(s)[:19], fmt).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            pass
    return str(s)


def fmt_date(s) -> str:
    if not s or str(s) in ("None", "null", "—"):
        return "—"
    try:
        return datetime.strptime(str(s)[:10], _D_FMT).strftime("%d/%m/%Y")
    except ValueError:
        return str(s)


def to_api_dt(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return s or None


def to_api_date(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s or None


def now_ui() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def safe(v, default: str = "—") -> str:
    s = str(v).strip() if v is not None else ""
    return default if s in ("", "None", "null") else s



def apply_treeview_style(name: str, hcol: str | None = None):
    s = tk.Style()
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

def make_scrollable(parent):
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

    return canvas, inner