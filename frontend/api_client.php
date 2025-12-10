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
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE); // Calculate is_success here
    $is_success = ($http_code >= 200 && $http_code < 300);

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
        $decoded_body = json_decode($body_str, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            // JSON decoding failed. If it's an error response, treat raw body as detail.
            if (!$is_success) {
                $body = ['detail' => "Errore API (" . $http_code . "): " . substr($body_str, 0, 200)];
            } else {
                // If it's a successful response but not JSON, keep as raw string.
                $body = $body_str;
            }
        } else {
            $body = $decoded_body;
        }
    }

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

// --- Groups & Firewall Functions ---

function get_groups($instance_id = null) {
    $url = '/groups';
    if ($instance_id) {
        $url .= '?instance_id=' . urlencode($instance_id);
    }
    return api_request($url);
}

function create_group($name, $instance_id, $description) {
    return api_request('/groups', 'POST', [
        'name' => $name,
        'instance_id' => $instance_id,
        'description' => $description
    ]);
}

function delete_group($group_id) {
    return api_request('/groups/' . urlencode($group_id), 'DELETE');
}

function add_group_member($group_id, $client_identifier, $subnet_info) {
    return api_request('/groups/' . urlencode($group_id) . '/members', 'POST', [
        'client_identifier' => $client_identifier,
        'subnet_info' => $subnet_info
    ]);
}

function remove_group_member($group_id, $client_identifier, $instance_name) {
    // Note: The backend endpoint expects parameters, but DELETE usually doesn't have body.
    // The backend route is /groups/{group_id}/members/{client_identifier}?instance_name=...
    // Actually in main.py: @app.delete("/api/groups/{group_id}/members/{client_identifier}")
    // with query param instance_name.
    // api_request supports adding query params to endpoint string.
    return api_request('/groups/' . urlencode($group_id) . '/members/' . urlencode($client_identifier) . '?instance_name=' . urlencode($instance_name), 'DELETE');
}

function get_rules($group_id = null) {
    $url = '/firewall/rules';
    if ($group_id) {
        $url .= '?group_id=' . urlencode($group_id);
    }
    return api_request($url);
}

// Helper to create rule
function create_rule($group_id, $action, $protocol, $destination, $port = null, $description = '', $order = null) {
    return api_request('/firewall/rules', 'POST', [
        'group_id' => $group_id,
        'action' => $action,
        'protocol' => $protocol,
        'port' => $port,
        'destination' => $destination,
        'description' => $description,
        'order' => $order
    ]);
}

function update_group_firewall_rule($rule_id, $group_id, $action, $protocol, $destination, $port = null, $description = '') {
    return api_request('/firewall/rules/' . urlencode($rule_id), 'PUT', [
        'group_id' => $group_id, // Needed for backend to locate the rule's group context
        'action' => $action,
        'protocol' => $protocol,
        'port' => $port,
        'destination' => $destination,
        'description' => $description
    ]);
}

function delete_rule($rule_id) {
    return api_request('/firewall/rules/' . urlencode($rule_id), 'DELETE');
}

function reorder_rules($orders) {
    return api_request('/firewall/rules/order', 'POST', $orders);
}

function update_instance_firewall_policy($instance_id, $new_policy) {
    return api_request("/instances/{$instance_id}/firewall-policy", 'PATCH', [
        'default_policy' => $new_policy
    ]);
}

// --- Machine Firewall Rules Functions ---

function get_machine_firewall_rules() {
    return api_request('/machine-firewall/rules');
}

function add_machine_firewall_rule($rule_data) {
    return api_request('/machine-firewall/rules', 'POST', $rule_data);
}

function delete_machine_firewall_rule($rule_id) {
    return api_request('/machine-firewall/rules/' . urlencode($rule_id), 'DELETE');
}

function update_machine_firewall_rule($rule_id, $rule_data) {
    return api_request('/machine-firewall/rules/' . urlencode($rule_id), 'PUT', $rule_data);
}

function apply_machine_firewall_rules($orders) {
    return api_request('/machine-firewall/rules/apply', 'PATCH', $orders);
}

// --- Machine Network Interface Functions ---

function get_machine_network_interfaces() {
    return api_request('/machine-network/interfaces');
}

function get_machine_network_interface_config($interface_name) {
    return api_request('/machine-network/interfaces/' . urlencode($interface_name) . '/config');
}

function update_machine_network_interface_config($interface_name, $config_data) {
    return api_request('/machine-network/interfaces/' . urlencode($interface_name) . '/config', 'POST', $config_data);
}

function apply_global_netplan_config() {
    return api_request('/machine-network/netplan-apply', 'POST');
}
?>