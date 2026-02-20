"""
tab_cronologia.py — IFControll v3.2 (CORRIGIDO — botões sempre visíveis)
Correções:
  - _build_nova: canvas+scrollbar para o formulário — botão sempre visível
  - _build_detalhe: painel esquerdo com canvas+scrollbar — botões sempre visíveis
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
from datetime import datetime

from credencials import CRON_API_URL, CRON_API_KEY, _CRON_TOKEN_HEADER_NAME

# ─── API CLIENT ──────────────────────────────────────────────────────────
def _cron_headers():
    return {"Content-Type": "application/json", _CRON_TOKEN_HEADER_NAME: CRON_API_KEY}

def _cron_req(method, path, params=None, body=None, timeout=15):
    try:
        q = {"path": path}
        if params:
            q.update(params)
        r = requests.request(
            method=method.upper(), url=CRON_API_URL,
            headers=_cron_headers(), params=q, json=body, timeout=timeout
        )
        try:
            data = r.json()
        except Exception:
            data = {"status": False, "error": f"Resposta não-JSON (HTTP {r.status_code})",
                    "raw": (r.text or "")[:4000]}
        return data, r.status_code
    except Exception as e:
        return {"status": False, "error": str(e)}, 0

def _cron_get(path, params=None):
    data, _ = _cron_req("GET", path, params=params)
    return data

def _cron_post(path, body=None, params=None):
    return _cron_req("POST", path, params=params, body=body)

def _cron_put(path, body=None, params=None):
    return _cron_req("PUT", path, params=params, body=body)

def _cron_delete(path, params=None):
    return _cron_req("DELETE", path, params=params)


# ─── CORES ───────────────────────────────────────────────────────────────
_C_DEFAULT = {
    "bg":"#0B0D12","surface":"#12151E","surface2":"#181C29","surface3":"#1E2335",
    "border":"#232840","accent":"#00C8F8","accent2":"#6C5CE7","warn":"#FFA502",
    "danger":"#FF3B4E","success":"#00F5A0","text":"#DDE1F0","text_dim":"#58607A",
    "text_mid":"#8B93B5","hover":"#1C2138","green":"#00F5A0","blue":"#00C8F8",
    "purple":"#6C5CE7","orange":"#FF7043","yellow":"#FFA502","red":"#FF3B4E",
    "pink":"#FD79A8",
}

def _get_C():
    try:
        import __main__
        return __main__.C
    except:
        return _C_DEFAULT


# ─── HELPERS UI ──────────────────────────────────────────────────────────
def _lbl(p, text, size=9, bold=False, col=None, bg=None, **kw):
    C = _get_C()
    return tk.Label(p, text=text, bg=bg or C["bg"], fg=col or C["text"],
                    font=("Helvetica Neue", size, "bold" if bold else "normal"), **kw)

def _ent(p, w=None, **kw):
    C = _get_C()
    e = tk.Entry(p, bg=C["surface3"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat",
                 highlightthickness=1, highlightbackground=C["border"],
                 highlightcolor=C["accent"], font=("Helvetica Neue", 10), **kw)
    if w:
        e.config(width=w)
    return e

def _btn(p, text, cmd, bg=None, fg=None, px=12, py=5):
    C = _get_C()
    col = bg or C["accent"]
    b = tk.Label(p, text=text, bg=col, fg=fg or C["bg"],
                 font=("Helvetica Neue", 9, "bold"),
                 padx=px, pady=py, cursor="hand2", relief="flat")
    b.bind("<Button-1>", lambda e: cmd())
    return b

def _btn2(p, text, cmd, bg=None, fg=None):
    C = _get_C()
    return tk.Button(p, text=text, command=cmd,
                     bg=bg or C["accent"], fg=fg or C["bg"],
                     activebackground=bg or C["accent"], activeforeground=fg or C["bg"],
                     relief="flat", bd=0, cursor="hand2",
                     font=("Helvetica Neue", 9, "bold"), padx=10, pady=6)

def _txtbox(p, h=5):
    C = _get_C()
    fr = tk.Frame(p, bg=C["surface2"], highlightthickness=1, highlightbackground=C["border"])
    t = tk.Text(fr, height=h, bg=C["surface2"], fg=C["text"],
                insertbackground=C["accent"], relief="flat",
                font=("Consolas", 9), padx=8, pady=6,
                selectbackground=C["accent2"], state="disabled")
    sb = tk.Scrollbar(fr, command=t.yview, bg=C["surface2"],
                      troughcolor=_get_C()["bg"], relief="flat")
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(fill="both", expand=True)
    return fr, t

def _write(t, text, col=None):
    C = _get_C()
    t.config(state="normal")
    t.delete("1.0", "end")
    t.config(fg=col or C["text"])
    t.insert("end", text)
    t.config(state="disabled")

def _safe_str(v, default="—"):
    s = str(v).strip() if v is not None else ""
    return default if s in ("", "None", "null") else s


# ─── SCROLL CANVAS helper ─────────────────────────────────────────────────
def _make_scrollable(parent):
    """
    Retorna (canvas, inner_frame).
    inner_frame é o frame onde você faz .pack() dos widgets.
    O canvas com scrollbar vertical é empacotado em parent com fill+expand.
    """
    C = _get_C()
    canvas = tk.Canvas(parent, bg=C["bg"], highlightthickness=0)
    vsb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)

    vsb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=C["bg"])
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfig(win_id, width=event.width)

    inner.bind("<Configure>", _on_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    # scroll com roda do mouse
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    return canvas, inner


# ─── DATAS ───────────────────────────────────────────────────────────────
def _fmt_dt_from_api(s):
    if not s or str(s) in ("None", "null", "—"): return "—"
    s = str(s)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try: return datetime.strptime(s, fmt).strftime("%d/%m/%Y %H:%M")
        except: pass
    return s

def _fmt_date_from_api(s):
    if not s or str(s) in ("None", "null", "—"): return "—"
    try: return datetime.strptime(str(s), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(s)

def _parse_dt_to_api(s):
    s = (s or "").strip()
    if not s: return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except: pass
    return s

def _parse_date_to_api(s):
    s = (s or "").strip()
    if not s: return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except: pass
    return s

def _now_ui_dt():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


# ─── ABA PRINCIPAL ────────────────────────────────────────────────────────
class TabCronologia(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=_get_C()["bg"])
        self._selected_id = None
        self._limit = 50
        self._offset = 0
        self._last_total = 0
        self._last_rows = []
        self._last_query_placa = ""
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._nb = nb
        self._build_buscar(nb)
        self._build_nova(nb)
        self._build_detalhe(nb)
        self._build_stats(nb)
        self._build_config(nb)

    # ══════════════════════════════════════════════════════════════
    # SUB-ABA 1: BUSCAR / LISTA
    # ══════════════════════════════════════════════════════════════
    def _build_buscar(self, nb):
        C = _get_C()
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text=" 🔍 Buscar / Lista ")

        ctrl = tk.Frame(f, bg=C["bg"]); ctrl.pack(fill="x", padx=8, pady=(6, 2))
        _lbl(ctrl, "Placa:", col=C["text_mid"]).pack(side="left")
        self.e_placa = _ent(ctrl, w=14); self.e_placa.pack(side="left", padx=6, ipady=4)
        self.e_placa.bind("<Return>", lambda e: self._buscar(reset=True))

        _lbl(ctrl, "Situação:", col=C["text_mid"]).pack(side="left", padx=(8, 2))
        self.cb_situ = ttk.Combobox(ctrl, values=["Todos", "Abertos", "Concluídos"], width=12, state="readonly")
        self.cb_situ.set("Todos"); self.cb_situ.pack(side="left", padx=4)

        _lbl(ctrl, "Por página:", col=C["text_mid"]).pack(side="left", padx=(8, 2))
        self.cb_limit = ttk.Combobox(ctrl, values=["25", "50", "100", "200"], width=6, state="readonly")
        self.cb_limit.set(str(self._limit)); self.cb_limit.pack(side="left", padx=4)

        _btn(ctrl, "🔍 BUSCAR", lambda: self._buscar(reset=True), C["accent"]).pack(side="left", padx=6)
        _btn(ctrl, "📋 PLACAS", self._listar_placas, C["surface3"], C["accent"]).pack(side="left", padx=4)

        self.lb_busca = _lbl(ctrl, "", col=C["text_dim"]); self.lb_busca.pack(side="right")

        nav = tk.Frame(f, bg=C["surface3"]); nav.pack(fill="x", padx=8, pady=(4, 4))
        _btn(nav, "⏮ Primeira", lambda: self._pag_first(), C["surface2"], C["text"]).pack(side="left", padx=4)
        _btn(nav, "◀ Anterior", lambda: self._pag_prev(), C["surface2"], C["text"]).pack(side="left", padx=4)
        _btn(nav, "Próxima ▶", lambda: self._pag_next(), C["surface2"], C["text"]).pack(side="left", padx=4)
        self.lb_page = _lbl(nav, "Página: —", 9, col=C["text_mid"], bg=C["surface3"]); self.lb_page.pack(side="left", padx=10)
        _btn(nav, "📊 STATS", self._abrir_stats_da_placa, C["blue"]).pack(side="right", padx=4)
        _btn(nav, "📥 CSV (Página)", lambda: self._exportar_csv("pagina"), C["surface2"], C["text_mid"]).pack(side="right", padx=4)
        _btn(nav, "📥 CSV (Tudo)",   lambda: self._exportar_csv("tudo"),   C["surface2"], C["text_mid"]).pack(side="right", padx=4)

        cols = ("ID","Placa","Situação","Data Cadastro","Quem Informou","Onde Está",
                "Status Atual","Categoria","Prioridade","Custo","Previsão","Conclusão","Concluído")
        ws   = (50, 80, 180, 140, 130, 160, 220, 120, 110, 90, 120, 120, 80)
        self._apply_style("Cron", C["accent"])
        inner = tk.Frame(f, bg=C["bg"]); inner.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(inner, columns=cols, show="headings", style="Cron.Treeview", height=14)
        for c, w in zip(cols, ws):
            self.tree.heading(c, text=c, anchor="w"); self.tree.column(c, width=w, anchor="w", stretch=True)
        vs = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(inner, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y"); hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("aberto",    background="#0d1a1a")
        self.tree.tag_configure("concluido", background="#0d1a0d")
        self.tree.tag_configure("urgente",   background="#1a0808")
        self.tree.tag_configure("normal",    background=C["surface2"])
        self.tree.bind("<Double-1>", lambda e: self._ver_selecionada())

        act = tk.Frame(f, bg=C["surface3"]); act.pack(fill="x", padx=8, pady=4)
        _lbl(act, "Ação rápida:", 8, col=C["text_mid"], bg=C["surface3"]).pack(side="left", padx=8)
        _btn(act, "👁 DETALHES",   self._ver_selecionada,       C["accent"]).pack(side="left", padx=4)
        _btn(act, "✏ EDITAR",      self._editar_selecionada,    C["warn"]).pack(side="left", padx=4)
        _btn(act, "➕ ADD STATUS", self._add_status_popup,      C["purple"]).pack(side="left", padx=4)
        _btn(act, "✔ CONCLUIR",    self._concluir_selecionada,  C["success"]).pack(side="left", padx=4)
        _btn(act, "🗑 DELETAR",    self._deletar_selecionada,   C["danger"]).pack(side="left", padx=4)

    # ══════════════════════════════════════════════════════════════
    # SUB-ABA 2: NOVA MANUTENÇÃO — com canvas scrollável
    # ══════════════════════════════════════════════════════════════
    def _build_nova(self, nb):
        C = _get_C()
        # Frame container que vai ao notebook
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text=" ➕ Nova Manutenção ")

        # ── BOTÕES FIXOS NO TOPO (sempre visíveis) ──────────────────
        bar_top = tk.Frame(f, bg=C["surface3"]); bar_top.pack(fill="x", padx=0, pady=0)
        _lbl(bar_top, "NOVA MANUTENÇÃO", 10, True, C["accent"], bg=C["surface3"]).pack(side="left", padx=12, pady=8)

        # ── ÁREA SCROLLÁVEL ─────────────────────────────────────────
        scroll_area = tk.Frame(f, bg=C["bg"]); scroll_area.pack(fill="both", expand=True)
        _, b = _make_scrollable(scroll_area)

        # Espaço interno
        pad = tk.Frame(b, bg=C["bg"]); pad.pack(fill="x", padx=20, pady=10)

        self._nova_fields = {}
        campos = [
            ("Placa *",        "placa",         True),
            ("Situação *",     "situacao",      True),
            ("Quem informou",  "quem_informou", False),
            ("Onde está",      "onde_esta",     False),
            ("Categoria",      "categoria",     False),
            ("Prioridade",     "prioridade",    False),
            ("Custo (R$)",     "custo",         False),
        ]
        for label, key, obrig in campos:
            row = tk.Frame(pad, bg=C["bg"]); row.pack(fill="x", pady=3)
            cor = C["accent"] if obrig else C["text_mid"]
            _lbl(row, f"{label}:", 9, col=cor, width=20).pack(side="left", anchor="w")
            e = _ent(row); e.pack(side="left", fill="x", expand=True, ipady=4)
            self._nova_fields[key] = e

        self._nova_fields["categoria"].insert(0, "Geral")
        self._nova_fields["prioridade"].insert(0, "Normal")
        self._nova_fields["custo"].insert(0, "0")

        row_dt = tk.Frame(pad, bg=C["bg"]); row_dt.pack(fill="x", pady=3)
        _lbl(row_dt, "Data cadastro:", 9, col=C["text_mid"], width=20).pack(side="left", anchor="w")
        self.e_data_cad = _ent(row_dt, w=22); self.e_data_cad.pack(side="left", ipady=4)
        self.e_data_cad.insert(0, _now_ui_dt())

        row_prev = tk.Frame(pad, bg=C["bg"]); row_prev.pack(fill="x", pady=3)
        _lbl(row_prev, "Previsão (dd/mm/aaaa):", 9, col=C["text_mid"], width=20).pack(side="left", anchor="w")
        self.e_previsao = _ent(row_prev, w=22); self.e_previsao.pack(side="left", ipady=4)

        _lbl(pad, "Observações:", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_obs = tk.Text(pad, height=3, bg=C["surface3"], fg=C["text"],
                             insertbackground=C["accent"], relief="flat",
                             font=("Helvetica Neue", 10), padx=8, pady=6)
        self.t_obs.pack(fill="x")

        _lbl(pad, "Status inicial (vira status_atual e cria update):", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_status_ini = tk.Text(pad, height=4, bg=C["surface3"], fg=C["text"],
                                    insertbackground=C["accent"], relief="flat",
                                    font=("Helvetica Neue", 10), padx=8, pady=6)
        self.t_status_ini.pack(fill="x")

        fr_res, self.res_nova = _txtbox(pad, 3); fr_res.pack(fill="x", pady=(10, 0))

        # ── BOTÃO CADASTRAR (dentro do scroll, mas bem separado) ────
        btn_frame = tk.Frame(pad, bg=C["bg"]); btn_frame.pack(fill="x", pady=16)
        _btn2(btn_frame, "💾 CADASTRAR MANUTENÇÃO", self._criar_manutencao, C["success"]).pack(side="left", padx=4)
        _btn2(btn_frame, "🗑 LIMPAR CAMPOS", self._limpar_nova, C["surface3"], C["text_mid"]).pack(side="left", padx=4)

    # ══════════════════════════════════════════════════════════════
    # SUB-ABA 3: DETALHE / EDIÇÃO — painel esquerdo scrollável
    # ══════════════════════════════════════════════════════════════
    def _build_detalhe(self, nb):
        C = _get_C()
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text=" 📄 Detalhe / Edição ")

        paned = ttk.Panedwindow(f, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Painel esquerdo: canvas scrollável ──────────────────────
        left_container = tk.Frame(paned, bg=C["bg"], width=520)
        left_container.pack_propagate(False)
        paned.add(left_container, weight=0)

        _, left = _make_scrollable(left_container)
        left_pad = tk.Frame(left, bg=C["bg"]); left_pad.pack(fill="x", padx=8, pady=6)

        # ── Painel direito: histórico ───────────────────────────────
        right = tk.Frame(paned, bg=C["bg"])
        paned.add(right, weight=1)

        # ─── CONTEÚDO DO PAINEL ESQUERDO ────────────────────────────
        _lbl(left_pad, "DADOS DA MANUTENÇÃO", 10, True, C["accent"]).pack(anchor="w", pady=(0, 6))

        self._edit_fields = {}
        edit_campos = [
            ("ID",             "id",             True),
            ("Placa",          "placa",          True),
            ("Situação",       "situacao",       False),
            ("Quem informou",  "quem_informou",  False),
            ("Onde está",      "onde_esta",      False),
            ("Categoria",      "categoria",      False),
            ("Prioridade",     "prioridade",     False),
            ("Custo (R$)",     "custo",          False),
            ("Data Cadastro",  "data_cadastro",  False),
            ("Previsão",       "previsao",       False),
            ("Data Conclusão", "data_conclusao", False),
        ]
        for label, key, readonly in edit_campos:
            row = tk.Frame(left_pad, bg=C["bg"]); row.pack(fill="x", pady=2)
            _lbl(row, f"{label}:", 9, col=C["text_mid"], width=16).pack(side="left", anchor="w")
            e = _ent(row)
            if readonly:
                e.config(state="readonly", fg=C["text_dim"])
            e.pack(side="left", fill="x", expand=True, ipady=4)
            self._edit_fields[key] = e

        row_conc = tk.Frame(left_pad, bg=C["bg"]); row_conc.pack(fill="x", pady=4)
        self._conc_var = tk.BooleanVar()
        tk.Checkbutton(row_conc, text="Concluído", variable=self._conc_var,
                       bg=C["bg"], fg=C["text"], activebackground=C["bg"],
                       selectcolor=C["surface3"], font=("Helvetica Neue", 10)).pack(side="left")

        _lbl(left_pad, "Observações:", 9, col=C["text_mid"]).pack(anchor="w", pady=(8, 2))
        self.t_edit_obs = tk.Text(left_pad, height=3, bg=C["surface3"], fg=C["text"],
                                  insertbackground=C["accent"], relief="flat",
                                  font=("Helvetica Neue", 10), padx=8, pady=6)
        self.t_edit_obs.pack(fill="x")

        _lbl(left_pad, "Novo status (opcional — adiciona ao histórico):", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.t_novo_status = tk.Text(left_pad, height=4, bg=C["surface3"], fg=C["text"],
                                     insertbackground=C["accent"], relief="flat",
                                     font=("Helvetica Neue", 10), padx=8, pady=6)
        self.t_novo_status.pack(fill="x")

        _lbl(left_pad, "Autor do status:", 9, col=C["text_mid"]).pack(anchor="w", pady=(8, 2))
        self.e_autor = _ent(left_pad); self.e_autor.pack(fill="x", ipady=4)

        # ── SEPARADOR ──────────────────────────────────────────────
        tk.Frame(left_pad, bg=C["border"], height=1).pack(fill="x", pady=10)

        # ── BOTÕES — sempre dentro do scroll mas com pady generoso ──
        btn_row1 = tk.Frame(left_pad, bg=C["bg"]); btn_row1.pack(fill="x", pady=(0, 6))
        _btn2(btn_row1, "💾 SALVAR (API)",        self._salvar_edicao,         C["success"]).pack(side="left", padx=(0, 6))
        _btn2(btn_row1, "➕ ADD STATUS (API)",    self._add_status_from_editor, C["purple"], C["text"]).pack(side="left", padx=6)

        btn_row2 = tk.Frame(left_pad, bg=C["bg"]); btn_row2.pack(fill="x", pady=(0, 10))
        _btn2(btn_row2, "✔ CONCLUIR",  self._concluir_do_editor, C["accent"]).pack(side="left", padx=(0, 6))
        _btn2(btn_row2, "🗑 DELETAR",  self._deletar_atual,       C["danger"]).pack(side="left", padx=6)

        fr_res, self.res_edit = _txtbox(left_pad, 4); fr_res.pack(fill="x", pady=(0, 16))

        # ─── PAINEL DIREITO: HISTÓRICO ───────────────────────────────
        _lbl(right, "HISTÓRICO DE STATUS", 10, True, C["accent"]).pack(anchor="w", padx=8, pady=(6, 4))
        self._apply_style("CronSt", C["green"])
        inner_r = tk.Frame(right, bg=C["bg"]); inner_r.pack(fill="both", expand=True, padx=8)
        st_cols = ("Data", "Autor", "Texto")
        st_ws   = (150, 130, 520)
        self.tree_status = ttk.Treeview(inner_r, columns=st_cols, show="headings",
                                         style="CronSt.Treeview", height=20)
        for c, w in zip(st_cols, st_ws):
            self.tree_status.heading(c, text=c, anchor="w")
            self.tree_status.column(c, width=w, anchor="w", stretch=True)
        vs2 = ttk.Scrollbar(inner_r, orient="vertical", command=self.tree_status.yview)
        self.tree_status.configure(yscrollcommand=vs2.set)
        vs2.pack(side="right", fill="y")
        self.tree_status.pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════
    # SUB-ABA 4: ESTATÍSTICAS
    # ══════════════════════════════════════════════════════════════
    def _build_stats(self, nb):
        C = _get_C()
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text=" 📊 Estatísticas ")
        self._f_stats = f

        top = tk.Frame(f, bg=C["bg"]); top.pack(fill="x", padx=12, pady=10)
        _lbl(top, "Placa (opcional):", col=C["text_mid"]).pack(side="left")
        self.e_stats_placa = _ent(top, w=14); self.e_stats_placa.pack(side="left", padx=6, ipady=4)
        self.e_stats_placa.bind("<Return>", lambda e: self._carregar_stats())
        _btn(top, "📊 CARREGAR STATS", self._carregar_stats, C["blue"]).pack(side="left", padx=6)
        _btn(top, "🌐 STATS GERAL", lambda: (self.e_stats_placa.delete(0,"end"), self._carregar_stats()), C["surface3"], C["accent"]).pack(side="left", padx=6)
        self.lb_stats = _lbl(top, "", col=C["text_dim"]); self.lb_stats.pack(side="right")

        cards = tk.Frame(f, bg=C["bg"]); cards.pack(fill="x", padx=12, pady=(0, 10))
        self._card_total = _lbl(cards, "Total: —", 10, True, C["accent"])
        self._card_conc  = _lbl(cards, "Concluídos: —", 10, True, C["success"])
        self._card_pend  = _lbl(cards, "Pendentes: —", 10, True, C["warn"])
        self._card_urg   = _lbl(cards, "Urgentes: —", 10, True, C["danger"])
        self._card_custo = _lbl(cards, "Custo Total: —", 10, True, C["purple"])
        for w in (self._card_total, self._card_conc, self._card_pend, self._card_urg, self._card_custo):
            w.pack(side="left", padx=10)

        _lbl(f, "Por categoria:", 10, True, C["accent"]).pack(anchor="w", padx=12, pady=(6, 4))
        self._apply_style("CronCat", C["accent"])
        inner = tk.Frame(f, bg=C["bg"]); inner.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.tree_cat = ttk.Treeview(inner, columns=("Categoria","Qtd"), show="headings",
                                      style="CronCat.Treeview", height=14)
        self.tree_cat.heading("Categoria", text="Categoria", anchor="w")
        self.tree_cat.heading("Qtd", text="Qtd", anchor="w")
        self.tree_cat.column("Categoria", width=260, anchor="w", stretch=True)
        self.tree_cat.column("Qtd", width=120, anchor="w", stretch=False)
        vs = ttk.Scrollbar(inner, orient="vertical", command=self.tree_cat.yview)
        self.tree_cat.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y"); self.tree_cat.pack(fill="both", expand=True)

        fr, self.res_stats = _txtbox(f, 3); fr.pack(fill="x", padx=12, pady=(0, 12))

    # ══════════════════════════════════════════════════════════════
    # SUB-ABA 5: CONFIGURAÇÃO
    # ══════════════════════════════════════════════════════════════
    def _build_config(self, nb):
        C = _get_C()
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text=" ⚙ Configuração ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=16)

        _lbl(b, "CONFIGURAÇÃO DA API (PHP v4.0)", 11, True, C["accent"]).pack(anchor="w", pady=(0, 10))

        _lbl(b, "URL da API:", 9, col=C["text_mid"]).pack(anchor="w", pady=(4, 2))
        self.e_api_url = _ent(b); self.e_api_url.pack(fill="x", ipady=5)
        self.e_api_url.insert(0, CRON_API_URL)

        _lbl(b, "Token (Header X-API-Token):", 9, col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        self.e_api_key = _ent(b); self.e_api_key.pack(fill="x", ipady=5)
        self.e_api_key.insert(0, CRON_API_KEY)

        fr, self.res_cfg = _txtbox(b, 6); fr.pack(fill="x", pady=(12, 0))

        def salvar_config():
            global CRON_API_URL, CRON_API_KEY
            CRON_API_URL = self.e_api_url.get().strip().rstrip("/")
            CRON_API_KEY = self.e_api_key.get().strip()
            _write(self.res_cfg, f"✔ Configuração salva!\nURL: {CRON_API_URL}", C["success"])

        def testar():
            _write(self.res_cfg, "⏳ Testando conexão (ping)...", C["accent"])
            def task():
                global CRON_API_URL, CRON_API_KEY
                CRON_API_URL = self.e_api_url.get().strip().rstrip("/")
                CRON_API_KEY = self.e_api_key.get().strip()
                resp = _cron_get("ping")
                if resp.get("status"):
                    d = resp.get("data", {})
                    _write(self.res_cfg, f"✔ OK!\n{_safe_str(d.get('mensagem'))}\n{_safe_str(d.get('timestamp'))}\nPHP: {_safe_str(d.get('php'))}", C["success"])
                else:
                    _write(self.res_cfg, f"✖ Falha:\n{resp.get('error','Erro desconhecido')}", C["danger"])
            threading.Thread(target=task, daemon=True).start()

        row = tk.Frame(b, bg=C["bg"]); row.pack(pady=12)
        _btn(row, "💾 SALVAR", salvar_config, C["accent"]).pack(side="left", padx=6)
        _btn(row, "🔌 TESTAR", testar, C["green"]).pack(side="left", padx=6)

        info = tk.Frame(b, bg=C["surface3"], highlightthickness=1, highlightbackground=C["border"])
        info.pack(fill="x", pady=(10, 0))
        tk.Label(info, text=(
            "Rotas PHP v4.0 (via ?path=...)\n"
            "GET  path=ping\n"
            "GET  path=listar&placa=ABC1234&concluido=0&limit=50&offset=0\n"
            "GET  path=buscar/123  |  PUT path=atualizar/123\n"
            "POST path=criar       |  DELETE path=deletar/123\n"
            "POST path=add_status/123  |  PUT path=concluir/123\n"
            "GET  path=stats[&placa=...]  |  GET path=placas\n"
            "Auth: Header X-API-Token: <token>"
        ), bg=C["surface3"], fg=C["text_mid"],
           font=("Consolas", 8), justify="left", padx=12, pady=10).pack(anchor="w")

    # ══════════════════════════════════════════════════════════════
    # STYLE
    # ══════════════════════════════════════════════════════════════
    def _apply_style(self, name, hcol=None):
        C = _get_C()
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(f"{name}.Treeview",
                    background=C["surface2"], foreground=C["text"],
                    rowheight=26, fieldbackground=C["surface2"],
                    borderwidth=0, font=("Consolas", 9))
        s.configure(f"{name}.Treeview.Heading",
                    background=C["surface3"], foreground=hcol or C["accent"],
                    font=("Helvetica Neue", 9, "bold"), borderwidth=0, relief="flat")
        s.map(f"{name}.Treeview", background=[("selected", C["accent2"])])

    # ══════════════════════════════════════════════════════════════
    # BUSCA / PAGINAÇÃO
    # ══════════════════════════════════════════════════════════════
    def _buscar(self, reset=False):
        C = _get_C()
        placa = self.e_placa.get().strip().upper()
        if not placa:
            messagebox.showwarning("Atenção", "Informe a placa para buscar.")
            return
        try:
            self._limit = int(self.cb_limit.get().strip())
        except:
            self._limit = 50
        if reset:
            self._offset = 0
        self._last_query_placa = placa
        self.lb_busca.config(text="⏳ Buscando...")
        situ = self.cb_situ.get().strip()
        concluido = None
        if situ == "Abertos":    concluido = 0
        elif situ == "Concluídos": concluido = 1

        def task():
            params = {"placa": placa, "limit": self._limit, "offset": self._offset}
            if concluido is not None:
                params["concluido"] = concluido
            resp = _cron_get("listar", params)
            for r in self.tree.get_children():
                self.tree.delete(r)
            if not resp.get("status"):
                self.lb_busca.config(text="✖ Erro")
                messagebox.showerror("Erro", resp.get("error") or "Erro ao listar")
                return
            data = resp.get("data", {}) or {}
            rows = data.get("registros", []) or []
            total = int(data.get("total", len(rows)) or len(rows))
            self._last_total = total
            self._last_rows  = rows
            for m in rows:
                conc = int(m.get("concluido", 0) or 0)
                tag  = "concluido" if conc else "aberto"
                try:
                    dt = datetime.strptime(str(m.get("data_cadastro",""))[:19], "%Y-%m-%d %H:%M:%S")
                    if (not conc) and (datetime.now()-dt).days > 7 and not m.get("previsao"):
                        tag = "urgente"
                except: pass
                sa = _safe_str(m.get("status_atual"))
                if len(sa) > 60: sa = sa[:60] + "..."
                try:   custo_fmt = f"{float(m.get('custo',0)):.2f}"
                except: custo_fmt = _safe_str(m.get("custo"))
                self.tree.insert("", "end", tags=(tag,), values=(
                    _safe_str(m.get("id")),
                    _safe_str(m.get("placa")),
                    _safe_str(m.get("situacao")),
                    _fmt_dt_from_api(m.get("data_cadastro")),
                    _safe_str(m.get("quem_informou")),
                    _safe_str(m.get("onde_esta")),
                    sa,
                    _safe_str(m.get("categoria"), default="Geral"),
                    _safe_str(m.get("prioridade"), default="Normal"),
                    custo_fmt,
                    _fmt_date_from_api(m.get("previsao")),
                    _fmt_date_from_api(m.get("data_conclusao")),
                    "✔" if conc else "✗",
                ))
            page  = (self._offset // max(1, self._limit)) + 1
            pages = max(1, (total + self._limit - 1) // self._limit)
            self.lb_page.config(text=f"Página: {page}/{pages}  |  Total: {total}")
            self.lb_busca.config(text=f"{len(rows)} na página")
        threading.Thread(target=task, daemon=True).start()

    def _pag_first(self):
        if not self._last_query_placa: return
        self._offset = 0; self._buscar(reset=False)

    def _pag_prev(self):
        if not self._last_query_placa: return
        self._offset = max(0, self._offset - self._limit); self._buscar(reset=False)

    def _pag_next(self):
        if not self._last_query_placa: return
        nxt = self._offset + self._limit
        if self._last_total and nxt >= self._last_total: return
        self._offset = nxt; self._buscar(reset=False)

    # ══════════════════════════════════════════════════════════════
    # PLACAS
    # ══════════════════════════════════════════════════════════════
    def _listar_placas(self):
        self.lb_busca.config(text="⏳ Carregando placas...")
        self.e_placa.delete(0, "end"); self._last_query_placa = ""
        def task():
            resp = _cron_get("placas")
            for r in self.tree.get_children(): self.tree.delete(r)
            if not resp.get("status"):
                self.lb_busca.config(text="✖ Erro")
                messagebox.showerror("Erro", resp.get("error") or "Erro ao listar placas")
                return
            rows = resp.get("data") or []
            for p in rows:
                self.tree.insert("", "end", tags=("normal",), values=(
                    "—", _safe_str(p.get("placa")), f"{p.get('registros',0)} registros",
                    "—","—","—","—","—","—","—","—","—","—"
                ))
            self.lb_busca.config(text=f"{len(rows)} placas")
            self.lb_page.config(text="Página: —")
        threading.Thread(target=task, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # SELEÇÃO / DETALHE
    # ══════════════════════════════════════════════════════════════
    def _get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atenção", "Selecione um registro."); return None
        values = self.tree.item(sel[0])["values"]
        if not values or str(values[0]) == "—":
            messagebox.showwarning("Atenção", "Selecione uma manutenção (não uma placa)."); return None
        try: return int(values[0])
        except: return None

    def _ir_aba_detalhe(self):
        for i, tab in enumerate(self._nb.tabs()):
            if "Detalhe" in self._nb.tab(tab, "text"):
                self._nb.select(i); break

    def _ver_selecionada(self):
        mid = self._get_selected_id()
        if mid is None: return
        self._selected_id = mid
        self._carregar_detalhe(mid)
        self._ir_aba_detalhe()

    def _editar_selecionada(self):
        self._ver_selecionada()

    def _carregar_detalhe(self, mid):
        C = _get_C()
        _write(self.res_edit, "⏳ Carregando...", C["accent"])
        def task():
            resp = _cron_get(f"buscar/{mid}")
            if not resp.get("status"):
                _write(self.res_edit, f"✖ {resp.get('error','Erro ao buscar')}", C["danger"]); return
            m = resp.get("data", {}) or {}

            def set_e(key, val, readonly=False):
                e = self._edit_fields.get(key)
                if not e: return
                if str(e.cget("state")) == "readonly": e.config(state="normal")
                e.delete(0, "end"); e.insert(0, val)
                if readonly: e.config(state="readonly", fg=_get_C()["text_dim"])

            set_e("id",    _safe_str(m.get("id"),""),     readonly=True)
            set_e("placa", _safe_str(m.get("placa"),""),  readonly=True)
            set_e("situacao",      _safe_str(m.get("situacao"),""))
            set_e("quem_informou", _safe_str(m.get("quem_informou"),""))
            set_e("onde_esta",     _safe_str(m.get("onde_esta"),""))
            set_e("categoria",     _safe_str(m.get("categoria"),"Geral"))
            set_e("prioridade",    _safe_str(m.get("prioridade"),"Normal"))
            try:   set_e("custo", f"{float(m.get('custo',0)):.2f}")
            except: set_e("custo", "0")
            set_e("data_cadastro",  _fmt_dt_from_api(m.get("data_cadastro")).replace("—",""))
            set_e("previsao",       _fmt_date_from_api(m.get("previsao")).replace("—",""))
            set_e("data_conclusao", _fmt_date_from_api(m.get("data_conclusao")).replace("—",""))
            self._conc_var.set(bool(int(m.get("concluido",0) or 0)))
            self.t_edit_obs.delete("1.0","end")
            self.t_edit_obs.insert("1.0", _safe_str(m.get("observacoes"),"").replace("—",""))
            self.t_novo_status.delete("1.0","end")
            for r in self.tree_status.get_children(): self.tree_status.delete(r)
            resp_h = _cron_get(f"historico/{mid}")
            if resp_h.get("status"):
                for upd in (resp_h.get("data") or []):
                    self.tree_status.insert("","end", values=(
                        _fmt_dt_from_api(upd.get("criado_em")),
                        _safe_str(upd.get("autor")),
                        _safe_str(upd.get("texto")),
                    ))
            _write(self.res_edit, f"✔ Manutenção #{mid} carregada.", C["success"])
        threading.Thread(target=task, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # AÇÕES DO EDITOR
    # ══════════════════════════════════════════════════════════════
    def _salvar_edicao(self):
        C = _get_C()
        mid = self._selected_id
        if not mid:
            _write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"]); return
        body = {
            "situacao":       self._edit_fields["situacao"].get().strip(),
            "quem_informou":  self._edit_fields["quem_informou"].get().strip(),
            "onde_esta":      self._edit_fields["onde_esta"].get().strip(),
            "categoria":      self._edit_fields["categoria"].get().strip() or "Geral",
            "prioridade":     self._edit_fields["prioridade"].get().strip() or "Normal",
            "observacoes":    self.t_edit_obs.get("1.0","end").strip(),
            "data_cadastro":  _parse_dt_to_api(self._edit_fields["data_cadastro"].get()),
            "previsao":       _parse_date_to_api(self._edit_fields["previsao"].get()),
            "data_conclusao": _parse_date_to_api(self._edit_fields["data_conclusao"].get()),
            "concluido":      1 if self._conc_var.get() else 0,
        }
        custo_txt = self._edit_fields["custo"].get().strip().replace(",",".")
        try:    body["custo"] = float(custo_txt) if custo_txt else 0.0
        except: body["custo"] = 0.0
        novo_st = self.t_novo_status.get("1.0","end").strip()
        autor   = self.e_autor.get().strip() or "Sistema"
        if novo_st:
            body["novo_status"]   = novo_st
            body["status_atual"]  = novo_st
            body["quem_informou"] = autor
        _write(self.res_edit, "⏳ Salvando...", C["accent"])
        def task():
            resp, code = _cron_put(f"atualizar/{mid}", body)
            if resp.get("status") or code in (200, 201):
                _write(self.res_edit, f"✔ Atualizado! (#{mid})", C["success"])
                self._carregar_detalhe(mid)
            else:
                _write(self.res_edit, f"✖ {resp.get('error', f'Falha {code}')}", C["danger"])
        threading.Thread(target=task, daemon=True).start()

    def _add_status_from_editor(self):
        C = _get_C()
        mid = self._selected_id
        if not mid:
            _write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"]); return
        texto = self.t_novo_status.get("1.0","end").strip()
        if not texto:
            _write(self.res_edit, "⚠ Escreva um texto em 'Novo status'.", C["warn"]); return
        autor = self.e_autor.get().strip() or "Sistema"
        _write(self.res_edit, "⏳ Adicionando status...", C["accent"])
        def task():
            resp, code = _cron_post(f"add_status/{mid}", body={"texto": texto, "autor": autor})
            if resp.get("status") or code in (200, 201):
                _write(self.res_edit, f"✔ Status adicionado! (#{mid})", C["success"])
                self._carregar_detalhe(mid)
            else:
                _write(self.res_edit, f"✖ {resp.get('error', f'Falha {code}')}", C["danger"])
        threading.Thread(target=task, daemon=True).start()

    def _concluir_do_editor(self):
        mid = self._selected_id
        if not mid: return
        if not messagebox.askyesno("Confirmar", f"Concluir manutenção #{mid}?"): return
        def task():
            body = {"data_conclusao": datetime.now().strftime("%Y-%m-%d"), "quem_informou": "Sistema"}
            resp, code = _cron_put(f"concluir/{mid}", body)
            if resp.get("status") or code in (200,):
                self._carregar_detalhe(mid)
                if self.e_placa.get().strip(): self._buscar(reset=False)
            else:
                messagebox.showerror("Erro", resp.get("error") or f"Falha {code}")
        threading.Thread(target=task, daemon=True).start()

    def _deletar_atual(self):
        C = _get_C()
        mid = self._selected_id
        if not mid:
            _write(self.res_edit, "⚠ Nenhuma manutenção carregada.", C["warn"]); return
        if not messagebox.askyesno("Confirmar", f"Deletar permanentemente #{mid}?"): return
        def task():
            resp, code = _cron_delete(f"deletar/{mid}")
            if resp.get("status") or code in (200, 204):
                _write(self.res_edit, f"✔ Deletada (#{mid}).", C["success"])
                self._selected_id = None
                for k, e in self._edit_fields.items():
                    if str(e.cget("state")) == "readonly": e.config(state="normal")
                    e.delete(0,"end")
                    if k in ("id","placa"): e.config(state="readonly", fg=_get_C()["text_dim"])
                self.t_edit_obs.delete("1.0","end")
                self.t_novo_status.delete("1.0","end")
                for r in self.tree_status.get_children(): self.tree_status.delete(r)
                if self.e_placa.get().strip(): self._buscar(reset=False)
            else:
                _write(self.res_edit, f"✖ {resp.get('error', f'Falha {code}')}", C["danger"])
        threading.Thread(target=task, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # AÇÕES NA LISTA
    # ══════════════════════════════════════════════════════════════
    def _concluir_selecionada(self):
        mid = self._get_selected_id()
        if mid is None: return
        if not messagebox.askyesno("Confirmar", f"Marcar #{mid} como CONCLUÍDA?"): return
        def task():
            resp, code = _cron_put(f"concluir/{mid}", {"data_conclusao": datetime.now().strftime("%Y-%m-%d"), "quem_informou": "Sistema"})
            if resp.get("status") or code in (200,): self._buscar(reset=False)
            else: messagebox.showerror("Erro", resp.get("error") or f"Falha {code}")
        threading.Thread(target=task, daemon=True).start()

    def _deletar_selecionada(self):
        mid = self._get_selected_id()
        if mid is None: return
        if not messagebox.askyesno("Confirmar", f"Deletar permanentemente #{mid}?"): return
        def task():
            resp, code = _cron_delete(f"deletar/{mid}")
            if resp.get("status") or code in (200, 204): self._buscar(reset=False)
            else: messagebox.showerror("Erro", resp.get("error") or f"Falha {code}")
        threading.Thread(target=task, daemon=True).start()

    def _add_status_popup(self):
        mid = self._get_selected_id()
        if mid is None: return
        C = _get_C()
        win = tk.Toplevel(self)
        win.title(f"Adicionar Status — #{mid}")
        win.configure(bg=C["bg"])
        win.geometry("520x320")
        _lbl(win, f"Adicionar status — #{mid}", 11, True, C["accent"]).pack(anchor="w", padx=12, pady=(12,6))
        _lbl(win, "Autor:", 9, col=C["text_mid"]).pack(anchor="w", padx=12)
        e_aut = _ent(win); e_aut.pack(fill="x", padx=12, ipady=4); e_aut.insert(0, "Sistema")
        _lbl(win, "Texto:", 9, col=C["text_mid"]).pack(anchor="w", padx=12, pady=(10,2))
        t = tk.Text(win, height=6, bg=C["surface3"], fg=C["text"],
                    insertbackground=C["accent"], relief="flat",
                    font=("Helvetica Neue",10), padx=8, pady=6)
        t.pack(fill="both", expand=True, padx=12)
        fr, res = _txtbox(win, 2); fr.pack(fill="x", padx=12, pady=(8,4))
        def enviar():
            texto = t.get("1.0","end").strip()
            autor = e_aut.get().strip() or "Sistema"
            if not texto:
                _write(res, "⚠ Escreva o texto.", C["warn"]); return
            _write(res, "⏳ Enviando...", C["accent"])
            def task():
                resp, code = _cron_post(f"add_status/{mid}", body={"texto": texto, "autor": autor})
                if resp.get("status") or code in (200,201):
                    _write(res, "✔ Status adicionado!", C["success"])
                    if self.e_placa.get().strip(): self._buscar(reset=False)
                else:
                    _write(res, f"✖ {resp.get('error', f'Falha {code}')}", C["danger"])
            threading.Thread(target=task, daemon=True).start()
        row = tk.Frame(win, bg=C["bg"]); row.pack(padx=12, pady=8, anchor="e")
        _btn(row, "➕ ADICIONAR", enviar, C["purple"]).pack(side="left", padx=6)
        _btn(row, "FECHAR", win.destroy, C["surface2"], C["text_mid"]).pack(side="left")

    # ══════════════════════════════════════════════════════════════
    # CRIAR MANUTENÇÃO
    # ══════════════════════════════════════════════════════════════
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
        self.e_data_cad.insert(0, _now_ui_dt())
        _write(self.res_nova, "Campos limpos.", _get_C()["text_dim"])

    def _criar_manutencao(self):
        C = _get_C()
        placa    = self._nova_fields["placa"].get().strip().upper()
        situacao = self._nova_fields["situacao"].get().strip()
        if not placa or not situacao:
            _write(self.res_nova, "⚠ Placa e Situação são obrigatórios.", C["warn"]); return
        custo_txt = (self._nova_fields["custo"].get() or "").strip().replace(",",".")
        try:   custo = float(custo_txt) if custo_txt else 0.0
        except: custo = 0.0
        body = {
            "placa": placa, "situacao": situacao,
            "quem_informou": self._nova_fields["quem_informou"].get().strip(),
            "onde_esta":     self._nova_fields["onde_esta"].get().strip(),
            "data_cadastro": _parse_dt_to_api(self.e_data_cad.get()) or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "previsao":      _parse_date_to_api(self.e_previsao.get()),
            "data_conclusao": None, "concluido": 0,
            "categoria":  self._nova_fields["categoria"].get().strip() or "Geral",
            "prioridade": self._nova_fields["prioridade"].get().strip() or "Normal",
            "custo": custo,
            "observacoes":  self.t_obs.get("1.0","end").strip(),
            "status_atual": self.t_status_ini.get("1.0","end").strip(),
        }
        _write(self.res_nova, "⏳ Cadastrando...", C["accent"])
        def task():
            resp, code = _cron_post("criar", body=body)
            if resp.get("status") or code in (200, 201):
                mid = (resp.get("data") or {}).get("id", "?")
                _write(self.res_nova, f"✔ Manutenção #{mid} cadastrada!", C["success"])
                self._limpar_nova()
                if self.e_placa.get().strip().upper() == placa:
                    self._buscar(reset=True)
            else:
                _write(self.res_nova, f"✖ {resp.get('error', f'Falha {code}')}", C["danger"])
        threading.Thread(target=task, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # EXPORT CSV
    # ══════════════════════════════════════════════════════════════
    def _exportar_csv(self, modo="pagina"):
        from tkinter import filedialog
        import csv as csv_mod
        C = _get_C()
        placa = (self.e_placa.get().strip().upper() or self._last_query_placa).strip()
        if modo == "pagina" and not self._last_rows:
            messagebox.showinfo("Exportar", "Nenhum dado na página."); return
        if modo == "tudo" and not placa:
            messagebox.showinfo("Exportar", "Informe a placa e faça uma busca primeiro."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv"),("Todos","*.*")],
            initialfile=f"cronologia_{modo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not path: return
        cols = ["id","placa","situacao","data_cadastro","quem_informou","onde_esta",
                "status_atual","categoria","prioridade","custo","previsao","data_conclusao","concluido","observacoes"]
        def wrow(f, regs):
            w = csv_mod.writer(f, delimiter=";")
            for m in regs:
                w.writerow([_safe_str(m.get(c),"") for c in cols])
        if modo == "pagina":
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    csv_mod.writer(f, delimiter=";").writerow(cols)
                    wrow(f, self._last_rows)
                messagebox.showinfo("Exportar", f"Salvo:\n{path}")
            except Exception as e:
                messagebox.showerror("Exportar", str(e))
            return
        def task():
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    csv_mod.writer(f, delimiter=";").writerow(cols)
                    limit = 200; offset = 0; total = None
                    situ = self.cb_situ.get().strip()
                    concluido = None
                    if situ == "Abertos": concluido = 0
                    elif situ == "Concluídos": concluido = 1
                    while True:
                        params = {"placa": placa, "limit": limit, "offset": offset}
                        if concluido is not None: params["concluido"] = concluido
                        resp = _cron_get("listar", params)
                        if not resp.get("status"):
                            messagebox.showerror("Exportar", resp.get("error","Erro ao exportar")); return
                        data = resp.get("data",{}) or {}
                        regs = data.get("registros",[]) or []
                        total = int(data.get("total",0) or 0)
                        if not regs: break
                        wrow(f, regs)
                        offset += limit
                        if total and offset >= total: break
                messagebox.showinfo("Exportar", f"CSV completo salvo:\n{path}")
            except Exception as e:
                messagebox.showerror("Exportar", str(e))
        threading.Thread(target=task, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # STATS
    # ══════════════════════════════════════════════════════════════
    def _abrir_stats_da_placa(self):
        placa = self.e_placa.get().strip().upper() or self._last_query_placa
        if placa:
            self.e_stats_placa.delete(0,"end"); self.e_stats_placa.insert(0, placa)
        for i, tab in enumerate(self._nb.tabs()):
            if "Estat" in self._nb.tab(tab,"text"):
                self._nb.select(i); break
        self._carregar_stats()

    def _carregar_stats(self):
        C = _get_C()
        placa = self.e_stats_placa.get().strip().upper()
        self.lb_stats.config(text="⏳ Carregando...")
        _write(self.res_stats, "⏳ Buscando stats...", C["accent"])
        def task():
            params = {}
            if placa: params["placa"] = placa
            resp = _cron_get("stats", params)
            if not resp.get("status"):
                self.lb_stats.config(text="✖ Erro")
                _write(self.res_stats, f"✖ {resp.get('error','Erro stats')}", C["danger"]); return
            d = resp.get("data",{}) or {}
            try:   custo_fmt = f"R$ {float(d.get('custo_total',0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")
            except: custo_fmt = f"R$ {d.get('custo_total',0)}"
            self._card_total.config(text=f"Total: {d.get('total',0)}")
            self._card_conc.config(text=f"Concluídos: {d.get('concluidos',0)}")
            self._card_pend.config(text=f"Pendentes: {d.get('pendentes',0)}")
            self._card_urg.config(text=f"Urgentes: {d.get('urgentes',0)}")
            self._card_custo.config(text=f"Custo Total: {custo_fmt}")
            for r in self.tree_cat.get_children(): self.tree_cat.delete(r)
            for c in (d.get("por_categoria") or []):
                self.tree_cat.insert("","end", values=(_safe_str(c.get("categoria")), _safe_str(c.get("qtd"))))
            self.lb_stats.config(text=f"✔ OK ({'placa '+placa if placa else 'geral'})")
            _write(self.res_stats, f"✔ Stats carregado.\nBase: {'placa '+placa if placa else 'geral'}", C["success"])
        threading.Thread(target=task, daemon=True).start()