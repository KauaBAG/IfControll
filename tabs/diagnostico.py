"""
tabs/diagnostico.py — com suporte a tema dinâmico
"""
import json, threading, tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta
from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, ts, parse_dt, auto_refresh_register
from core import (get_all_events, get_trackers_all, find_vehicle, extract_list,
                  api_get, safe_int, safe_float, safe_str, haversine)
from widgets import (lbl, ent, btn, txtbox, write, mk_tree, mk_export_btn, interval_row)
from widgets.tree import attach_copy
from widgets.alert_colors import _ac


class TabDiagnostico(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_gps_snapshot(nb)
        self._tab_gps_periodo(nb)
        self._tab_ignicao(nb)
        self._tab_sensores(nb)
        self._tab_desatualizados(nb)

    # ── GPS Travado (snapshot) ─────────────────────────────────────────────────
    def _tab_gps_snapshot(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  🛰 GPS Travado  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"Tolerância defasagem (min):",9,col=C["text_mid"]).pack(side="left")
        e_tol=ent(c,w=5); e_tol.pack(side="left",padx=6,ipady=4); e_tol.insert(0,"5")
        lbl(c,"  Tolerância sem mover (m):",9,col=C["text_mid"]).pack(side="left")
        e_mov=ent(c,w=6); e_mov.pack(side="left",padx=6,ipady=4); e_mov.insert(0,"50")
        lb1=lbl(c,"",col=C["text_dim"]); lb1.pack(side="right")
        cols=("Placa","Veículo","Motorista","Data GPS","Data Envio","Defasagem","Vel.","Situação")
        self._t_gps=mk_tree(f,cols,(90,130,130,150,150,110,70,140),"GpsT",C["warn"],14)
        def _tags(): self._t_gps.tag_configure("al",background=_ac("med"))
        _tags(); register_theme_listener(_tags)
        info=tk.Frame(f,bg=C["surface3"]); info.pack(fill="x",padx=8,pady=(0,4))
        lbl(info,"ℹ  GPS Travado: diferença entre Data GPS e Data Envio > tolerância  |  e/ou  veículo em movimento sem mudança de posição.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")
        def gps_travado():
            try: tol=int(e_tol.get()); mov_m=float(e_mov.get())
            except: tol=5; mov_m=50
            lb1.config(text="⏳ Verificando...")
            def task():
                data=get_all_events(); now=datetime.now()
                for r in self._t_gps.get_children(): self._t_gps.delete(r)
                ac=0
                for ev in data:
                    d_gps=safe_str(ev.get("ras_eve_data_gps")); d_env=safe_str(ev.get("ras_eve_data_enviado"))
                    dt_gps=parse_dt(d_gps); dt_env=parse_dt(d_env)
                    vel=safe_int(ev.get("ras_eve_velocidade",0)); problemas=[]; defasagem="—"
                    if dt_gps and dt_env:
                        diff=abs((dt_env-dt_gps).total_seconds())/60; defasagem=f"{diff:.1f} min"
                        if diff>=tol: problemas.append(f"Defasagem {diff:.0f}min")
                    elif dt_gps:
                        diff=(now-dt_gps).total_seconds()/60; defasagem=f"{diff:.1f} min (sem envio)"
                        if diff>=tol: problemas.append(f"Sem envio {diff:.0f}min")
                    if vel>5: problemas.append(f"Vel={vel}km/h")
                    if problemas:
                        ac+=1
                        self._t_gps.insert("","end",values=(safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                            safe_str(ev.get("ras_mot_nome")),d_gps,d_env,defasagem,f"{vel} km/h"," | ".join(problemas)),tags=("al",))
                lb1.config(text=f"Total: {len(data)}  |  ⚠ Suspeitos: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"🔍 VERIFICAR",gps_travado,C["warn"]).pack(side="left",padx=8)
        mk_export_btn(c,self._t_gps).pack(side="left",padx=4)
        self.after(300,gps_travado)

    # ── GPS Travado (período) ──────────────────────────────────────────────────
    def _tab_gps_periodo(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  🛰 GPS Travado (Período)  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"Veículo:").pack(side="left")
        e_v=ent(c,w=18); e_v.pack(side="left",padx=6,ipady=4)
        lbl(c,"  Tol.GPS(min):").pack(side="left")
        e_t=ent(c,w=5); e_t.pack(side="left",padx=4,ipady=4); e_t.insert(0,"5")
        lbl(c,"  Dist.mín(m):").pack(side="left")
        e_d=ent(c,w=6); e_d.pack(side="left",padx=4,ipady=4); e_d.insert(0,"10")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        fr_int=tk.Frame(f,bg=C["bg"]); fr_int.pack(fill="x",padx=8,pady=2)
        ei,ef=interval_row(fr_int)
        cols=("Seq","Data GPS","Data Envio","Defasagem(min)","Vel.","Lat","Lon","Status")
        self._t_gpsp=mk_tree(f,cols,(50,150,150,120,70,120,120,160),"GpsTp",C["warn"],14)
        def _tags():
            self._t_gpsp.tag_configure("al",background=_ac("med"))
            self._t_gpsp.tag_configure("ok",background=C["surface2"])
        _tags(); register_theme_listener(_tags)
        def analisar():
            q=e_v.get().strip()
            if not q: lb.config(text="⚠ Informe o veículo"); return
            try:
                tol=int(e_t.get()); dist_m=float(e_d.get())
                ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
            except: lb.config(text="⚠ Parâmetros inválidos"); return
            lb.config(text="⏳...")
            def task():
                entry=find_vehicle(q)
                if not entry: lb.config(text="✖ Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                for r in self._t_gpsp.get_children(): self._t_gpsp.delete(r)
                ac=0; prev_lat=prev_lon=prev_gps_dt=None
                for i,ev in enumerate(evs,1):
                    vel=safe_int(ev.get("ras_eve_velocidade",0)); lat=safe_float(ev.get("ras_eve_latitude"),None)
                    lon=safe_float(ev.get("ras_eve_longitude"),None); d_gps=safe_str(ev.get("ras_eve_data_gps"))
                    d_env=safe_str(ev.get("ras_eve_data_enviado")); dt_gps=parse_dt(d_gps); dt_env=parse_dt(d_env)
                    defasagem="—"; problemas=[]
                    if dt_gps and dt_env:
                        diff=abs((dt_env-dt_gps).total_seconds())/60; defasagem=f"{diff:.1f}"
                        if diff>=tol: problemas.append(f"Defasagem {diff:.0f}min")
                    if prev_lat is not None and lat is not None and vel>5:
                        dist_km=haversine(prev_lat,prev_lon,lat,lon)
                        if dist_km*1000<dist_m: problemas.append(f"Pos.congelada({dist_km*1000:.0f}m)")
                    if prev_gps_dt and dt_gps and prev_gps_dt==dt_gps and vel>0: problemas.append("Timestamp repetido")
                    status="⚠ "+(" | ".join(problemas)) if problemas else "✓ OK"
                    if problemas: ac+=1
                    self._t_gpsp.insert("","end",values=(i,d_gps,d_env,defasagem,f"{vel} km/h",
                        f"{lat:.5f}" if lat else "—",f"{lon:.5f}" if lon else "—",status),
                        tags=("al" if problemas else "ok",))
                    prev_lat=lat; prev_lon=lon; prev_gps_dt=dt_gps
                lb.config(text=f"{entry.get('ras_vei_placa','—')}  |  {len(evs)} eventos  |  ⚠ {ac} problemas  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"🔍 ANALISAR",analisar,C["warn"]).pack(side="left",padx=8)
        mk_export_btn(c,self._t_gpsp).pack(side="left",padx=4)

    # ── Ignição Defeituosa ─────────────────────────────────────────────────────
    def _tab_ignicao(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  🔑 Ignição Defeituosa  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"Vel. mín para detectar (km/h):",9,col=C["text_mid"]).pack(side="left")
        e_v=ent(c,w=5); e_v.pack(side="left",padx=6,ipady=4); e_v.insert(0,"5")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cols=("Placa","Veículo","Motorista","Ignição","Velocidade","GPS","Data GPS","Cliente")
        self._t_ign=mk_tree(f,cols,(90,130,130,80,100,60,150,130),"IgnD",C["danger"],14)
        def _tags(): self._t_ign.tag_configure("al",background=_ac("al"))
        _tags(); register_theme_listener(_tags)
        info=tk.Frame(f,bg=C["surface3"]); info.pack(fill="x",padx=8,pady=(0,4))
        lbl(info,"ℹ  Ignição Defeituosa: ignição OFF mas velocidade acima do limiar configurado.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")
        def verificar():
            try: vmin=int(e_v.get())
            except: vmin=5
            lb.config(text="⏳ Verificando...")
            def task():
                data=get_all_events()
                for r in self._t_ign.get_children(): self._t_ign.delete(r)
                ac=0
                for ev in data:
                    ign=safe_int(ev.get("ras_eve_ignicao",0)); vel=safe_int(ev.get("ras_eve_velocidade",0))
                    if ign==0 and vel>=vmin:
                        ac+=1
                        self._t_ign.insert("","end",values=(safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                            safe_str(ev.get("ras_mot_nome")),"⚫ OFF",f"🚨 {vel} km/h",
                            "✓" if safe_int(ev.get("ras_eve_gps_status")) else "✗",
                            safe_str(ev.get("ras_eve_data_gps")),safe_str(ev.get("ras_cli_desc"))),tags=("al",))
                lb.config(text=f"Total: {len(data)}  |  🚨 Defeituosas: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"🔍 VERIFICAR",verificar,C["danger"]).pack(side="left",padx=8)
        mk_export_btn(c,self._t_ign).pack(side="left",padx=4)
        self.after(400,verificar)

    # ── Sensores com Problema ──────────────────────────────────────────────────
    def _tab_sensores(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  🌡 Sensores Problema  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"Temp. mín (°C):",9,col=C["text_mid"]).pack(side="left")
        e_min=ent(c,w=7); e_min.pack(side="left",padx=4,ipady=4); e_min.insert(0,"-40")
        lbl(c,"  Temp. máx (°C):",9,col=C["text_mid"]).pack(side="left")
        e_max=ent(c,w=7); e_max.pack(side="left",padx=4,ipady=4); e_max.insert(0,"85")
        lbl(c,"  Bat. mín (%):").pack(side="left")
        e_bat=ent(c,w=5); e_bat.pack(side="left",padx=4,ipady=4); e_bat.insert(0,"20")
        lbl(c,"  Volt. mín (V):").pack(side="left")
        e_volt=ent(c,w=5); e_volt.pack(side="left",padx=4,ipady=4); e_volt.insert(0,"10.0")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cols=("Placa","Veículo","Problema","Valor","Sensor/Campo","Data GPS","Cliente")
        self._t_sen=mk_tree(f,cols,(90,130,160,100,130,150,130),"SenP",C["orange"],14)
        def _tags(): self._t_sen.tag_configure("al",background=_ac("alto"))
        _tags(); register_theme_listener(_tags)
        info=tk.Frame(f,bg=C["surface3"]); info.pack(fill="x",padx=8,pady=(0,4))
        lbl(info,"ℹ  Detecta temperaturas fora da faixa, bateria baixa e voltagem abaixo do mínimo.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")
        def verificar():
            try:
                tmin=float(e_min.get()); tmax=float(e_max.get())
                bat_min=int(e_bat.get()); volt_min=float(e_volt.get())
            except: tmin=-40; tmax=85; bat_min=20; volt_min=10.0
            lb.config(text="⏳ Verificando...")
            def task():
                data=get_all_events()
                for r in self._t_sen.get_children(): self._t_sen.delete(r)
                ac=0
                for ev in data:
                    placa=safe_str(ev.get("ras_vei_placa")); veiculo=safe_str(ev.get("ras_vei_veiculo"))
                    cliente=safe_str(ev.get("ras_cli_desc")); data_gps=safe_str(ev.get("ras_eve_data_gps"))
                    probs=[]
                    bat=safe_int(ev.get("ras_eve_porc_bat_backup",100))
                    if bat<bat_min: probs.append((placa,veiculo,"Bateria baixa",f"{bat}%","bat_backup",data_gps,cliente))
                    volt=safe_float(ev.get("ras_eve_voltagem",0))
                    if 0<volt<volt_min: probs.append((placa,veiculo,"Voltagem baixa",f"{volt:.1f}V","voltagem",data_gps,cliente))
                    sensors=ev.get("sensor_temperatura") or ev.get("ras_eve_temperatura") or {}
                    if isinstance(sensors,str):
                        try: sensors=json.loads(sensors)
                        except: sensors={}
                    if isinstance(sensors,dict):
                        for k,v in sensors.items():
                            fv=safe_float(v,None)
                            if fv is not None and (fv<tmin or fv>tmax):
                                probs.append((placa,veiculo,"🔴 Temp.Alta" if fv>tmax else "🔵 Temp.Baixa",f"{fv:.1f}°C",k,data_gps,cliente))
                    elif isinstance(sensors,list):
                        for i,v in enumerate(sensors):
                            fv=safe_float(v,None)
                            if fv is not None and (fv<tmin or fv>tmax):
                                probs.append((placa,veiculo,"🔴 Temp.Alta" if fv>tmax else "🔵 Temp.Baixa",f"{fv:.1f}°C",f"sensor_{i+1}",data_gps,cliente))
                    for p in probs:
                        ac+=1; self._t_sen.insert("","end",values=p,tags=("al",))
                lb.config(text=f"Total: {len(data)}  |  ⚠ Problemas: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"🔍 VERIFICAR",verificar,C["orange"]).pack(side="left",padx=8)
        mk_export_btn(c,self._t_sen).pack(side="left",padx=4)
        self.after(500,verificar)

    # ── Veículos Desatualizados ────────────────────────────────────────────────
    def _tab_desatualizados(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ⏰ Desatualizados  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lbl(c,"Tolerância:",9,col=C["text_mid"]).pack(side="left")
        e_val=ent(c,w=5); e_val.pack(side="left",padx=4,ipady=4); e_val.insert(0,"1")
        e_unit=ttk.Combobox(c,values=["minutos","horas","dias"],width=8,state="readonly",font=("Helvetica Neue",9))
        e_unit.pack(side="left",padx=4,ipady=4); e_unit.set("horas")
        lbl(c,"  Filtrar:",8,col=C["text_dim"]).pack(side="left",padx=(12,2))
        e_filtro=ttk.Combobox(c,values=["Todos","Ign. ON","Ign. OFF","GPS Falha","GPS OK"],
                               width=10,state="readonly",font=("Helvetica Neue",9))
        e_filtro.pack(side="left",padx=2); e_filtro.set("Todos")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")

        # Cards resumo
        resumo_f=tk.Frame(f,bg=C["surface"]); resumo_f.pack(fill="x",padx=8,pady=(0,4))
        def _rcard(p,titulo,col):
            fr=tk.Frame(p,bg=C["surface"]); fr.pack(side="left",padx=16,pady=5)
            tk.Label(fr,text=titulo,bg=C["surface"],fg=C["text_dim"],font=("Helvetica Neue",7,"bold")).pack()
            lb2=tk.Label(fr,text="—",bg=C["surface"],fg=col,font=("Helvetica Neue",13,"bold")); lb2.pack()
            return lb2
        r_total=_rcard(resumo_f,"ANALISADOS",C["blue"])
        r_desatual=_rcard(resumo_f,"DESATUALIZADOS",C["danger"])
        r_ign_on=_rcard(resumo_f,"IGN. ON",C["green"])
        r_ign_off=_rcard(resumo_f,"IGN. OFF",C["text_mid"])
        r_no_gps=_rcard(resumo_f,"SEM GPS",C["warn"])
        r_maior=_rcard(resumo_f,"MAIOR ATRASO",C["orange"])

        cols=("Placa","Veículo","Motorista","Cliente","Última GPS","Última Envio",
              "Atraso","Ignição","GPS Status","Chip","Nº Equipamento","Modelo Equip.","Linha","Operadora")
        ws=(90,130,130,130,150,150,110,80,90,120,120,110,100,100)

        # Treeview manual (sem mk_tree para ter style próprio)
        _st=ttk.Style(); _st.theme_use("clam")

        def _apply_desatual_style():
            _st.configure("Desatual.Treeview",
                background=C["surface2"],foreground=C["text"],rowheight=26,
                fieldbackground=C["surface2"],borderwidth=0,font=("Consolas",9))
            _st.configure("Desatual.Treeview.Heading",
                background=C["surface3"],foreground=C["purple"],
                font=("Helvetica Neue",9,"bold"),borderwidth=0,relief="flat")
            _st.map("Desatual.Treeview",background=[("selected",C["accent2"])])

        _apply_desatual_style()
        register_theme_listener(_apply_desatual_style)

        fr4=tk.Frame(f,bg=C["bg"]); fr4.pack(fill="both",expand=True,padx=8)
        self._t_des=ttk.Treeview(fr4,columns=cols,show="headings",style="Desatual.Treeview",height=14)
        for _c,_w in zip(cols,ws):
            self._t_des.heading(_c,text=_c,anchor="w"); self._t_des.column(_c,width=_w,anchor="w",stretch=True)
        vs=ttk.Scrollbar(fr4,orient="vertical",command=self._t_des.yview)
        hs=ttk.Scrollbar(fr4,orient="horizontal",command=self._t_des.xview)
        self._t_des.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
        vs.pack(side="right",fill="y"); hs.pack(side="bottom",fill="x"); self._t_des.pack(fill="both",expand=True)
        attach_copy(self._t_des)

        def _tags_des():
            self._t_des.tag_configure("al_crit",background=_ac("crit"))
            self._t_des.tag_configure("al_alto",background=_ac("alto"))
            self._t_des.tag_configure("al_med", background=_ac("med"))
        _tags_des(); register_theme_listener(_tags_des)

        info=tk.Frame(f,bg=C["surface3"]); info.pack(fill="x",padx=8,pady=(0,4))
        lbl(info,"ℹ  Vermelho = atraso crítico (>4h) · Laranja = alto (1h–4h) · Amarelo = médio (<1h). Ctrl+C copia.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")

        _cache={"rows":[]}

        def _render(rows):
            for r in self._t_des.get_children(): self._t_des.delete(r)
            filtro=e_filtro.get(); on=off=no_gps=0; maior_s=0; shown=[]
            for vals,tag,diff_s in rows:
                ign_txt=vals[7]; gps_txt=vals[8]
                if filtro=="Ign. ON"   and "ON"    not in ign_txt: continue
                if filtro=="Ign. OFF"  and "OFF"   not in ign_txt: continue
                if filtro=="GPS Falha" and "FALHA" not in gps_txt: continue
                if filtro=="GPS OK"    and "OK"    not in gps_txt: continue
                shown.append((vals,tag,diff_s))
                if "ON" in ign_txt: on+=1
                else: off+=1
                if "FALHA" in gps_txt: no_gps+=1
                maior_s=max(maior_s,diff_s)
            for vals,tag,_ in shown: self._t_des.insert("","end",values=vals,tags=(tag,))
            r_desatual.config(text=str(len(shown)))
            r_ign_on.config(text=str(on)); r_ign_off.config(text=str(off)); r_no_gps.config(text=str(no_gps))
            r_maior.config(text=f"{maior_s/60:.0f} min" if maior_s<3600 else f"{maior_s/3600:.1f} h" if maior_s<86400 else f"{maior_s/86400:.1f} dias")

        e_filtro.bind("<<ComboboxSelected>>",lambda e:_render(_cache["rows"]))

        def verificar():
            try:
                val=float(e_val.get()); unit=e_unit.get()
                tol_s=val*60 if unit=="minutos" else val*3600 if unit=="horas" else val*86400
            except: tol_s=3600
            lb.config(text="⏳ Verificando...")
            def task():
                TZ_BR=timezone(timedelta(hours=-3)); now=datetime.now(TZ_BR).replace(tzinfo=None)
                events=get_all_events()
                r_total.config(text=str(len(events)))
                try:
                    trackers_raw=get_trackers_all()
                    tracker_by_veic={safe_str(tr.get("ras_vei_id","")): tr for tr in trackers_raw if safe_str(tr.get("ras_vei_id",""))!="—"}
                    tracker_by_ap={safe_str(tr.get("ras_ras_id_aparelho","")): tr for tr in trackers_raw}
                except: tracker_by_veic={}; tracker_by_ap={}
                rows=[]; ac=0
                for ev in events:
                    d_gps=safe_str(ev.get("ras_eve_data_gps")); dt_gps=parse_dt(d_gps)
                    if dt_gps is None: continue
                    diff_s=max(0,(now-dt_gps).total_seconds())
                    if diff_s<tol_s: continue
                    ac+=1
                    if diff_s<3600: atraso=f"{diff_s/60:.0f} min"; tag="al_med"
                    elif diff_s<14400: atraso=f"{diff_s/3600:.1f} h"; tag="al_alto"
                    else: atraso=f"{diff_s/3600:.1f} h" if diff_s<86400 else f"{diff_s/86400:.1f} dias"; tag="al_crit"
                    ign=safe_int(ev.get("ras_eve_ignicao",0)); gps=safe_int(ev.get("ras_eve_gps_status",0))
                    d_env=safe_str(ev.get("ras_eve_data_enviado")); vid_str=safe_str(ev.get("ras_vei_id",""))
                    ap_id=safe_str(ev.get("ras_ras_id_aparelho",""))
                    tr=tracker_by_veic.get(vid_str) or tracker_by_ap.get(ap_id) or {}
                    rows.append(((safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                        safe_str(ev.get("ras_mot_nome")),safe_str(ev.get("ras_cli_desc")),
                        d_gps,d_env,atraso,"🟢 ON" if ign else "⚫ OFF","✓ OK" if gps else "✗ FALHA",
                        safe_str(tr.get("ras_ras_chip")),safe_str(tr.get("ras_ras_id_aparelho") or tr.get("ras_ras_id")),
                        safe_str(tr.get("ras_ras_prd_id") or tr.get("ras_ras_modelo")),
                        safe_str(tr.get("ras_ras_linha")),safe_str(tr.get("ras_ras_operadora") or tr.get("ras_ras_chip_operadora"))),
                        tag,diff_s))
                rows.sort(key=lambda x:x[2],reverse=True)
                _cache["rows"]=rows; _render(rows)
                lb.config(text=f"Total: {len(events)}  |  ⏰ Desatualizados: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"🔍 VERIFICAR",verificar,C["purple"]).pack(side="left",padx=8)
        mk_export_btn(c,self._t_des).pack(side="left",padx=4)
        auto_refresh_register("desatualizados",verificar)
        self.after(600,verificar)