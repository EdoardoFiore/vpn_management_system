<?php
// frontend/ajax_handler.php

require_once 'api_client.php';

header('Content-Type: application/json');

$action = $_GET['action'] ?? $_POST['action'] ?? '';

switch ($action) {
    case 'get_clients':
        $response = get_clients();
        echo json_encode($response);
        break;

    case 'create_client':
        $client_name = $_POST['client_name'] ?? '';
        if (empty($client_name) || !preg_match('/^[a-zA-Z0-9_.-]+$/', $client_name)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'Nome client non valido.']]);
            exit;
        }
        $response = create_client($client_name);
        echo json_encode($response);
        break;

    case 'download_client':
        $client_name = $_GET['client_name'] ?? '';
        if (empty($client_name) || !preg_match('/^[a-zA-Z0-9_.-]+$/', $client_name)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'Nome client non valido.']]);
            exit;
        }
        $response = download_client_config($client_name);
        if ($response['success']) {
            // Se è un successo, il body contiene il file .ovpn
            header('Content-Type: application/x-openvpn-profile');
            header('Content-Disposition: attachment; filename="' . $client_name . '.ovpn"');
            echo $response['body'];
        } else {
            // Errore
            echo json_encode($response); // Restituisce l'errore JSON
        }
        break;

    case 'revoke_client':
        $client_name = $_POST['client_name'] ?? '';
        if (empty($client_name) || !preg_match('/^[a-zA-Z0-9_.-]+$/', $client_name)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'Nome client non valido.']]);
            exit;
        }
        $response = revoke_client($client_name);
        echo json_encode($response);
        break;

    default:
        echo json_encode(['success' => false, 'body' => ['detail' => 'Azione non riconosciuta.']]);
        break;
}
