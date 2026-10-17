<?php
/** Read-only device catalog built from the user's captured alarm history. */
declare(strict_types=1);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
$devices = json_decode((string)file_get_contents(__DIR__.'/data/devices.json'), true) ?: [];
$dashboard = json_decode((string)file_get_contents(__DIR__.'/data/dashboard.json'), true) ?: [];
$id = $_GET['device'] ?? null;
if ($id !== null) {
    foreach ($devices as $device) {
        if ($device['id'] === (string)$id) {
            echo json_encode(['device'=>$device], JSON_UNESCAPED_SLASHES);
            exit;
        }
    }
    http_response_code(404);
    echo json_encode(['error'=>'Device ID not found in captured data']);
    exit;
}
echo json_encode(['dashboard'=>$dashboard,'devices'=>$devices], JSON_UNESCAPED_SLASHES);
