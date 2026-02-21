"""
tabs/comportamento.py
Aba 11 — Análise Comportamental: Score de Risco, Motor Ocioso,
          Velocidade × Horário, Comparativo entre veículos e Mapa de Calor.
"""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, ts, parse_dt
from core import (
    get_all_events, find_vehicle, extract_list, api_get,
    safe_int, safe_float, safe_str, haversine, hms,
)
from widgets.alert_colors import _ac
from widgets import (
    lbl, ent, btn, txtbox, write, loading, ok, err,
    mk_tree, mk_export_btn, interval_row, FilterableTree,
)


class TabComportamento(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_score(nb)
        self._tab_ocioso(nb)
        self._tab_vel_horario(nb)
        self._tab_comparativo(nb)
        self._tab_heat_map(nb)

    # ── Score de Risco ────────────────────────────────────────────────────────
    def _tab_score(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  🎯 Score de Risco  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Vel.crítica (km/h):",9,col=C["text_mid"]).pack(side="left")
        e_vc=ent(c,w=5); e_vc.pack(side="left",padx=4,ipady=4); e_vc.insert(0,"90")
        lbl(c,"  Bat.mín (%):").pack(side="left")
        e_bat=ent(c,w=5); e_bat.pack(side="left",padx=4,ipady=4); e_bat.insert(0,"20")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        ft=FilterableTree(f,("Score","Motorista","Veículos","Vel.Máx","Vel.Méd","Excesso.V","Sem.GPS","Bat.Baixa","Classificação"),
                          (55,160,70,90,90,90,80,90,120),"Score",C["danger"],15)
        self._ft_score = ft
        def _tags_score():
            ft.tag_configure("critico",background=_ac("crit"))
            ft.tag_configure("alto",background=_ac("alto"))
            ft.tag_configure("medio",background=_ac("med"))
            ft.tag_configure("ok",background=C["surface2"])
        _tags_score(); register_theme_listener(_tags_score)
        info=tk.Frame(f,bg=C["surface3"]); info.pack(fill="x",padx=8,pady=(0,4))
        lbl(info,"ℹ  Score 0-100: penaliza vel. acima do limite (-2/km/h), sem GPS (-5), bat baixa (-3). 100 = perfeito.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")

        def calc_score():
            try: vc=int(e_vc.get()); bat_lim=int(e_bat.get())
            except: vc=90; bat_lim=20
            lb.config(text="⏳ Calculando...")
            def task():
                data=get_all_events(); mots={}
                for ev in data:
                    nm=safe_str(ev.get("ras_mot_nome"),"Desconhecido")
                    vel=abs(safe_int(ev.get("ras_eve_velocidade",0)))
                    gps=safe_int(ev.get("ras_eve_gps_status",0))
                    bat=safe_int(ev.get("ras_eve_porc_bat_backup",100))
                    pl=safe_str(ev.get("ras_vei_placa"))
                    if nm not in mots: mots[nm]={"veics":set(),"vels":[],"no_gps":0,"low_bat":0}
                    mots[nm]["veics"].add(pl)
                    if vel>0: mots[nm]["vels"].append(vel)
                    if not gps: mots[nm]["no_gps"]+=1
                    if bat<bat_lim: mots[nm]["low_bat"]+=1
                rows=[]
                for nm,d in mots.items():
                    vs=d["vels"]; vmx=max(vs) if vs else 0; vmd=sum(vs)/len(vs) if vs else 0
                    excesso=sum(1 for v in vs if v>vc)
                    pen=max(0,vmx-vc)*2+d["no_gps"]*5+d["low_bat"]*3
                    sc=max(0,100-pen)
                    if sc<40: cls_="🔴 CRÍTICO"; tag="critico"
                    elif sc<65: cls_="🟠 ALTO"; tag="alto"
                    elif sc<80: cls_="🟡 MÉDIO"; tag="medio"
                    else: cls_="🟢 BOM"; tag="ok"
                    rows.append(((f"{sc}",nm,len(d["veics"]),f"{vmx} km/h",f"{vmd:.1f} km/h",
                                  excesso,d["no_gps"],d["low_bat"],cls_),tag))
                rows.sort(key=lambda x:int(x[0][0]))
                ft.load(rows); lb.config(text=f"{len(mots)} motoristas | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"🎯 CALCULAR",calc_score,C["danger"]).pack(side="left",padx=8)
        mk_export_btn(c,ft.tree).pack(side="left",padx=4)
        self.after(400,calc_score)

    # ── Motor Ocioso ──────────────────────────────────────────────────────────
    def _tab_ocioso(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ⏱ Motor Ocioso  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Veículo:",9,col=C["text_mid"]).pack(side="left")
        e_v=ent(c,w=18); e_v.pack(side="left",padx=4,ipady=4)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        fr_int=tk.Frame(f,bg=C["bg"]); fr_int.pack(fill="x",padx=8); ei,ef=interval_row(fr_int)
        lbl(f,"Mín. ocioso (min):",9,col=C["text_mid"]).pack(anchor="w",padx=8)
        e_mn=ent(f,w=5); e_mn.pack(anchor="w",padx=8,ipady=4); e_mn.insert(0,"5")
        _,res=txtbox(f,16); _.pack(fill="both",expand=True,padx=8,pady=4)

        def motor_ocioso():
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
                    mn=int(e_mn.get() or 5)
                except: write(res,"⚠ Inválido.",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res,"ℹ Nenhum evento.",C["text_mid"]); return
                ociosos=[]; inicio_ocio=None; tot_ocio=0.0
                for ev in evs:
                    ign=safe_int(ev.get("ras_eve_ignicao",0)); vel=safe_int(ev.get("ras_eve_velocidade",0))
                    try: dt=datetime.strptime(ev.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                    except: dt=None
                    if dt and ign==1 and vel==0:
                        if inicio_ocio is None: inicio_ocio=dt
                    else:
                        if inicio_ocio and dt:
                            dur=(dt-inicio_ocio).total_seconds()/60
                            if dur>=mn: ociosos.append((inicio_ocio,dt,dur)); tot_ocio+=dur
                        inicio_ocio=None
                consumo_est=tot_ocio*0.5
                lines=[f"  {entry.get('ras_vei_placa','—')}  |  {ini.strftime('%d/%m %H:%M')} → {fim.strftime('%d/%m %H:%M')}",
                    f"  Eventos analisados : {len(evs)}",
                    f"  Períodos ociosos ≥{mn}min: {len(ociosos)}",
                    f"  Tempo total ocioso : {tot_ocio:.0f} min  ({tot_ocio/60:.1f} h)",
                    f"  Consumo estimado   : {consumo_est:.1f} L (@ 0.5L/h)",
                    "","  ─── Detalhamento ─────────────────────────",
                    f"  {'#':>3}  {'Início':<20}  {'Fim':<20}  {'Duração':>8}","  "+"─"*58]
                for i,(a,b,d) in enumerate(ociosos,1):
                    lines.append(f"  {i:>3}  {a.strftime('%d/%m %H:%M:%S'):<20}  {b.strftime('%d/%m %H:%M:%S'):<20}  {d:>5.1f} min")
                write(res,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()

        btn(c,"⏱ ANALISAR",motor_ocioso,C["accent"]).pack(side="left",padx=8)
        mk_export_btn(c,res,is_text=True).pack(side="left",padx=4)

    # ── Velocidade × Horário ──────────────────────────────────────────────────
    def _tab_vel_horario(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  📈 Velocidade × Horário  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Veículo:",9,col=C["text_mid"]).pack(side="left")
        e_v=ent(c,w=18); e_v.pack(side="left",padx=4,ipady=4)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        fr_int=tk.Frame(f,bg=C["bg"]); fr_int.pack(fill="x",padx=8); ei,ef=interval_row(fr_int)
        cv=tk.Canvas(f,bg=C["surface2"],height=220,highlightthickness=0); cv.pack(fill="x",padx=8,pady=4)
        _,res=txtbox(f,5); _.pack(fill="x",padx=8,pady=2)

        def vel_horario():
            q=e_v.get().strip()
            if not q: return
            lb.config(text="⏳...")
            def task():
                entry=find_vehicle(q)
                if not entry: lb.config(text="✖"); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
                except: lb.config(text="⚠ Datas"); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: lb.config(text="Sem eventos"); return
                hora_vel=[[] for _ in range(24)]
                for ev in evs:
                    try: h=datetime.strptime(ev.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S").hour
                    except: continue
                    v=abs(safe_int(ev.get("ras_eve_velocidade",0))); hora_vel[h].append(v)
                avg_h=[sum(vs)/len(vs) if vs else 0 for vs in hora_vel]
                max_h=[max(vs) if vs else 0 for vs in hora_vel]
                cv.delete("all"); W=cv.winfo_width() or 900; H=220
                pad=40; bar_w=max(4,(W-pad*2)//24); max_v=max(max_h) or 1
                for h in range(24):
                    x=pad+h*bar_w
                    bh=int(max_h[h]/max_v*(H-pad-20)); y1=H-pad; y0=y1-bh
                    cv.create_rectangle(x+1,y0,x+bar_w-2,y1,fill=C["surface3"],outline="")
                    bh2=int(avg_h[h]/max_v*(H-pad-20)); y0_2=y1-bh2
                    cv.create_rectangle(x+3,y0_2,x+bar_w-4,y1,fill=C["accent"],outline="")
                    cv.create_text(x+bar_w//2,y1+12,text=str(h),fill=C["text_dim"],font=("Consolas",6),anchor="n")
                cv.create_rectangle(W-180,8,W-170,18,fill=C["surface3"],outline="")
                cv.create_text(W-168,13,text="Vel.Máx",fill=C["text_dim"],font=("Consolas",8),anchor="w")
                cv.create_rectangle(W-180,22,W-170,32,fill=C["accent"],outline="")
                cv.create_text(W-168,27,text="Vel.Média",fill=C["text_dim"],font=("Consolas",8),anchor="w")
                hora_pico=avg_h.index(max(avg_h)); lines=[
                    f"  Hora de maior velocidade média: {hora_pico:02d}h ({max(avg_h):.1f} km/h)",
                    f"  Velocidade máxima registrada: {max(max_h):.0f} km/h",
                    f"  Eventos analisados: {len(evs)}"]
                write(res,"\n".join(lines))
                lb.config(text=f"{entry.get('ras_vei_placa','—')} | {len(evs)} pts | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"📈 GERAR",vel_horario,C["accent2"]).pack(side="left",padx=8)

    # ── Comparativo ───────────────────────────────────────────────────────────
    def _tab_comparativo(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ⚖ Comparativo  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Veículo A:",9,col=C["text_mid"]).pack(side="left")
        e_a=ent(c,w=16); e_a.pack(side="left",padx=4,ipady=4)
        lbl(c,"  vs  Veículo B:",9,col=C["text_mid"]).pack(side="left")
        e_b=ent(c,w=16); e_b.pack(side="left",padx=4,ipady=4)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        fr_int=tk.Frame(f,bg=C["bg"]); fr_int.pack(fill="x",padx=8); ei,ef=interval_row(fr_int)
        _,res=txtbox(f,18); _.pack(fill="both",expand=True,padx=8,pady=4)

        def comparar():
            qa=e_a.get().strip(); qb=e_b.get().strip()
            if not qa or not qb: return
            loading(res)
            def task():
                ea=find_vehicle(qa); eb=find_vehicle(qb)
                if not ea or not eb: err(res,"Um ou ambos não encontrados."); return
                try:
                    ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
                except: write(res,"⚠ Datas.",C["warn"]); return
                def stats(entry):
                    vid=safe_int(entry.get("ras_vei_id",0))
                    evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                    vel_l=[abs(safe_int(e.get("ras_eve_velocidade",0))) for e in evs]
                    t_on=t_off=km=0.0; prev=None
                    for ev in evs:
                        vel=safe_int(ev.get("ras_eve_velocidade",0)); ign=safe_int(ev.get("ras_eve_ignicao",0))
                        lat=ev.get("ras_eve_latitude"); lon=ev.get("ras_eve_longitude")
                        try: dt=datetime.strptime(ev.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                        except: dt=None
                        if prev and dt and prev[0]:
                            s=max(0,(dt-prev[0]).total_seconds())
                            if prev[1]: t_on+=s
                            else: t_off+=s
                        if prev and prev[2] and lat: km+=haversine(prev[2],prev[3],lat,lon)
                        prev=(dt,ign,lat,lon)
                    return {"placa":safe_str(entry.get("ras_vei_placa")),"veiculo":safe_str(entry.get("ras_vei_veiculo")),
                            "eventos":len(evs),"km":km,"vmax":max(vel_l) if vel_l else 0,
                            "vmed":sum(vel_l)/len(vel_l) if vel_l else 0,"t_on":t_on,"t_off":t_off,
                            "excesso":sum(1 for v in vel_l if v>80)}
                sa=stats(ea); sb=stats(eb); w=38
                lines=["="*70,
                    f"  {'MÉTRICA':<22}  {'VEÍCULO A':<{w}}  {'VEÍCULO B':<{w}}",
                    "  "+"─"*66,
                    f"  {'Placa':<22}  {sa['placa']:<{w}}  {sb['placa']:<{w}}",
                    f"  {'Descrição':<22}  {sa['veiculo'][:w]:<{w}}  {sb['veiculo'][:w]:<{w}}",
                    f"  {'Eventos':<22}  {sa['eventos']:<{w}}  {sb['eventos']:<{w}}",
                    f"  {'Distância (km)':<22}  {sa['km']:<{w}.1f}  {sb['km']:<{w}.1f}",
                    f"  {'Vel. Máxima':<22}  {sa['vmax']:<{w}} km/h  {sb['vmax']:<{w}} km/h",
                    f"  {'Vel. Média':<22}  {sa['vmed']:<{w}.1f}  {sb['vmed']:<{w}.1f}",
                    f"  {'Tempo Ign.ON':<22}  {hms(sa['t_on']):<{w}}  {hms(sb['t_on']):<{w}}",
                    f"  {'Excessos >80km/h':<22}  {sa['excesso']:<{w}}  {sb['excesso']:<{w}}",
                    "="*70]
                write(res,"\n".join(lines)); lb.config(text=f"Comparativo gerado | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"⚖ COMPARAR",comparar,C["accent2"]).pack(side="left",padx=8)
        mk_export_btn(c,res,is_text=True).pack(side="left",padx=4)

    # ── Mapa de Calor ─────────────────────────────────────────────────────────
    def _tab_heat_map(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  🔥 Mapa de Calor  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Início:",9,col=C["text_mid"]).pack(side="left")
        ei=ent(c,w=18); ei.pack(side="left",padx=4,ipady=4)
        ei.insert(0,(datetime.now()-timedelta(days=30)).strftime("%d/%m/%Y %H:%M"))
        lbl(c,"  Fim:").pack(side="left")
        ef=ent(c,w=18); ef.pack(side="left",padx=4,ipady=4)
        ef.insert(0,datetime.now().strftime("%d/%m/%Y %H:%M"))
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cv=tk.Canvas(f,bg=C["surface2"],height=200,highlightthickness=0); cv.pack(fill="x",padx=8,pady=4)
        info_lbl=lbl(f,"",8,col=C["text_mid"]); info_lbl.pack(padx=8,anchor="w")

        def heat_map():
            lb.config(text="⏳ Carregando alertas...")
            try:
                ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
            except: lb.config(text="⚠ Datas"); return
            def task():
                from core.api import extract_list, api_get
                d=extract_list(api_get(f"/alerts/period/initial/{ts(ini)}/final/{ts(fim)}").get("data",[]))
                mat=[[0]*24 for _ in range(7)]; dias=["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
                for a in d:
                    dt=parse_dt(safe_str(a.get("ras_eal_data_alerta")))
                    if dt: mat[dt.weekday()][dt.hour]+=1
                mx=max(max(row) for row in mat) or 1
                cv.delete("all"); W=cv.winfo_width() or 900; H=200
                cell_w=(W-50)//24; cell_h=(H-20)//7
                for h in range(24):
                    cv.create_text(50+h*cell_w+cell_w//2,8,text=str(h),fill=C["text_dim"],font=("Consolas",6))
                for d_idx,dia in enumerate(dias):
                    cv.create_text(24,22+d_idx*cell_h+cell_h//2,text=dia,fill=C["text_dim"],font=("Consolas",7))
                    for h in range(24):
                        v=mat[d_idx][h]; intensity=int(255*v/mx) if mx>0 else 0
                        r2=min(255,intensity+50); g2=max(0,50-intensity//3); b2=10
                        col_hex=f"#{r2:02x}{g2:02x}{b2:02x}"; x=50+h*cell_w; y=16+d_idx*cell_h
                        cv.create_rectangle(x+1,y+1,x+cell_w-1,y+cell_h-1,fill=col_hex,outline=C["bg"])
                        if v>0 and cell_w>16:
                            cv.create_text(x+cell_w//2,y+cell_h//2,text=str(v),fill="white",font=("Consolas",6))
                total=sum(mat[d_idx][h] for d_idx in range(7) for h in range(24))
                pico_d=max(range(7),key=lambda d_idx:sum(mat[d_idx]))
                pico_h=max(range(24),key=lambda h:sum(mat[d_idx][h] for d_idx in range(7)))
                info_lbl.config(text=f"Total: {total} alertas  |  Dia pico: {dias[pico_d]}  |  Hora pico: {pico_h:02d}h")
                lb.config(text=f"{len(d)} alertas carregados | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"🔥 GERAR MAPA",heat_map,C["danger"]).pack(side="left",padx=8)