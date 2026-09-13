"""
tabs/alertas.py
Aba 2 — Alertas abertos, por período, fechar alerta e tipos.
"""

import json
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from utils.theme_manager import C
from utils.auto_refresh_export import fmt_hours_ago, fmt_now_default, now_str, ts
from core import get_alerts_all, get_alert_types, extract_list, api_get, api_post, safe_int, safe_str
from widgets import lbl, ent, btn, sec, txtbox, write, loading, err, ok, mk_tree, mk_export_btn


class TabAlertas(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_abertos(nb)
        self._tab_periodo(nb)
        self._tab_fechar(nb)
        self._tab_tipos(nb)

    def _tab_abertos(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Alertas Abertos  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        t  = mk_tree(f, ("ID Veículo","Descrição","Data","Tipo ID","Lat","Lon"),
                     (90,220,150,70,110,110), "Aler", C["danger"], 14)

        def load():
            lb.config(text="⏳...")
            def task():
                d = get_alerts_all()
                for r in t.get_children(): t.delete(r)
                for a in d:
                    t.insert("","end", values=(
                        safe_str(a.get("ras_eal_id_veiculo")),
                        safe_str(a.get("ras_eal_descricao")),
                        safe_str(a.get("ras_eal_data_alerta")),
                        safe_str(a.get("ras_eal_id_alerta_tipo")),
                        safe_str(a.get("ras_eal_latitude")),
                        safe_str(a.get("ras_eal_longitude")),
                    ))
                lb.config(text=f"{len(d)} alertas | {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "⟳  ATUALIZAR", load, C["danger"]).pack(side="left")
        mk_export_btn(c, t).pack(side="left", padx=6)
        self.after(300, load)

    def _tab_periodo(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Por Período  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c, "Início:").pack(side="left")
        ei = ent(c, w=18); ei.pack(side="left", padx=4, ipady=4); ei.insert(0, fmt_hours_ago(7))
        lbl(c, "  Fim:").pack(side="left")
        ef = ent(c, w=18); ef.pack(side="left", padx=4, ipady=4); ef.insert(0, fmt_now_default())
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        t  = mk_tree(f, ("ID Veículo","Descrição","Data","Baixado","Motivo","Obs","Lat","Lon"),
                     (90,180,140,70,130,160,110,110), "AlerP", C["warn"], 14)

        def buscar():
            lb.config(text="⏳...")
            def task():
                try:
                    ini = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                except Exception:
                    lb.config(text="⚠ Datas inválidas"); return
                d = extract_list(api_get(f"/alerts/period/initial/{ts(ini)}/final/{ts(fim)}").get("data",[]))
                for r in t.get_children(): t.delete(r)
                for a in d:
                    t.insert("","end", values=(
                        safe_str(a.get("ras_eal_id_veiculo")),
                        safe_str(a.get("ras_eal_descricao")),
                        safe_str(a.get("ras_eal_data_alerta")),
                        "Sim" if safe_int(a.get("ras_eal_baixado")) else "Não",
                        safe_str(a.get("ras_eal_descricao_motivo")),
                        safe_str(a.get("ras_eal_obs")),
                        safe_str(a.get("ras_eal_latitude")),
                        safe_str(a.get("ras_eal_longitude")),
                    ))
                lb.config(text=f"{len(d)} alertas | {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "BUSCAR", buscar, C["warn"]).pack(side="left", padx=8)
        mk_export_btn(c, t).pack(side="left", padx=4)

    def _tab_fechar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Fechar Alerta  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=16)
        sec(b, "FECHAR ALERTA")
        lbl(b, "ID do Alerta:",    col=C["text_mid"]).pack(anchor="w", pady=(4, 2))
        e_id  = ent(b); e_id.pack(fill="x", ipady=5)
        lbl(b, "Motivo (número):", col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        e_mot = ent(b); e_mot.pack(fill="x", ipady=5)
        lbl(b, "Observação:",      col=C["text_mid"]).pack(anchor="w", pady=(10, 2))
        e_obs = ent(b); e_obs.pack(fill="x", ipady=5)
        _f, res = txtbox(b, 5); _f.pack(fill="x", pady=(12, 0))

        def fechar():
            aid = e_id.get().strip()
            if not aid:
                write(res, "⚠ Informe o ID.", C["warn"]); return
            write(res, "⏳ Enviando...", C["accent"])
            def task():
                resp, code = api_post(f"/alerts/close/id/{aid}", {
                    "ras_eal_motivo": safe_int(e_mot.get() or 0),
                    "ras_eal_obs":    e_obs.get().strip(),
                })
                if resp.get("status"):
                    ok(res, f"Alerta {aid} fechado! HTTP {code}")
                else:
                    err(res, f"Falha HTTP {code}\n{json.dumps(resp, indent=2)}")
            threading.Thread(target=task, daemon=True).start()

        btn(b, "FECHAR ALERTA", fechar, C["danger"]).pack(pady=(12, 0))
        mk_export_btn(b, res, is_text=True).pack(pady=(6, 0))

    def _tab_tipos(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Tipos  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        t  = mk_tree(f, ("ID","Descrição"), (70, 340), "AlerT", C["orange"], 14)

        def load():
            def task():
                d = get_alert_types()
                for r in t.get_children(): t.delete(r)
                for a in d:
                    t.insert("","end", values=(
                        safe_str(a.get("ras_eat_id")),
                        safe_str(a.get("ras_eat_descricao")),
                    ))
                lb.config(text=f"{len(d)} tipos")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "CARREGAR", load, C["orange"]).pack(side="left")
        mk_export_btn(c, t).pack(side="left", padx=6)
        self.after(400, load)