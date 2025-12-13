<?php
require_once 'frontend/api_client.php';
// Header includes session check
require_once 'frontend/includes/header.php';

// Enforce Admin Role
if (($_SESSION['role'] ?? '') !== 'admin') {
    die('<div class="container text-center mt-5"><h1>403 Forbidden</h1><p>Access restricted to Administrators.</p></div>');
}

$error = '';
$success = '';

// Handle Create User
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action']) && $_POST['action'] === 'create') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';
    $role = $_POST['role'] ?? 'viewer';

    if ($username && $password) {
        $result = create_user($username, $password, $role);
        if ($result['success']) {
            $success = "User '$username' created successfully.";
        } else {
            $error = $result['body']['detail'] ?? 'Failed to create user.';
        }
    } else {
        $error = "Username and Password are required.";
    }
}

// Handle Delete User
if (isset($_GET['delete'])) {
    $userToDelete = $_GET['delete'];
    if ($userToDelete === $_SESSION['username']) {
        $error = "You cannot delete yourself!";
    } else {
        $result = delete_user($userToDelete);
        if ($result['success']) {
            $success = "User deleted successfully.";
        } else {
            $error = $result['body']['detail'] ?? 'Failed to delete user.';
        }
    }
}

// Fetch Users
$usersResponse = get_users();
$users = ($usersResponse['success'] && is_array($usersResponse['body'])) ? $usersResponse['body'] : [];
?>

<div class="page-wrapper">
    <div class="container-xl">
        <div class="page-header d-print-none">
            <div class="row align-items-center">
                <div class="col">
                    <h2 class="page-title">
                        Gestione Utenti
                    </h2>
                </div>
                <div class="col-auto ms-auto d-print-none">
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal"
                        data-bs-target="#modal-new-user">
                        <svg xmlns="http://www.w3.org/2000/svg" class="icon" width="24" height="24" viewBox="0 0 24 24"
                            stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round"
                            stroke-linejoin="round">
                            <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                            <line x1="12" y1="5" x2="12" y2="19" />
                            <line x1="5" y1="12" x2="19" y2="12" />
                        </svg>
                        Nuovo Utente
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="page-body">
        <div class="container-xl">
            <?php if ($error): ?>
                <div class="alert alert-danger" role="alert"><?= htmlspecialchars($error) ?></div>
            <?php endif; ?>
            <?php if ($success): ?>
                <div class="alert alert-success" role="alert"><?= htmlspecialchars($success) ?></div>
            <?php endif; ?>

            <div class="card">
                <div class="table-responsive">
                    <table class="table card-table table-vcenter text-nowrap datatable">
                        <thead>
                            <tr>
                                <th>Username</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th class="w-1">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($users as $user): ?>
                                <tr>
                                    <td><?= htmlspecialchars($user['username']) ?></td>
                                    <td>
                                        <span
                                            class="badge bg-blue-lt"><?= htmlspecialchars(ucfirst($user['role'])) ?></span>
                                    </td>
                                    <td>
                                        <?php if ($user['is_active']): ?>
                                            <span class="status status-green">Active</span>
                                        <?php else: ?>
                                            <span class="status status-red">Inactive</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if ($user['username'] !== 'admin' && $user['username'] !== $_SESSION['username']): ?>
                                            <a href="?delete=<?= urlencode($user['username']) ?>" class="btn btn-danger btn-sm"
                                                onclick="return confirm('Are you sure?')">Delete</a>
                                        <?php endif; ?>
                                    </td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Modal New User -->
<div class="modal modal-blur fade" id="modal-new-user" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-lg" role="document">
        <div class="modal-content">
            <form action="users.php" method="post">
                <input type="hidden" name="action" value="create">
                <div class="modal-header">
                    <h5 class="modal-title">Nuovo Utente</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" class="form-control" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" class="form-control" name="password" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Ruolo</label>
                        <select class="form-select" name="role">
                            <option value="viewer">Viewer (Solo Lettura)</option>
                            <option value="operator">Operator (Gestione Istanze)</option>
                            <option value="partner">Partner (Full VPN Mgmt)</option>
                            <option value="admin">Admin (Full System)</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn me-auto" data-bs-dismiss="modal">Annulla</button>
                    <button type="submit" class="btn btn-primary" data-bs-dismiss="modal">Crea Utente</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0-beta17/dist/js/tabler.min.js"></script>
</body>

</html>