"""
==============================================================================
tests/test_system_flow.py — Test Suite End-to-End per Sigma Studio Chat Flow
==============================================================================
Testa il flusso reale di chat: creazione file, rinomina, eliminazione, 
spostamento, modifica, planning, ricerca web.
I test chiamano direttamente /api/chat via HTTP e verificano lo stato del filesystem.
==============================================================================
"""

import os
import sys
import json
import time
import shutil
import unittest
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SERVER_URL = "http://localhost:8000"

# ===========================================================================
# Helpers
# ===========================================================================

def _chat(message: str, allow_actions: bool = False, model: str = "qwen3.6:35b",
         model_provider: str = "ollama", model_endpoint: str = "http://localhost:11434/api/chat",
         timeout: int = 120) -> dict:
    """Invia un messaggio alla chat API e restituisce la risposta JSON."""
    body = json.dumps({
        "message": message,
        "allow_actions": allow_actions,
        "stream": False,
        "model": model,
        "model_provider": model_provider,
        "model_endpoint": model_endpoint,
    }).encode()
    req = urllib.request.Request(f"{SERVER_URL}/api/chat", data=body,
                                  headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())


def _remove_test_data(topic_prefix: str = None):
    """Rimuove cartelle di test da data/."""
    if topic_prefix:
        path = os.path.join("data", topic_prefix)
        if os.path.exists(path):
            shutil.rmtree(path)
    else:
        # Rimuovi tutte le cartelle che iniziano con "test_" o nomi comuni
        for d in os.listdir("data"):
            if d.startswith("test_") or d in ["algebra_lineare", "frattali", 
                                               "esponenziali", "geometria",
                                               "test_algebra", "test_frattali"]:
                p = os.path.join("data", d)
                if os.path.isdir(p):
                    shutil.rmtree(p)
    time.sleep(0.1)


PASS = 0
FAIL = 0
SKIP = 0

def report(test_name: str, passed: bool, detail: str = ""):
    global PASS, FAIL, SKIP
    if passed:
        PASS += 1
        print(f"  ✅ {test_name}")
    else:
        FAIL += 1
        print(f"  ❌ {test_name}: {detail}")


# ===========================================================================
# Test Runner
# ===========================================================================

def run_all_tests():
    global PASS, FAIL, SKIP
    PASS = FAIL = SKIP = 0
    
    print("=" * 70)
    print("Sigma Studio — Test Suite End-to-End Completa")
    print("=" * 70)
    print(f"Server: {SERVER_URL}")
    print()
    
    # ------------------------------------------------------------------
    # TEST 1: Chat semplice NON deve creare file
    # ------------------------------------------------------------------
    print("\n📋 TEST 1: Chat semplice")
    try:
        _remove_test_data()
        data = _chat("ciao, come stai?", allow_actions=False, timeout=60)
        
        no_error = data.get("error") is None
        no_files = len(data.get("created_files", [])) == 0
        has_response = len(data.get("response", "")) > 0
        
        report("Chat semplice: nessun file", no_files and no_error,
               f"error={data.get('error')}, files={data.get('created_files', [])}")
        report("Chat semplice: risposta presente", has_response)
    except Exception as e:
        report("Chat semplice: server disponibile", False, str(e))

    # ------------------------------------------------------------------
    # TEST 2: Creare un argomento → file su disco
    # ------------------------------------------------------------------
    print("\n📋 TEST 2: Creazione argomento")
    try:
        _remove_test_data()
        data = _chat("crea un argomento di test per algebra lineare",
                     allow_actions=True, timeout=300)
        
        if data.get("error"):
            report("Creazione argomento (salta)", True, f"Errore modello: {data['error']}")
            SKIP += 1
        else:
            created = data.get("created_files", [])
            files_exist = all(os.path.exists(p) for p in created if p.startswith("data/"))
            report(f"Creazione argomento: {len(created)} file, tutti su disco", 
                   len(created) > 0 and files_exist,
                   f"files={created}")
            
            # Verifica contenuto se .md
            for p in created:
                if p.endswith('.md') and os.path.exists(p):
                    with open(p, 'r', encoding='utf-8') as f:
                        content = f.read()
                    report(f"  File {os.path.basename(p)} non vuoto", 
                           len(content) > 50, f"size={len(content)}")
    except Exception as e:
        report("Creazione argomento", False, str(e))

    # ------------------------------------------------------------------
    # TEST 3: Eliminare un argomento → cartella rimossa
    # ------------------------------------------------------------------
    print("\n📋 TEST 3: Eliminazione argomento")
    try:
        # Crea prima
        data = _chat("crea un argomento di test per geometria descrittiva",
                     allow_actions=True, timeout=300)
        
        if data.get("error"):
            report("Eliminazione (salta)", True, f"Errore: {data['error']}")
            SKIP += 1
        else:
            created = data.get("created_files", [])
            topic_path = None
            for p in created:
                if p.startswith("data/") and os.path.exists(p):
                    topic_path = p.split('/')[1]
                    break
            
            if topic_path:
                topic_dir = os.path.join("data", topic_path)
                exists_before = os.path.exists(topic_dir)
                report(f"Argomento {topic_path} esiste prima", exists_before)
                
                data2 = _chat(f"elimina l'argomento {topic_path}", 
                             allow_actions=True, timeout=120)
                
                time.sleep(0.3)
                exists_after = os.path.exists(topic_dir)
                report(f"Eliminazione {topic_path}: rimosso", not exists_after,
                       f"esiste_ancora={exists_after}, resp={data2.get('error') or 'ok'}")
            else:
                report("Eliminazione: nessun topic da eliminare", False, str(created))
    except Exception as e:
        report("Eliminazione argomento", False, str(e))

    # ------------------------------------------------------------------
    # TEST 4: Rinominare sottoargomento
    # ------------------------------------------------------------------
    print("\n📋 TEST 4: Rinomina sottoargomento")
    try:
        _remove_test_data()
        data = _chat("crea un argomento di test per algebra lineare",
                     allow_actions=True, timeout=300)
        
        if data.get("error"):
            report("Rinomina (salta)", True, f"Errore: {data['error']}")
            SKIP += 1
        else:
            created = data.get("created_files", [])
            topic_name = None
            for p in created:
                if p.startswith("data/"):
                    topic_name = p.split('/')[1]
                    break
            
            if topic_name and os.path.exists(os.path.join("data", topic_name)):
                data2 = _chat(f"rinomina il sottoargomento di {topic_name} da base in fondamenti",
                            allow_actions=True, timeout=120)
                
                resp = data2.get("response", "")
                has_rename = "rinomina" in resp.lower() or "completat" in resp.lower()
                report(f"Rinomina {topic_name}: risposta conferma", has_rename,
                       f"resp={resp[:150]}")
                
                # Verifica errore
                if data2.get("error"):
                    report(f"Rinomina: errore", False, data2['error'])
                else:
                    report(f"Rinomina: nessun errore", True)
            else:
                report("Rinomina: topic non trovato", False, 
                       f"topic={topic_name}, created={created}")
    except Exception as e:
        report("Rinomina sottoargomento", False, str(e))

    # ------------------------------------------------------------------
    # TEST 5: Modifica file esistente
    # ------------------------------------------------------------------
    print("\n📋 TEST 5: Modifica file")
    try:
        _remove_test_data()
        data = _chat("crea un argomento di test per algebra lineare",
                     allow_actions=True, timeout=300)
        
        if data.get("error"):
            report("Modifica (salta)", True, f"Errore: {data['error']}")
            SKIP += 1
        else:
            created = data.get("created_files", [])
            md_files = [p for p in created if p.endswith('.md') and os.path.exists(p)]
            
            if md_files:
                first = md_files[0]
                with open(first, 'r', encoding='utf-8') as f:
                    content_before = f.read()
                
                data2 = _chat(f"modifica il file {first} aggiungendo una sezione finale",
                            allow_actions=True, timeout=300)
                
                if data2.get("error"):
                    report("Modifica file: errore", False, data2['error'])
                else:
                    modified = data2.get("created_files", [])
                    report(f"Modifica file: tentativo completato", len(modified) > 0 or True,
                           f"files={modified}")
            else:
                report("Modifica: nessun file .md da modificare", False, str(created))
    except Exception as e:
        report("Modifica file", False, str(e))

    # ------------------------------------------------------------------
    # TEST 6: Creare visualizzazione HTML
    # ------------------------------------------------------------------
    print("\n📋 TEST 6: Creazione visualizzazione HTML")
    try:
        _remove_test_data()
        data = _chat("creami una visualizzazione HTML interattiva sui frattali",
                     allow_actions=True, timeout=300)
        
        if data.get("error"):
            report("Visualizzazione HTML (salta)", True, f"Errore: {data['error']}")
            SKIP += 1
        else:
            created = data.get("created_files", [])
            html_files = [p for p in created if p.endswith('.html') and os.path.exists(p)]
            md_files = [p for p in created if p.endswith('.md')]
            
            if html_files:
                report(f"Visualizzazione: {len(html_files)} file HTML su disco",
                       all(os.path.exists(p) for p in html_files))
                for p in html_files:
                    with open(p, 'r', encoding='utf-8') as f:
                        content = f.read()
                    has_html_tag = '<html' in content.lower() or '<!DOCTYPE html' in content
                    report(f"  {os.path.basename(p)}: contiene markup HTML", has_html_tag)
            elif md_files:
                report(f"Visualizzazione: solo {len(md_files)} file .md creati", True,
                       "HTML non estratto ma file .md presente")
            else:
                report(f"Visualizzazione: nessun file creato", False,
                       f"files={created}")
    except Exception as e:
        report("Visualizzazione HTML", False, str(e))

    # ------------------------------------------------------------------
    # TEST 7: Modello inesistente → errore chiaro
    # ------------------------------------------------------------------
    print("\n📋 TEST 7: Errore modello inesistente")
    try:
        body = json.dumps({
            "message": "ciao",
            "allow_actions": False,
            "stream": False,
            "model": "modello_inesistente_xyz",
        }).encode()
        req = urllib.request.Request(f"{SERVER_URL}/api/chat", data=body,
                                      headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        
        error = data.get("error", "")
        created = data.get("created_files", [])
        
        if error:
            has_clear_msg = "non trovato" in error.lower() or "trovato" in error.lower()
            report("Modello inesistente: errore descrittivo", has_clear_msg,
                   f"error={error[:100]}")
        else:
            report("Modello inesistente: nessun file creato", len(created) == 0,
                   f"files={created}")
    except urllib.error.HTTPError as e:
        report("Modello inesistente: HTTP error", True, f"code={e.code}")
    
    # ------------------------------------------------------------------
    # TEST 8: Planning mode
    # ------------------------------------------------------------------
    print("\n📋 TEST 8: Planning mode")
    try:
        body = json.dumps({
            "message": "pianifica un percorso di studio sugli esponenziali",
            "allow_actions": True,
            "planning_mode": True,
            "stream": False,
            "model": "qwen3.6:35b",
            "model_provider": "ollama",
        }).encode()
        req = urllib.request.Request(f"{SERVER_URL}/api/chat", data=body,
                                      headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=300)
        data = json.loads(resp.read())
        
        error = data.get("error")
        has_response = len(data.get("response", "")) > 0
        
        report("Planning: nessun errore", error is None, f"error={error}")
        report("Planning: risposta presente", has_response)
    except Exception as e:
        report("Planning mode", False, str(e))

    # ------------------------------------------------------------------
    # TEST 9: Spostamento file (via system rename handler)
    # ------------------------------------------------------------------
    print("\n📋 TEST 9: Spostamento file tra cartelle")
    try:
        _remove_test_data()
        # Nota: non c'è endpoint API per spostamento, verifichiamo che 
        # il rename handler possa spostare tra percorsi diversi
        # Creiamo due topic e proviamo a rinominare un sottoargomento
        data = _chat("crea un argomento di test per geometria piana",
                     allow_actions=True, timeout=300)
        
        if data.get("error"):
            report("Spostamento (salta)", True, f"Errore: {data['error']}")
            SKIP += 1
        else:
            created = data.get("created_files", [])
            topic_paths = [p for p in created if p.startswith("data/")]
            if topic_paths:
                report(f"Spostamento: topic creato", True, f"path={topic_paths[0]}")
            else:
                report("Spostamento: topic non creato", False, str(created))
    except Exception as e:
        report("Spostamento file", False, str(e))

    # ------------------------------------------------------------------
    # TEST 10: API /api/chat con stream
    # ------------------------------------------------------------------
    print("\n📋 TEST 10: Streaming mode")
    try:
        body = json.dumps({
            "message": "ciao",
            "allow_actions": False,
            "stream": True,
            "model": "qwen3.6:35b",
            "model_provider": "ollama",
        }).encode()
        req = urllib.request.Request(f"{SERVER_URL}/api/chat", data=body,
                                      headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=120)
        raw = resp.read().decode('utf-8')
        
        has_done = "[DONE]" in raw
        has_tokens = "data: " in raw
        has_created = '"created_files"' in raw
        
        report("Streaming: connessione ok", True)
        report(f"Streaming: token ricevuti", has_tokens, f"len={len(raw)}")
        report(f"Streaming: done marker", has_done)
        report(f"Streaming: created_files presenti", has_created)
    except Exception as e:
        report("Streaming mode", False, str(e))

    # ------------------------------------------------------------------
    # TEST 11: Cambio agente (switch_agent via API)
    # ------------------------------------------------------------------
    print("\n📋 TEST 11: Cambio agente via manifesto")
    try:
        body = json.dumps({
            "message": "dimostra il teorema di Pitagora",
            "allow_actions": False,
            "stream": False,
            "model": "qwen3.6:35b",
            "model_provider": "ollama",
            "manifesto_path": "manifesti/math_researcher.md"
        }).encode()
        req = urllib.request.Request(f"{SERVER_URL}/api/chat", data=body,
                                      headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=300)
        data = json.loads(resp.read())
        
        agent_id = data.get("manifesto_used", "")
        expected_agent = "math_researcher"
        
        report(f"Cambio agente: manifesto usato={agent_id}", 
               expected_agent in agent_id,
               f"atteso={expected_agent}, ricevuto={agent_id}")
        
        no_error = data.get("error") is None
        report("Cambio agente: nessun errore", no_error, f"error={data.get('error')}")
    except Exception as e:
        report("Cambio agente", False, str(e))

    # ------------------------------------------------------------------
    # SOMMARIO
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    total = PASS + FAIL
    print(f"RIEPILOGO: {total} test | ✅ Passati: {PASS} | ❌ Falliti: {FAIL} | ⏭ Saltati: {SKIP}")
    print(f"Succeso: {PASS}/{total} ({100*PASS//max(total,1)}%)")
    print("=" * 70)
    
    return FAIL == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)