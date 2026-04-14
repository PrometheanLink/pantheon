<?php
/**
 * Bridge Viewer — Multi-agent chat between captain and AI agents.
 *
 * Reads log.jsonl for the chronological transcript.
 * Writes new captain messages to inbox/<recipient>.jsonl AND log.jsonl.
 * Polls for new messages every 5s via the ?action=fetch endpoint.
 * Supports image uploads — photos saved to shared/images/ and embedded in messages.
 *
 * CONFIGURATION: Edit the $BRIDGE_CONFIG block below to set your agent names,
 * colors, roles, and domain.
 */
declare(strict_types=1);

// ============================================================
// CONFIGURATION — Set your agents, colors, and domain here
// ============================================================
$BRIDGE_CONFIG = [
    'domain'  => 'YOUR_DOMAIN',         // e.g. example.com
    'title'   => 'Pantheon Bridge',       // Page title
    'captain' => 'captain',               // Human operator name
    'agents'  => [
        'agent-a' => ['color' => '#60a5fa', 'role' => 'Planner'],
        'agent-b' => ['color' => '#8ffa39', 'role' => 'Builder'],
        'agent-c' => ['color' => '#a78bfa', 'role' => 'Verifier'],
    ],
    'captain_color' => '#fbbf24',
];

// Build lookup arrays from config
$ALL_AGENTS = array_keys($BRIDGE_CONFIG['agents']);
$VALID_RECIPIENTS = array_merge($ALL_AGENTS, ['all']);
$AGENT_COLORS = [];
foreach ($BRIDGE_CONFIG['agents'] as $name => $info) {
    $AGENT_COLORS[$name] = $info['color'];
}
$AGENT_COLORS[$BRIDGE_CONFIG['captain']] = $BRIDGE_CONFIG['captain_color'];

require_once __DIR__ . "/auth.php";

header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('Expires: Thu, 01 Jan 1970 00:00:00 GMT');
header('X-Accel-Expires: 0');

$dir      = __DIR__;
$logFile  = $dir . '/log.jsonl';
$inboxDir = $dir . '/inbox';
$imageDir = $dir . '/shared/images';
$fileDir  = $dir . '/shared/files';

// Ensure directories exist
if (!is_dir($imageDir)) mkdir($imageDir, 0755, true);
if (!is_dir($fileDir))  mkdir($fileDir, 0755, true);

/** Read and parse log.jsonl into an array of messages. */
function read_log(string $file): array {
    if (!file_exists($file)) return [];
    $out = [];
    $lines = file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        $m = json_decode($line, true);
        if (is_array($m)) $out[] = $m;
    }
    return $out;
}

/** AJAX: return messages beyond $since index. */
if (($_GET['action'] ?? '') === 'fetch') {
    $since = max(0, (int)($_GET['since'] ?? 0));
    $messages = read_log($logFile);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
    header('Pragma: no-cache');
    echo json_encode([
        'count'    => count($messages),
        'messages' => array_slice($messages, $since),
    ]);
    exit;
}

/** POST: captain sends a new message (with optional image). */
// Block readonly users from posting
if ($bridge_role === 'readonly' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    header('HTTP/1.0 403 Forbidden');
    echo 'Read-only access.';
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $to    = in_array($_POST['to'] ?? '', $VALID_RECIPIENTS, true) ? $_POST['to'] : 'all';
    $topic = preg_replace('/[^a-zA-Z0-9\-_]/', '', trim((string)($_POST['topic'] ?? ''))) ?: 'general';
    $kind  = in_array($_POST['kind'] ?? '', ['note','question','answer','proposal','ack','handoff'], true) ? $_POST['kind'] : 'note';
    $body  = trim((string)($_POST['body'] ?? ''));

    // Handle image upload
    $imageUrl = '';
    if (!empty($_FILES['image']['tmp_name']) && $_FILES['image']['error'] === UPLOAD_ERR_OK) {
        $allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/heic'];
        $finfo = finfo_open(FILEINFO_MIME_TYPE);
        $mime = finfo_file($finfo, $_FILES['image']['tmp_name']);
        finfo_close($finfo);

        if (in_array($mime, $allowed, true)) {
            $ext = match($mime) {
                'image/jpeg' => '.jpg',
                'image/png'  => '.png',
                'image/gif'  => '.gif',
                'image/webp' => '.webp',
                'image/heic' => '.heic',
                default      => '.jpg',
            };
            $fname = date('Y-m-d_His') . '_' . bin2hex(random_bytes(4)) . $ext;
            $dest = $imageDir . '/' . $fname;
            if (move_uploaded_file($_FILES['image']['tmp_name'], $dest)) {
                $imageUrl = 'https://' . $BRIDGE_CONFIG['domain'] . '/_claude-bridge/shared/images/' . $fname;
            }
        }
    }

    // Handle file upload (CSV, TXT, PDF)
    $fileUrl = '';
    if (!empty($_FILES['attachment']['tmp_name']) && $_FILES['attachment']['error'] === UPLOAD_ERR_OK) {
        $allowedFiles = ['text/csv', 'text/plain', 'application/csv', 'application/pdf',
                         'application/vnd.ms-excel', 'application/json'];
        $finfo2 = finfo_open(FILEINFO_MIME_TYPE);
        $fileMime = finfo_file($finfo2, $_FILES['attachment']['tmp_name']);
        finfo_close($finfo2);

        $origName = $_FILES['attachment']['name'] ?? '';
        $origExt = strtolower(pathinfo($origName, PATHINFO_EXTENSION));

        if (in_array($fileMime, $allowedFiles, true) || in_array($origExt, ['csv', 'txt', 'json'], true)) {
            $safeExt = match($origExt) {
                'csv'  => '.csv',
                'txt'  => '.txt',
                'json' => '.json',
                'pdf'  => '.pdf',
                default => '.csv',
            };
            $safeName = preg_replace('/[^a-zA-Z0-9_\-]/', '_', pathinfo($origName, PATHINFO_FILENAME));
            $fname2 = date('Y-m-d_His') . '_' . $safeName . $safeExt;
            $dest2 = $fileDir . '/' . $fname2;
            if (move_uploaded_file($_FILES['attachment']['tmp_name'], $dest2)) {
                $fileUrl = 'https://' . $BRIDGE_CONFIG['domain'] . '/_claude-bridge/shared/files/' . $fname2;
            }
        }
    }

    // Build body with image
    if ($imageUrl && $body) {
        $body = $body . "\n\n[image:" . $imageUrl . "]";
    } elseif ($imageUrl) {
        $body = "[image:" . $imageUrl . "]";
    }
    if ($fileUrl && $body) {
        $body = $body . "\n\n[file:" . $fileUrl . "]";
    } elseif ($fileUrl) {
        $body = "[file:" . $fileUrl . "]";
    }

    if ($body === '') {
        header('Location: viewer.php');
        exit;
    }

    $ts = gmdate('Y-m-d\TH:i:s\Z');
    $captain = $BRIDGE_CONFIG['captain'];
    $recipients = ($to === 'all') ? $ALL_AGENTS : [$to];
    $counter = 1;

    foreach ($recipients as $rcpt) {
        $id = $ts . '-' . sprintf('%03d', $counter++);
        $msg = [
            'id'       => $id,
            'from'     => $captain,
            'to'       => $rcpt,
            'ts'       => $ts,
            'reply_to' => null,
            'topic'    => $topic,
            'kind'     => $kind,
            'body'     => $body,
        ];
        $line = json_encode($msg, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n";
        file_put_contents($inboxDir . '/' . $rcpt . '.jsonl', $line, FILE_APPEND | LOCK_EX);
        file_put_contents($logFile, $line, FILE_APPEND | LOCK_EX);
    }

    header('Location: viewer.php?sent=1#bottom');
    exit;
}

// Initial page render
$messages = read_log($logFile);
$initialCount = count($messages);
$justSent = isset($_GET['sent']);

// Load scoreboard
$scoreboardFile = $dir . '/scoreboard-status.json';
$scoreboard = file_exists($scoreboardFile) ? json_decode(file_get_contents($scoreboardFile), true) : null;

// Load task registry
$taskRegistryFile = $dir . '/task-registry.json';
$taskRegistry = file_exists($taskRegistryFile) ? json_decode(file_get_contents($taskRegistryFile), true) : null;
$tasks = $taskRegistry['tasks'] ?? [];

// AJAX: return scoreboard data
if (($_GET['action'] ?? '') === 'scoreboard') {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($scoreboard ?: ['error' => 'no scoreboard']);
    exit;
}
// AJAX: return task registry
if (($_GET['action'] ?? '') === 'tasks') {
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($taskRegistry ?: ['error' => 'no tasks']);
    exit;
}

// Build CSS variables for agent colors
$agentCssVars = "";
foreach ($BRIDGE_CONFIG['agents'] as $name => $info) {
    $safeName = preg_replace('/[^a-z0-9]/', '', $name);
    $agentCssVars .= "  --{$safeName}-color: {$info['color']};\n";
}
$captainSafe = preg_replace('/[^a-z0-9]/', '', $BRIDGE_CONFIG['captain']);
$agentCssVars .= "  --{$captainSafe}-color: {$BRIDGE_CONFIG['captain_color']};\n";
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title><?= htmlspecialchars($BRIDGE_CONFIG['title']) ?></title>
<style>
:root {
  --deep-navy: #0a1628;
  --navy: #0e1f35;
  --navy-light: #162944;
  --accent: #8ffa39;
  --accent-soft: #a8fb66;
  --text: #e2e8f0;
  --text-muted: #94a3b8;
<?= $agentCssVars ?>
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; }
body {
  font-family: -apple-system, system-ui, 'Segoe UI', sans-serif;
  background: linear-gradient(135deg, var(--deep-navy) 0%, var(--navy) 100%);
  color: var(--text);
  min-height: 100vh;
  padding-top: 200px;
  padding-bottom: 24px;
}

.jump-latest {
  position: fixed;
  right: 24px;
  bottom: 24px;
  background: var(--accent);
  color: var(--deep-navy);
  border: none;
  border-radius: 999px;
  padding: 10px 18px;
  font-weight: 700;
  font-size: 0.82rem;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(143, 250, 57, 0.35);
  z-index: 25;
  display: none;
  animation: slideIn 0.25s ease-out;
}
.jump-latest:hover { background: var(--accent-soft); transform: translateY(-1px); }
.jump-latest.visible { display: inline-flex; align-items: center; gap: 6px; }
header {
  background: rgba(10, 22, 40, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(143, 250, 57, 0.2);
  padding: 14px 24px;
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 15;
}
header .inner {
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
}
h1 {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--accent);
}
.stats {
  margin-left: auto;
  font-size: 0.82rem;
  color: var(--text-muted);
}
.pulse {
  width: 10px; height: 10px;
  background: var(--accent);
  border-radius: 50%;
  display: inline-block;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(143,250,57,0.5); }
  50% { opacity: 0.7; box-shadow: 0 0 0 8px rgba(143,250,57,0); }
}
@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Messages */
.messages {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.msg {
  display: flex;
  gap: 10px;
  animation: slideIn 0.2s ease-out;
}
.avatar {
  width: 36px; height: 36px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
  overflow: hidden;
  border: 2px solid transparent;
}
.avatar img {
  width: 100%; height: 100%;
  object-fit: cover;
  border-radius: 50%;
}
<?php foreach ($BRIDGE_CONFIG['agents'] as $name => $info):
  $safe = preg_replace('/[^a-z0-9]/', '', $name);
?>
.avatar--<?= $safe ?>   { background: var(--<?= $safe ?>-color); color: #0a1628; border-color: var(--<?= $safe ?>-color); }
.bubble--<?= $safe ?>   { border-left: 3px solid var(--<?= $safe ?>-color); }
.msg-from--<?= $safe ?> { color: var(--<?= $safe ?>-color); }
<?php endforeach; ?>
.avatar--<?= $captainSafe ?>   { background: var(--<?= $captainSafe ?>-color); color: #0a1628; border-color: var(--<?= $captainSafe ?>-color); }
.bubble--<?= $captainSafe ?>   { border-left: 3px solid var(--<?= $captainSafe ?>-color); }
.msg-from--<?= $captainSafe ?> { color: var(--<?= $captainSafe ?>-color); }
.bubble {
  background: var(--navy-light);
  border-radius: 12px;
  padding: 10px 14px;
  flex: 1;
  min-width: 0;
}
.msg-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
  font-size: 0.8rem;
}
.msg-from { font-weight: 700; }
.msg-arrow { color: var(--text-muted); }
.msg-to { color: var(--text-muted); }
.chip {
  background: rgba(255,255,255,0.06);
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.72rem;
  color: var(--text-muted);
}
.chip--kind { background: rgba(143,250,57,0.1); color: var(--accent); }
.msg-time { margin-left: auto; color: var(--text-muted); font-size: 0.72rem; }
.msg-body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.88rem;
  line-height: 1.55;
}
.msg-body img.bridge-img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  margin-top: 8px;
  border: 1px solid rgba(143, 250, 57, 0.2);
  cursor: pointer;
}
.msg-body img.bridge-img:hover {
  border-color: var(--accent);
  box-shadow: 0 4px 16px rgba(143, 250, 57, 0.2);
}
.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 48px 0;
  font-style: italic;
}

/* Compose */
.compose {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  background: rgba(10, 22, 40, 0.97);
  backdrop-filter: blur(16px);
  border-top: 2px solid var(--accent);
  padding: 16px 24px;
  z-index: 20;
}
.compose form {
  max-width: 900px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 10px;
  align-items: end;
}
.compose-field label {
  display: block;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 3px;
}
.compose-field select,
.compose-field input[type="text"] {
  width: 100%;
  background: var(--navy-light);
  color: var(--text);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 0.85rem;
}
.compose-field--body { grid-column: 1 / -1; }
.compose-field--body textarea {
  width: 100%;
  background: var(--navy-light);
  color: var(--text);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 0.88rem;
  min-height: 50px;
  resize: vertical;
}
.compose-field--image { grid-column: 1 / 3; }
.compose-field--image input[type="file"] {
  width: 100%;
  background: var(--navy-light);
  color: var(--text);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.82rem;
}
.compose-field--image input[type="file"]::file-selector-button {
  background: var(--accent);
  color: var(--deep-navy);
  border: none;
  border-radius: 4px;
  padding: 4px 10px;
  font-weight: 600;
  font-size: 0.78rem;
  cursor: pointer;
  margin-right: 8px;
}
.compose-field--preview { grid-column: 3 / -1; display: flex; align-items: center; }
.compose-field--preview img {
  max-height: 60px;
  border-radius: 6px;
  border: 1px solid var(--accent);
}
.compose-field--preview .no-preview {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-style: italic;
}
.compose button {
  background: var(--accent);
  color: var(--deep-navy);
  border: none;
  border-radius: 6px;
  padding: 9px 18px;
  font-weight: 700;
  font-size: 0.88rem;
  cursor: pointer;
  grid-column: 1 / -1;
}
.compose button:hover { background: var(--accent-soft); }

.toast {
  position: fixed; bottom: 70px; left: 50%;
  transform: translateX(-50%);
  background: var(--accent);
  color: var(--deep-navy);
  padding: 8px 20px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.84rem;
  z-index: 30;
  animation: toastIn 0.3s ease-out, toastOut 0.4s 2s forwards;
}
@keyframes toastIn {
  from { opacity: 0; transform: translate(-50%, 10px); }
  to   { opacity: 1; transform: translate(-50%, 0); }
}
@keyframes toastOut {
  to { opacity: 0; transform: translate(-50%, 10px); }
}
@media (max-width: 780px) {
  .compose form {
    grid-template-columns: 1fr 1fr 1fr;
  }
  .compose-field--body { grid-column: 1 / -1; }
  .compose-field--image { grid-column: 1 / -1; }
  .compose-field--preview { grid-column: 1 / -1; }
  .compose button { grid-column: 1 / -1; width: 100%; }
}
/* Lightbox */
.lightbox {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.9);
  z-index: 100;
  justify-content: center;
  align-items: center;
  cursor: pointer;
}
.lightbox.active { display: flex; }
.lightbox img {
  max-width: 95vw;
  max-height: 95vh;
  border-radius: 8px;
}
</style>
</head>
<body>

<header>
  <div class="inner">
    <span class="pulse"></span>
    <h1><?= htmlspecialchars($BRIDGE_CONFIG['title']) ?></h1>
    <span class="stats">
      <span id="msg-count"><?= $initialCount ?></span> msgs &middot;
      refresh <span id="refresh-status">on</span>
    </span>
  </div>
</header>

<?php if ($justSent): ?>
  <div class="toast" id="toast">&#10003; Message sent</div>
<?php endif; ?>

<div class="messages" id="messages">
<?php if (empty($messages)): ?>
  <div class="empty">The bridge is quiet. Send the first message below.</div>
<?php else: foreach ($messages as $m):
  $from = preg_replace('/[^a-z0-9\-]/', '', strtolower($m['from'] ?? ''));
  $fromSafe = preg_replace('/[^a-z0-9]/', '', $from);
  $to   = htmlspecialchars($m['to'] ?? '?');
  $time = (string)($m['ts'] ?? '');
  $timeShort = $time ? substr($time, 11, 5) . ' UTC' : '';
  $topic = htmlspecialchars($m['topic'] ?? '');
  $kind  = htmlspecialchars($m['kind'] ?? '');
  $rawBody = $m['body'] ?? '';
  // Render [image:URL] tags as actual images
  $body = htmlspecialchars($rawBody);
  $body = preg_replace(
    '/\[image:(https?:\/\/[^\]]+)\]/',
    '<br><img class="bridge-img" src="$1" alt="shared image" onclick="openLightbox(this.src)">',
    $body
  );
  $avatar = strtoupper(substr($from ?: '?', 0, 1));
?>
  <div class="msg">
    <div class="avatar avatar--<?= $fromSafe ?>"><?= $avatar ?></div>
    <div class="bubble bubble--<?= $fromSafe ?>">
      <div class="msg-header">
        <span class="msg-from msg-from--<?= $fromSafe ?>"><?= htmlspecialchars($from) ?></span>
        <span class="msg-arrow">&rarr;</span>
        <span class="msg-to"><?= $to ?></span>
        <span class="chip"><?= $topic ?></span>
        <span class="chip chip--kind"><?= $kind ?></span>
        <span class="msg-time"><?= $timeShort ?></span>
      </div>
      <div class="msg-body"><?= $body ?></div>
    </div>
  </div>
<?php endforeach; endif; ?>
</div>

<div id="bottom"></div>

<button type="button" class="jump-latest" id="jump-latest">&darr; Jump to latest</button>

<!-- Lightbox for full-screen image view -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <img id="lightbox-img" src="" alt="full size">
</div>

<?php if ($bridge_role === "admin"): ?>
<div class="compose">
  <form method="POST" action="viewer.php" enctype="multipart/form-data">
    <div class="compose-field">
      <label>To</label>
      <select name="to">
        <option value="all">all</option>
        <?php foreach ($ALL_AGENTS as $agent): ?>
          <option value="<?= htmlspecialchars($agent) ?>"><?= htmlspecialchars($agent) ?></option>
        <?php endforeach; ?>
      </select>
    </div>
    <div class="compose-field">
      <label>Topic</label>
      <input type="text" name="topic" value="general" maxlength="40">
    </div>
    <div class="compose-field">
      <label>Kind</label>
      <select name="kind">
        <option value="note">note</option>
        <option value="question">question</option>
        <option value="proposal">proposal</option>
        <option value="answer">answer</option>
        <option value="ack">ack</option>
        <option value="handoff">handoff</option>
      </select>
    </div>
    <div class="compose-field compose-field--body">
      <label>Message</label>
      <textarea name="body" placeholder="Type your message... (image optional)" ></textarea>
    </div>
    <div class="compose-field compose-field--image">
      <label>Attach Photo</label>
      <input type="file" name="image" accept="image/*" id="image-input">
    </div>
    <div class="compose-field compose-field--image">
      <label>Attach File (CSV, TXT, JSON, PDF)</label>
      <input type="file" name="attachment" accept=".csv,.txt,.json,.pdf" id="file-input">
    </div>
    <div class="compose-field compose-field--preview" id="preview-area">
      <span class="no-preview">No image selected</span>
    </div>
    <button type="submit">Send</button>
  </form>
</div>
<?php endif; ?>

<script>
let messageCount = <?= $initialCount ?>;
let refreshEnabled = true;

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderBodyWithImages(raw) {
  let html = escapeHtml(raw);
  html = html.replace(
    /\[image:(https?:\/\/[^\]]+)\]/g,
    '<br><img class="bridge-img" src="$1" alt="shared image" onclick="openLightbox(this.src)">'
  );
  return html;
}

function renderMessage(m) {
  const from = String(m.from || '?').replace(/[^a-z0-9\-]/gi, '').toLowerCase();
  const fromSafe = from.replace(/[^a-z0-9]/gi, '');
  const to = escapeHtml(m.to || '?');
  const time = (m.ts || '').substr(11, 5) + ' UTC';
  const topic = escapeHtml(m.topic || '');
  const kind = escapeHtml(m.kind || '');
  const body = renderBodyWithImages(m.body || '');

  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = `
    <div class="avatar avatar--${fromSafe}">${(from || '?').charAt(0).toUpperCase()}</div>
    <div class="bubble bubble--${fromSafe}">
      <div class="msg-header">
        <span class="msg-from msg-from--${fromSafe}">${from}</span>
        <span class="msg-arrow">&rarr;</span>
        <span class="msg-to">${to}</span>
        <span class="chip">${topic}</span>
        <span class="chip chip--kind">${kind}</span>
        <span class="msg-time">${time}</span>
      </div>
      <div class="msg-body">${body}</div>
    </div>`;
  return div;
}

async function poll() {
  if (!refreshEnabled) return;
  try {
    const res = await fetch('viewer.php?action=fetch&since=' + messageCount, { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    if (data.messages && data.messages.length > 0) {
      const container = document.getElementById('messages');
      const empty = container.querySelector('.empty');
      if (empty) empty.remove();

      const nearBottom = (window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 300);
      data.messages.forEach(m => container.appendChild(renderMessage(m)));

      messageCount = data.count;
      document.getElementById('msg-count').textContent = messageCount;

      if (nearBottom) window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
      if (typeof updateJumpVisibility === 'function') updateJumpVisibility();
    }
  } catch (e) {
    console.error('poll error', e);
  }
}

setInterval(poll, 5000);

/* ---- Lightbox ---- */
function openLightbox(src) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.add('active');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('active');
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

/* ---- Image preview ---- */
const imgInput = document.getElementById('image-input');
if (imgInput) {
  imgInput.addEventListener('change', function(e) {
    const preview = document.getElementById('preview-area');
    if (this.files && this.files[0]) {
      const reader = new FileReader();
      reader.onload = function(ev) {
        preview.innerHTML = '<img src="' + ev.target.result + '" alt="preview">';
      };
      reader.readAsDataURL(this.files[0]);
    } else {
      preview.innerHTML = '<span class="no-preview">No image selected</span>';
    }
  });
}

/* ---- Jump button + scroll ---- */
const jumpBtn = document.getElementById('jump-latest');

function isNearBottom() {
  return (window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 200);
}

function scrollToLatest(smooth) {
  window.scrollTo({ top: document.body.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
}

function updateJumpVisibility() {
  if (isNearBottom()) jumpBtn.classList.remove('visible');
  else jumpBtn.classList.add('visible');
}

window.addEventListener('load', () => {
  scrollToLatest(false);
  updateJumpVisibility();
});

window.addEventListener('scroll', updateJumpVisibility, { passive: true });
jumpBtn.addEventListener('click', () => scrollToLatest(true));

const ta = document.querySelector('textarea[name=body]');
if (ta) {
  const status = document.getElementById('refresh-status');
  ta.addEventListener('focus', () => {
    refreshEnabled = false;
    status.textContent = 'paused';
  });
  ta.addEventListener('blur', () => {
    if (!ta.value.trim()) {
      refreshEnabled = true;
      status.textContent = 'on';
    }
  });
}
</script>
</body>
</html>
