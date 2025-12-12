import subprocess
import logging
import os
from typing import Tuple, List

logger = logging.getLogger(__name__)

class WireGuardManager:
    """
    Gestisce le operazioni di basso livello di WireGuard, come la generazione
    di chiavi, PSK e la manipolazione dei file di configurazione e delle interfacce.
    """

    @staticmethod
    def _run_wg_command(args: List[str], input: str = None) -> str:
        """Esegue un comando 'wg' e restituisce lo stdout o solleva un errore."""
        try:
            result = subprocess.run(
                ['wg'] + args,
                capture_output=True,
                text=True,
                check=True,
                input=input
            )
            return result.stdout.strip()
        except FileNotFoundError:
            logger.error("Comando 'wg' non trovato. Assicurati che WireGuard sia installato e 'wg-tools' sia nel PATH.")
            raise RuntimeError("WireGuard tools (wg) not found.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Errore nell'esecuzione del comando 'wg {' '.join(args)}': {e.stderr.strip()}")
            raise RuntimeError(f"Failed to execute wg command: {e.stderr.strip()}")

    @staticmethod
    def generate_keypair() -> Tuple[str, str]:
        """Genera una coppia di chiavi privata e pubblica per WireGuard."""
        private_key = WireGuardManager._run_wg_command(['genkey'])
        public_key = WireGuardManager._run_wg_command(['pubkey'], input=private_key)
        return private_key, public_key

    @staticmethod
    def generate_psk() -> str:
        """Genera una PresharedKey per WireGuard."""
        return WireGuardManager._run_wg_command(['genpsk'])

    @staticmethod
    def create_interface_config(instance_name: str, listen_port: int, private_key: str, address: str) -> str:
        """
        Genera il contenuto iniziale del file di configurazione dell'interfaccia server WireGuard.
        Non include ancora i peer.
        """
        config_content = f"""[Interface]
Address = {address}
ListenPort = {listen_port}
PrivateKey = {private_key}
SaveConfig = false
"""
        return config_content

    @staticmethod
    def add_peer_to_interface_config(config_file_path: str, public_key: str, psk: str, allowed_ips: str, comment: str = ""):
        """
        Aggiunge un peer a un file di configurazione WireGuard esistente.
        Questo metodo appende il peer al file.
        """
        peer_config = f"""
[Peer]
# {comment}
PublicKey = {public_key}
PresharedKey = {psk}
AllowedIPs = {allowed_ips}
"""
        try:
            with open(config_file_path, "a") as f:
                f.write(peer_config)
            logger.info(f"Peer con chiave pubblica {public_key[:8]}... aggiunto a {config_file_path}")
        except IOError as e:
            logger.error(f"Impossibile scrivere il file di configurazione WireGuard {config_file_path}: {e}")
            raise RuntimeError(f"Failed to write WireGuard config file: {e}")

    @staticmethod
    def remove_peer_from_interface_config(config_file_path: str, public_key: str):
        """
        Rimuove un peer da un file di configurazione WireGuard basandosi sulla chiave pubblica.
        """
        try:
            with open(config_file_path, "r") as f:
                lines = f.readlines()
            
            new_lines = []
            current_block = []
            block_contains_target = False
            
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("[Peer]") or stripped.startswith("[Interface]"):
                    # Flush previous block (if any) if it wasn't the target
                    if current_block and not block_contains_target:
                        new_lines.extend(current_block)
                    
                    # Start new block
                    current_block = [line]
                    block_contains_target = False
                else:
                    current_block.append(line)
                    if f"PublicKey = {public_key}" in stripped: # More precise match
                        block_contains_target = True

            # Flush last block
            if current_block and not block_contains_target:
                new_lines.extend(current_block)

            with open(config_file_path, "w") as f:
                f.writelines(new_lines)
            logger.info(f"Peer con chiave pubblica {public_key[:8]}... rimosso da {config_file_path}")

        except IOError as e:
            logger.error(f"Impossibile leggere/scrivere il file di configurazione WireGuard {config_file_path}: {e}")
            raise RuntimeError(f"Failed to modify WireGuard config file: {e}")
        except Exception as e:
            logger.error(f"Errore generico durante la rimozione del peer: {e}")
            raise RuntimeError(f"Failed to remove peer: {e}")

    @staticmethod
    def hot_reload_interface(interface_name: str):
        """
        Applica le modifiche a un'interfaccia WireGuard senza riavviare il servizio.
        Utilizza 'wg syncconf' con l'output di 'wg-quick strip'.
        """
        config_file_path = f"/etc/wireguard/{interface_name}.conf"
        try:
            # 1. Strip config (remove Address, DNS, etc. which wg doesn't understand)
            stripped = subprocess.run(
                ['wg-quick', 'strip', config_file_path],
                check=True,
                capture_output=True,
                text=True
            )
            stripped_config = stripped.stdout

            # 2. Sync config via stdin
            subprocess.run(
                ['wg', 'syncconf', interface_name, '/dev/stdin'],
                input=stripped_config,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Interfaccia WireGuard '{interface_name}' ricaricata a caldo.")
        except FileNotFoundError:
            logger.error("Comandi 'wg' o 'wg-quick' non trovati.")
            raise RuntimeError("WireGuard tools not found.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Errore nel ricaricamento a caldo dell'interfaccia '{interface_name}': {e.stderr.strip()}")
            raise RuntimeError(f"Failed to hot-reload WireGuard interface: {e.stderr.strip()}")

    @staticmethod
    def get_interface_status(interface_name: str) -> bool:
        """Verifica se l'interfaccia WireGuard è attiva."""
        try:
            # wg show wg0 (returns 0 if interface exists and is up)
            subprocess.run(['wg', 'show', interface_name], check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False
        except FileNotFoundError:
            logger.error("Comando 'wg' non trovato.")
            return False
