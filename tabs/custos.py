"""
tabs/custos.py
Aba 12 — Centro de Custos: custo por veículo (período),
          ranking por motorista e configuração de parâmetros.
"""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, ts
from core import (
    get_all_events, find_vehicle, extract_list, api_get, api_put,
    safe_int, safe_float, safe_str, haversine, hms,
)
from widgets.alert_colors import _ac
from widgets import (
    lbl, ent, btn, sec, txtbox, write, loading, ok, err,
    mk_export_btn, interval_row, FilterableTree,
)


class TabCustos(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_custo_veiculo(nb)
        self._tab_ranking(nb)
        self._tab_parametros(nb)

    # ── Custo por Veículo ─────────────────────────────────────────────────────
    def _tab_custo_veiculo(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  💰 Custo por Veículo  ")
        ph = tk.Frame(f, bg=C["bg"]); ph.pack(fill="x", padx=8, pady=6)
        lbl(ph,"Veículo (placa/nome):",9,col=C["text_mid"]).pack(anchor="w",pady=(0,2))
        e_v=ent(ph); e_v.pack(fill="x",ipady=5)
        ei,ef=interval_row(ph)
        rp=tk.Frame(ph,bg=C["bg"]); rp.pack(fill="x",pady=4)
        lbl(rp,"Preço combustível R$/L:",9,col=C["text_mid"],width=24).pack(side="left",anchor="w")
        e_preco=ent(rp,w=8); e_preco.pack(side="left",padx=4,ipady=4); e_preco.insert(0,"6.20")
        lbl(rp,"  Consumo km/L:",9,col=C["text_mid"]).pack(side="left")
        e_cons=ent(rp,w=8); e_cons.pack(side="left",padx=4,ipady=4); e_cons.insert(0,"10.0")
        lbl(rp,"  Custo/h motorista R$:",9,col=C["text_mid"]).pack(side="left")
        e_mot=ent(rp,w=8); e_mot.pack(side="left",padx=4,ipady=4); e_mot.insert(0,"25.0")
        _,res=txtbox(f,18); _.pack(fill="both",expand=True,padx=8,pady=4)

        def custo_veiculo():
            q=e_v.get().strip()
            if not q: return
            loading(res)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res,"Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
                    preco=float(e_preco.get()); cons=float(e_cons.get()); custo_h=float(e_mot.get())
                except: write(res,"⚠ Parâmetros inválidos.",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res,"ℹ Nenhum evento.",C["text_mid"]); return
                km=0.0; t_on=t_off=t_ocio=0.0; vmax=0; prev=None
                for ev in evs:
                    vel=safe_int(ev.get("ras_eve_velocidade",0)); ign=safe_int(ev.get("ras_eve_ignicao",0))
                    lat=ev.get("ras_eve_latitude"); lon=ev.get("ras_eve_longitude")
                    try: dt=datetime.strptime(ev.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                    except: dt=None
                    if prev and dt and prev[0]:
                        s=max(0,(dt-prev[0]).total_seconds())
                        if prev[1]: t_on+=s
                        else: t_off+=s
                        if prev[1] and prev[2]==0: t_ocio+=s
                    vmax=max(vmax,vel)
                    if prev and prev[3] and lat: km+=haversine(prev[3],prev[4],lat,lon)
                    prev=(dt,ign,vel,lat,lon)
                litros=km/cons if cons>0 else 0
                c_comb=litros*preco; h_on=t_on/3600; c_mot=h_on*custo_h
                c_ocio=(t_ocio/3600)*0.5*preco; c_total=c_comb+c_mot+c_ocio
                c_km=c_total/km if km>0 else 0
                lines=["="*52,f"  RELATÓRIO DE CUSTOS — {entry.get('ras_vei_placa','—')}",
                    f"  {entry.get('ras_vei_veiculo','—')}",
                    f"  Motorista: {entry.get('ras_mot_nome','—')}",
                    f"  Período  : {ini.strftime('%d/%m/%Y %H:%M')} → {fim.strftime('%d/%m/%Y %H:%M')}","",
                    "  ─── Desempenho ───────────────────────────",
                    f"    Distância percorrida  : {km:>9.1f} km",
                    f"    Vel. máxima           : {vmax:>9} km/h",
                    f"    Tempo ignição ON      : {hms(t_on):>12}",
                    f"    Tempo ocioso (ign.ON) : {hms(t_ocio):>12}","",
                    "  ─── Estimativa de Custos ─────────────────",
                    f"    Litros consumidos     : {litros:>9.1f} L",
                    f"    Custo combustível     : R$ {c_comb:>8.2f}",
                    f"    Custo motorista       : R$ {c_mot:>8.2f}  ({h_on:.1f}h × R${custo_h:.2f})",
                    f"    Custo ocioso          : R$ {c_ocio:>8.2f}  (est.)",
                    f"  {'─'*44}",
                    f"    CUSTO TOTAL ESTIMADO  : R$ {c_total:>8.2f}",
                    f"    Custo por km          : R$ {c_km:>8.2f}/km","",
                    "  ─── Parâmetros Utilizados ────────────────",
                    f"    Combustível           : R$ {preco:.2f}/L",
                    f"    Consumo médio         : {cons:.1f} km/L",
                    f"    Custo horista mot.    : R$ {custo_h:.2f}/h","="*52]
                write(res,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()

        btn(ph,"💰 CALCULAR CUSTOS",custo_veiculo,C["success"]).pack(pady=(6,0))
        mk_export_btn(ph,res,is_text=True).pack(pady=(4,0))

    # ── Ranking por Motorista ─────────────────────────────────────────────────
    def _tab_ranking(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  📋 Ranking por Motorista  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Custo/km R$:",9,col=C["text_mid"]).pack(side="left")
        e_c=ent(c,w=7); e_c.pack(side="left",padx=4,ipady=4); e_c.insert(0,"0.62")
        lbl(c,"  Penalidade excesso (R$/ocorr.):").pack(side="left")
        e_p=ent(c,w=7); e_p.pack(side="left",padx=4,ipady=4); e_p.insert(0,"10.0")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        ft=FilterableTree(f,("Pos.","Motorista","Placas","Vel.Máx","Vel.Méd","Excessos","Custo.Estim.","Penalidade","Total"),
                          (40,160,80,90,90,80,110,110,110),"CustoRk",C["success"],14)
        self._ft_custo_rank = ft
        def _tags_rank():
            ft.tag_configure("caro",background=_ac("al3"))
            ft.tag_configure("ok",background=C["surface2"])
        _tags_rank(); register_theme_listener(_tags_rank)

        def ranking_custo():
            try: cpm=float(e_c.get()); pen=float(e_p.get())
            except: cpm=0.62; pen=10.0
            lb.config(text="⏳...")
            def task():
                data=get_all_events(); mots={}
                for ev in data:
                    nm=safe_str(ev.get("ras_mot_nome"),"Desconhecido")
                    vel=abs(safe_int(ev.get("ras_eve_velocidade",0)))
                    pl=safe_str(ev.get("ras_vei_placa"))
                    if nm not in mots: mots[nm]={"veics":set(),"vels":[]}
                    mots[nm]["veics"].add(pl); mots[nm]["vels"].append(vel)
                rows=[]
                for nm,d in mots.items():
                    vs=d["vels"]; vmx=max(vs) if vs else 0; vmd=sum(vs)/len(vs) if vs else 0
                    exc=sum(1 for v in vs if v>80)
                    custo_est=len(vs)*0.1*cpm; pen_t=exc*pen; total_c=custo_est+pen_t
                    rows.append(((f"—",nm,len(d["veics"]),f"{vmx} km/h",f"{vmd:.1f} km/h",
                                  exc,f"R$ {custo_est:.2f}",f"R$ {pen_t:.2f}",f"R$ {total_c:.2f}"),
                                 "caro" if total_c>200 else "ok"))
                rows.sort(key=lambda x:-float(x[0][8].replace("R$ ","")))
                medals=["🥇","🥈","🥉"]
                for i in range(len(rows)):
                    vals,tag=rows[i]
                    rows[i]=((medals[i] if i<3 else f"#{i+1}",)+vals[1:],tag)
                ft.load(rows); lb.config(text=f"{len(mots)} motoristas | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"📋 CALCULAR",ranking_custo,C["success"]).pack(side="left",padx=8)
        mk_export_btn(c,ft.tree).pack(side="left",padx=4)
        self.after(400,ranking_custo)

    # ── Parâmetros ────────────────────────────────────────────────────────────
    def _tab_parametros(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ⚙ Parâmetros  ")
        b = tk.Frame(f, bg=C["bg"]); b.pack(fill="both", expand=True, padx=20, pady=12)
        sec(b,"CONFIGURAÇÃO DE PARÂMETROS DE CUSTO",C["success"])
        lbl(b,"Use estes valores como referência nos cálculos de custo.",9,col=C["text_mid"]).pack(anchor="w",pady=(0,10))
        params=[
            ("Preço médio combustível (R$/L)","6.20"),("Consumo médio frota (km/L)","10.0"),
            ("Custo horista motorista (R$/h)","25.0"),("Custo manutenção (R$/km)","0.08"),
            ("Seguro médio mensal (R$)","800.0"),("Depreciação mensal (R$)","1200.0"),
            ("Penalidade por excesso de vel. (R$/ocorr.)","10.0"),("Consumo em ocioso (L/h)","0.5"),
        ]
        for lab, default in params:
            r=tk.Frame(b,bg=C["bg"]); r.pack(fill="x",pady=3)
            lbl(r,f"{lab}:",9,col=C["text_mid"],width=38).pack(side="left",anchor="w")
            e=ent(r,w=12); e.pack(side="left",ipady=4); e.insert(0,default)
        lbl(b,"\nℹ  Estes parâmetros são locais a esta sessão. Configure conforme sua realidade operacional.",
            8,col=C["text_dim"]).pack(anchor="w",pady=8)