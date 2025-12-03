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

## 🚀 Stack Tecnologico

-   **VPN**: [OpenVPN](https://openvpn.net/)
-   **Script di Automazione**: Bash
-   **Backend API**: Python 3 con [FastAPI](https://fastapi.tiangolo.com/)
-   **Frontend**: JavaScript con [React](https://reactjs.org/) e [Bootstrap](https://getbootstrap.com/)
-   **Web Server / Reverse Proxy**: [Nginx](https://www.nginx.com/)
-   **Sistema Operativo**: Progettato per **Ubuntu 24.04 LTS**.

## 🖼️ Screenshot

*Ecco un'anteprima dell'interfaccia web.*

**(Placeholder per uno screenshot della dashboard principale)**
`![Dashboard Principale](https://user-images.githubusercontent.com/../placeholder.png)`

**(Placeholder per uno screenshot del form di creazione client)**
`![Creazione Client](https://user-images.githubusercontent.com/../placeholder.png)`

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
    git clone https://github.com/<TUO_NOME_UTENTE>/<NOME_REPOSITORY>.git
    ```

2.  **Esegui lo Script di Installazione**

    Naviga nella directory dello script e lancialo con privilegi `sudo`. Lo script si occuperà di tutto il resto.
    ```bash
    cd <NOME_REPOSITORY>/vpn_management_system/scripts/
    sudo bash setup-vpn-manager.sh
    ```

    L'installazione richiederà alcuni minuti. Lo script aggiornerà il sistema, installerà OpenVPN, configurerà il backend e il frontend e avvierà tutti i servizi.

3.  **Accesso alla Dashboard**

    Una volta completata l'installazione, lo script mostrerà l'URL per accedere alla dashboard web (es. `http://<IP_DELLA_TUA_VM>`) e la chiave API generata.

    Apri l'URL nel tuo browser e inizia a gestire la tua VPN!

---

## 🔧 Architettura

Il sistema è composto da quattro parti principali che lavorano insieme:

1.  **Script di Installazione (`setup-vpn-manager.sh`)**: L'orchestratore che prepara l'ambiente, installa tutte le dipendenze, configura i componenti e li avvia come servizi di sistema (`systemd`).
2.  **Backend API (FastAPI)**: Un'API REST scritta in Python che espone endpoint sicuri per interagire con il server OpenVPN. Si occupa di leggere i log, eseguire comandi per creare/revocare certificati e servire i file di configurazione.
3.  **Frontend (React)**: Un'applicazione single-page che fornisce l'interfaccia utente. Comunica con il backend tramite chiamate API per visualizzare i dati e inviare comandi.
4.  **Web Server (Nginx)**: Agisce come reverse proxy. Indirizza le richieste per l'API al backend FastAPI e serve i file statici dell'applicazione React a tutti gli altri utenti.

## 📄 Licenza

Questo progetto è rilasciato sotto la Licenza MIT. Vedi il file `LICENSE` per maggiori dettagli.
