# IFControll v3.0 — Fleet Intelligence Platform
## Worktree Modular

```
ifcontroll/
│
├── icon.ico                    ← Icone do programa
|
├── main.py                     ← Ponto de entrada (janela, header, notebook)
│
├── core/                       ← Núcleo da aplicação
│   ├── __init__.py
│   ├── api.py                  ← Camada HTTP / endpoints Fulltrack2
│   ├── models.py               ← Helpers de tipo (safe_int, safe_float, haversine, hms)
|   ├── credencials.py          ← Credenciais do programa (ApiKeys, Urls, Ports, Tokens)
│   └── config.py               ← Constantes, credenciais (re-exporta credencials.py)
│
├── widgets/                    ← Componentes de UI reutilizáveis
│   ├── __init__.py
│   ├── primitives.py           ← lbl, ent, btn, sec, txtbox, write, loading, err, ok
│   ├── tree.py                 ← mk_tree, apply_tree_style, export_tree, export_text, attach_copy
│   ├── filterable_tree.py      ← FilterableTree, mk_ftree
|   ├── alert_colors.py         ← _ac, DARK, LIGHT
│   └── helpers.py              ← interval_row, mk_export_btn (versão local)
│
├── tabs/                       ← Uma classe por aba
│   ├── __init__.py
│   ├── dashboard.py            ← TabDashboard
│   ├── alertas.py              ← TabAlertas
│   ├── cercas.py               ← TabCercas
│   ├── veiculos.py             ← TabVeiculos
│   ├── relatorios.py           ← TabRelatorios
│   ├── clientes.py             ← TabClientes
│   ├── rastreadores.py         ← TabRastreadores
│   ├── comandos.py             ← TabComandos
│   ├── diagnostico.py          ← TabDiagnostico
│   ├── kpis.py                 ← TabKPIs
│   ├── comportamento.py        ← TabComportamento
│   ├── custos.py               ← TabCustos
│   ├── comunicacao.py          ← TabComunicacao
|   ├── comandos.py             ← TabComandos
|   └── cronologia.py           ← TabCronologia
│
└── utils/                      ← Utilitários independentes
    ├── __init__.py
    ├── auto_refresh_export.py  ← Gerenciador de refresh automatico e exportação (PDF, CSV, TXT)
    ├── migrate_tab.py          ← Gerenciador de migração de janelas   
    ├── theme_manager.py        ← Gerenciador de troca de temas
    └── clipboard.py            ← bind_global_copy, attach_copy (bridge)
```

