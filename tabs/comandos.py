"""
tabs/comandos.py
Aba 8 — Comandos diretos, status, lista disponível, paginação e auditoria.
"""

import json
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from utils.theme_manager import C
from utils.auto_refresh_export import now_str, ts, parse_dt
from core import (
    find_vehicle, extract_list, api_get, api_post,
    safe_int, safe_str, safe_float,
)
from widgets import (
    lbl, ent, btn, sec, txtbox, write, loading, ok, err,
    mk_tree, mk_export_btn,
)


class TabComandos(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_enviar(nb)
        self._tab_status(nb)
        self._tab_lista(nb)
        self._tab_paginacao(nb)
        self._tab_auditoria(nb)

    def _tab_enviar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Enviar Comando  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b, "ENVIAR COMANDO DIRETO AO APARELHO")
        lbl(b, "ID do Aparelho (ras_ras_id_aparelho):", col=C["text_mid"]).pack(anchor="w", pady=(4,2))
        e_ap = ent(b); e_ap.pack(fill="x", ipady=5)
        lbl(b, "String do comando:", col=C["text_mid"]).pack(anchor="w", pady=(8,2))
        e_cmd = ent(b); e_cmd.pack(fill="x", ipady=5)
        lbl(b, "Descrição:", col=C["text_mid"]).pack(anchor="w", pady=(8,2))
        e_desc = ent(b); e_desc.pack(fill="x", ipady=5)
        _, res = txtbox(b, 6); _.pack(fill="x", pady=(12,0))

        def enviar():
            if not e_ap.get().strip() or not e_cmd.get().strip():
                write(res, "⚠ Preencha aparelho e comando.", C["warn"]); return
            write(res, "⏳ Enviando...", C["accent"])
            def task():
                resp, code = api_post("/commands/direct", {
                    "ras_ras_id_aparelho": e_ap.get().strip(),
                    "comando_string":      e_cmd.get().strip(),
                    "comando_descricao":   e_desc.get().strip(),
                })
                if resp.get("status") or code in (200,201):
                    d = extract_list(resp.get("data", resp))
                    ok(res, f"Enviado! ID comando: {d[0].get('ras_com_id','?') if d else '?'}")
                else:
                    err(res, f"Falha {code}\n{json.dumps(resp, indent=2)}")
            threading.Thread(target=task, daemon=True).start()

        btn(b, "⚡  ENVIAR", enviar, C["danger"]).pack(pady=(10,0))
        mk_export_btn(b, res, is_text=True).pack(pady=(6,0))

    def _tab_status(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Status Comando  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b, "STATUS DO COMANDO ENVIADO")
        lbl(b, "ID do Comando:", col=C["text_mid"]).pack(anchor="w", pady=(4,2))
        e2 = ent(b); e2.pack(fill="x", ipady=5)
        _, res2 = txtbox(b, 12); _.pack(fill="both", expand=True, pady=(12,0))

        def status():
            cid = e2.get().strip()
            if not cid: return
            loading(res2)
            def task():
                d = extract_list(api_get(f"/commands/status/id/{cid}").get("data",[]))
                if not d: err(res2, "Não encontrado."); return
                lines = ["="*44]
                for k, v in d[0].items():
                    lines.append(f"  {k:30s}: {safe_str(v)}")
                lines.append("="*44)
                write(res2, "\n".join(lines))
            threading.Thread(target=task, daemon=True).start()

        btn(b, "CONSULTAR STATUS", status, C["accent"]).pack(pady=(10,0))
        mk_export_btn(b, res2, is_text=True).pack(pady=(6,0))

    def _tab_lista(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Comandos Disponíveis  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c, "ID Produto:").pack(side="left")
        e3 = ent(c, w=12); e3.pack(side="left", padx=8, ipady=4)
        lb3 = lbl(c, "", col=C["text_dim"]); lb3.pack(side="right")
        t3 = mk_tree(f, ("ID Cmd","Descrição"), (100,400), "CmdL", C["accent"], 14)

        def cmd_list():
            pid = e3.get().strip()
            if not pid: return
            def task():
                d = extract_list(api_get(f"/commands/list/id/{pid}").get("data",[]))
                for r in t3.get_children(): t3.delete(r)
                for c4 in d:
                    t3.insert("","end", values=(
                        safe_str(c4.get("ras_stc_id")),
                        safe_str(c4.get("ras_stc_descricao")),
                    ))
                lb3.config(text=f"{len(d)} comandos")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "LISTAR", cmd_list, C["accent"]).pack(side="left")
        mk_export_btn(c, t3).pack(side="left", padx=6)

    def _tab_paginacao(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Paginação de Eventos  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c, "Página:").pack(side="left")
        e4 = ent(c, w=5); e4.pack(side="left", padx=4, ipady=4); e4.insert(0,"1")
        lbl(c, "  Por página:").pack(side="left")
        e4b = ent(c, w=5); e4b.pack(side="left", padx=4, ipady=4); e4b.insert(0,"50")
        lb4 = lbl(c, "", col=C["text_dim"]); lb4.pack(side="right")
        cols = ("Placa","Motorista","Data GPS","Vel.","Ign.","GPS","Lat","Lon")
        t4 = mk_tree(f, cols, (90,130,150,70,60,60,120,120), "Pag", C["accent2"], 13)

        def buscar4():
            lb4.config(text="⏳...")
            def task():
                try: pg=int(e4.get()); pp=int(e4b.get())
                except: pg=1; pp=50
                resp = api_get("/events/pagination", {"page":pg,"per_page":pp})
                d    = resp.get("data",{})
                evs  = d.get("eventos",[]) if isinstance(d,dict) else extract_list(d)
                tpg  = d.get("pages",["?"])[0] if isinstance(d,dict) and d.get("pages") else resp.get("pages","?")
                for r in t4.get_children(): t4.delete(r)
                for ev in evs:
                    t4.insert("","end", values=(
                        safe_str(ev.get("ras_vei_placa")),  safe_str(ev.get("ras_mot_nome")),
                        safe_str(ev.get("ras_eve_data_gps")),
                        f"{safe_int(ev.get('ras_eve_velocidade',0))} km/h",
                        "ON" if safe_int(ev.get("ras_eve_ignicao")) else "OFF",
                        "✓" if safe_int(ev.get("ras_eve_gps_status")) else "✗",
                        safe_str(ev.get("ras_eve_latitude")),safe_str(ev.get("ras_eve_longitude")),
                    ))
                lb4.config(text=f"Pg {pg}/{tpg}  |  {len(evs)} eventos  |  {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        def prev4():
            try: p=max(1,int(e4.get())-1)
            except: p=1
            e4.delete(0,"end"); e4.insert(0,str(p)); buscar4()

        def next4():
            try: p=int(e4.get())+1
            except: p=2
            e4.delete(0,"end"); e4.insert(0,str(p)); buscar4()

        c4b = tk.Frame(f, bg=C["bg"]); c4b.pack(fill="x", padx=8, pady=(0,4))
        btn(c4b,"◀ ANTERIOR",prev4,C["surface3"],C["text"]).pack(side="left")
        btn(c4b,"  BUSCAR  ",buscar4,C["accent2"]).pack(side="left",padx=4)
        btn(c4b,"PRÓXIMA ▶",next4,C["surface3"],C["text"]).pack(side="left")
        mk_export_btn(c4b, t4).pack(side="left", padx=8)
        self.after(200, buscar4)

    def _tab_auditoria(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Auditoria  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c, "Placa/nome:").pack(side="left")
        e5 = ent(c, w=16); e5.pack(side="left", padx=6, ipady=4)
        lbl(c, "  Início:").pack(side="left")
        ei5 = ent(c, w=16); ei5.pack(side="left", padx=4, ipady=4)
        ei5.insert(0, (datetime.now()-timedelta(hours=4)).strftime("%d/%m/%Y %H:%M"))
        lbl(c, "  Fim:").pack(side="left")
        ef5 = ent(c, w=16); ef5.pack(side="left", padx=4, ipady=4)
        ef5.insert(0, datetime.now().strftime("%d/%m/%Y %H:%M"))
        lb5 = lbl(c, "", col=C["text_dim"]); lb5.pack(side="right")
        cols = ("Seq","Data GPS","Vel.","Ign.","GPS","Satél.","Volt.","Lat","Lon")
        t5 = mk_tree(f, cols, (50,150,80,60,60,60,80,120,120), "Aud", C["text_mid"], 14)

        def audit():
            q = e5.get().strip()
            if not q: lb5.config(text="⚠ Informe a placa."); return
            lb5.config(text="⏳...")
            def task():
                entry = find_vehicle(q)
                if not entry: lb5.config(text="✖ Não encontrado."); return
                vid = safe_int(entry.get("ras_vei_id",0))
                try:
                    ini = datetime.strptime(ei5.get().strip(),"%d/%m/%Y %H:%M")
                    fim = datetime.strptime(ef5.get().strip(),"%d/%m/%Y %H:%M")
                except: lb5.config(text="⚠ Datas inválidas."); return
                evs = extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                for r in t5.get_children(): t5.delete(r)
                for i, ev in enumerate(evs, 1):
                    t5.insert("","end", values=(
                        i, safe_str(ev.get("ras_eve_data_gps")),
                        f"{safe_int(ev.get('ras_eve_velocidade',0))} km/h",
                        "ON" if safe_int(ev.get("ras_eve_ignicao")) else "OFF",
                        "✓" if safe_int(ev.get("ras_eve_gps_status")) else "✗",
                        safe_int(ev.get("ras_eve_satelites",0)),
                        f"{safe_float(ev.get('ras_eve_voltagem',0)):.1f}V",
                        safe_str(ev.get("ras_eve_latitude")),safe_str(ev.get("ras_eve_longitude")),
                    ))
                lb5.config(text=f"{entry.get('ras_vei_placa','—')}  |  {len(evs)} eventos  |  {now_str()}")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "🔍  BUSCAR", audit, C["accent2"]).pack(side="left", padx=8)
        mk_export_btn(c, t5).pack(side="left", padx=4)