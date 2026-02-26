"""
tab_stats.py — Sub-aba 4: Estatísticas.
"""

import threading

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C

from core.api import _cron_get
from ._helpers import lbl, ent, btn, txtbox, write, apply_treeview_style, safe


class StatsMixin:
    """
    Mixin com toda a lógica da sub-aba Estatísticas.
    Deve ser misturado em TabCronologia.
    """

    def _build_stats(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📊 Estatísticas ")

        top = tk.Frame(f, bg=C["bg"])
        top.pack(fill="x", padx=12, pady=10)

        lbl(top, "Placa (opcional):", col=C["text_mid"]).pack(side="left")
        self.e_stats_placa = ent(top, width=14)
        self.e_stats_placa.pack(side="left", padx=6, ipady=4)
        self.e_stats_placa.bind("<Return>", lambda _e: self._carregar_stats())

        btn(top, "📊 CARREGAR STATS", self._carregar_stats,
            C["blue"]).pack(side="left", padx=6)
        btn(top, "🌐 GERAL",
            lambda: (self.e_stats_placa.delete(0, "end"), self._carregar_stats()),
            C["surface3"], C["accent"]).pack(side="left", padx=6)

        self.lb_stats = lbl(top, "", col=C["text_dim"])
        self.lb_stats.pack(side="right")

        # Cards de resumo
        cards = tk.Frame(f, bg=C["bg"])
        cards.pack(fill="x", padx=12, pady=(0, 10))

        self._card_total = lbl(cards, "Total: —",      10, True, C["accent"])
        self._card_conc  = lbl(cards, "Concluídos: —", 10, True, C["success"])
        self._card_pend  = lbl(cards, "Pendentes: —",  10, True, C["warn"])
        self._card_urg   = lbl(cards, "Urgentes: —",   10, True, C["danger"])
        self._card_custo = lbl(cards, "Custo: —",      10, True, C["purple"])
        for w in (self._card_total, self._card_conc, self._card_pend,
                  self._card_urg, self._card_custo):
            w.pack(side="left", padx=10)

        lbl(f, "Por categoria:", 10, True, C["accent"]).pack(
            anchor="w", padx=12, pady=(6, 4)
        )
        apply_treeview_style("CronCat", C["accent"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self.tree_cat = ttk.Treeview(
            inner, columns=("Categoria", "Qtd"), show="headings",
            style="CronCat.Treeview", height=14,
        )
        self.tree_cat.heading("Categoria", text="Categoria", anchor="w")
        self.tree_cat.heading("Qtd",       text="Qtd",       anchor="w")
        self.tree_cat.column("Categoria", width=260, anchor="w", stretch=True)
        self.tree_cat.column("Qtd",       width=120, anchor="w", stretch=False)

        vs = ttk.Scrollbar(inner, orient="vertical", command=self.tree_cat.yview)
        self.tree_cat.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tree_cat.pack(fill="both", expand=True)

        fr, self.res_stats = txtbox(f, 3)
        fr.pack(fill="x", padx=12, pady=(0, 12))

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _abrir_stats_da_placa(self):
        placa = (self.e_placa.get().strip().upper() or self._last_query_placa)
        if placa:
            self.e_stats_placa.delete(0, "end")
            self.e_stats_placa.insert(0, placa)
        for i, tab in enumerate(self._nb.tabs()):
            if "Estat" in self._nb.tab(tab, "text"):
                self._nb.select(i)
                break
        self._carregar_stats()

    def _carregar_stats(self):
        placa = self.e_stats_placa.get().strip().upper()
        self.lb_stats.config(text="⏳ Carregando...")
        write(self.res_stats, "⏳ Buscando estatísticas...", C["accent"])

        def task():
            params = {"placa": placa} if placa else {}
            resp   = _cron_get("stats", params)

            if not resp.get("status"):
                def _err():
                    self.lb_stats.config(text="✖ Erro")
                    write(self.res_stats, f"✖ {resp.get('error', 'Erro')}", C["danger"])
                self.after(0, _err)
                return

            d = resp.get("data", {}) or {}
            try:
                custo_fmt = (
                    f"R$ {float(d.get('custo_total') or 0):,.2f}"
                    .replace(",", "X").replace(".", ",").replace("X", ".")
                )
            except (TypeError, ValueError):
                custo_fmt = f"R$ {d.get('custo_total', 0)}"

            categorias = d.get("por_categoria") or []
            label_txt  = f"✔ OK ({'placa ' + placa if placa else 'geral'})"

            def _update():
                self._card_total.config(text=f"Total: {d.get('total', 0)}")
                self._card_conc.config( text=f"Concluídos: {d.get('concluidos', 0)}")
                self._card_pend.config( text=f"Pendentes: {d.get('pendentes', 0)}")
                self._card_urg.config(  text=f"Urgentes: {d.get('urgentes', 0)}")
                self._card_custo.config(text=f"Custo: {custo_fmt}")

                for r in self.tree_cat.get_children():
                    self.tree_cat.delete(r)
                for cat in categorias:
                    self.tree_cat.insert("", "end", values=(
                        safe(cat.get("categoria")),
                        safe(cat.get("qtd")),
                    ))

                self.lb_stats.config(text=label_txt)
                write(self.res_stats, "✔ Estatísticas carregadas.", C["success"])

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()
