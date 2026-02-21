"""
tabs/clientes.py
Aba 6 — Clientes: listagem, cadastro, motoristas e contatos.
"""

import threading
import tkinter as tk
from tkinter import ttk

from utils.theme_manager import C
from utils.auto_refresh_export import now_str
from core import (
    get_clients_all, extract_list, api_get, api_put,
    safe_int, safe_str,
)
from widgets import (
    lbl, ent, btn, sec, txtbox, write, ok, err,
    mk_tree, mk_export_btn,
)


class TabClientes(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_lista(nb)
        self._tab_cadastrar(nb)
        self._tab_motoristas(nb)
        self._tab_contatos(nb)

    def _tab_lista(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Todos  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        cols = ("ID","Nome","Razão Social","Endereço","Cidade","UF","CNPJ","Tipo","Liberado")
        t = mk_tree(f, cols, (65,160,160,160,120,50,120,50,70), "Cli", C["pink"], 14)

        def load():
            lb.config(text="⏳...")
            def task():
                d = get_clients_all()
                for r in t.get_children(): t.delete(r)
                for c2 in d:
                    t.insert("","end", values=(
                        safe_str(c2.get("ras_cli_id")),    safe_str(c2.get("ras_cli_desc")),
                        safe_str(c2.get("ras_cli_razao")), safe_str(c2.get("ras_cli_endereco")),
                        safe_str(c2.get("ras_cli_cidade")),safe_str(c2.get("ras_cli_uf")),
                        safe_str(c2.get("ras_cli_cnpj")),  safe_str(c2.get("ras_cli_tipo")),
                        safe_str(c2.get("ras_cli_liberado")),
                    ))
                lb.config(text=f"{len(d)} clientes")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "⟳  CARREGAR", load, C["pink"]).pack(side="left")
        mk_export_btn(c, t).pack(side="left", padx=6)
        self.after(200, load)

    def _tab_cadastrar(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Cadastrar  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b, "NOVO CLIENTE")
        field_defs = [
            ("Nome*","ras_cli_desc"),("Tipo (F/J)*","ras_cli_tipo"),("Razão Social","ras_cli_razao"),
            ("Endereço","ras_cli_endereco"),("Bairro","ras_cli_bairro"),("CEP","ras_cli_cep"),
            ("UF","ras_cli_uf"),("Cidade","ras_cli_cidade"),("CNPJ/CPF","ras_cli_cnpj"),
        ]
        fd2 = {}
        for lab, key in field_defs:
            r = tk.Frame(b, bg=C["bg"]); r.pack(fill="x", pady=2)
            lbl(r, f"{lab}:", 9, col=C["text_mid"], width=18).pack(side="left", anchor="w")
            e = ent(r); e.pack(side="left", fill="x", expand=True, ipady=4)
            fd2[key] = e
        _, res2 = txtbox(b, 4); _.pack(fill="x", pady=(8,0))

        def cad():
            write(res2, "⏳...", C["accent"])
            def task():
                resp, code = api_put("/clients/save", {k: v.get() for k,v in fd2.items() if v.get().strip()})
                if resp.get("status") or code in (200,201):
                    d = extract_list(resp.get("data", resp))
                    ok(res2, f"Cliente criado! ID: {d[0].get('ras_cli_id','?') if d else '?'}")
                else:
                    err(res2, f"Falha {code}")
            threading.Thread(target=task, daemon=True).start()

        btn(b, "CADASTRAR", cad, C["green"]).pack(pady=(8,0))

    def _tab_motoristas(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Motoristas  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c, "ID Cliente:").pack(side="left")
        e3 = ent(c, w=12); e3.pack(side="left", padx=8, ipady=4)
        lb3 = lbl(c, "", col=C["text_dim"]); lb3.pack(side="right")
        t3 = mk_tree(f, ("ID Motorista","Nome","CPF","CNH"), (100,200,130,130), "Mot", C["yellow"], 14)

        def mot():
            cid = e3.get().strip()
            if not cid: return
            lb3.config(text="⏳...")
            def task():
                d = extract_list(api_get("/drivers", {"client": cid}).get("data",[]))
                for r in t3.get_children(): t3.delete(r)
                for m in d:
                    t3.insert("","end", values=(
                        safe_str(m.get("ras_mot_id")),   safe_str(m.get("ras_mot_nome")),
                        safe_str(m.get("ras_mot_cpf")),  safe_str(m.get("ras_mot_cnh")),
                    ))
                lb3.config(text=f"{len(d)} motoristas")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "BUSCAR", mot, C["yellow"]).pack(side="left")
        mk_export_btn(c, t3).pack(side="left", padx=6)

    def _tab_contatos(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Contatos  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c, "ID Cliente:").pack(side="left")
        e4 = ent(c, w=12); e4.pack(side="left", padx=8, ipady=4)
        lb4 = lbl(c, "", col=C["text_dim"]); lb4.pack(side="right")
        cols = ("ID","Nome","Telefone","Email","Email Alerta","SMS Alerta","Principal")
        t4 = mk_tree(f, cols, (70,160,120,180,90,90,80), "Cont", C["pink"], 12)

        def cont():
            cid = e4.get().strip()
            if not cid: return
            def task():
                d = extract_list(api_get(f"/contacts/single/id/{cid}").get("data",[]))
                for r in t4.get_children(): t4.delete(r)
                for c2 in d:
                    t4.insert("","end", values=(
                        safe_str(c2.get("ras_ccn_id")),       safe_str(c2.get("ras_ccn_contato")),
                        safe_str(c2.get("ras_ccn_telefone")), safe_str(c2.get("ras_ccn_email")),
                        "Sim" if safe_int(c2.get("ras_ccn_email_alerta")) else "Não",
                        "Sim" if safe_int(c2.get("ras_ccn_sms_alerta"))   else "Não",
                        "Sim" if safe_int(c2.get("ras_ccn_email_master")) else "Não",
                    ))
                lb4.config(text=f"{len(d)} contatos")
            threading.Thread(target=task, daemon=True).start()

        btn(c, "BUSCAR", cont, C["pink"]).pack(side="left")
        mk_export_btn(c, t4).pack(side="left", padx=6)