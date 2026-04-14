<?php
/**
 * Pantheon Scoreboard
 *
 * Reads/writes scores from scoreboard.json
 * Accessible at YOUR_DOMAIN/_claude-bridge/scoreboard.php
 *
 * CONFIGURATION: Edit the $AGENTS array below to match your agent names.
 */
declare(strict_types=1);

// ============================================================
// CONFIGURATION - Set your agent names here
// ============================================================
$AGENTS = ['agent-a', 'agent-b', 'agent-c', 'captain'];

header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
require_once __DIR__ . "/auth.php";

$scoreFile = __DIR__ . '/shared/scoreboard.json';

// API: update scores
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['action'])) {
    header('Content-Type: application/json');
    $data = json_decode(file_get_contents('php://input'), true);

    if ($_GET['action'] === 'score') {
        $scores = file_exists($scoreFile) ? json_decode(file_get_contents($scoreFile), true) : ['players' => [], 'rounds' => []];

        $player = $data['player'] ?? '';
        $points = $data['points'] ?? 1;
        $round = $data['round'] ?? '';
        $reason = $data['reason'] ?? '';

        if ($player) {
            if (!isset($scores['players'][$player])) {
                $scores['players'][$player] = 0;
            }
            $scores['players'][$player] += $points;
            $scores['rounds'][] = [
                'player' => $player,
                'points' => $points,
                'round' => $round,
                'reason' => $reason,
                'ts' => date('c')
            ];
            file_put_contents($scoreFile, json_encode($scores, JSON_PRETTY_PRINT));
            echo json_encode(['ok' => true, 'scores' => $scores['players']]);
        } else {
            echo json_encode(['error' => 'missing player']);
        }
        exit;
    }

    if ($_GET['action'] === 'fetch') {
        $scores = file_exists($scoreFile) ? json_decode(file_get_contents($scoreFile), true) : ['players' => [], 'rounds' => []];
        echo json_encode($scores);
        exit;
    }
}

// Initialize scores if empty
if (!file_exists($scoreFile)) {
    $init = ['players' => [], 'rounds' => []];
    foreach ($AGENTS as $agent) {
        $init['players'][$agent] = 0;
    }
    @mkdir(dirname($scoreFile), 0755, true);
    file_put_contents($scoreFile, json_encode($init, JSON_PRETTY_PRINT));
}

$scores = json_decode(file_get_contents($scoreFile), true);
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pantheon Scoreboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Montserrat', 'Segoe UI', sans-serif;
    background: #0a1628;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem;
}
h1 {
    font-size: 2rem;
    color: #8ffa39;
    margin-bottom: 0.5rem;
    text-align: center;
}
.subtitle {
    color: #94a3b8;
    font-size: 0.9rem;
    margin-bottom: 2rem;
    text-align: center;
}
.scoreboard {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1.5rem;
    width: 100%;
    max-width: 800px;
    margin-bottom: 3rem;
}
.player-card {
    background: linear-gradient(135deg, #0e2c57 0%, #081b38 100%);
    border: 2px solid #1e3a5f;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.player-card.leading {
    border-color: #8ffa39;
    box-shadow: 0 0 20px rgba(143, 250, 57, 0.2);
}
.player-card .name {
    font-size: 1.2rem;
    font-weight: 700;
    text-transform: capitalize;
    margin-bottom: 0.5rem;
}
.player-card .score {
    font-size: 3rem;
    font-weight: 800;
    color: #8ffa39;
    line-height: 1;
}
.player-card .label {
    font-size: 0.75rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.25rem;
}
.rounds {
    width: 100%;
    max-width: 800px;
}
.rounds h2 {
    font-size: 1.2rem;
    color: #8ffa39;
    margin-bottom: 1rem;
}
.round-entry {
    background: #0e2c57;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
}
.round-entry .player-tag {
    font-weight: 700;
    text-transform: capitalize;
    min-width: 60px;
}
.round-entry .reason { color: #94a3b8; flex: 1; margin: 0 1rem; }
.round-entry .pts {
    color: #8ffa39;
    font-weight: 700;
    white-space: nowrap;
}
.back-link {
    margin-top: 2rem;
    color: #64748b;
    text-decoration: none;
    font-size: 0.85rem;
}
.back-link:hover { color: #8ffa39; }
</style>
</head>
<body>

<h1>Pantheon Scoreboard</h1>
<p class="subtitle">Multi-Agent Collaboration Tracker</p>

<div class="scoreboard" id="scoreboard">
<?php
$maxScore = max(array_values($scores['players']) ?: [0]);
foreach ($scores['players'] as $name => $pts):
    $leading = ($pts > 0 && $pts === $maxScore) ? 'leading' : '';
?>
    <div class="player-card <?= $leading ?>">
        <div class="name"><?= htmlspecialchars($name) ?></div>
        <div class="score"><?= (int)$pts ?></div>
        <div class="label">points</div>
    </div>
<?php endforeach; ?>
</div>

<div class="rounds">
    <h2>Round History</h2>
    <?php if (empty($scores['rounds'])): ?>
        <div class="round-entry">
            <span class="reason">No rounds played yet.</span>
        </div>
    <?php else: ?>
        <?php foreach (array_reverse($scores['rounds']) as $r): ?>
        <div class="round-entry">
            <span class="player-tag"><?= htmlspecialchars($r['player']) ?></span>
            <span class="reason"><?= htmlspecialchars($r['reason'] ?? $r['round'] ?? '') ?></span>
            <span class="pts">+<?= (int)$r['points'] ?></span>
        </div>
        <?php endforeach; ?>
    <?php endif; ?>
</div>

<a href="viewer.php" class="back-link">&larr; Back to Bridge</a>

<script>
setInterval(async () => {
    try {
        const r = await fetch('?action=fetch', { method: 'POST', body: '{}' });
        const data = await r.json();
        // Auto-refresh page when scores change
        const current = document.querySelectorAll('.score');
        let changed = false;
        Object.values(data.players || {}).forEach((pts, i) => {
            if (current[i] && parseInt(current[i].textContent) !== pts) changed = true;
        });
        if (changed) location.reload();
    } catch(e) {}
}, 10000);
</script>

</body>
</html>
