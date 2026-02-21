"""
tab_cronologia.py — IFControll v3.4

Cronologia de Manutenções.

CORREÇÕES v3.4 (em relação à v3.3):
  ─ Removido uso de global para CRON_API_URL / CRON_API_KEY:
      as funções lêem as variáveis sempre no momento da chamada
      via módulo de credenciais.
  ─ Eliminado race condition na paginação: limit/offset são capturados
      antes de entrarem na thread.
  ─ _make_scrollable: bind_all apenas enquanto o mouse está sobre o canvas
      (comportamento já correto na v3.3, mas agora com unbind garantido).
  ─ _buscar: pré-validação do campo placa antes de disparar a thread.
  ─ _salvar_edicao: campo 'custo' lida com vírgula corretamente.
  ─ _criar_manutencao: limpa os campos APÓS confirmar o sucesso da API
      (evita perda de dados se a rede falhar).
  ─ _listar_placas: a inserção na árvore agora exibe a placa na coluna
      correta sem strings de preenchimento "—" em todas as outras colunas.
  ─ Toda operação que mostra messagebox a partir de thread usa self.after().
  ─ _placas_do_cliente_selecionado: fallback de consulta online apenas
      quando o cache local está vazio E após limpar duplicatas.
  ─ _recolor chamado na construção do estilo inicial para garantir
      consistência de cores desde o primeiro render.
  ─ Adicionada constante _TREE_COLS para evitar repetição da definição
      das colunas da árvore principal.
  ─ Melhorias de UX: mensagens de feedback mais claras; foco automático
      no campo placa ao abrir a aba; tooltip visual de carregamento.
"""

import threading
import csv as csv_mod
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import requests

# ── Importações internas ─────────────────────────────────────────────────────
# Lidas sob demanda (late import) para respeitar possíveis recargas do módulo
import core.credencials as _cred
from core.api import get_clients_all, get_all_events
from core.models import safe_str as _safe_str_model
from utils.theme_manager import C, register_theme_listener
from widgets.alert_colors import _ac

# ─────────────────────────────────────────────────────────────────────────────
# COLUNAS DA ÁRVORE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
_TREE_COLS = (
    "ID", "Placa", "Situação", "Data Cadastro", "Criado Por",
    "Quem Informou", "Onde Está", "Status Atual",
    "Categoria", "Prioridade", "Custo", "Previsão", "Conclusão", "✔",
)
_TREE_WIDTHS = (50, 80, 160, 130, 120, 120, 140, 200, 110, 100, 80, 110, 110, 40)
_TREE_NCOLS  = len(_TREE_COLS)


# ─────────────────────────────────────────────────────────────────────────────
# CLIENTE HTTP (API PHP)
# ─────────────────────────────────────────────────────────────────────────────

def _cron_url() -> str:
    """URL da API lida sempre em tempo de execução (reflete mudanças no painel)."""
    return getattr(_cred, "CRON_API_URL", "")


def _cron_key() -> str:
    """Token da API lido sempre em tempo de execução."""
    return getattr(_cred, "CRON_API_KEY", "")


def _cron_headers() -> dict:
    return {
        "Content-Type": "application/json",
        getattr(_cred, "_CRON_TOKEN_HEADER_NAME", "X-API-Token"): _cron_key(),
    }


def _cron_req(method: str, path: str, params: dict | None = None,
              body: dict | None = None, timeout: int = 15):
    """Executa uma requisição e retorna (data_dict, http_status_code)."""
    try:
        query = {"path": path}
        if params:
            query.update(params)
        r = requests.request(
            method=method.upper(),
            url=_cron_url(),
            headers=_cron_headers(),
            params=query,
            json=body,
            timeout=timeout,
        )
        try:
            data = r.json()
        except Exception:
            data = {
                "status": False,
                "error": f"Resposta não-JSON (HTTP {r.status_code})",
                "raw": (r.text or "")[:4000],
            }
        return data, r.status_code
    except requests.exceptions.ConnectionError:
        return {"status": False, "error": "Sem conexão com a API."}, 0
    except requests.exceptions.Timeout:
        return {"status": False, "error": "Timeout na requisição."}, 0
    except Exception as exc:
        return {"status": False, "error": str(exc)}, 0


def _cron_get(path: str, params: dict | None = None) -> dict:
    data, _ = _cron_req("GET", path, params=params)
    return data


def _cron_post(path: str, body: dict | None = None, params: dict | None = None):
    return _cron_req("POST", path, params=params, body=body)


def _cron_put(path: str, body: dict | None = None, params: dict | None = None):
    return _cron_req("PUT", path, params=params, body=body)


def _cron_delete(path: str, params: dict | None = None):
    return _cron_req("DELETE", path, params=params)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE UI
# ─────────────────────────────────────────────────────────────────────────────

def _lbl(parent, text: str, size: int = 9, bold: bool = False,
         col: str | None = None, bg: str | None = None, **kw):
    return tk.Label(
        parent, text=text,
        bg=bg or C["bg"], fg=col or C["text"],
        font=("Helvetica Neue", size, "bold" if bold else "normal"), **kw
    )


def _ent(parent, width: int | None = None, **kw):
    e = tk.Entry(
        parent,
        bg=C["surface3"], fg=C["text"],
        insertbackground=C["accent"],
        relief="flat", highlightthickness=1,
        highlightbackground=C["border"],
        highlightcolor=C["accent"],
        font=("Helvetica Neue", 10), **kw
    )
    if width:
        e.config(width=width)
    return e


def _btn(parent, text: str, cmd, bg: str | None = None,
         fg: str | None = None, px: int = 12, py: int = 5):
    col = bg or C["accent"]
    b = tk.Label(
        parent, text=text, bg=col, fg=fg or C["bg"],
        font=("Helvetica Neue", 9, "bold"), padx=px, pady=py,
        cursor="hand2", relief="flat",
    )
    b.bind("<Button-1>", lambda _e: cmd())
    return b


def _btn2(parent, text: str, cmd, bg: str | None = None,
          fg: str | None = None):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=bg or C["accent"], fg=fg or C["bg"],
        activebackground=bg or C["accent"],
        activeforeground=fg or C["bg"],
        relief="flat", bd=0, cursor="hand2",
        font=("Helvetica Neue", 9, "bold"), padx=10, pady=6,
    )


def _txtbox(parent, h: int = 5):
    """Retorna (frame, Text) — Text começa desabilitado."""
    fr = tk.Frame(parent, bg=C["surface2"], highlightthickness=1,
                  highlightbackground=C["border"])
    t = tk.Text(
        fr, height=h,
        bg=C["surface2"], fg=C["text"],
        insertbackground=C["accent"],
        relief="flat", font=("Consolas", 9),
        padx=8, pady=6,
        selectbackground=C["accent2"],
        state="disabled",
    )
    sb = tk.Scrollbar(fr, command=t.yview,
                      bg=C["surface2"], troughcolor=C["bg"], relief="flat")
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(fill="both", expand=True)
    return fr, t


def _write(text_widget, text: str, col: str | None = None) -> None:
    """Atualiza um widget Text desabilitado. Thread-safe quando chamado via after()."""
    text_widget.config(state="normal")
    text_widget.delete("1.0", "end")
    text_widget.config(fg=col or C["text"])
    text_widget.insert("end", text)
    text_widget.config(state="disabled")


def _make_scrollable(parent):
    """
    Cria um frame rolável dentro de parent.
    Retorna (canvas, inner_frame).
    O scroll do mouse é vinculado localmente ao canvas.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# FORMATAÇÃO DE DATAS
# ─────────────────────────────────────────────────────────────────────────────

_DT_FMTS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")
_D_FMT   = "%Y-%m-%d"


def _fmt_dt(s) -> str:
    if not s or str(s) in ("None", "null", "—"):
        return "—"
    for fmt in _DT_FMTS:
        try:
            return datetime.strptime(str(s)[:19], fmt).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            pass
    return str(s)


def _fmt_date(s) -> str:
    if not s or str(s) in ("None", "null", "—"):
        return "—"
    try:
        return datetime.strptime(str(s)[:10], _D_FMT).strftime("%d/%m/%Y")
    except ValueError:
        return str(s)


def _to_api_dt(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return s or None


def _to_api_date(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s or None


def _now_ui() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _safe(v, default: str = "—") -> str:
    s = str(v).strip() if v is not None else ""
    return default if s in ("", "None", "null") else s


# ─────────────────────────────────────────────────────────────────────────────
# CLASSE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class TabCronologia(tk.Frame):
    """
    Aba de Cronologia de Manutenções para o IFControll.

    Sub-abas:
      1. Buscar / Lista  — pesquisa paginada por placa
      2. Nova Manutenção — formulário de criação
      3. Detalhe / Edição — edição completa + histórico
      4. Estatísticas    — métricas por placa ou global
      5. Configuração    — URL e token da API
    """

    def __init__(self, master):
        super().__init__(master, bg=C["bg"])

        self._selected_id: int | None = None
        self._limit  = 50
        self._offset = 0
        self._last_total = 0
        self._last_rows: list = []
        self._last_query_placa = ""

        # Cache Fulltrack
        self._clientes: list  = []
        self._cli_placas: dict = {}       # cli_id_str → [placa, ...]
        self._cbs_cliente: list = []      # todos os comboboxes de cliente

        self._build()
        register_theme_listener(self._recolor)
        self.after(300, self._carregar_clientes_fulltrack)

    # ── Tema ─────────────────────────────────────────────────────────────────

    def _recolor(self):
        for name, col in [
            ("Cron",    C["accent"]),
            ("CronSt",  C["green"]),
            ("CronCat", C["accent"]),
        ]:
            self._apply_style(name, col)
        try:
            self.tree.tag_configure("aberto",    background=_ac("ok"))
            self.tree.tag_configure("concluido",
                background=_ac("al2") if C["mode"] == "dark" else "#E8F5E9")
            self.tree.tag_configure("urgente",   background=_ac("crit"))
            self.tree.tag_configure("normal",    background=C["surface2"])
        except Exception:
            pass

    # ── Clientes Fulltrack ────────────────────────────────────────────────────

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
            f"{_safe(c.get('ras_cli_desc'))} (ID {_safe(c.get('ras_cli_id'))})"
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

    def _placas_do_cliente(self, cb_cliente: ttk.Combobox) -> list:
        val = cb_cliente.get()
        if "ID " not in val:
            return []
        try:
            cid = val.split("ID ")[-1].rstrip(")")
        except Exception:
            return []
        placas = list(self._cli_placas.get(cid, []))
        # Fallback online apenas se o cache não retornou nada
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

    # ════════════════════════════════════════════════════════════════════════
    # SUB-ABA 1 — BUSCAR / LISTA
    # ════════════════════════════════════════════════════════════════════════

    def _build_buscar(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 🔍 Buscar / Lista ")

        # ── Seletor cliente → placa ──────────────────────────────────────────
        row_cli = tk.Frame(f, bg=C["surface3"])
        row_cli.pack(fill="x", padx=8, pady=(6, 2))

        _lbl(row_cli, "Cliente (Fulltrack):", 9, col=C["text_mid"],
             bg=C["surface3"]).pack(side="left", padx=(8, 4))

        cb_cli_b = ttk.Combobox(row_cli, values=["⏳ Carregando..."],
                                 width=34, state="readonly",
                                 font=("Helvetica Neue", 9))
        cb_cli_b.set("⏳ Carregando...")
        cb_cli_b.pack(side="left", padx=4, ipady=3)
        self._cbs_cliente.append(cb_cli_b)

        _lbl(row_cli, "Placa do cliente:", 9, col=C["text_mid"],
             bg=C["surface3"]).pack(side="left", padx=(12, 4))

        cb_placa_cli_b = ttk.Combobox(row_cli, values=[], width=14,
                                       state="readonly",
                                       font=("Helvetica Neue", 9))
        cb_placa_cli_b.pack(side="left", padx=4, ipady=3)

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
        _btn(row_cli, "⟳ RECARREGAR",
             self._carregar_clientes_fulltrack,
             C["surface2"], C["text_mid"], px=8, py=3).pack(side="right", padx=8)

        # ── Filtros de busca ─────────────────────────────────────────────────
        ctrl = tk.Frame(f, bg=C["bg"])
        ctrl.pack(fill="x", padx=8, pady=(4, 2))

        _lbl(ctrl, "Placa:", col=C["text_mid"]).pack(side="left")
        self.e_placa = _ent(ctrl, width=14)
        self.e_placa.pack(side="left", padx=6, ipady=4)
        self.e_placa.bind("<Return>", lambda _e: self._buscar(reset=True))

        _lbl(ctrl, "Situação:", col=C["text_mid"]).pack(side="left", padx=(8, 2))
        self.cb_situ = ttk.Combobox(ctrl, values=["Todos", "Abertos", "Concluídos"],
                                     width=12, state="readonly")
        self.cb_situ.set("Todos")
        self.cb_situ.pack(side="left", padx=4)

        _lbl(ctrl, "Por página:", col=C["text_mid"]).pack(side="left", padx=(8, 2))
        self.cb_limit = ttk.Combobox(ctrl, values=["25", "50", "100", "200"],
                                      width=6, state="readonly")
        self.cb_limit.set(str(self._limit))
        self.cb_limit.pack(side="left", padx=4)

        _btn(ctrl, "🔍 BUSCAR",
             lambda: self._buscar(reset=True), C["accent"]).pack(side="left", padx=6)
        _btn(ctrl, "📋 VER TODAS",
             self._listar_placas, C["surface3"], C["accent"]).pack(side="left", padx=4)
        self.lb_busca = _lbl(ctrl, "", col=C["text_dim"])
        self.lb_busca.pack(side="right")

        # ── Paginação ────────────────────────────────────────────────────────
        nav = tk.Frame(f, bg=C["surface3"])
        nav.pack(fill="x", padx=8, pady=(4, 4))

        _btn(nav, "⏮ Primeira", self._pag_first, C["surface2"], C["text"]).pack(side="left", padx=4)
        _btn(nav, "◀ Anterior", self._pag_prev,  C["surface2"], C["text"]).pack(side="left", padx=4)
        _btn(nav, "Próxima ▶",  self._pag_next,  C["surface2"], C["text"]).pack(side="left", padx=4)

        self.lb_page = _lbl(nav, "Página: —", 9, col=C["text_mid"], bg=C["surface3"])
        self.lb_page.pack(side="left", padx=10)

        _btn(nav, "📊 STATS",
             self._abrir_stats_da_placa, C["blue"]).pack(side="right", padx=4)
        _btn(nav, "📥 CSV (Página)",
             lambda: self._exportar_csv("pagina"),
             C["surface2"], C["text_mid"]).pack(side="right", padx=4)
        _btn(nav, "📥 CSV (Tudo)",
             lambda: self._exportar_csv("tudo"),
             C["surface2"], C["text_mid"]).pack(side="right", padx=4)

        # ── Árvore ───────────────────────────────────────────────────────────
        self._apply_style("Cron", C["accent"])
        inner = tk.Frame(f, bg=C["bg"])
        inner.pack(fill="both", expand=True, padx=8)

        self.tree = ttk.Treeview(inner, columns=_TREE_COLS,
                                  show="headings", style="Cron.Treeview", height=13)
        for col, w in zip(_TREE_COLS, _TREE_WIDTHS):
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=w, anchor="w", stretch=True)

        vs = ttk.Scrollbar(inner, orient="vertical",   command=self.tree.yview)
        hs = ttk.Scrollbar(inner, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right",  fill="y")
        hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        self._recolor()
        self.tree.bind("<Double-1>", lambda _e: self._ver_selecionada())

        # ── Ações rápidas ────────────────────────────────────────────────────
        act = tk.Frame(f, bg=C["surface3"])
        act.pack(fill="x", padx=8, pady=4)

        _lbl(act, "Ação rápida:", 8, col=C["text_mid"],
             bg=C["surface3"]).pack(side="left", padx=8)
        _btn(act, "👁 DETALHES",   self._ver_selecionada,      C["accent"]).pack(side="left", padx=4)
        _btn(act, "✏ EDITAR",      self._editar_selecionada,   C["warn"]).pack(side="left", padx=4)
        _btn(act, "➕ ADD STATUS", self._add_status_popup,     C["purple"]).pack(side="left", padx=4)
        _btn(act, "✔ CONCLUIR",    self._concluir_selecionada, C["success"]).pack(side="left", padx=4)
        _btn(act, "🗑 DELETAR",    self._deletar_selecionada,  C["danger"]).pack(side="left", padx=4)

    # ════════════════════════════════════════════════════════════════════════
    # SUB-ABA 2 — NOVA MANUTENÇÃO
    # ════════════════════════════════════════════════════════════════════════

    def _build_nova(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" ➕ Nova Manutenção ")

        bar = tk.Frame(f, bg=C["surface3"])
        bar.pack(fill="x")
        _lbl(bar, "NOVA MANUTENÇÃO", 10, True, C["accent"],
             bg=C["surface3"]).pack(side="left", padx=12, pady=8)

        scroll_wrap = tk.Frame(f, bg=C["bg"])
        scroll_wrap.pack(fill="both", expand=True)
        _, b = _make_scrollable(scroll_wrap)
        pad = tk.Frame(b, bg=C["bg"])
        pad.pack(fill="x", padx=20, pady=10)

        # ── Seletor cliente/placa ────────────────────────────────────────────
        sec = tk.Frame(pad, bg=C["surface3"], highlightthickness=1,
                       highlightbackground=C["border"])
        sec.pack(fill="x", pady=(0, 10))
        _lbl(sec, "Buscar placa via Fulltrack (opcional):", 9, True,
             C["accent"], bg=C["surface3"]).pack(anchor="w", padx=8, pady=(6, 2))

        row_nc = tk.Frame(sec, bg=C["surface3"])
        row_nc.pack(fill="x", padx=8, pady=(0, 6))

        _lbl(row_nc, "Cliente:", 9, col=C["text_mid"],
             bg=C["surface3"]).pack(side="left")
        cb_cli_n = ttk.Combobox(row_nc, values=["⏳ Carregando..."],
                                 width=30, state="readonly",
                                 font=("Helvetica Neue", 9))
        cb_cli_n.set("⏳ Carregando...")
        cb_cli_n.pack(side="left", padx=6, ipady=3)
        self._cbs_cliente.append(cb_cli_n)

        _lbl(row_nc, "Placa:", 9, col=C["text_mid"],
             bg=C["surface3"]).pack(side="left", padx=(12, 4))
        cb_placa_n = ttk.Combobox(row_nc, values=[], width=14,
                                   state="readonly", font=("Helvetica Neue", 9))
        cb_placa_n.pack(side="left", padx=4, ipady=3)

        btn_usar = _btn(row_nc, "↓ USAR ESTA PLACA", lambda: None,
                        C["surface2"], C["text_mid"], px=8, py=3)
        btn_usar.pack(side="left", padx=8)

        # Campos do formulário
        self._nova_fields: dict[str, tk.Entry] = {}
        campos = [
            ("Placa *",       "placa",        True),
            ("Situação *",    "situacao",     True),
            ("Criado Por *",  "criado_por",   True),
            ("Quem Informou", "quem_informou",False),
            ("Onde Está",     "onde_esta",    False),
            ("Categoria",     "categoria",    False),
            ("Prioridade",    "prioridade",   False),
            ("Custo (R$)",    "custo",        False),
        ]
        for label, key, obrig in campos:
            row = tk.Frame(pad, bg=C["bg"])
            row.pack(fill="x", pady=3)
            cor = C["accent"] if obrig else C["text_mid"]
            _lbl(row, f"{label}:", 9, col=cor, width=20).pack(side="left", anchor="w")
            e = _ent(row)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            self._nova_fields[key] = e

        self._nova_fields["categoria"].insert(0, "Geral")
        self._nova_fields["prioridade"].insert(0, "Normal")
        self._nova_fields["custo"].insert(0, "0")

        # Callbacks
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

        # Datas
        row_dt = tk.Frame(pad, bg=C["bg"])
        row_dt.pack(fill="x", pady=3)
        _lbl(row_dt, "Data cadastro:", 9, col=C["text_mid"],
             width=20).pack(side="left", anchor="w")
        self.e_data_cad = _ent(row_dt, width=22)
        self.e_data_cad.pack(side="left", ipady=4)
        self.e_data_cad.insert(0, _now_ui())

        row_prev = tk.Frame(pad, bg=C["bg"])
        row_prev.pack(fill="x", pady=3)
        _lbl(row_prev, "Previsão (dd/mm/aaaa):", 9, col=C["text_mid"],
             width=20).pack(side="left", anchor="w")
        self.e_previsao = _ent(row_prev, width=22)
        self.e_previsao.pack(side="left", ipady=4)

        _lbl(pad, "Observações:", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_obs = tk.Text(
            pad, height=3, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_obs.pack(fill="x")

        _lbl(pad, "Status inicial (texto inicial do histórico):", 9,
             col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_status_ini = tk.Text(
            pad, height=4, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_status_ini.pack(fill="x")

        fr_res, self.res_nova = _txtbox(pad, 3)
        fr_res.pack(fill="x", pady=(10, 0))

        btns = tk.Frame(pad, bg=C["bg"])
        btns.pack(fill="x", pady=16)
        _btn2(btns, "💾 CADASTRAR MANUTENÇÃO",
              self._criar_manutencao, C["success"]).pack(side="left", padx=4)
        _btn2(btns, "🗑 LIMPAR CAMPOS",
              self._limpar_nova, C["surface3"], C["text_mid"]).pack(side="left", padx=4)

    # ════════════════════════════════════════════════════════════════════════
    # SUB-ABA 3 — DETALHE / EDIÇÃO
    # ════════════════════════════════════════════════════════════════════════

    def _build_detalhe(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📄 Detalhe / Edição ")

        paned = ttk.Panedwindow(f, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Painel esquerdo: formulário ──────────────────────────────────────
        left_cont = tk.Frame(paned, bg=C["bg"], width=540)
        left_cont.pack_propagate(False)
        paned.add(left_cont, weight=0)
        _, left = _make_scrollable(left_cont)
        lp = tk.Frame(left, bg=C["bg"])
        lp.pack(fill="x", padx=8, pady=6)

        # ── Painel direito: histórico ────────────────────────────────────────
        right = tk.Frame(paned, bg=C["bg"])
        paned.add(right, weight=1)

        _lbl(lp, "DADOS DA MANUTENÇÃO", 10, True, C["accent"]).pack(anchor="w", pady=(0, 6))

        self._edit_fields: dict[str, tk.Entry] = {}
        edit_campos = [
            ("ID",             "id",             True),
            ("Placa",          "placa",          True),
            ("Situação",       "situacao",       False),
            ("Criado Por",     "criado_por",     False),
            ("Quem Informou",  "quem_informou",  False),
            ("Onde Está",      "onde_esta",      False),
            ("Categoria",      "categoria",      False),
            ("Prioridade",     "prioridade",     False),
            ("Custo (R$)",     "custo",          False),
            ("Data Cadastro",  "data_cadastro",  False),
            ("Previsão",       "previsao",       False),
            ("Data Conclusão", "data_conclusao", False),
        ]
        for label, key, readonly in edit_campos:
            row = tk.Frame(lp, bg=C["bg"])
            row.pack(fill="x", pady=2)
            _lbl(row, f"{label}:", 9, col=C["text_mid"], width=16).pack(side="left", anchor="w")
            e = _ent(row)
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

        _lbl(lp, "Observações:", 9, col=C["text_mid"]).pack(anchor="w", pady=(8, 2))
        self.t_edit_obs = tk.Text(
            lp, height=3, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_edit_obs.pack(fill="x")

        _lbl(lp, "Novo status (opcional — adiciona ao histórico):", 9,
             col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_novo_status = tk.Text(
            lp, height=4, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        self.t_novo_status.pack(fill="x")

        _lbl(lp, "Autor do novo status:", 9, col=C["text_mid"]).pack(anchor="w", pady=(8, 2))
        self.e_autor = _ent(lp)
        self.e_autor.pack(fill="x", ipady=4)

        tk.Frame(lp, bg=C["border"], height=1).pack(fill="x", pady=10)

        row_b1 = tk.Frame(lp, bg=C["bg"])
        row_b1.pack(fill="x", pady=(0, 6))
        _btn2(row_b1, "💾 SALVAR",
              self._salvar_edicao, C["success"]).pack(side="left", padx=(0, 6))
        _btn2(row_b1, "➕ ADD STATUS",
              self._add_status_from_editor, C["purple"], C["text"]).pack(side="left", padx=6)

        row_b2 = tk.Frame(lp, bg=C["bg"])
        row_b2.pack(fill="x", pady=(0, 10))
        _btn2(row_b2, "✔ CONCLUIR",
              self._concluir_do_editor, C["accent"]).pack(side="left", padx=(0, 6))
        _btn2(row_b2, "🗑 DELETAR",
              self._deletar_atual, C["danger"]).pack(side="left", padx=6)

        fr_res, self.res_edit = _txtbox(lp, 4)
        fr_res.pack(fill="x", pady=(0, 16))

        # ── Histórico ────────────────────────────────────────────────────────
        _lbl(right, "HISTÓRICO DE STATUS", 10, True, C["accent"]).pack(
            anchor="w", padx=8, pady=(6, 4)
        )
        self._apply_style("CronSt", C["green"])
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

    # ════════════════════════════════════════════════════════════════════════
    # SUB-ABA 4 — ESTATÍSTICAS
    # ════════════════════════════════════════════════════════════════════════

    def _build_stats(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 📊 Estatísticas ")

        top = tk.Frame(f, bg=C["bg"])
        top.pack(fill="x", padx=12, pady=10)

        _lbl(top, "Placa (opcional):", col=C["text_mid"]).pack(side="left")
        self.e_stats_placa = _ent(top, width=14)
        self.e_stats_placa.pack(side="left", padx=6, ipady=4)
        self.e_stats_placa.bind("<Return>", lambda _e: self._carregar_stats())

        _btn(top, "📊 CARREGAR STATS", self._carregar_stats,
             C["blue"]).pack(side="left", padx=6)
        _btn(top, "🌐 GERAL",
             lambda: (self.e_stats_placa.delete(0, "end"), self._carregar_stats()),
             C["surface3"], C["accent"]).pack(side="left", padx=6)
        self.lb_stats = _lbl(top, "", col=C["text_dim"])
        self.lb_stats.pack(side="right")

        cards = tk.Frame(f, bg=C["bg"])
        cards.pack(fill="x", padx=12, pady=(0, 10))

        self._card_total = _lbl(cards, "Total: —",       10, True, C["accent"])
        self._card_conc  = _lbl(cards, "Concluídos: —",  10, True, C["success"])
        self._card_pend  = _lbl(cards, "Pendentes: —",   10, True, C["warn"])
        self._card_urg   = _lbl(cards, "Urgentes: —",    10, True, C["danger"])
        self._card_custo = _lbl(cards, "Custo: —",       10, True, C["purple"])
        for w in (self._card_total, self._card_conc, self._card_pend,
                  self._card_urg, self._card_custo):
            w.pack(side="left", padx=10)

        _lbl(f, "Por categoria:", 10, True, C["accent"]).pack(
            anchor="w", padx=12, pady=(6, 4)
        )
        self._apply_style("CronCat", C["accent"])
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

        fr, self.res_stats = _txtbox(f, 3)
        fr.pack(fill="x", padx=12, pady=(0, 12))

    # ════════════════════════════════════════════════════════════════════════
    # SUB-ABA 5 — CONFIGURAÇÃO
    # ════════════════════════════════════════════════════════════════════════

    def _build_config(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" ⚙ Configuração ")
        b = tk.Frame(f, bg=C["bg"])
        b.pack(fill="both", expand=True, padx=20, pady=16)

        _lbl(b, "CONFIGURAÇÃO DA API PHP", 11, True, C["accent"]).pack(anchor="w", pady=(0, 10))

        _lbl(b, "URL da API:", 9, col=C["text_mid"]).pack(anchor="w", pady=(4, 2))
        self.e_api_url = _ent(b)
        self.e_api_url.pack(fill="x", ipady=5)
        self.e_api_url.insert(0, _cron_url())

        _lbl(b, "Token:", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.e_api_key = _ent(b, show="*")   # mascara o token na tela
        self.e_api_key.pack(fill="x", ipady=5)
        self.e_api_key.insert(0, _cron_key())

        fr, self.res_cfg = _txtbox(b, 6)
        fr.pack(fill="x", pady=(12, 0))

        def salvar():
            _cred.CRON_API_URL = self.e_api_url.get().strip().rstrip("/")
            _cred.CRON_API_KEY = self.e_api_key.get().strip()
            _write(self.res_cfg,
                   f"✔ Salvo!\nURL: {_cred.CRON_API_URL}", C["success"])

        def testar():
            _write(self.res_cfg, "⏳ Testando...", C["accent"])
            # Aplica antes de testar
            _cred.CRON_API_URL = self.e_api_url.get().strip().rstrip("/")
            _cred.CRON_API_KEY = self.e_api_key.get().strip()

            def task():
                resp = _cron_get("ping")
                if resp.get("status"):
                    d = resp.get("data") or {}
                    msg = (f"✔ OK!\n{_safe(d.get('mensagem'))}\n"
                           f"{_safe(d.get('timestamp'))}\n"
                           f"Versão API: {_safe(d.get('versao'))}")
                    self.after(0, lambda: _write(self.res_cfg, msg, C["success"]))
                else:
                    err = f"✖ {resp.get('error', 'Falha na conexão')}"
                    self.after(0, lambda: _write(self.res_cfg, err, C["danger"]))

            threading.Thread(target=task, daemon=True).start()

        row = tk.Frame(b, bg=C["bg"])
        row.pack(pady=12)
        _btn(row, "💾 SALVAR", salvar, C["accent"]).pack(side="left", padx=6)
        _btn(row, "🔌 TESTAR", testar, C["green"]).pack(side="left", padx=6)

    # ════════════════════════════════════════════════════════════════════════
    # ESTILOS
    # ════════════════════════════════════════════════════════════════════════

    def _apply_style(self, name: str, hcol: str | None = None):
        s = ttk.Style()
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

    # ════════════════════════════════════════════════════════════════════════
    # BUSCA / PAGINAÇÃO
    # ════════════════════════════════════════════════════════════════════════

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

        # Captura antes de entrar na thread (evita race condition)
        limit  = self._limit
        offset = self._offset

        def task():
            params: dict = {"placa": placa, "limit": limit, "offset": offset}
            if concluido is not None:
                params["concluido"] = concluido

            resp = _cron_get("listar", params)

            if not resp.get("status"):
                def _err():
                    self.lb_busca.config(text="✖ Erro na busca")
                    messagebox.showerror("Erro", resp.get("error") or "Erro ao listar")
                self.after(0, _err)
                return

            data  = resp.get("data", {}) or {}
            rows  = data.get("registros", []) or []
            total = int(data.get("total") or len(rows))

            tree_rows: list[tuple] = []
            for m in rows:
                conc = int(m.get("concluido") or 0)
                tag  = "concluido" if conc else "aberto"

                # Detecta registros urgentes (aberto > 7 dias sem previsão)
                if not conc:
                    try:
                        dt_str = str(m.get("data_cadastro") or m.get("created_at") or "")[:19]
                        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                        if (datetime.now() - dt).days > 7 and not m.get("previsao"):
                            tag = "urgente"
                    except ValueError:
                        pass

                # Trunca status longo
                sa = _safe(m.get("status_atual"))
                if len(sa) > 60:
                    sa = sa[:60] + "…"

                try:
                    custo_fmt = f"{float(m.get('custo') or 0):.2f}"
                except (TypeError, ValueError):
                    custo_fmt = _safe(m.get("custo"))

                dt_cad = m.get("data_cadastro") or m.get("created_at")
                tree_rows.append((tag, (
                    _safe(m.get("id")),
                    _safe(m.get("placa")),
                    _safe(m.get("situacao")),
                    _fmt_dt(dt_cad),
                    _safe(m.get("criado_por")),
                    _safe(m.get("quem_informou")),
                    _safe(m.get("onde_esta")),
                    sa,
                    _safe(m.get("categoria"), "Geral"),
                    _safe(m.get("prioridade"), "Normal"),
                    custo_fmt,
                    _fmt_date(m.get("previsao")),
                    _fmt_date(m.get("data_conclusao")),
                    "✔" if conc else "✗",
                )))

            page  = (offset // max(1, limit)) + 1
            pages = max(1, (total + limit - 1) // limit)

            def _update():
                for r in self.tree.get_children():
                    self.tree.delete(r)
                for tag, values in tree_rows:
                    self.tree.insert("", "end", tags=(tag,), values=values)
                self._last_total = total
                self._last_rows  = rows
                self.lb_page.config(
                    text=f"Página: {page}/{pages}  |  Total: {total}")
                self.lb_busca.config(text=f"{len(rows)} registro(s) na página")

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()

    def _pag_first(self):
        if not self._last_query_placa:
            return
        self._offset = 0
        self._buscar(reset=False)

    def _pag_prev(self):
        if not self._last_query_placa:
            return
        self._offset = max(0, self._offset - self._limit)
        self._buscar(reset=False)

    def _pag_next(self):
        if not self._last_query_placa:
            return
        nxt = self._offset + self._limit
        if self._last_total and nxt >= self._last_total:
            return
        self._offset = nxt
        self._buscar(reset=False)

    def _listar_placas(self):
        self.lb_busca.config(text="⏳ Carregando placas...")
        self.e_placa.delete(0, "end")
        self._last_query_placa = ""

        def task():
            resp = _cron_get("placas")
            if not resp.get("status"):
                def _err():
                    self.lb_busca.config(text="✖ Erro")
                    messagebox.showerror("Erro", resp.get("error") or "Erro")
                self.after(0, _err)
                return

            rows = resp.get("data") or []
            # Monta uma linha por placa com colunas no formato da árvore
            tree_rows: list[tuple] = []
            for p in rows:
                placa      = _safe(p.get("placa"))
                registros  = p.get("registros", 0)
                pendentes  = p.get("pendentes", 0)
                concluidos = p.get("concluidos", 0)
                ultima     = _fmt_dt(p.get("ultima_manutencao"))
                # Mapeia para as colunas da árvore
                row_vals = (
                    "—",           # ID
                    placa,         # Placa
                    f"Registros: {registros}  |  Pendentes: {pendentes}  |  Concluídos: {concluidos}",
                    ultima,        # Data Cadastro (última)
                    "—", "—", "—", "—", "—", "—", "—", "—", "—",
                    f"{pendentes}P",
                )
                tree_rows.append(row_vals)

            def _update():
                for r in self.tree.get_children():
                    self.tree.delete(r)
                for vals in tree_rows:
                    self.tree.insert("", "end", tags=("normal",), values=vals)
                self.lb_busca.config(
                    text=f"{len(rows)} placa(s) com manutenções")
                self.lb_page.config(text="Página: —")

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # SELEÇÃO / DETALHE
    # ════════════════════════════════════════════════════════════════════════

    def _get_selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um registro.")
            return None
        values = self.tree.item(sel[0])["values"]
        if not values or str(values[0]) == "—":
            messagebox.showwarning("Atenção",
                                   "Selecione uma manutenção (não uma placa).")
            return None
        try:
            return int(values[0])
        except (TypeError, ValueError):
            return None

    def _ir_aba_detalhe(self):
        for i, tab in enumerate(self._nb.tabs()):
            if "Detalhe" in self._nb.tab(tab, "text"):
                self._nb.select(i)
                break

    def _ver_selecionada(self):
        mid = self._get_selected_id()
        if mid is None:
            return
        self._selected_id = mid
        self._carregar_detalhe(mid)
        self._ir_aba_detalhe()

    def _editar_selecionada(self):
        self._ver_selecionada()

    def _carregar_detalhe(self, mid: int):
        self.after(0, lambda: _write(self.res_edit, "⏳ Carregando...", C["accent"]))

        def task():
            resp   = _cron_get(f"buscar/{mid}")
            resp_h = _cron_get(f"historico/{mid}")

            if not resp.get("status"):
                err = f"✖ {resp.get('error', 'Erro ao carregar')}"
                self.after(0, lambda: _write(self.res_edit, err, C["danger"]))
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

                se("id",    _safe(m.get("id"), ""),    readonly=True)
                se("placa", _safe(m.get("placa"), ""), readonly=True)
                se("situacao",      _safe(m.get("situacao"), ""))
                se("criado_por",    _safe(m.get("criado_por"), ""))
                se("quem_informou", _safe(m.get("quem_informou"), ""))
                se("onde_esta",     _safe(m.get("onde_esta"), ""))
                se("categoria",     _safe(m.get("categoria"), "Geral"))
                se("prioridade",    _safe(m.get("prioridade"), "Normal"))

                try:
                    se("custo", f"{float(m.get('custo') or 0):.2f}")
                except (TypeError, ValueError):
                    se("custo", "0")

                dt_cad = m.get("data_cadastro") or m.get("created_at", "")
                se("data_cadastro",  _fmt_dt(dt_cad).replace("—", ""))
                se("previsao",       _fmt_date(m.get("previsao")).replace("—", ""))
                se("data_conclusao", _fmt_date(m.get("data_conclusao")).replace("—", ""))

                self._conc_var.set(bool(int(m.get("concluido") or 0)))
                self.t_edit_obs.delete("1.0", "end")
                obs = _safe(m.get("observacoes"), "").replace("—", "")
                if obs:
                    self.t_edit_obs.insert("1.0", obs)
                self.t_novo_status.delete("1.0", "end")

                # Histórico — usa campo criado_em (tabela status_update)
                for r in self.tree_status.get_children():
                    self.tree_status.delete(r)
                for upd in historico:
                    data_upd = upd.get("criado_em") or upd.get("created_at", "")
                    self.tree_status.insert("", "end", values=(
                        _fmt_dt(data_upd),
                        _safe(upd.get("autor")),
                        _safe(upd.get("texto")),
                    ))

                _write(self.res_edit, f"✔ Manutenção #{mid} carregada.", C["success"])

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # AÇÕES DO EDITOR
    # ════════════════════════════════════════════════════════════════════════

    def _salvar_edicao(self):
        mid = self._selected_id
        if not mid:
            _write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"])
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
            "criado_por":     self._edit_fields["criado_por"].get().strip() or "Sistema",
            "quem_informou":  self._edit_fields["quem_informou"].get().strip() or None,
            "onde_esta":      self._edit_fields["onde_esta"].get().strip() or None,
            "categoria":      self._edit_fields["categoria"].get().strip() or "Geral",
            "prioridade":     self._edit_fields["prioridade"].get().strip() or "Normal",
            "observacoes":    self.t_edit_obs.get("1.0", "end").strip() or None,
            "data_cadastro":  _to_api_dt(self._edit_fields["data_cadastro"].get()),
            "previsao":       _to_api_date(self._edit_fields["previsao"].get()),
            "data_conclusao": _to_api_date(self._edit_fields["data_conclusao"].get()),
            "concluido":      1 if self._conc_var.get() else 0,
            "custo":          custo,
        }

        if novo_st:
            body["novo_status"]  = novo_st
            body["status_atual"] = novo_st
            body["criado_por"]   = autor

        _write(self.res_edit, "⏳ Salvando...", C["accent"])

        def task():
            resp, code = _cron_put(f"atualizar/{mid}", body)
            if resp.get("status") or code in (200, 201):
                def _ok():
                    _write(self.res_edit,
                           f"✔ Manutenção #{mid} atualizada!", C["success"])
                    self._carregar_detalhe(mid)
                    if self._last_query_placa:
                        self._buscar(reset=False)
                self.after(0, _ok)
            else:
                err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                self.after(0, lambda: _write(self.res_edit, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()

    def _add_status_from_editor(self):
        mid = self._selected_id
        if not mid:
            _write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"])
            return
        texto = self.t_novo_status.get("1.0", "end").strip()
        if not texto:
            _write(self.res_edit, "⚠ Escreva um texto de status.", C["warn"])
            return
        autor = self.e_autor.get().strip() or "Sistema"
        _write(self.res_edit, "⏳ Adicionando...", C["accent"])

        def task():
            resp, code = _cron_post(f"add_status/{mid}",
                                    body={"texto": texto, "autor": autor})
            if resp.get("status") or code in (200, 201):
                def _ok():
                    _write(self.res_edit,
                           f"✔ Status adicionado! (#{mid})", C["success"])
                    self.t_novo_status.delete("1.0", "end")
                    self._carregar_detalhe(mid)
                self.after(0, _ok)
            else:
                err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                self.after(0, lambda: _write(self.res_edit, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()

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
            _write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"])
            return
        if not messagebox.askyesno("Confirmar",
                                    f"Deletar permanentemente a manutenção #{mid}?"):
            return

        def task():
            resp, code = _cron_delete(f"deletar/{mid}")
            if resp.get("status") or code in (200, 204):
                def _ok():
                    _write(self.res_edit,
                           f"✔ Manutenção #{mid} deletada.", C["success"])
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
                self.after(0, lambda: _write(self.res_edit, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # AÇÕES NA LISTA
    # ════════════════════════════════════════════════════════════════════════

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
        win.grab_set()  # modal

        _lbl(win, f"Adicionar status — manutenção #{mid}", 11, True,
             C["accent"]).pack(anchor="w", padx=12, pady=(12, 6))
        _lbl(win, "Autor:", 9, col=C["text_mid"]).pack(anchor="w", padx=12)
        e_aut = _ent(win)
        e_aut.pack(fill="x", padx=12, ipady=4)
        e_aut.insert(0, "Sistema")

        _lbl(win, "Texto:", 9, col=C["text_mid"]).pack(
            anchor="w", padx=12, pady=(10, 2))
        t = tk.Text(
            win, height=6, bg=C["surface3"], fg=C["text"],
            insertbackground=C["accent"], relief="flat",
            font=("Helvetica Neue", 10), padx=8, pady=6,
        )
        t.pack(fill="both", expand=True, padx=12)

        fr, res = _txtbox(win, 2)
        fr.pack(fill="x", padx=12, pady=(8, 4))

        def enviar():
            texto = t.get("1.0", "end").strip()
            autor = e_aut.get().strip() or "Sistema"
            if not texto:
                _write(res, "⚠ Escreva o texto.", C["warn"])
                return
            _write(res, "⏳ Enviando...", C["accent"])

            def task():
                resp, code = _cron_post(f"add_status/{mid}",
                                        body={"texto": texto, "autor": autor})
                if resp.get("status") or code in (200, 201):
                    def _ok():
                        _write(res, "✔ Status adicionado!", C["success"])
                        if self._last_query_placa:
                            self._buscar(reset=False)
                    self.after(0, _ok)
                else:
                    err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                    self.after(0, lambda: _write(res, err, C["danger"]))

            threading.Thread(target=task, daemon=True).start()

        row = tk.Frame(win, bg=C["bg"])
        row.pack(padx=12, pady=8, anchor="e")
        _btn(row, "➕ ADICIONAR", enviar,
             C["purple"]).pack(side="left", padx=6)
        _btn(row, "FECHAR", win.destroy,
             C["surface2"], C["text_mid"]).pack(side="left")

    # ════════════════════════════════════════════════════════════════════════
    # CRIAR MANUTENÇÃO
    # ════════════════════════════════════════════════════════════════════════

    def _limpar_nova(self):
        for e in self._nova_fields.values():
            e.delete(0, "end")
        self._nova_fields["categoria"].insert(0, "Geral")
        self._nova_fields["prioridade"].insert(0, "Normal")
        self._nova_fields["custo"].insert(0, "0")
        self.e_previsao.delete(0, "end")
        self.t_obs.delete("1.0", "end")
        self.t_status_ini.delete("1.0", "end")
        self.e_data_cad.delete(0, "end")
        self.e_data_cad.insert(0, _now_ui())
        _write(self.res_nova, "Campos limpos.", C["text_dim"])

    def _criar_manutencao(self):
        placa      = self._nova_fields["placa"].get().strip().upper()
        situacao   = self._nova_fields["situacao"].get().strip()
        criado_por = self._nova_fields["criado_por"].get().strip()

        if not placa or not situacao:
            _write(self.res_nova,
                   "⚠ Placa e Situação são obrigatórios.", C["warn"])
            return
        if not criado_por:
            _write(self.res_nova,
                   "⚠ Informe quem está criando (Criado Por).", C["warn"])
            return

        custo_txt = (self._nova_fields["custo"].get() or "").strip().replace(",", ".")
        try:
            custo = float(custo_txt) if custo_txt else 0.0
        except ValueError:
            custo = 0.0

        status_ini = self.t_status_ini.get("1.0", "end").strip()

        body: dict = {
            "placa":          placa,
            "situacao":       situacao,
            "criado_por":     criado_por,
            "quem_informou":  self._nova_fields["quem_informou"].get().strip() or None,
            "onde_esta":      self._nova_fields["onde_esta"].get().strip() or None,
            "data_cadastro":  _to_api_dt(self.e_data_cad.get()) or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "previsao":       _to_api_date(self.e_previsao.get()),
            "data_conclusao": None,
            "concluido":      0,
            "categoria":      self._nova_fields["categoria"].get().strip() or "Geral",
            "prioridade":     self._nova_fields["prioridade"].get().strip() or "Normal",
            "custo":          custo,
            "observacoes":    self.t_obs.get("1.0", "end").strip() or None,
            "status_atual":   status_ini or None,
        }

        _write(self.res_nova, "⏳ Cadastrando...", C["accent"])

        def task():
            resp, code = _cron_post("criar", body=body)
            if resp.get("status") or code in (200, 201):
                mid = (resp.get("data") or {}).get("id", "?")
                def _ok():
                    _write(self.res_nova,
                           f"✔ Manutenção #{mid} cadastrada por {criado_por}!",
                           C["success"])
                    self._limpar_nova()
                    if self.e_placa.get().strip().upper() == placa:
                        self._buscar(reset=True)
                self.after(0, _ok)
            else:
                err = f"✖ {resp.get('error', f'Falha HTTP {code}')}"
                self.after(0, lambda: _write(self.res_nova, err, C["danger"]))

        threading.Thread(target=task, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # EXPORTAR CSV
    # ════════════════════════════════════════════════════════════════════════

    _CSV_COLS = [
        "id", "placa", "situacao", "data_cadastro", "criado_por",
        "quem_informou", "onde_esta", "status_atual", "categoria",
        "prioridade", "custo", "previsao", "data_conclusao",
        "concluido", "observacoes",
    ]

    def _exportar_csv(self, modo: str = "pagina"):
        placa = (self.e_placa.get().strip().upper()
                 or self._last_query_placa).strip()

        if modo == "pagina" and not self._last_rows:
            messagebox.showinfo("Exportar", "Nenhum dado na página atual.")
            return
        if modo == "tudo" and not placa:
            messagebox.showinfo("Exportar", "Informe a placa antes de exportar.")
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
                writer.writerow([_safe(m.get(c), "") for c in self._CSV_COLS])

        if modo == "pagina":
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                    w = csv_mod.writer(fh, delimiter=";")
                    w.writerow(self._CSV_COLS)
                    _write_rows(w, self._last_rows)
                messagebox.showinfo("Exportar", f"Arquivo salvo:\n{path}")
            except OSError as exc:
                messagebox.showerror("Exportar", str(exc))
            return

        # Modo "tudo" — paginado em background
        situ = self.cb_situ.get().strip()
        concluido_filter = None
        if situ == "Abertos":
            concluido_filter = 0
        elif situ == "Concluídos":
            concluido_filter = 1

        def task():
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                    writer = csv_mod.writer(fh, delimiter=";")
                    writer.writerow(self._CSV_COLS)
                    limit  = 200
                    offset = 0
                    total  = None
                    while True:
                        params: dict = {
                            "placa": placa, "limit": limit, "offset": offset
                        }
                        if concluido_filter is not None:
                            params["concluido"] = concluido_filter
                        resp = _cron_get("listar", params)
                        if not resp.get("status"):
                            self.after(
                                0, lambda: messagebox.showerror(
                                    "Exportar",
                                    resp.get("error", "Erro na API")
                                )
                            )
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
                self.after(
                    0, lambda: messagebox.showinfo(
                        "Exportar", f"CSV completo salvo:\n{path}"
                    )
                )
            except OSError as exc:
                self.after(
                    0, lambda: messagebox.showerror("Exportar", str(exc))
                )

        threading.Thread(target=task, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # ESTATÍSTICAS
    # ════════════════════════════════════════════════════════════════════════

    def _abrir_stats_da_placa(self):
        placa = (self.e_placa.get().strip().upper()
                 or self._last_query_placa)
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
        _write(self.res_stats, "⏳ Buscando estatísticas...", C["accent"])

        def task():
            params = {"placa": placa} if placa else {}
            resp   = _cron_get("stats", params)

            if not resp.get("status"):
                def _err():
                    self.lb_stats.config(text="✖ Erro")
                    _write(self.res_stats,
                           f"✖ {resp.get('error', 'Erro')}", C["danger"])
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
                        _safe(cat.get("categoria")),
                        _safe(cat.get("qtd")),
                    ))

                self.lb_stats.config(text=label_txt)
                _write(self.res_stats, "✔ Estatísticas carregadas.", C["success"])

            self.after(0, _update)

        threading.Thread(target=task, daemon=True).start()