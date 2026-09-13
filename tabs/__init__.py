from .dashboard      import TabDashboard
from .alertas        import TabAlertas
from .cercas         import TabCercas
from .veiculos       import TabVeiculos
from .relatorios     import TabRelatorios
from .clientes       import TabClientes
from .rastreadores   import TabRastreadores
from .comandos       import TabComandos
from .diagnostico    import TabDiagnostico
from .kpis           import TabKPIs
from .comportamento  import TabComportamento
from .custos         import TabCustos
from .comunicacao    import TabComunicacao
from .telemetria     import TabTelemetria
from .cronologia     import TabCronologia

# Registro da ordem de exibição no notebook principal.
# A aba TabCronologia é importada direto em main.py por ser módulo externo legado.
TAB_REGISTRY = [
    ("  📡  Dashboard  ",       TabDashboard),
    ("  🚨  Alertas  ",         TabAlertas),
    ("  🗺  Cercas  ",          TabCercas),
    ("  🚚  Veículos  ",        TabVeiculos),
    ("  📊  Relatórios  ",      TabRelatorios),
    ("  👥  Clientes  ",        TabClientes),
    ("  📡  Rastreadores  ",    TabRastreadores),
    ("  ⚡  Comandos  ",        TabComandos),
    ("  🔧  Diagnóstico  ",     TabDiagnostico),
    ("  📈  KPIs Executivos  ", TabKPIs),
    ("  🎯  Comportamento  ",   TabComportamento),
    ("  💰  Custos  ",          TabCustos),
    ("  📶  Comunicação  ",     TabComunicacao),
    ("  📡  Telemetria  ",      TabTelemetria),
    ("  🕒  Cronologia  ",      TabCronologia),
]