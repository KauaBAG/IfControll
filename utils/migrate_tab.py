"""
utils/migrate_tab.py
Script auxiliar de desenvolvimento:
Orienta como migrar cada Tab do main.py legado para o módulo correto.

USO:
    python utils/migrate_tab.py

Não executa nada — apenas imprime o checklist de migração.
"""

TABS = [
    ("TabRelatorios",   "tabs/relatorios.py"),
    ("TabClientes",     "tabs/clientes.py"),
    ("TabRastreadores", "tabs/rastreadores.py"),
    ("TabComandos",     "tabs/comandos.py"),
    ("TabDiagnostico",  "tabs/diagnostico.py"),
    ("TabKPIs",         "tabs/kpis.py"),
    ("TabComportamento","tabs/comportamento.py"),
    ("TabCustos",       "tabs/custos.py"),
    ("TabComunicacao",  "tabs/comunicacao.py"),
]

IMPORTS_PADRAO = """\
import threading
import tkinter as tk
from tkinter import ttk
from theme_manager import C
from auto_refresh_export import now_str, ts
from core import (
    get_all_events, find_vehicle, extract_list,
    api_get, api_post, api_put, api_del,
    safe_int, safe_float, safe_str, haversine, hms,
)
from widgets import (
    lbl, ent, btn, sec, txtbox, write, loading, ok, err,
    mk_tree, mk_export_btn, interval_row,
    FilterableTree, mk_ftree,
)
"""

CHECKLIST = """\
CHECKLIST DE MIGRAÇÃO — IFControll v3.0
========================================

Para cada Tab listada abaixo:

1. Abra main.py (legado) e localize a classe.
2. Cole o corpo completo no arquivo de destino indicado.
3. Substitua os imports globais pelos imports padronizados abaixo.
4. Verifique que não há referência direta a variáveis globais de main.py.
5. Teste isolado:
       python -c "from tabs.<modulo> import Tab<Nome>; print('OK')"
6. Marque ✓ no checklist.

IMPORTS PADRÃO (cole no topo de cada arquivo):
{imports}

TABS PENDENTES:
{tabs}

ARQUIVOS JÁ PRONTOS:
  ✓ core/models.py        — safe_int, safe_float, safe_str, haversine, hms
  ✓ core/api.py           — _req, api_get/post/put/del, extract_list, endpoints
  ✓ widgets/primitives.py — lbl, ent, btn, sec, txtbox, write, loading, ok, err
  ✓ widgets/tree.py       — apply_tree_style, mk_tree, export_tree, attach_copy
  ✓ widgets/filterable_tree.py — FilterableTree, mk_ftree
  ✓ widgets/helpers.py    — interval_row, mk_export_btn
  ✓ tabs/dashboard.py     — TabDashboard
  ✓ tabs/alertas.py       — TabAlertas
  ✓ tabs/cercas.py        — TabCercas
  ✓ tabs/veiculos.py      — TabVeiculos
  ✓ main.py               — Entrada limpa (build_window/header/notebook/footer)
"""

if __name__ == "__main__":
    tab_lines = "\n".join(f"  [ ] {cls:20s} → {dest}" for cls, dest in TABS)
    print(CHECKLIST.format(imports=IMPORTS_PADRAO, tabs=tab_lines))