<?php
/**
 * cronologia_api.php — IFControll v3.0
 * API REST para Cronologia de Manutenções de Veículos
 *
 * INSTALAÇÃO NO CPANEL:
 * 1. Crie o arquivo MySQL via phpMyAdmin (SQL abaixo)
 * 2. Edite as constantes DB_* com suas credenciais
 * 3. Faça upload deste arquivo para public_html/ifcontroll/api.php
 * 4. Acesse: https://seudominio.com/ifcontroll/api.php
 *
 * ─── SQL PARA CRIAR BANCO ────────────────────────────────────────────────────
 * CREATE DATABASE ifcontroll_cronologia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
 * USE ifcontroll_cronologia;
 *
 * CREATE TABLE manutencoes (
 *   id           INT AUTO_INCREMENT PRIMARY KEY,
 *   placa        VARCHAR(20) NOT NULL,
 *   situacao     VARCHAR(100) NOT NULL,
 *   data_cadastro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 *   quem_informou VARCHAR(120),
 *   onde_esta    VARCHAR(200),
 *   status_texto TEXT,
 *   previsao     DATETIME,
 *   data_conclusao DATETIME,
 *   concluido    TINYINT(1) NOT NULL DEFAULT 0,
 *   created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 *   updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 *   INDEX idx_placa (placa),
 *   INDEX idx_concluido (concluido)
 * ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
 *
 * CREATE TABLE status_updates (
 *   id             INT AUTO_INCREMENT PRIMARY KEY,
 *   manutencao_id  INT NOT NULL,
 *   texto          TEXT NOT NULL,
 *   autor          VARCHAR(120),
 *   created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 *   FOREIGN KEY (manutencao_id) REFERENCES manutencoes(id) ON DELETE CASCADE,
 *   INDEX idx_man_id (manutencao_id)
 * ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ── Configuração do banco de dados ──────────────────────────────────────────
define('DB_HOST', 'localhost');
define('DB_NAME', 'ifcontroll_cronologia');   // nome do banco criado
define('DB_USER', 'usuario_cpanel');           // usuário MySQL do cPanel
define('DB_PASS', 'senha_aqui');               // senha MySQL

// ── Chave de API simples para autenticação básica ───────────────────────────
define('API_SECRET', 'ifcontroll_secret_2025'); // mude para algo seguro

// ── CORS & Headers ───────────────────────────────────────────────────────────
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// ── Autenticação ─────────────────────────────────────────────────────────────
$headers = getallheaders();
$api_key = $headers['X-Api-Key'] ?? $headers['X-API-Key'] ?? ($_GET['api_key'] ?? '');
if ($api_key !== API_SECRET) {
    respond(401, false, 'Chave de API inválida');
}

// ── Conexão PDO ──────────────────────────────────────────────────────────────
try {
    $pdo = new PDO(
        'mysql:host='.DB_HOST.';dbname='.DB_NAME.';charset=utf8mb4',
        DB_USER, DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
         PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
    );
} catch (Exception $e) {
    respond(500, false, 'Erro de conexão: ' . $e->getMessage());
}

// ── Roteamento ───────────────────────────────────────────────────────────────
$method = $_SERVER['REQUEST_METHOD'];
$path   = trim(parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH), '/');
$parts  = explode('/', $path);

// Remove prefixo "ifcontroll" se existir
if (isset($parts[0]) && $parts[0] === 'ifcontroll') {
    array_shift($parts);
}
// Remove "api.php" do início se presente
if (isset($parts[0]) && strpos($parts[0], 'api.php') !== false) {
    array_shift($parts);
}

$resource = $parts[0] ?? '';
$id       = isset($parts[1]) ? (int)$parts[1] : null;

$body = json_decode(file_get_contents('php://input'), true) ?? [];

switch ($resource) {

    // ── GET /manutencoes?placa=ABC1234 ──────────────────────────
    // ── GET /manutencoes — lista todas ─────────────────────────
    // ── GET /manutencoes/{id} — uma específica ──────────────────
    case 'manutencoes':
        if ($method === 'GET') {
            if ($id) {
                // Busca uma + seus status_updates
                $stmt = $pdo->prepare('SELECT * FROM manutencoes WHERE id = ?');
                $stmt->execute([$id]);
                $man = $stmt->fetch();
                if (!$man) respond(404, false, 'Não encontrado');
                $stmt2 = $pdo->prepare(
                    'SELECT * FROM status_updates WHERE manutencao_id = ? ORDER BY created_at ASC');
                $stmt2->execute([$id]);
                $man['atualizacoes'] = $stmt2->fetchAll();
                respond(200, true, 'OK', $man);
            }

            $placa = strtoupper(trim($_GET['placa'] ?? ''));
            $concluido = $_GET['concluido'] ?? null;
            $limit = min(500, (int)($_GET['limit'] ?? 100));
            $offset = (int)($_GET['offset'] ?? 0);

            $where = []; $params = [];
            if ($placa) { $where[] = 'placa LIKE ?'; $params[] = "%$placa%"; }
            if ($concluido !== null) { $where[] = 'concluido = ?'; $params[] = (int)$concluido; }

            $sql = 'SELECT * FROM manutencoes';
            if ($where) $sql .= ' WHERE ' . implode(' AND ', $where);
            $sql .= ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
            $params[] = $limit; $params[] = $offset;

            $stmt = $pdo->prepare($sql);
            $stmt->execute($params);
            $rows = $stmt->fetchAll();

            // Conta total
            $sql_count = 'SELECT COUNT(*) FROM manutencoes';
            if ($where) $sql_count .= ' WHERE ' . implode(' AND ', array_slice($where, 0));
            $stmt_c = $pdo->prepare($sql_count);
            $stmt_c->execute(array_slice($params, 0, count($params) - 2));
            $total = (int)$stmt_c->fetchColumn();

            respond(200, true, 'OK', $rows, ['total' => $total, 'limit' => $limit, 'offset' => $offset]);
        }

        // ── POST /manutencoes — criar ────────────────────────────
        if ($method === 'POST') {
            $required = ['placa', 'situacao'];
            foreach ($required as $f) {
                if (empty($body[$f])) respond(400, false, "Campo obrigatório: $f");
            }
            $stmt = $pdo->prepare(
                'INSERT INTO manutencoes (placa, situacao, data_cadastro, quem_informou,
                 onde_esta, status_texto, previsao, data_conclusao, concluido)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
            $stmt->execute([
                strtoupper(trim($body['placa'])),
                trim($body['situacao']),
                $body['data_cadastro'] ?? date('Y-m-d H:i:s'),
                $body['quem_informou'] ?? null,
                $body['onde_esta'] ?? null,
                $body['status_texto'] ?? null,
                $body['previsao'] ?? null,
                $body['data_conclusao'] ?? null,
                isset($body['concluido']) ? (int)$body['concluido'] : 0,
            ]);
            $new_id = $pdo->lastInsertId();

            // Status inicial automático
            if (!empty($body['status_texto'])) {
                $pdo->prepare('INSERT INTO status_updates (manutencao_id, texto, autor) VALUES (?,?,?)')
                    ->execute([$new_id, $body['status_texto'], $body['quem_informou'] ?? 'Sistema']);
            }

            $stmt2 = $pdo->prepare('SELECT * FROM manutencoes WHERE id = ?');
            $stmt2->execute([$new_id]);
            respond(201, true, 'Manutenção criada', $stmt2->fetch());
        }

        // ── PUT /manutencoes/{id} — atualizar ───────────────────
        if ($method === 'PUT' && $id) {
            $stmt = $pdo->prepare('SELECT id FROM manutencoes WHERE id = ?');
            $stmt->execute([$id]);
            if (!$stmt->fetch()) respond(404, false, 'Não encontrado');

            $fields = [];  $params = [];
            $allowed = ['placa','situacao','quem_informou','onde_esta',
                        'status_texto','previsao','data_conclusao','concluido'];
            foreach ($allowed as $f) {
                if (array_key_exists($f, $body)) {
                    $fields[] = "$f = ?";
                    $params[] = $f === 'placa' ? strtoupper(trim($body[$f])) : $body[$f];
                }
            }
            if (empty($fields)) respond(400, false, 'Nenhum campo para atualizar');

            $params[] = $id;
            $pdo->prepare('UPDATE manutencoes SET '.implode(', ', $fields).' WHERE id = ?')
                ->execute($params);

            // Adiciona entrada no histórico de status se veio texto novo
            if (!empty($body['novo_status'])) {
                $pdo->prepare('INSERT INTO status_updates (manutencao_id, texto, autor) VALUES (?,?,?)')
                    ->execute([$id, $body['novo_status'], $body['quem_informou'] ?? 'Sistema']);
            }

            $stmt2 = $pdo->prepare('SELECT * FROM manutencoes WHERE id = ?');
            $stmt2->execute([$id]);
            respond(200, true, 'Atualizado', $stmt2->fetch());
        }

        // ── DELETE /manutencoes/{id} ─────────────────────────────
        if ($method === 'DELETE' && $id) {
            $stmt = $pdo->prepare('SELECT id FROM manutencoes WHERE id = ?');
            $stmt->execute([$id]);
            if (!$stmt->fetch()) respond(404, false, 'Não encontrado');
            $pdo->prepare('DELETE FROM manutencoes WHERE id = ?')->execute([$id]);
            respond(200, true, 'Deletado com sucesso');
        }

        respond(405, false, 'Método não permitido');
        break;

    // ── POST /status_update/{manutencao_id} — nova atualização ──
    case 'status_update':
        if ($method === 'POST' && $id) {
            if (empty($body['texto'])) respond(400, false, 'Campo obrigatório: texto');
            $stmt = $pdo->prepare('SELECT id FROM manutencoes WHERE id = ?');
            $stmt->execute([$id]);
            if (!$stmt->fetch()) respond(404, false, 'Manutenção não encontrada');

            $pdo->prepare('INSERT INTO status_updates (manutencao_id, texto, autor) VALUES (?,?,?)')
                ->execute([$id, $body['texto'], $body['autor'] ?? 'Sistema']);

            $new_id = $pdo->lastInsertId();
            respond(201, true, 'Status adicionado', ['id' => $new_id]);
        }
        respond(405, false, 'Método não permitido');
        break;

    // ── GET /placas — lista placas únicas com manutenções ───────
    case 'placas':
        if ($method === 'GET') {
            $stmt = $pdo->query(
                'SELECT DISTINCT placa, COUNT(*) as total,
                 SUM(concluido) as concluidas,
                 MAX(created_at) as ultima_atualizacao
                 FROM manutencoes GROUP BY placa ORDER BY ultima_atualizacao DESC LIMIT 500');
            respond(200, true, 'OK', $stmt->fetchAll());
        }
        respond(405, false, 'Método não permitido');
        break;

    // ── GET /ping — teste de conectividade ───────────────────────
    case 'ping':
        respond(200, true, 'pong', ['timestamp' => date('Y-m-d H:i:s'), 'version' => '3.0']);
        break;

    default:
        respond(404, false, "Rota desconhecida: /$resource");
}

// ── Helper de resposta ───────────────────────────────────────────────────────
function respond(int $code, bool $status, string $message, $data = null, array $meta = []) {
    http_response_code($code);
    $resp = ['status' => $status, 'message' => $message, 'data' => $data];
    if ($meta) $resp['meta'] = $meta;
    echo json_encode($resp, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    exit;
}
