"""
tabs/kpis.py
Aba 10 — KPIs Executivos: cards, gráficos de barra, pizza, top10 e relatório.
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from collections import Counter

from utils.theme_manager import C
from utils.auto_refresh_export import now_str, auto_refresh_register
from core import get_all_events, safe_int, safe_float, safe_str
from widgets import btn, lbl, mk_export_btn, FilterableTree


class TabKPIs(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._data = []
        self._build()
        auto_refresh_register("kpis", self.refresh)

    def _build(self):
        ctrl = tk.Frame(self, bg=C["bg"]); ctrl.pack(fill="x", padx=10, pady=8)
        btn(ctrl,"⟳  ATUALIZAR KPIs",self.refresh,C["accent"]).pack(side="left")
        self._status=lbl(ctrl,"Aguardando...",8,col=C["text_dim"]); self._status.pack(side="left",padx=12)
        btn(ctrl,"📥 EXPORTAR RELATÓRIO",self._export_report,C["surface3"],C["accent"],px=10,py=5).pack(side="right")
        tk.Frame(self,bg=C["border"],height=1).pack(fill="x")
        outer=tk.Frame(self,bg=C["bg"]); outer.pack(fill="both",expand=True)
        canvas=tk.Canvas(outer,bg=C["bg"],highlightthickness=0)
        vsb=ttk.Scrollbar(outer,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right",fill="y"); canvas.pack(fill="both",expand=True)
        self._scroll_frame=tk.Frame(canvas,bg=C["bg"])
        self._sf_id=canvas.create_window((0,0),window=self._scroll_frame,anchor="nw")
        self._scroll_frame.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e:canvas.itemconfig(self._sf_id,width=e.width))
        canvas.bind_all("<MouseWheel>",lambda e:canvas.yview_scroll(int(-1*(e.delta/120)),"units"))
        self.sf=self._scroll_frame
        self.after(400,self.refresh)

    def _sec(self,title):
        f=tk.Frame(self.sf,bg=C["bg"]); f.pack(fill="x",pady=(10,4))
        tk.Label(f,text=title,bg=C["bg"],fg=C["accent"],font=("Helvetica Neue",9,"bold")).pack(side="left")
        tk.Frame(f,bg=C["border"],height=1).pack(side="left",fill="x",expand=True,padx=(6,0),pady=6)

    def _card(self,parent,title,value,sub,col,w=200):
        f=tk.Frame(parent,bg=C["surface2"],width=w,height=110,highlightthickness=1,highlightbackground=C["border"])
        f.pack_propagate(False); f.pack(side="left",padx=6,pady=6)
        tk.Label(f,text=title,bg=C["surface2"],fg=C["text_dim"],font=("Helvetica Neue",7,"bold")).pack(pady=(10,0))
        tk.Label(f,text=value,bg=C["surface2"],fg=col,font=("Helvetica Neue",20,"bold")).pack()
        tk.Label(f,text=sub,bg=C["surface2"],fg=C["text_mid"],font=("Helvetica Neue",8),wraplength=180).pack()
        return f

    def _bar_chart(self,parent,title,data_pairs,col,h=120,w_total=None):
        sec_f=tk.Frame(parent,bg=C["bg"]); sec_f.pack(fill="x",padx=10,pady=4)
        tk.Label(sec_f,text=title,bg=C["bg"],fg=C["accent"],font=("Helvetica Neue",9,"bold")).pack(anchor="w")
        if not data_pairs: return
        cv_w=w_total or 900
        cv=tk.Canvas(sec_f,bg=C["surface2"],height=h,highlightthickness=0,width=cv_w)
        cv.pack(fill="x",pady=2)
        max_v=max(v for _,v in data_pairs) or 1
        bar_w=max(8,(cv_w-40)//max(len(data_pairs),1))
        for i,(lab,val) in enumerate(data_pairs):
            x0=20+i*bar_w; bar_h=int((val/max_v)*(h-35)); y1=h-22; y0=y1-bar_h
            cv.create_rectangle(x0+2,y0,x0+bar_w-4,y1,fill=col,outline="")
            cv.create_text(x0+bar_w//2,y1+2,text=lab[:6],fill=C["text_dim"],font=("Consolas",6),anchor="n")
            cv.create_text(x0+bar_w//2,y0-2,text=str(int(val)),fill=col,font=("Consolas",7),anchor="s")

    def _pie_canvas(self,parent,title,data_pairs,colors):
        sec_f=tk.Frame(parent,bg=C["surface2"],highlightthickness=1,highlightbackground=C["border"])
        sec_f.pack(side="left",padx=6,pady=6)
        tk.Label(sec_f,text=title,bg=C["surface2"],fg=C["accent"],font=("Helvetica Neue",8,"bold")).pack(pady=(6,0))
        cv=tk.Canvas(sec_f,bg=C["surface2"],width=160,height=130,highlightthickness=0); cv.pack(padx=6,pady=4)
        total=sum(v for _,v in data_pairs) or 1; start=0; cx,cy,r=65,65,55
        for i,(lab,val) in enumerate(data_pairs):
            extent=360*val/total; c_col=colors[i%len(colors)]
            cv.create_arc(cx-r,cy-r,cx+r,cy+r,start=start,extent=extent,fill=c_col,outline=C["bg"])
            cv.create_rectangle(135,10+i*18,148,22+i*18,fill=c_col,outline="")
            pct=f"{100*val//total}%"
            cv.create_text(150,16+i*18,text=pct,fill=C["text_mid"],font=("Consolas",7),anchor="w")
            cv.create_text(133,16+i*18,text=lab[:7],fill=C["text_dim"],font=("Consolas",6),anchor="e")
            start+=extent

    def refresh(self):
        def task():
            d=get_all_events(); self._data=d; self._render(d)
            self._status.config(text=f"Atualizado: {now_str()}  |  {len(d)} veículos")
        threading.Thread(target=task,daemon=True).start()

    def _render(self,data):
        for w in self.sf.winfo_children(): w.destroy()
        if not data: return
        on=sum(1 for e in data if safe_int(e.get("ras_eve_ignicao"))); off=len(data)-on
        no_gps=sum(1 for e in data if not safe_int(e.get("ras_eve_gps_status")))
        vel_list=[abs(safe_int(e.get("ras_eve_velocidade",0))) for e in data]
        speeding=sum(1 for v in vel_list if v>80); vmax=max(vel_list) if vel_list else 0
        vmed=sum(vel_list)/len(vel_list) if vel_list else 0
        bats=[safe_int(e.get("ras_eve_porc_bat_backup",100)) for e in data]
        low_bat=sum(1 for b in bats if b<30); avg_bat=sum(bats)/len(bats) if bats else 0
        volts=[safe_float(e.get("ras_eve_voltagem",0)) for e in data if safe_float(e.get("ras_eve_voltagem",0))>0]
        avg_volt=sum(volts)/len(volts) if volts else 0
        moving=sum(1 for e in data if safe_int(e.get("ras_eve_velocidade",0))>0)
        counts_f=[sum(1 for v in vel_list if v==0),sum(1 for v in vel_list if 1<=v<=30),
                  sum(1 for v in vel_list if 31<=v<=60),sum(1 for v in vel_list if 61<=v<=80),
                  sum(1 for v in vel_list if 81<=v<=100),sum(1 for v in vel_list if v>100)]

        self._sec("📊  KPIs PRINCIPAIS")
        row1=tk.Frame(self.sf,bg=C["bg"]); row1.pack(fill="x",padx=6)
        self._card(row1,"FROTA TOTAL",str(len(data)),"veículos monitorados",C["blue"])
        self._card(row1,"IGN. ON",str(on),f"{100*on//max(len(data),1)}% da frota",C["green"])
        self._card(row1,"IGN. OFF",str(off),f"{100*off//max(len(data),1)}% da frota",C["text_mid"])
        self._card(row1,"EM MOVIMENTO",str(moving),"com velocidade > 0",C["accent"])
        self._card(row1,"SEM GPS",str(no_gps),"sinal perdido/falha",C["danger"])
        self._card(row1,"EXCESSO VEL.",str(speeding),"acima de 80 km/h",C["warn"])

        self._sec("🚀  VELOCIDADE")
        row2=tk.Frame(self.sf,bg=C["bg"]); row2.pack(fill="x",padx=6)
        self._card(row2,"VEL. MÁXIMA",f"{vmax}","km/h registrado agora",C["danger"])
        self._card(row2,"VEL. MÉDIA",f"{vmed:.1f}","km/h média da frota",C["warn"])
        self._card(row2,"ACIMA 60",str(sum(1 for v in vel_list if v>60)),"veículos",C["orange"])
        self._card(row2,"ACIMA 80",str(speeding),"veículos em excesso",C["danger"])
        self._card(row2,"ACIMA 100",str(sum(1 for v in vel_list if v>100)),"crítico","#FF0000")
        self._bar_chart(self.sf,"📊 Distribuição de Velocidade (km/h)",
                        list(zip(["0","1-30","31-60","61-80","81-100",">100"],counts_f)),C["accent"])

        self._sec("🔋  SAÚDE DA FROTA")
        row3=tk.Frame(self.sf,bg=C["bg"]); row3.pack(fill="x",padx=6)
        self._card(row3,"BAT. MÉDIA",f"{avg_bat:.0f}%","bateria backup",C["green"] if avg_bat>50 else C["warn"])
        self._card(row3,"BAT. BAIXA (<30%)",str(low_bat),"veículos críticos",C["danger"])
        self._card(row3,"VOLT. MÉDIA",f"{avg_volt:.1f}V","tensão elétrica",C["blue"])
        sat_vals=[safe_int(e.get("ras_eve_satelites",0)) for e in data]
        avg_sat=sum(sat_vals)/len(sat_vals) if sat_vals else 0
        self._card(row3,"SATÉLITES MÉD.",f"{avg_sat:.1f}","satélites por veículo",C["accent"])
        gps_ok=len(data)-no_gps
        self._card(row3,"GPS OK",str(gps_ok),f"{100*gps_ok//max(len(data),1)}% da frota",C["green"])

        self._sec("🥧  Distribuição Visual")
        row_pie=tk.Frame(self.sf,bg=C["bg"]); row_pie.pack(fill="x",padx=10,pady=4)
        self._pie_canvas(row_pie,"Ignição",[("ON",on),("OFF",off)],[C["green"],C["surface3"]])
        self._pie_canvas(row_pie,"GPS Status",[("OK",gps_ok),("Falha",no_gps)],[C["accent"],C["danger"]])
        self._pie_canvas(row_pie,"Velocidade",[("Parado",counts_f[0]),("Normal",counts_f[1]+counts_f[2]),
                          ("Atento",counts_f[3]),("Excesso",counts_f[4]+counts_f[5])],
                         [C["text_mid"],C["green"],C["warn"],C["danger"]])

        self._sec("🏎  TOP 10 MAIS RÁPIDOS AGORA")
        top10=sorted(data,key=lambda e:abs(safe_int(e.get("ras_eve_velocidade",0))),reverse=True)[:10]
        ft=FilterableTree(self.sf,("Pos.","Placa","Veículo","Motorista","Velocidade","Ignição","GPS","Data"),
                          (40,90,130,130,100,80,60,150),"Top10",C["warn"],10)
        for i,e in enumerate(top10,1):
            v=abs(safe_int(e.get("ras_eve_velocidade",0)))
            medals=["🥇","🥈","🥉"]
            ft.tree.insert("","end",values=(medals[i-1] if i<=3 else f"#{i}",
                safe_str(e.get("ras_vei_placa")),safe_str(e.get("ras_vei_veiculo")),
                safe_str(e.get("ras_mot_nome")),f"{v} km/h",
                "🟢 ON" if safe_int(e.get("ras_eve_ignicao")) else "⚫ OFF",
                "✓" if safe_int(e.get("ras_eve_gps_status")) else "✗",
                safe_str(e.get("ras_eve_data_gps"))),tags=("al" if v>80 else "ok",))
        ft.tag_configure("al",background="#1a0808"); ft.tag_configure("ok",background=C["surface2"])

        self._sec("👥  FROTA POR CLIENTE")
        cli_count=Counter(safe_str(e.get("ras_cli_desc","Desconhecido")) for e in data)
        self._bar_chart(self.sf,"Veículos por Cliente (Top 15)",cli_count.most_common(15),C["purple"])

        self._sec("📡  QUALIDADE DE SINAL GPS")
        sat_ranges=[("0 sat",sum(1 for e in data if safe_int(e.get("ras_eve_satelites",0))==0)),
                    ("1-3",  sum(1 for e in data if 1<=safe_int(e.get("ras_eve_satelites",0))<=3)),
                    ("4-6",  sum(1 for e in data if 4<=safe_int(e.get("ras_eve_satelites",0))<=6)),
                    ("7-9",  sum(1 for e in data if 7<=safe_int(e.get("ras_eve_satelites",0))<=9)),
                    ("10+",  sum(1 for e in data if safe_int(e.get("ras_eve_satelites",0))>=10))]
        self._bar_chart(self.sf,"Distribuição de Satélites",sat_ranges,C["accent"])

    def _export_report(self):
        if not self._data: messagebox.showinfo("KPIs","Carregue os dados primeiro."); return
        data=self._data
        on=sum(1 for e in data if safe_int(e.get("ras_eve_ignicao"))); off=len(data)-on
        no_gps=sum(1 for e in data if not safe_int(e.get("ras_eve_gps_status")))
        vel_list=[abs(safe_int(e.get("ras_eve_velocidade",0))) for e in data]
        speeding=sum(1 for v in vel_list if v>80)
        vmax=max(vel_list) if vel_list else 0; vmed=sum(vel_list)/len(vel_list) if vel_list else 0
        bats=[safe_int(e.get("ras_eve_porc_bat_backup",100)) for e in data]
        avg_bat=sum(bats)/len(bats) if bats else 0
        lines=["="*60,"  RELATÓRIO EXECUTIVO DE FROTA — IFControll v3.0",
            f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}","="*60,"",
            "  ─── SUMÁRIO EXECUTIVO ─────────────────────────────",
            f"    Veículos monitorados  : {len(data)}",
            f"    Ignição ON            : {on} ({100*on//max(len(data),1)}%)",
            f"    Ignição OFF           : {off} ({100*off//max(len(data),1)}%)",
            f"    Sem GPS               : {no_gps} ({100*no_gps//max(len(data),1)}%)","",
            "  ─── VELOCIDADE ─────────────────────────────────────",
            f"    Velocidade máxima     : {vmax} km/h",
            f"    Velocidade média      : {vmed:.1f} km/h",
            f"    Em excesso (>80 km/h) : {speeding} veículos","",
            "  ─── SAÚDE DA FROTA ──────────────────────────────────",
            f"    Bateria média backup  : {avg_bat:.0f}%",
            f"    Veículos bat < 30%    : {sum(1 for b in bats if b<30)}","",
            "  ─── TOP 10 MAIS RÁPIDOS ─────────────────────────────"]
        top10=sorted(data,key=lambda e:abs(safe_int(e.get("ras_eve_velocidade",0))),reverse=True)[:10]
        for i,e in enumerate(top10,1):
            lines.append(f"    {i:>2}. {safe_str(e.get('ras_vei_placa')):<10} {abs(safe_int(e.get('ras_eve_velocidade',0))):>4} km/h  {safe_str(e.get('ras_mot_nome'))}")
        lines+=["","="*60]
        path=filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("Texto","*.txt"),("Todos","*.*")],
            initialfile=f"relatorio_executivo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        if not path: return
        with open(path,"w",encoding="utf-8") as f: f.write("\n".join(lines))
        messagebox.showinfo("Relatório",f"Salvo:\n{path}")