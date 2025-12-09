# Gestore Automatizzato per OpenVPN con Interfaccia Web

[![Licenza: MIT](https://img.shields.io/badge/Licenza-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Un sistema completo per automatizzare il deployment e la gestione di server OpenVPN su Ubuntu 24.
Questo progetto nasce con l'obiettivo di rendere la creazione di una VPN accessibile a tutti, eliminando la complessità della configurazione manuale da riga di comando e offrendo una dashboard web moderna per la gestione quotidiana.

Che tu sia un amministratore di sistema esperto che vuole risparmiare tempo o un appassionato che vuole proteggere la propria navigazione, questo sistema ti permette di essere operativo in pochi minuti.

---

## 🚀 Installazione Rapida

L'installazione è progettata per essere "Zero Config": cloni la repository, lanci lo script e il sistema fa il resto.

### Prerequisiti

*   **OS**: Una macchina (fisica o virtuale) con **Ubuntu 24.04 LTS** (consigliato) o Debian 12.
*   **Privilegi**: Accesso root (`sudo`).
*   **Rete**:
    *   **IP Pubblico**: Ideale.
    *   **NAT**: Se sei dietro un router, devi inoltrare la porta UDP (default `1194`) e TCP `80` (per la dashboard) verso l'IP della VM.

### Passaggi

1.  **Scarica il Progetto**
    Accedi al tuo server e clona la repository:
    ```bash
    git clone https://github.com/EdoardoFiore/VPNManager.git
    cd VPNManager/scripts
    ```

2.  **Avvia l'Installazione**
    Esegui lo script di setup. Ti guiderà attraverso i pochi passaggi necessari (creazione utente dashboard, scelta rotte opzionali).
    ```bash
    sudo bash setup-vpn-manager.sh
    ```

3.  **Finito!**
    Al termine, lo script ti fornirà l'URL per accedere alla dashboard (es. `http://TUO_IP_PUBBLICO`) e la chiave API generata.

---

## ✨ Funzionalità Principali

*   **Gestione Multi-Istanza**: Non sei limitato a una sola VPN. Crea istanze multiple su porte diverse per separare team o servizi (es. una VPN per l'ufficio, una per i developer).
*   **Dashboard Intuitiva**: Pannello web responsive per vedere chi è connesso, aggiungere client e monitorare il traffico.
*   **Tunneling Flessibile**:
    *   **Full Tunnel**: Tutto il traffico passa per la VPN (ottimo per privacy/Wi-Fi pubblici).
    *   **Split Tunnel**: Decidi tu quali reti (es. `192.168.1.0/24`) passano per la VPN, lasciando il resto del traffico su internet normale.
*   **Gestione Client Semplificata**:
    *   Crea nuovi utenti in un click.
    *   Scarica il file `.ovpn` autoconfigurante.
    *   Revoca l'accesso istantaneamente se un dispositivo viene perso o compromesso.
*   **DNS Personalizzati**: Configura server DNS specifici per ogni istanza VPN (es. Pi-Hole, Google DNS).
*   **Firewall ACL per Gruppi**:
    *   Crea gruppi di client (es. "Amministratori", "Sviluppatori") per ogni istanza.
    *   Assegna regole granulari per consentire (`ACCEPT`) o bloccare (`DROP`) il traffico verso specifiche destinazioni (IP/CIDR) e porte.
    *   A ogni client aggiunto a un gruppo viene assegnato un IP statico per garantire la coerenza delle regole.
    *   Gestisci l'ordine di priorità delle regole direttamente dall'interfaccia.

---

## 🛠 Come Funziona (Backend e Architettura)

Per chi vuole capire cosa succede "sotto il cofano", ecco come è strutturato il sistema dopo l'installazione.

### Posizionamento File

Tutto il sistema risiede in `/opt/vpn-manager/`. Non sporchiamo il resto del filesystem se non necessario.

| Directory | Contenuto |
| :--- | :--- |
| `/opt/vpn-manager/backend` | Il cuore del sistema (API Python/FastAPI). |
| `/opt/vpn-manager/frontend` | L'interfaccia web (PHP/HTML/JS) servita da Nginx. |
| `/opt/vpn-manager/scripts` | Script di supporto (es. gestione iptables, forwarding). |
| `/etc/openvpn` | Configurazioni standard di OpenVPN (`server.conf`). |

### Processi e Servizi

Il sistema installa dei servizi `systemd` che si avviano al boot:

1.  **Backend API** (`vpn-manager.service`): È il cervello. Ascolta su porta locale, riceve i comandi dalla dashboard e pilota OpenVPN.
2.  **Web Server** (`nginx`): Serve la dashboard e protegge l'accesso con password.
3.  **OpenVPN** (`openvpn@<nome>.service`): Ogni istanza VPN ha il suo processo dedicato separato.
4.  **Firewall Persistence** (`iptables-openvpn.service`): Assicura che le regole di NAT e routing sopravvivano al riavvio del server.

---

## 👥 Gestione Utenti Dashboard

L'accesso alla dashboard è protetto da un livello di sicurezza aggiuntivo (Nginx Basic Auth).

Se vuoi aggiungere colleghi o cambiare la tua password, usa il comando `htpasswd` sul server:

*   **Cambia password / Aggiungi utente**:
    ```bash
    sudo htpasswd /etc/nginx/.htpasswd tuonomeutente
    ```
*   **Rimuovi utente**:
    ```bash
    sudo htpasswd -D /etc/nginx/.htpasswd utente_da_rimuovere
    ```
    *Ricorda di riavviare nginx (`sudo systemctl reload nginx`) dopo le modifiche.*

---

## � Stack Tecnologico

*   **Core**: OpenVPN (protocollo standard industriale).
*   **Backend**: Python con FastAPI (veloce, asincrono).
*   **Frontend**: PHP leggero + JavaScript Vanilla (nessun processo di build complesso necessario).
*   **Server**: Nginx (affidabilità e performance).

---

## 🆘 Troubleshooting

Qualcosa non va? Ecco i primi controlli da fare:

*   **La dashboard non carica**: Verifica che Nginx sia attivo (`systemctl status nginx`).
*   **Errore "API Error"**: Verifica che il backend sia su (`systemctl status vpn-manager.service`).
*   **I client si connettono ma non navigano**: Spesso è un problema di IP Forwarding o Firewall. Controlla se le regole iptables sono caricate (`iptables -L -t nat`).

---

**Licenza**: MIT. Fanne buon uso!
