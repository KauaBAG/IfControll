"""
tab_nova.py — Sub-aba 2: Nova Manutenção.
"""

import threading
from datetime import datetime
from tkinter import messagebox

import tkinter as tk

from utils.theme_manager import C

from core.api import _cron_post
from ._constants import SITUACOES_PADRAO
from ._helpers import (
    lbl, ent, btn, txtbox, write, make_scrollable,
    to_api_dt, to_api_date, now_ui, safe,
)
from ._widgets import FilterableCombobox


class NovaMixin:
    """
    Mixin com toda a lógica da sub-aba Nova Manutenção.
    Deve ser misturado em TabCronologia.
    """

    def _build_nova(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" ➕ Nova Manutenção ")

        bar = tk.Frame(f, bg=C["surface3"])
        bar.pack(fill="x")
        lbl(bar, "NOVA MANUTENÇÃO", 10, True, C["accent"],
            bg=C["surface3"]).pack(side="left", padx=12, pady=8)

        scroll_wrap = tk.Frame(f, bg=C["bg"])
        scroll_wrap.pack(fill="both", expand=True)
        _, b = make_scrollable(scroll_wrap)
        pad = tk.Frame(b, bg=C["bg"])
        pad.pack(fill="x", padx=20, pady=10)

        # ── Seletor cliente/placa ─────────────────────────────────────────────
        sec = tk.Frame(pad, bg=C["surface3"], highlightthickness=1,
                       highlightbackground=C["border"])
        sec.pack(fill="x", pady=(0, 10))
        lbl(sec, "Buscar placa via Fulltrack (opcional):", 9, True,
            C["accent"], bg=C["surface3"]).pack(anchor="w", padx=8, pady=(6, 2))

        row_nc = tk.Frame(sec, bg=C["surface3"])
        row_nc.pack(fill="x", padx=8, pady=(0, 6))

        lbl(row_nc, "Cliente:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left")
        cb_cli_n = FilterableCombobox(
            row_nc, values=["⏳ Carregando..."], width=30,
            font=("Helvetica Neue", 9),
        )
        cb_cli_n.set("⏳ Carregando...")
        cb_cli_n.pack(side="left", padx=6)
        self._cbs_cliente.append(cb_cli_n)

        lbl(row_nc, "Placa:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=(12, 4))
        cb_placa_n = FilterableCombobox(
            row_nc, values=[], width=14, font=("Helvetica Neue", 9),
        )
        cb_placa_n.pack(side="left", padx=4)

        btn_usar = btn(row_nc, "↓ USAR ESTA PLACA", lambda: None,
                       C["surface2"], C["text_mid"], px=8, py=3)
        btn_usar.pack(side="left", padx=8)

        # ── Campos do formulário ──────────────────────────────────────────────
        # Os campos abaixo são Entry simples; "situacao" é tratado à parte
        # como FilterableCombobox logo após o loop.
        self._nova_fields: dict[str, tk.Entry] = {}

        campos_antes_situ = [
            ("Placa *",          "placa",        True),
            ("ID do Rastreador", "rastreador_id", False),
        ]
        campos_apos_situ = [
            ("Criado Por *",  "criado_por",   True),
            ("Quem Informou", "quem_informou", False),
            ("Onde Está",     "onde_esta",     False),
            ("Categoria",     "categoria",     False),
            ("Técnico",       "prioridade",    False),
            ("Custo (R$)",    "custo",         False),
        ]

        def _add_entry_row(label_txt: str, key: str, obrig: bool):
            row = tk.Frame(pad, bg=C["bg"])
            row.pack(fill="x", pady=3)
            cor = C["accent"] if obrig else C["text_mid"]
            lbl(row, f"{label_txt}:", 9, col=cor, width=20).pack(side="left", anchor="w")
            e = ent(row)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            self._nova_fields[key] = e

        for label_txt, key, obrig in campos_antes_situ:
            _add_entry_row(label_txt, key, obrig)

        # ── Situação — FilterableCombobox ─────────────────────────────────────
        row_situ = tk.Frame(pad, bg=C["bg"])
        row_situ.pack(fill="x", pady=3)
        lbl(row_situ, "Situação *:", 9, col=C["accent"],
            width=20).pack(side="left", anchor="w")

        # Usa as situações padrão + as que já foram carregadas do banco
        situ_values = list(getattr(self, "_situacoes", SITUACOES_PADRAO))
        self._cb_situ_nova = FilterableCombobox(
            row_situ, values=situ_values, width=28,
            font=("Helvetica Neue", 10),
        )
        self._cb_situ_nova.pack(side="left", ipady=2)

        for label_txt, key, obrig in campos_apos_situ:
            _add_entry_row(label_txt, key, obrig)

        self._nova_fields["categoria"].insert(0, "Geral")
        self._nova_fields["prioridade"].insert(0, "Geordano")
        self._nova_fields["custo"].insert(0, "0")

        # ── Callbacks cliente/placa ───────────────────────────────────────────
        def _nova_on_cli(e=None):
            placas = self._placas_do_cliente(cb_cli_n)
            cb_placa_n["values"] = placas
            cb_placa_n.set(placas[0] if placas else "")

        def _nova_usar():
            p = cb_placa_n.get()
            if p:
                f_placa = self._nova_fields["placa"]
                f_placa.delete(0, "end")
                f_placa.insert(0, p.upper())

        cb_cli_n.bind("<<ComboboxSelected>>", _nova_on_cli)
        cb_placa_n.bind("<<ComboboxSelected>>", lambda _e: _nova_usar())
        btn_usar.bind("<Button-1>", lambda _e: _nova_usar())

        # ── Datas ─────────────────────────────────────────────────────────────
        row_dt = tk.Frame(pad, bg=C["bg"])
        row_dt.pack(fill="x", pady=3)
        lbl(row_dt, "Data cadastro:", 9, col=C["text_mid"],
            width=20).pack(side="left", anchor="w")
        self.e_data_cad = ent(row_dt, width=22)
        self.e_data_cad.pack(side="left", ipady=4)
        self.e_data_cad.insert(0, now_ui())

        row_prev = tk.Frame(pad, bg=C["bg"])
        row_prev.pack(fill="x", pady=3)
        lbl(row_prev, "Previsão (dd/mm/aaaa):", 9, col=C["text_mid"],
            width=20).pack(side="left", anchor="w")
        self.e_previsao = ent(row_prev, width=22)
        self.e_previsao.pack(side="left", ipady=4)

        # ── Textos livres ─────────────────────────────────────────────────────
        lbl(pad, "Observações:", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_obs = tk.Text(
            pad, height=3, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_obs.pack(fill="x")

        lbl(pad, "Status inicial (texto inicial do histórico):", 9,
            col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_status_ini = tk.Text(
            pad, height=4, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_status_ini.pack(fill="x")

        fr_res, self.res_nova = txtbox(pad, 3)
        fr_res.pack(fill="x", pady=(10, 0))

        btns = tk.Frame(pad, bg=C["bg"])
        btns.pack(fill="x", pady=16)
        btn(btns, "💾 CADASTRAR MANUTENÇÃO",
            self._criar_manutencao, C["success"]).pack(side="left", padx=4)
        btn(btns, "🗑 LIMPAR CAMPOS",
            self._limpar_nova, C["surface3"], C["text_mid"]).pack(side="left", padx=4)

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _limpar_nova(self):
        for e in self._nova_fields.values():
            e.delete(0, "end")
        self._nova_fields["categoria"].insert(0, "Geral")
        self._nova_fields["prioridade"].insert(0, "Normal")
        self._nova_fields["custo"].insert(0, "0")
        self._cb_situ_nova.set("")
        self.e_previsao.delete(0, "end")
        self.t_obs.delete("1.0", "end")
        self.t_status_ini.delete("1.0", "end")
        self.e_data_cad.delete(0, "end")
        self.e_data_cad.insert(0, now_ui())
        write(self.res_nova, "Campos limpos.", C["text_dim"])

    def _criar_manutencao(self):
        placa      = self._nova_fields["placa"].get().strip().upper()
        situacao   = self._cb_situ_nova.get().strip()          # ← lê do combobox
        criado_por = self._nova_fields["criado_por"].get().strip()

        if not placa or not situacao:
            write(self.res_nova, "⚠ Placa e Situação são obrigatórios.", C["warn"])
            return
        if not criado_por:
            write(self.res_nova, "⚠ Informe quem está criando (Criado Por).", C["warn"])
            return

        custo_txt = (self._nova_fields["custo"].get() or "").strip().replace(",", ".")
        try:
            custo = float(custo_txt) if custo_txt else 0.0
        except ValueError:
            custo = 0.0

        status_ini = self.t_status_ini.get("1.0", "end").strip()

        body: dict = {
            "placa":          placa,
            "rastreador_id":  self._nova_fields["rastreador_id"].get().strip() or None,
            "situacao":       situacao,
            "criado_por":     criado_por,
            "quem_informou":  self._nova_fields["quem_informou"].get().strip() or None,
            "onde_esta":      self._nova_fields["onde_esta"].get().strip() or None,
            "data_cadastro":  to_api_dt(self.e_data_cad.get()) or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "previsao":       to_api_date(self.e_previsao.get()),
            "data_conclusao": None,
            "concluido":      0,
            "categoria":      self._nova_fields["categoria"].get().strip() or "Geral",
            "prioridade":     self._nova_fields["prioridade"].get().strip() or "Normal",
            "custo":          custo,
            "observacoes":    self.t_obs.get("1.0", "end").strip() or None,
            "status_atual":   status_ini or None,
        }

        write(self.res_nova, "⏳ Cadastrando...", C["accent"])

        def task():
            resp, code = _cron_post("criar", body=body)
            if resp.get("status") or code in (200, 201):
                mid = (resp.get("data") or {}).get("id", "?")
                def _ok():
                    write(self.res_nova,
                          f"✔ Manutenção #{mid} cadastrada por {criado_por}!",
                          C["success"])
                    self._limpar_nova()
                    if self.e_placa.get().strip().upper() == placa:
                        self._buscar(reset=True)
                self.after(0, _ok)
            else:
                err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                self.after(0, lambda: write(self.res_nova, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()