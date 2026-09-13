"""
tabs/comunicacao.py
Aba 13 — Comunicação & Disponibilidade: Janelas de Silêncio,
          Status da Frota (snapshot) e Uptime por Veículo.
"""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from utils.theme_manager import C, register_theme_listener
from utils.auto_refresh_export import now_str, ts, parse_dt
from core import (
    get_all_events, find_vehicle, extract_list, api_get,
    safe_int, safe_float, safe_str,
)
from widgets.alert_colors import _ac
from widgets import (
    lbl, ent, btn, txtbox, write, loading, ok, err,
    mk_export_btn, interval_row, FilterableTree,
)
from core.models import hms


class TabComunicacao(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=C["bg"])
        self._build()

    def _build(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._tab_silencio(nb)
        self._tab_status_frota(nb)
        self._tab_uptime(nb)

    # ── Janelas de Silêncio ───────────────────────────────────────────────────
    def _tab_silencio(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  📡 Janelas de Silêncio  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Veículo:",9,col=C["text_mid"]).pack(side="left")
        e_v=ent(c,w=18); e_v.pack(side="left",padx=4,ipady=4)
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        fr_int=tk.Frame(f,bg=C["bg"]); fr_int.pack(fill="x",padx=8); ei,ef=interval_row(fr_int)
        lbl(f,"Gap mínimo para silêncio (min):",9,col=C["text_mid"]).pack(anchor="w",padx=8)
        e_mn=ent(f,w=5); e_mn.pack(anchor="w",padx=8,ipady=4); e_mn.insert(0,"10")
        _,res=txtbox(f,16); _.pack(fill="both",expand=True,padx=8,pady=4)

        def silencio():
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
                    mn=int(e_mn.get() or 10)
                except: write(res,"⚠",C["warn"]); return
                evs=extract_list(api_get(f"/events/interval/id/{vid}/begin/{ts(ini)}/end/{ts(fim)}").get("data",[]))
                if not evs: write(res,"ℹ Sem eventos.",C["text_mid"]); return
                gaps=[]; prev_dt=None; tot_gap=0.0
                for ev in evs:
                    dt=parse_dt(safe_str(ev.get("ras_eve_data_enviado") or ev.get("ras_eve_data_gps")))
                    if dt is None: continue
                    if prev_dt:
                        g=(dt-prev_dt).total_seconds()/60
                        if g>=mn: gaps.append((prev_dt,dt,g)); tot_gap+=g
                    prev_dt=dt
                periodo_min=(fim-ini).total_seconds()/60 or 1
                disponib=max(0,100-tot_gap*100/periodo_min)
                lines=[f"  {entry.get('ras_vei_placa','—')}  |  {ini.strftime('%d/%m %H:%M')} → {fim.strftime('%d/%m %H:%M')}",
                    f"  Eventos transmitidos : {len(evs)}",
                    f"  Janelas de silêncio ≥{mn}min: {len(gaps)}",
                    f"  Tempo total sem sinal: {tot_gap:.0f} min  ({tot_gap/60:.1f} h)",
                    f"  Disponibilidade comun.: {disponib:.1f}%","",
                    "  ─── Gaps Detectados ──────────────────────",
                    f"  {'#':>3}  {'Último sinal':<22}  {'Retorno':<22}  {'Duração':>8}","  "+"─"*62]
                for i,(a,b,g) in enumerate(gaps,1):
                    sev="🔴" if g>60 else "🟡" if g>30 else "🟠"
                    lines.append(f"  {i:>3}  {a.strftime('%d/%m %H:%M:%S'):<22}  {b.strftime('%d/%m %H:%M:%S'):<22}  {sev} {g:.0f} min")
                col=C["success"] if disponib>95 else C["warn"] if disponib>80 else C["danger"]
                write(res,"\n".join(lines),col)
            threading.Thread(target=task,daemon=True).start()

        btn(c,"📡 ANALISAR",silencio,C["accent"]).pack(side="left",padx=8)
        mk_export_btn(c,res,is_text=True).pack(side="left",padx=4)

    # ── Status da Frota ───────────────────────────────────────────────────────
    def _tab_status_frota(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  📊 Status da Frota  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Atraso máximo aceito:",9,col=C["text_mid"]).pack(side="left")
        e_v=ent(c,w=5); e_v.pack(side="left",padx=4,ipady=4); e_v.insert(0,"30")
        lbl(c,"min",8,col=C["text_dim"]).pack(side="left")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        ft=FilterableTree(f,("Placa","Veículo","Motorista","Última.Comun.","Atraso","Status.Comun.","GPS","Ign."),
                          (90,130,130,160,100,130,60,60),"ComSt",C["accent"],16)
        self._ft_status = ft
        def _tags_status():
            ft.tag_configure("ok",  background=C["surface2"])
            ft.tag_configure("warn",background=_ac("warn"))
            ft.tag_configure("crit",background=_ac("crit"))
        _tags_status(); register_theme_listener(_tags_status)

        def status_frota():
            try: max_min=int(e_v.get())
            except: max_min=30
            lb.config(text="⏳...")
            def task():
                data=get_all_events(); now=datetime.now(); rows=[]
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
                    ign=safe_int(ev.get("ras_eve_ignicao",0)); gps=safe_int(ev.get("ras_eve_gps_status",0))
                    rows.append(((safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                                  safe_str(ev.get("ras_mot_nome")),d_env,atr,st,
                                  "✓ OK" if gps else "✗ FALHA","🟢 ON" if ign else "⚫ OFF"),tag))
                rows.sort(key=lambda x:(0 if x[1]=="crit" else 1 if x[1]=="warn" else 2))
                ft.load(rows)
                ok_c=sum(1 for _,t in rows if t=="ok")
                lb.config(text=f"✅ OK: {ok_c}  |  ⚠: {sum(1 for _,t in rows if t=='warn')}  |  🔴: {sum(1 for _,t in rows if t=='crit')}  |  {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"⟳ VERIFICAR",status_frota,C["accent"]).pack(side="left",padx=8)
        mk_export_btn(c,ft.tree).pack(side="left",padx=4)
        self.after(300,status_frota)

    # ── Uptime por Veículo ────────────────────────────────────────────────────
    def _tab_uptime(self, nb):
        f = tk.Frame(nb, bg=C["bg"]); nb.add(f, text="  ⏱ Uptime / Disponibilidade  ")
        c = tk.Frame(f, bg=C["bg"]); c.pack(fill="x", padx=8, pady=6)
        lbl(c,"Intervalo máx entre eventos (min):",9,col=C["text_mid"]).pack(side="left")
        e_int=ent(c,w=5); e_int.pack(side="left",padx=4,ipady=4); e_int.insert(0,"15")
        lb=lbl(c,"",col=C["text_dim"]); lb.pack(side="right")
        fr_int=tk.Frame(f,bg=C["bg"]); fr_int.pack(fill="x",padx=8); ei,ef=interval_row(fr_int)
        ft=FilterableTree(f,("Placa","Veículo","Eventos","Uptime%","Tempo.Online","Janelas.Silêncio","Maior.Gap"),
                          (90,130,70,80,120,130,110),"Uptime",C["green"],14)
        self._ft_uptime = ft
        def _tags_uptime():
            ft.tag_configure("ok",  background=C["surface2"])
            ft.tag_configure("warn",background=_ac("warn"))
            ft.tag_configure("crit",background=_ac("crit"))
        _tags_uptime(); register_theme_listener(_tags_uptime)

        def uptime_all():
            try:
                max_gap=int(e_int.get())*60
                ini=datetime.strptime(ei.get().strip(),"%d/%m/%Y %H:%M")
                fim=datetime.strptime(ef.get().strip(),"%d/%m/%Y %H:%M")
            except: lb.config(text="⚠ Parâmetros"); return
            lb.config(text="⏳...")
            def task():
                periodo_s=(fim-ini).total_seconds()
                data=get_all_events(); rows=[]
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
                    rows.append(((safe_str(ev.get("ras_vei_placa")),safe_str(ev.get("ras_vei_veiculo")),
                                  len(evs),f"{uptime:.1f}%",hms(t_online),len(gaps_over),f"{maior:.0f} min"),tag))
                rows.sort(key=lambda x:float(str(x[0][3]).replace("%","")))
                ft.load(rows); lb.config(text=f"{len(rows)} veículos analisados | {now_str()}")
            threading.Thread(target=task,daemon=True).start()

        btn(c,"⏱ ANALISAR TODOS",uptime_all,C["green"]).pack(side="left",padx=8)
        mk_export_btn(c,ft.tree).pack(side="left",padx=4)