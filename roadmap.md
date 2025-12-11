# Roadmap: Implementazione di Autenticazione a Token e Gestione Permessi (RBAC)

## Obiettivo

Questo documento descrive il piano per evolvere il sistema di autenticazione da una singola API key statica e Basic Auth (htpasswd) a un moderno sistema di **autenticazione basato su token (JWT)** e **controllo degli accessi basato sui ruoli (RBAC)**.

L'obiettivo è aumentare la sicurezza, la flessibilità e permettere una gestione granulare dei permessi per utenti diversi.

---

## Stack Tecnologico Proposto

*   **Autenticazione**: **JSON Web Tokens (JWT)**. Standard de-facto per la creazione di token di accesso che possono contenere in modo sicuro i dati dell'utente (ID, ruolo) e una data di scadenza.
*   **Database Utenti**: **SQLite**. Un database leggero basato su file, perfetto per non appesantire l'architettura. Verrà gestito tramite **SQLAlchemy** nel backend Python.
*   **Hashing Password**: **Passlib** con l'algoritmo `bcrypt`. Per garantire che le password nel database siano salvate in modo sicuro e non in chiaro.

---

## Piano di Implementazione a Fasi

### Fase 1: Setup del Backend e del Database

1.  **1.1. Aggiornamento Dipendenze Python**:
    *   Aggiungere a `backend/requirements.txt` le librerie necessarie:
        ```
        fastapi[all]
        python-jose[cryptography]  # Per la gestione dei JWT
        passlib[bcrypt]            # Per l'hashing delle password
        sqlalchemy                 # ORM per interagire con SQLite
        ```

2.  **1.2. Definizione Modello Dati**:
    *   Creare un nuovo file `backend/database.py` per definire la connessione a SQLite e i modelli.
    *   Definire il modello `User` con SQLAlchemy, che includerà i campi:
        *   `id` (Integer, Primary Key)
        *   `username` (String, Unique)
        *   `hashed_password` (String)
        *   `role` (String, es. "admin", "manager")
        *   `is_active` (Boolean)

3.  **1.3. Script di Inizializzazione**:
    *   Creare una logica (che può essere eseguita all'avvio del backend) per creare il file del database SQLite (`users.db`) e le tabelle se non esistono.
    *   Questo script creerà anche un primo utente `admin` con una password di default da cambiare al primo accesso.

### Fase 2: Logica di Autenticazione nel Backend (FastAPI)

1.  **2.1. Creazione Endpoint di Login**:
    *   Sviluppare un nuovo endpoint `POST /api/login` in `main.py`.
    *   Questo endpoint accetterà username e password.
    *   Verificherà le credenziali confrontando l'hash della password fornita con quello nel database.
    *   Se le credenziali sono valide, genererà e restituirà un token JWT.

2.  **2.2. Utility per la Gestione dei Token**:
    *   Creare un file `backend/security.py`.
    *   Implementare le funzioni:
        *   `create_access_token(data: dict)`: Crea un JWT firmato con una chiave segreta e una data di scadenza.
        *   `get_current_user(token: str = Depends(oauth2_scheme))`: Una "dependency" di FastAPI che verrà usata per proteggere gli endpoint. Questa funzione decodifica il token, ne valida la firma e la scadenza, e recupera l'utente dal database.

3.  **2.3. Protezione degli Endpoint Esistenti**:
    *   Modificare tutti gli endpoint attuali (es. `/api/instances`, `/api/firewall/rules`) per includere la dependency `get_current_user`. In questo modo, qualsiasi chiamata senza un token valido verrà automaticamente respinta con un errore `401 Unauthorized`.

### Fase 3: Gestione dei Permessi (RBAC) nel Backend

1.  **3.1. Creazione Dependency per i Ruoli**:
    *   In `backend/security.py`, creare una nuova dependency `require_role(required_role: str)`.
    *   Questa dependency riutilizzerà `get_current_user` per ottenere l'utente attuale e poi confronterà il suo ruolo con quello richiesto (`required_role`).
    *   Se il ruolo non è adeguato, solleverà un'eccezione `HTTPException` con status `403 Forbidden`.

2.  **3.2. Applicazione dei Ruoli agli Endpoint**:
    *   Applicare la nuova dependency agli endpoint che richiedono permessi specifici.
    *   Esempio:
        *   `@router.get("/api/machine/firewall", dependencies=[Depends(require_role("admin"))])`: Solo gli admin possono accedere.
        *   `@router.post("/api/instance/{id}/firewall", dependencies=[Depends(require_role("manager"))])`: Sia `manager` che `admin` (con una piccola modifica alla dependency) possono accedere.

### Fase 4: Aggiornamento del Frontend (PHP/JS)

1.  **4.1. Creazione Pagina di Login**:
    *   Creare un nuovo file `frontend/login.php` con un form HTML per username e password.
    *   Questa pagina diventerà il nuovo punto di ingresso dell'applicazione.

2.  **4.2. Logica di Login in JavaScript**:
    *   Nel file JS della pagina di login, intercettare il submit del form.
    *   Eseguire una chiamata `fetch` all'endpoint `/api/login` del backend.
    *   Se la chiamata ha successo, salvare il token JWT ricevuto nel `localStorage` del browser e reindirizzare l'utente alla dashboard (`index.php`).
    *   In caso di errore, mostrare un messaggio all'utente.

3.  **4.3. Modifica Chiamate API**:
    *   Aggiornare il file `frontend/js/utils.js` (o `api_client.php`) per includere l'header `Authorization: Bearer <token>` in tutte le chiamate API, recuperando il token da `localStorage`.

4.  **4.4. UI Dinamica e Logout**:
    *   Al caricamento della pagina, il frontend può ispezionare il payload del JWT (decodificandolo, senza validare la firma) per leggere il ruolo dell'utente.
    *   In base al ruolo, nascondere/mostrare elementi della UI (es. il link a "Impostazioni Macchina" nel menu laterale per i `manager`).
    *   Aggiungere un pulsante "Logout" che rimuova il token dal `localStorage` e reindirizzi alla pagina di login.

### Fase 5: Pulizia e Migrazione Finale

1.  **5.1. Rimozione Basic Auth da Nginx**:
    *   Modificare il file `nginx/vpn-dashboard.conf` e rimuovere le direttive `auth_basic` e `auth_basic_user_file`.

2.  **5.2. Rimozione Vecchia API Key**:
    *   Rimuovere la logica relativa alla `API_KEY` statica dal file `frontend/config.php` e dal backend Python.

3.  **5.3. Documentazione**:
    *   Aggiornare il `README.md` per descrivere la nuova modalità di accesso e la gestione degli utenti tramite la UI (se verrà sviluppata) o tramite comandi da shell per aggiungere nuovi utenti al database.
