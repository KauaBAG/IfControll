"""
tabs/telemetria/sub_risco.py
Sub-aba 5 — Score de Risco.
Pontuação 0–100 composta de velocidade, ociosidade, GPS, voltagem e ciclos.
"""

import tkinter as tk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl
from ._calc import calc_risco, calc_percurso, calc_velocidade, calc_ociosidade, calc_motor


class RiscoMixin:

    def _build_risco(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" ⚠ Risco ")

        # Score + nível
        score_top = tk.Frame(f, bg=C["surface"])
        score_top.pack(fill="x")

        left = tk.Frame(score_top, bg=C["surface"])
        left.pack(side="left", padx=30, pady=20)
        lbl(left, "SCORE DE RISCO", 9, True, C["text_dim"],
            bg=C["surface"]).pack()
        self._score_num = tk.Label(
            left, text="—", bg=C["surface"], fg=C["accent"],
            font=("Helvetica Neue", 54, "bold"),
        )
        self._score_num.pack()
        lbl(left, "/ 100", 11, col=C["text_dim"], bg=C["surface"]).pack()

        mid = tk.Frame(score_top, bg=C["surface"])
        mid.pack(side="left", padx=20, pady=20)
        self._nivel_lbl = tk.Label(
            mid, text="—", bg=C["surface"], fg=C["text"],
            font=("Helvetica Neue", 22, "bold"),
        )
        self._nivel_lbl.pack(anchor="w")

        lbl(mid, "Interpretação:", 9, True, C["text_dim"],
            bg=C["surface"]).pack(anchor="w", pady=(10, 2))
        for faixa, nome, cor in [
            ("0 – 19",   "✅ BAIXO",   C["success"]),
            ("20 – 49",  "⚠️  MÉDIO",  C["warn"]),
            ("50 – 74",  "🔴 ALTO",    C["danger"]),
            ("75 – 100", "💀 CRÍTICO", C["danger"]),
        ]:
            row = tk.Frame(mid, bg=C["surface"])
            row.pack(anchor="w")
            lbl(row, faixa, 8, col=C["text_dim"], bg=C["surface"], width=8).pack(side="left")
            lbl(row, nome,  9, col=cor,            bg=C["surface"]).pack(side="left")

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Barra visual
        bw = tk.Frame(f, bg=C["bg"])
        bw.pack(fill="x", padx=14, pady=10)
        lbl(bw, "Nível de Risco:", 9, True, C["text_mid"]).pack(anchor="w")
        self._risk_bg   = tk.Frame(bw, bg=C["surface3"], height=22)
        self._risk_bg.pack(fill="x", pady=4)
        self._risk_fill = tk.Frame(self._risk_bg, bg=C["success"], height=22)
        self._risk_fill.place(x=0, y=0, relwidth=0)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        # Detalhes
        lbl(f, "Componentes do Score", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))
        self._risco_det_frame = tk.Frame(f, bg=C["bg"])
        self._risco_det_frame.pack(fill="x", padx=14)

        # Recomendações
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x", pady=(10, 0))
        lbl(f, "Recomendações Automáticas", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))
        self._recom_frame = tk.Frame(f, bg=C["bg"])
        self._recom_frame.pack(fill="x", padx=14, pady=(0, 12))

    def _render_risco(self, points: list[dict], limite_vel: int = 80):
        perc = calc_percurso(points)
        vel  = calc_velocidade(points, limite_vel)
        ocio = calc_ociosidade(points)
        mot  = calc_motor(points)
        risk = calc_risco(perc, vel, ocio, mot, points)

        score = risk["score"]
        cor   = C["success"] if score < 20 else (C["warn"] if score < 50 else C["danger"])

        self._score_num.config(text=str(score), fg=cor)
        self._nivel_lbl.config(text=risk["nivel"], fg=cor)

        # Barra
        self._risk_bg.update_idletasks()
        bw = self._risk_bg.winfo_width() or 400
        self._risk_fill.config(bg=cor)
        self._risk_fill.place(x=0, y=0, width=max(4, int(bw * score / 100)), height=22)

        # Detalhes
        for w in self._risco_det_frame.winfo_children():
            w.destroy()
        for det in risk["detalhes"]:
            lbl(self._risco_det_frame, det, 9, col=C["text"]).pack(anchor="w", pady=2)

        # Recomendações
        for w in self._recom_frame.winfo_children():
            w.destroy()
        for rec in self._montar_recomendacoes(risk, vel, ocio, mot):
            card = tk.Frame(self._recom_frame, bg=C["surface2"],
                            highlightthickness=1, highlightbackground=C["border"])
            card.pack(fill="x", pady=3)
            lbl(card, rec, 9, col=C["text"], bg=C["surface2"]).pack(
                padx=10, pady=7, anchor="w")

    @staticmethod
    def _montar_recomendacoes(risk: dict, vel: dict,
                               ocio: dict, mot: dict) -> list[str]:
        recs = []
        if vel.get("pct_acima_limite", 0) > 10:
            recs.append(
                "🚨 Mais de 10% do percurso acima do limite de velocidade. "
                "Recomenda-se treinamento de direção defensiva para o motorista."
            )
        if ocio.get("ocioso_h", 0) > 1:
            recs.append(
                f"⛽ {ocio['ocioso_h']}h de motor ligado parado. "
                "Orientar o motorista a desligar o motor em paradas longas (>5 min)."
            )
        if mot.get("volt_min", 12) > 0 and mot.get("volt_min", 12) < 11.5:
            recs.append(
                f"🔋 Voltagem mínima crítica detectada: {mot['volt_min']}V. "
                "Verificar estado da bateria e alternador com urgência."
            )
        if mot.get("ciclos_ignicao", 0) > 30:
            recs.append(
                f"🔑 Alto número de ciclos de ignição ({mot['ciclos_ignicao']}). "
                "Pode indicar uso inadequado do veículo ou falha de equipamento."
            )
        if risk["score"] < 20:
            recs.append(
                "✅ Comportamento exemplar no período. Baixo risco implica menor "
                "custo de manutenção, seguros e desgaste de componentes."
            )
        if not recs:
            recs.append(
                "📋 Nenhuma anomalia crítica detectada. "
                "Continue o monitoramento contínuo para garantir a tendência positiva."
            )
        return recs
