"""
tabs/veiculos.py
Aba 4 — Veículos: listagem, atualização, cadastro e instalação de rastreadores.
Importa lógica de core/ e componentes de widgets/.
"""

import threading
import tkinter as tk
from tkinter import ttk
from utils.theme_manager import C
from utils.auto_refresh_export import now_str
from core import (get_vehicles_all, find_vehicle, extract_list,
                  api_get, api_post, api_put, safe_int, safe_str, safe_float)
from widgets import lbl, ent, btn, sec, txtbox, write, loading, ok, err, mk_tree, mk_export_btn


class TabVeiculos(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_lista(nb)
        self._tab_atualizar(nb)
        self._tab_cadastrar(nb)
        self._tab_instalacao(nb)

    # ── Lista ─────────────────────────────────────────────────────────────────
    def _tab_lista(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Lista  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        cols = ("ID","Cli.","Placa","Veículo","Tipo","Fabricante","Ano","Cor","Veloc.Lim","Odômetro","Cadastro")
        t = mk_tree(f, cols, (65,65,85,140,55,90,55,70,90,90,130), "VL", C["blue"], 14)

        def load():
            lb.config(text="⏳...")
            def task():
                d = get_vehicles_all()
                for r in t.get_children(): t.delete(r)
                for v in d:
                    t.insert("","end", values=(
                        safe_str(v.get("ras_vei_id")),       safe_str(v.get("ras_vei_id_cli")),
                        safe_str(v.get("ras_vei_placa")),    safe_str(v.get("ras_vei_veiculo")),
                        safe_str(v.get("ras_vei_tipo")),     safe_str(v.get("ras_vei_fabricante")),
                        safe_str(v.get("ras_vei_ano")),      safe_str(v.get("ras_vei_cor")),
                        safe_str(v.get("ras_vei_velocidade_limite")),
                        safe_str(v.get("ras_vei_odometro")),
                        safe_str(v.get("ras_vei_data_cadastro")),
                    ))
                lb.config(text=f"{len(d)} veículos")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "⟳  CARREGAR", load, C["blue"]).pack(side="left")
        mk_export_btn(c, t).pack(side="left", padx=6)
        self.after(200, load)

    # ── Atualizar ─────────────────────────────────────────────────────────────
    def _tab_atualizar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Atualizar  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b, "ATUALIZAR VEÍCULO")
        rq = tk.Frame(b, bg=C["bg"]); rq.pack(fill="x", pady=4)
        lbl(rq, "Placa/nome:").pack(side="left")
        e_q = ent(rq, w=20); e_q.pack(side="left", padx=8, ipady=5)
        _f2, res = txtbox(b, 4); _f2.pack(fill="x", pady=(0, 8))

        field_defs = [
            ("Placa","ras_vei_placa"),("Descrição","ras_vei_veiculo"),("Chassi","ras_vei_chassi"),
            ("Ano","ras_vei_ano"),("Cor","ras_vei_cor"),("Veloc. Limite","ras_vei_velocidade_limite"),
            ("Odômetro","ras_vei_odometro"),("Horímetro","ras_vei_horimetro"),
        ]
        fields = {}
        for lab, key in field_defs:
            r = tk.Frame(b, bg=C["bg"]); r.pack(fill="x", pady=2)
            lbl(r, f"{lab}:", 9, col=C["text_mid"], width=14).pack(side="left", anchor="w")
            e = ent(r); e.pack(side="left", fill="x", expand=True, ipady=4)
            fields[key] = e

        def popular():
            q = e_q.get().strip()
            if not q: return
            loading(res)
            def task():
                ev = find_vehicle(q)
                if not ev: err(res, "Não encontrado."); return
                vid = safe_int(ev.get("ras_vei_id", 0))
                d = extract_list(api_get(f"/vehicles/single/id/{vid}").get("data",[]))
                v = d[0] if d else ev
                for k, e in fields.items():
                    e.delete(0,"end"); e.insert(0, safe_str(v.get(k,""), default=""))
                ok(res, f"Veículo {vid} carregado.")
            threading.Thread(target=task, daemon=True).start()

        def salvar():
            q = e_q.get().strip()
            if not q: return
            loading(res)
            def task():
                ev = find_vehicle(q)
                if not ev: err(res, "Não encontrado."); return
                vid = safe_int(ev.get("ras_vei_id", 0))
                resp, code = api_post(f"/vehicles/update/id/{vid}", {k: v.get() for k, v in fields.items()})
                if resp.get("status") or code in (200,201): ok(res, f"Veículo {vid} atualizado!")
                else: err(res, f"Falha {code}")
            threading.Thread(target=task, daemon=True).start()

        btn(rq, "CARREGAR", popular, C["accent"]).pack(side="left")
        btn(b, "💾  SALVAR", salvar, C["green"]).pack(pady=(8,0))

    # ── Cadastrar ─────────────────────────────────────────────────────────────
    def _tab_cadastrar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Cadastrar  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b, "CADASTRAR VEÍCULO")
        field_defs = [
            ("ID Cliente*","ras_vei_id_cli"),("Placa*","ras_vei_placa"),("Descrição*","ras_vei_veiculo"),
            ("Chassi","ras_vei_chassi"),("Ano","ras_vei_ano"),("Cor","ras_vei_cor"),
            ("Tipo","ras_vei_tipo"),("Modelo","ras_vei_modelo"),("Combustível","ras_vei_combustivel"),
            ("Consumo km/l","ras_vei_consumo"),("Veloc. Limite","ras_vei_velocidade_limite"),
            ("Odômetro","ras_vei_odometro"),
        ]
        fd3 = {}
        for lab, key in field_defs:
            r = tk.Frame(b, bg=C["bg"]); r.pack(fill="x", pady=2)
            lbl(r, f"{lab}:", 9, col=C["text_mid"], width=15).pack(side="left", anchor="w")
            e = ent(r); e.pack(side="left", fill="x", expand=True, ipady=4)
            fd3[key] = e
        _f3, res3 = txtbox(b, 4); _f3.pack(fill="x", pady=(8,0))

        def cadastrar():
            write(res3, "⏳ Cadastrando...", C["accent"])
            def task():
                resp, code = api_put("/vehicles/save", {k: v.get() for k,v in fd3.items() if v.get().strip()})
                if resp.get("status") or code in (200,201):
                    d = extract_list(resp.get("data", resp))
                    ok(res3, f"Veículo criado! ID: {d[0].get('ras_vei_id','?') if d else '?'}")
                else:
                    err(res3, f"Falha {code}")
            threading.Thread(target=task, daemon=True).start()

        btn(b, "CADASTRAR", cadastrar, C["green"]).pack(pady=(8,0))

    # ── Instalação ────────────────────────────────────────────────────────────
    def _tab_instalacao(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Instalação  ")
        nb4 = ttk.Notebook(f); nb4.pack(fill="both", expand=True)

        # Ativas
        fa = tk.Frame(nb4, bg=C["bg"]); nb4.add(fa, text="  Ativas  ")
        ca = tk.Frame(fa, bg=C["bg"]); ca.pack(fill="x", padx=8, pady=6)
        lba = lbl(ca, "", col=C["text_dim"]); lba.pack(side="right")
        ta = mk_tree(fa, ("Inst.ID","Aparelho","Veículo","Placa","Cliente"),
                     (100,130,160,90,160), "Inst", C["purple"], 12)

        def load_inst():
            def task():
                d = extract_list(api_get("/workshop/list").get("data",[]))
                for r in ta.get_children(): ta.delete(r)
                for i in d:
                    ta.insert("","end", values=(
                        safe_str(i.get("ras_ins_id")),   safe_str(i.get("ras_ras_id_aparelho")),
                        safe_str(i.get("ras_vei_veiculo")),safe_str(i.get("ras_vei_placa")),
                        safe_str(i.get("ras_cli_desc")),
                    ))
                lba.config(text=f"{len(d)} instalações")
            threading.Thread(target=task, daemon=True).start()

        btn(ca, "CARREGAR", load_inst, C["purple"]).pack(side="left")
        mk_export_btn(ca, ta).pack(side="left", padx=6)
        self.after(300, load_inst)

        # Vincular
        fb = tk.Frame(nb4, bg=C["bg"]); nb4.add(fb, text="  Vincular  ")
        bb = tk.Frame(fb, bg=C["bg"]); bb.pack(fill="both", expand=True, padx=20, pady=12)
        sec(bb, "VINCULAR VEÍCULO ↔ RASTREADOR")
        lbl(bb, "ID Veículo:",  col=C["text_mid"]).pack(anchor="w", pady=(4,2))
        e_vv = ent(bb); e_vv.pack(fill="x", ipady=5)
        lbl(bb, "ID Aparelho:", col=C["text_mid"]).pack(anchor="w", pady=(8,2))
        e_ap = ent(bb); e_ap.pack(fill="x", ipady=5)
        _, resv = txtbox(bb, 4); _.pack(fill="x", pady=(10,0))

        def vincular():
            write(resv,"⏳...", C["accent"])
            def task():
                resp, code = api_post("/workshop/install", {
                    "ras_vei_id": safe_int(e_vv.get()),
                    "ras_ras_id_aparelho": e_ap.get().strip(),
                })
                if resp.get("status") or code in (200,201): ok(resv,"Vinculado com sucesso!")
                else: err(resv, f"Falha {code}")
            threading.Thread(target=task, daemon=True).start()

        btn(bb, "VINCULAR", vincular, C["green"]).pack(pady=(8,0))

        # Desvincular
        fc = tk.Frame(nb4, bg=C["bg"]); nb4.add(fc, text="  Desvincular  ")
        bc = tk.Frame(fc, bg=C["bg"]); bc.pack(fill="both", expand=True, padx=20, pady=12)
        sec(bc, "DESVINCULAR POR ID DE INSTALAÇÃO")
        lbl(bc, "ras_ins_id:", col=C["text_mid"]).pack(anchor="w", pady=(4,2))
        e_ins = ent(bc); e_ins.pack(fill="x", ipady=5)
        _, resd = txtbox(bc, 4); _.pack(fill="x", pady=(10,0))

        def desvincular():
            write(resd,"⏳...", C["accent"])
            def task():
                resp, code = api_put("/workshop/uninstall", {"ras_ins_id": safe_int(e_ins.get())})
                if resp.get("status") or code in (200,201): ok(resd,"Desvinculado!")
                else: err(resd, f"Falha {code}")
            threading.Thread(target=task, daemon=True).start()

        btn(bc, "DESVINCULAR", desvincular, C["danger"]).pack(pady=(8,0))