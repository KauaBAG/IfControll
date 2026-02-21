"""
debug_cronologia.py — Script de diagnóstico standalone

Execute diretamente:
    python debug_cronologia.py

Não depende de nenhum módulo do IFControll.
Testa cada endpoint da API e imprime o resultado detalhado.
"""

import requests
import json
import sys
from datetime import datetime

# ─── CONFIGURAÇÃO — ajuste se necessário ────────────────────────────────────
CRON_API_URL         = "https://infosousa.com.br/api/api_cronologia.php"
CRON_API_KEY         = "ifcontroll_token_2025_seguro"
TOKEN_HEADER_NAME    = "X-API-Token"   # nome exato do header enviado pelo Python
DEBUG_API_URL        = "https://infosousa.com.br/api/debug_cronologia_api.php"

SEPARADOR = "─" * 70

def h(titulo):
    print(f"\n{SEPARADOR}")
    print(f"  {titulo}")
    print(SEPARADOR)

def ok(msg):   print(f"  ✔  {msg}")
def err(msg):  print(f"  ✖  {msg}")
def info(msg): print(f"  ℹ  {msg}")
def dump(obj, indent=4):
    print(json.dumps(obj, indent=indent, ensure_ascii=False, default=str))


def headers():
    return {
        "Content-Type": "application/json",
        TOKEN_HEADER_NAME: CRON_API_KEY,
    }


def req(method, path, params=None, body=None, timeout=15, use_auth=True):
    """Faz requisição e retorna (resp_dict, status_code, raw_text)."""
    q = {"path": path}
    if params:
        q.update(params)
    try:
        r = requests.request(
            method=method.upper(),
            url=CRON_API_URL,
            headers=headers() if use_auth else {"Content-Type": "application/json"},
            params=q,
            json=body,
            timeout=timeout,
        )
        try:
            data = r.json()
        except Exception:
            data = None
        return data, r.status_code, r.text
    except Exception as e:
        return None, 0, str(e)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 0 — Script de debug PHP (se disponível)
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 0 — Script debug_cronologia_api.php (upload separado)")
try:
    r = requests.get(DEBUG_API_URL, timeout=20)
    if r.status_code == 200:
        ok(f"debug_cronologia_api.php acessível (HTTP {r.status_code})")
        try:
            d = r.json()
            dump(d)
        except Exception:
            err(f"Resposta não é JSON:\n{r.text[:2000]}")
    else:
        err(f"HTTP {r.status_code} — debug PHP não encontrado ou inacessível")
        info("Faça upload do debug_cronologia_api.php para o servidor e acesse-o primeiro.")
except Exception as e:
    err(f"Não foi possível acessar o debug PHP: {e}")


# ════════════════════════════════════════════════════════════════════════════
# TESTE 1 — Conectividade básica (ping sem auth)
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 1 — Conectividade / URL base")
try:
    r = requests.get(CRON_API_URL, params={"path": "ping"}, timeout=10)
    info(f"HTTP Status: {r.status_code}")
    info(f"Content-Type: {r.headers.get('Content-Type', '?')}")
    info(f"Corpo bruto (primeiros 500 chars):\n{r.text[:500]}")
except Exception as e:
    err(f"Sem resposta: {e}")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 2 — Autenticação (com token correto)
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 2 — Autenticação com token correto")
info(f"Header enviado: {TOKEN_HEADER_NAME}: {CRON_API_KEY}")
data, code, raw = req("GET", "ping")
info(f"HTTP {code}")
if data is None:
    err(f"Resposta não-JSON:\n{raw[:500]}")
elif data.get("status"):
    ok("Autenticação OK")
    dump(data)
else:
    err(f"Autenticação FALHOU")
    dump(data)
    info("Possíveis causas:")
    info("  • Header X-API-Token não está chegando ao PHP (proxy strip headers?)")
    info("  • Token diferente entre Python e PHP")
    info("  • getallheaders() não disponível no servidor (CGI mode)")


# ════════════════════════════════════════════════════════════════════════════
# TESTE 2b — Autenticação via query string (fallback)
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 2b — Autenticação via ?api_key= (query string)")
try:
    r = requests.get(
        CRON_API_URL,
        params={"path": "ping", "api_key": CRON_API_KEY},
        timeout=10,
    )
    info(f"HTTP {r.status_code}")
    try:
        d = r.json()
        if d.get("status"):
            ok("Autenticação via query string FUNCIONA")
            info("→ O problema é que o header não está chegando. Solução: use ?api_key= OU corrija o PHP para aceitar.")
        else:
            err(f"Também falhou via query string: {d}")
    except Exception:
        err(f"Resposta não-JSON: {r.text[:300]}")
except Exception as e:
    err(str(e))


# ════════════════════════════════════════════════════════════════════════════
# TESTE 3 — Listar manutenções (sem placa = erro esperado, com placa = OK)
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 3 — GET listar (sem placa)")
data, code, raw = req("GET", "listar", params={"limit": 5, "offset": 0})
info(f"HTTP {code}")
if data is None:
    err(f"Resposta não-JSON:\n{raw[:500]}")
else:
    dump(data)

h("TESTE 3b — GET listar (com placa genérica)")
data, code, raw = req("GET", "listar", params={"placa": "A", "limit": 5, "offset": 0})
info(f"HTTP {code}")
if data is None:
    err(f"Resposta não-JSON:\n{raw[:500]}")
else:
    if data.get("status"):
        registros = (data.get("data") or {}).get("registros") or []
        total     = (data.get("data") or {}).get("total", 0)
        ok(f"Retornou {len(registros)} registros (total: {total})")
        if registros:
            info("Campos do primeiro registro:")
            dump(list(registros[0].keys()))
            info("Primeiro registro completo:")
            dump(registros[0])
    else:
        err("Falhou")
        dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 4 — GET placas
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 4 — GET placas")
data, code, raw = req("GET", "placas")
info(f"HTTP {code}")
if data is None:
    err(f"Resposta não-JSON:\n{raw[:500]}")
elif data.get("status"):
    placas = data.get("data") or []
    ok(f"{len(placas)} placas encontradas")
    for p in placas[:5]:
        info(f"  {p}")
else:
    err("Falhou")
    dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 5 — POST criar manutenção
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 5 — POST criar manutenção (registro de teste)")
payload_criar = {
    "placa":         "DEBUGPY",
    "situacao":      "TESTE DEBUG PYTHON",
    "criado_por":    "debug_cronologia.py",
    "quem_informou": "Automação",
    "onde_esta":     "Oficina Teste",
    "status_atual":  "Criado pelo script de debug",
    "observacoes":   "DELETAR - registro de diagnóstico",
    "previsao":      None,
    "data_conclusao": None,
    "concluido":     0,
    "categoria":     "Geral",
    "prioridade":    "Normal",
    "custo":         0.0,
    "data_cadastro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}
info("Payload enviado:")
dump(payload_criar)

data, code, raw = req("POST", "criar", body=payload_criar)
info(f"HTTP {code}")
if data is None:
    err(f"Resposta não-JSON:\n{raw[:500]}")
    NEW_ID = None
elif data.get("status") or code in (200, 201):
    NEW_ID = (data.get("data") or {}).get("id")
    ok(f"Criado com ID: {NEW_ID}")
    dump(data)
else:
    err("Falhou")
    dump(data)
    NEW_ID = None


# ════════════════════════════════════════════════════════════════════════════
# TESTE 6 — GET buscar por ID
# ════════════════════════════════════════════════════════════════════════════
if NEW_ID:
    h(f"TESTE 6 — GET buscar/{NEW_ID}")
    data, code, raw = req("GET", f"buscar/{NEW_ID}")
    info(f"HTTP {code}")
    if data is None:
        err(f"Resposta não-JSON:\n{raw[:500]}")
    elif data.get("status"):
        ok("Registro encontrado")
        dump(data.get("data"))
    else:
        err("Falhou")
        dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 7 — POST add_status
# ════════════════════════════════════════════════════════════════════════════
if NEW_ID:
    h(f"TESTE 7 — POST add_status/{NEW_ID}")
    payload_status = {
        "texto": f"Status de debug adicionado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "autor": "debug_cronologia.py",
    }
    info("Payload enviado:")
    dump(payload_status)

    data, code, raw = req("POST", f"add_status/{NEW_ID}", body=payload_status)
    info(f"HTTP {code}")
    if data is None:
        err(f"Resposta não-JSON:\n{raw[:500]}")
    elif data.get("status") or code in (200, 201):
        ok("Status adicionado")
        dump(data)
    else:
        err("Falhou")
        dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 8 — GET histórico
# ════════════════════════════════════════════════════════════════════════════
if NEW_ID:
    h(f"TESTE 8 — GET historico/{NEW_ID}")
    data, code, raw = req("GET", f"historico/{NEW_ID}")
    info(f"HTTP {code}")
    if data is None:
        err(f"Resposta não-JSON:\n{raw[:500]}")
    elif data.get("status"):
        historico = data.get("data") or []
        ok(f"{len(historico)} entradas no histórico")
        for entry in historico:
            info(f"  Campos disponíveis: {list(entry.keys())}")
            dump(entry)
    else:
        err("Falhou")
        dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 9 — PUT atualizar
# ════════════════════════════════════════════════════════════════════════════
if NEW_ID:
    h(f"TESTE 9 — PUT atualizar/{NEW_ID}")
    payload_atualizar = {
        "situacao":    "ATUALIZADO VIA DEBUG",
        "criado_por":  "debug_cronologia.py",
        "onde_esta":   "Oficina Debug Atualizado",
        "novo_status": "Status atualizado via PUT",
        "status_atual":"Status atualizado via PUT",
    }
    info("Payload enviado:")
    dump(payload_atualizar)

    data, code, raw = req("PUT", f"atualizar/{NEW_ID}", body=payload_atualizar)
    info(f"HTTP {code}")
    if data is None:
        err(f"Resposta não-JSON:\n{raw[:500]}")
    elif data.get("status") or code in (200, 201):
        ok("Atualizado")
        dump(data)
    else:
        err("Falhou")
        dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 10 — PUT concluir
# ════════════════════════════════════════════════════════════════════════════
if NEW_ID:
    h(f"TESTE 10 — PUT concluir/{NEW_ID}")
    payload_concluir = {
        "data_conclusao": datetime.now().strftime("%Y-%m-%d"),
        "quem_informou":  "debug_cronologia.py",
    }
    data, code, raw = req("PUT", f"concluir/{NEW_ID}", body=payload_concluir)
    info(f"HTTP {code}")
    if data is None:
        err(f"Resposta não-JSON:\n{raw[:500]}")
    elif data.get("status") or code == 200:
        ok("Concluído")
        dump(data)
    else:
        err("Falhou")
        dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 11 — DELETE deletar (limpa o registro de teste)
# ════════════════════════════════════════════════════════════════════════════
if NEW_ID:
    h(f"TESTE 11 — DELETE deletar/{NEW_ID}")
    data, code, raw = req("DELETE", f"deletar/{NEW_ID}")
    info(f"HTTP {code}")
    if data is None:
        err(f"Resposta não-JSON:\n{raw[:500]}")
    elif data.get("status") or code in (200, 204):
        ok(f"Registro #{NEW_ID} deletado (limpeza de teste)")
        dump(data)
    else:
        err("Falhou — delete o registro manualmente se necessário")
        dump(data)


# ════════════════════════════════════════════════════════════════════════════
# TESTE 12 — GET stats
# ════════════════════════════════════════════════════════════════════════════
h("TESTE 12 — GET stats (geral)")
data, code, raw = req("GET", "stats")
info(f"HTTP {code}")
if data is None:
    err(f"Resposta não-JSON:\n{raw[:500]}")
elif data.get("status"):
    ok("Stats OK")
    dump(data.get("data"))
else:
    err("Falhou")
    dump(data)


# ════════════════════════════════════════════════════════════════════════════
# RESUMO FINAL
# ════════════════════════════════════════════════════════════════════════════
h("RESUMO — Checklist de diagnóstico")
print("""
  Se TESTE 2 falhou mas TESTE 2b passou:
    → O servidor está removendo headers customizados (comum em CGI/FastCGI).
    → Solução A: adicionar ao .htaccess:
          SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1
          RewriteRule .* - [E=HTTP_X_API_TOKEN:%{HTTP:X-API-Token}]
    → Solução B: modificar o PHP para aceitar via $_GET['api_key']
    → Solução C: modificar o Python para enviar via query string.

  Se TESTE 5 (criar) falhou com erro SQL:
    → Verifique os campos retornados no debug_cronologia_api.php (TESTE 0).
    → A tabela 'manutencoes' pode ter colunas com nomes diferentes.
    → O campo 'created_at' precisa existir ou ser removido do ORDER BY.

  Se TESTE 7/8 (add_status / historico) falhou:
    → A tabela pode ser 'status_updates' (com s) em vez de 'status_update'.
    → O campo FK pode ser 'cronologia_id' em vez de 'manutencao_id'.
    → O campo de data pode ser 'created_at' em vez de 'criado_em'.

  Se TUDO passou (✔):
    → A API está funcionando. O problema é no código Python (UI/threading).
    → Verifique os imports em credencials.py e se CRON_API_URL está correto.
""")

print(f"{SEPARADOR}")
print("  Debug concluído.")
print(f"{SEPARADOR}\n")