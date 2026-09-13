"""
tabs/dashboard.py
Aba 1 — Dashboard em tempo real da frota.

Correções em relação à versão anterior:
  • Thread-safety: _render() agora é sempre chamado via self.after(0, ...)
    pela main thread — elimina crash silencioso por acesso a widgets fora
    da main thread.
  • Auto-refresh unificado: removido o _loop() interno redundante; o único
    mecanismo de auto-refresh é o externo (auto_refresh_register), evitando
    chamadas duplicadas ao servidor.
  • Placeholder robusto: FocusOut restaura o texto quando o campo fica vazio,
    evitando que o placeholder suma permanentemente.
  • Stat cards com recolor de tema: _stat_card() registra um listener de
    tema para cada card, corrigindo labels que ficavam com cores antigas ao
    trocar de tema.
  • Stat cards via dict: self._stats guarda referências por chave, eliminando
    6 atributos soltos (s_total, s_on, …) e tornando _update_stats() limpo.
  • Lógica separada da UI: _aggregate() calcula os totais, _render() só
    exibe — cada um faz uma coisa.
  • _is_searching(): helper centralizado para saber se há filtro ativo,
    evitando comparação com string literal em dois lugares.
  • mk_export_btn movido para após a criação de self.tree (corrige
    AttributeError na inicialização — self.tree ainda não existia quando
    _build_controls() era chamado).
"""

import re
import threading
import tkinter as tk

from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, auto_refresh_register
from core import get_all_events, safe_int, safe_float, safe_str
from widgets import lbl, ent, btn, mk_tree, mk_export_btn

# ── Colunas da tree ───────────────────────────────────────────────────────────
_COLS = (
    "Placa", "Veículo", "Motorista", "Cliente",
    "Ign.", "Vel. km/h", "GPS", "Satél.", "Bat.%", "Volt.", "Última GPS",
)
_WIDTHS = (80, 130, 130, 130, 70, 80, 70, 60, 60, 70, 150)

# ── Definição dos stat cards (chave, label, cor) ──────────────────────────────
_STAT_DEFS = [
    ("total",  "VEÍCULOS",    C["blue"]),
    ("on",     "IGN ON",      C["green"]),
    ("off",    "IGN OFF",     C["text_mid"]),
    ("no_gps", "SEM GPS",     C["danger"]),
    ("vmax",   "MAIS RÁPIDO", C["yellow"]),
    ("upd",    "ATUALIZADO",  C["text_dim"]),
]

_PLACEHOLDER = "Filtrar placa / motorista..."


class TabDashboard(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._data: list = []
        self._stats: dict[str, tk.Label] = {}  # chave → label de valor
        self._build()
        auto_refresh_register("dashboard", self.refresh)
        register_theme_listener(self._reapply_tags)
        self.after(300, self.refresh)

    # ── Recolor de tema ───────────────────────────────────────────────────────

    def _reapply_tags(self):
        self.tree.tag_configure("on",  background=C["surface2"])
        self.tree.tag_configure("off", background=C["surface3"])

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_stat_bar()
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        # _build_controls() retorna o frame ctrl para que mk_export_btn
        # seja adicionado somente após self.tree existir
        ctrl = self._build_controls()

        self.tree = mk_tree(self, _COLS, _WIDTHS, "Dash", C["accent"], 18)
        self._reapply_tags()

        # self.tree já existe aqui — sem AttributeError
        mk_export_btn(ctrl, self.tree).pack(side="right", padx=4)

    def _build_stat_bar(self):
        sf = tk.Frame(self, bg=C["surface"])
        sf.pack(fill="x")
        for key, label, col in _STAT_DEFS:
            self._stats[key] = self._stat_card(sf, label, "—", col)

    def _build_controls(self) -> tk.Frame:
        """Constrói a barra de controles. Retorna o frame para uso posterior."""
        ctrl = tk.Frame(self, bg=C["bg"])
        ctrl.pack(fill="x", padx=10, pady=6)

        btn(ctrl, "⟳  ATUALIZAR", self.refresh, C["accent"]).pack(side="left")

        self.se = ent(ctrl, w=24)
        self.se.pack(side="left", padx=(20, 4), ipady=4)
        self._placeholder_set()
        self.se.bind("<FocusIn>",    lambda e: self._placeholder_clear())
        self.se.bind("<FocusOut>",   lambda e: self._placeholder_restore())
        self.se.bind("<KeyRelease>", lambda e: self._filter())

        btn(ctrl, "LIMPAR", self._clear_filter, C["surface3"], C["text"]).pack(side="left", padx=4)
        return ctrl

    # ── Stat card ─────────────────────────────────────────────────────────────

    def _stat_card(self, parent, label: str, val: str, col: str) -> tk.Label:
        """Cria um card de estatística e registra recolor de tema."""
        f = tk.Frame(parent, bg=C["surface"])
        f.pack(side="left", padx=18, pady=8)

        title_lbl = tk.Label(
            f, text=label, bg=C["surface"], fg=C["text_dim"],
            font=("Helvetica Neue", 7, "bold"),
        )
        title_lbl.pack()

        val_lbl = tk.Label(
            f, text=val, bg=C["surface"], fg=col,
            font=("Helvetica Neue", 14, "bold"),
        )
        val_lbl.pack()

        def recolor():
            try:
                f.config(bg=C["surface"])
                title_lbl.config(bg=C["surface"], fg=C["text_dim"])
                val_lbl.config(bg=C["surface"])
            except Exception:
                pass

        register_theme_listener(recolor)
        return val_lbl

    # ── Placeholder ───────────────────────────────────────────────────────────

    def _is_searching(self) -> bool:
        return self.se.get() not in ("", _PLACEHOLDER)

    def _placeholder_set(self):
        self.se.delete(0, "end")
        self.se.insert(0, _PLACEHOLDER)
        self.se.config(fg=C["text_dim"])

    def _placeholder_clear(self):
        if self.se.get() == _PLACEHOLDER:
            self.se.delete(0, "end")
            self.se.config(fg=C["text"])

    def _placeholder_restore(self):
        if self.se.get().strip() == "":
            self._placeholder_set()

    def _clear_filter(self):
        self._placeholder_set()
        self._render(self._data)

    # ── Lógica de negócio (separada da UI) ───────────────────────────────────

    @staticmethod
    def _aggregate(data: list) -> dict:
        """Calcula totais a partir dos dados brutos. Não toca em widgets."""
        on = off = no_gps = vmax = 0
        for ev in data:
            ign = safe_int(ev.get("ras_eve_ignicao", 0))
            gps = safe_int(ev.get("ras_eve_gps_status", 0))
            vel = safe_int(ev.get("ras_eve_velocidade", 0))
            if ign:
                on += 1
            else:
                off += 1
            if not gps:
                no_gps += 1
            vmax = max(vmax, vel)
        return {
            "total":  len(data),
            "on":     on,
            "off":    off,
            "no_gps": no_gps,
            "vmax":   vmax,
        }

    # ── Renderização (sempre na main thread) ─────────────────────────────────

    def _update_stats(self, agg: dict):
        self._stats["total"].config( text=str(agg["total"]))
        self._stats["on"].config(    text=str(agg["on"]))
        self._stats["off"].config(   text=str(agg["off"]))
        self._stats["no_gps"].config(text=str(agg["no_gps"]))
        self._stats["vmax"].config(  text=f"{agg['vmax']} km/h")
        self._stats["upd"].config(   text=now_str())

    def _row(self, ev: dict):
        ign = safe_int(ev.get("ras_eve_ignicao", 0))
        self.tree.insert("", "end", values=(
            safe_str(ev.get("ras_vei_placa")),
            safe_str(ev.get("ras_vei_veiculo")),
            safe_str(ev.get("ras_mot_nome")),
            safe_str(ev.get("ras_cli_desc")),
            "🟢 ON" if ign else "⚫ OFF",
            safe_int(ev.get("ras_eve_velocidade", 0)),
            "✓ OK"  if safe_int(ev.get("ras_eve_gps_status", 0)) else "✗ FALHA",
            safe_int(ev.get("ras_eve_satelites", 0)),
            f"{safe_int(ev.get('ras_eve_porc_bat_backup', 100))}%",
            f"{safe_float(ev.get('ras_eve_voltagem', 0)):.1f}V",
            safe_str(ev.get("ras_eve_data_gps")),
        ), tags=("on" if ign else "off",))

    def _render(self, data: list):
        """Limpa e repopula a tree + atualiza stat cards. Deve rodar na main thread."""
        for r in self.tree.get_children():
            self.tree.delete(r)
        for ev in data:
            self._row(ev)
        self._update_stats(self._aggregate(data))

    def _filter(self):
        """Filtra a tree pelo texto do campo de busca sem novo fetch."""
        if not self._is_searching():
            self._render(self._data)
            return
        q = re.sub(r"[^A-Z0-9]", "", self.se.get().upper())
        for r in self.tree.get_children():
            self.tree.delete(r)
        for ev in self._data:
            placa = re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_vei_placa", "")).upper())
            nome  = re.sub(r"[^A-Z0-9]", "", str(ev.get("ras_mot_nome",  "")).upper())
            if q in placa or q in nome:
                self._row(ev)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        """
        Busca dados em thread separada e agenda _on_data() na main thread.
        Nunca chama widgets diretamente do thread filho.
        """
        def task():
            data = get_all_events()
            self.after(0, lambda: self._on_data(data))

        threading.Thread(target=task, daemon=True).start()

    def _on_data(self, data: list):
        """Callback da main thread após fetch concluído."""
        self._data = data
        if self._is_searching():
            self._filter()
        else:
            self._render(data)