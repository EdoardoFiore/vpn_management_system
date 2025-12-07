# Gestore Automatizzato per OpenVPN con Interfaccia Web

[![Licenza: MIT](https://img.shields.io/badge/Licenza-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Un sistema completo per automatizzare il deployment e la gestione di un server OpenVPN su Ubuntu 24, dotato di una moderna interfaccia web per il monitoraggio e la gestione dei client.

Questo progetto nasce dall'esigenza di semplificare e rendere più affidabile l'installazione ripetitiva di server OpenVPN, fornendo al contempo un'interfaccia grafica intuitiva per le operazioni di amministrazione più comuni.

---

## ✨ Funzionalità Principali

-   **Installazione 1-Click**: Esegui un singolo script per installare e configurare l'intero stack (OpenVPN, backend, frontend, web server).
-   **Interfaccia Web Moderna**: Una dashboard pulita e reattiva basata su React e Bootstrap.
-   **Gestione Clienti**:
    -   Visualizza tutti i client configurati e il loro stato di connessione in tempo reale.
    -   Crea nuovi client direttamente dall'interfaccia.
    -   Scarica i file di configurazione `.ovpn` con un click.
    -   Revoca l'accesso ai client in modo permanente.
-   **Sicuro**: Genera una chiave API univoca per proteggere l'accesso al backend.
-   **Automatizzato e Affidabile**: Utilizza script collaudati dalla community per la configurazione di OpenVPN, riducendo il rischio di errori manuali.

---

## ⚙️ Installazione Rapida

L'installazione è progettata per essere il più semplice possibile. Ti basterà clonare la repository ed eseguire uno script.

### Prerequisiti

-   Una macchina (fisica o virtuale) con **Ubuntu 24.04 LTS** pulita.
-   Accesso come utente `root` o un utente con privilegi `sudo`.

#### Requisiti di Rete

Il server OpenVPN deve essere raggiungibile pubblicamente. Assicurati che la tua configurazione di rete soddisfi uno dei seguenti requisiti:

-   **Scenario 1 (Ideale): IP Pubblico Diretto**
    Se la tua VM ha un indirizzo IP pubblico assegnato direttamente alla sua interfaccia di rete, lo script funzionerà senza configurazioni aggiuntive.

-   **Scenario 2: VM dietro un NAT/Firewall**
    Se la tua VM si trova in una rete privata (con un IP come `192.168.x.x`) e accede a Internet tramite un router, devi configurare il **Port Forwarding**. Inoltra la porta UDP scelta per OpenVPN (default: `1194`) dall'IP pubblico del tuo router all'IP privato della tua VM.

La porta `80` (TCP) deve essere sempre accessibile per l'interfaccia web.

### Passaggi

1.  **Clona la Repository**

    Connettiti via SSH alla tua VM Ubuntu e clona questa repository:
    ```bash
    git clone https://github.com/EdoardoFiore/VPNManager.git
    ```

2.  **Esegui lo Script di Installazione**

    Naviga nella directory dello script e lancialo con privilegi `sudo`. Lo script si occuperà di tutto il resto.
    ```bash
    cd vpn_management_system/scripts/
    sudo bash setup-vpn-manager.sh
    ```
    Durante l'installazione, ti verrà richiesto di creare un nome utente e una password per accedere alla dashboard web protetta da Nginx Basic Authentication.

    L'installazione richiederà alcuni minuti. Lo script aggiornerà il sistema, installerà OpenVPN, configurerà il backend e il frontend e avvierà tutti i servizi.

3.  **Accesso alla Dashboard**

    Una volta completata l'installazione, lo script mostrerà l'URL per accedere alla dashboard web (es. `http://<IP_DELLA_TUA_VM>`) e la chiave API generata.

    Apri l'URL nel tuo browser e inizia a gestire la tua VPN! Ti verranno richieste le credenziali impostate durante l'installazione.

---

## 🚀 Novità e Miglioramenti Recenti

Questa sezione riassume gli aggiornamenti significativi e le modifiche introdotte per migliorare la funzionalità, la robustezza e la sicurezza del sistema.

### 🐛 Correzioni e Miglioramenti Funzionali:
-   **Validazione Nomi Client Flessibile**: Ora i nomi dei client possono includere lettere, numeri, trattini (`-`), underscore (`_`) e punti (`.`), offrendo maggiore libertà nella denominazione.
-   **Prevenzione Duplicati**: Il sistema ora impedisce la creazione di client con nomi già esistenti.
-   **Revoca Client Robusta**: La revoca dei client è stata completamente rifattorizzata per utilizzare direttamente i comandi Easy-RSA. Questo garantisce un processo di revoca affidabile, un corretto aggiornamento dell'indice dei certificati (`index.txt`) e della Certificate Revocation List (CRL).
-   **Avviso di Revoca Irreversibile**: Un popup di conferma più chiaro avvisa l'utente che l'operazione di revoca è irreversibile.
-   **Script di Installazione Più Robusto**: Migliorata la gestione degli aggiornamenti `apt-get` e risolti problemi occasionali di pacchetti non trovati.
-   **Scoperta Dinamica dei Percorsi**: Lo script di installazione ora individua dinamicamente i percorsi critici di OpenVPN e Easy-RSA sul sistema, rendendo l'installazione più adattabile a diverse configurazioni.

### 🔒 Miglioramenti della Sicurezza:
-   **Autenticazione Frontend (Nginx Basic Auth)**: La dashboard web è ora protetta da Nginx Basic Authentication, richiedendo un nome utente e una password per l'accesso. Questo garantisce che solo gli utenti autorizzati possano accedere all'interfaccia di gestione.

### ⚙️ Gestione della Configurazione:
-   **Centralizzazione della Configurazione con `.env`**: I percorsi critici e altre impostazioni (come la chiave API) sono ora gestiti in un unico file `.env` situato in `/opt/vpn-manager/backend/.env`. Questo file viene popolato automaticamente durante l'installazione e letto sia dal backend Python che dagli script Bash per garantire coerenza.

---

## 👥 Gestione Utenti Nginx Basic Auth

Per aggiungere, modificare o rimuovere utenti per l'autenticazione Nginx Basic Auth che protegge la dashboard web, puoi utilizzare il comando `htpasswd` sul server. Il file delle password si trova in `/etc/nginx/.htpasswd`.

-   **Aggiungere un nuovo utente (o cambiare la password di un utente esistente):**
    ```bash
    sudo htpasswd /etc/nginx/.htpasswd <nome_utente>
    ```
    Ti verrà chiesto di inserire e confermare la password. Se l'utente non esiste, verrà creato. Se esiste, la sua password verrà aggiornata.

-   **Rimuovere un utente:**
    ```bash
    sudo htpasswd -D /etc/nginx/.htpasswd <nome_utente>
    ```

**Importante**: Dopo ogni modifica al file `.htpasswd`, è consigliabile riavviare Nginx per assicurarsi che i cambiamenti vengano caricati:
```bash
sudo systemctl reload nginx
```

---

## 🔒 Sicurezza del File `.env`

Il file `.env` (`/opt/vpn-manager/backend/.env`) contiene configurazioni sensibili (come la chiave API e percorsi di sistema). È importante sapere che:
-   **Non è accessibile via web**: La directory `/opt/vpn-manager/backend/` è al di fuori della root dei documenti di Nginx, quindi il file `.env` non può essere letto direttamente tramite un browser web.
-   **Utilizzo interno**: È destinato esclusivamente ad essere letto dal backend FastAPI e dagli script di gestione.

---

## 🚀 Stack Tecnologico

-   **VPN**: [OpenVPN](https://openvpn.net/)
-   **Script di Automazione**: Bash
-   **Backend API**: Python 3 con [FastAPI](https://fastapi.tiangolo.com/)
-   **Frontend**: JavaScript con [React](https://reactjs.org/) e [Bootstrap](https://getbootstrap.com/)
-   **Web Server / Reverse Proxy**: [Nginx](https://www.nginx.com/)
-   **Sistema Operativo**: Progettato per **Ubuntu 24.04 LTS**.

---

## 🔧 Architettura

Il sistema è composto da quattro parti principali che lavorano insieme:

1.  **Script di Installazione (`setup-vpn-manager.sh`)**: L'orchestratore che prepara l'ambiente, installa tutte le dipendenze, configura i componenti e li avvia come servizi di sistema (`systemd`).
2.  **Backend API (FastAPI)**: Un'API REST scritta in Python che espone endpoint sicuri per interagire con il server OpenVPN. Si occupa di leggere i log, eseguire comandi per creare/revocare certificati e servire i file di configurazione.
3.  **Frontend (React)**: Un'applicazione single-page che fornisce l'interfaccia utente. Comunica con il backend tramite chiamate API per visualizzare i dati e inviare comandi.
4.  **Web Server (Nginx)**: Agisce come reverse proxy. Indirizza le richieste per l'API al backend FastAPI e serve i file statici dell'applicazione React a tutti gli altri utenti.

## 📄 Licenza

Questo progetto è rilasciato sotto la Licenza MIT. Vedi il file `LICENSE` per maggiori dettagli.
