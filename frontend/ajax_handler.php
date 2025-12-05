<?php
// frontend/ajax_handler.php

require_once 'api_client.php';

header('Content-Type: application/json');

$action = $_GET['action'] ?? $_POST['action'] ?? '';


switch ($action) {
    case 'get_network_interfaces':
        $response = get_network_interfaces();
        echo json_encode($response);
        break;

    case 'get_instances':
        $response = get_instances();
        echo json_encode($response);
        break;

    case 'create_instance':
        // Handle JSON payload
        $input = file_get_contents('php://input');
        $data = json_decode($input, true);

        if (!$data || !isset($data['name']) || !isset($data['port']) || !isset($data['subnet'])) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'Dati mancanti.']]);
            exit;
        }

        $response = create_instance(
            $data['name'],
            $data['port'],
            $data['subnet'],
            $data['protocol'] ?? 'udp',
            $data['outgoing_interface'] ?? null,
            $data['tunnel_mode'] ?? 'full',
            $data['routes'] ?? []
        );
        echo json_encode($response);
        break;

    case 'delete_instance':
        $instance_id = $_POST['instance_id'] ?? '';
        if (empty($instance_id)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'ID istanza mancante.']]);
            exit;
        }
        $response = delete_instance($instance_id);
        echo json_encode($response);
        break;

    case 'get_clients':
        $instance_id = $_GET['instance_id'] ?? '';
        if (empty($instance_id)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'ID istanza mancante.']]);
            exit;
        }
        $response = get_clients($instance_id);
        echo json_encode($response);
        break;

    case 'create_client':
        $instance_id = $_POST['instance_id'] ?? '';
        $client_name = $_POST['client_name'] ?? '';
        if (empty($instance_id) || empty($client_name) || !preg_match('/^[a-zA-Z0-9_.-]+$/', $client_name)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'Dati non validi.']]);
            exit;
        }
        $response = create_client($instance_id, $client_name);
        echo json_encode($response);
        break;

    case 'download_client':
        $instance_id = $_GET['instance_id'] ?? '';
        $client_name = $_GET['client_name'] ?? '';
        if (empty($instance_id) || empty($client_name) || !preg_match('/^[a-zA-Z0-9_.-]+$/', $client_name)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'Dati non validi.']]);
            exit;
        }
        $response = download_client_config($instance_id, $client_name);
        if ($response['success']) {
            header('Content-Type: application/x-openvpn-profile');
            header('Content-Disposition: attachment; filename="' . $client_name . '.ovpn"');
            echo $response['body'];
        } else {
            echo json_encode($response);
        }
        break;

    case 'revoke_client':
        $instance_id = $_POST['instance_id'] ?? '';
        $client_name = $_POST['client_name'] ?? '';
        if (empty($instance_id) || empty($client_name) || !preg_match('/^[a-zA-Z0-9_.-]+$/', $client_name)) {
            echo json_encode(['success' => false, 'body' => ['detail' => 'Dati non validi.']]);
            exit;
        }
        $response = revoke_client($instance_id, $client_name);
        echo json_encode($response);
        break;

    default:
        echo json_encode(['success' => false, 'body' => ['detail' => 'Azione non riconosciuta.']]);
        break;
}

