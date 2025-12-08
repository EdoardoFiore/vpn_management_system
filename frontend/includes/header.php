<!doctype html>
<html lang="it">

<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta http-equiv="X-UA-Compatible" content="ie=edge" />
    <title>VPN Manager Dashboard</title>
    <!-- CSS files -->
    <link href="https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0-beta17/dist/css/tabler.min.css" rel="stylesheet" />
    <link href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css" rel="stylesheet" />
    <style>
        .card-actions {
            margin-left: auto;
        }

        .icon {
            width: 20px;
            height: 20px;
        }

        .cursor-pointer {
            cursor: pointer;
        }

        /* 1. Card Hover Effect */
        .instance-card {
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .instance-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1) !important;
        }

        /* 2. Wider Layout (Less "Claustrophobic") */
        @media (min-width: 1200px) {
            .container-xl {
                max-width: 1300px;
            }
        }

        /* 3. Notification Styles (Left Border) */
        .alert-success {
            border-left: 5px solid #2fb344 !important;
        }

        .alert-danger {
            border-left: 5px solid #d63939 !important;
        }
    </style>
</head>

<body class="layout-boxed">
    <div class="page">
        <!-- Navbar -->
        <header class="navbar navbar-expand-md navbar-light d-print-none">
            <div class="container-xl">
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbar-menu">
                    <span class="navbar-toggler-icon"></span>
                </button>
                </h1>
                <div class="collapse navbar-collapse" id="navbar-menu">
                    <div class="d-flex flex-column flex-md-row flex-fill align-items-stretch align-items-md-center">
                        <ul class="navbar-nav">
                            <li class="nav-item">
                                <a class="nav-link" href="index.php">
                                    <span class="nav-link-icon d-md-none d-lg-inline-block">
                                        <i class="ti ti-home"></i>
                                    </span>
                                    <span class="nav-link-title">Dashboard</span>
                                </a>
                            </li>
                        </ul>
                    </div>
                </div>
                <div class="navbar-nav flex-row order-md-last">
                    <div class="nav-item">
                        <a href="https://github.com/edoardofiore/vpn_management_system" target="_blank"
                            class="nav-link px-0" title="Source Code" rel="noreferrer">
                            <i class="ti ti-brand-github icon"></i>
                        </a>
                    </div>
                </div>
            </div>
        </header>

        <div class="page-wrapper">
            <!-- Page body -->
            <div class="page-body">
                <div class="container-xl">