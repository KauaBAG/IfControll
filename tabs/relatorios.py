"""
tabs/relatorios.py — com suporte a tema dinâmico
"""
import json, threading, tkinter as tk
from tkinter import ttk
from datetime import datetime
from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, ts
from core import (get_all_events, find_vehicle, extract_list, api_get,
                  safe_int, safe_float, safe_str, haversine, hms)
from widgets import (lbl, ent, btn, txtbox, write, loading, ok, err,
                     mk_tree, mk_export_btn, interval_row)
from widgets.alert_colors import _ac


class TabRelatorios(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _hdr(self, parent):
        b = tk.Frame(parent, bg=C["bg"]); b.pack(fill="x", padx=10, pady=6)
        lbl(b, "Veículo (placa/nome):", 9, col=C["text_mid"]).pack(anchor="w", pady=(0,2))
        ev = ent(b); ev.pack(fill="x", ipady=5)
        ei, ef = interval_row(b)
        return b, ev, ei, ef

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_utilizacao(nb)
        self._tab_paradas(nb)
        self._tab_replay(nb)
        self._tab_temperatura(nb)
        self._tab_cadeia_frio(nb)
        self._tab_alertas_vel(nb)

    # ── Utilização ────────────────────────────────────────────────────────────
    def _tab_utilizacao(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Utilização  ")
        hdr, ev, ei, ef = self._hdr(f)
        _fr, res = txtbox(f, 16); _fr.pack(fill="both", expand=True, padx=10)
        def util():
            q = ev.get().strip()
            if not q: return
            loading(res)
            def task():
                entry = find_vehicle(q)
                if not entry: err(res, "Não encontrado."); return
                vid = safe_int(entry.get("ras_vei_id", 0))
                try:
                    ini = datetime.strptime(ei.get().strip(), "%d/%m/%Y %H:%M")
                    fim = datetime.strptime(ef.get().strip(), "%d/%m/%Y %H:%M")
                except: write(res, "⚠ Datas inválidas.", C["warn"]); return
                evs = extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res, "ℹ Nenhum evento.", C["text_mid"]); return
                km=0.0; t_on=t_off=t_par=0.0; vmax=0; vels=[]; prev=None
                for ev2 in evs:
                    vel=safe_int(ev2.get("ras_eve_velocidade",0)); ign=safe_int(ev2.get("ras_eve_ignicao",0))
                    lat=ev2.get("ras_eve_latitude"); lon=ev2.get("ras_eve_longitude")
                    try: dt=datetime.strptime(ev2.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                    except: dt=None
                    if prev and dt and prev[0]:
                        s=max(0,(dt-prev[0]).total_seconds())
                        if prev[1]: t_on+=s
                        else: t_off+=s
                        if prev[1] and prev[2]==0: t_par+=s
                    if vel>0: vmax=max(vmax,vel); vels.append(vel)
                    if prev and prev[3] and lat: km+=haversine(prev[3],prev[4],lat,lon)
                    prev=(dt,ign,vel,lat,lon)
                vmed=sum(vels)/len(vels) if vels else 0
                lines=["="*46,f"  {entry.get('ras_vei_placa','—')} — {entry.get('ras_vei_veiculo','—')}",
                    f"  Motorista: {entry.get('ras_mot_nome','—')}",
                    f"  Período  : {ini.strftime('%d/%m/%Y %H:%M')} → {fim.strftime('%d/%m/%Y %H:%M')}",
                    f"  Eventos  : {len(evs)}","",
                    "  ─── Distância & Velocidade ──────────",
                    f"    Distância estimada : {km:>9.1f} km",
                    f"    Velocidade máxima  : {vmax:>9} km/h",
                    f"    Velocidade média   : {vmed:>9.1f} km/h","",
                    "  ─── Tempo ────────────────────────────",
                    f"    Ignição ON         : {hms(t_on):>12}",
                    f"    Ignição OFF        : {hms(t_off):>12}",
                    f"    Parado c/ign.ON    : {hms(t_par):>12}","","="*46]
                write(res,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()
        btn(hdr,"📊 GERAR",util,C["green"]).pack(side="right",pady=4)
        mk_export_btn(hdr,res,is_text=True).pack(side="right",padx=4,pady=4)

    # ── Paradas ───────────────────────────────────────────────────────────────
    def _tab_paradas(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Paradas  ")
        hdr, ev2, ei2, ef2 = self._hdr(f)
        rmin=tk.Frame(hdr,bg=C["bg"]); rmin.pack(fill="x",pady=3)
        lbl(rmin,"Mín. parada (min):",9,col=C["text_mid"],width=20).pack(side="left",anchor="w")
        e_min=ent(rmin,w=8); e_min.pack(side="left",ipady=4); e_min.insert(0,"5")
        _,res2=txtbox(f,16); _.pack(fill="both",expand=True,padx=10)
        def paradas():
            q=ev2.get().strip()
            if not q: return
            loading(res2)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res2,"Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei2.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef2.get().strip(),"%d/%m/%Y %H:%M")
                    mn=int(e_min.get() or 5)
                except: write(res2,"⚠ Inválido.",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res2,"ℹ Nenhum evento.",C["text_mid"]); return
                pars=[]; pi=None
                for ev3 in evs:
                    vel=safe_int(ev3.get("ras_eve_velocidade",0))
                    try: dt=datetime.strptime(ev3.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                    except: dt=None
                    if vel==0 and dt:
                        if pi is None: pi=dt
                    else:
                        if pi and dt:
                            d=(dt-pi).total_seconds()/60
                            if d>=mn: pars.append((pi,dt,d))
                        pi=None
                tot=sum(d for _,_,d in pars)
                lines=[f"  {entry.get('ras_vei_placa','—')}  |  Paradas ≥ {mn} min: {len(pars)}",
                    f"  Total parado: {tot:.0f} min  ({tot/60:.1f} h)","",
                    f"  {'#':>3}  {'Início':<18}  {'Fim':<18}  {'Duração':>9}","  "+"─"*56]
                for i,(a,b,d) in enumerate(pars,1):
                    lines.append(f"  {i:>3}  {a.strftime('%d/%m %H:%M:%S'):<18}  {b.strftime('%d/%m %H:%M:%S'):<18}  {d:>6.1f} min")
                write(res2,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()
        btn(hdr,"⏸ ANALISAR",paradas,C["blue"]).pack(side="right",pady=4)
        mk_export_btn(hdr,res2,is_text=True).pack(side="right",padx=4,pady=4)

    # ── Replay ────────────────────────────────────────────────────────────────
    def _tab_replay(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Replay de Rota  ")
        hdr, ev3, ei3, ef3 = self._hdr(f)
        cols=("Seq","Data GPS","Lat","Lon","Vel. km/h","Ign.","GPS","Satél.")
        self._t3=mk_tree(f,cols,(50,150,110,110,90,70,60,60),"Replay",C["purple"],14)
        lb3=lbl(f,"",col=C["text_dim"]); lb3.pack(anchor="e",padx=10,pady=2)
        def _tags3():
            self._t3.tag_configure("on",background=C["surface2"])
            self._t3.tag_configure("off",background=C["surface3"])
        _tags3(); register_theme_listener(_tags3)
        def replay():
            q=ev3.get().strip()
            if not q: return
            lb3.config(text="⏳...")
            def task():
                entry=find_vehicle(q)
                if not entry: lb3.config(text="✖ Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei3.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef3.get().strip(),"%d/%m/%Y %H:%M")
                except: lb3.config(text="⚠ Datas inválidas."); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                for r in self._t3.get_children(): self._t3.delete(r)
                for i,ev4 in enumerate(evs,1):
                    ign=safe_int(ev4.get("ras_eve_ignicao",0))
                    self._t3.insert("","end",values=(i,safe_str(ev4.get("ras_eve_data_gps")),
                        safe_str(ev4.get("ras_eve_latitude")),safe_str(ev4.get("ras_eve_longitude")),
                        safe_int(ev4.get("ras_eve_velocidade",0)),"ON" if ign else "OFF",
                        "✓" if safe_int(ev4.get("ras_eve_gps_status")) else "✗",
                        safe_int(ev4.get("ras_eve_satelites",0))),tags=("on" if ign else "off",))
                lb3.config(text=f"{entry.get('ras_vei_placa','—')}  |  {len(evs)} pontos  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(hdr,"🗺 REPLAY",replay,C["purple"]).pack(side="right",pady=4)
        mk_export_btn(hdr,self._t3).pack(side="right",padx=4,pady=4)

    # ── Temperatura Viva ──────────────────────────────────────────────────────
    def _tab_temperatura(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Temperatura Viva  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=10,pady=6)
        lbl(c,"Placa/nome:",9,col=C["text_mid"]).pack(side="left")
        e4=ent(c,w=22); e4.pack(side="left",padx=8,ipady=4)
        _,res4=txtbox(f,18); _.pack(fill="both",expand=True,padx=10)
        def temp():
            q=e4.get().strip()
            if not q: return
            loading(res4)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res4,"Não encontrado."); return
                sensors=entry.get("sensor_temperatura") or {}
                if isinstance(sensors,str):
                    try: sensors=json.loads(sensors)
                    except: sensors={}
                ign=safe_int(entry.get("ras_eve_ignicao",0)); inp=entry.get("ras_eve_input","000")
                lines=["="*42,f"  Placa  : {entry.get('ras_vei_placa','—')}",
                    f"  Veículo: {entry.get('ras_vei_veiculo','—')}",
                    f"  Ignição: {'🟢 ON' if ign else '⚫ OFF'}",
                    f"  Frio   : {'🟢 ON' if (safe_int(inp[2]) if len(inp)>2 else 0) else '⚫ OFF'}",
                    f"  Vel.   : {safe_int(entry.get('ras_eve_velocidade',0))} km/h",
                    f"  GPS    : {'✓ OK' if safe_int(entry.get('ras_eve_gps_status')) else '✗ FALHA'}",
                    f"  Última : {entry.get('ras_eve_data_gps','—')}","","  Sensores:","  "+"─"*36]
                if isinstance(sensors,dict) and sensors:
                    for k,v in sensors.items():
                        fv=safe_float(v); bar="█"*max(0,min(20,int(fv)//3)) if fv>0 else ""
                        lines.append(f"  {k:12s}: {fv:>6.1f}°C  {bar}")
                else: lines.append("  Sem dados de temperatura.")
                write(res4,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()
        btn(c,"🌡 CONSULTAR",temp,C["orange"]).pack(side="left")
        mk_export_btn(c,res4,is_text=True).pack(side="left",padx=6)

    # ── Cadeia de Frio ────────────────────────────────────────────────────────
    def _tab_cadeia_frio(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Cadeia de Frio  ")
        hdr, ev5, ei5, ef5 = self._hdr(f)
        rt=tk.Frame(hdr,bg=C["bg"]); rt.pack(fill="x",pady=3)
        lbl(rt,"Temp. mín (°C):",9,col=C["text_mid"],width=18).pack(side="left",anchor="w")
        e_tmin=ent(rt,w=8); e_tmin.pack(side="left",ipady=4); e_tmin.insert(0,"-5")
        lbl(rt,"  Temp. máx (°C):",9,col=C["text_mid"]).pack(side="left")
        e_tmax=ent(rt,w=8); e_tmax.pack(side="left",padx=8,ipady=4); e_tmax.insert(0,"8")
        _,res5=txtbox(f,14); _.pack(fill="both",expand=True,padx=10)
        def frio():
            q=ev5.get().strip()
            if not q: return
            loading(res5)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res5,"Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei5.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef5.get().strip(),"%d/%m/%Y %H:%M")
                    tmin=float(e_tmin.get()); tmax=float(e_tmax.get())
                except: write(res5,"⚠ Inválido.",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res5,"ℹ Nenhum evento.",C["text_mid"]); return
                temps={}; viols=[]
                for ev6 in evs:
                    raw=ev6.get("ras_eve_temperatura") or {}
                    if isinstance(raw,str):
                        try: raw=json.loads(raw)
                        except: raw=[]
                    if isinstance(raw,list):
                        for i,v in enumerate(raw):
                            fv=safe_float(v,None)
                            if fv is None: continue
                            sn=f"sensor_{i+1}"; temps.setdefault(sn,[]).append(fv)
                            if fv<tmin or fv>tmax: viols.append((safe_str(ev6.get("ras_eve_data_gps")),sn,fv))
                    elif isinstance(raw,dict):
                        for k,v in raw.items():
                            fv=safe_float(v,None)
                            if fv is None: continue
                            temps.setdefault(k,[]).append(fv)
                            if fv<tmin or fv>tmax: viols.append((safe_str(ev6.get("ras_eve_data_gps")),k,fv))
                tot=sum(len(v) for v in temps.values()) or len(evs)
                pct=max(0,100-len(viols)*100//max(tot,1))
                lines=[f"  {entry.get('ras_vei_placa','—')}  |  {ini.strftime('%d/%m/%Y %H:%M')} → {fim.strftime('%d/%m/%Y %H:%M')}",
                    f"  Faixa: {tmin}°C a {tmax}°C  |  Eventos: {len(evs)}","","  ─── Sensores ────────────────────"]
                if temps:
                    for s,vals in sorted(temps.items()):
                        lines.append(f"  {s:12s}: min={min(vals):.1f}  max={max(vals):.1f}  med={(sum(vals)/len(vals)):.1f}°C ({len(vals)} leituras)")
                else: lines.append("  ⚠ Sem dados de temperatura neste intervalo.")
                lines+=[f"",f"  Conformidade: {pct}%  |  Violações: {len(viols)}"]
                if viols:
                    lines+=["","  Últimas violações:"]
                    for d,s,v in viols[-5:]: lines.append(f"  {'🔴' if v>tmax else '🔵'} {d}  {s}: {v:.1f}°C")
                col=C["success"] if pct>=90 else C["warn"] if pct>=70 else C["danger"]
                write(res5,"\n".join(lines),col)
            threading.Thread(target=task,daemon=True).start()
        btn(hdr,"❄ RELATÓRIO",frio,C["blue"]).pack(side="right",pady=4)
        mk_export_btn(hdr,res5,is_text=True).pack(side="right",padx=4,pady=4)

    # ── Alertas de Velocidade ─────────────────────────────────────────────────
    def _tab_alertas_vel(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  Alertas Veloc.  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"Limite (km/h):").pack(side="left")
        e_lim=ent(c,w=6); e_lim.pack(side="left",padx=6,ipady=4); e_lim.insert(0,"80")
        lb6=lbl(c,"",col=C["text_dim"]); lb6.pack(side="right")
        cols=("Placa","Motorista","Velocidade","Ignição","GPS","Data")
        self._t6=mk_tree(f,cols,(90,140,110,80,60,150),"AlerV",C["danger"],14)
        def _tags6(): self._t6.tag_configure("al",background=_ac("al"))
        _tags6(); register_theme_listener(_tags6)
        def alertas_vel():
            try: lim=int(e_lim.get())
            except: lim=80
            lb6.config(text="⏳ Verificando...")
            def task():
                data=get_all_events()
                for r in self._t6.get_children(): self._t6.delete(r)
                ac=0
                for ev7 in data:
                    vel=safe_int(ev7.get("ras_eve_velocidade",0))
                    if vel>lim or vel<0:
                        ac+=1
                        self._t6.insert("","end",values=(safe_str(ev7.get("ras_vei_placa")),
                            safe_str(ev7.get("ras_mot_nome")),f"🚨 {vel} km/h",
                            "ON" if safe_int(ev7.get("ras_eve_ignicao")) else "OFF",
                            "✓" if safe_int(ev7.get("ras_eve_gps_status")) else "✗",
                            safe_str(ev7.get("ras_eve_data_gps"))),tags=("al",))
                lb6.config(text=f"Total: {len(data)}  |  ⚠ Alertas: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⚡ VERIFICAR",alertas_vel,C["danger"]).pack(side="left",padx=8)
        mk_export_btn(c,self._t6).pack(side="left",padx=4)
        self.after(500,alertas_vel)