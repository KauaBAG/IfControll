"""
IFControll v2.0 - Sistema completo de gestao de frota via API Fulltrack2
"""
import requests, json, re, math, threading, csv, os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from theme_manager import (
        C, toggle_theme, get_theme_label, mk_theme_btn,
        register_theme_listener, _repaint
    )
from auto_refresh_export import fmt_now_default, fmt_hours_ago, fmt_days_ago
from auto_refresh_export import (
        now_str, ts, parse_dt, now_br,
        auto_refresh_register, auto_refresh_loop, auto_refresh_run_all,
        auto_refresh_set_enabled, mk_refresh_controls,
        export_universal, mk_export_btn, bind_global_copy,
    )
from tab_cronologia import TabCronologia
from credencials import API_KEY, SECRET_KEY, BASE_URL, AUTH

def safe_int(v, default=0):
    if v is None: return default
    try: return int(float(str(v).replace(",",".")))
    except: return default

def safe_float(v, default=0.0):
    if v is None: return default
    try: return float(str(v).replace(",","."))
    except: return default

def safe_str(v, default="—"):
    s = str(v).strip() if v is not None else ""
    return default if s in ("","None","null") else s

def haversine(lat1,lon1,lat2,lon2):
    try:
        R=6371.0; la1,lo1,la2,lo2=(math.radians(safe_float(x)) for x in [lat1,lon1,lat2,lon2])
        dlat,dlon=la2-la1,lo2-lo1
        a=math.sin(dlat/2)**2+math.cos(la1)*math.cos(la2)*math.sin(dlon/2)**2
        return R*2*math.asin(math.sqrt(max(0,min(1,a))))
    except: return 0.0

def hms(s):
    s=max(0,int(s)); return f"{s//3600:02d}h {(s%3600)//60:02d}m"

def export_tree(tree, title="Exportar CSV"):
    """Exporta os dados de um Treeview para CSV."""
    cols = [tree.heading(c)["text"] for c in tree["columns"]]
    rows = [tree.item(r)["values"] for r in tree.get_children()]
    if not rows:
        messagebox.showinfo("Exportar", "Nenhum dado para exportar.")
        return
    path = filedialog.asksaveasfilename(
        title=title, defaultextension=".csv",
        filetypes=[("CSV","*.csv"),("Todos","*.*")],
        initialfile=f"ifcontroll_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    if not path: return
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cols)
            w.writerows(rows)
        messagebox.showinfo("Exportar", f"Arquivo salvo:\n{path}")
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")

def export_text(text_widget, title="Exportar TXT"):
    """Exporta conteúdo de um Text widget para arquivo."""
    content = text_widget.get("1.0", "end").strip()
    if not content:
        messagebox.showinfo("Exportar", "Nenhum conteúdo para exportar.")
        return
    path = filedialog.asksaveasfilename(
        title=title, defaultextension=".txt",
        filetypes=[("Texto","*.txt"),("CSV","*.csv"),("Todos","*.*")],
        initialfile=f"ifcontroll_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    if not path: return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("Exportar", f"Arquivo salvo:\n{path}")
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")

# ─── API LAYER ───────────────────────────────────────────────────────────────
def _req(method, path, params=None, body=None, timeout=30):
    url = f"{BASE_URL}{path}/run"
    p   = {**AUTH, **(params or {})}
    try:
        if method=="GET":    r=requests.get(url,params=p,timeout=timeout)
        elif method=="POST": r=requests.post(url,json={**(body or {}),**AUTH},params=AUTH,timeout=timeout)
        elif method=="PUT":  r=requests.put(url,json={**(body or {}),**AUTH},params=AUTH,timeout=timeout)
        elif method=="DEL":  r=requests.delete(url,params=p,timeout=timeout)
        else: return {},0
        return r.json(), r.status_code
    except Exception as e: return {"status":False,"error":str(e)},0

def api_get(path,params=None):  d,_=_req("GET",path,params=params); return d
def api_post(path,body):        return _req("POST",path,body=body)
def api_put(path,body):         return _req("PUT",path,body=body)
def api_del(path):              return _req("DEL",path)

def extract_list(d):
    if isinstance(d,list): return d
    if isinstance(d,dict):
        if "data" in d:
            v=d["data"]
            if isinstance(v,list): return v
            if isinstance(v,dict):
                for k in ("eventos","data"):
                    if k in v and isinstance(v[k],list): return v[k]
        for v in d.values():
            if isinstance(v,list) and v: return v
    return []

def get_all_events():     return extract_list(api_get("/events/all").get("data",[]))
def get_vehicles_all():   return extract_list(api_get("/vehicles/all").get("data",[]))
def get_alerts_all():     return extract_list(api_get("/alerts/all").get("data",[]))
def get_clients_all():    return extract_list(api_get("/clients/all").get("data",[]))
def get_trackers_all():   return extract_list(api_get("/trackers/all").get("data",[]))
def get_passengers_all(): return extract_list(api_get("/passenger/all").get("data",[]))
def get_alert_types():    return extract_list(api_get("/alerts/types").get("data",[]))
def get_fences_all():
    resp=api_get("/fence/all"); msg=resp.get("message",[])
    if isinstance(msg,list) and msg and isinstance(msg[0],list): return msg[0]
    return extract_list(resp)

def find_vehicle(q):
    nq=re.sub(r"[^A-Z0-9]","",q.upper())
    for ev in get_all_events():
        if re.sub(r"[^A-Z0-9]","",str(ev.get("ras_vei_placa","")).upper())==nq: return ev
        if nq in re.sub(r"[^A-Z0-9]","",str(ev.get("ras_vei_veiculo","")).upper()): return ev
    return None      

# ─── WIDGET HELPERS ──────────────────────────────────────────────────────────
def apply_tree_style(name, hcol=None):
    s=ttk.Style(); s.theme_use("clam")
    s.configure(f"{name}.Treeview",background=C["surface2"],foreground=C["text"],
                rowheight=26,fieldbackground=C["surface2"],borderwidth=0,font=("Consolas",9))
    s.configure(f"{name}.Treeview.Heading",background=C["surface3"],
                foreground=hcol or C["accent"],font=("Helvetica Neue",9,"bold"),borderwidth=0,relief="flat")
    s.map(f"{name}.Treeview",background=[("selected",C["accent2"])])
    return f"{name}.Treeview"

def mk_tree(parent, cols, ws, sname="B", hcol=None, h=12):
    style=apply_tree_style(sname,hcol)
    fr=tk.Frame(parent,bg=C["bg"])
    t=ttk.Treeview(fr,columns=cols,show="headings",style=style,height=h)
    for c,w in zip(cols,ws): t.heading(c,text=c,anchor="w"); t.column(c,width=w,anchor="w",stretch=True)
    vs=ttk.Scrollbar(fr,orient="vertical",command=t.yview)
    hs=ttk.Scrollbar(fr,orient="horizontal",command=t.xview)
    t.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
    vs.pack(side="right",fill="y"); hs.pack(side="bottom",fill="x"); t.pack(fill="both",expand=True)
    fr.pack(fill="both",expand=True); return t

def lbl(p,text,size=10,bold=False,col=None,bg=None,**kw):
    return tk.Label(p,text=text,bg=bg or C["bg"],fg=col or C["text"],
                    font=("Helvetica Neue",size,"bold" if bold else "normal"),**kw)

def ent(p,w=None,**kw):
    e=tk.Entry(p,bg=C["surface3"],fg=C["text"],insertbackground=C["accent"],relief="flat",
               highlightthickness=1,highlightbackground=C["border"],highlightcolor=C["accent"],
               font=("Helvetica Neue",10),**kw)
    if w: e.config(width=w)
    return e

def btn(p,text,cmd,bg=None,fg=None,px=14,py=6,w=None):
    col=bg or C["accent"]
    b=tk.Label(p,text=text,bg=col,fg=fg or C["bg"],
               font=("Helvetica Neue",9,"bold"),padx=px,pady=py,cursor="hand2",relief="flat")
    if w: b.config(width=w)
    def _on(e): b.config(bg=_lt(col))
    def _off(e): b.config(bg=col)
    b.bind("<Enter>",_on); b.bind("<Leave>",_off); b.bind("<Button-1>",lambda e:cmd())
    return b

def _lt(h):
    h=h.lstrip("#"); r,g,b=int(h[:2],16),int(h[2:4],16),int(h[4:],16)
    return f"#{min(255,r+28):02x}{min(255,g+28):02x}{min(255,b+28):02x}"

def txtbox(p,h=6):
    fr=tk.Frame(p,bg=C["surface2"],highlightthickness=1,highlightbackground=C["border"])
    t=tk.Text(fr,height=h,bg=C["surface2"],fg=C["text"],insertbackground=C["accent"],
              relief="flat",font=("Consolas",9),padx=8,pady=6,selectbackground=C["accent2"],state="disabled")
    sb=tk.Scrollbar(fr,command=t.yview,bg=C["surface2"],troughcolor=C["bg"],relief="flat")
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right",fill="y"); t.pack(fill="both",expand=True)
    return fr,t

def write(t,text,col=None):
    t.config(state="normal"); t.delete("1.0","end")
    t.config(fg=col or C["text"]); t.insert("end",text); t.config(state="disabled")

def sec(p,title,col=None):
    f=tk.Frame(p,bg=C["bg"]); f.pack(fill="x",pady=(10,4))
    tk.Label(f,text=title,bg=C["bg"],fg=col or C["accent"],font=("Helvetica Neue",9,"bold")).pack(side="left")
    tk.Frame(f,bg=C["border"],height=1).pack(side="left",fill="x",expand=True,padx=(6,0),pady=6)

def loading(t): write(t,"⏳  Aguardando API...",C["accent"])
def err(t,m):   write(t,f"✖  {m}",C["danger"])
def ok(t,m):    write(t,f"✔  {m}",C["success"])

def interval_row(parent):
    r=tk.Frame(parent,bg=C["bg"]); r.pack(fill="x",pady=3)
    lbl(r,"Início:",9,col=C["text_mid"]).pack(side="left",anchor="w",padx=(0,4))
    ei=ent(r,w=18); ei.pack(side="left",padx=(0,16),ipady=4)
    ei.insert(0,fmt_hours_ago(8))
    lbl(r,"Fim:",9,col=C["text_mid"]).pack(side="left")
    ef=ent(r,w=18); ef.pack(side="left",ipady=4)
    ef.insert(0,datetime.now().strftime("%d/%m/%Y %H:%M"))
    return ei,ef

def mk_export_btn(parent, tree_or_text, is_text=False):
    """Cria botão de exportação padronizado."""
    def do_export():
        if is_text:
            export_text(tree_or_text)
        else:
            export_tree(tree_or_text)
    return btn(parent,"📥 EXPORTAR CSV",do_export,C["surface3"],C["accent"],px=10,py=5)

# ─── ABA 1: DASHBOARD ────────────────────────────────────────────────────────
class TabDashboard(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()
        auto_refresh_register("dashboard", self.refresh)

    def _build(self):
        sf=tk.Frame(self,bg=C["surface"]); sf.pack(fill="x")
        self.s_total  = self._stat(sf,"VEÍCULOS","—",C["blue"])
        self.s_on     = self._stat(sf,"IGN ON","—",C["green"])
        self.s_off    = self._stat(sf,"IGN OFF","—",C["text_mid"])
        self.s_nogps  = self._stat(sf,"SEM GPS","—",C["danger"])
        self.s_vmax   = self._stat(sf,"MAIS RÁPIDO","—",C["yellow"])
        self.s_upd    = self._stat(sf,"ATUALIZADO","—",C["text_dim"])
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")

        ctrl=tk.Frame(self,bg=C["bg"]); ctrl.pack(fill="x",padx=10,pady=6)
        btn(ctrl,"⟳  ATUALIZAR",self.refresh,C["accent"]).pack(side="left")
        self.auto=tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl,text="Auto 30s",variable=self.auto,bg=C["bg"],fg=C["text_mid"],
                       activebackground=C["bg"],selectcolor=C["surface3"],
                       font=("Helvetica Neue",9)).pack(side="left",padx=8)
        self.se=ent(ctrl,w=24); self.se.pack(side="left",padx=(20,4),ipady=4)
        self.se.insert(0,"Filtrar placa / motorista...")
        self.se.bind("<FocusIn>",lambda e:self._clr())
        self.se.bind("<KeyRelease>",lambda e:self._filter())
        btn(ctrl,"LIMPAR",self._clear_f,C["surface3"],C["text"]).pack(side="left",padx=4)
        # Exportar na barra de controle
        mk_export_btn(ctrl, None).pack(side="right",padx=4)
        # Guardar referência para exportação depois
        self._export_ref = ctrl

        cols=("Placa","Veículo","Motorista","Cliente","Ign.","Vel. km/h","GPS","Satél.","Bat.%","Volt.","Última GPS")
        ws=(80,130,130,130,70,80,70,60,60,70,150)
        self.tree=mk_tree(self,cols,ws,"Dash",C["accent"],18)
        self.tree.tag_configure("on",background=C["surface2"])
        self.tree.tag_configure("off",background=C["surface3"])

        # Recriar botão com referência correta ao tree
        for w in ctrl.winfo_children():
            if isinstance(w,tk.Label) and "EXPORTAR" in w.cget("text"):
                w.destroy()
        mk_export_btn(ctrl,self.tree).pack(side="right",padx=4)

        self._data=[]; self.after(300,self.refresh); self.after(30000,self._loop)

    def _stat(self,p,label,val,col):
        f=tk.Frame(p,bg=C["surface"]); f.pack(side="left",padx=18,pady=8)
        tk.Label(f,text=label,bg=C["surface"],fg=C["text_dim"],font=("Helvetica Neue",7,"bold")).pack()
        lb=tk.Label(f,text=val,bg=C["surface"],fg=col,font=("Helvetica Neue",14,"bold")); lb.pack()
        return lb

    def _clr(self):
        if self.se.get()=="Filtrar placa / motorista...": self.se.delete(0,"end")

    def _filter(self):
        q=re.sub(r"[^A-Z0-9]","",self.se.get().upper())
        for r in self.tree.get_children(): self.tree.delete(r)
        for ev in self._data:
            if not q or q in re.sub(r"[^A-Z0-9]","",str(ev.get("ras_vei_placa","")).upper()) \
                     or q in re.sub(r"[^A-Z0-9]","",str(ev.get("ras_mot_nome","")).upper()):
                self._row(ev)

    def _clear_f(self):
        self.se.delete(0,"end"); self.se.insert(0,"Filtrar placa / motorista...")
        self._render(self._data)

    def _row(self,ev):
        ign=safe_int(ev.get("ras_eve_ignicao",0)); gps=safe_int(ev.get("ras_eve_gps_status",0))
        self.tree.insert("","end",values=(
            safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
            safe_str(ev.get("ras_mot_nome")),safe_str(ev.get("ras_cli_desc")),
            "🟢 ON" if ign else "⚫ OFF",safe_int(ev.get("ras_eve_velocidade",0)),
            "✓ OK" if gps else "✗ FALHA",safe_int(ev.get("ras_eve_satelites",0)),
            f"{safe_int(ev.get('ras_eve_porc_bat_backup',100))}%",
            f"{safe_float(ev.get('ras_eve_voltagem',0)):.1f}V",
            safe_str(ev.get("ras_eve_data_gps")),
        ),tags=("on" if ign else "off",))

    def _render(self,data):
        for r in self.tree.get_children(): self.tree.delete(r)
        on=off=no_gps=0; vmax=0
        for ev in data:
            ign=safe_int(ev.get("ras_eve_ignicao",0)); gps=safe_int(ev.get("ras_eve_gps_status",0))
            vel=safe_int(ev.get("ras_eve_velocidade",0))
            if ign: on+=1
            else: off+=1
            if not gps: no_gps+=1
            vmax=max(vmax,vel); self._row(ev)
        self.s_total.config(text=str(len(data))); self.s_on.config(text=str(on))
        self.s_off.config(text=str(off)); self.s_nogps.config(text=str(no_gps))
        self.s_vmax.config(text=f"{vmax} km/h"); self.s_upd.config(text=now_str())

    def refresh(self):
        def t():
            d=get_all_events(); self._data=d; self._render(d)
        threading.Thread(target=t,daemon=True).start()

    def _loop(self):
        if self.auto.get(): self.refresh()
        self.after(30000,self._loop)

# ─── ABA 2: ALERTAS ──────────────────────────────────────────────────────────
class TabAlertas(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)
        # Abertos
        f=tk.Frame(nb,bg=C["bg"]); nb.add(f,text="  Alertas Abertos  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cols=("ID Veículo","Descrição","Data","Tipo ID","Lat","Lon")
        ws=(90,220,150,70,110,110)
        t=mk_tree(f,cols,ws,"Aler",C["danger"],14)
        def load():
            lb.config(text="⏳...")
            def task():
                d=get_alerts_all()
                for r in t.get_children(): t.delete(r)
                for a in d:
                    t.insert("","end",values=(safe_str(a.get("ras_eal_id_veiculo")),
                        safe_str(a.get("ras_eal_descricao")),safe_str(a.get("ras_eal_data_alerta")),
                        safe_str(a.get("ras_eal_id_alerta_tipo")),
                        safe_str(a.get("ras_eal_latitude")),safe_str(a.get("ras_eal_longitude"))))
                lb.config(text=f"{len(d)} alertas | {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⟳  ATUALIZAR",load,C["danger"]).pack(side="left")
        mk_export_btn(c,t).pack(side="left",padx=6)
        self.after(300,load)
        # Por período
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  Por Período  ")
        c2=tk.Frame(f2,bg=C["bg"]); c2.pack(fill="x",padx=8,pady=6)
        lbl(c2,"Início:").pack(side="left")
        ei=ent(c2,w=18); ei.pack(side="left",padx=4,ipady=4)
        ei.insert(0,fmt_hours_ago(7))
        lbl(c2,"  Fim:").pack(side="left")
        ef=ent(c2,w=18); ef.pack(side="left",padx=4,ipady=4)
        ef.insert(0,fmt_now_default())
        lb2=lbl(c2,"",col=C["text_dim"]); lb2.pack(side="right")
        cols2=("ID Veículo","Descrição","Data","Baixado","Motivo","Obs","Lat","Lon")
        ws2=(90,180,140,70,130,160,110,110)
        t2=mk_tree(f2,cols2,ws2,"AlerP",C["warn"],14)
        def buscar2():
            lb2.config(text="⏳...")
            def task():
                try:
                    ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
                except: lb2.config(text="⚠ Datas inválidas"); return
                d=extract_list(api_get(f"/alerts/period/initial/{ts(ini)}/final/{ts(fim)}").get("data",[]))
                for r in t2.get_children(): t2.delete(r)
                for a in d:
                    t2.insert("","end",values=(safe_str(a.get("ras_eal_id_veiculo")),
                        safe_str(a.get("ras_eal_descricao")),safe_str(a.get("ras_eal_data_alerta")),
                        "Sim" if safe_int(a.get("ras_eal_baixado")) else "Não",
                        safe_str(a.get("ras_eal_descricao_motivo")),safe_str(a.get("ras_eal_obs")),
                        safe_str(a.get("ras_eal_latitude")),safe_str(a.get("ras_eal_longitude"))))
                lb2.config(text=f"{len(d)} alertas | {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c2,"BUSCAR",buscar2,C["warn"]).pack(side="left",padx=8)
        mk_export_btn(c2,t2).pack(side="left",padx=4)
        # Fechar
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  Fechar Alerta  ")
        b3=tk.Frame(f3,bg=C["bg"]); b3.pack(fill="both",expand=True,padx=20,pady=16)
        sec(b3,"FECHAR ALERTA")
        lbl(b3,"ID do Alerta:",col=C["text_mid"]).pack(anchor="w",pady=(4,2))
        e_id=ent(b3); e_id.pack(fill="x",ipady=5)
        lbl(b3,"Motivo (número):",col=C["text_mid"]).pack(anchor="w",pady=(10,2))
        e_mot=ent(b3); e_mot.pack(fill="x",ipady=5)
        lbl(b3,"Observação:",col=C["text_mid"]).pack(anchor="w",pady=(10,2))
        e_obs=ent(b3); e_obs.pack(fill="x",ipady=5)
        _f,res=txtbox(b3,5); _f.pack(fill="x",pady=(12,0))
        def fechar():
            aid=e_id.get().strip()
            if not aid: write(res,"⚠ Informe o ID.",C["warn"]); return
            write(res,"⏳ Enviando...",C["accent"])
            def task():
                resp,code=api_post(f"/alerts/close/id/{aid}",
                    {"ras_eal_motivo":safe_int(e_mot.get() or 0),"ras_eal_obs":e_obs.get().strip()})
                if resp.get("status"): ok(res,f"Alerta {aid} fechado! HTTP {code}")
                else: err(res,f"Falha HTTP {code}\n{json.dumps(resp,indent=2)}")
            threading.Thread(target=task,daemon=True).start()
        btn(b3,"FECHAR ALERTA",fechar,C["danger"]).pack(pady=(12,0))
        mk_export_btn(b3,res,is_text=True).pack(pady=(6,0))
        # Tipos
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  Tipos  ")
        c4=tk.Frame(f4,bg=C["bg"]); c4.pack(fill="x",padx=8,pady=6)
        lb4=lbl(c4,"",col=C["text_dim"]); lb4.pack(side="right")
        t4=mk_tree(f4,("ID","Descrição"),(70,340),"AlerT",C["orange"],14)
        def load4():
            def task():
                d=get_alert_types()
                for r in t4.get_children(): t4.delete(r)
                for a in d: t4.insert("","end",values=(safe_str(a.get("ras_eat_id")),safe_str(a.get("ras_eat_descricao"))))
                lb4.config(text=f"{len(d)} tipos")
            threading.Thread(target=task,daemon=True).start()
        btn(c4,"CARREGAR",load4,C["orange"]).pack(side="left")
        mk_export_btn(c4,t4).pack(side="left",padx=6)
        self.after(400,load4)

# ─── ABA 3: CERCAS ───────────────────────────────────────────────────────────
class TabCercas(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)
        # Listar
        f=tk.Frame(nb,bg=C["bg"]); nb.add(f,text="  Todas as Cercas  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cols=("ID","Cliente","Nome","Ativa","Cor","Início","Fim","Veículos")
        ws=(70,80,180,60,80,80,80,200)
        t=mk_tree(f,cols,ws,"Fenc",C["green"],14)
        def load():
            lb.config(text="⏳...")
            def task():
                d=get_fences_all()
                for r in t.get_children(): t.delete(r)
                for fc in d:
                    veics=",".join(str(v) for v in (fc.get("ras_vei_id") or []))
                    t.insert("","end",values=(safe_str(fc.get("fence_id")),safe_str(fc.get("ras_vei_id_cli")),
                        safe_str(fc.get("ras_cer_observacao")),"Sim" if fc.get("is_active") else "Não",
                        safe_str(fc.get("color")),safe_str(fc.get("start_time")),
                        safe_str(fc.get("end_time")),veics[:50] or "—"))
                lb.config(text=f"{len(d)} cercas | {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⟳  CARREGAR",load,C["green"]).pack(side="left")
        mk_export_btn(c,t).pack(side="left",padx=6)
        self.after(300,load)
        # Eventos por cliente
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  Eventos por Cliente  ")
        c2=tk.Frame(f2,bg=C["bg"]); c2.pack(fill="x",padx=8,pady=6)
        lbl(c2,"ID Cliente:").pack(side="left")
        e_cli=ent(c2,w=10); e_cli.pack(side="left",padx=4,ipady=4)
        lbl(c2,"  Início:").pack(side="left")
        ei=ent(c2,w=16); ei.pack(side="left",padx=4,ipady=4)
        ei.insert(0,fmt_hours_ago(8))
        lbl(c2,"  Fim:").pack(side="left")
        ef=ent(c2,w=16); ef.pack(side="left",padx=4,ipady=4)
        ef.insert(0,datetime.now().strftime("%d/%m/%Y %H:%M"))
        lb2=lbl(c2,"",col=C["text_dim"]); lb2.pack(side="right")
        cols2=("ID Veículo","Placa","Veículo","Cerca","Entrada","Saída","Permanência")
        ws2=(80,80,130,180,140,140,110)
        t2=mk_tree(f2,cols2,ws2,"FencE",C["green"],14)
        def buscar2():
            lb2.config(text="⏳...")
            def task():
                try:
                    ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
                except: lb2.config(text="⚠ Datas inválidas"); return
                cli=e_cli.get().strip() or "0"
                d=extract_list(api_get(f"/fence/client/id/{cli}/initial/{ts(ini)}/final/{ts(fim)}").get("data",[]))
                for r in t2.get_children(): t2.delete(r)
                for ev in d:
                    t2.insert("","end",values=(safe_str(ev.get("ras_vei_id")),safe_str(ev.get("ras_vei_placa")),
                        safe_str(ev.get("ras_vei_veiculo")),safe_str(ev.get("ras_cer_observacao")),
                        safe_str(ev.get("data_entrada")),safe_str(ev.get("data_saida")),
                        safe_str(ev.get("tempo_permanencia"))))
                lb2.config(text=f"{len(d)} eventos | {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c2,"BUSCAR",buscar2,C["green"]).pack(side="left",padx=8)
        mk_export_btn(c2,t2).pack(side="left",padx=4)
        # Criar cerca
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  Criar Cerca  ")
        b3=tk.Frame(f3,bg=C["bg"]); b3.pack(fill="both",expand=True,padx=20,pady=12)
        sec(b3,"NOVA CERCA VIRTUAL")
        lbl(b3,"Nome da cerca:",col=C["text_mid"]).pack(anchor="w",pady=(4,2))
        e_nm=ent(b3); e_nm.pack(fill="x",ipady=5)
        rr=tk.Frame(b3,bg=C["bg"]); rr.pack(fill="x",pady=6)
        lbl(rr,"ID Cliente:").pack(side="left")
        e_cl=ent(rr,w=12); e_cl.pack(side="left",padx=6,ipady=5)
        lbl(rr,"  Cor:").pack(side="left")
        e_cr=ent(rr,w=12); e_cr.pack(side="left",padx=6,ipady=5); e_cr.insert(0,"#00C8F8")
        lbl(b3,"IDs dos veículos (vírgula):",col=C["text_mid"]).pack(anchor="w",pady=(8,2))
        e_vs=ent(b3); e_vs.pack(fill="x",ipady=5)
        lbl(b3,"Coordenadas (lat,lon — uma por linha):",col=C["text_mid"]).pack(anchor="w",pady=(8,2))
        _,t_co=txtbox(b3,5); _.pack(fill="x"); t_co.config(state="normal")
        t_co.insert("end","-22.195034,-49.676055\n-22.203934,-49.571685\n-22.295449,-49.665069")
        _fr,res3=txtbox(b3,4); _fr.pack(fill="x",pady=(8,0))
        def criar():
            write(res3,"⏳ Criando...",C["accent"])
            def task():
                veics=[safe_int(v.strip()) for v in e_vs.get().split(",") if v.strip()]
                coords=[]
                for ln in t_co.get("1.0","end").strip().split("\n"):
                    pp=ln.strip().split(",")
                    if len(pp)==2: coords.append([pp[0].strip(),pp[1].strip()])
                payload={"ras_cer_observacao":e_nm.get().strip(),"ras_vei_id_cli":safe_int(e_cl.get()),
                    "color":e_cr.get().strip() or "blue","is_active":True,"ras_vei_id":veics,
                    "contacts_id":[],"coordinates":coords,"start_time":"00:00:00","end_time":"23:59:59",
                    "group_id":0,"days_active":{d:True for d in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]},
                    "shipping_settings":{"send_alert_email":False,"send_alert_client":True,"send_alert_mobile":False,
                                         "send_alert_fullarm":False,"send_alert_in_screen":True,"send_alert_monitoring":False},
                    "generate_alerts":{"ignition_on":False,"ignition_off":False,"inside_fence":True,"outside_fence":True,
                                       "speed_limit":{"is_active":False,"limit":0},
                                       "time_inside_fence":{"is_active":False,"time":"00:00:00"},
                                       "time_outside_fence":{"is_active":False,"time":"00:00:00"},
                                       "time_on":{"is_active":False,"time":"00:00:00"},
                                       "time_off":{"is_active":False,"time":"00:00:00"}}}
                resp,code=api_put("/fence/save",payload)
                if resp.get("status") or code in (200,201): ok(res3,f"Cerca criada! HTTP {code}")
                else: err(res3,f"Falha {code}\n{json.dumps(resp,indent=2)}")
            threading.Thread(target=task,daemon=True).start()
        btn(b3,"CRIAR CERCA",criar,C["green"]).pack(pady=(10,0))
        # Deletar
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  Deletar  ")
        b4=tk.Frame(f4,bg=C["bg"]); b4.pack(fill="both",expand=True,padx=20,pady=16)
        sec(b4,"DELETAR CERCA")
        lbl(b4,"fence_id:",col=C["text_mid"]).pack(anchor="w",pady=(4,2))
        e_fid=ent(b4); e_fid.pack(fill="x",ipady=5)
        _f4,res4=txtbox(b4,4); _f4.pack(fill="x",pady=(12,0))
        def deletar():
            fid=e_fid.get().strip()
            if not fid: write(res4,"⚠ Informe o ID.",C["warn"]); return
            if not messagebox.askyesno("Confirmar","Deletar permanentemente?",parent=self): return
            def task():
                resp,code=api_del(f"/fence/delete/id/{fid}")
                if resp.get("status") or code in (200,204): ok(res4,f"Cerca {fid} deletada!")
                else: err(res4,f"Falha {code}")
            threading.Thread(target=task,daemon=True).start()
        btn(b4,"DELETAR",deletar,C["danger"]).pack(pady=(12,0))

# ─── ABA 4: VEÍCULOS ─────────────────────────────────────────────────────────
class TabVeiculos(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)
        # Lista
        f=tk.Frame(nb,bg=C["bg"]); nb.add(f,text="  Lista  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cols=("ID","Cli.","Placa","Veículo","Tipo","Fabricante","Ano","Cor","Veloc.Lim","Odômetro","Cadastro")
        ws=(65,65,85,140,55,90,55,70,90,90,130)
        t=mk_tree(f,cols,ws,"VL",C["blue"],14)
        def load():
            lb.config(text="⏳...")
            def task():
                d=get_vehicles_all()
                for r in t.get_children(): t.delete(r)
                for v in d:
                    t.insert("","end",values=(safe_str(v.get("ras_vei_id")),safe_str(v.get("ras_vei_id_cli")),
                        safe_str(v.get("ras_vei_placa")),safe_str(v.get("ras_vei_veiculo")),
                        safe_str(v.get("ras_vei_tipo")),safe_str(v.get("ras_vei_fabricante")),
                        safe_str(v.get("ras_vei_ano")),safe_str(v.get("ras_vei_cor")),
                        safe_str(v.get("ras_vei_velocidade_limite")),safe_str(v.get("ras_vei_odometro")),
                        safe_str(v.get("ras_vei_data_cadastro"))))
                lb.config(text=f"{len(d)} veículos")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⟳  CARREGAR",load,C["blue"]).pack(side="left")
        mk_export_btn(c,t).pack(side="left",padx=6)
        self.after(200,load)
        # Atualizar
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  Atualizar  ")
        b2=tk.Frame(f2,bg=C["bg"]); b2.pack(fill="both",expand=True,padx=20,pady=12)
        sec(b2,"ATUALIZAR VEÍCULO")
        rq=tk.Frame(b2,bg=C["bg"]); rq.pack(fill="x",pady=4)
        lbl(rq,"Placa/nome:").pack(side="left")
        e_q=ent(rq,w=20); e_q.pack(side="left",padx=8,ipady=5)
        _f2,res2=txtbox(b2,4); _f2.pack(fill="x",pady=(0,8))
        fields={}
        for lab,key in [("Placa","ras_vei_placa"),("Descrição","ras_vei_veiculo"),("Chassi","ras_vei_chassi"),
                        ("Ano","ras_vei_ano"),("Cor","ras_vei_cor"),("Veloc. Limite","ras_vei_velocidade_limite"),
                        ("Odômetro","ras_vei_odometro"),("Horímetro","ras_vei_horimetro")]:
            r=tk.Frame(b2,bg=C["bg"]); r.pack(fill="x",pady=2)
            lbl(r,f"{lab}:",9,col=C["text_mid"],width=14).pack(side="left",anchor="w")
            e=ent(r); e.pack(side="left",fill="x",expand=True,ipady=4); fields[key]=e
        def popular2():
            q=e_q.get().strip()
            if not q: return
            loading(res2)
            def task():
                ev=find_vehicle(q)
                if not ev: err(res2,"Não encontrado."); return
                vid=safe_int(ev.get("ras_vei_id",0))
                d=extract_list(api_get(f"/vehicles/single/id/{vid}").get("data",[]))
                v=d[0] if d else ev
                for k,e in fields.items(): e.delete(0,"end"); e.insert(0,safe_str(v.get(k,""),default=""))
                ok(res2,f"Veículo {vid} carregado.")
            threading.Thread(target=task,daemon=True).start()
        btn(rq,"CARREGAR",popular2,C["accent"]).pack(side="left")
        def salvar2():
            q=e_q.get().strip()
            if not q: return
            loading(res2)
            def task():
                ev=find_vehicle(q)
                if not ev: err(res2,"Não encontrado."); return
                vid=safe_int(ev.get("ras_vei_id",0))
                resp,code=api_post(f"/vehicles/update/id/{vid}",{k:v.get() for k,v in fields.items()})
                if resp.get("status") or code in (200,201): ok(res2,f"Veículo {vid} atualizado!")
                else: err(res2,f"Falha {code}")
            threading.Thread(target=task,daemon=True).start()
        btn(b2,"💾  SALVAR",salvar2,C["green"]).pack(pady=(8,0))
        # Cadastrar
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  Cadastrar  ")
        b3=tk.Frame(f3,bg=C["bg"]); b3.pack(fill="both",expand=True,padx=20,pady=12)
        sec(b3,"CADASTRAR VEÍCULO")
        fd3={}
        for lab,key in [("ID Cliente*","ras_vei_id_cli"),("Placa*","ras_vei_placa"),("Descrição*","ras_vei_veiculo"),
                        ("Chassi","ras_vei_chassi"),("Ano","ras_vei_ano"),("Cor","ras_vei_cor"),
                        ("Tipo","ras_vei_tipo"),("Modelo","ras_vei_modelo"),("Combustível","ras_vei_combustivel"),
                        ("Consumo km/l","ras_vei_consumo"),("Veloc. Limite","ras_vei_velocidade_limite"),("Odômetro","ras_vei_odometro")]:
            r=tk.Frame(b3,bg=C["bg"]); r.pack(fill="x",pady=2)
            lbl(r,f"{lab}:",9,col=C["text_mid"],width=15).pack(side="left",anchor="w")
            e=ent(r); e.pack(side="left",fill="x",expand=True,ipady=4); fd3[key]=e
        _f3,res3=txtbox(b3,4); _f3.pack(fill="x",pady=(8,0))
        def cadastrar():
            write(res3,"⏳ Cadastrando...",C["accent"])
            def task():
                resp,code=api_put("/vehicles/save",{k:v.get() for k,v in fd3.items() if v.get().strip()})
                if resp.get("status") or code in (200,201):
                    d=extract_list(resp.get("data",resp))
                    ok(res3,f"Veículo criado! ID: {d[0].get('ras_vei_id','?') if d else '?'}")
                else: err(res3,f"Falha {code}\n{json.dumps(resp,indent=2)}")
            threading.Thread(target=task,daemon=True).start()
        btn(b3,"CADASTRAR",cadastrar,C["green"]).pack(pady=(8,0))
        # Instalação
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  Instalação  ")
        nb4=ttk.Notebook(f4); nb4.pack(fill="both",expand=True)
        fa=tk.Frame(nb4,bg=C["bg"]); nb4.add(fa,text="  Ativas  ")
        ca=tk.Frame(fa,bg=C["bg"]); ca.pack(fill="x",padx=8,pady=6)
        lba=lbl(ca,"",col=C["text_dim"]); lba.pack(side="right")
        ta=mk_tree(fa,("Inst.ID","Aparelho","Veículo","Placa","Cliente"),(100,130,160,90,160),"Inst",C["purple"],12)
        def load_inst():
            def task():
                d=extract_list(api_get("/workshop/list").get("data",[]))
                for r in ta.get_children(): ta.delete(r)
                for i in d:
                    ta.insert("","end",values=(safe_str(i.get("ras_ins_id")),safe_str(i.get("ras_ras_id_aparelho")),
                        safe_str(i.get("ras_vei_veiculo")),safe_str(i.get("ras_vei_placa")),safe_str(i.get("ras_cli_desc"))))
                lba.config(text=f"{len(d)} instalações")
            threading.Thread(target=task,daemon=True).start()
        btn(ca,"CARREGAR",load_inst,C["purple"]).pack(side="left")
        mk_export_btn(ca,ta).pack(side="left",padx=6)
        self.after(300,load_inst)
        fb=tk.Frame(nb4,bg=C["bg"]); nb4.add(fb,text="  Vincular  ")
        bb=tk.Frame(fb,bg=C["bg"]); bb.pack(fill="both",expand=True,padx=20,pady=12)
        sec(bb,"VINCULAR VEÍCULO ↔ RASTREADOR")
        lbl(bb,"ID Veículo:",col=C["text_mid"]).pack(anchor="w",pady=(4,2))
        e_vv=ent(bb); e_vv.pack(fill="x",ipady=5)
        lbl(bb,"ID Aparelho:",col=C["text_mid"]).pack(anchor="w",pady=(8,2))
        e_ap=ent(bb); e_ap.pack(fill="x",ipady=5)
        _,resv=txtbox(bb,4); _.pack(fill="x",pady=(10,0))
        def vincular():
            write(resv,"⏳...",C["accent"])
            def task():
                resp,code=api_post("/workshop/install",{"ras_vei_id":safe_int(e_vv.get()),"ras_ras_id_aparelho":e_ap.get().strip()})
                if resp.get("status") or code in (200,201): ok(resv,"Vinculado com sucesso!")
                else: err(resv,f"Falha {code}")
            threading.Thread(target=task,daemon=True).start()
        btn(bb,"VINCULAR",vincular,C["green"]).pack(pady=(8,0))
        fc=tk.Frame(nb4,bg=C["bg"]); nb4.add(fc,text="  Desvincular  ")
        bc=tk.Frame(fc,bg=C["bg"]); bc.pack(fill="both",expand=True,padx=20,pady=12)
        sec(bc,"DESVINCULAR POR ID DE INSTALAÇÃO")
        lbl(bc,"ras_ins_id:",col=C["text_mid"]).pack(anchor="w",pady=(4,2))
        e_ins=ent(bc); e_ins.pack(fill="x",ipady=5)
        _,resd=txtbox(bc,4); _.pack(fill="x",pady=(10,0))
        def desvincular():
            write(resd,"⏳...",C["accent"])
            def task():
                resp,code=api_put("/workshop/uninstall",{"ras_ins_id":safe_int(e_ins.get())})
                if resp.get("status") or code in (200,201): ok(resd,"Desvinculado!")
                else: err(resd,f"Falha {code}")
            threading.Thread(target=task,daemon=True).start()
        btn(bc,"DESVINCULAR",desvincular,C["danger"]).pack(pady=(8,0))

# ─── ABA 5: RELATÓRIOS ───────────────────────────────────────────────────────
class TabRelatorios(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()

    def _hdr(self,f):
        b=tk.Frame(f,bg=C["bg"]); b.pack(fill="x",padx=10,pady=6)
        lbl(b,"Veículo (placa/nome):",9,col=C["text_mid"]).pack(anchor="w",pady=(0,2))
        ev=ent(b); ev.pack(fill="x",ipady=5)
        ei,ef=interval_row(b)
        return b,ev,ei,ef

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)

        # ── Utilização ──
        f=tk.Frame(nb,bg=C["bg"]); nb.add(f,text="  Utilização  ")
        hdr,ev,ei,ef=self._hdr(f)
        _fr_res,res=txtbox(f,16); _fr_res.pack(fill="both",expand=True,padx=10)
        def util():
            q=ev.get().strip()
            if not q: return
            loading(res)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res,"Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
                except: write(res,"⚠ Datas inválidas.",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res,"ℹ Nenhum evento.",C["text_mid"]); return
                km=0.0; t_on=t_off=t_par=0.0; vmax=0; vels=[]; prev=None
                for ev2 in evs:
                    vel=safe_int(ev2.get("ras_eve_velocidade",0))
                    ign=safe_int(ev2.get("ras_eve_ignicao",0))
                    lat=ev2.get("ras_eve_latitude"); lon=ev2.get("ras_eve_longitude")
                    try: dt=datetime.strptime(ev2.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                    except: dt=None
                    if prev and dt and prev[0]:
                        s=max(0,(dt-prev[0]).total_seconds())
                        if prev[1]: t_on+=s
                        else: t_off+=s
                        if prev[1] and prev[2]==0: t_par+=s
                    if vel>0: vmax=max(vmax,vel); vels.append(vel)
                    if prev and prev[3] is not None and lat: km+=haversine(prev[3],prev[4],lat,lon)
                    prev=(dt,ign,vel,lat,lon)
                vmed=sum(vels)/len(vels) if vels else 0
                lines=["="*46,f"  {entry.get('ras_vei_placa','—')} — {entry.get('ras_vei_veiculo','—')}",
                    f"  Motorista: {entry.get('ras_mot_nome','—')}",
                    f"  Período  : {ini.strftime('%d/%m/%Y %H:%M')} → {fim.strftime('%d/%m/%Y %H:%M')}",
                    f"  Eventos  : {len(evs)}","","  ─── Distância & Velocidade ──────────",
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

        # ── Paradas ──
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  Paradas  ")
        hdr2,ev2,ei2,ef2=self._hdr(f2)
        rmin=tk.Frame(hdr2,bg=C["bg"]); rmin.pack(fill="x",pady=3)
        lbl(rmin,"Mín. parada (min):",9,col=C["text_mid"],width=20).pack(side="left",anchor="w")
        e_min=ent(rmin,w=8); e_min.pack(side="left",ipady=4); e_min.insert(0,"5")
        _,res2=txtbox(f2,16); _.pack(fill="both",expand=True,padx=10)
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
        btn(hdr2,"⏸ ANALISAR",paradas,C["blue"]).pack(side="right",pady=4)
        mk_export_btn(hdr2,res2,is_text=True).pack(side="right",padx=4,pady=4)

        # ── Replay ──
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  Replay de Rota  ")
        hdr3,ev3,ei3,ef3=self._hdr(f3)
        cols3=("Seq","Data GPS","Lat","Lon","Vel. km/h","Ign.","GPS","Satél.")
        ws3=(50,150,110,110,90,70,60,60)
        t3=mk_tree(f3,cols3,ws3,"Replay",C["purple"],14)
        lb3=lbl(f3,"",col=C["text_dim"]); lb3.pack(anchor="e",padx=10,pady=2)
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
                for r in t3.get_children(): t3.delete(r)
                for i,ev4 in enumerate(evs,1):
                    ign=safe_int(ev4.get("ras_eve_ignicao",0))
                    t3.insert("","end",values=(i,safe_str(ev4.get("ras_eve_data_gps")),
                        safe_str(ev4.get("ras_eve_latitude")),safe_str(ev4.get("ras_eve_longitude")),
                        safe_int(ev4.get("ras_eve_velocidade",0)),
                        "ON" if ign else "OFF","✓" if safe_int(ev4.get("ras_eve_gps_status")) else "✗",
                        safe_int(ev4.get("ras_eve_satelites",0))),tags=("on" if ign else "off",))
                t3.tag_configure("on",background=C["surface2"]); t3.tag_configure("off",background=C["surface3"])
                lb3.config(text=f"{entry.get('ras_vei_placa','—')}  |  {len(evs)} pontos  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(hdr3,"🗺 REPLAY",replay,C["purple"]).pack(side="right",pady=4)
        mk_export_btn(hdr3,t3).pack(side="right",padx=4,pady=4)

        # ── Temperatura Viva ──
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  Temperatura Viva  ")
        c4=tk.Frame(f4,bg=C["bg"]); c4.pack(fill="x",padx=10,pady=6)
        lbl(c4,"Placa/nome:",9,col=C["text_mid"]).pack(side="left")
        e4=ent(c4,w=22); e4.pack(side="left",padx=8,ipady=4)
        _,res4=txtbox(f4,18); _.pack(fill="both",expand=True,padx=10)
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
                ign=safe_int(entry.get("ras_eve_ignicao",0))
                lines=["="*42,f"  Placa  : {entry.get('ras_vei_placa','—')}",
                    f"  Veículo: {entry.get('ras_vei_veiculo','—')}",
                    f"  Ignição: {'🟢 ON' if ign else '⚫ OFF'}",
                    f"  Frio   : {'🟢 ON' if safe_int(entry.get('ras_eve_input',0)[2]) else '⚫ OFF'}",
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
        btn(c4,"🌡 CONSULTAR",temp,C["orange"]).pack(side="left")
        mk_export_btn(c4,res4,is_text=True).pack(side="left",padx=6)

        # ── Cadeia de Frio ──
        f5=tk.Frame(nb,bg=C["bg"]); nb.add(f5,text="  Cadeia de Frio  ")
        hdr5,ev5,ei5,ef5=self._hdr(f5)
        rt=tk.Frame(hdr5,bg=C["bg"]); rt.pack(fill="x",pady=3)
        lbl(rt,"Temp. mín (°C):",9,col=C["text_mid"],width=18).pack(side="left",anchor="w")
        e_tmin=ent(rt,w=8); e_tmin.pack(side="left",ipady=4); e_tmin.insert(0,"-5")
        lbl(rt,"  Temp. máx (°C):",9,col=C["text_mid"]).pack(side="left")
        e_tmax=ent(rt,w=8); e_tmax.pack(side="left",padx=8,ipady=4); e_tmax.insert(0,"8")
        _,res5=txtbox(f5,14); _.pack(fill="both",expand=True,padx=10)
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
                            sn=f"sensor_{i+1}"
                            temps.setdefault(sn,[]).append(fv)
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
                    for d,s,v in viols[-5:]:
                        lines.append(f"  {'🔴' if v>tmax else '🔵'} {d}  {s}: {v:.1f}°C")
                col=C["success"] if pct>=90 else C["warn"] if pct>=70 else C["danger"]
                write(res5,"\n".join(lines),col)
            threading.Thread(target=task,daemon=True).start()
        btn(hdr5,"❄ RELATÓRIO",frio,C["blue"]).pack(side="right",pady=4)
        mk_export_btn(hdr5,res5,is_text=True).pack(side="right",padx=4,pady=4)

        # ── Alertas Velocidade ──
        f6=tk.Frame(nb,bg=C["bg"]); nb.add(f6,text="  Alertas Veloc.  ")
        c6=tk.Frame(f6,bg=C["bg"]); c6.pack(fill="x",padx=8,pady=6)
        lbl(c6,"Limite (km/h):").pack(side="left")
        e_lim=ent(c6,w=6); e_lim.pack(side="left",padx=6,ipady=4); e_lim.insert(0,"80")
        lb6=lbl(c6,"",col=C["text_dim"]); lb6.pack(side="right")
        cols6=("Placa","Motorista","Velocidade","Ignição","GPS","Data")
        ws6=(90,140,110,80,60,150)
        t6=mk_tree(f6,cols6,ws6,"AlerV",C["danger"],14)
        def alertas_vel():
            try: lim=int(e_lim.get())
            except: lim=80
            lb6.config(text="⏳ Verificando...")
            def task():
                data=get_all_events()
                for r in t6.get_children(): t6.delete(r)
                ac=0
                for ev7 in data:
                    vel=safe_int(ev7.get("ras_eve_velocidade",0))
                    if vel>lim or vel<0:
                        ac+=1
                        t6.insert("","end",values=(safe_str(ev7.get("ras_vei_placa")),
                            safe_str(ev7.get("ras_mot_nome")),f"🚨 {vel} km/h",
                            "ON" if safe_int(ev7.get("ras_eve_ignicao")) else "OFF",
                            "✓" if safe_int(ev7.get("ras_eve_gps_status")) else "✗",
                            safe_str(ev7.get("ras_eve_data_gps"))),tags=("al",))
                t6.tag_configure("al",background="#1a0808")
                lb6.config(text=f"Total: {len(data)}  |  ⚠ Alertas: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c6,"⚡ VERIFICAR",alertas_vel,C["danger"]).pack(side="left",padx=8)
        mk_export_btn(c6,t6).pack(side="left",padx=4)
        self.after(500,alertas_vel)

# ─── ABA 6: CLIENTES ─────────────────────────────────────────────────────────
class TabClientes(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)
        # Lista
        f=tk.Frame(nb,bg=C["bg"]); nb.add(f,text="  Todos  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cols=("ID","Nome","Razão Social","Endereço","Cidade","UF","CNPJ","Tipo","Liberado")
        ws=(65,160,160,160,120,50,120,50,70)
        t=mk_tree(f,cols,ws,"Cli",C["pink"],14)
        def load():
            lb.config(text="⏳...")
            def task():
                d=get_clients_all()
                for r in t.get_children(): t.delete(r)
                for c2 in d:
                    t.insert("","end",values=(safe_str(c2.get("ras_cli_id")),safe_str(c2.get("ras_cli_desc")),
                        safe_str(c2.get("ras_cli_razao")),safe_str(c2.get("ras_cli_endereco")),
                        safe_str(c2.get("ras_cli_cidade")),safe_str(c2.get("ras_cli_uf")),
                        safe_str(c2.get("ras_cli_cnpj")),safe_str(c2.get("ras_cli_tipo")),
                        safe_str(c2.get("ras_cli_liberado"))))
                lb.config(text=f"{len(d)} clientes")
            threading.Thread(target=task,daemon=True).start()
        btn(c,"⟳  CARREGAR",load,C["pink"]).pack(side="left")
        mk_export_btn(c,t).pack(side="left",padx=6)
        self.after(200,load)
        # Cadastrar
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  Cadastrar  ")
        b2=tk.Frame(f2,bg=C["bg"]); b2.pack(fill="both",expand=True,padx=20,pady=12)
        sec(b2,"NOVO CLIENTE")
        fd2={}
        for lab,key in [("Nome*","ras_cli_desc"),("Tipo (F/J)*","ras_cli_tipo"),("Razão Social","ras_cli_razao"),
                        ("Endereço","ras_cli_endereco"),("Bairro","ras_cli_bairro"),("CEP","ras_cli_cep"),
                        ("UF","ras_cli_uf"),("Cidade","ras_cli_cidade"),("CNPJ/CPF","ras_cli_cnpj")]:
            r=tk.Frame(b2,bg=C["bg"]); r.pack(fill="x",pady=2)
            lbl(r,f"{lab}:",9,col=C["text_mid"],width=18).pack(side="left",anchor="w")
            e=ent(r); e.pack(side="left",fill="x",expand=True,ipady=4); fd2[key]=e
        _,res2=txtbox(b2,4); _.pack(fill="x",pady=(8,0))
        def cad():
            write(res2,"⏳...",C["accent"])
            def task():
                resp,code=api_put("/clients/save",{k:v.get() for k,v in fd2.items() if v.get().strip()})
                if resp.get("status") or code in (200,201):
                    d=extract_list(resp.get("data",resp))
                    ok(res2,f"Cliente criado! ID: {d[0].get('ras_cli_id','?') if d else '?'}")
                else: err(res2,f"Falha {code}")
            threading.Thread(target=task,daemon=True).start()
        btn(b2,"CADASTRAR",cad,C["green"]).pack(pady=(8,0))
        # Motoristas
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  Motoristas  ")
        c3=tk.Frame(f3,bg=C["bg"]); c3.pack(fill="x",padx=8,pady=6)
        lbl(c3,"ID Cliente:").pack(side="left")
        e3=ent(c3,w=12); e3.pack(side="left",padx=8,ipady=4)
        lb3=lbl(c3,"",col=C["text_dim"]); lb3.pack(side="right")
        t3=mk_tree(f3,("ID Motorista","Nome","CPF","CNH"),(100,200,130,130),"Mot",C["yellow"],14)
        def mot():
            cid=e3.get().strip()
            if not cid: return
            lb3.config(text="⏳...")
            def task():
                d=extract_list(api_get("/drivers",{"client":cid}).get("data",[]))
                for r in t3.get_children(): t3.delete(r)
                for m in d:
                    t3.insert("","end",values=(safe_str(m.get("ras_mot_id")),safe_str(m.get("ras_mot_nome")),
                        safe_str(m.get("ras_mot_cpf")),safe_str(m.get("ras_mot_cnh"))))
                lb3.config(text=f"{len(d)} motoristas")
            threading.Thread(target=task,daemon=True).start()
        btn(c3,"BUSCAR",mot,C["yellow"]).pack(side="left")
        mk_export_btn(c3,t3).pack(side="left",padx=6)
        # Contatos
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  Contatos  ")
        c4=tk.Frame(f4,bg=C["bg"]); c4.pack(fill="x",padx=8,pady=6)
        lbl(c4,"ID Cliente:").pack(side="left")
        e4=ent(c4,w=12); e4.pack(side="left",padx=8,ipady=4)
        lb4=lbl(c4,"",col=C["text_dim"]); lb4.pack(side="right")
        cols4=("ID","Nome","Telefone","Email","Email Alerta","SMS Alerta","Principal")
        ws4=(70,160,120,180,90,90,80)
        t4=mk_tree(f4,cols4,ws4,"Cont",C["pink"],12)
        def cont():
            cid=e4.get().strip()
            if not cid: return
            def task():
                d=extract_list(api_get(f"/contacts/single/id/{cid}").get("data",[]))
                for r in t4.get_children(): t4.delete(r)
                for c2 in d:
                    t4.insert("","end",values=(safe_str(c2.get("ras_ccn_id")),safe_str(c2.get("ras_ccn_contato")),
                        safe_str(c2.get("ras_ccn_telefone")),safe_str(c2.get("ras_ccn_email")),
                        "Sim" if safe_int(c2.get("ras_ccn_email_alerta")) else "Não",
                        "Sim" if safe_int(c2.get("ras_ccn_sms_alerta")) else "Não",
                        "Sim" if safe_int(c2.get("ras_ccn_email_master")) else "Não"))
                lb4.config(text=f"{len(d)} contatos")
            threading.Thread(target=task,daemon=True).start()
        btn(c4,"BUSCAR",cont,C["pink"]).pack(side="left")
        mk_export_btn(c4,t4).pack(side="left",padx=6)

# ─── ABA 7: RASTREADORES & UTILITÁRIOS ───────────────────────────────────────
class TabRastreadores(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)
        # Rastreadores
        f=tk.Frame(nb,bg=C["bg"]); nb.add(f,text="  Rastreadores  ")
        c=tk.Frame(f,bg=C["bg"]); c.pack(fill="x",padx=8,pady=6)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        cols=("ID","Aparelho","Status","Produto","Cliente","Chip","Linha","Ult. Comunicação")
        ws=(65,120,65,80,80,110,100,160)
        t=mk_tree(f,cols,ws,"Rastr",C["orange"],14)
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
        # Veículos próximos
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  Veículos Próximos  ")
        c2=tk.Frame(f2,bg=C["bg"]); c2.pack(fill="x",padx=8,pady=6)
        lbl(c2,"ID Cliente:").pack(side="left")
        e_cl=ent(c2,w=10); e_cl.pack(side="left",padx=4,ipady=4)
        lbl(c2,"  Lat:").pack(side="left")
        e_la=ent(c2,w=14); e_la.pack(side="left",padx=4,ipady=4); e_la.insert(0,"-22.2154713")
        lbl(c2,"  Lon:").pack(side="left")
        e_lo=ent(c2,w=14); e_lo.pack(side="left",padx=4,ipady=4); e_lo.insert(0,"-49.6541367")
        lbl(c2,"  Raio(m):").pack(side="left")
        e_r=ent(c2,w=8); e_r.pack(side="left",padx=4,ipady=4); e_r.insert(0,"5000")
        lb2=lbl(c2,"",col=C["text_dim"]); lb2.pack(side="right")
        cols2=("Placa","Veículo","Tipo","Ign.","Vel.","Distância(m)","Data GPS","Lat","Lon")
        ws2=(80,130,60,60,60,110,150,110,110)
        t2=mk_tree(f2,cols2,ws2,"VPrx",C["green"],14)
        def prox():
            cid=e_cl.get().strip() or "0"; lat=e_la.get().strip(); lon=e_lo.get().strip(); r=e_r.get().strip() or "5000"
            if not lat or not lon: return
            lb2.config(text="⏳...")
            def task():
                d=extract_list(api_get(f"/vehiclesnearby/nearpoint/id/{cid}/lat/{lat}/long/{lon}/limit/{r}").get("data",[]))
                for r2 in t2.get_children(): t2.delete(r2)
                for v in d:
                    loc=v.get("loc") or ["—","—"]
                    t2.insert("","end",values=(safe_str(v.get("ras_vei_placa")),safe_str(v.get("ras_vei_veiculo")),
                        safe_str(v.get("ras_vei_tipo")),"ON" if safe_int(v.get("ras_eve_ignicao")) else "OFF",
                        safe_str(v.get("ras_eve_velocidade")),safe_str(v.get("distancia")),
                        safe_str(v.get("ras_eve_data_gps")),str(loc[0]),str(loc[1])))
                lb2.config(text=f"{len(d)} veículos próximos | {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c2,"BUSCAR",prox,C["green"]).pack(side="left",padx=8)
        mk_export_btn(c2,t2).pack(side="left",padx=4)
        # Pontos de referência
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  Pontos de Ref.  ")
        c3=tk.Frame(f3,bg=C["bg"]); c3.pack(fill="x",padx=8,pady=6)
        lbl(c3,"ID Cliente (vazio=todos):").pack(side="left")
        e3=ent(c3,w=12); e3.pack(side="left",padx=8,ipady=4)
        lb3=lbl(c3,"",col=C["text_dim"]); lb3.pack(side="right")
        cols3=("ID","Descrição","Lat","Lon","Ícone","Cidade","UF","Cadastro")
        ws3=(80,200,110,110,120,120,50,130)
        t3=mk_tree(f3,cols3,ws3,"PRef",C["accent"],14)
        def pts():
            cid=e3.get().strip()
            def task():
                if cid: d=extract_list(api_get(f"/referencepoints/client/id/{cid}").get("data",[]))
                else: d=extract_list(api_get("/referencepoints/all",{"limit":500,"offset":0}).get("data",[]))
                for r in t3.get_children(): t3.delete(r)
                for p in d:
                    t3.insert("","end",values=(safe_str(p.get("ras_ref_id")),safe_str(p.get("ras_ref_descricao")),
                        safe_str(p.get("ras_ref_latitude")),safe_str(p.get("ras_ref_longitude")),
                        safe_str(p.get("ras_ref_icone")),safe_str(p.get("ras_ref_cidade")),
                        safe_str(p.get("ras_ref_uf")),safe_str(p.get("ras_ref_data_cadastro"))))
                lb3.config(text=f"{len(d)} pontos")
            threading.Thread(target=task,daemon=True).start()
        btn(c3,"BUSCAR",pts,C["accent"]).pack(side="left")
        mk_export_btn(c3,t3).pack(side="left",padx=6)
        # Passageiros
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  Passageiros  ")
        c4=tk.Frame(f4,bg=C["bg"]); c4.pack(fill="x",padx=8,pady=6)
        lb4=lbl(c4,"",col=C["text_dim"]); lb4.pack(side="right")
        t4=mk_tree(f4,("ID","Nome","RFID","Empresa","Setor","Cargo","Cadastro"),(70,160,100,140,100,120,150),"Pass",C["accent2"],14)
        def pass_load():
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
        btn(c4,"⟳  CARREGAR",pass_load,C["accent2"]).pack(side="left")
        mk_export_btn(c4,t4).pack(side="left",padx=6)
        self.after(400,pass_load)
        # Saúde da frota
        f5=tk.Frame(nb,bg=C["bg"]); nb.add(f5,text="  Saúde da Frota  ")
        c5=tk.Frame(f5,bg=C["bg"]); c5.pack(fill="x",padx=8,pady=6)
        lb5=lbl(c5,"",col=C["text_dim"]); lb5.pack(side="right")
        cols5=("Placa","Veículo","Bat.%","Voltagem","GPS","Satél.","Ign.","Última GPS")
        ws5=(90,130,70,80,70,60,60,150)
        t5=mk_tree(f5,cols5,ws5,"Sau",C["warn"],14)
        def saude():
            lb5.config(text="⏳...")
            def task():
                d=get_all_events(); al=0
                for r in t5.get_children(): t5.delete(r)
                for ev in d:
                    bat=safe_int(ev.get("ras_eve_porc_bat_backup",100))
                    volt=safe_float(ev.get("ras_eve_voltagem",0))
                    gps=safe_int(ev.get("ras_eve_gps_status",0))
                    ign=safe_int(ev.get("ras_eve_ignicao",0))
                    tag="al" if bat<30 or volt==0 or not gps else "ok"
                    if tag=="al": al+=1
                    t5.insert("","end",values=(safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                        f"{bat}%",f"{volt:.1f}V","✓ OK" if gps else "✗ FALHA",
                        safe_int(ev.get("ras_eve_satelites",0)),"ON" if ign else "OFF",
                        safe_str(ev.get("ras_eve_data_gps"))),tags=(tag,))
                t5.tag_configure("al",background="#1a0808"); t5.tag_configure("ok",background=C["surface2"])
                lb5.config(text=f"Total: {len(d)}  |  ⚠ Alertas: {al}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c5,"⟳  ATUALIZAR",saude,C["warn"]).pack(side="left")
        mk_export_btn(c5,t5).pack(side="left",padx=6)
        self.after(300,saude)
        # Ranking
        f6=tk.Frame(nb,bg=C["bg"]); nb.add(f6,text="  Ranking Motoristas  ")
        c6=tk.Frame(f6,bg=C["bg"]); c6.pack(fill="x",padx=8,pady=6)
        lb6=lbl(c6,"",col=C["text_dim"]); lb6.pack(side="right")
        t6=mk_tree(f6,("Pos.","Motorista","Veículos","Vel.Máx","Vel.Méd","Score/100"),(50,180,80,100,100,90),"Rank",C["yellow"],14)
        def rank():
            lb6.config(text="⏳ Calculando...")
            def task():
                data=get_all_events(); mots={}
                for ev in data:
                    nm=safe_str(ev.get("ras_mot_nome"),"Desconhecido")
                    vel=abs(safe_int(ev.get("ras_eve_velocidade",0)))
                    pl=safe_str(ev.get("ras_vei_placa"))
                    if nm not in mots: mots[nm]={"v":set(),"vels":[]}
                    mots[nm]["v"].add(pl)
                    if vel>0: mots[nm]["vels"].append(vel)
                rk=[]
                for nm,d in mots.items():
                    vs=d["vels"]; vmx=max(vs) if vs else 0; vmd=sum(vs)/len(vs) if vs else 0
                    sc=max(0,100-max(0,vmx-80)//2-int(max(0,vmd-60)))
                    rk.append((nm,len(d["v"]),vmx,vmd,sc))
                rk.sort(key=lambda x:x[4],reverse=True)
                for r in t6.get_children(): t6.delete(r)
                m=["🥇","🥈","🥉"]
                for i,(nm,nv,vmx,vmd,sc) in enumerate(rk,1):
                    t6.insert("","end",values=(m[i-1] if i<=3 else f"#{i}",nm,nv,f"{vmx} km/h",f"{vmd:.1f} km/h",f"{sc}"),
                              tags=("t" if i<=3 else "n",))
                t6.tag_configure("t",background="#1a1a2e"); t6.tag_configure("n",background=C["surface2"])
                lb6.config(text=f"{len(rk)} motoristas")
            threading.Thread(target=task,daemon=True).start()
        btn(c6,"🏆 CALCULAR",rank,C["yellow"]).pack(side="left")
        mk_export_btn(c6,t6).pack(side="left",padx=6)
        self.after(400,rank)

# ─── ABA 8: COMANDOS & PAGINAÇÃO ─────────────────────────────────────────────
class TabComandos(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()

    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)
        # Enviar comando
        f=tk.Frame(nb,bg=C["bg"]); nb.add(f,text="  Enviar Comando  ")
        b=tk.Frame(f,bg=C["bg"]); b.pack(fill="both",expand=True,padx=20,pady=12)
        sec(b,"ENVIAR COMANDO DIRETO AO APARELHO")
        lbl(b,"ID do Aparelho (ras_ras_id_aparelho):",col=C["text_mid"]).pack(anchor="w",pady=(4,2))
        e_ap=ent(b); e_ap.pack(fill="x",ipady=5)
        lbl(b,"String do comando:",col=C["text_mid"]).pack(anchor="w",pady=(8,2))
        e_cmd=ent(b); e_cmd.pack(fill="x",ipady=5)
        lbl(b,"Descrição:",col=C["text_mid"]).pack(anchor="w",pady=(8,2))
        e_desc=ent(b); e_desc.pack(fill="x",ipady=5)
        _,res=txtbox(b,6); _.pack(fill="x",pady=(12,0))
        def enviar():
            if not e_ap.get().strip() or not e_cmd.get().strip():
                write(res,"⚠ Preencha aparelho e comando.",C["warn"]); return
            write(res,"⏳ Enviando...",C["accent"])
            def task():
                resp,code=api_post("/commands/direct",{"ras_ras_id_aparelho":e_ap.get().strip(),
                    "comando_string":e_cmd.get().strip(),"comando_descricao":e_desc.get().strip()})
                if resp.get("status") or code in (200,201):
                    d=extract_list(resp.get("data",resp))
                    ok(res,f"Enviado! ID comando: {d[0].get('ras_com_id','?') if d else '?'}")
                else: err(res,f"Falha {code}\n{json.dumps(resp,indent=2)}")
            threading.Thread(target=task,daemon=True).start()
        btn(b,"⚡  ENVIAR",enviar,C["danger"]).pack(pady=(10,0))
        mk_export_btn(b,res,is_text=True).pack(pady=(6,0))
        # Status comando
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  Status Comando  ")
        b2=tk.Frame(f2,bg=C["bg"]); b2.pack(fill="both",expand=True,padx=20,pady=12)
        sec(b2,"STATUS DO COMANDO ENVIADO")
        lbl(b2,"ID do Comando:",col=C["text_mid"]).pack(anchor="w",pady=(4,2))
        e2=ent(b2); e2.pack(fill="x",ipady=5)
        _,res2=txtbox(b2,12); _.pack(fill="both",expand=True,pady=(12,0))
        def status():
            cid=e2.get().strip()
            if not cid: return
            loading(res2)
            def task():
                d=extract_list(api_get(f"/commands/status/id/{cid}").get("data",[]))
                if not d: err(res2,"Não encontrado."); return
                lines=["="*44]
                for k,v in d[0].items(): lines.append(f"  {k:30s}: {safe_str(v)}")
                lines.append("="*44); write(res2,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()
        btn(b2,"CONSULTAR STATUS",status,C["accent"]).pack(pady=(10,0))
        mk_export_btn(b2,res2,is_text=True).pack(pady=(6,0))
        # Comandos disponíveis
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  Comandos Disponíveis  ")
        c3=tk.Frame(f3,bg=C["bg"]); c3.pack(fill="x",padx=8,pady=6)
        lbl(c3,"ID Produto:").pack(side="left")
        e3=ent(c3,w=12); e3.pack(side="left",padx=8,ipady=4)
        lb3=lbl(c3,"",col=C["text_dim"]); lb3.pack(side="right")
        t3=mk_tree(f3,("ID Cmd","Descrição"),(100,400),"CmdL",C["accent"],14)
        def cmd_list():
            pid=e3.get().strip()
            if not pid: return
            def task():
                d=extract_list(api_get(f"/commands/list/id/{pid}").get("data",[]))
                for r in t3.get_children(): t3.delete(r)
                for c4 in d: t3.insert("","end",values=(safe_str(c4.get("ras_stc_id")),safe_str(c4.get("ras_stc_descricao"))))
                lb3.config(text=f"{len(d)} comandos")
            threading.Thread(target=task,daemon=True).start()
        btn(c3,"LISTAR",cmd_list,C["accent"]).pack(side="left")
        mk_export_btn(c3,t3).pack(side="left",padx=6)
        # Paginação
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  Paginação de Eventos  ")
        c4=tk.Frame(f4,bg=C["bg"]); c4.pack(fill="x",padx=8,pady=6)
        lbl(c4,"Página:").pack(side="left")
        e4=ent(c4,w=5); e4.pack(side="left",padx=4,ipady=4); e4.insert(0,"1")
        lbl(c4,"  Por página:").pack(side="left")
        e4b=ent(c4,w=5); e4b.pack(side="left",padx=4,ipady=4); e4b.insert(0,"50")
        lb4=lbl(c4,"",col=C["text_dim"]); lb4.pack(side="right")
        t4=mk_tree(f4,("Placa","Motorista","Data GPS","Vel.","Ign.","GPS","Lat","Lon"),
                   (90,130,150,70,60,60,120,120),"Pag",C["accent2"],13)
        def buscar4():
            lb4.config(text="⏳...")
            def task():
                try: pg=int(e4.get()); pp=int(e4b.get())
                except: pg=1; pp=50
                resp=api_get("/events/pagination",{"page":pg,"per_page":pp})
                d=resp.get("data",{})
                evs=d.get("eventos",[]) if isinstance(d,dict) else extract_list(d)
                tpg=d.get("pages",["?"])[0] if isinstance(d,dict) and d.get("pages") else resp.get("pages","?")
                for r in t4.get_children(): t4.delete(r)
                for ev in evs:
                    t4.insert("","end",values=(safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_mot_nome")),
                        safe_str(ev.get("ras_eve_data_gps")),f"{safe_int(ev.get('ras_eve_velocidade',0))} km/h",
                        "ON" if safe_int(ev.get("ras_eve_ignicao")) else "OFF",
                        "✓" if safe_int(ev.get("ras_eve_gps_status")) else "✗",
                        safe_str(ev.get("ras_eve_latitude")),safe_str(ev.get("ras_eve_longitude"))))
                lb4.config(text=f"Pg {pg}/{tpg}  |  {len(evs)} eventos  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        def prev4():
            try: p=max(1,int(e4.get())-1)
            except: p=1
            e4.delete(0,"end"); e4.insert(0,str(p)); buscar4()
        def next4():
            try: p=int(e4.get())+1
            except: p=2
            e4.delete(0,"end"); e4.insert(0,str(p)); buscar4()
        c4b=tk.Frame(f4,bg=C["bg"]); c4b.pack(fill="x",padx=8,pady=(0,4))
        btn(c4b,"◀ ANTERIOR",prev4,C["surface3"],C["text"]).pack(side="left")
        btn(c4b,"  BUSCAR  ",buscar4,C["accent2"]).pack(side="left",padx=4)
        btn(c4b,"PRÓXIMA ▶",next4,C["surface3"],C["text"]).pack(side="left")
        mk_export_btn(c4b,t4).pack(side="left",padx=8)
        self.after(200,buscar4)
        # Auditoria
        f5=tk.Frame(nb,bg=C["bg"]); nb.add(f5,text="  Auditoria  ")
        c5=tk.Frame(f5,bg=C["bg"]); c5.pack(fill="x",padx=8,pady=6)
        lbl(c5,"Placa/nome:").pack(side="left")
        e5=ent(c5,w=16); e5.pack(side="left",padx=6,ipady=4)
        lbl(c5,"  Início:").pack(side="left")
        ei5=ent(c5,w=16); ei5.pack(side="left",padx=4,ipady=4)
        ei5.insert(0,(datetime.now()-timedelta(hours=4)).strftime("%d/%m/%Y %H:%M"))
        lbl(c5,"  Fim:").pack(side="left")
        ef5=ent(c5,w=16); ef5.pack(side="left",padx=4,ipady=4)
        ef5.insert(0,datetime.now().strftime("%d/%m/%Y %H:%M"))
        lb5=lbl(c5,"",col=C["text_dim"]); lb5.pack(side="right")
        cols5=("Seq","Data GPS","Vel.","Ign.","GPS","Satél.","Volt.","Lat","Lon")
        ws5=(50,150,80,60,60,60,80,120,120)
        t5=mk_tree(f5,cols5,ws5,"Aud",C["text_mid"],14)
        def audit():
            q=e5.get().strip()
            if not q: lb5.config(text="⚠ Informe a placa."); return
            lb5.config(text="⏳...")
            def task():
                entry=find_vehicle(q)
                if not entry: lb5.config(text="✖ Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei5.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef5.get().strip(),"%d/%m/%Y %H:%M")
                except: lb5.config(text="⚠ Datas inválidas."); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                for r in t5.get_children(): t5.delete(r)
                for i,ev in enumerate(evs,1):
                    t5.insert("","end",values=(i,safe_str(ev.get("ras_eve_data_gps")),
                        f"{safe_int(ev.get('ras_eve_velocidade',0))} km/h",
                        "ON" if safe_int(ev.get("ras_eve_ignicao")) else "OFF",
                        "✓" if safe_int(ev.get("ras_eve_gps_status")) else "✗",
                        safe_int(ev.get("ras_eve_satelites",0)),
                        f"{safe_float(ev.get('ras_eve_voltagem',0)):.1f}V",
                        safe_str(ev.get("ras_eve_latitude")),safe_str(ev.get("ras_eve_longitude"))))
                lb5.config(text=f"{entry.get('ras_vei_placa','—')}  |  {len(evs)} eventos  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()
        btn(c5,"🔍  BUSCAR",audit,C["accent2"]).pack(side="left",padx=8)
        mk_export_btn(c5,t5).pack(side="left",padx=4)

# ─── ABA 9: DIAGNÓSTICO ──────────────────────────────────────────────────────
class TabDiagnostico(tk.Frame):
    def __init__(self,master):
        super().__init__(master,bg=C["bg"]); self._build()
        
    def _build(self):
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=6,pady=6)

        # ── GPS Travado ──────────────────────────────────────────────────────
        f1=tk.Frame(nb,bg=C["bg"]); nb.add(f1,text="  🛰 GPS Travado  ")
        c1=tk.Frame(f1,bg=C["bg"]); c1.pack(fill="x",padx=8,pady=6)

        lbl(c1,"Tolerância defasagem (min):",9,col=C["text_mid"]).pack(side="left")
        e_tol=ent(c1,w=5); e_tol.pack(side="left",padx=6,ipady=4); e_tol.insert(0,"5")
        lbl(c1,"  Tolerância sem mover (m):",9,col=C["text_mid"]).pack(side="left")
        e_mov=ent(c1,w=6); e_mov.pack(side="left",padx=6,ipady=4); e_mov.insert(0,"50")
        lb1=lbl(c1,"",col=C["text_dim"]); lb1.pack(side="right")

        cols1=("Placa","Veículo","Motorista","Data GPS","Data Envio","Defasagem","Vel.","Situação")
        ws1=(90,130,130,150,150,110,70,140)
        t1=mk_tree(f1,cols1,ws1,"GpsT",C["warn"],14)

        info1=tk.Frame(f1,bg=C["surface3"]); info1.pack(fill="x",padx=8,pady=(0,4))
        lbl(info1,"ℹ  GPS Travado: diferença entre Data GPS e Data Envio > tolerância  |  e/ou  veículo em movimento sem mudança de posição GPS.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")

        def gps_travado():
            try: tol=int(e_tol.get()); mov_m=float(e_mov.get())
            except: tol=5; mov_m=50
            lb1.config(text="⏳ Verificando...")
            def task():
                data=get_all_events()
                for r in t1.get_children(): t1.delete(r)
                ac=0; now=datetime.now()
                for ev in data:
                    placa=safe_str(ev.get("ras_vei_placa"))
                    vel=safe_int(ev.get("ras_eve_velocidade",0))
                    d_gps=safe_str(ev.get("ras_eve_data_gps"))
                    d_env=safe_str(ev.get("ras_eve_data_enviado"))
                    dt_gps=parse_dt(d_gps)
                    dt_env=parse_dt(d_env)
                    problemas=[]
                    defasagem="—"
                    # Defasagem de tempo
                    if dt_gps and dt_env:
                        diff=abs((dt_env-dt_gps).total_seconds())/60
                        defasagem=f"{diff:.1f} min"
                        if diff>=tol:
                            problemas.append(f"Defasagem {diff:.0f}min")
                    elif dt_gps:
                        diff=(now-dt_gps).total_seconds()/60
                        defasagem=f"{diff:.1f} min (sem envio)"
                        if diff>=tol:
                            problemas.append(f"Sem envio {diff:.0f}min")
                    # Veículo andando com velocidade mas GPS não muda
                    lat=safe_float(ev.get("ras_eve_latitude"),None)
                    lon=safe_float(ev.get("ras_eve_longitude"),None)
                    if vel>5 and lat is not None:
                        # Marca como suspeito — análise completa requereria histórico
                        problemas.append(f"Vel={vel}km/h")
                    if problemas:
                        ac+=1
                        sit=" | ".join(problemas)
                        t1.insert("","end",values=(placa,safe_str(ev.get("ras_vei_veiculo")),
                            safe_str(ev.get("ras_mot_nome")),d_gps,d_env,defasagem,
                            f"{vel} km/h",sit),tags=("al",))
                t1.tag_configure("al",background="#1a1500")
                lb1.config(text=f"Total: {len(data)}  |  ⚠ Suspeitos: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c1,"🔍 VERIFICAR",gps_travado,C["warn"]).pack(side="left",padx=8)
        mk_export_btn(c1,t1).pack(side="left",padx=4)
        self.after(300,gps_travado)

        # ── GPS Travado por Período (análise de rota) ────────────────────────
        f1b=tk.Frame(nb,bg=C["bg"]); nb.add(f1b,text="  🛰 GPS Travado (Período)  ")
        c1b=tk.Frame(f1b,bg=C["bg"]); c1b.pack(fill="x",padx=8,pady=6)
        lbl(c1b,"Veículo:").pack(side="left")
        e1b_v=ent(c1b,w=18); e1b_v.pack(side="left",padx=6,ipady=4)
        lbl(c1b,"  Tol.GPS(min):").pack(side="left")
        e1b_t=ent(c1b,w=5); e1b_t.pack(side="left",padx=4,ipady=4); e1b_t.insert(0,"5")
        lbl(c1b,"  Dist.mín(m):").pack(side="left")
        e1b_d=ent(c1b,w=6); e1b_d.pack(side="left",padx=4,ipady=4); e1b_d.insert(0,"10")
        lb1b=lbl(c1b,"",col=C["text_dim"]); lb1b.pack(side="right")

        ei1b,ef1b=interval_row(c1b.master if False else tk.Frame(f1b,bg=C["bg"]))
        ei1b.master.pack(fill="x",padx=8,pady=2)

        cols1b=("Seq","Data GPS","Data Envio","Defasagem(min)","Vel.","Lat","Lon","Status")
        ws1b=(50,150,150,120,70,120,120,160)
        t1b=mk_tree(f1b,cols1b,ws1b,"GpsTp",C["warn"],14)

        def gps_travado_periodo():
            q=e1b_v.get().strip()
            if not q: lb1b.config(text="⚠ Informe o veículo"); return
            try:
                tol=int(e1b_t.get()); dist_m=float(e1b_d.get())
                ini=datetime.strptime(ei1b.get().strip(),"%d/%m/%Y %H:%M")
                fim=datetime.strptime(ef1b.get().strip(),"%d/%m/%Y %H:%M")
            except: lb1b.config(text="⚠ Parâmetros inválidos"); return
            lb1b.config(text="⏳...")
            def task():
                entry=find_vehicle(q)
                if not entry: lb1b.config(text="✖ Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                for r in t1b.get_children(): t1b.delete(r)
                ac=0; prev_lat=None; prev_lon=None; prev_gps_dt=None
                for i,ev in enumerate(evs,1):
                    vel=safe_int(ev.get("ras_eve_velocidade",0))
                    lat=safe_float(ev.get("ras_eve_latitude"),None)
                    lon=safe_float(ev.get("ras_eve_longitude"),None)
                    d_gps=safe_str(ev.get("ras_eve_data_gps"))
                    d_env=safe_str(ev.get("ras_eve_data_enviado"))
                    dt_gps=parse_dt(d_gps)
                    dt_env=parse_dt(d_env)
                    defasagem="—"; problemas=[]
                    if dt_gps and dt_env:
                        diff=abs((dt_env-dt_gps).total_seconds())/60
                        defasagem=f"{diff:.1f}"
                        if diff>=tol: problemas.append(f"Defasagem {diff:.0f}min")
                    # GPS congelado: posição não muda mas velocidade > 0
                    if prev_lat is not None and lat is not None and vel>5:
                        dist_km=haversine(prev_lat,prev_lon,lat,lon)
                        if dist_km*1000<dist_m:
                            problemas.append(f"Pos.congelada({dist_km*1000:.0f}m)")
                    # GPS congelado: mesmo timestamp GPS em eventos seguidos
                    if prev_gps_dt and dt_gps and prev_gps_dt==dt_gps and vel>0:
                        problemas.append("Timestamp repetido")
                    status="⚠ "+(" | ".join(problemas)) if problemas else "✓ OK"
                    if problemas: ac+=1
                    t1b.insert("","end",values=(i,d_gps,d_env,defasagem,f"{vel} km/h",
                        f"{lat:.5f}" if lat else "—",f"{lon:.5f}" if lon else "—",status),
                        tags=("al" if problemas else "ok",))
                    prev_lat=lat; prev_lon=lon; prev_gps_dt=dt_gps
                t1b.tag_configure("al",background="#1a1500")
                t1b.tag_configure("ok",background=C["surface2"])
                lb1b.config(text=f"{entry.get('ras_vei_placa','—')}  |  {len(evs)} eventos  |  ⚠ {ac} problemas  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c1b,"🔍 ANALISAR",gps_travado_periodo,C["warn"]).pack(side="left",padx=8)
        mk_export_btn(c1b,t1b).pack(side="left",padx=4)

        # ── Ignição Defeituosa ───────────────────────────────────────────────
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  🔑 Ignição Defeituosa  ")
        c2=tk.Frame(f2,bg=C["bg"]); c2.pack(fill="x",padx=8,pady=6)
        lbl(c2,"Vel. mín para detectar (km/h):",9,col=C["text_mid"]).pack(side="left")
        e2_v=ent(c2,w=5); e2_v.pack(side="left",padx=6,ipady=4); e2_v.insert(0,"5")
        lb2=lbl(c2,"",col=C["text_dim"]); lb2.pack(side="right")

        cols2=("Placa","Veículo","Motorista","Ignição","Velocidade","GPS","Data GPS","Cliente")
        ws2=(90,130,130,80,100,60,150,130)
        t2=mk_tree(f2,cols2,ws2,"IgnD",C["danger"],14)

        info2=tk.Frame(f2,bg=C["surface3"]); info2.pack(fill="x",padx=8,pady=(0,4))
        lbl(info2,"ℹ  Ignição Defeituosa: ignição reportada como OFF mas velocidade acima do limiar configurado.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")

        def ignicao_defeituosa():
            try: vmin=int(e2_v.get())
            except: vmin=5
            lb2.config(text="⏳ Verificando...")
            def task():
                data=get_all_events()
                for r in t2.get_children(): t2.delete(r)
                ac=0
                for ev in data:
                    ign=safe_int(ev.get("ras_eve_ignicao",0))
                    vel=safe_int(ev.get("ras_eve_velocidade",0))
                    if ign==0 and vel>=vmin:
                        ac+=1
                        t2.insert("","end",values=(
                            safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                            safe_str(ev.get("ras_mot_nome")),"⚫ OFF",f"🚨 {vel} km/h",
                            "✓" if safe_int(ev.get("ras_eve_gps_status")) else "✗",
                            safe_str(ev.get("ras_eve_data_gps")),safe_str(ev.get("ras_cli_desc"))),
                            tags=("al",))
                t2.tag_configure("al",background="#1a0808")
                lb2.config(text=f"Total: {len(data)}  |  🚨 Defeituosas: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c2,"🔍 VERIFICAR",ignicao_defeituosa,C["danger"]).pack(side="left",padx=8)
        mk_export_btn(c2,t2).pack(side="left",padx=4)
        self.after(400,ignicao_defeituosa)

        # ── Sensores com Problema ────────────────────────────────────────────
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  🌡 Sensores Problema  ")
        c3=tk.Frame(f3,bg=C["bg"]); c3.pack(fill="x",padx=8,pady=6)
        lbl(c3,"Temp. mín (°C):",9,col=C["text_mid"]).pack(side="left")
        e3_min=ent(c3,w=7); e3_min.pack(side="left",padx=4,ipady=4); e3_min.insert(0,"-40")
        lbl(c3,"  Temp. máx (°C):",9,col=C["text_mid"]).pack(side="left")
        e3_max=ent(c3,w=7); e3_max.pack(side="left",padx=4,ipady=4); e3_max.insert(0,"85")
        lbl(c3,"  Bat. mín (%):").pack(side="left")
        e3_bat=ent(c3,w=5); e3_bat.pack(side="left",padx=4,ipady=4); e3_bat.insert(0,"20")
        lbl(c3,"  Volt. mín (V):").pack(side="left")
        e3_volt=ent(c3,w=5); e3_volt.pack(side="left",padx=4,ipady=4); e3_volt.insert(0,"10.0")
        lb3=lbl(c3,"",col=C["text_dim"]); lb3.pack(side="right")

        cols3=("Placa","Veículo","Problema","Valor","Sensor/Campo","Data GPS","Cliente")
        ws3=(90,130,160,100,130,150,130)
        t3=mk_tree(f3,cols3,ws3,"SenP",C["orange"],14)

        info3=tk.Frame(f3,bg=C["surface3"]); info3.pack(fill="x",padx=8,pady=(0,4))
        lbl(info3,"ℹ  Detecta temperaturas fora da faixa configurada, bateria baixa e voltagem abaixo do mínimo.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")

        def sensores_problema():
            try:
                tmin=float(e3_min.get()); tmax=float(e3_max.get())
                bat_min=int(e3_bat.get()); volt_min=float(e3_volt.get())
            except: tmin=-40; tmax=85; bat_min=20; volt_min=10.0
            lb3.config(text="⏳ Verificando...")
            def task():
                data=get_all_events()
                for r in t3.get_children(): t3.delete(r)
                ac=0
                for ev in data:
                    placa=safe_str(ev.get("ras_vei_placa"))
                    veiculo=safe_str(ev.get("ras_vei_veiculo"))
                    cliente=safe_str(ev.get("ras_cli_desc"))
                    data_gps=safe_str(ev.get("ras_eve_data_gps"))
                    problemas=[]
                    # Bateria baixa
                    bat=safe_int(ev.get("ras_eve_porc_bat_backup",100))
                    if bat<bat_min:
                        problemas.append((placa,veiculo,f"Bateria baixa",f"{bat}%","bat_backup",data_gps,cliente))
                    # Voltagem baixa
                    volt=safe_float(ev.get("ras_eve_voltagem",0))
                    if 0<volt<volt_min:
                        problemas.append((placa,veiculo,f"Voltagem baixa",f"{volt:.1f}V","voltagem",data_gps,cliente))
                    # Temperatura
                    sensors=ev.get("sensor_temperatura") or ev.get("ras_eve_temperatura") or {}
                    if isinstance(sensors,str):
                        try: sensors=json.loads(sensors)
                        except: sensors={}
                    if isinstance(sensors,dict):
                        for k,v in sensors.items():
                            fv=safe_float(v,None)
                            if fv is not None and (fv<tmin or fv>tmax):
                                label="🔴 Temp.Alta" if fv>tmax else "🔵 Temp.Baixa"
                                problemas.append((placa,veiculo,label,f"{fv:.1f}°C",k,data_gps,cliente))
                    elif isinstance(sensors,list):
                        for i,v in enumerate(sensors):
                            fv=safe_float(v,None)
                            if fv is not None and (fv<tmin or fv>tmax):
                                label="🔴 Temp.Alta" if fv>tmax else "🔵 Temp.Baixa"
                                problemas.append((placa,veiculo,label,f"{fv:.1f}°C",f"sensor_{i+1}",data_gps,cliente))
                    for p in problemas:
                        ac+=1; t3.insert("","end",values=p,tags=("al",))
                t3.tag_configure("al",background="#1a0a00")
                lb3.config(text=f"Total: {len(data)}  |  ⚠ Problemas: {ac}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c3,"🔍 VERIFICAR",sensores_problema,C["orange"]).pack(side="left",padx=8)
        mk_export_btn(c3,t3).pack(side="left",padx=4)
        self.after(500,sensores_problema)

        # ── Veículos Desatualizados ──────────────────────────────────────────
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  ⏰ Desatualizados  ")

        # Controles superiores
        c4=tk.Frame(f4,bg=C["bg"]); c4.pack(fill="x",padx=8,pady=6)
        lbl(c4,"Tolerância:",9,col=C["text_mid"]).pack(side="left")
        e4_val=ent(c4,w=5); e4_val.pack(side="left",padx=4,ipady=4); e4_val.insert(0,"1")
        e4_unit=ttk.Combobox(c4,values=["minutos","horas","dias"],width=8,state="readonly",
                              font=("Helvetica Neue",9))
        e4_unit.pack(side="left",padx=4,ipady=4); e4_unit.set("horas")
        lbl(c4,"  (vs. horário atual):",8,col=C["text_dim"]).pack(side="left")

        # Filtro rápido por status
        lbl(c4,"  Filtrar:",8,col=C["text_dim"]).pack(side="left",padx=(12,2))
        e4_filtro=ttk.Combobox(c4,values=["Todos","Ign. ON","Ign. OFF","GPS Falha","GPS OK"],
                                width=10,state="readonly",font=("Helvetica Neue",9))
        e4_filtro.pack(side="left",padx=2); e4_filtro.set("Todos")

        lb4=lbl(c4,"",col=C["text_dim"]); lb4.pack(side="right")

        # Linha de resumo visual
        resumo_f=tk.Frame(f4,bg=C["surface"]); resumo_f.pack(fill="x",padx=8,pady=(0,4))
        def _rcard(p,titulo,var,col):
            f=tk.Frame(p,bg=C["surface"]); f.pack(side="left",padx=16,pady=5)
            tk.Label(f,text=titulo,bg=C["surface"],fg=C["text_dim"],font=("Helvetica Neue",7,"bold")).pack()
            lb=tk.Label(f,text=var,bg=C["surface"],fg=col,font=("Helvetica Neue",13,"bold")); lb.pack()
            return lb
        r4_total  = _rcard(resumo_f,"ANALISADOS","—",C["blue"])
        r4_desatual= _rcard(resumo_f,"DESATUALIZADOS","—",C["danger"])
        r4_ign_on  = _rcard(resumo_f,"IGN. ON","—",C["green"])
        r4_ign_off = _rcard(resumo_f,"IGN. OFF","—",C["text_mid"])
        r4_no_gps  = _rcard(resumo_f,"SEM GPS","—",C["warn"])
        r4_maior   = _rcard(resumo_f,"MAIOR ATRASO","—",C["orange"])

        # Colunas expandidas
        cols4=(
            "Placa","Veículo","Motorista","Cliente",
            "Última GPS","Última Envio","Atraso","Ignição","GPS Status",
            "Chip","Nº Equipamento","Modelo Equip.","Linha","Operadora"
        )
        ws4=(90,130,130,130,150,150,110,80,90,120,120,110,100,100)

        # Treeview com estilo próprio
        _sname4="Desatual"
        _st4=ttk.Style(); _st4.theme_use("clam")
        _st4.configure(f"{_sname4}.Treeview",background=C["surface2"],foreground=C["text"],
                       rowheight=26,fieldbackground=C["surface2"],borderwidth=0,font=("Consolas",9))
        _st4.configure(f"{_sname4}.Treeview.Heading",background=C["surface3"],foreground=C["purple"],
                       font=("Helvetica Neue",9,"bold"),borderwidth=0,relief="flat")
        _st4.map(f"{_sname4}.Treeview",background=[("selected",C["accent2"])])

        fr4=tk.Frame(f4,bg=C["bg"]); fr4.pack(fill="both",expand=True,padx=8)
        t4=ttk.Treeview(fr4,columns=cols4,show="headings",style=f"{_sname4}.Treeview",height=14)
        for _c,_w in zip(cols4,ws4):
            t4.heading(_c,text=_c,anchor="w")
            t4.column(_c,width=_w,anchor="w",stretch=True)
        vs4=ttk.Scrollbar(fr4,orient="vertical",command=t4.yview)
        hs4=ttk.Scrollbar(fr4,orient="horizontal",command=t4.xview)
        t4.configure(yscrollcommand=vs4.set,xscrollcommand=hs4.set)
        vs4.pack(side="right",fill="y"); hs4.pack(side="bottom",fill="x"); t4.pack(fill="both",expand=True)

        t4.tag_configure("al_crit",background="#1a0505")   # crítico: atraso > 4h
        t4.tag_configure("al_alto",background="#1a0d00")   # alto: 1h-4h
        t4.tag_configure("al_med", background="#1a1500")   # médio: <1h mas acima tolerância
        attach_copy(t4)

        # Info box
        info4=tk.Frame(f4,bg=C["surface3"]); info4.pack(fill="x",padx=8,pady=(0,4))
        lbl(info4,
            "ℹ  Vermelho escuro = atraso crítico (>4h) · Laranja = alto (1h–4h) · Amarelo = médio (<1h). "
            "Chip, Linha e Operadora vêm do cadastro de rastreadores. Ctrl+C copia seleção.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")

        # Cache para re-filtrar sem nova chamada à API
        _d4_cache={"rows":[]}

        def _render4(rows):
            for r in t4.get_children(): t4.delete(r)
            filtro=e4_filtro.get()
            on=off=no_gps=0; maior_s=0
            shown=[]
            for vals,tag,diff_s in rows:
                ign_txt=vals[7]; gps_txt=vals[8]
                if filtro=="Ign. ON" and "ON" not in ign_txt: continue
                if filtro=="Ign. OFF" and "OFF" not in ign_txt: continue
                if filtro=="GPS Falha" and "FALHA" not in gps_txt: continue
                if filtro=="GPS OK" and "OK" not in gps_txt: continue
                shown.append((vals,tag,diff_s))
                if "ON" in ign_txt: on+=1
                else: off+=1
                if "FALHA" in gps_txt: no_gps+=1
                maior_s=max(maior_s,diff_s)

            for vals,tag,_ in shown:
                t4.insert("","end",values=vals,tags=(tag,))

            r4_desatual.config(text=str(len(shown)))
            r4_ign_on.config(text=str(on))
            r4_ign_off.config(text=str(off))
            r4_no_gps.config(text=str(no_gps))
            if maior_s<3600: r4_maior.config(text=f"{maior_s/60:.0f} min")
            elif maior_s<86400: r4_maior.config(text=f"{maior_s/3600:.1f} h")
            else: r4_maior.config(text=f"{maior_s/86400:.1f} dias")

        e4_filtro.bind("<<ComboboxSelected>>",lambda e:_render4(_d4_cache["rows"]))

        def desatualizados():
            try:
                val=float(e4_val.get())
                unit=e4_unit.get()
                if unit=="minutos": tol_s=val*60
                elif unit=="horas": tol_s=val*3600
                else: tol_s=val*86400
            except: tol_s=3600
            lb4.config(text="⏳ Verificando...")

            def task():
                from datetime import timezone,timedelta as _td
                TZ_BR=timezone(_td(hours=-3))
                now=datetime.now(TZ_BR).replace(tzinfo=None)

                events=get_all_events()
                r4_total.config(text=str(len(events)))

                # Indexa rastreadores por veiculo_id e por aparelho
                try:
                    trackers_raw=get_trackers_all()
                    tracker_by_veic={safe_str(tr.get("ras_vei_id","")): tr
                                     for tr in trackers_raw if safe_str(tr.get("ras_vei_id",""))!="—"}
                    tracker_by_ap={safe_str(tr.get("ras_ras_id_aparelho","")): tr
                                   for tr in trackers_raw}
                except:
                    tracker_by_veic={}; tracker_by_ap={}

                rows=[]; ac=0
                for ev in events:
                    d_gps=safe_str(ev.get("ras_eve_data_gps"))
                    dt_gps=parse_dt(d_gps)
                    if dt_gps is None: continue
                    diff_s=(now-dt_gps).total_seconds()
                    if diff_s<0: diff_s=0
                    if diff_s<tol_s: continue
                    ac+=1

                    # Formata atraso e define tag de severidade
                    if diff_s<3600:
                        atraso=f"{diff_s/60:.0f} min"; tag="al_med"
                    elif diff_s<14400:
                        atraso=f"{diff_s/3600:.1f} h"; tag="al_alto"
                    else:
                        atraso=f"{diff_s/3600:.1f} h" if diff_s<86400 else f"{diff_s/86400:.1f} dias"
                        tag="al_crit"

                    ign=safe_int(ev.get("ras_eve_ignicao",0))
                    gps=safe_int(ev.get("ras_eve_gps_status",0))
                    d_env=safe_str(ev.get("ras_eve_data_enviado"))

                    # Dados do rastreador
                    vid_str=safe_str(ev.get("ras_vei_id",""))
                    ap_id=safe_str(ev.get("ras_ras_id_aparelho",""))
                    tr=tracker_by_veic.get(vid_str) or tracker_by_ap.get(ap_id) or {}
                    chip     =safe_str(tr.get("ras_ras_chip"))
                    num_equip=safe_str(tr.get("ras_ras_id_aparelho") or tr.get("ras_ras_id"))
                    modelo   =safe_str(tr.get("ras_ras_prd_id") or tr.get("ras_ras_modelo"))
                    linha    =safe_str(tr.get("ras_ras_linha"))
                    operadora=safe_str(tr.get("ras_ras_operadora") or tr.get("ras_ras_chip_operadora"))

                    rows.append((
                        (safe_str(ev.get("ras_vei_placa")),
                         safe_str(ev.get("ras_vei_veiculo")),
                         safe_str(ev.get("ras_mot_nome")),
                         safe_str(ev.get("ras_cli_desc")),
                         d_gps, d_env, atraso,
                         "🟢 ON" if ign else "⚫ OFF",
                         "✓ OK" if gps else "✗ FALHA",
                         chip, num_equip, modelo, linha, operadora),
                        tag, diff_s
                    ))

                # Ordena por maior atraso primeiro
                rows.sort(key=lambda x: x[2], reverse=True)
                _d4_cache["rows"]=rows
                _render4(rows)
                lb4.config(text=f"Total: {len(events)}  |  ⏰ Desatualizados: {ac}  |  {now_str()}")

            threading.Thread(target=task,daemon=True).start()

        btn(c4,"🔍 VERIFICAR",desatualizados,C["purple"]).pack(side="left",padx=8)
        mk_export_btn(c4,t4).pack(side="left",padx=4)
        auto_refresh_register("desatualizados",desatualizados)
        self.after(600,desatualizados)

# ═══════════════════════════════════════════════════════════════════════════════
#  JANELA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
#  SISTEMA DE FILTROS UNIVERSAIS PARA TREEVIEW
# ═══════════════════════════════════════════════════════════════════════════════

class FilterableTree:
    """
    Wrapper que adiciona filtro de texto, ordenação por coluna (asc/desc),
    cópia Ctrl+C e menu de contexto a qualquer Treeview.
    """
    def __init__(self, parent, cols, ws, sname="B", hcol=None, h=12):
        self._all_data = []          # lista de (values, tags) originais
        self._sort_col = None
        self._sort_asc = True

        # Container principal
        self.frame = tk.Frame(parent, bg=C["bg"])
        self.frame.pack(fill="both", expand=True)

        # Barra de filtro
        fb = tk.Frame(self.frame, bg=C["surface3"], pady=3)
        fb.pack(fill="x", padx=0, pady=(0,1))

        tk.Label(fb, text="🔍", bg=C["surface3"], fg=C["accent"],
                 font=("Helvetica Neue", 9)).pack(side="left", padx=(6,2))

        self._filter_var = tk.StringVar()
        self._filter_var.trace("w", self._on_filter_change)
        fe = tk.Entry(fb, textvariable=self._filter_var, bg=C["surface2"], fg=C["text"],
                      insertbackground=C["accent"], relief="flat", font=("Consolas",9), width=28,
                      highlightthickness=1, highlightbackground=C["border"],
                      highlightcolor=C["accent"])
        fe.pack(side="left", padx=4, ipady=3)

        tk.Label(fb, text="Coluna:", bg=C["surface3"], fg=C["text_dim"],
                 font=("Helvetica Neue",8)).pack(side="left", padx=(8,2))

        self._col_var = tk.StringVar(value="Todas")
        col_opts = ["Todas"] + list(cols)
        self._col_cb = ttk.Combobox(fb, textvariable=self._col_var, values=col_opts,
                                     state="readonly", width=14,
                                     font=("Helvetica Neue",8))
        self._col_cb.pack(side="left", padx=2)
        self._col_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        tk.Label(fb, text="  Ordenar:", bg=C["surface3"], fg=C["text_dim"],
                 font=("Helvetica Neue",8)).pack(side="left", padx=(8,2))
        self._sort_var = tk.StringVar(value="—")
        sort_opts = ["—"] + list(cols)
        self._sort_cb = ttk.Combobox(fb, textvariable=self._sort_var, values=sort_opts,
                                      state="readonly", width=14,
                                      font=("Helvetica Neue",8))
        self._sort_cb.pack(side="left", padx=2)
        self._sort_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_sort())

        self._asc_btn = tk.Label(fb, text="↑ ASC", bg=C["surface2"], fg=C["accent"],
                                  font=("Helvetica Neue",8,"bold"), padx=6, pady=3,
                                  cursor="hand2")
        self._asc_btn.pack(side="left", padx=2)
        self._asc_btn.bind("<Button-1>", lambda e: self._toggle_dir())

        self._count_lbl = tk.Label(fb, text="", bg=C["surface3"], fg=C["text_dim"],
                                    font=("Helvetica Neue",8))
        self._count_lbl.pack(side="right", padx=8)

        btn_clear = tk.Label(fb, text="✕ LIMPAR", bg=C["surface2"], fg=C["text_mid"],
                              font=("Helvetica Neue",8), padx=6, pady=3, cursor="hand2")
        btn_clear.pack(side="right", padx=2)
        btn_clear.bind("<Button-1>", lambda e: self._clear_filter())

        # Treeview real
        style = apply_tree_style(sname, hcol)
        inner = tk.Frame(self.frame, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(inner, columns=cols, show="headings", style=style, height=h)
        for c, w in zip(cols, ws):
            self.tree.heading(c, text=c, anchor="w",
                              command=lambda _c=c: self._header_click(_c))
            self.tree.column(c, width=w, anchor="w", stretch=True)

        vs = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(inner, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # Binds de cópia e menu
        self.tree.bind("<Control-c>", self._copy_selection)
        self.tree.bind("<Control-C>", self._copy_selection)
        self.tree.bind("<Button-3>", self._context_menu)

        # Menu de contexto
        self._menu = tk.Menu(self.tree, tearoff=0, bg=C["surface3"], fg=C["text"],
                              activebackground=C["accent2"], activeforeground=C["text"],
                              font=("Helvetica Neue",9))
        self._menu.add_command(label="📋  Copiar linha", command=self._copy_row)
        self._menu.add_command(label="📋  Copiar célula", command=self._copy_cell_from_menu)
        self._menu.add_command(label="📋  Copiar tudo (CSV)", command=self._copy_all_csv)
        self._menu.add_separator()
        self._menu.add_command(label="📥  Exportar CSV", command=lambda: export_tree(self.tree))
        self._menu.add_separator()
        self._menu.add_command(label="🔃  Limpar filtros", command=self._clear_filter)

        self._menu_click_pos = None  # para saber qual célula foi clicada

        self._cols = cols

    def _header_click(self, col):
        """Clique no cabeçalho ordena por aquela coluna."""
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._sort_var.set(col)
        self._asc_btn.config(text="↑ ASC" if self._sort_asc else "↓ DESC")
        self._apply_filter()

    def _toggle_dir(self):
        self._sort_asc = not self._sort_asc
        self._asc_btn.config(text="↑ ASC" if self._sort_asc else "↓ DESC")
        self._apply_filter()

    def _on_filter_change(self, *_):
        self._apply_filter()

    def _apply_sort(self):
        col = self._sort_var.get()
        if col == "—":
            self._sort_col = None
        else:
            self._sort_col = col
        self._apply_filter()

    def _clear_filter(self):
        self._filter_var.set("")
        self._sort_var.set("—")
        self._col_var.set("Todas")
        self._sort_col = None
        self._sort_asc = True
        self._asc_btn.config(text="↑ ASC")
        self._apply_filter()

    def _apply_filter(self):
        q = self._filter_var.get().lower().strip()
        filter_col = self._col_var.get()
        cols = self._cols

        # Filtra
        if not q:
            filtered = list(self._all_data)
        else:
            filtered = []
            for (vals, tags) in self._all_data:
                if filter_col == "Todas":
                    haystack = " ".join(str(v).lower() for v in vals)
                else:
                    try:
                        idx = list(cols).index(filter_col)
                        haystack = str(vals[idx]).lower()
                    except:
                        haystack = " ".join(str(v).lower() for v in vals)
                if q in haystack:
                    filtered.append((vals, tags))

        # Ordena
        if self._sort_col and self._sort_col in cols:
            idx = list(cols).index(self._sort_col)
            def sort_key(x):
                val = x[0][idx] if idx < len(x[0]) else ""
                s = str(val).replace("—","").replace("km/h","").replace("%","").replace("V","").strip()
                try: return (0, float(s))
                except: return (1, s.lower())
            filtered.sort(key=sort_key, reverse=not self._sort_asc)

        # Renderiza
        for r in self.tree.get_children():
            self.tree.delete(r)
        for (vals, tags) in filtered:
            self.tree.insert("", "end", values=vals, tags=tags)

        self._count_lbl.config(text=f"{len(filtered)}/{len(self._all_data)}")

    def load(self, data_list):
        """data_list: list of (values_tuple, tags_tuple_or_str)"""
        self._all_data = []
        for item in data_list:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], (tuple,list,str)):
                vals, tags = item
            else:
                vals, tags = item, ()
            if isinstance(tags, str): tags = (tags,)
            self._all_data.append((vals, tuple(tags)))
        self._apply_filter()

    def tag_configure(self, tag, **kw):
        self.tree.tag_configure(tag, **kw)

    # ── Clipboard ──────────────────────────────────────────────────────────
    def _copy_selection(self, event=None):
        self._copy_row()

    def _copy_row(self):
        sel = self.tree.selection()
        if not sel:
            return
        lines = []
        for item in sel:
            vals = self.tree.item(item)["values"]
            lines.append("\t".join(str(v) for v in vals))
        text = "\n".join(lines)
        self.tree.clipboard_clear()
        self.tree.clipboard_append(text)

    def _copy_cell_from_menu(self):
        """Copia o valor da célula mais próxima do último clique."""
        sel = self.tree.selection()
        if not sel or self._menu_click_pos is None:
            return
        x, y = self._menu_click_pos
        col_id = self.tree.identify_column(x)
        item = self.tree.identify_row(y)
        if not col_id or not item:
            self._copy_row(); return
        col_idx = int(col_id.replace("#","")) - 1
        vals = self.tree.item(item)["values"]
        if 0 <= col_idx < len(vals):
            self.tree.clipboard_clear()
            self.tree.clipboard_append(str(vals[col_idx]))

    def _copy_all_csv(self):
        cols = [self.tree.heading(c)["text"] for c in self.tree["columns"]]
        rows = [self.tree.item(r)["values"] for r in self.tree.get_children()]
        lines = [";".join(str(c) for c in cols)]
        for row in rows:
            lines.append(";".join(str(v) for v in row))
        text = "\n".join(lines)
        self.tree.clipboard_clear()
        self.tree.clipboard_append(text)

    def _context_menu(self, event):
        self._menu_click_pos = (event.x, event.y)
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def get_children(self): return self.tree.get_children()
    def delete(self, *a): return self.tree.delete(*a)
    def insert(self, *a, **kw): return self.tree.insert(*a, **kw)
    def item(self, *a, **kw): return self.tree.item(*a, **kw)
    def heading(self, *a, **kw): return self.tree.heading(*a, **kw)
    def __getitem__(self, k): return self.tree[k]


def mk_ftree(parent, cols, ws, sname="B", hcol=None, h=12):
    """Cria um FilterableTree e retorna o objeto (use .tree para o widget raw)."""
    ft = FilterableTree(parent, cols, ws, sname, hcol, h)
    return ft


def attach_copy(tree_widget):
    """Adiciona Ctrl+C e menu de contexto a um Treeview existente (mk_tree legado)."""
    menu = tk.Menu(tree_widget, tearoff=0, bg=C["surface3"], fg=C["text"],
                   activebackground=C["accent2"], activeforeground=C["text"],
                   font=("Helvetica Neue",9))

    def copy_row():
        sel = tree_widget.selection()
        if not sel: return
        lines = ["\t".join(str(v) for v in tree_widget.item(i)["values"]) for i in sel]
        tree_widget.clipboard_clear(); tree_widget.clipboard_append("\n".join(lines))

    def copy_all():
        cols = [tree_widget.heading(c)["text"] for c in tree_widget["columns"]]
        rows = [tree_widget.item(r)["values"] for r in tree_widget.get_children()]
        lines = [";".join(str(c) for c in cols)]
        for row in rows: lines.append(";".join(str(v) for v in row))
        tree_widget.clipboard_clear(); tree_widget.clipboard_append("\n".join(lines))

    menu.add_command(label="📋  Copiar linha selecionada", command=copy_row)
    menu.add_command(label="📋  Copiar tudo (CSV)", command=copy_all)
    menu.add_separator()
    menu.add_command(label="📥  Exportar CSV", command=lambda: export_tree(tree_widget))

    def ctx(e):
        item = tree_widget.identify_row(e.y)
        if item: tree_widget.selection_set(item)
        try: menu.tk_popup(e.x_root, e.y_root)
        finally: menu.grab_release()

    tree_widget.bind("<Control-c>", lambda e: copy_row())
    tree_widget.bind("<Control-C>", lambda e: copy_row())
    tree_widget.bind("<Button-3>", ctx)
    return tree_widget


# ═══════════════════════════════════════════════════════════════════════════════
#  ABA 10: KPIs EXECUTIVOS — Painel visual com métricas e mini-gráficos
# ═══════════════════════════════════════════════════════════════════════════════
class TabKPIs(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._data = []
        self._build()
        auto_refresh_register("kpis", self.refresh)


    def _build(self):
        # Header controls
        ctrl = tk.Frame(self, bg=C["bg"]); ctrl.pack(fill="x", padx=10, pady=8)
        btn(ctrl, "⟳  ATUALIZAR KPIs", self.refresh, C["accent"]).pack(side="left")
        self._status = lbl(ctrl, "Aguardando...", 8, col=C["text_dim"]); self._status.pack(side="left", padx=12)
        btn(ctrl, "📥 EXPORTAR RELATÓRIO", self._export_report, C["surface3"], C["accent"], px=10, py=5).pack(side="right")

        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        # Scroll canvas
        outer = tk.Frame(self, bg=C["bg"]); outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); canvas.pack(fill="both", expand=True)

        self._scroll_frame = tk.Frame(canvas, bg=C["bg"])
        self._sf_id = canvas.create_window((0,0), window=self._scroll_frame, anchor="nw")
        self._scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._sf_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self.sf = self._scroll_frame
        self.after(400, self.refresh)

    def _card(self, parent, title, value, sub, col, w=200):
        f = tk.Frame(parent, bg=C["surface2"], width=w, height=110,
                     highlightthickness=1, highlightbackground=C["border"])
        f.pack_propagate(False); f.pack(side="left", padx=6, pady=6)
        tk.Label(f, text=title, bg=C["surface2"], fg=C["text_dim"],
                 font=("Helvetica Neue",7,"bold")).pack(pady=(10,0))
        tk.Label(f, text=value, bg=C["surface2"], fg=col,
                 font=("Helvetica Neue",20,"bold")).pack()
        tk.Label(f, text=sub, bg=C["surface2"], fg=C["text_mid"],
                 font=("Helvetica Neue",8), wraplength=180).pack()
        return f

    def _bar_chart(self, parent, title, data_pairs, col, h=120, w_total=None):
        """data_pairs: list of (label, value)"""
        sec_f = tk.Frame(parent, bg=C["bg"]); sec_f.pack(fill="x", padx=10, pady=4)
        tk.Label(sec_f, text=title, bg=C["bg"], fg=C["accent"],
                 font=("Helvetica Neue",9,"bold")).pack(anchor="w")
        if not data_pairs: return

        cv_w = w_total or 900
        cv = tk.Canvas(sec_f, bg=C["surface2"], height=h, highlightthickness=0, width=cv_w)
        cv.pack(fill="x", pady=2)

        max_v = max(v for _, v in data_pairs) or 1
        bar_w = max(8, (cv_w - 40) // max(len(data_pairs),1))
        for i, (lab, val) in enumerate(data_pairs):
            x0 = 20 + i * bar_w
            bar_h = int((val / max_v) * (h - 35))
            y1 = h - 22
            y0 = y1 - bar_h
            cv.create_rectangle(x0+2, y0, x0+bar_w-4, y1, fill=col, outline="")
            # label abreviado
            short = lab[:6] if len(lab)>6 else lab
            cv.create_text(x0 + bar_w//2, y1+2, text=short, fill=C["text_dim"],
                           font=("Consolas",6), anchor="n")
            cv.create_text(x0 + bar_w//2, y0-2, text=str(int(val)), fill=col,
                           font=("Consolas",7), anchor="s")

    def _pie_canvas(self, parent, title, data_pairs, colors):
        """Mini gráfico de pizza em canvas."""
        sec_f = tk.Frame(parent, bg=C["surface2"], highlightthickness=1,
                         highlightbackground=C["border"])
        sec_f.pack(side="left", padx=6, pady=6)
        tk.Label(sec_f, text=title, bg=C["surface2"], fg=C["accent"],
                 font=("Helvetica Neue",8,"bold")).pack(pady=(6,0))

        cv = tk.Canvas(sec_f, bg=C["surface2"], width=160, height=130, highlightthickness=0)
        cv.pack(padx=6, pady=4)

        total = sum(v for _, v in data_pairs) or 1
        start = 0
        cx, cy, r = 65, 65, 55
        for i, (lab, val) in enumerate(data_pairs):
            extent = 360 * val / total
            c_col = colors[i % len(colors)]
            cv.create_arc(cx-r, cy-r, cx+r, cy+r, start=start, extent=extent,
                          fill=c_col, outline=C["bg"])
            # Legend
            cv.create_rectangle(135, 10+i*18, 148, 22+i*18, fill=c_col, outline="")
            pct = f"{100*val//total}%"
            cv.create_text(150, 16+i*18, text=f"{pct}", fill=C["text_mid"],
                           font=("Consolas",7), anchor="w")
            cv.create_text(133, 16+i*18, text=f"{lab[:7]}", fill=C["text_dim"],
                           font=("Consolas",6), anchor="e")
            start += extent

    def refresh(self):
        def task():
            d = get_all_events()
            self._data = d
            self._render(d)
            self._status.config(text=f"Atualizado: {now_str()}  |  {len(d)} veículos")
        threading.Thread(target=task, daemon=True).start()

    def _render(self, data):
        for w in self.sf.winfo_children(): w.destroy()
        if not data: return

        on = sum(1 for e in data if safe_int(e.get("ras_eve_ignicao")))
        off = len(data) - on
        no_gps = sum(1 for e in data if not safe_int(e.get("ras_eve_gps_status")))
        vel_list = [abs(safe_int(e.get("ras_eve_velocidade",0))) for e in data]
        speeding = sum(1 for v in vel_list if v > 80)
        vmax = max(vel_list) if vel_list else 0
        vmed = sum(vel_list)/len(vel_list) if vel_list else 0
        bats = [safe_int(e.get("ras_eve_porc_bat_backup",100)) for e in data]
        low_bat = sum(1 for b in bats if b < 30)
        avg_bat = sum(bats)/len(bats) if bats else 0
        volts = [safe_float(e.get("ras_eve_voltagem",0)) for e in data if safe_float(e.get("ras_eve_voltagem",0))>0]
        avg_volt = sum(volts)/len(volts) if volts else 0
        moving = sum(1 for e in data if safe_int(e.get("ras_eve_velocidade",0)) > 0)

        # ─── Row 1: Cards principais ───────────────────────────────────────
        sec(self.sf, "📊  KPIs PRINCIPAIS")
        row1 = tk.Frame(self.sf, bg=C["bg"]); row1.pack(fill="x", padx=6)
        self._card(row1,"FROTA TOTAL", str(len(data)), "veículos monitorados", C["blue"])
        self._card(row1,"IGN. ON", str(on), f"{100*on//max(len(data),1)}% da frota", C["green"])
        self._card(row1,"IGN. OFF", str(off), f"{100*off//max(len(data),1)}% da frota", C["text_mid"])
        self._card(row1,"EM MOVIMENTO", str(moving), "com velocidade > 0", C["accent"])
        self._card(row1,"SEM GPS", str(no_gps), "sinal perdido/falha", C["danger"])
        self._card(row1,"EXCESSO VEL.", str(speeding), "acima de 80 km/h", C["warn"])

        # ─── Row 2: Velocidade ─────────────────────────────────────────────
        sec(self.sf, "🚀  VELOCIDADE")
        row2 = tk.Frame(self.sf, bg=C["bg"]); row2.pack(fill="x", padx=6)
        self._card(row2,"VEL. MÁXIMA", f"{vmax}", "km/h registrado agora", C["danger"])
        self._card(row2,"VEL. MÉDIA", f"{vmed:.1f}", "km/h média da frota", C["warn"])
        self._card(row2,"ACIMA 60", str(sum(1 for v in vel_list if v>60)), "veículos", C["orange"])
        self._card(row2,"ACIMA 80", str(speeding), "veículos em excesso", C["danger"])
        self._card(row2,"ACIMA 100", str(sum(1 for v in vel_list if v>100)), "crítico", "#FF0000")

        # ─── Bar chart: vel por faixa ─────────────────────────────────────
        faixas = [("0","0"),("1-30","1-30"),("31-60","31-60"),("61-80","61-80"),("81-100","81-100"),(">100",">100")]
        counts_f = [
            sum(1 for v in vel_list if v==0),
            sum(1 for v in vel_list if 1<=v<=30),
            sum(1 for v in vel_list if 31<=v<=60),
            sum(1 for v in vel_list if 61<=v<=80),
            sum(1 for v in vel_list if 81<=v<=100),
            sum(1 for v in vel_list if v>100),
        ]
        self._bar_chart(self.sf, "📊 Distribuição de Velocidade (km/h)",
                        list(zip(["0","1-30","31-60","61-80","81-100",">100"], counts_f)), C["accent"])

        # ─── Row 3: Saúde ─────────────────────────────────────────────────
        sec(self.sf, "🔋  SAÚDE DA FROTA")
        row3 = tk.Frame(self.sf, bg=C["bg"]); row3.pack(fill="x", padx=6)
        self._card(row3,"BAT. MÉDIA", f"{avg_bat:.0f}%", "bateria backup", C["green"] if avg_bat>50 else C["warn"])
        self._card(row3,"BAT. BAIXA (<30%)", str(low_bat), "veículos críticos", C["danger"])
        self._card(row3,"VOLT. MÉDIA", f"{avg_volt:.1f}V", "tensão elétrica", C["blue"])
        sat_vals = [safe_int(e.get("ras_eve_satelites",0)) for e in data]
        avg_sat = sum(sat_vals)/len(sat_vals) if sat_vals else 0
        self._card(row3,"SATÉLITES MÉD.", f"{avg_sat:.1f}", "satélites por veículo", C["accent"])
        gps_ok = len(data) - no_gps
        self._card(row3,"GPS OK", str(gps_ok), f"{100*gps_ok//max(len(data),1)}% da frota", C["green"])

        # ─── Gráfico pizza: Ignição ────────────────────────────────────────
        row4 = tk.Frame(self.sf, bg=C["bg"]); row4.pack(fill="x", padx=10, pady=4)
        sec(self.sf, "🥧  Distribuição Visual")
        row_pie = tk.Frame(self.sf, bg=C["bg"]); row_pie.pack(fill="x", padx=10, pady=4)
        if len(data) > 0:
            self._pie_canvas(row_pie, "Ignição",
                             [("ON", on),("OFF", off)],
                             [C["green"], C["surface3"]])
            self._pie_canvas(row_pie, "GPS Status",
                             [("OK", gps_ok),("Falha", no_gps)],
                             [C["accent"], C["danger"]])
            self._pie_canvas(row_pie, "Velocidade",
                             [("Parado",counts_f[0]),("Normal",counts_f[1]+counts_f[2]),
                              ("Atento",counts_f[3]),("Excesso",counts_f[4]+counts_f[5])],
                             [C["text_mid"],C["green"],C["warn"],C["danger"]])

        # ─── Top 10 mais rápidos ───────────────────────────────────────────
        sec(self.sf, "🏎  TOP 10 MAIS RÁPIDOS AGORA")
        top10 = sorted(data, key=lambda e: abs(safe_int(e.get("ras_eve_velocidade",0))), reverse=True)[:10]
        ft_top = FilterableTree(self.sf,
            ("Pos.","Placa","Veículo","Motorista","Velocidade","Ignição","GPS","Data"),
            (40,90,130,130,100,80,60,150), "Top10", C["warn"], 10)
        for i,e in enumerate(top10,1):
            v = abs(safe_int(e.get("ras_eve_velocidade",0)))
            medals = ["🥇","🥈","🥉"]
            pos = medals[i-1] if i<=3 else f"#{i}"
            ft_top.tree.insert("","end", values=(pos,
                safe_str(e.get("ras_vei_placa")),safe_str(e.get("ras_vei_veiculo")),
                safe_str(e.get("ras_mot_nome")),f"{v} km/h",
                "🟢 ON" if safe_int(e.get("ras_eve_ignicao")) else "⚫ OFF",
                "✓" if safe_int(e.get("ras_eve_gps_status")) else "✗",
                safe_str(e.get("ras_eve_data_gps"))),
                tags=("al" if v>80 else "ok",))
        ft_top.tag_configure("al", background="#1a0808")
        ft_top.tag_configure("ok", background=C["surface2"])

        # ─── Clientes com mais veículos ────────────────────────────────────
        sec(self.sf, "👥  FROTA POR CLIENTE")
        from collections import Counter
        cli_count = Counter(safe_str(e.get("ras_cli_desc","Desconhecido")) for e in data)
        top_cli = cli_count.most_common(15)
        self._bar_chart(self.sf, "Veículos por Cliente (Top 15)",
                        top_cli, C["purple"])

        # ─── Alerta de qualidade GPS ───────────────────────────────────────
        sec(self.sf, "📡  QUALIDADE DE SINAL GPS")
        sat_ranges = [
            ("0 sat",  sum(1 for e in data if safe_int(e.get("ras_eve_satelites",0)) == 0)),
            ("1-3",    sum(1 for e in data if 1 <= safe_int(e.get("ras_eve_satelites",0)) <= 3)),
            ("4-6",    sum(1 for e in data if 4 <= safe_int(e.get("ras_eve_satelites",0)) <= 6)),
            ("7-9",    sum(1 for e in data if 7 <= safe_int(e.get("ras_eve_satelites",0)) <= 9)),
            ("10+",    sum(1 for e in data if safe_int(e.get("ras_eve_satelites",0)) >= 10)),
        ]
        self._bar_chart(self.sf, "Distribuição de Satélites",
                        sat_ranges, C["accent"])

    def _export_report(self):
        if not self._data:
            messagebox.showinfo("KPIs","Carregue os dados primeiro."); return
        data = self._data
        on = sum(1 for e in data if safe_int(e.get("ras_eve_ignicao")))
        off = len(data) - on
        no_gps = sum(1 for e in data if not safe_int(e.get("ras_eve_gps_status")))
        vel_list = [abs(safe_int(e.get("ras_eve_velocidade",0))) for e in data]
        speeding = sum(1 for v in vel_list if v > 80)
        vmax = max(vel_list) if vel_list else 0
        vmed = sum(vel_list)/len(vel_list) if vel_list else 0
        bats = [safe_int(e.get("ras_eve_porc_bat_backup",100)) for e in data]
        avg_bat = sum(bats)/len(bats) if bats else 0

        lines = [
            "="*60,
            "  RELATÓRIO EXECUTIVO DE FROTA — IFControll v2.0",
            f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            "="*60,"",
            "  ─── SUMÁRIO EXECUTIVO ─────────────────────────────",
            f"    Veículos monitorados  : {len(data)}",
            f"    Ignição ON            : {on} ({100*on//max(len(data),1)}%)",
            f"    Ignição OFF           : {off} ({100*off//max(len(data),1)}%)",
            f"    Sem GPS               : {no_gps} ({100*no_gps//max(len(data),1)}%)",
            "",
            "  ─── VELOCIDADE ─────────────────────────────────────",
            f"    Velocidade máxima     : {vmax} km/h",
            f"    Velocidade média      : {vmed:.1f} km/h",
            f"    Em excesso (>80 km/h) : {speeding} veículos",
            "",
            "  ─── SAÚDE DA FROTA ──────────────────────────────────",
            f"    Bateria média backup  : {avg_bat:.0f}%",
            f"    Veículos bat < 30%    : {sum(1 for b in bats if b<30)}",
            "",
            "  ─── TOP 10 MAIS RÁPIDOS ─────────────────────────────",
        ]
        top10 = sorted(data, key=lambda e: abs(safe_int(e.get("ras_eve_velocidade",0))), reverse=True)[:10]
        for i, e in enumerate(top10,1):
            lines.append(f"    {i:>2}. {safe_str(e.get('ras_vei_placa')):<10} {abs(safe_int(e.get('ras_eve_velocidade',0))):>4} km/h  {safe_str(e.get('ras_mot_nome'))}")
        lines += ["","="*60]

        path = filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("Texto","*.txt"),("Todos","*.*")],
            initialfile=f"relatorio_executivo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("Relatório", f"Salvo:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ABA 11: ANÁLISE COMPORTAMENTAL — Eventos críticos, risco, comportamento
# ═══════════════════════════════════════════════════════════════════════════════
class TabComportamento(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)

        # ── Score de Risco por Motorista ──────────────────────────────────
        f1 = tk.Frame(nb, bg=C["bg"]); nb.add(f1, text="  🎯 Score de Risco  ")
        c1 = tk.Frame(f1, bg=C["bg"]); c1.pack(fill="x", padx=8, pady=6)
        lbl(c1,"Vel.crítica (km/h):",9,col=C["text_mid"]).pack(side="left")
        e_vc=ent(c1,w=5); e_vc.pack(side="left",padx=4,ipady=4); e_vc.insert(0,"90")
        lbl(c1,"  Bat.mín (%):").pack(side="left")
        e_bat=ent(c1,w=5); e_bat.pack(side="left",padx=4,ipady=4); e_bat.insert(0,"20")
        lb1=lbl(c1,"",col=C["text_dim"]); lb1.pack(side="right")

        ft1 = FilterableTree(f1,
            ("Score","Motorista","Veículos","Vel.Máx","Vel.Méd","Excesso.V","Sem.GPS","Bat.Baixa","Classificação"),
            (55,160,70,90,90,90,80,90,120), "Score", C["danger"], 15)
        ft1.tag_configure("critico", background="#2a0505")
        ft1.tag_configure("alto", background="#1a0d00")
        ft1.tag_configure("medio", background="#1a1400")
        ft1.tag_configure("ok", background=C["surface2"])

        info1=tk.Frame(f1,bg=C["surface3"]); info1.pack(fill="x",padx=8,pady=(0,4))
        lbl(info1,"ℹ  Score 0-100: penaliza vel. acima do limite (-2/km/h), sem GPS (-5), bat baixa (-3). 100 = perfeito.",
            8,col=C["text_mid"],bg=C["surface3"]).pack(padx=8,pady=4,anchor="w")

        def calc_score():
            try: vc=int(e_vc.get()); bat_lim=int(e_bat.get())
            except: vc=90; bat_lim=20
            lb1.config(text="⏳ Calculando...")
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
                ft1.load(rows)
                lb1.config(text=f"{len(mots)} motoristas | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c1,"🎯 CALCULAR",calc_score,C["danger"]).pack(side="left",padx=8)
        mk_export_btn(c1,ft1.tree).pack(side="left",padx=4)
        self.after(400,calc_score)

        # ── Motor Ocioso ──────────────────────────────────────────────────
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  ⏱ Motor Ocioso  ")
        c2=tk.Frame(f2,bg=C["bg"]); c2.pack(fill="x",padx=8,pady=6)
        lbl(c2,"Veículo:",9,col=C["text_mid"]).pack(side="left")
        e2v=ent(c2,w=18); e2v.pack(side="left",padx=4,ipady=4)
        lb2=lbl(c2,"",col=C["text_dim"]); lb2.pack(side="right")
        ei2,ef2=interval_row(tk.Frame(f2,bg=C["bg"]))
        ei2.master.pack(fill="x",padx=8)
        lbl(f2,"Mín. ocioso (min):",9,col=C["text_mid"]).pack(anchor="w",padx=8)
        e2_mn=ent(f2,w=5); e2_mn.pack(anchor="w",padx=8,ipady=4); e2_mn.insert(0,"5")
        _,res2=txtbox(f2,16); _.pack(fill="both",expand=True,padx=8,pady=4)

        def motor_ocioso():
            q=e2v.get().strip()
            if not q: return
            loading(res2)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res2,"Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei2.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef2.get().strip(),"%d/%m/%Y %H:%M")
                    mn=int(e2_mn.get() or 5)
                except: write(res2,"⚠ Inválido.",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res2,"ℹ Nenhum evento.",C["text_mid"]); return

                ociosos=[]; inicio_ocio=None; tot_ocio=0.0
                for ev in evs:
                    ign=safe_int(ev.get("ras_eve_ignicao",0))
                    vel=safe_int(ev.get("ras_eve_velocidade",0))
                    try: dt=datetime.strptime(ev.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                    except: dt=None
                    if dt and ign==1 and vel==0:
                        if inicio_ocio is None: inicio_ocio=dt
                    else:
                        if inicio_ocio and dt:
                            dur=(dt-inicio_ocio).total_seconds()/60
                            if dur>=mn:
                                ociosos.append((inicio_ocio,dt,dur))
                                tot_ocio+=dur
                        inicio_ocio=None

                consumo_est=tot_ocio*0.5  # estimativa: ~0.5L/h ocioso
                lines=[f"  {entry.get('ras_vei_placa','—')}  |  Período: {ini.strftime('%d/%m %H:%M')} → {fim.strftime('%d/%m %H:%M')}",
                    f"  Eventos analisados : {len(evs)}",
                    f"  Períodos ociosos ≥{mn}min: {len(ociosos)}",
                    f"  Tempo total ocioso : {tot_ocio:.0f} min  ({tot_ocio/60:.1f} h)",
                    f"  Consumo estimado   : {consumo_est:.1f} L (@ 0.5L/h)",
                    "","  ─── Detalhamento ─────────────────────────",
                    f"  {'#':>3}  {'Início':<20}  {'Fim':<20}  {'Duração':>8}","  "+"─"*58]
                for i,(a,b,d) in enumerate(ociosos,1):
                    lines.append(f"  {i:>3}  {a.strftime('%d/%m %H:%M:%S'):<20}  {b.strftime('%d/%m %H:%M:%S'):<20}  {d:>5.1f} min")
                write(res2,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()

        btn(c2,"⏱ ANALISAR",motor_ocioso,C["accent"]).pack(side="left",padx=8)
        mk_export_btn(c2,res2,is_text=True).pack(side="left",padx=4)

        # ── Análise de Velocidade por Horário ─────────────────────────────
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  📈 Velocidade × Horário  ")
        c3=tk.Frame(f3,bg=C["bg"]); c3.pack(fill="x",padx=8,pady=6)
        lbl(c3,"Veículo:",9,col=C["text_mid"]).pack(side="left")
        e3v=ent(c3,w=18); e3v.pack(side="left",padx=4,ipady=4)
        lb3=lbl(c3,"",col=C["text_dim"]); lb3.pack(side="right")
        ei3,ef3=interval_row(tk.Frame(f3,bg=C["bg"]))
        ei3.master.pack(fill="x",padx=8)

        cv3=tk.Canvas(f3,bg=C["surface2"],height=220,highlightthickness=0)
        cv3.pack(fill="x",padx=8,pady=4)
        _,res3=txtbox(f3,5); _.pack(fill="x",padx=8,pady=2)

        def vel_horario():
            q=e3v.get().strip()
            if not q: return
            lb3.config(text="⏳...")
            def task():
                entry=find_vehicle(q)
                if not entry: lb3.config(text="✖"); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei3.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef3.get().strip(),"%d/%m/%Y %H:%M")
                except: lb3.config(text="⚠ Datas"); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: lb3.config(text="Sem eventos"); return

                hora_vel=[[] for _ in range(24)]
                for ev in evs:
                    try: h=datetime.strptime(ev.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S").hour
                    except: continue
                    v=abs(safe_int(ev.get("ras_eve_velocidade",0)))
                    hora_vel[h].append(v)

                avg_h=[sum(vs)/len(vs) if vs else 0 for vs in hora_vel]
                max_h=[max(vs) if vs else 0 for vs in hora_vel]

                # Desenha gráfico
                cv3.delete("all")
                W=cv3.winfo_width() or 900; H=220
                pad=40; bar_w=max(4,(W-pad*2)//24)
                max_v=max(max_h) or 1
                for h in range(24):
                    x=pad+h*bar_w
                    # Barra max (fundo)
                    bh=int(max_h[h]/max_v*(H-pad-20))
                    cv3.create_rectangle(x+1,H-pad-bh,x+bar_w-2,H-pad,
                                         fill=C["surface3"],outline="")
                    # Barra média
                    bh2=int(avg_h[h]/max_v*(H-pad-20))
                    cv3.create_rectangle(x+3,H-pad-bh2,x+bar_w-4,H-pad,
                                         fill=C["accent"],outline="")
                    # Hora label
                    cv3.create_text(x+bar_w//2,H-pad+12,text=str(h),
                                    fill=C["text_dim"],font=("Consolas",6),anchor="n")
                # Legenda
                cv3.create_rectangle(W-180,8,W-170,18,fill=C["surface3"],outline="")
                cv3.create_text(W-168,13,text="Vel.Máx",fill=C["text_dim"],font=("Consolas",8),anchor="w")
                cv3.create_rectangle(W-180,22,W-170,32,fill=C["accent"],outline="")
                cv3.create_text(W-168,27,text="Vel.Média",fill=C["text_dim"],font=("Consolas",8),anchor="w")
                cv3.create_text(pad//2,H//2,text="km/h",fill=C["text_dim"],
                                font=("Consolas",7),angle=90)

                # Resumo texto
                hora_pico=avg_h.index(max(avg_h))
                lines=[f"  Hora de maior velocidade média: {hora_pico:02d}h ({max(avg_h):.1f} km/h)",
                    f"  Velocidade máxima registrada: {max(max_h):.0f} km/h",
                    f"  Eventos analisados: {len(evs)}"]
                write(res3,"\n".join(lines))
                lb3.config(text=f"{entry.get('ras_vei_placa','—')} | {len(evs)} pts | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c3,"📈 GERAR",vel_horario,C["accent2"]).pack(side="left",padx=8)

        # ── Comparativo entre dois veículos ───────────────────────────────
        f4=tk.Frame(nb,bg=C["bg"]); nb.add(f4,text="  ⚖ Comparativo  ")
        c4=tk.Frame(f4,bg=C["bg"]); c4.pack(fill="x",padx=8,pady=6)
        lbl(c4,"Veículo A:",9,col=C["text_mid"]).pack(side="left")
        e4a=ent(c4,w=16); e4a.pack(side="left",padx=4,ipady=4)
        lbl(c4,"  vs  Veículo B:",9,col=C["text_mid"]).pack(side="left")
        e4b=ent(c4,w=16); e4b.pack(side="left",padx=4,ipady=4)
        lb4=lbl(c4,"",col=C["text_dim"]); lb4.pack(side="right")
        ei4,ef4=interval_row(tk.Frame(f4,bg=C["bg"]))
        ei4.master.pack(fill="x",padx=8)
        _,res4=txtbox(f4,18); _.pack(fill="both",expand=True,padx=8,pady=4)

        def comparar():
            qa=e4a.get().strip(); qb=e4b.get().strip()
            if not qa or not qb: return
            loading(res4)
            def task():
                ea=find_vehicle(qa); eb=find_vehicle(qb)
                if not ea or not eb: err(res4,"Um ou ambos não encontrados."); return
                try:
                    ini=datetime.strptime(ei4.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef4.get().strip(),"%d/%m/%Y %H:%M")
                except: write(res4,"⚠ Datas.",C["warn"]); return

                def stats(entry):
                    vid=safe_int(entry.get("ras_vei_id",0))
                    evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                    vel_l=[abs(safe_int(e.get("ras_eve_velocidade",0))) for e in evs]
                    t_on=t_off=km=0.0; prev=None
                    for ev in evs:
                        vel=safe_int(ev.get("ras_eve_velocidade",0))
                        ign=safe_int(ev.get("ras_eve_ignicao",0))
                        lat=ev.get("ras_eve_latitude"); lon=ev.get("ras_eve_longitude")
                        try: dt=datetime.strptime(ev.get("ras_eve_data_gps",""),"%d/%m/%Y %H:%M:%S")
                        except: dt=None
                        if prev and dt and prev[0]:
                            s=max(0,(dt-prev[0]).total_seconds())
                            if prev[1]: t_on+=s
                            else: t_off+=s
                        if prev and prev[2] and lat: km+=haversine(prev[2],prev[3],lat,lon)
                        prev=(dt,ign,lat,lon)
                    return {"placa":safe_str(entry.get("ras_vei_placa")),
                            "veiculo":safe_str(entry.get("ras_vei_veiculo")),
                            "eventos":len(evs),"km":km,
                            "vmax":max(vel_l) if vel_l else 0,
                            "vmed":sum(vel_l)/len(vel_l) if vel_l else 0,
                            "t_on":t_on,"t_off":t_off,
                            "excesso":sum(1 for v in vel_l if v>80)}

                sa=stats(ea); sb=stats(eb)

                def cmp(a,b,inv=False):
                    if a>b: return ("★","—") if not inv else ("—","★")
                    elif b>a: return ("—","★") if not inv else ("★","—")
                    return ("=","=")

                w=38
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
                write(res4,"\n".join(lines))
                lb4.config(text=f"Comparativo gerado | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c4,"⚖ COMPARAR",comparar,C["accent2"]).pack(side="left",padx=8)
        mk_export_btn(c4,res4,is_text=True).pack(side="left",padx=4)

        # ── Mapa de Calor de Alertas por Hora/Dia ─────────────────────────
        f5=tk.Frame(nb,bg=C["bg"]); nb.add(f5,text="  🔥 Mapa de Calor  ")
        c5=tk.Frame(f5,bg=C["bg"]); c5.pack(fill="x",padx=8,pady=6)
        lbl(c5,"Início:",9,col=C["text_mid"]).pack(side="left")
        ei5=ent(c5,w=18); ei5.pack(side="left",padx=4,ipady=4)
        ei5.insert(0,(datetime.now()-timedelta(days=30)).strftime("%d/%m/%Y %H:%M"))
        lbl(c5,"  Fim:").pack(side="left")
        ef5=ent(c5,w=18); ef5.pack(side="left",padx=4,ipady=4)
        ef5.insert(0,datetime.now().strftime("%d/%m/%Y %H:%M"))
        lb5=lbl(c5,"",col=C["text_dim"]); lb5.pack(side="right")

        cv5=tk.Canvas(f5,bg=C["surface2"],height=200,highlightthickness=0)
        cv5.pack(fill="x",padx=8,pady=4)
        info5=lbl(f5,"",8,col=C["text_mid"]); info5.pack(padx=8,anchor="w")

        def heat_map():
            lb5.config(text="⏳ Carregando alertas...")
            try:
                ini=datetime.strptime(ei5.get().strip(),"%d/%m/%Y %H:%M")
                fim=datetime.strptime(ef5.get().strip(),"%d/%m/%Y %H:%M")
            except: lb5.config(text="⚠ Datas"); return
            def task():
                d=extract_list(api_get(f"/alerts/period/initial/{ts(ini)}/final/{ts(fim)}").get("data",[]))
                # matriz 7 dias × 24 horas
                mat=[[0]*24 for _ in range(7)]
                dias=["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
                for a in d:
                    dt=parse_dt(safe_str(a.get("ras_eal_data_alerta")))
                    if dt: mat[dt.weekday()][dt.hour]+=1

                mx=max(max(row) for row in mat) or 1
                cv5.delete("all")
                W=cv5.winfo_width() or 900; H=200
                cell_w=(W-50)//24; cell_h=(H-20)//7
                # Cabeçalhos horas
                for h in range(24):
                    cv5.create_text(50+h*cell_w+cell_w//2,8,text=str(h),
                                    fill=C["text_dim"],font=("Consolas",6))
                for d_idx,dia in enumerate(dias):
                    cv5.create_text(24,22+d_idx*cell_h+cell_h//2,text=dia,
                                    fill=C["text_dim"],font=("Consolas",7))
                    for h in range(24):
                        v=mat[d_idx][h]
                        intensity=int(255*v/mx) if mx>0 else 0
                        r2=min(255,intensity+50); g2=max(0,50-intensity//3); b2=10
                        col_hex=f"#{r2:02x}{g2:02x}{b2:02x}"
                        x=50+h*cell_w; y=16+d_idx*cell_h
                        cv5.create_rectangle(x+1,y+1,x+cell_w-1,y+cell_h-1,
                                             fill=col_hex,outline=C["bg"])
                        if v>0 and cell_w>16:
                            cv5.create_text(x+cell_w//2,y+cell_h//2,text=str(v),
                                            fill="white",font=("Consolas",6))

                total=sum(mat[d_idx][h] for d_idx in range(7) for h in range(24))
                pico_d=max(range(7),key=lambda d_idx:sum(mat[d_idx]))
                pico_h=max(range(24),key=lambda h:sum(mat[d_idx][h] for d_idx in range(7)))
                info5.config(text=f"Total: {total} alertas  |  Dia pico: {dias[pico_d]}  |  Hora pico: {pico_h:02d}h")
                lb5.config(text=f"{len(d)} alertas carregados | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c5,"🔥 GERAR MAPA",heat_map,C["danger"]).pack(side="left",padx=8)


# ═══════════════════════════════════════════════════════════════════════════════
#  ABA 12: CENTRO DE CUSTOS — Estimativas financeiras de frota
# ═══════════════════════════════════════════════════════════════════════════════
class TabCustos(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)

        # ── Custo por Veículo (Período) ───────────────────────────────────
        f1=tk.Frame(nb,bg=C["bg"]); nb.add(f1,text="  💰 Custo por Veículo  ")
        ph=tk.Frame(f1,bg=C["bg"]); ph.pack(fill="x",padx=8,pady=6)
        lbl(ph,"Veículo (placa/nome):",9,col=C["text_mid"]).pack(anchor="w",pady=(0,2))
        e1v=ent(ph); e1v.pack(fill="x",ipady=5)
        ei1,ef1=interval_row(ph)
        rp=tk.Frame(ph,bg=C["bg"]); rp.pack(fill="x",pady=4)
        lbl(rp,"Preço combustível R$/L:",9,col=C["text_mid"],width=24).pack(side="left",anchor="w")
        e1_preco=ent(rp,w=8); e1_preco.pack(side="left",padx=4,ipady=4); e1_preco.insert(0,"6.20")
        lbl(rp,"  Consumo km/L:",9,col=C["text_mid"]).pack(side="left")
        e1_cons=ent(rp,w=8); e1_cons.pack(side="left",padx=4,ipady=4); e1_cons.insert(0,"10.0")
        lbl(rp,"  Custo/h motorista R$:",9,col=C["text_mid"]).pack(side="left")
        e1_mot=ent(rp,w=8); e1_mot.pack(side="left",padx=4,ipady=4); e1_mot.insert(0,"25.0")
        _,res1=txtbox(f1,18); _.pack(fill="both",expand=True,padx=8,pady=4)

        def custo_veiculo():
            q=e1v.get().strip()
            if not q: return
            loading(res1)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res1,"Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei1.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef1.get().strip(),"%d/%m/%Y %H:%M")
                    preco=float(e1_preco.get()); cons=float(e1_cons.get()); custo_h=float(e1_mot.get())
                except: write(res1,"⚠ Parâmetros inválidos.",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res1,"ℹ Nenhum evento.",C["text_mid"]); return

                km=0.0; t_on=t_off=t_ocio=0.0; vmax=0; prev=None
                for ev in evs:
                    vel=safe_int(ev.get("ras_eve_velocidade",0))
                    ign=safe_int(ev.get("ras_eve_ignicao",0))
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
                c_comb=litros*preco
                h_on=t_on/3600
                c_mot=h_on*custo_h
                c_ocio=(t_ocio/3600)*0.5*preco  # ocioso: ~0.5L/h
                c_total=c_comb+c_mot+c_ocio
                c_km=c_total/km if km>0 else 0

                lines=["="*52,
                    f"  RELATÓRIO DE CUSTOS — {entry.get('ras_vei_placa','—')}",
                    f"  {entry.get('ras_vei_veiculo','—')}",
                    f"  Motorista: {entry.get('ras_mot_nome','—')}",
                    f"  Período  : {ini.strftime('%d/%m/%Y %H:%M')} → {fim.strftime('%d/%m/%Y %H:%M')}",
                    "","  ─── Desempenho ───────────────────────────",
                    f"    Distância percorrida  : {km:>9.1f} km",
                    f"    Vel. máxima           : {vmax:>9} km/h",
                    f"    Tempo ignição ON      : {hms(t_on):>12}",
                    f"    Tempo ocioso (ign.ON) : {hms(t_ocio):>12}",
                    "","  ─── Estimativa de Custos ─────────────────",
                    f"    Litros consumidos     : {litros:>9.1f} L",
                    f"    Custo combustível     : R$ {c_comb:>8.2f}",
                    f"    Custo motorista       : R$ {c_mot:>8.2f}  ({h_on:.1f}h × R${custo_h:.2f})",
                    f"    Custo ocioso          : R$ {c_ocio:>8.2f}  (est.)",
                    f"  {'─'*44}",
                    f"    CUSTO TOTAL ESTIMADO  : R$ {c_total:>8.2f}",
                    f"    Custo por km          : R$ {c_km:>8.2f}/km",
                    "","  ─── Parâmetros Utilizados ────────────────",
                    f"    Combustível           : R$ {preco:.2f}/L",
                    f"    Consumo médio         : {cons:.1f} km/L",
                    f"    Custo horista mot.    : R$ {custo_h:.2f}/h",
                    "="*52]
                write(res1,"\n".join(lines))
            threading.Thread(target=task,daemon=True).start()

        btn(ph,"💰 CALCULAR CUSTOS",custo_veiculo,C["success"]).pack(pady=(6,0))
        mk_export_btn(ph,res1,is_text=True).pack(pady=(4,0))

        # ── Ranking de Custo por Motorista (snapshot) ─────────────────────
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  📋 Ranking por Motorista  ")
        c2=tk.Frame(f2,bg=C["bg"]); c2.pack(fill="x",padx=8,pady=6)
        lbl(c2,"Custo/km R$:",9,col=C["text_mid"]).pack(side="left")
        e2c=ent(c2,w=7); e2c.pack(side="left",padx=4,ipady=4); e2c.insert(0,"0.62")
        lbl(c2,"  Penalidade excesso (R$/ocorr.):").pack(side="left")
        e2p=ent(c2,w=7); e2p.pack(side="left",padx=4,ipady=4); e2p.insert(0,"10.0")
        lb2=lbl(c2,"",col=C["text_dim"]); lb2.pack(side="right")

        ft2 = FilterableTree(f2,
            ("Pos.","Motorista","Placas","Vel.Máx","Vel.Méd","Excessos","Custo.Estim.","Penalidade","Total"),
            (40,160,80,90,90,80,110,110,110),"CustoRk",C["success"],14)
        ft2.tag_configure("caro",background="#150d00")
        ft2.tag_configure("ok",background=C["surface2"])

        def ranking_custo():
            try: cpm=float(e2c.get()); pen=float(e2p.get())
            except: cpm=0.62; pen=10.0
            lb2.config(text="⏳...")
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
                    # Estimativa muito simplificada (sem km real)
                    custo_est=len(vs)*0.1*cpm  # heurística
                    pen_t=exc*pen
                    total_c=custo_est+pen_t
                    rows.append(((f"—",nm,len(d["veics"]),f"{vmx} km/h",f"{vmd:.1f} km/h",
                                  exc,f"R$ {custo_est:.2f}",f"R$ {pen_t:.2f}",f"R$ {total_c:.2f}"),
                                 "caro" if total_c>200 else "ok"))
                rows.sort(key=lambda x:-float(x[0][8].replace("R$ ","")))
                medals=["🥇","🥈","🥉"]
                for i,(vals,tag) in enumerate(rows):
                    rows[i]=((medals[i] if i<3 else f"#{i+1}",)+vals[1:],tag)
                ft2.load(rows)
                lb2.config(text=f"{len(mots)} motoristas | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c2,"📋 CALCULAR",ranking_custo,C["success"]).pack(side="left",padx=8)
        mk_export_btn(c2,ft2.tree).pack(side="left",padx=4)
        self.after(400,ranking_custo)

        # ── Configuração de parâmetros de custo ───────────────────────────
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  ⚙ Parâmetros  ")
        b3=tk.Frame(f3,bg=C["bg"]); b3.pack(fill="both",expand=True,padx=20,pady=12)
        sec(b3,"CONFIGURAÇÃO DE PARÂMETROS DE CUSTO",C["success"])
        lbl(b3,"Use estes valores como referência nos cálculos de custo.",
            9,col=C["text_mid"]).pack(anchor="w",pady=(0,10))
        params=[
            ("Preço médio combustível (R$/L)","6.20"),
            ("Consumo médio frota (km/L)","10.0"),
            ("Custo horista motorista (R$/h)","25.0"),
            ("Custo manutenção (R$/km)","0.08"),
            ("Seguro médio mensal (R$)","800.0"),
            ("Depreciação mensal (R$)","1200.0"),
            ("Penalidade por excesso de vel. (R$/ocorr.)","10.0"),
            ("Consumo em ocioso (L/h)","0.5"),
        ]
        for lab,default in params:
            r=tk.Frame(b3,bg=C["bg"]); r.pack(fill="x",pady=3)
            lbl(r,f"{lab}:",9,col=C["text_mid"],width=38).pack(side="left",anchor="w")
            e=ent(r,w=12); e.pack(side="left",ipady=4); e.insert(0,default)
        lbl(b3,"\nℹ  Estes parâmetros são locais a esta sessão. Configure conforme sua realidade operacional.",
            8,col=C["text_dim"]).pack(anchor="w",pady=8)


# ═══════════════════════════════════════════════════════════════════════════════
#  ABA 13: COMUNICAÇÃO & DISPONIBILIDADE — Janelas sem sinal
# ═══════════════════════════════════════════════════════════════════════════════
class TabComunicacao(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)

        # ── Janelas de Silêncio por Veículo ──────────────────────────────
        f1=tk.Frame(nb,bg=C["bg"]); nb.add(f1,text="  📡 Janelas de Silêncio  ")
        c1=tk.Frame(f1,bg=C["bg"]); c1.pack(fill="x",padx=8,pady=6)
        lbl(c1,"Veículo:",9,col=C["text_mid"]).pack(side="left")
        e1v=ent(c1,w=18); e1v.pack(side="left",padx=4,ipady=4)
        lb1=lbl(c1,"",col=C["text_dim"]); lb1.pack(side="right")
        ei1,ef1=interval_row(tk.Frame(f1,bg=C["bg"]))
        ei1.master.pack(fill="x",padx=8)
        lbl(f1,"Gap mínimo para silêncio (min):",9,col=C["text_mid"]).pack(anchor="w",padx=8)
        e1mn=ent(f1,w=5); e1mn.pack(anchor="w",padx=8,ipady=4); e1mn.insert(0,"10")
        _,res1=txtbox(f1,16); _.pack(fill="both",expand=True,padx=8,pady=4)

        def silencio():
            q=e1v.get().strip()
            if not q: return
            loading(res1)
            def task():
                entry=find_vehicle(q)
                if not entry: err(res1,"Não encontrado."); return
                vid=safe_int(entry.get("ras_vei_id",0))
                try:
                    ini=datetime.strptime(ei1.get().strip(),"%d/%m/%Y %H:%M")
                    fim=datetime.strptime(ef1.get().strip(),"%d/%m/%Y %H:%M")
                    mn=int(e1mn.get() or 10)
                except: write(res1,"⚠",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res1,"ℹ Sem eventos.",C["text_mid"]); return

                gaps=[]; prev_dt=None; tot_gap=0.0
                for ev in evs:
                    dt=parse_dt(safe_str(ev.get("ras_eve_data_enviado") or ev.get("ras_eve_data_gps")))
                    if dt is None: continue
                    if prev_dt:
                        g=(dt-prev_dt).total_seconds()/60
                        if g>=mn:
                            gaps.append((prev_dt,dt,g))
                            tot_gap+=g
                    prev_dt=dt

                periodo_min=(fim-ini).total_seconds()/60 or 1
                disponib=max(0,100-tot_gap*100/periodo_min)
                lines=[f"  {entry.get('ras_vei_placa','—')}  |  {ini.strftime('%d/%m %H:%M')} → {fim.strftime('%d/%m %H:%M')}",
                    f"  Eventos transmitidos : {len(evs)}",
                    f"  Janelas de silêncio ≥{mn}min: {len(gaps)}",
                    f"  Tempo total sem sinal: {tot_gap:.0f} min  ({tot_gap/60:.1f} h)",
                    f"  Disponibilidade comun.: {disponib:.1f}%",
                    "","  ─── Gaps Detectados ──────────────────────",
                    f"  {'#':>3}  {'Último sinal':<22}  {'Retorno':<22}  {'Duração':>8}",
                    "  "+"─"*62]
                for i,(a,b,g) in enumerate(gaps,1):
                    sev="🔴" if g>60 else "🟡" if g>30 else "🟠"
                    lines.append(f"  {i:>3}  {a.strftime('%d/%m %H:%M:%S'):<22}  {b.strftime('%d/%m %H:%M:%S'):<22}  {sev} {g:.0f} min")
                write(res1,"\n".join(lines),C["success"] if disponib>95 else C["warn"] if disponib>80 else C["danger"])
            threading.Thread(target=task,daemon=True).start()

        btn(c1,"📡 ANALISAR",silencio,C["accent"]).pack(side="left",padx=8)
        mk_export_btn(c1,res1,is_text=True).pack(side="left",padx=4)

        # ── Status de Comunicação da Frota (snapshot) ─────────────────────
        f2=tk.Frame(nb,bg=C["bg"]); nb.add(f2,text="  📊 Status da Frota  ")
        c2=tk.Frame(f2,bg=C["bg"]); c2.pack(fill="x",padx=8,pady=6)
        lbl(c2,"Atraso máximo aceito:",9,col=C["text_mid"]).pack(side="left")
        e2v=ent(c2,w=5); e2v.pack(side="left",padx=4,ipady=4); e2v.insert(0,"30")
        lbl(c2,"min",8,col=C["text_dim"]).pack(side="left")
        lb2=lbl(c2,"",col=C["text_dim"]); lb2.pack(side="right")

        ft2 = FilterableTree(f2,
            ("Placa","Veículo","Motorista","Última.Comun.","Atraso","Status.Comun.","GPS","Ign."),
            (90,130,130,160,100,130,60,60),"ComSt",C["accent"],16)
        ft2.tag_configure("ok", background=C["surface2"])
        ft2.tag_configure("warn", background="#1a1300")
        ft2.tag_configure("crit", background="#1a0505")

        def status_frota():
            try: max_min=int(e2v.get())
            except: max_min=30
            lb2.config(text="⏳...")
            def task():
                data=get_all_events(); now=datetime.now()
                rows=[]
                for ev in data:
                    d_env=safe_str(ev.get("ras_eve_data_enviado") or ev.get("ras_eve_data_gps"))
                    dt=parse_dt(d_env)
                    if dt:
                        diff_min=(now-dt).total_seconds()/60
                        if diff_min<0: diff_min=0
                        if diff_min<5: st="🟢 OK"; tag="ok"
                        elif diff_min<max_min: st="🟡 Atrasado"; tag="warn"
                        else: st="🔴 Crítico"; tag="crit"
                        atr=f"{diff_min:.0f} min"
                    else:
                        diff_min=9999; st="⚫ Sem data"; tag="crit"; atr="?"
                    ign=safe_int(ev.get("ras_eve_ignicao",0))
                    gps=safe_int(ev.get("ras_eve_gps_status",0))
                    rows.append(((safe_str(ev.get("ras_vei_placa")),
                                  safe_str(ev.get("ras_vei_veiculo")),
                                  safe_str(ev.get("ras_mot_nome")),
                                  d_env, atr, st,
                                  "✓ OK" if gps else "✗ FALHA",
                                  "🟢 ON" if ign else "⚫ OFF"),tag))
                rows.sort(key=lambda x: (0 if x[1]=="crit" else 1 if x[1]=="warn" else 2))
                ft2.load(rows)
                ok_c=sum(1 for _,t in rows if t=="ok")
                lb2.config(text=f"✅ OK: {ok_c}  |  ⚠: {sum(1 for _,t in rows if t=='warn')}  |  🔴: {sum(1 for _,t in rows if t=='crit')}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c2,"⟳ VERIFICAR",status_frota,C["accent"]).pack(side="left",padx=8)
        mk_export_btn(c2,ft2.tree).pack(side="left",padx=4)
        self.after(300,status_frota)

        # ── Uptime por Veículo (Período) ──────────────────────────────────
        f3=tk.Frame(nb,bg=C["bg"]); nb.add(f3,text="  ⏱ Uptime / Disponibilidade  ")
        c3=tk.Frame(f3,bg=C["bg"]); c3.pack(fill="x",padx=8,pady=6)
        lbl(c3,"Intervalo máx entre eventos (min):",9,col=C["text_mid"]).pack(side="left")
        e3int=ent(c3,w=5); e3int.pack(side="left",padx=4,ipady=4); e3int.insert(0,"15")
        lb3=lbl(c3,"",col=C["text_dim"]); lb3.pack(side="right")
        ei3,ef3=interval_row(tk.Frame(f3,bg=C["bg"]))
        ei3.master.pack(fill="x",padx=8)

        ft3 = FilterableTree(f3,
            ("Placa","Veículo","Eventos","Uptime%","Tempo.Online","Janelas.Silêncio","Maior.Gap"),
            (90,130,70,80,120,130,110),"Uptime",C["green"],14)
        ft3.tag_configure("ok",background=C["surface2"])
        ft3.tag_configure("warn",background="#1a1300")
        ft3.tag_configure("crit",background="#1a0505")

        def uptime_all():
            try:
                max_gap=int(e3int.get())*60
                ini=datetime.strptime(ei3.get().strip(),"%d/%m/%Y %H:%M")
                fim=datetime.strptime(ef3.get().strip(),"%d/%m/%Y %H:%M")
            except: lb3.config(text="⚠ Parâmetros"); return
            lb3.config(text="⏳...")
            def task():
                periodo_s=(fim-ini).total_seconds()
                data=get_all_events()
                rows=[]
                for ev in data:
                    vid=safe_int(ev.get("ras_vei_id",0))
                    if not vid: continue
                    evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                    if not evs: continue
                    dts=sorted(filter(None,[parse_dt(safe_str(e.get("ras_eve_data_enviado") or e.get("ras_eve_data_gps"))) for e in evs]))
                    if not dts: continue
                    gaps_over=[]; tot_gap=0
                    for i in range(1,len(dts)):
                        g=(dts[i]-dts[i-1]).total_seconds()
                        if g>max_gap: gaps_over.append(g); tot_gap+=g
                    uptime=max(0,100-tot_gap*100/periodo_s)
                    t_online=periodo_s-tot_gap
                    maior=max(gaps_over)/60 if gaps_over else 0
                    tag="ok" if uptime>95 else "warn" if uptime>80 else "crit"
                    rows.append(((safe_str(ev.get("ras_vei_placa")),
                                  safe_str(ev.get("ras_vei_veiculo")),
                                  len(evs),f"{uptime:.1f}%",hms(t_online),
                                  len(gaps_over),f"{maior:.0f} min"),tag))
                rows.sort(key=lambda x:float(str(x[0][3]).replace("%","")))
                ft3.load(rows)
                lb3.config(text=f"{len(rows)} veículos analisados | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c3,"⏱ ANALISAR TODOS",uptime_all,C["green"]).pack(side="left",padx=8)
        mk_export_btn(c3,ft3.tree).pack(side="left",padx=4)



# ═══════════════════════════════════════════════════════════════════════════════
#  JANELA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
root=tk.Tk()
root.title("IFControll v3.0 — Fleet Intelligence Platform")
root.configure(bg=C["bg"])
sw,sh=root.winfo_screenwidth(),root.winfo_screenheight()
W,H=1280,800; root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}"); root.minsize(1024,650)

# Header
hdr=tk.Frame(root,bg=C["surface"],height=52); hdr.pack(fill="x"); hdr.pack_propagate(False)
tk.Frame(root,bg=C["accent"],height=2).pack(fill="x")
lf=tk.Frame(hdr,bg=C["surface"]); lf.pack(side="left",padx=20)
tk.Label(lf,text="⬡",bg=C["surface"],fg=C["accent"],font=("Helvetica Neue",22,"bold")).pack(side="left")
tk.Label(lf,text="  IFControll",bg=C["surface"],fg=C["text"],font=("Helvetica Neue",17,"bold")).pack(side="left")
tk.Label(hdr,text="Fleet Intelligence Platform  ·  Fulltrack2 API  v3.0",
         bg=C["surface"],fg=C["text_dim"],font=("Helvetica Neue",9)).pack(side="left",padx=8,pady=20)
rf=tk.Frame(hdr,bg=C["surface"]); rf.pack(side="right",padx=20)
mk_theme_btn(rf, root).pack(side="right", padx=8, pady=14)
ctrl_rf = mk_refresh_controls(rf, root)
ctrl_rf.pack(side="right", padx=4, pady=14)
tk.Label(rf,text="  LIVE  ",bg=C["success"],fg=C["bg"],font=("Helvetica Neue",8,"bold"),padx=6,pady=3).pack(side="right",pady=16)
clk=tk.Label(rf,bg=C["surface"],fg=C["text_dim"],font=("Courier New",9)); clk.pack(side="right",padx=12,pady=16)
def tick(): clk.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S")); root.after(1000,tick)
tick()

# Notebook principal
st=ttk.Style(); st.theme_use("clam")
st.configure("M.TNotebook",background=C["bg"],borderwidth=0,tabmargins=0)
st.configure("M.TNotebook.Tab",background=C["surface"],foreground=C["text_dim"],
             font=("Helvetica Neue",9),padding=[10,8],borderwidth=0)
st.map("M.TNotebook.Tab",background=[("selected",C["surface2"]),("active",C["hover"])],
       foreground=[("selected",C["accent"]),("active",C["text"])])

nb=ttk.Notebook(root,style="M.TNotebook"); nb.pack(fill="both",expand=True)
for name,cls in [
    ("  📡  Dashboard  ",TabDashboard),
    ("  🚨  Alertas  ",TabAlertas),
    ("  🗺  Cercas  ",TabCercas),
    ("  🚚  Veículos  ",TabVeiculos),
    ("  📊  Relatórios  ",TabRelatorios),
    ("  👥  Clientes  ",TabClientes),
    ("  📡  Rastreadores  ",TabRastreadores),
    ("  ⚡  Comandos  ",TabComandos),
    ("  🔧  Diagnóstico  ",TabDiagnostico),
    ("  📈  KPIs Executivos  ",TabKPIs),
    ("  🎯  Comportamento  ",TabComportamento),
    ("  💰  Custos  ",TabCustos),
    ("  📶  Comunicação  ",TabComunicacao),
    (" 📋 Cronologia ",    TabCronologia),
]:
    nb.add(cls(nb),text=name)

# Footer
tk.Frame(root,bg=C["border"],height=1).pack(fill="x")
ft=tk.Frame(root,bg=C["surface"],height=24); ft.pack(fill="x"); ft.pack_propagate(False)
tk.Label(ft,text="IFControll v3.0  ·  Powered by Fulltrack2 REST API  ·  © 2025",
         bg=C["surface"],fg=C["text_dim"],font=("Helvetica Neue",8)).pack(side="left",padx=16,pady=4)
tk.Label(ft,text=f"Python {__import__('sys').version.split()[0]}  ·  Tkinter  ·  Ctrl+C para copiar  ·  Clique direito no cabeçalho para ordenar",
         bg=C["surface"],fg=C["text_dim"],font=("Helvetica Neue",8)).pack(side="right",padx=16,pady=4)

# Ctrl+C universal
bind_global_copy(root)

# Inicia o loop de auto-refresh de 60 segundos
auto_refresh_loop(root)
root.mainloop()