"""
tabs/cercas.py
Aba 3 — Geofences: listagem, eventos por cliente, criar e deletar cercas.
"""

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from utils.theme_manager import C
from utils.auto_refresh_export import now_str, ts
from core import get_fences_all, extract_list, api_get, api_put, api_del, safe_int, safe_str
from widgets import lbl, ent, btn, sec, txtbox, write, ok, err, mk_tree, mk_export_btn
from widgets.helpers import interval_row


class TabCercas(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_listar(nb)
        self._tab_eventos(nb)
        self._tab_criar(nb)
        self._tab_deletar(nb)

    def _tab_listar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Todas as Cercas  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        cols = ("ID","Cliente","Nome","Ativa","Cor","Início","Fim","Veículos")
        t = mk_tree(f, cols, (70,80,180,60,80,80,80,200), "Fenc", C["green"], 14)

        def load():
            lb.config(text="⏳...")
            def task():
                d = get_fences_all()
                for r in t.get_children(): t.delete(r)
                for fc in d:
                    veics = ",".join(str(v) for v in (fc.get("ras_vei_id") or []))
                    t.insert("","end", values=(
                        safe_str(fc.get("fence_id")),
                        safe_str(fc.get("ras_vei_id_cli")),
                        safe_str(fc.get("ras_cer_observacao")),
                        "Sim" if fc.get("is_active") else "Não",
                        safe_str(fc.get("color")),
                        safe_str(fc.get("start_time")),
                        safe_str(fc.get("end_time")),
                        veics[:50] or "—",
                    ))
                lb.config(text=f"{len(d)} cercas | {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "⟳  CARREGAR", load, C["green"]).pack(side="left")
        mk_export_btn(c, t).pack(side="left", padx=6)
        self.after(300, load)

    def _tab_eventos(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Eventos por Cliente  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c, "ID Cliente:").pack(side="left")
        e_cli = ent(c, w=10); e_cli.pack(side="left", padx=4, ipady=4)
        lbl(c, "  Início:").pack(side="left")
        ei = ent(c, w=16); ei.pack(side="left", padx=4, ipady=4)
        from utils.auto_refresh_export import fmt_hours_ago
        ei.insert(0, fmt_hours_ago(8))
        lbl(c, "  Fim:").pack(side="left")
        ef = ent(c, w=16); ef.pack(side="left", padx=4, ipady=4)
        ef.insert(0, datetime.now().strftime("%d/%m/%Y %H:%M"))
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        cols = ("ID Veículo","Placa","Veículo","Cerca","Entrada","Saída","Permanência")
        t = mk_tree(f, cols, (80,80,130,180,140,140,110), "FencE", C["green"], 14)

        def buscar():
            lb.config(text="⏳...")
            def task():
                try:
                    ini = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                except Exception:
                    lb.config(text="⚠ Datas inválidas"); return
                cli = e_cli.get().strip() or "0"
                d = extract_list(api_get(f"/fence/client/id/{cli}/initial/{ts(ini)}/final/{ts(fim)}").get("data",[]))
                for r in t.get_children(): t.delete(r)
                for ev in d:
                    t.insert("","end", values=(
                        safe_str(ev.get("ras_vei_id")),     safe_str(ev.get("ras_vei_placa")),
                        safe_str(ev.get("ras_vei_veiculo")),safe_str(ev.get("ras_cer_observacao")),
                        safe_str(ev.get("data_entrada")),    safe_str(ev.get("data_saida")),
                        safe_str(ev.get("tempo_permanencia")),
                    ))
                lb.config(text=f"{len(d)} eventos | {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "BUSCAR", buscar, C["green"]).pack(side="left", padx=8)
        mk_export_btn(c, t).pack(side="left", padx=4)

    def _tab_criar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Criar Cerca  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b, "NOVA CERCA VIRTUAL")
        lbl(b, "Nome da cerca:", col=C["text_mid"]).pack(anchor="w", pady=(4,2))
        e_nm = ent(b); e_nm.pack(fill="x", ipady=5)
        rr = tk.Frame(b, bg=C["bg"]); rr.pack(fill="x", pady=6)
        lbl(rr, "ID Cliente:").pack(side="left")
        e_cl = ent(rr, w=12); e_cl.pack(side="left", padx=6, ipady=5)
        lbl(rr, "  Cor:").pack(side="left")
        e_cr = ent(rr, w=12); e_cr.pack(side="left", padx=6, ipady=5); e_cr.insert(0,"#00C8F8")
        lbl(b, "IDs dos veículos (vírgula):", col=C["text_mid"]).pack(anchor="w", pady=(8,2))
        e_vs = ent(b); e_vs.pack(fill="x", ipady=5)
        lbl(b, "Coordenadas (lat,lon — uma por linha):", col=C["text_mid"]).pack(anchor="w", pady=(8,2))
        _, t_co = txtbox(b, 5); _.pack(fill="x"); t_co.config(state="normal")
        t_co.insert("end","-22.195034,-49.676055\n-22.203934,-49.571685\n-22.295449,-49.665069")
        _fr, res = txtbox(b, 4); _fr.pack(fill="x", pady=(8,0))

        def criar():
            write(res, "⏳ Criando...", C["accent"])
            def task():
                veics  = [safe_int(v.strip()) for v in e_vs.get().split(",") if v.strip()]
                coords = []
                for ln in t_co.get("1.0","end").strip().split("\n"):
                    pp = ln.strip().split(",")
                    if len(pp) == 2: coords.append([pp[0].strip(), pp[1].strip()])
                payload = {
                    "ras_cer_observacao": e_nm.get().strip(),
                    "ras_vei_id_cli":     safe_int(e_cl.get()),
                    "color":              e_cr.get().strip() or "blue",
                    "is_active":          True,
                    "ras_vei_id":         veics,
                    "contacts_id":        [],
                    "coordinates":        coords,
                    "start_time":         "00:00:00",
                    "end_time":           "23:59:59",
                    "group_id":           0,
                    "days_active": {d: True for d in
                                   ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]},
                    "shipping_settings": {
                        "send_alert_email": False, "send_alert_client": True,
                        "send_alert_mobile": False, "send_alert_fullarm": False,
                        "send_alert_in_screen": True, "send_alert_monitoring": False,
                    },
                    "generate_alerts": {
                        "ignition_on": False, "ignition_off": False,
                        "inside_fence": True, "outside_fence": True,
                        "speed_limit":            {"is_active": False, "limit": 0},
                        "time_inside_fence":      {"is_active": False, "time": "00:00:00"},
                        "time_outside_fence":     {"is_active": False, "time": "00:00:00"},
                        "time_on":                {"is_active": False, "time": "00:00:00"},
                        "time_off":               {"is_active": False, "time": "00:00:00"},
                    },
                }
                resp, code = api_put("/fence/save", payload)
                if resp.get("status") or code in (200, 201):
                    ok(res, f"Cerca criada! HTTP {code}")
                else:
                    err(res, f"Falha {code}\n{json.dumps(resp, indent=2)}")
            threading.Thread(target=task, daemon=True).start()

        btn(b, "CRIAR CERCA", criar, C["green"]).pack(pady=(10, 0))

    def _tab_deletar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Deletar  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=16)
        sec(b, "DELETAR CERCA")
        lbl(b, "fence_id:", col=C["text_mid"]).pack(anchor="w", pady=(4,2))
        e_fid = ent(b); e_fid.pack(fill="x", ipady=5)
        _f4, res4 = txtbox(b, 4); _f4.pack(fill="x", pady=(12, 0))

        def deletar():
            fid = e_fid.get().strip()
            if not fid:
                write(res4, "⚠ Informe o ID.", C["warn"]); return
            if not messagebox.askyesno("Confirmar","Deletar permanentemente?", parent=self):
                return
            def task():
                resp, code = api_del(f"/fence/delete/id/{fid}")
                if resp.get("status") or code in (200, 204):
                    ok(res4, f"Cerca {fid} deletada!")
                else:
                    err(res4, f"Falha {code}")
            threading.Thread(target=task, daemon=True).start()

        btn(b, "DELETAR", deletar, C["danger"]).pack(pady=(12, 0))