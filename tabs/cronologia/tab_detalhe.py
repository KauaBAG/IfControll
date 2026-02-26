"""
tab_detalhe.py — Sub-aba 3: Detalhe / Edição de Manutenção.
"""

import threading
from datetime import datetime
from tkinter import messagebox

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C

from core.api import _cron_get, _cron_put, _cron_post, _cron_delete
from ._helpers import (
    lbl, ent, btn, txtbox, write, make_scrollable,
    apply_treeview_style, fmt_dt, fmt_date, to_api_dt, to_api_date, safe,
)


class DetalheMixin:
    """
    Mixin com toda a lógica da sub-aba Detalhe / Edição.
    Deve ser misturado em TabCronologia.
    """

    def _build_detalhe(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📄 Detalhe / Edição ")

        paned = ttk.Panedwindow(f, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=4, pady=4)

        # Painel esquerdo: formulário
        left_cont = tk.Frame(paned, bg=C["bg"], width=540)
        left_cont.pack_propagate(False)
        paned.add(left_cont, weight=0)
        _, left = make_scrollable(left_cont)
        lp = tk.Frame(left, bg=C["bg"])
        lp.pack(fill="x", padx=8, pady=6)

        # Painel direito: histórico
        right = tk.Frame(paned, bg=C["bg"])
        paned.add(right, weight=1)

        lbl(lp, "DADOS DA MANUTENÇÃO", 10, True, C["accent"]).pack(anchor="w", pady=(0, 6))

        self._edit_fields: dict[str, tk.Entry] = {}
        edit_campos = [
            ("ID",               "id",             True),
            ("Placa",            "placa",          True),
            ("ID do Rastreador", "rastreador_id",  False),
            ("Situação",         "situacao",       False),
            ("Criado Por",       "criado_por",     False),
            ("Quem Informou",    "quem_informou",  False),
            ("Onde Está",        "onde_esta",      False),
            ("Categoria",        "categoria",      False),
            ("Técnico",          "prioridade",     False),
            ("Custo (R$)",       "custo",          False),
            ("Data Cadastro",    "data_cadastro",  False),
            ("Previsão",         "previsao",       False),
            ("Data Conclusão",   "data_conclusao", False),
        ]
        for label, key, readonly in edit_campos:
            row = tk.Frame(lp, bg=C["bg"])
            row.pack(fill="x", pady=2)
            lbl(row, f"{label}:", 9, col=C["text_mid"], width=18).pack(side="left", anchor="w")
            e = ent(row)
            if readonly:
                e.config(state="readonly", fg=C["text_dim"])
            e.pack(side="left", fill="x", expand=True, ipady=4)
            self._edit_fields[key] = e

        row_conc = tk.Frame(lp, bg=C["bg"])
        row_conc.pack(fill="x", pady=4)
        self._conc_var = tk.BooleanVar()
        tk.Checkbutton(
            row_conc, text="Concluído", variable=self._conc_var,
            bg=C["bg"], fg=C["text"], activebackground=C["bg"],
            selectcolor=C["surface3"], font=("Helvetica Neue", 10),
        ).pack(side="left")

        lbl(lp, "Observações:", 9, col=C["text_mid"]).pack(anchor="w", pady=(8, 2))
        self.t_edit_obs = tk.Text(
            lp, height=3, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_edit_obs.pack(fill="x")

        lbl(lp, "Novo status (opcional — adiciona ao histórico):", 9,
            col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_novo_status = tk.Text(
            lp, height=4, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_novo_status.pack(fill="x")

        lbl(lp, "Autor do novo status:", 9, col=C["text_mid"]).pack(anchor="w", pady=(8, 2))
        self.e_autor = ent(lp)
        self.e_autor.pack(fill="x", ipady=4)

        tk.Frame(lp, bg=C["border"], height=1).pack(fill="x", pady=10)

        row_b1 = tk.Frame(lp, bg=C["bg"])
        row_b1.pack(fill="x", pady=(0, 6))
        btn(row_b1, "💾 SALVAR",
             self._salvar_edicao, C["success"]).pack(side="left", padx=(0, 6))
        btn(row_b1, "➕ ADD STATUS",
             self._add_status_from_editor, C["purple"], C["text"]).pack(side="left", padx=6)

        row_b2 = tk.Frame(lp, bg=C["bg"])
        row_b2.pack(fill="x", pady=(0, 10))
        btn(row_b2, "✔ CONCLUIR",
             self._concluir_do_editor, C["accent"]).pack(side="left", padx=(0, 6))
        btn(row_b2, "🗑 DELETAR",
             self._deletar_atual, C["danger"]).pack(side="left", padx=6)

        fr_res, self.res_edit = txtbox(lp, 4)
        fr_res.pack(fill="x", pady=(0, 16))

        # Histórico
        lbl(right, "HISTÓRICO DE STATUS", 10, True, C["accent"]).pack(
            anchor="w", padx=8, pady=(6, 4)
        )
        apply_treeview_style("CronSt", C["green"])
        inner_r = tk.Frame(right, bg=C["bg"])
        inner_r.pack(fill="both", expand=True, padx=8)

        st_cols = ("Data", "Autor", "Texto")
        st_ws   = (150, 130, 520)
        self.tree_status = ttk.Treeview(
            inner_r, columns=st_cols, show="headings",
            style="CronSt.Treeview", height=20,
        )
        for c, w in zip(st_cols, st_ws):
            self.tree_status.heading(c, text=c, anchor="w")
            self.tree_status.column(c, width=w, anchor="w", stretch=True)

        vs2 = ttk.Scrollbar(inner_r, orient="vertical", command=self.tree_status.yview)
        self.tree_status.configure(yscrollcommand=vs2.set)
        vs2.pack(side="right", fill="y")
        self.tree_status.pack(fill="both", expand=True)

    # ── Carregar detalhe ──────────────────────────────────────────────────────

    def _carregar_detalhe(self, mid: int):
        self.after(0, lambda: write(self.res_edit, "⏳ Carregando...", C["accent"]))

        def task():
            resp   = _cron_get(f"buscar/{mid}")
            resp_h = _cron_get(f"historico/{mid}")

            if not resp.get("status"):
                err = f"✖ {resp.get('error', 'Erro ao carregar')}"
                self.after(0, lambda: write(self.res_edit, err, C["danger"]))
                return

            m         = resp.get("data") or {}
            historico = resp_h.get("data") or [] if resp_h.get("status") else []

            def _update():
                def se(key: str, val: str, readonly: bool = False):
                    e = self._edit_fields.get(key)
                    if not e:
                        return
                    cur_state = str(e.cget("state"))
                    if cur_state == "readonly":
                        e.config(state="normal")
                    e.delete(0, "end")
                    e.insert(0, val)
                    if readonly:
                        e.config(state="readonly", fg=C["text_dim"])

                se("id",    safe(m.get("id"), ""),    readonly=True)
                se("placa", safe(m.get("placa"), ""), readonly=True)
                se("rastreador_id",  safe(m.get("rastreador_id"), ""))
                se("situacao",       safe(m.get("situacao"), ""))
                se("criado_por",     safe(m.get("criado_por"), ""))
                se("quem_informou",  safe(m.get("quem_informou"), ""))
                se("onde_esta",      safe(m.get("onde_esta"), ""))
                se("categoria",      safe(m.get("categoria"), "Geral"))
                se("prioridade",     safe(m.get("prioridade"), "Normal"))

                try:
                    se("custo", f"{float(m.get('custo') or 0):.2f}")
                except (TypeError, ValueError):
                    se("custo", "0")

                dt_cad = m.get("data_cadastro") or m.get("created_at", "")
                se("data_cadastro",  fmt_dt(dt_cad).replace("—", ""))
                se("previsao",       fmt_date(m.get("previsao")).replace("—", ""))
                se("data_conclusao", fmt_date(m.get("data_conclusao")).replace("—", ""))

                self._conc_var.set(bool(int(m.get("concluido") or 0)))
                self.t_edit_obs.delete("1.0", "end")
                obs = safe(m.get("observacoes"), "").replace("—", "")
                if obs:
                    self.t_edit_obs.insert("1.0", obs)
                self.t_novo_status.delete("1.0", "end")

                for r in self.tree_status.get_children():
                    self.tree_status.delete(r)
                for upd in historico:
                    data_upd = upd.get("criado_em") or upd.get("created_at", "")
                    self.tree_status.insert("", "end", values=(
                        fmt_dt(data_upd),
                        safe(upd.get("autor")),
                        safe(upd.get("texto")),
                    ))

                write(self.res_edit, f"✔ Manutenção #{mid} carregada.", C["success"])

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()

    # ── Salvar edição ─────────────────────────────────────────────────────────

    def _salvar_edicao(self):
        mid = self._selected_id
        if not mid:
            write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"])
            return

        novo_st = self.t_novo_status.get("1.0", "end").strip()
        autor   = self.e_autor.get().strip() or "Sistema"

        custo_txt = (self._edit_fields["custo"].get() or "").strip().replace(",", ".")
        try:
            custo = float(custo_txt) if custo_txt else 0.0
        except ValueError:
            custo = 0.0

        body: dict = {
            "situacao":       self._edit_fields["situacao"].get().strip(),
            "rastreador_id":  self._edit_fields["rastreador_id"].get().strip() or None,
            "criado_por":     self._edit_fields["criado_por"].get().strip() or "Sistema",
            "quem_informou":  self._edit_fields["quem_informou"].get().strip() or None,
            "onde_esta":      self._edit_fields["onde_esta"].get().strip() or None,
            "categoria":      self._edit_fields["categoria"].get().strip() or "Geral",
            "prioridade":     self._edit_fields["prioridade"].get().strip() or "Normal",
            "observacoes":    self.t_edit_obs.get("1.0", "end").strip() or None,
            "data_cadastro":  to_api_dt(self._edit_fields["data_cadastro"].get()),
            "previsao":       to_api_date(self._edit_fields["previsao"].get()),
            "data_conclusao": to_api_date(self._edit_fields["data_conclusao"].get()),
            "concluido":      1 if self._conc_var.get() else 0,
            "custo":          custo,
        }

        if novo_st:
            body["novo_status"]  = novo_st
            body["status_atual"] = novo_st
            body["criado_por"]   = autor

        write(self.res_edit, "⏳ Salvando...", C["accent"])

        def task():
            resp, code = _cron_put(f"atualizar/{mid}", body)
            if resp.get("status") or code in (200, 201):
                def _ok():
                    write(self.res_edit, f"✔ Manutenção #{mid} atualizada!", C["success"])
                    self._carregar_detalhe(mid)
                    if self._last_query_placa:
                        self._buscar(reset=False)
                self.after(0, _ok)
            else:
                err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                self.after(0, lambda: write(self.res_edit, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()

    # ── Adicionar status ──────────────────────────────────────────────────────

    def _add_status_from_editor(self):
        mid = self._selected_id
        if not mid:
            write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"])
            return
        texto = self.t_novo_status.get("1.0", "end").strip()
        if not texto:
            write(self.res_edit, "⚠ Escreva um texto de status.", C["warn"])
            return
        autor = self.e_autor.get().strip() or "Sistema"
        write(self.res_edit, "⏳ Adicionando...", C["accent"])

        def task():
            resp, code = _cron_post(f"add_status/{mid}",
                                    body={"texto": texto, "autor": autor})
            if resp.get("status") or code in (200, 201):
                def _ok():
                    write(self.res_edit, f"✔ Status adicionado! (#{mid})", C["success"])
                    self.t_novo_status.delete("1.0", "end")
                    self._carregar_detalhe(mid)
                self.after(0, _ok)
            else:
                err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                self.after(0, lambda: write(self.res_edit, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()

    # ── Concluir / Deletar ────────────────────────────────────────────────────

    def _concluir_do_editor(self):
        mid = self._selected_id
        if not mid:
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
                def _ok():
                    self._carregar_detalhe(mid)
                    if self._last_query_placa:
                        self._buscar(reset=False)
                self.after(0, _ok)
            else:
                err = resp.get("error") or f"Falha HTTP {code}"
                self.after(0, lambda: messagebox.showerror("Erro", err))

        threading.Thread(target=task, daemon=True).start()

    def _deletar_atual(self):
        mid = self._selected_id
        if not mid:
            write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"])
            return
        if not messagebox.askyesno("Confirmar",
                                   f"Deletar permanentemente a manutenção #{mid}?"):
            return

        def task():
            resp, code = _cron_delete(f"deletar/{mid}")
            if resp.get("status") or code in (200, 204):
                def _ok():
                    write(self.res_edit, f"✔ Manutenção #{mid} deletada.", C["success"])
                    self._selected_id = None
                    for key, e in self._edit_fields.items():
                        if str(e.cget("state")) == "readonly":
                            e.config(state="normal")
                        e.delete(0, "end")
                        if key in ("id", "placa"):
                            e.config(state="readonly", fg=C["text_dim"])
                    self.t_edit_obs.delete("1.0", "end")
                    self.t_novo_status.delete("1.0", "end")
                    for r in self.tree_status.get_children():
                        self.tree_status.delete(r)
                    if self._last_query_placa:
                        self._buscar(reset=False)
                self.after(0, _ok)
            else:
                err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                self.after(0, lambda: write(self.res_edit, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()
