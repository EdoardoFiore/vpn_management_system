<?php
// api_client.php

require_once 'config.php';

function api_request($endpoint, $method = 'GET', $data = [], $raw_response = false)
{
    $url = API_BASE_URL . $endpoint;
    $ch = curl_init();

    $headers = [
        'Content-Type: application/json',
        'X-API-Key: ' . API_KEY
    ];

    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
    // Timeout per evitare attese infinite
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);

    if (($method === 'POST' || $method === 'PATCH' || $method === 'PUT') && $data) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    }

    // Per avere l'header nella risposta (utile per il download)
    curl_setopt($ch, CURLOPT_HEADER, true);

    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $header_size = curl_getinfo($ch, CURLINFO_HEADER_SIZE);

    if (curl_errno($ch)) {
        // Errore cURL, es. backend non raggiungibile
        $error_msg = curl_error($ch);
        curl_close($ch);
        // Ritorniamo un formato consistente per gli errori
        return ['success' => false, 'body' => ['detail' => "Errore di connessione all'API: " . $error_msg], 'code' => 503];
    }

    curl_close($ch);

    $header = substr($response, 0, $header_size);
    $body_str = substr($response, $header_size);

    if ($raw_response) {
        $body = $body_str;
    } else {
        $body = json_decode($body_str, true);
        // Se il json_decode fallisce, potrebbe essere un file o testo semplice
        if (json_last_error() !== JSON_ERROR_NONE) {
            $body = $body_str;
        }
    }

    $is_success = ($http_code >= 200 && $http_code < 300);

    return [
        'success' => $is_success,
        'code' => $http_code,
        'header' => $header,
        'body' => $body
    ];
}


function get_network_interfaces()
{
    return api_request('/network/interfaces');
}

function get_instances()
{
    return api_request('/instances');
}

function get_instance($instance_id)
{
    return api_request("/instances/$instance_id");
}

function create_instance($name, $port, $subnet, $protocol, $tunnel_mode = 'full', $routes = [], $dns_servers = [])
{
    return api_request('/instances', 'POST', [
        'name' => $name,
        'port' => (int) $port,
        'subnet' => $subnet,
        'protocol' => $protocol,
        'tunnel_mode' => $tunnel_mode,
        'routes' => $routes,
        'dns_servers' => $dns_servers
    ]);
}

function delete_instance($instance_id)
{
    return api_request("/instances/$instance_id", 'DELETE');
}

function update_instance_routes($instance_id, $tunnel_mode, $routes, $dns_servers = [])
{
    return api_request("/instances/$instance_id/routes", 'PATCH', [
        'tunnel_mode' => $tunnel_mode,
        'routes' => $routes,
        'dns_servers' => $dns_servers
    ]);
}

function get_clients($instance_id)
{
    return api_request('/instances/' . urlencode($instance_id) . '/clients');
}

function create_client($instance_id, $client_name)
{
    return api_request('/instances/' . urlencode($instance_id) . '/clients', 'POST', ['client_name' => $client_name]);
}

function download_client_config($instance_id, $client_name)
{
    return api_request("/instances/$instance_id/clients/$client_name/download", 'GET', [], true);
}

function revoke_client($instance_id, $client_name)
{
    return api_request('/instances/' . urlencode($instance_id) . '/clients/' . urlencode($client_name), 'DELETE');
}

function get_top_clients()
{
    return api_request('/stats/top-clients');
}
?>