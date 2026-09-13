"""
_constants.py — Constantes globais do módulo Cronologia.
"""

# ─── Situações padrão ────────────────────────────────────────────────────────
SITUACOES_PADRAO = [
    "Visita Técnica",
    "Oficina",
    "Garagem",
    "Sinistro",
    "GPS",
    "Instalação",
    "Outros",
]

# ─── Colunas da árvore principal ─────────────────────────────────────────────
TREE_COLS = (
    "ID", "Placa", "Rastreador", "Situação", "Data Cadastro", "Criado Por",
    "Quem Informou", "Onde Está", "Status Atual",
    "Categoria", "Técnico", "Custo", "Previsão", "Conclusão", "✔",
)
TREE_WIDTHS = (50, 80, 100, 160, 130, 120, 120, 140, 200, 110, 100, 80, 110, 110, 40)

# ─── Colunas do CSV de exportação ────────────────────────────────────────────
CSV_COLS = [
    "id", "placa", "rastreador_id", "situacao", "data_cadastro", "criado_por",
    "quem_informou", "onde_esta", "status_atual", "categoria",
    "prioridade", "custo", "previsao", "data_conclusao",
    "concluido", "observacoes",
]
