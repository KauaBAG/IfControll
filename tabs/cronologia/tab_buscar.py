"""
tab_buscar.py — Sub-aba 1: Buscar / Lista de Manutenções.
"""

import csv as csv_mod
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C
from widgets.alert_colors import _ac

from core.api import _cron_get, _cron_put, _cron_delete, _cron_post
from ._constants import TREE_COLS, TREE_WIDTHS, CSV_COLS
from ._helpers import (
    lbl, btn, txtbox, write, apply_treeview_style,
    fmt_dt, fmt_date, safe,
)
from ._widgets import FilterableCombobox


class BuscarMixin:
    """
    Mixin com toda a lógica da sub-aba Buscar / Lista.
    Deve ser misturado em TabCronologia, que provê:
      - self._nb, self._clientes, self._cli_placas
      - self._cbs_cliente, self._limit, self._offset
      - self._last_query_placa, self._last_query_situ
      - self._last_total, self._last_rows
      - self._situacoes
      - self._placas_do_cliente()
      - self._carregar_clientes_fulltrack()
    """

    # ── Construção da aba ─────────────────────────────────────────────────────

    def _build_buscar(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 🔍 Buscar / Lista ")

        # Seletor cliente → placa
        row_cli = tk.Frame(f, bg=C["surface3"])
        row_cli.pack(fill="x", padx=8, pady=(6, 2))

        lbl(row_cli, "Cliente:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=(8, 4))

        cb_cli_b = FilterableCombobox(
            row_cli, values=["⏳ Carregando..."], width=34,
            font=("Helvetica Neue", 9),
        )
        cb_cli_b.set("⏳ Carregando...")
        cb_cli_b.pack(side="left", padx=4)
        self._cbs_cliente.append(cb_cli_b)

        lbl(row_cli, "Placa:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=(12, 4))

        cb_placa_cli_b = FilterableCombobox(
            row_cli, values=[], width=14, font=("Helvetica Neue", 9),
        )
        cb_placa_cli_b.pack(side="left", padx=4)

        def _on_cli_b(e=None):
            placas = self._placas_do_cliente(cb_cli_b)
            cb_placa_cli_b["values"] = placas
            if placas:
                cb_placa_cli_b.set(placas[0])
                self.e_placa.delete(0, "end")
                self.e_placa.insert(0, placas[0])
            else:
                cb_placa_cli_b.set("")

        def _on_placa_cli_b(e=None):
            p = cb_placa_cli_b.get()
            if p:
                self.e_placa.delete(0, "end")
                self.e_placa.insert(0, p)

        cb_cli_b.bind("<<ComboboxSelected>>", _on_cli_b)
        cb_placa_cli_b.bind("<<ComboboxSelected>>", _on_placa_cli_b)
        btn(row_cli, "⟳ RECARREGAR",
            self._carregar_clientes_fulltrack,
            C["surface2"], C["text_mid"], px=8, py=3).pack(side="right", padx=8)

        # Filtros
        ctrl = tk.Frame(f, bg=C["bg"])
        ctrl.pack(fill="x", padx=8, pady=(4, 2))

        lbl(ctrl, "Placa:", col=C["text_mid"]).pack(side="left")
        from ._helpers import ent
        self.e_placa = ent(ctrl, width=14)
        self.e_placa.pack(side="left", padx=6, ipady=4)
        self.e_placa.bind("<Return>", lambda _e: self._buscar(reset=True))

        lbl(ctrl, "Concluído:", col=C["text_mid"]).pack(side="left", padx=(8, 2))
        self.cb_situ = ttk.Combobox(ctrl, values=["Todos", "Abertos", "Concluídos"],
                                    width=12, state="readonly")
        self.cb_situ.set("Todos")
        self.cb_situ.pack(side="left", padx=4)

        lbl(ctrl, "Por página:", col=C["text_mid"]).pack(side="left", padx=(8, 2))
        self.cb_limit = ttk.Combobox(ctrl, values=["25", "50", "100", "200"],
                                     width=6, state="readonly")
        self.cb_limit.set(str(self._limit))
        self.cb_limit.pack(side="left", padx=4)

        btn(ctrl, "🔍 BUSCAR",
            lambda: self._buscar(reset=True), C["accent"]).pack(side="left", padx=6)
        btn(ctrl, "📋 VER TODAS",
            self._listar_placas, C["surface3"], C["accent"]).pack(side="left", padx=4)
        btn(ctrl, "🗂 POR SITUAÇÃO",
            self._popup_situacao, C["purple"]).pack(side="left", padx=4)

        self.lb_busca = lbl(ctrl, "", col=C["text_dim"])
        self.lb_busca.pack(side="right")

        # Paginação
        nav = tk.Frame(f, bg=C["surface3"])
        nav.pack(fill="x", padx=8, pady=(4, 4))

        btn(nav, "⏮ Primeira", self._pag_first, C["surface2"], C["text"]).pack(side="left", padx=4)
        btn(nav, "◀ Anterior", self._pag_prev,  C["surface2"], C["text"]).pack(side="left", padx=4)
        btn(nav, "Próxima ▶",  self._pag_next,  C["surface2"], C["text"]).pack(side="left", padx=4)

        self.lb_page = lbl(nav, "Página: —", 9, col=C["text_mid"], bg=C["surface3"])
        self.lb_page.pack(side="left", padx=10)

        self.lb_situ_ativa = lbl(nav, "", 9, col=C["purple"], bg=C["surface3"])
        self.lb_situ_ativa.pack(side="left", padx=6)

        btn(nav, "📊 STATS",
            self._abrir_stats_da_placa, C["blue"]).pack(side="right", padx=4)
        btn(nav, "📥 CSV (Página)",
            lambda: self._exportar_csv("pagina"),
            C["surface2"], C["text_mid"]).pack(side="right", padx=4)
        btn(nav, "📥 CSV (Tudo)",
            lambda: self._exportar_csv("tudo"),
            C["surface2"], C["text_mid"]).pack(side="right", padx=4)

        # Árvore
        apply_treeview_style("Cron", C["accent"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True, padx=8)

        self.tree = ttk.Treeview(inner, columns=TREE_COLS,
                                 show="headings", style="Cron.Treeview", height=13)
        for col, w in zip(TREE_COLS, TREE_WIDTHS):
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=w, anchor="w", stretch=True)

        vs = ttk.Scrollbar(inner, orient="vertical",   command=self.tree.yview)
        hs = ttk.Scrollbar(inner, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right",  fill="y")
        hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        self._recolor_tree()
        self.tree.bind("<Double-1>", lambda _e: self._ver_selecionada())

        # Ações rápidas
        act = tk.Frame(f, bg=C["surface3"])
        act.pack(fill="x", padx=8, pady=4)

        lbl(act, "Ação rápida:", 8, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=8)
        btn(act, "👁 DETALHES",   self._ver_selecionada,      C["accent"]).pack(side="left", padx=4)
        btn(act, "✏ EDITAR",      self._editar_selecionada,   C["warn"]).pack(side="left", padx=4)
        btn(act, "➕ ADD STATUS", self._add_status_popup,     C["purple"]).pack(side="left", padx=4)
        btn(act, "✔ CONCLUIR",    self._concluir_selecionada, C["success"]).pack(side="left", padx=4)
        btn(act, "🗑 DELETAR",    self._deletar_selecionada,  C["danger"]).pack(side="left", padx=4)

    def _recolor_tree(self):
        apply_treeview_style("Cron", C["accent"])
        try:
            self.tree.tag_configure("aberto",    background=_ac("ok"))
            self.tree.tag_configure("concluido",
                background=_ac("al2") if C["mode"] == "dark" else "#E8F5E9")
            self.tree.tag_configure("urgente",   background=_ac("crit"))
            self.tree.tag_configure("normal",    background=C["surface2"])
        except Exception:
            pass

    # ── Popup situação ────────────────────────────────────────────────────────

    def _popup_situacao(self):
        win = tk.Toplevel(self)
        win.title("Filtrar por Situação")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.grab_set()

        lbl(win, "Selecione a situação:", 11, True, C["accent"]).pack(
            anchor="w", padx=16, pady=(16, 8)
        )

        grid = tk.Frame(win, bg=C["bg"])
        grid.pack(padx=16, pady=(0, 8))

        def _escolher(situ: str):
            win.destroy()
            self._last_query_situ = situ
            self.lb_situ_ativa.config(text=f"Situação: {situ}")
            self._buscar_por_situacao(situ, reset=True)

        for i, situ in enumerate(self._situacoes):
            is_outros = situ.lower() == "outros"
            b = tk.Label(
                grid, text=situ,
                bg=C["warn"] if is_outros else C["surface3"],
                fg=C["bg"]   if is_outros else C["accent"],
                font=("Helvetica Neue", 10, "bold"),
                padx=20, pady=10, cursor="hand2", relief="flat", width=18,
            )
            b.grid(row=i // 2, column=i % 2, padx=6, pady=4, sticky="ew")
            b.bind("<Button-1>", lambda _e, s=situ: _escolher(s))

        tk.Frame(win, bg=C["border"], height=1).pack(fill="x", padx=16, pady=(4, 0))
        row_bot = tk.Frame(win, bg=C["bg"])
        row_bot.pack(padx=16, pady=12, anchor="e")
        btn(row_bot, "✖ LIMPAR FILTRO",
            lambda: (win.destroy(), self._limpar_filtro_situacao()),
            C["surface3"], C["text_mid"]).pack(side="left", padx=6)
        btn(row_bot, "FECHAR", win.destroy,
            C["surface2"], C["text_mid"]).pack(side="left")

    def _limpar_filtro_situacao(self):
        self._last_query_situ = ""
        self.lb_situ_ativa.config(text="")
        if self._last_query_placa:
            self._buscar(reset=True)

    # ── Busca principal ───────────────────────────────────────────────────────

    def _buscar(self, reset: bool = False):
        placa = self.e_placa.get().strip().upper()
        if not placa:
            messagebox.showwarning("Atenção", "Informe a placa para buscar.")
            return

        try:
            self._limit = int(self.cb_limit.get().strip())
        except (ValueError, AttributeError):
            self._limit = 50

        if reset:
            self._offset = 0

        self._last_query_placa = placa
        self.lb_busca.config(text="⏳ Buscando...")

        situ = self.cb_situ.get().strip()
        concluido = None
        if situ == "Abertos":
            concluido = 0
        elif situ == "Concluídos":
            concluido = 1

        limit  = self._limit
        offset = self._offset
        situacao_filtro = self._last_query_situ or None

        def task():
            params: dict = {"placa": placa, "limit": limit, "offset": offset}
            if concluido is not None:
                params["concluido"] = concluido
            if situacao_filtro:
                params["situacao"] = situacao_filtro

            resp = _cron_get("listar", params)
            if not resp.get("status"):
                self.after(0, lambda: (
                    self.lb_busca.config(text="✖ Erro na busca"),
                    messagebox.showerror("Erro", resp.get("error") or "Erro ao listar")
                ))
                return

            data  = resp.get("data", {}) or {}
            rows  = data.get("registros", []) or []
            total = int(data.get("total") or len(rows))
            tree_rows = self._montar_tree_rows(rows)
            page  = (offset // max(1, limit)) + 1
            pages = max(1, (total + limit - 1) // limit)

            def _update():
                for r in self.tree.get_children():
                    self.tree.delete(r)
                for tag, values in tree_rows:
                    self.tree.insert("", "end", tags=(tag,), values=values)
                self._last_total = total
                self._last_rows  = rows
                self.lb_page.config(text=f"Página: {page}/{pages}  |  Total: {total}")
                self.lb_busca.config(text=f"{len(rows)} registro(s) na página")

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()

    def _buscar_por_situacao(self, situacao: str, reset: bool = True):
        try:
            self._limit = int(self.cb_limit.get().strip())
        except (ValueError, AttributeError):
            self._limit = 50

        if reset:
            self._offset = 0

        self.lb_busca.config(text="⏳ Buscando por situação...")

        situ_conc = self.cb_situ.get().strip()
        concluido = None
        if situ_conc == "Abertos":
            concluido = 0
        elif situ_conc == "Concluídos":
            concluido = 1

        limit  = self._limit
        offset = self._offset
        placa  = self.e_placa.get().strip().upper() or None

        def task():
            params: dict = {"situacao": situacao, "limit": limit, "offset": offset}
            if placa:
                params["placa"] = placa
            if concluido is not None:
                params["concluido"] = concluido

            resp = _cron_get("listar", params)
            if not resp.get("status"):
                self.after(0, lambda: (
                    self.lb_busca.config(text="✖ Erro na busca"),
                    messagebox.showerror("Erro", resp.get("error") or "Erro ao listar")
                ))
                return

            data  = resp.get("data", {}) or {}
            rows  = data.get("registros", []) or []
            total = int(data.get("total") or len(rows))
            self._last_rows  = rows
            self._last_total = total
            tree_rows = self._montar_tree_rows(rows)
            page  = (offset // max(1, limit)) + 1
            pages = max(1, (total + limit - 1) // limit)

            def _update():
                for r in self.tree.get_children():
                    self.tree.delete(r)
                for tag, values in tree_rows:
                    self.tree.insert("", "end", tags=(tag,), values=values)
                self._last_total = total
                self.lb_page.config(text=f"Página: {page}/{pages}  |  Total: {total}")
                self.lb_busca.config(text=f"{len(rows)} registro(s) — situação: {situacao}")

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()

    # ── Paginação ─────────────────────────────────────────────────────────────

    def _pag_first(self):
        if not self._last_query_placa and not self._last_query_situ:
            return
        self._offset = 0
        self._pag_dispatch()

    def _pag_prev(self):
        if not self._last_query_placa and not self._last_query_situ:
            return
        self._offset = max(0, self._offset - self._limit)
        self._pag_dispatch()

    def _pag_next(self):
        if not self._last_query_placa and not self._last_query_situ:
            return
        nxt = self._offset + self._limit
        if self._last_total and nxt >= self._last_total:
            return
        self._offset = nxt
        self._pag_dispatch()

    def _pag_dispatch(self):
        if self._last_query_situ and not self._last_query_placa:
            self._buscar_por_situacao(self._last_query_situ, reset=False)
        else:
            self._buscar(reset=False)

    # ── Ver todas as placas ───────────────────────────────────────────────────

    def _listar_placas(self):
        self.lb_busca.config(text="⏳ Carregando placas...")
        self.e_placa.delete(0, "end")
        self._last_query_placa = ""
        self._last_query_situ  = ""
        self.lb_situ_ativa.config(text="")

        def task():
            resp = _cron_get("placas")
            if not resp.get("status"):
                self.after(0, lambda: (
                    self.lb_busca.config(text="✖ Erro"),
                    messagebox.showerror("Erro", resp.get("error") or "Erro")
                ))
                return

            rows = resp.get("data") or []
            tree_rows = []
            for p in rows:
                placa      = safe(p.get("placa"))
                registros  = p.get("registros", 0)
                pendentes  = p.get("pendentes", 0)
                concluidos = p.get("concluidos", 0)
                ultima     = fmt_dt(p.get("ultima_manutencao"))
                tree_rows.append((
                    "—", placa, "—",
                    f"Registros: {registros}  |  Pendentes: {pendentes}  |  Concluídos: {concluidos}",
                    ultima, "—", "—", "—", "—", "—", "—", "—", "—", "—",
                    f"{pendentes}P",
                ))

            def _update():
                for r in self.tree.get_children():
                    self.tree.delete(r)
                for vals in tree_rows:
                    self.tree.insert("", "end", tags=("normal",), values=vals)
                self.lb_busca.config(text=f"{len(rows)} placa(s) com manutenções")
                self.lb_page.config(text="Página: —")

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()

    # ── Seleção ───────────────────────────────────────────────────────────────

    def _get_selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um registro.")
            return None
        values = self.tree.item(sel[0])["values"]
        if not values or str(values[0]) == "—":
            messagebox.showwarning("Atenção", "Selecione uma manutenção (não uma placa).")
            return None
        try:
            return int(values[0])
        except (TypeError, ValueError):
            return None

    def _ver_selecionada(self):
        mid = self._get_selected_id()
        if mid is None:
            return
        self._selected_id = mid
        self._carregar_detalhe(mid)
        self._ir_aba_detalhe()

    def _editar_selecionada(self):
        self._ver_selecionada()

    def _ir_aba_detalhe(self):
        for i, tab in enumerate(self._nb.tabs()):
            if "Detalhe" in self._nb.tab(tab, "text"):
                self._nb.select(i)
                break

    # ── Ações rápidas da lista ────────────────────────────────────────────────

    def _concluir_selecionada(self):
        mid = self._get_selected_id()
        if mid is None:
            return
        if not messagebox.askyesno("Confirmar", f"Marcar #{mid} como CONCLUÍDA?"):
            return

        def task():
            resp, code = _cron_put(
                f"concluir/{mid}",
                body={"data_conclusao": datetime.now().strftime("%Y-%m-%d"),
                      "quem_informou": "Sistema"},
            )
            if resp.get("status") or code == 200:
                self.after(0, lambda: self._buscar(reset=False))
            else:
                err = resp.get("error") or f"Falha HTTP {code}"
                self.after(0, lambda: messagebox.showerror("Erro", err))

        threading.Thread(target=task, daemon=True).start()

    def _deletar_selecionada(self):
        mid = self._get_selected_id()
        if mid is None:
            return
        if not messagebox.askyesno("Confirmar",
                                   f"Deletar permanentemente a manutenção #{mid}?"):
            return

        def task():
            resp, code = _cron_delete(f"deletar/{mid}")
            if resp.get("status") or code in (200, 204):
                self.after(0, lambda: self._buscar(reset=False))
            else:
                err = resp.get("error") or f"Falha HTTP {code}"
                self.after(0, lambda: messagebox.showerror("Erro", err))

        threading.Thread(target=task, daemon=True).start()

    def _add_status_popup(self):
        mid = self._get_selected_id()
        if mid is None:
            return

        win = tk.Toplevel(self)
        win.title(f"Adicionar Status — #{mid}")
        win.configure(bg=C["bg"])
        win.geometry("520x340")
        win.grab_set()

        lbl(win, f"Adicionar status — manutenção #{mid}", 11, True,
            C["accent"]).pack(anchor="w", padx=12, pady=(12, 6))
        lbl(win, "Autor:", 9, col=C["text_mid"]).pack(anchor="w", padx=12)

        from ._helpers import ent as _ent
        e_aut = _ent(win)
        e_aut.pack(fill="x", padx=12, ipady=4)
        e_aut.insert(0, "Sistema")

        lbl(win, "Texto:", 9, col=C["text_mid"]).pack(anchor="w", padx=12, pady=(10, 2))
        t = tk.Text(
            win, height=6, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        t.pack(fill="both", expand=True, padx=12)

        fr, res = txtbox(win, 2)
        fr.pack(fill="x", padx=12, pady=(8, 4))

        def enviar():
            texto = t.get("1.0", "end").strip()
            autor = e_aut.get().strip() or "Sistema"
            if not texto:
                write(res, "⚠ Escreva o texto.", C["warn"])
                return
            write(res, "⏳ Enviando...", C["accent"])

            def task():
                resp, code = _cron_post(f"add_status/{mid}",
                                        body={"texto": texto, "autor": autor})
                if resp.get("status") or code in (200, 201):
                    def _ok():
                        write(res, "✔ Status adicionado!", C["success"])
                        if self._last_query_placa:
                            self._buscar(reset=False)
                    self.after(0, _ok)
                else:
                    err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                    self.after(0, lambda: write(res, err, C["danger"]))

            threading.Thread(target=task, daemon=True).start()

        row = tk.Frame(win, bg=C["bg"])
        row.pack(padx=12, pady=8, anchor="e")
        btn(row, "➕ ADICIONAR", enviar, C["purple"]).pack(side="left", padx=6)
        btn(row, "FECHAR", win.destroy, C["surface2"], C["text_mid"]).pack(side="left")

    # ── Exportar CSV ──────────────────────────────────────────────────────────

    def _exportar_csv(self, modo: str = "pagina"):
        placa = (self.e_placa.get().strip().upper() or self._last_query_placa).strip()

        if modo == "pagina" and not self._last_rows:
            messagebox.showinfo("Exportar", "Nenhum dado na página atual.")
            return
        if modo == "tudo" and not placa and not self._last_query_situ:
            messagebox.showinfo("Exportar", "Informe a placa ou filtre por situação antes de exportar.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            initialfile=f"cronologia_{modo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return

        def _write_rows(writer, regs):
            for m in regs:
                writer.writerow([safe(m.get(c), "") for c in CSV_COLS])

        if modo == "pagina":
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                    w = csv_mod.writer(fh, delimiter=";")
                    w.writerow(CSV_COLS)
                    _write_rows(w, self._last_rows)
                messagebox.showinfo("Exportar", f"Arquivo salvo:\n{path}")
            except OSError as exc:
                messagebox.showerror("Exportar", str(exc))
            return

        situ_conc = self.cb_situ.get().strip()
        concluido_filter = None
        if situ_conc == "Abertos":
            concluido_filter = 0
        elif situ_conc == "Concluídos":
            concluido_filter = 1
        situacao_filter = self._last_query_situ or None

        def task():
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                    writer = csv_mod.writer(fh, delimiter=";")
                    writer.writerow(CSV_COLS)
                    limit = 200
                    offset = 0
                    total  = None
                    while True:
                        params: dict = {"limit": limit, "offset": offset}
                        if placa:
                            params["placa"] = placa
                        if concluido_filter is not None:
                            params["concluido"] = concluido_filter
                        if situacao_filter:
                            params["situacao"] = situacao_filter
                        resp = _cron_get("listar", params)
                        if not resp.get("status"):
                            self.after(0, lambda: messagebox.showerror(
                                "Exportar", resp.get("error", "Erro na API")))
                            return
                        data  = resp.get("data", {}) or {}
                        regs  = data.get("registros", []) or []
                        total = int(data.get("total") or 0)
                        if not regs:
                            break
                        _write_rows(writer, regs)
                        offset += limit
                        if total and offset >= total:
                            break
                self.after(0, lambda: messagebox.showinfo(
                    "Exportar", f"CSV completo salvo:\n{path}"))
            except OSError as exc:
                self.after(0, lambda: messagebox.showerror("Exportar", str(exc)))

        threading.Thread(target=task, daemon=True).start()

    # ── Montar linhas da árvore ───────────────────────────────────────────────

    def _montar_tree_rows(self, rows: list) -> list[tuple]:
        tree_rows: list[tuple] = []
        for m in rows:
            conc = int(m.get("concluido") or 0)
            tag  = "concluido" if conc else "aberto"

            if not conc:
                try:
                    dt_str = str(m.get("data_cadastro") or m.get("created_at") or "")[:19]
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    if (datetime.now() - dt).days > 7 and not m.get("previsao"):
                        tag = "urgente"
                except ValueError:
                    pass

            sa = safe(m.get("status_atual"))
            if len(sa) > 60:
                sa = sa[:60] + "…"

            try:
                custo_fmt = f"{float(m.get('custo') or 0):.2f}"
            except (TypeError, ValueError):
                custo_fmt = safe(m.get("custo"))

            dt_cad = m.get("data_cadastro") or m.get("created_at")
            tree_rows.append((tag, (
                safe(m.get("id")),
                safe(m.get("placa")),
                safe(m.get("rastreador_id")),
                safe(m.get("situacao")),
                fmt_dt(dt_cad),
                safe(m.get("criado_por")),
                safe(m.get("quem_informou")),
                safe(m.get("onde_esta")),
                sa,
                safe(m.get("categoria"), "Geral"),
                safe(m.get("prioridade"), "Normal"),
                custo_fmt,
                fmt_date(m.get("previsao")),
                fmt_date(m.get("data_conclusao")),
                "✔" if conc else "✗",
            )))
        return tree_rows
