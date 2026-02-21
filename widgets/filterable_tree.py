"""
widgets/filterable_tree.py
FilterableTree: Treeview com barra de filtro, ordenação por coluna,
cópia Ctrl+C e menu de contexto integrados.
Todos os widgets internos se recolorem automaticamente ao trocar de tema.
"""

import tkinter as tk
from tkinter import ttk
from utils.theme_manager import C, register_theme_listener
from .tree import apply_tree_style, export_tree


class FilterableTree:
    """
    Wrapper que adiciona filtro de texto, ordenação por coluna (asc/desc),
    cópia Ctrl+C e menu de contexto a qualquer Treeview.

    Uso:
        ft = FilterableTree(parent, cols, ws, sname, hcol, h)
        ft.load([(values_tuple, tag_str), ...])
        ft.tag_configure("tag", background="#...")
        ft.tree  →  ttk.Treeview raw
    """

    def __init__(self, parent, cols, ws, sname: str = "B", hcol=None, h: int = 12):
        self._all_data: list = []
        self._sort_col = None
        self._sort_asc = True
        self._cols     = cols
        self._sname    = sname
        self._hcol_key = None

        # Guarda a chave de C para a cor do cabeçalho
        if hcol is not None:
            for k, v in C.items():
                if v == hcol:
                    self._hcol_key = k
                    break
            if self._hcol_key is None:
                self._hcol_key = hcol  # cor literal

        # ── Container principal ───────────────────────────────────────────
        self.frame = tk.Frame(parent, bg=C["bg"])
        self.frame.pack(fill="both", expand=True)

        # ── Barra de filtro ───────────────────────────────────────────────
        self._fb = tk.Frame(self.frame, bg=C["surface3"], pady=3)
        self._fb.pack(fill="x", pady=(0, 1))

        self._ico_lbl = tk.Label(
            self._fb, text="🔍", bg=C["surface3"], fg=C["accent"],
            font=("Helvetica Neue", 9),
        )
        self._ico_lbl.pack(side="left", padx=(6, 2))

        self._filter_var = tk.StringVar()
        self._filter_var.trace("w", self._on_filter_change)
        self._fe = tk.Entry(
            self._fb, textvariable=self._filter_var,
            bg=C["surface2"], fg=C["text"],
            insertbackground=C["accent"],
            relief="flat", font=("Consolas", 9), width=28,
            highlightthickness=1, highlightbackground=C["border"],
            highlightcolor=C["accent"],
        )
        self._fe.pack(side="left", padx=4, ipady=3)

        self._col_lbl = tk.Label(
            self._fb, text="Coluna:", bg=C["surface3"], fg=C["text_dim"],
            font=("Helvetica Neue", 8),
        )
        self._col_lbl.pack(side="left", padx=(8, 2))

        self._col_var = tk.StringVar(value="Todas")
        self._col_cb  = ttk.Combobox(
            self._fb, textvariable=self._col_var,
            values=["Todas"] + list(cols),
            state="readonly", width=14, font=("Helvetica Neue", 8),
        )
        self._col_cb.pack(side="left", padx=2)
        self._col_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        self._sort_lbl = tk.Label(
            self._fb, text="  Ordenar:", bg=C["surface3"], fg=C["text_dim"],
            font=("Helvetica Neue", 8),
        )
        self._sort_lbl.pack(side="left", padx=(8, 2))

        self._sort_var = tk.StringVar(value="—")
        self._sort_cb  = ttk.Combobox(
            self._fb, textvariable=self._sort_var,
            values=["—"] + list(cols),
            state="readonly", width=14, font=("Helvetica Neue", 8),
        )
        self._sort_cb.pack(side="left", padx=2)
        self._sort_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_sort())

        self._asc_btn = tk.Label(
            self._fb, text="↑ ASC",
            bg=C["surface2"], fg=C["accent"],
            font=("Helvetica Neue", 8, "bold"),
            padx=6, pady=3, cursor="hand2",
        )
        self._asc_btn.pack(side="left", padx=2)
        self._asc_btn.bind("<Button-1>", lambda e: self._toggle_dir())

        self._count_lbl = tk.Label(
            self._fb, text="", bg=C["surface3"], fg=C["text_dim"],
            font=("Helvetica Neue", 8),
        )
        self._count_lbl.pack(side="right", padx=8)

        self._btn_clear = tk.Label(
            self._fb, text="✕ LIMPAR", bg=C["surface2"], fg=C["text_mid"],
            font=("Helvetica Neue", 8), padx=6, pady=3, cursor="hand2",
        )
        self._btn_clear.pack(side="right", padx=2)
        self._btn_clear.bind("<Button-1>", lambda e: self._clear_filter())

        # ── Treeview ──────────────────────────────────────────────────────
        style = apply_tree_style(sname, hcol)
        self._inner = tk.Frame(self.frame, bg=C["bg"])
        self._inner.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            self._inner, columns=cols, show="headings", style=style, height=h,
        )
        for c, w in zip(cols, ws):
            self.tree.heading(c, text=c, anchor="w",
                              command=lambda _c=c: self._header_click(_c))
            self.tree.column(c, width=w, anchor="w", stretch=True)

        vs = ttk.Scrollbar(self._inner, orient="vertical",   command=self.tree.yview)
        hs = ttk.Scrollbar(self._inner, orient="horizontal",  command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right",  fill="y")
        hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # ── Menu de contexto ──────────────────────────────────────────────
        self._menu_click_pos = None
        self._menu = None
        self._build_menu()

        # ── Binds ─────────────────────────────────────────────────────────
        self.tree.bind("<Control-c>", self._copy_selection)
        self.tree.bind("<Control-C>", self._copy_selection)
        self.tree.bind("<Button-3>",  self._context_menu)

        # ── Registro de recoloração automática ────────────────────────────
        register_theme_listener(self._recolor)

    # ── Recoloração de tema ───────────────────────────────────────────────────

    def _recolor(self):
        """Atualiza todas as cores internas ao trocar de tema."""
        try:
            self.frame.config(bg=C["bg"])
            self._inner.config(bg=C["bg"])
            self._fb.config(bg=C["surface3"])
            self._ico_lbl.config(bg=C["surface3"], fg=C["accent"])
            self._col_lbl.config(bg=C["surface3"], fg=C["text_dim"])
            self._sort_lbl.config(bg=C["surface3"], fg=C["text_dim"])
            self._count_lbl.config(bg=C["surface3"], fg=C["text_dim"])
            self._fe.config(
                bg=C["surface2"], fg=C["text"],
                insertbackground=C["accent"],
                highlightbackground=C["border"],
                highlightcolor=C["accent"],
            )
            self._asc_btn.config(bg=C["surface2"], fg=C["accent"])
            self._btn_clear.config(bg=C["surface2"], fg=C["text_mid"])
            # Reaplica estilo do Treeview
            hcol = C[self._hcol_key] if self._hcol_key and self._hcol_key in C else self._hcol_key
            apply_tree_style(self._sname, hcol)
            # Reconstrói menu com novas cores
            self._build_menu()
            # Atualiza estilos dos Combobox via ttk
            self._style_comboboxes()
        except Exception:
            pass

    def _style_comboboxes(self):
        """Estiliza os Combobox internos via ttk.Style."""
        s = ttk.Style()
        s.configure("FT.TCombobox",
                     fieldbackground=C["surface2"],
                     background=C["surface3"],
                     foreground=C["text"],
                     selectbackground=C["accent2"],
                     selectforeground=C["text"],
                     arrowcolor=C["accent"])
        for cb in (self._col_cb, self._sort_cb):
            cb.configure(style="FT.TCombobox")

    def _build_menu(self):
        """Cria (ou recria) o menu de contexto com as cores atuais do tema."""
        if self._menu is not None:
            try:
                self._menu.destroy()
            except Exception:
                pass
        self._menu = tk.Menu(
            self.tree, tearoff=0,
            bg=C["surface3"], fg=C["text"],
            activebackground=C["accent2"], activeforeground=C["text"],
            font=("Helvetica Neue", 9),
        )
        self._menu.add_command(label="📋  Copiar linha",       command=self._copy_row)
        self._menu.add_command(label="📋  Copiar célula",      command=self._copy_cell_from_menu)
        self._menu.add_command(label="📋  Copiar tudo (CSV)",  command=self._copy_all_csv)
        self._menu.add_separator()
        self._menu.add_command(label="📥  Exportar CSV",       command=lambda: export_tree(self.tree))
        self._menu.add_separator()
        self._menu.add_command(label="🔃  Limpar filtros",     command=self._clear_filter)

    # ── Ordenação ─────────────────────────────────────────────────────────────

    def _header_click(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._sort_var.set(col)
        self._asc_btn.config(text="↑ ASC" if self._sort_asc else "↓ DESC")
        self._apply_filter()

    def _toggle_dir(self):
        self._sort_asc = not self._sort_asc
        self._asc_btn.config(text="↑ ASC" if self._sort_asc else "↓ DESC")
        self._apply_filter()

    def _apply_sort(self):
        col = self._sort_var.get()
        self._sort_col = None if col == "—" else col
        self._apply_filter()

    # ── Filtro ────────────────────────────────────────────────────────────────

    def _on_filter_change(self, *_):
        self._apply_filter()

    def _clear_filter(self):
        self._filter_var.set("")
        self._sort_var.set("—")
        self._col_var.set("Todas")
        self._sort_col = None
        self._sort_asc = True
        self._asc_btn.config(text="↑ ASC")
        self._apply_filter()

    def _apply_filter(self):
        q          = self._filter_var.get().lower().strip()
        filter_col = self._col_var.get()
        cols       = self._cols

        if not q:
            filtered = list(self._all_data)
        else:
            filtered = []
            for (vals, tags) in self._all_data:
                if filter_col == "Todas":
                    haystack = " ".join(str(v).lower() for v in vals)
                else:
                    try:
                        idx      = list(cols).index(filter_col)
                        haystack = str(vals[idx]).lower()
                    except ValueError:
                        haystack = " ".join(str(v).lower() for v in vals)
                if q in haystack:
                    filtered.append((vals, tags))

        if self._sort_col and self._sort_col in cols:
            idx = list(cols).index(self._sort_col)

            def sort_key(x):
                val = x[0][idx] if idx < len(x[0]) else ""
                s   = str(val).replace("—","").replace("km/h","").replace("%","").replace("V","").strip()
                try:    return (0, float(s))
                except: return (1, s.lower())

            filtered.sort(key=sort_key, reverse=not self._sort_asc)

        for r in self.tree.get_children():
            self.tree.delete(r)
        for (vals, tags) in filtered:
            self.tree.insert("", "end", values=vals, tags=tags)

        self._count_lbl.config(text=f"{len(filtered)}/{len(self._all_data)}")

    # ── API pública ───────────────────────────────────────────────────────────

    def load(self, data_list: list):
        self._all_data = []
        for item in data_list:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], (tuple, list, str)):
                vals, tags = item
            else:
                vals, tags = item, ()
            if isinstance(tags, str):
                tags = (tags,)
            self._all_data.append((vals, tuple(tags)))
        self._apply_filter()

    def tag_configure(self, tag: str, **kw):
        self.tree.tag_configure(tag, **kw)

    # ── Clipboard ─────────────────────────────────────────────────────────────

    def _copy_selection(self, event=None):
        self._copy_row()

    def _copy_row(self):
        sel = self.tree.selection()
        if not sel:
            return
        lines = ["\t".join(str(v) for v in self.tree.item(i)["values"]) for i in sel]
        self.tree.clipboard_clear()
        self.tree.clipboard_append("\n".join(lines))

    def _copy_cell_from_menu(self):
        sel = self.tree.selection()
        if not sel or self._menu_click_pos is None:
            return
        x, y    = self._menu_click_pos
        col_id  = self.tree.identify_column(x)
        item    = self.tree.identify_row(y)
        if not col_id or not item:
            self._copy_row(); return
        col_idx = int(col_id.replace("#", "")) - 1
        vals    = self.tree.item(item)["values"]
        if 0 <= col_idx < len(vals):
            self.tree.clipboard_clear()
            self.tree.clipboard_append(str(vals[col_idx]))

    def _copy_all_csv(self):
        cols  = [self.tree.heading(c)["text"] for c in self.tree["columns"]]
        rows  = [self.tree.item(r)["values"]  for r in self.tree.get_children()]
        lines = [";".join(str(c) for c in cols)]
        for row in rows:
            lines.append(";".join(str(v) for v in row))
        self.tree.clipboard_clear()
        self.tree.clipboard_append("\n".join(lines))

    def _context_menu(self, event):
        self._menu_click_pos = (event.x, event.y)
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    # ── Delegação para compatibilidade com mk_tree legado ─────────────────────

    def get_children(self):         return self.tree.get_children()
    def delete(self, *a):           return self.tree.delete(*a)
    def insert(self, *a, **kw):     return self.tree.insert(*a, **kw)
    def item(self, *a, **kw):       return self.tree.item(*a, **kw)
    def heading(self, *a, **kw):    return self.tree.heading(*a, **kw)
    def __getitem__(self, k):       return self.tree[k]


def mk_ftree(parent, cols, ws, sname: str = "B", hcol=None, h: int = 12) -> "FilterableTree":
    """Fábrica conveniente — equivalente a FilterableTree(...)."""
    return FilterableTree(parent, cols, ws, sname, hcol, h)