<?php
/**
 * Claude Bridge - Secure File Writer
 *
 * Upload to: YOUR_DOMAIN/_claude-bridge/writer.php
 *
 * Usage:
 *   POST /_claude-bridge/writer.php
 *   Content-Type: application/json
 *
 *   {
 *     "secret": "YOUR_SECRET_KEY",
 *     "action": "write|read|list|delete",
 *     "path": "landing.html",
 *     "content": "HTML content here"
 *   }
 */

// ============================================================
// CONFIGURATION - Change this secret before uploading!
// ============================================================
define('BRIDGE_SECRET', 'CHANGE_ME_GENERATE_A_RANDOM_SECRET_HERE');

// Base directory for all file operations (relative to this script)
define('BASE_DIR', __DIR__);

// Allowed file extensions
define('ALLOWED_EXTENSIONS', ['html', 'htm', 'css', 'js', 'json', 'txt', 'md']);

// Max file size (1MB)
define('MAX_FILE_SIZE', 1024 * 1024);

// ============================================================
// SECURITY
// ============================================================

// Only allow POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die(json_encode(['error' => 'Method not allowed']));
}

// Parse JSON body
$input = json_decode(file_get_contents('php://input'), true);
if (!$input) {
    http_response_code(400);
    die(json_encode(['error' => 'Invalid JSON']));
}

// Validate secret
if (!isset($input['secret']) || $input['secret'] !== BRIDGE_SECRET) {
    http_response_code(403);
    die(json_encode(['error' => 'Invalid secret']));
}

// Get action
$action = $input['action'] ?? 'write';
$path = $input['path'] ?? null;
$content = $input['content'] ?? null;

// Validate path
if ($path) {
    // Prevent directory traversal
    $path = basename($path); // Only allow files in base directory
    if (strpos($path, '..') !== false || strpos($path, '/') !== false) {
        http_response_code(400);
        die(json_encode(['error' => 'Invalid path - no directory traversal allowed']));
    }

    // Check extension
    $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
    if (!in_array($ext, ALLOWED_EXTENSIONS)) {
        http_response_code(400);
        die(json_encode(['error' => 'File extension not allowed: ' . $ext]));
    }
}

// ============================================================
// ACTIONS
// ============================================================

header('Content-Type: application/json');

switch ($action) {
    case 'write':
        if (!$path || $content === null) {
            http_response_code(400);
            die(json_encode(['error' => 'Missing path or content']));
        }

        if (strlen($content) > MAX_FILE_SIZE) {
            http_response_code(400);
            die(json_encode(['error' => 'Content too large (max 1MB)']));
        }

        $fullPath = BASE_DIR . '/' . $path;
        $bytes = file_put_contents($fullPath, $content);

        if ($bytes === false) {
            http_response_code(500);
            die(json_encode(['error' => 'Failed to write file']));
        }

        echo json_encode([
            'success' => true,
            'action' => 'write',
            'path' => $path,
            'bytes' => $bytes,
            'url' => 'https://YOUR_DOMAIN/_claude-bridge/' . $path
        ]);
        break;

    case 'read':
        if (!$path) {
            http_response_code(400);
            die(json_encode(['error' => 'Missing path']));
        }

        $fullPath = BASE_DIR . '/' . $path;
        if (!file_exists($fullPath)) {
            http_response_code(404);
            die(json_encode(['error' => 'File not found']));
        }

        echo json_encode([
            'success' => true,
            'action' => 'read',
            'path' => $path,
            'content' => file_get_contents($fullPath),
            'size' => filesize($fullPath)
        ]);
        break;

    case 'list':
        $files = [];
        foreach (glob(BASE_DIR . '/*') as $file) {
            if (is_file($file) && basename($file) !== 'writer.php') {
                $files[] = [
                    'name' => basename($file),
                    'size' => filesize($file),
                    'modified' => date('Y-m-d H:i:s', filemtime($file)),
                    'url' => 'https://YOUR_DOMAIN/_claude-bridge/' . basename($file)
                ];
            }
        }
        echo json_encode([
            'success' => true,
            'action' => 'list',
            'files' => $files,
            'count' => count($files)
        ]);
        break;

    case 'delete':
        if (!$path) {
            http_response_code(400);
            die(json_encode(['error' => 'Missing path']));
        }

        // Don't allow deleting the bridge itself
        if ($path === 'writer.php') {
            http_response_code(400);
            die(json_encode(['error' => 'Cannot delete bridge script']));
        }

        $fullPath = BASE_DIR . '/' . $path;
        if (!file_exists($fullPath)) {
            http_response_code(404);
            die(json_encode(['error' => 'File not found']));
        }

        if (unlink($fullPath)) {
            echo json_encode([
                'success' => true,
                'action' => 'delete',
                'path' => $path
            ]);
        } else {
            http_response_code(500);
            die(json_encode(['error' => 'Failed to delete file']));
        }
        break;

    case 'ping':
        echo json_encode([
            'success' => true,
            'action' => 'ping',
            'message' => 'Claude Bridge is operational',
            'time' => date('Y-m-d H:i:s'),
            'php_version' => PHP_VERSION
        ]);
        break;

    default:
        http_response_code(400);
        die(json_encode(['error' => 'Unknown action: ' . $action]));
}
