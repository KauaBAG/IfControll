"""
tabs/telemetria/sub_motor.py
Sub-aba 4 — Motor e Bateria.
Voltagem, ciclos de ignição, tempo ligado/desligado, sensores de temperatura.
"""

import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C, register_theme_listener
from widgets.primitives import lbl, apply_treeview_style
from widgets.helpers import mk_export_btn
from ._calc import calc_motor, calc_temperatura

_COLS_IGN   = ("Data/Hora", "Evento")
_WIDTHS_IGN = (155, 120)


class MotorMixin:

    def _build_motor(self, nb):
        f = tk.Frame(nb, bg=C["bg"])
        nb.add(f, text=" 🔋 Motor/Bateria ")

        # KPI bar
        kbar = tk.Frame(f, bg=C["surface"])
        kbar.pack(fill="x")
        self._mkpis: dict[str, tk.Label] = {}
        for key, title, col in [
            ("ligado",   "TEMPO LIGADO",   C["success"]),
            ("deslig",   "DESLIGADO",      C["text_mid"]),
            ("ciclos",   "CICLOS IGN.",    C["accent"]),
            ("volt_med", "VOLT MÉDIA",     C["blue"]),
            ("volt_min", "VOLT MÍNIMA",    C["warn"]),
            ("volt_max", "VOLT MÁXIMA",    C["success"]),
            ("bat",      "BAT MÉDIA %",    C["accent"]),
        ]:
            self._mkpis[key] = self._tele_kpi(kbar, title, "—", col)

        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")

        content = tk.Frame(f, bg=C["bg"])
        content.pack(fill="both", expand=True)

        # Esquerda: histórico de ignição
        left = tk.Frame(content, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True)

        lbl(left, "Histórico de Ignição", 10, True,
            C["accent"]).pack(anchor="w", padx=14, pady=(8, 4))

        apply_treeview_style("TMotor", C["accent"])
        inner_l = tk.Frame(left, bg=C["bg"])
        inner_l.pack(fill="both", expand=True)

        self._tree_ign = ttk.Treeview(
            inner_l, columns=_COLS_IGN, show="headings",
            style="TMotor.Treeview", height=18,
        )
        for c, w in zip(_COLS_IGN, _WIDTHS_IGN):
            self._tree_ign.heading(c, text=c, anchor="w")
            self._tree_ign.column(c, width=w, anchor="w", stretch=True)

        vsb = ttk.Scrollbar(inner_l, orient="vertical", command=self._tree_ign.yview)
        self._tree_ign.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree_ign.pack(fill="both", expand=True)
        mk_export_btn(left, self._tree_ign).pack(anchor="e", padx=8, pady=4)

        # Direita: temperatura
        right = tk.Frame(content, bg=C["surface2"], width=270)
        right.pack(side="right", fill="y", padx=(4, 0))
        right.pack_propagate(False)

        lbl(right, "Sensores de Temperatura", 10, True,
            C["accent"], bg=C["surface2"]).pack(padx=10, pady=(10, 6), anchor="w")

        self._temp_frame   = tk.Frame(right, bg=C["surface2"])
        self._temp_frame.pack(fill="x", padx=10)
        self._temp_no_data = lbl(right, "Sem dados de temperatura\nnesta consulta.",
                                 9, col=C["text_dim"], bg=C["surface2"])
        self._temp_no_data.pack(pady=20)

        register_theme_listener(lambda: apply_treeview_style("TMotor", C["accent"]))

    def _render_motor(self, points: list[dict]):
        m = calc_motor(points)

        self._mkpis["ligado"].config(  text=f"{m['ligado_h']}h")
        self._mkpis["deslig"].config(  text=f"{m['desligado_h']}h")
        self._mkpis["ciclos"].config(  text=str(m["ciclos_ignicao"]))
        self._mkpis["volt_med"].config(text=f"{m['volt_media']}V")
        self._mkpis["volt_min"].config(text=f"{m['volt_min']}V",
                                       fg=C["danger"] if 0 < m["volt_min"] < 11.5 else C["warn"])
        self._mkpis["volt_max"].config(text=f"{m['volt_max']}V")
        self._mkpis["bat"].config(     text=f"{m['bat_media']}%")

        for r in self._tree_ign.get_children():
            self._tree_ign.delete(r)
        for ev in m["historico_ign"]:
            tag = "liga" if "LIGOU" in ev["evento"] else "desl"
            self._tree_ign.insert("", "end", tags=(tag,), values=(
                ev["data"], ev["evento"],
            ))
        self._tree_ign.tag_configure("liga", foreground=C["success"])
        self._tree_ign.tag_configure("desl", foreground=C["text_mid"])

        # Temperatura
        t = calc_temperatura(points)
        for w in self._temp_frame.winfo_children():
            w.destroy()

        if t["disponivel"]:
            self._temp_no_data.pack_forget()
            for canal, nome in [("digital_1", "Digital 1 (°C)"),
                                 ("analog_1",  "Analógico 1 (°C)"),
                                 ("analog_2",  "Analógico 2 (°C)")]:
                st = t.get(canal)
                if not st:
                    continue
                sec = tk.Frame(self._temp_frame, bg=C["surface3"],
                               highlightthickness=1, highlightbackground=C["border"])
                sec.pack(fill="x", pady=4)
                lbl(sec, nome, 9, True, C["accent"],
                    bg=C["surface3"]).pack(padx=8, pady=(6, 2), anchor="w")
                for k, v in [("Mín", st["min"]), ("Máx", st["max"]),
                             ("Média", st["media"]), ("Amostras", st["n"])]:
                    row = tk.Frame(sec, bg=C["surface3"])
                    row.pack(fill="x", padx=8, pady=1)
                    lbl(row, f"{k}:", 9, col=C["text_mid"], bg=C["surface3"],
                        width=8).pack(side="left")
                    lbl(row, str(v), 9, col=C["text"], bg=C["surface3"]).pack(side="left")
                lbl(sec, "", 1, bg=C["surface3"]).pack()  # spacer
        else:
            self._temp_no_data.pack(pady=20)
