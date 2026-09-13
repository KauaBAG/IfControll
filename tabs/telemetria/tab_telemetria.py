"""
tabs/telemetria/tab_telemetria.py
Aba de Telemetria — orquestrador principal.

Correções aplicadas:
  BUG 1 — Períodos longos (7d) sem dados:
    A API retorna vazio para janelas grandes. Solução: chunking automático —
    qualquer período > CHUNK_THRESHOLD_H é dividido em fatias de CHUNK_MIN minutos
    e consolidado com dedup por _id / ras_eve_data_gps.

  BUG 2 — Segunda busca não atualiza a tabela:
    Thread anterior ainda em execução chamava self.after() depois da nova thread,
    sobrescrevendo os dados corretos com os antigos. Solução: _search_token (int)
    incrementado a cada busca. Cada thread captura o token no início; o callback
    só executa se o token ainda corresponder ao atual.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import auto_refresh_register, fmt_hours_ago, fmt_now_default
from core.api import get_all_events, extract_list
from core.models import safe_int, safe_float, safe_str

from widgets.primitives import lbl, ent, btn, apply_treeview_style
from widgets.filtercombo import FilterableCombobox

from ._api import (
    get_telemetry, get_events_interval,
    get_vehicle_single, get_fence_vehicle, to_ts,
    DEFAULT_VEL_LIMITE,
    get_telemetry_vehicle,           # ← adicionar
    merge_telemetry_into_points,     # ← adicionar
)

from .sub_percurso   import PercursoMixin
from .sub_velocidade import VelocidadeMixin
from .sub_ociosidade import OciosidadeMixin
from .sub_motor      import MotorMixin
from .sub_risco      import RiscoMixin
from .sub_consumo    import ConsumoMixin
from .sub_cercas     import CercasMixin
from .sub_resumo         import ResumoMixin
from .sub_motor_avancado import MotorAvancadoMixin
from .sub_bateria        import BateriaMixin
from .sub_comparativo    import ComparativoMixin


# ── Parâmetros de chunking ────────────────────────────────────────────────────
# Qualquer janela maior que este valor usa busca fragmentada.
CHUNK_THRESHOLD_H = 2        # horas — acima disso, divide em fatias
CHUNK_SIZE_MIN    = 60       # minutos por fatia


# Número de threads paralelas para busca de chunks
CHUNK_WORKERS = 8


def _fetch_chunked(vei_id, begin_ts: int, end_ts: int,
                   progress_cb=None) -> list[dict]:
    """
    Busca eventos em fatias de CHUNK_SIZE_MIN minutos, em paralelo.
    - CHUNK_WORKERS threads simultâneas reduzem o tempo de 7d de ~50s para ~6s.
    - Chunks sem dados ou com erro são ignorados silenciosamente.
    - progress_cb(n_pontos, chunks_prontos, total_chunks) atualiza a UI.
    """
    chunk_sec = CHUNK_SIZE_MIN * 60

    # Gera lista de (begin, end) para cada fatia
    windows = []
    cur = begin_ts
    while cur < end_ts:
        nxt = min(cur + chunk_sec, end_ts)
        windows.append((cur, nxt))
        cur = nxt

    total_chunks  = len(windows)
    all_points:   list[dict] = []
    seen:         set        = set()
    completed     = 0
    lock          = threading.Lock()

    def fetch_window(win):
        b, e = win
        try:
            return get_events_interval(vei_id, b, e)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=CHUNK_WORKERS) as pool:
        futures = {pool.submit(fetch_window, w): w for w in windows}
        for fut in as_completed(futures):
            chunk = fut.result() or []
            with lock:
                for p in chunk:
                    uid = p.get("_id") or p.get("ras_eve_data_gps") or id(p)
                    if uid not in seen:
                        seen.add(uid)
                        all_points.append(p)
                completed += 1
                if progress_cb:
                    progress_cb(len(all_points), completed, total_chunks)

    # Ordena por timestamp GPS para manter ordem cronológica
    all_points.sort(key=lambda p: p.get("ras_eve_data_gps", ""))
    return all_points


class TabTelemetria(
    PercursoMixin, VelocidadeMixin, OciosidadeMixin,
    MotorMixin, RiscoMixin, ConsumoMixin, CercasMixin, ResumoMixin,
    MotorAvancadoMixin, BateriaMixin, ComparativoMixin,
    tk.Frame,
):
    """
    Aba completa de Telemetria com 8 sub-abas de análise de frota.
    Fonte principal: GET /events/interval  (telemetry instável — descartado)
    """

    def __init__(self, master):
        super().__init__(master, bg=C["bg"])

        # Estado compartilhado
        self._vei_map:          dict        = {}
        self._cached_points:    list[dict]  = []
        self._cached_fences:    list[dict]  = []
        self._current_vei:      dict        = {}
        self._ocio_consumo_l_h: float       = 0.5
        self._granularity_sec: int          = 0   # 0 = todos os pontos

        # ── Token de busca — FIX BUG 2 ───────────────────────────────────────
        # Incrementado a cada _buscar(). Threads antigas verificam antes de
        # chamar _on_data e descartam o resultado se o token mudou.
        self._search_token: int = 0

        self._build()
        auto_refresh_register("telemetria_vehicles", self._reload_vehicles)
        register_theme_listener(self._reapply_styles)
        self.after(600, self._reload_vehicles)

    # ── Recoloração global de tema ────────────────────────────────────────────

    def _reapply_styles(self):
        for name, col in [
            ("TPerc",      C["blue"]),
            ("TVel",       C["warn"]),
            ("TOcio",      C["warn"]),
            ("TMotor",     C["accent"]),
            ("TCerca",     C["accent"]),
            ("TCercaDet",  C["blue"]),
            ("TResumExp",  C["accent"]),
        ]:
            try:
                apply_treeview_style(name, col)
            except Exception:
                pass

    # ── KPI helper compartilhado ──────────────────────────────────────────────

    def _tele_kpi(self, parent, title: str, val: str, col: str) -> tk.Label:
        f = tk.Frame(parent, bg=C["surface"])
        f.pack(side="left", padx=14, pady=8)
        tk.Label(
            f, text=title,
            bg=C["surface"], fg=C["text_dim"],
            font=("Helvetica Neue", 7, "bold"),
        ).pack()
        v_lbl = tk.Label(
            f, text=val,
            bg=C["surface"], fg=col,
            font=("Helvetica Neue", 14, "bold"),
        )
        v_lbl.pack()

        def recolor():
            try:
                f.config(bg=C["surface"])
                f.winfo_children()[0].config(bg=C["surface"], fg=C["text_dim"])
                v_lbl.config(bg=C["surface"])
            except Exception:
                pass

        register_theme_listener(recolor)
        return v_lbl

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_selector()
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")
        self._build_subnotebook()

    # ── Painel de seleção (topo) ──────────────────────────────────────────────

    def _build_selector(self):
        sel = tk.Frame(self, bg=C["surface3"])
        sel.pack(fill="x")

        lbl(sel, "🛰  TELEMETRIA", 11, True, C["accent"],
            bg=C["surface3"]).pack(side="left", padx=14, pady=10)
        tk.Frame(sel, bg=C["border"], width=1).pack(side="left", fill="y", pady=6)

        # Veículo
        lbl(sel, "Veículo:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=(12, 4), pady=10)
        self._cb_vei = FilterableCombobox(
            sel, values=["⏳ Carregando..."], width=30,
            font=("Helvetica Neue", 9),
        )
        self._cb_vei.pack(side="left", padx=4, pady=8)
        self._cb_vei.bind("<<ComboboxSelected>>", self._on_vei_select)
        tk.Frame(sel, bg=C["border"], width=1).pack(side="left", fill="y", pady=6)

        # Período
        lbl(sel, "Início:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=(12, 4))
        self._e_inicio = ent(sel, w=16)
        self._e_inicio.pack(side="left", ipady=3, padx=4)
        self._e_inicio.insert(0, fmt_hours_ago(8))

        lbl(sel, "Fim:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=(8, 4))
        self._e_fim = ent(sel, w=16)
        self._e_fim.pack(side="left", ipady=3, padx=4)
        self._e_fim.insert(0, fmt_now_default())

        # Atalhos de período
        atalhos = tk.Frame(sel, bg=C["surface3"])
        atalhos.pack(side="left", padx=6)
        for txt, horas in [("1h", 1), ("8h", 8), ("24h", 24), ("3d", 72), ("7d", 168)]:
            btn(atalhos, txt,
                lambda h=horas: self._set_periodo(h),
                C["surface2"], C["text_mid"], px=6, py=3).pack(side="left", padx=2)

        btn(sel, "🔍  BUSCAR", self._buscar,
            C["accent"], px=14, py=6).pack(side="left", padx=10)

        tk.Frame(sel, bg=C["border"], width=1).pack(side="left", fill="y", pady=6)

        # Granularidade da tabela
        lbl(sel, "Tabela a cada:", 9, col=C["text_mid"],
            bg=C["surface3"]).pack(side="left", padx=(8, 4))
        self._gran_var = tk.StringVar(value="Todos")
        gran_opts = ["Todos", "1 min", "5 min", "15 min", "30 min", "1 hora"]
        gran_cb = ttk.Combobox(
            sel, textvariable=self._gran_var,
            values=gran_opts, width=8, state="readonly",
            font=("Helvetica Neue", 9),
        )
        gran_cb.pack(side="left", padx=4, pady=8)
        gran_cb.bind("<<ComboboxSelected>>", self._on_gran_change)

        tk.Frame(sel, bg=C["border"], width=1).pack(side="left", fill="y", pady=6)

        self._status_lbl = lbl(sel, "Pronto.", 8, col=C["text_dim"], bg=C["surface3"])
        self._status_lbl.pack(side="left", padx=10)
        self._pts_lbl = lbl(sel, "", 9, col=C["accent"], bg=C["surface3"])
        self._pts_lbl.pack(side="right", padx=14)

    # ── Sub-notebook ──────────────────────────────────────────────────────────

    def _build_subnotebook(self):
        st = ttk.Style()
        st.configure("TelNB.TNotebook", background=C["bg"], borderwidth=0)
        st.configure("TelNB.TNotebook.Tab",
                     background=C["surface2"], foreground=C["text_mid"],
                     font=("Helvetica Neue", 9), padding=[8, 6])
        st.map("TelNB.TNotebook.Tab",
               background=[("selected", C["surface3"])],
               foreground=[("selected", C["accent"])])

        self._nb = ttk.Notebook(self, style="TelNB.TNotebook")
        self._nb.pack(fill="both", expand=True)

        def _recolor_nb():
            try:
                st.configure("TelNB.TNotebook", background=C["bg"])
                st.configure("TelNB.TNotebook.Tab",
                             background=C["surface2"], foreground=C["text_mid"])
                st.map("TelNB.TNotebook.Tab",
                       background=[("selected", C["surface3"])],
                       foreground=[("selected", C["accent"])])
            except Exception:
                pass
        register_theme_listener(_recolor_nb)

        self._build_percurso(self._nb)
        self._build_velocidade(self._nb)
        self._build_ociosidade(self._nb)
        self._build_motor(self._nb)
        self._build_risco(self._nb)
        self._build_consumo(self._nb)
        self._build_cercas(self._nb)
        self._build_resumo(self._nb)
        self._build_motor_avancado(self._nb)
        self._build_bateria(self._nb)
        self._build_comparativo(self._nb)

    # ── Carregamento de veículos ──────────────────────────────────────────────

    def _reload_vehicles(self):
        def task():
            events = get_all_events()
            self.after(0, lambda: self._on_vehicles_loaded(events))
        threading.Thread(target=task, daemon=True).start()

    def _on_vehicles_loaded(self, events: list[dict]):
        self._vei_map = {}
        seen: set = set()
        for ev in events:
            vid   = ev.get("ras_vei_id")
            placa = safe_str(ev.get("ras_vei_placa"))
            nome  = safe_str(ev.get("ras_vei_veiculo"))
            cli   = safe_str(ev.get("ras_cli_desc"))
            if vid and placa not in ("—",) and vid not in seen:
                seen.add(vid)
                key = f"{placa} — {nome} ({cli})"
                self._vei_map[key] = {"id": vid, "ev": ev}

        values = sorted(self._vei_map.keys())
        self._cb_vei["values"] = values
        if values:
            self._status_lbl.config(
                text=f"✔ {len(values)} veículos carregados.", fg=C["success"]
            )

    def _on_vei_select(self, _e=None):
        key = self._cb_vei.get()
        info = self._vei_map.get(key, {})
        self._current_vei = info.get("ev", {})

    # ── Atalhos de período ────────────────────────────────────────────────────

    def _set_periodo(self, horas: int):
        fim    = datetime.now()
        inicio = fim - timedelta(hours=horas)
        self._e_inicio.delete(0, "end")
        self._e_inicio.insert(0, inicio.strftime("%d/%m/%Y %H:%M"))
        self._e_fim.delete(0, "end")
        self._e_fim.insert(0, fim.strftime("%d/%m/%Y %H:%M"))

    # ── Granularidade da tabela ──────────────────────────────────────────────────

    _GRAN_MAP = {
        "Todos":   0,
        "1 min":   60,
        "5 min":   300,
        "15 min":  900,
        "30 min":  1800,
        "1 hora":  3600,
    }

    def _on_gran_change(self, _e=None):
        """Usuário mudou a granularidade — re-renderiza a tabela de percurso sem rebuscar."""
        self._granularity_sec = self._GRAN_MAP.get(self._gran_var.get(), 0)
        if self._cached_points:
            sampled = self._sample_points(self._cached_points)
            self._render_percurso(sampled)

    def _sample_points(self, points: list[dict]) -> list[dict]:
        """
        Filtra pontos mantendo no máximo 1 por janela de _granularity_sec.
        Se granularity == 0, retorna todos.
        """
        if not self._granularity_sec or not points:
            return points

        from ._api import to_ts as _to_ts_fn
        from datetime import datetime

        result      = []
        last_bucket = None

        for p in points:
            raw = p.get("ras_eve_data_gps", "")
            # Tenta converter data GPS em timestamp para calcular bucket
            ts = None
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    ts = int(datetime.strptime(str(raw).strip(), fmt).timestamp())
                    break
                except ValueError:
                    continue

            if ts is None:
                # Sem timestamp válido — inclui sempre
                result.append(p)
                continue

            bucket = ts // self._granularity_sec
            if bucket != last_bucket:
                result.append(p)
                last_bucket = bucket

        return result

    # ── Busca principal ───────────────────────────────────────────────────────

    def _buscar(self):
        key  = self._cb_vei.get()
        info = self._vei_map.get(key)
        if not info:
            self._status_lbl.config(text="⚠ Selecione um veículo.", fg=C["warn"])
            return

        vei_id   = info["id"]
        begin_ts = to_ts(self._e_inicio.get())
        end_ts   = to_ts(self._e_fim.get())

        if end_ts <= begin_ts:
            self._status_lbl.config(text="⚠ Período inválido.", fg=C["warn"])
            return

        # FIX BUG 2: incrementa token — threads antigas com token antigo são ignoradas
        self._search_token += 1
        my_token = self._search_token

        duracao_h = (end_ts - begin_ts) / 3600
        usar_chunk = duracao_h > CHUNK_THRESHOLD_H

        self._status_lbl.config(
            text=f"⏳ Buscando {duracao_h:.1f}h"
                 + (" em fatias..." if usar_chunk else "..."),
            fg=C["accent"],
        )
        self._pts_lbl.config(text="")

        def _progress(n: int, chunk_i: int, chunk_total: int):
            if self._search_token == my_token:
                self.after(0, lambda: (
                    self._pts_lbl.config(text=f"⏳ {n:,} pts"),
                    self._status_lbl.config(
                        text=f"⏳ Fatiando... {chunk_i}/{chunk_total}",
                        fg=C["accent"],
                    ),
                ))

        def task():
            try:
                # FIX BUG 1: chunking automático para períodos longos
                if usar_chunk:
                    points = _fetch_chunked(vei_id, begin_ts, end_ts,
                                            progress_cb=_progress)
                else:
                    # Para períodos curtos: tenta telemetry, cai em interval
                    points = get_telemetry(vei_id, begin_ts, end_ts)
                    if not points:
                        points = get_events_interval(vei_id, begin_ts, end_ts)

                vei_meta = get_vehicle_single(vei_id) or info.get("ev", {})
                fences   = get_fence_vehicle(vei_id, begin_ts, end_ts)

                from .sub_motor_avancado import MotorAvancadoMixin  # já herdado
                tel_points = get_telemetry_vehicle(vei_id, begin_ts, end_ts)
                if tel_points:
                    points = merge_telemetry_into_points(points, tel_points)

            except Exception as exc:
                # Erro de rede/API — avisa na UI se ainda for a busca atual
                if self._search_token == my_token:
                    self.after(0, lambda: self._status_lbl.config(
                        text=f"❌ Erro: {exc}", fg=C["danger"]
                    ))
                return

            # FIX BUG 2: só despacha para a UI se este token ainda é o mais recente
            if self._search_token == my_token:
                self.after(0, lambda: self._on_data(
                    points, vei_meta, fences, my_token
                ))

        threading.Thread(target=task, daemon=True).start()

    # ── Callback da main thread ───────────────────────────────────────────────

    def _on_data(self, points: list[dict], vei_meta: dict,
                 fences: list[dict], token: int):
        """
        Recebe dados da thread e distribui para todas as sub-abas.
        FIX BUG 2: verifica token antes de qualquer operação para descartar
        resultados de buscas que já foram superadas por uma nova.
        """
        if token != self._search_token:
            # Esta busca foi cancelada por uma mais recente — descarta silenciosamente
            return

        if not points:
            self._status_lbl.config(
                text="⚠ Nenhum dado retornado. Verifique o período ou conectividade.",
                fg=C["warn"],
            )
            self._pts_lbl.config(text="0 pontos")
            return

        self._cached_points = points
        self._cached_fences = fences
        self._current_vei   = vei_meta

        limite_vel = (
            safe_int(vei_meta.get("ras_vei_velocidade_limite", 0)) or DEFAULT_VEL_LIMITE
        )

        n = len(points)
        self._status_lbl.config(text=f"✔ Dados carregados.", fg=C["success"])
        self._pts_lbl.config(text=f"{n:,} pontos")

        # Amostra pontos para a tabela conforme granularidade escolhida
        sampled = self._sample_points(points)
        n_sampled = len(sampled)
        if n_sampled < n:
            self._pts_lbl.config(text=f"{n:,} pontos  |  tabela: {n_sampled:,}")

        # Renderiza cada sub-aba dentro de try/except para não travar caso
        # uma falhe (ex.: dados inesperados de sensor).
        for render_fn, args in [
            (self._render_percurso,   (sampled,)),
            (self._render_velocidade, (points, limite_vel)),
            (self._render_ociosidade, (points,)),
            (self._render_motor,      (points,)),
            (self._render_risco,      (points, limite_vel)),
            (self._render_consumo,    (points,)),
            (self._render_cercas,     (fences,)),
            (self._render_resumo,       (points, vei_meta, limite_vel)),
            (self._render_motor_avancado, (points,)),
            (self._render_bateria,        (points,)),
        ]:
            try:
                render_fn(*args)
            except Exception as exc:
                print(f"[telemetria] render error in {render_fn.__name__}: {exc}")