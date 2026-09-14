# ==============================================================================
# core/harness/docker_fs.py — Esplorazione e I/O Filesystem nei Container Docker
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Consente a Developer Studio di navigare e modificare i file dentro i container Docker attivi."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from core.harness.esecutori import docker_disponibile, trova_docker, _ambiente_per_docker

log = get_logger("docker_fs")


def container_attivi() -> List[Dict[str, Any]]:
    """Elenco dei container Docker attualmente in esecuzione con dettagli di mount."""
    disponibile, _ = docker_disponibile()
    if not disponibile:
        return []

    eseguibile = trova_docker()
    env = _ambiente_per_docker()
    risultati: List[Dict[str, Any]] = []

    try:
        esito = subprocess.run(
            [eseguibile, "ps", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=8, env=env,
        )
        if esito.returncode != 0 or not esito.stdout.strip():
            return []

        for riga in esito.stdout.strip().splitlines():
            if not riga.strip():
                continue
            try:
                dati = json.loads(riga.strip())
                cid = dati.get("ID", "")
                cname = dati.get("Names", cid[:12])
                image = dati.get("Image", "")

                # Ispezione per i volumi / mount bind verso l'host
                mounts = []
                try:
                    ispezione = subprocess.run(
                        [eseguibile, "inspect", cid, "--format", "{{json .Mounts}}"],
                        capture_output=True, text=True, timeout=5, env=env,
                    )
                    if ispezione.returncode == 0 and ispezione.stdout.strip():
                        mounts = json.loads(ispezione.stdout.strip())
                except Exception as exc_insp:
                    log.debug("[DockerFS] Errore ispezione mount per %s: %s", cid, exc_insp)

                risultati.append({
                    "id": cid,
                    "name": cname,
                    "image": image,
                    "status": dati.get("Status", ""),
                    "ports": dati.get("Ports", ""),
                    "mounts": mounts if isinstance(mounts, list) else [],
                })
            except Exception as exc_parse:
                log.debug("[DockerFS] Errore parsing riga ps: %s", exc_parse)
    except Exception as exc:
        log.warning("[DockerFS] Errore esecuzione docker ps: %s", exc)

    return risultati


def parse_docker_uri(uri: str) -> Tuple[Optional[str], str]:
    """Scompone un URI tipo 'docker://<container_id_o_nome>/percorso' in (container, percorso)."""
    if not uri.startswith("docker://"):
        return None, uri
    senza_prefisso = uri[len("docker://"):]
    parti = senza_prefisso.split("/", 1)
    container_id = parti[0]
    percorso_interno = "/" + parti[1] if len(parti) > 1 and parti[1] else "/"
    return container_id, percorso_interno


def get_docker_tree(container_id: str, subpath: str = "/", max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
    """Costruisce ricorsivamente l'albero delle directory all'interno del container Docker."""
    eseguibile = trova_docker()
    env = _ambiente_per_docker()
    norm_path = subpath.rstrip("/") if subpath != "/" else "/"

    tree: Dict[str, Any] = {
        "name": norm_path.split("/")[-1] or f"docker:{container_id[:8]}",
        "path": f"docker://{container_id}{norm_path}",
        "is_dir": True,
        "children": [],
    }

    if current_depth >= max_depth:
        tree["has_children"] = True
        return tree

    # Script compatto in shell per elencare cartelle e file con tipo e dimensione
    cmd = (
        f"ls -la '{norm_path}' 2>/dev/null | awk 'NR>3 {{print $1, $5, $9}}'"
    )
    try:
        esito = subprocess.run(
            [eseguibile, "exec", container_id, "sh", "-c", cmd],
            capture_output=True, text=True, timeout=8, env=env,
        )
        if esito.returncode != 0:
            tree["error"] = esito.stderr.strip() or "Accesso negato o percorso inesistente"
            return tree

        for linea in esito.stdout.splitlines():
            parti = linea.strip().split(maxsplit=2)
            if len(parti) < 3:
                continue
            perm, dim_str, nome = parti[0], parti[1], parti[2]
            if nome in (".", "..", ".git", "node_modules", "__pycache__", "proc", "sys", "dev"):
                continue

            is_dir = perm.startswith("d")
            child_path = f"{norm_path}/{nome}".replace("//", "/")
            child_uri = f"docker://{container_id}{child_path}"

            try:
                size_bytes = int(dim_str)
            except ValueError:
                size_bytes = 0

            if is_dir:
                child_tree = get_docker_tree(container_id, child_path, max_depth, current_depth + 1)
                tree["children"].append(child_tree)
            else:
                tree["children"].append({
                    "name": nome,
                    "path": child_uri,
                    "is_dir": False,
                    "size": size_bytes,
                })

        tree["children"].sort(key=lambda x: (not x.get("is_dir", False), x.get("name", "").lower()))
    except Exception as exc:
        log.warning("[DockerFS] Errore lettura albero container %s (%s): %s", container_id, norm_path, exc)
        tree["error"] = str(exc)

    return tree


def read_docker_file(container_id: str, file_path: str) -> Dict[str, Any]:
    """Legge il contenuto di un file dentro il container Docker specificato."""
    eseguibile = trova_docker()
    env = _ambiente_per_docker()

    try:
        esito = subprocess.run(
            [eseguibile, "exec", container_id, "cat", file_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, env=env,
        )
        if esito.returncode != 0:
            return {
                "success": False,
                "error": f"Errore lettura file nel container: {esito.stderr.strip()}",
                "path": f"docker://{container_id}{file_path}",
            }
        return {
            "success": True,
            "path": f"docker://{container_id}{file_path}",
            "filename": file_path.split("/")[-1],
            "content": esito.stdout,
            "is_binary": False,
        }
    except Exception as exc:
        log.warning("[DockerFS] Eccezione lettura %s in %s: %s", file_path, container_id, exc)
        return {"success": False, "error": str(exc), "path": f"docker://{container_id}{file_path}"}


def write_docker_file(container_id: str, file_path: str, content: str) -> Dict[str, Any]:
    """Scrive il contenuto in un file dentro il container Docker specificato."""
    eseguibile = trova_docker()
    env = _ambiente_per_docker()

    try:
        # Crea la directory genitore se non esiste
        cartella = str(Path(file_path).parent).replace("\\", "/")
        if cartella and cartella != "/":
            subprocess.run(
                [eseguibile, "exec", container_id, "mkdir", "-p", cartella],
                capture_output=True, text=True, timeout=10, env=env,
            )

        processo = subprocess.Popen(
            [eseguibile, "exec", "-i", container_id, "sh", "-c", f"cat > '{file_path}'"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env,
        )
        _, stderr = processo.communicate(input=content, timeout=15)
        if processo.returncode != 0:
            return {
                "success": False,
                "error": f"Errore scrittura nel container: {stderr.strip()}",
                "path": f"docker://{container_id}{file_path}",
            }
        return {
            "success": True,
            "path": f"docker://{container_id}{file_path}",
            "message": "File salvato nel container Docker",
        }
    except Exception as exc:
        log.warning("[DockerFS] Eccezione scrittura %s in %s: %s", file_path, container_id, exc)
        return {"success": False, "error": str(exc), "path": f"docker://{container_id}{file_path}"}


def avvia_container(container_id: str) -> Dict[str, Any]:
    """Avvia un container Docker esistente (stato exited o arrestato)."""
    disponibile, err = docker_disponibile()
    if not disponibile:
        return {"success": False, "error": err}

    eseguibile = trova_docker()
    env = _ambiente_per_docker()
    try:
        esito = subprocess.run(
            [eseguibile, "start", container_id],
            capture_output=True, text=True, timeout=20, env=env,
        )
        if esito.returncode != 0:
            return {"success": False, "error": esito.stderr.strip() or "Errore durante l'avvio del container"}
        return {"success": True, "id": container_id, "message": f"Container {container_id} avviato con successo"}
    except Exception as exc:
        log.warning("[DockerFS] Errore avvio container %s: %s", container_id, exc)
        return {"success": False, "error": str(exc)}


def ferma_container(container_id: str, timeout_sec: int = 10) -> Dict[str, Any]:
    """Arresta un container Docker in esecuzione."""
    disponibile, err = docker_disponibile()
    if not disponibile:
        return {"success": False, "error": err}

    eseguibile = trova_docker()
    env = _ambiente_per_docker()
    try:
        esito = subprocess.run(
            [eseguibile, "stop", "-t", str(timeout_sec), container_id],
            capture_output=True, text=True, timeout=timeout_sec + 15, env=env,
        )
        if esito.returncode != 0:
            return {"success": False, "error": esito.stderr.strip() or "Errore durante l'arresto del container"}
        return {"success": True, "id": container_id, "message": f"Container {container_id} arrestato con successo"}
    except Exception as exc:
        log.warning("[DockerFS] Errore arresto container %s: %s", container_id, exc)
        return {"success": False, "error": str(exc)}


def riavvia_container(container_id: str, timeout_sec: int = 10) -> Dict[str, Any]:
    """Riavvia un container Docker."""
    disponibile, err = docker_disponibile()
    if not disponibile:
        return {"success": False, "error": err}

    eseguibile = trova_docker()
    env = _ambiente_per_docker()
    try:
        esito = subprocess.run(
            [eseguibile, "restart", "-t", str(timeout_sec), container_id],
            capture_output=True, text=True, timeout=timeout_sec + 20, env=env,
        )
        if esito.returncode != 0:
            return {"success": False, "error": esito.stderr.strip() or "Errore durante il riavvio del container"}
        return {"success": True, "id": container_id, "message": f"Container {container_id} riavviato con successo"}
    except Exception as exc:
        log.warning("[DockerFS] Errore riavvio container %s: %s", container_id, exc)
        return {"success": False, "error": str(exc)}


def rimuovi_container(container_id: str, forzato: bool = False) -> Dict[str, Any]:
    """Rimuove un container Docker."""
    disponibile, err = docker_disponibile()
    if not disponibile:
        return {"success": False, "error": err}

    eseguibile = trova_docker()
    env = _ambiente_per_docker()
    cmd = [eseguibile, "rm"]
    if forzato:
        cmd.append("-f")
    cmd.append(container_id)
    try:
        esito = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=env)
        if esito.returncode != 0:
            return {"success": False, "error": esito.stderr.strip() or "Errore durante la rimozione del container"}
        return {"success": True, "id": container_id, "message": f"Container {container_id} rimosso"}
    except Exception as exc:
        log.warning("[DockerFS] Errore rimozione container %s: %s", container_id, exc)
        return {"success": False, "error": str(exc)}


def lancia_container(
    immagine: Optional[str] = None,
    nome: Optional[str] = None,
    workspace_root: Optional[str] = None,
    porte: Optional[List[str]] = None,
    comando: Optional[str] = None,
) -> Dict[str, Any]:
    """Crea e avvia un nuovo container sandbox in background."""
    import re
    disponibile, err = docker_disponibile()
    if not disponibile:
        return {"success": False, "error": err}

    eseguibile = trova_docker()
    env = _ambiente_per_docker()
    img = (immagine or "python:3.12-slim").strip()

    cmd = [eseguibile, "run", "-d"]
    if nome:
        pulito = re.sub(r"[^a-zA-Z0-9_.-]", "_", nome.strip())
        if pulito:
            cmd.extend(["--name", pulito])

    if workspace_root:
        try:
            p_host = str(Path(workspace_root).resolve()).replace("\\", "/")
            cmd.extend(["-v", f"{p_host}:/workspace", "-w", "/workspace"])
        except Exception as exc_p:
            log.warning("[DockerFS] Percorso workspace non valido per mount: %s", exc_p)

    if porte:
        for p in porte:
            p_str = str(p).strip()
            if ":" in p_str:
                cmd.extend(["-p", p_str])

    cmd.append(img)
    if comando:
        cmd.extend(["sh", "-c", comando])
    else:
        # Mantiene il container vivo in background
        cmd.extend(["sh", "-c", "tail -f /dev/null"])

    try:
        esito = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        if esito.returncode != 0:
            return {"success": False, "error": esito.stderr.strip() or "Errore durante il lancio del container"}
        new_id = esito.stdout.strip()[:12]
        return {
            "success": True,
            "id": new_id,
            "name": nome or new_id,
            "image": img,
            "message": f"Container {nome or new_id} lanciato ed attivo con successo.",
        }
    except Exception as exc:
        log.warning("[DockerFS] Errore lancio container %s (%s): %s", nome, img, exc)
        return {"success": False, "error": str(exc)}

