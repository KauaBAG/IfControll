"""
tab_cronologia.py — IFControll v3.5

Ponto de entrada da aba Cronologia de Manutenções.
A classe TabCronologia orquestra os cinco mixins, cada um responsável
por uma sub-aba:

  BuscarMixin   → sub-aba Buscar / Lista
  NovaMixin     → sub-aba Nova Manutenção
  DetalheMixin  → sub-aba Detalhe / Edição
  StatsMixin    → sub-aba Estatísticas
  ConfigMixin   → sub-aba Configuração

Toda lógica de UI e negócio vive nos mixins; este arquivo apenas
inicializa o estado compartilhado e dispara os carregamentos iniciais.
"""

import threading

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from core.api import get_clients_all, get_all_events, _cron_get

from ._constants import SITUACOES_PADRAO
from ._helpers import safe, apply_treeview_style
from ._widgets import FilterableCombobox

from .tab_buscar  import BuscarMixin
from .tab_nova    import NovaMixin
from .tab_detalhe import DetalheMixin
from .tab_stats   import StatsMixin
from .tab_config  import ConfigMixin


class TabCronologia(BuscarMixin, NovaMixin, DetalheMixin, StatsMixin, ConfigMixin,
                    tk.Frame):
    """
    Aba de Cronologia de Manutenções para o IFControll.

    Herda de todos os mixins de sub-abas e de tk.Frame.
    O estado compartilhado entre as sub-abas é inicializado aqui:

      _selected_id         ID da manutenção atualmente carregada no editor
      _limit / _offset     Paginação da lista
      _last_total          Total de registros da última busca
      _last_rows           Linhas da última página carregada
      _last_query_placa    Última placa buscada (para re-buscar após ações)
      _last_query_situ     Última situação filtrada
      _clientes            Cache de clientes Fulltrack
      _cli_placas          Mapa clienteID → lista de placas
      _cbs_cliente         Referências a todos os FilterableCombobox de cliente
      _situacoes           Lista de situações (padrão + banco)
    """

    def __init__(self, master):
        tk.Frame.__init__(self, master, bg=C["bg"])

        # ── Estado compartilhado ──────────────────────────────────────────────
        self._selected_id: int | None = None
        self._limit  = 50
        self._offset = 0
        self._last_total = 0
        self._last_rows: list = []
        self._last_query_placa = ""
        self._last_query_situ  = ""

        self._clientes: list   = []
        self._cli_placas: dict = {}
        self._cbs_cliente: list = []

        self._situacoes: list[str] = list(SITUACOES_PADRAO)

        # ── Build ─────────────────────────────────────────────────────────────
        self._build()

        # ── Tema e carregamentos iniciais ─────────────────────────────────────
        register_theme_listener(self._recolor)
        self.after(300, self._carregar_clientes_fulltrack)
        self.after(500, self._carregar_situacoes)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._nb = nb
        self._build_buscar(nb)
        self._build_nova(nb)
        self._build_detalhe(nb)
        self._build_stats(nb)
        self._build_config(nb)

    # ── Tema ──────────────────────────────────────────────────────────────────

    def _recolor(self):
        apply_treeview_style("Cron",    C["accent"])
        apply_treeview_style("CronSt",  C["green"])
        apply_treeview_style("CronCat", C["accent"])
        self._recolor_tree()

    # ── Carregamentos iniciais ────────────────────────────────────────────────

    def _carregar_situacoes(self):
        """Carrega situações do banco via API e mescla com as padrão."""
        def task():
            resp = _cron_get("situacoes")
            if resp.get("status") and resp.get("data"):
                self._situacoes = resp["data"]
            if "Outros" not in self._situacoes:
                self._situacoes.append("Outros")
        threading.Thread(target=task, daemon=True).start()

    def _carregar_clientes_fulltrack(self):
        def task():
            try:
                clientes = get_clients_all()
                clientes_sorted = sorted(
                    clientes,
                    key=lambda c: str(c.get("ras_cli_desc") or "").lower(),
                )
                eventos = get_all_events()
                mapa: dict[str, set] = {}
                for ev in eventos:
                    cid   = str(ev.get("ras_vei_id_cli") or ev.get("ras_cli_id") or "").strip()
                    placa = str(ev.get("ras_vei_placa") or "").strip()
                    if cid and placa:
                        mapa.setdefault(cid, set()).add(placa.upper())

                self._clientes   = clientes_sorted
                self._cli_placas = {k: sorted(v) for k, v in mapa.items()}
                self.after(0, self._atualizar_combos_clientes)
            except Exception as exc:
                print(f"[Cronologia] Erro ao carregar clientes: {exc}")

        threading.Thread(target=task, daemon=True).start()

    def _atualizar_combos_clientes(self):
        nomes = ["— Selecione um cliente —"] + [
            f"{safe(c.get('ras_cli_desc'))} (ID {safe(c.get('ras_cli_id'))})"
            for c in self._clientes
        ]
        for cb in self._cbs_cliente:
            try:
                atual = cb.get()
                cb["values"] = nomes
                if atual in ("", "⏳ Carregando...", "— Selecione um cliente —"):
                    cb.set(nomes[0])
            except Exception:
                pass

    def _placas_do_cliente(self, cb_cliente: FilterableCombobox) -> list:
        val = cb_cliente.get()
        if "ID " not in val:
            return []
        try:
            cid = val.split("ID ")[-1].rstrip(")")
        except Exception:
            return []
        placas = list(self._cli_placas.get(cid, []))
        if not placas:
            try:
                seen: set = set()
                for ev in get_all_events():
                    ec = str(ev.get("ras_vei_id_cli") or ev.get("ras_cli_id") or "").strip()
                    p  = str(ev.get("ras_vei_placa") or "").strip().upper()
                    if ec == cid and p and p not in seen:
                        seen.add(p)
                        placas.append(p)
            except Exception:
                pass
        return sorted(placas)
