"""
tabs/rastreadores.py — com suporte a tema dinâmico
"""
import threading, tkinter as tk
from tkinter import ttk
from collections import Counter
from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str
from core import (get_all_events, get_trackers_all, get_passengers_all, extract_list,
                  api_get, safe_int, safe_float, safe_str)
from widgets import lbl, ent, btn, mk_tree, mk_export_btn, FilterableTree
from widgets.alert_colors import _ac


class TabRastreadores(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_rastreadores(nb)
        self._tab_proximos(nb)
        self._tab_pontos_ref(nb)
        self._tab_passageiros(nb)
        self._tab_saude(nb)
        self._tab_ranking(nb)

    def _tab_rastreadores(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Rastreadores  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lb = lbl(c, "", col=C["text_dim"]); lb.pack(side="right")
        cols=("ID","Aparelho","Status","Produto","Cliente","Chip","Linha","Ult. Comunicação")
        t=mk_tree(f,cols,(65,120,65,80,80,110,100,160),"Rastr",C["orange"],14)
        def load():
            def task():
                d=get_trackers_all()
                for r in t.get_children(): t.delete(r)
                for tr in d:
                    t.insert("","end",values=(safe_str(tr.get("ras_ras_id")),safe_str(tr.get("ras_ras_id_aparelho")),
                        safe_str(tr.get("ras_ras_status")),safe_str(tr.get("ras_ras_prd_id")),
                        safe_str(tr.get("ras_ras_cli_id")),safe_str(tr.get("ras_ras_chip")),
                        safe_str(tr.get("ras_ras_linha")),safe_str(tr.get("ras_ras_data_ult_comunicacao"))))
                lb.config(text=f"{len(d)} rastreadores")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⟳  CARREGAR",load,C["orange"]).pack(side="left")
        mk_export_btn(c,t).pack(side="left",padx=6)
        self.after(200,load)

    def _tab_proximos(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Veículos Próximos  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"ID Cliente:").pack(side="left")
        e_cl=ent(c,w=10); e_cl.pack(side="left",padx=4,ipady=4)
        lbl(c,"  Lat:").pack(side="left")
        e_la=ent(c,w=14); e_la.pack(side="left",padx=4,ipady=4); e_la.insert(0,"-22.2154713")
        lbl(c,"  Lon:").pack(side="left")
        e_lo=ent(c,w=14); e_lo.pack(side="left",padx=4,ipady=4); e_lo.insert(0,"-49.6541367")
        lbl(c,"  Raio(m):").pack(side="left")
        e_r=ent(c,w=8); e_r.pack(side="left",padx=4,ipady=4); e_r.insert(0,"5000")
        lb2=lbl(c,"",col=C["text_dim"]); lb2.pack(side="right")
        cols=("Placa","Veículo","Tipo","Ign.","Vel.","Distância(m)","Data GPS","Lat","Lon")
        t2=mk_tree(f,cols,(80,130,60,60,60,110,150,110,110),"VPrx",C["green"],14)
        def prox():
            cid=e_cl.get().strip() or "0"; lat=e_la.get().strip(); lon=e_lo.get().strip()
            if not lat or not lon: return
            lb2.config(text="⏳...")
            def task():
                d=extract_list(api_get(f"/vehiclesnearby/nearpoint/id/{cid}/lat/{lat}/long/{lon}/limit/{e_r.get().strip() or '5000'}").get("data",[]))
                for r in t2.get_children(): t2.delete(r)
                for v in d:
                    loc=v.get("loc") or ["—","—"]
                    t2.insert("","end",values=(safe_str(v.get("ras_vei_placa")),safe_str(v.get("ras_vei_veiculo")),
                        safe_str(v.get("ras_vei_tipo")),"ON" if safe_int(v.get("ras_eve_ignicao")) else "OFF",
                        safe_str(v.get("ras_eve_velocidade")),safe_str(v.get("distancia")),
                        safe_str(v.get("ras_eve_data_gps")),str(loc[0]),str(loc[1])))
                lb2.config(text=f"{len(d)} veículos próximos | {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"BUSCAR",prox,C["green"]).pack(side="left",padx=8)
        mk_export_btn(c,t2).pack(side="left",padx=4)

    def _tab_pontos_ref(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Pontos de Ref.  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"ID Cliente (vazio=todos):").pack(side="left")
        e3=ent(c,w=12); e3.pack(side="left",padx=8,ipady=4)
        lb3=lbl(c,"",col=C["text_dim"]); lb3.pack(side="right")
        cols=("ID","Descrição","Lat","Lon","Ícone","Cidade","UF","Cadastro")
        t3=mk_tree(f,cols,(80,200,110,110,120,120,50,130),"PRef",C["accent"],14)
        def pts():
            cid=e3.get().strip()
            def task():
                d=extract_list((api_get(f"/referencepoints/client/id/{cid}") if cid else api_get("/referencepoints/all",{"limit":500,"offset":0})).get("data",[]))
                for r in t3.get_children(): t3.delete(r)
                for p in d:
                    t3.insert("","end",values=(safe_str(p.get("ras_ref_id")),safe_str(p.get("ras_ref_descricao")),
                        safe_str(p.get("ras_ref_latitude")),safe_str(p.get("ras_ref_longitude")),
                        safe_str(p.get("ras_ref_icone")),safe_str(p.get("ras_ref_cidade")),
                        safe_str(p.get("ras_ref_uf")),safe_str(p.get("ras_ref_data_cadastro"))))
                lb3.config(text=f"{len(d)} pontos")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"BUSCAR",pts,C["accent"]).pack(side="left")
        mk_export_btn(c,t3).pack(side="left",padx=6)

    def _tab_passageiros(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Passageiros  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb4=lbl(c,"",col=C["text_dim"]); lb4.pack(side="right")
        cols=("ID","Nome","RFID","Empresa","Setor","Cargo","Cadastro")
        t4=mk_tree(f,cols,(70,160,100,140,100,120,150),"Pass",C["accent2"],14)
        def pass_load():
            from core import get_passengers_all
            def task():
                d=get_passengers_all()
                for r in t4.get_children(): t4.delete(r)
                for p in d:
                    t4.insert("","end",values=(safe_str(p.get("ras_pas_id")),safe_str(p.get("ras_pas_nome")),
                        safe_str(p.get("ras_pas_rfid")),safe_str(p.get("ras_pas_empresa")),
                        safe_str(p.get("ras_pas_setor")),safe_str(p.get("ras_pas_cargo")),
                        safe_str(p.get("ras_pas_data_cadastro"))))
                lb4.config(text=f"{len(d)} passageiros")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⟳  CARREGAR",pass_load,C["accent2"]).pack(side="left")
        mk_export_btn(c,t4).pack(side="left",padx=6)
        self.after(400,pass_load)

    def _tab_saude(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Saúde da Frota  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb5=lbl(c,"",col=C["text_dim"]); lb5.pack(side="right")
        cols=("Placa","Veículo","Bat.%","Voltagem","GPS","Satél.","Ign.","Última GPS")
        self._t_saude=mk_tree(f,cols,(90,130,70,80,70,60,60,150),"Sau",C["warn"],14)
        # Tags adaptativas
        def _tags_saude():
            self._t_saude.tag_configure("al",background=_ac("al"))
            self._t_saude.tag_configure("ok",background=C["surface2"])
        _tags_saude(); register_theme_listener(_tags_saude)
        def saude():
            lb5.config(text="⏳...")
            def task():
                d=get_all_events(); al=0
                for r in self._t_saude.get_children(): self._t_saude.delete(r)
                for ev in d:
                    bat=safe_int(ev.get("ras_eve_porc_bat_backup",100))
                    volt=safe_float(ev.get("ras_eve_voltagem",0))
                    gps=safe_int(ev.get("ras_eve_gps_status",0))
                    ign=safe_int(ev.get("ras_eve_ignicao",0))
                    tag="al" if bat<30 or volt==0 or not gps else "ok"
                    if tag=="al": al+=1
                    self._t_saude.insert("","end",values=(safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                        f"{bat}%",f"{volt:.1f}V","✓ OK" if gps else "✗ FALHA",
                        safe_int(ev.get("ras_eve_satelites",0)),"ON" if ign else "OFF",
                        safe_str(ev.get("ras_eve_data_gps"))),tags=(tag,))
                lb5.config(text=f"Total: {len(d)}  |  ⚠ Alertas: {al}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⟳  ATUALIZAR",saude,C["warn"]).pack(side="left")
        mk_export_btn(c,self._t_saude).pack(side="left",padx=6)
        self.after(300,saude)

    def _tab_ranking(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Ranking Motoristas  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb6=lbl(c,"",col=C["text_dim"]); lb6.pack(side="right")
        cols=("Pos.","Motorista","Veículos","Vel.Máx","Vel.Méd","Score/100")
        self._t_rank=mk_tree(f,cols,(50,180,80,100,100,90),"Rank",C["yellow"],14)
        def _tags_rank():
            self._t_rank.tag_configure("t",background=_ac("al2"))
            self._t_rank.tag_configure("n",background=C["surface2"])
        _tags_rank(); register_theme_listener(_tags_rank)
        def rank():
            lb6.config(text="⏳ Calculando...")
            def task():
                data=get_all_events(); mots={}
                for ev in data:
                    nm=safe_str(ev.get("ras_mot_nome"),"Desconhecido")
                    vel=abs(safe_int(ev.get("ras_eve_velocidade",0))); pl=safe_str(ev.get("ras_vei_placa"))
                    if nm not in mots: mots[nm]={"v":set(),"vels":[]}
                    mots[nm]["v"].add(pl)
                    if vel>0: mots[nm]["vels"].append(vel)
                rk=[]
                for nm,d in mots.items():
                    vs=d["vels"]; vmx=max(vs) if vs else 0; vmd=sum(vs)/len(vs) if vs else 0
                    sc=max(0,100-max(0,vmx-80)//2-int(max(0,vmd-60)))
                    rk.append((nm,len(d["v"]),vmx,vmd,sc))
                rk.sort(key=lambda x:x[4],reverse=True)
                for r in self._t_rank.get_children(): self._t_rank.delete(r)
                medals=["🥇","🥈","🥉"]
                for i,(nm,nv,vmx,vmd,sc) in enumerate(rk,1):
                    self._t_rank.insert("","end",values=(medals[i-1] if i<=3 else f"#{i}",
                        nm,nv,f"{vmx} km/h",f"{vmd:.1f} km/h",f"{sc}"),tags=("t" if i<=3 else "n",))
                lb6.config(text=f"{len(rk)} motoristas")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"🏆 CALCULAR",rank,C["yellow"]).pack(side="left")
        mk_export_btn(c,self._t_rank).pack(side="left",padx=6)
        self.after(400,rank)