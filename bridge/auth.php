<?php
/**
 * Bridge Authentication
 * Include at the top of viewer.php and scoreboard.php
 *
 * Roles:
 *   admin (full access) - read + write + upload
 *   spectator (read-only) - can watch but not post
 */

define('BRIDGE_USERS', [
    'admin'     => ['pass' => 'CHANGE_ME_ADMIN_PASSWORD', 'role' => 'admin'],
    'spectator' => ['pass' => 'CHANGE_ME_SPECTATOR_PASSWORD', 'role' => 'readonly'],
]);

function bridge_authenticate(): array {
    if (!isset($_SERVER['PHP_AUTH_USER'])) {
        header('WWW-Authenticate: Basic realm="Pantheon Bridge"');
        header('HTTP/1.0 401 Unauthorized');
        echo 'Authentication required.';
        exit;
    }

    $user = $_SERVER['PHP_AUTH_USER'];
    $pass = $_SERVER['PHP_AUTH_PW'];

    if (!isset(BRIDGE_USERS[$user]) || BRIDGE_USERS[$user]['pass'] !== $pass) {
        header('WWW-Authenticate: Basic realm="Pantheon Bridge"');
        header('HTTP/1.0 401 Unauthorized');
        echo 'Invalid credentials.';
        exit;
    }

    return ['user' => $user, 'role' => BRIDGE_USERS[$user]['role']];
}

$bridge_auth = bridge_authenticate();
$bridge_role = $bridge_auth['role'];
