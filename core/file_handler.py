"""File CRUD handlers for Sigma Studio."""
import os
import json
import subprocess
from core.logger import get_logger

log = get_logger(__name__)

def handle_get_file(self):
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        path = query.get('path', [None])[0]
        if not path or not self._is_path_allowed(path) or not os.path.exists(path):
            return self.send_json_response({"success": False, "error": "Path invalido o non consentito"}, 400)
        with open(path, 'r', encoding='utf-8') as fh:
            self.send_json_response({"success": True, "content": fh.read()})
    except Exception as exc:
        log.error("handle_get_file: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_create_file(self):
    try:
        req = self.read_json_body()
        path = req.get('path')
        if not path or not self._is_path_allowed(path):
            return self.send_json_response({"error": "Path invalido o non consentito"}, 400)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(req.get('content', ''))
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_create_file: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_delete_file(self):
    try:
        req = self.read_json_body()
        path = req.get('path')
        if not path or not self._is_path_allowed(path) or not os.path.exists(path):
            return self.send_json_response({"error": "Path invalido o non consentito"}, 400)
        os.remove(path)
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_delete_file: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def _parse_multipart(self):
    """Parse multipart/form-data body."""
    ct = self.headers.get('Content-Type', '')
    boundary = None
    for part in ct.split(';'):
        part = part.strip()
        if part.startswith('boundary='):
            boundary = part[len('boundary='):]
            if boundary.startswith('"') and boundary.endswith('"'):
                boundary = boundary[1:-1]
    if not boundary:
        raise ValueError("No boundary found in Content-Type")
    content_length = int(self.headers.get('Content-Length', 0))
    body = self.rfile.read(content_length)
    parts = body.split(('--' + boundary).encode())
    result = {}
    for part in parts:
        if part.strip() in (b'', b'--', b'--\r\n'):
            continue
        header_end = part.find(b'\r\n\r\n')
        if header_end == -1:
            continue
        header_bytes = part[:header_end]
        value_bytes = part[header_end + 4:]
        if value_bytes.endswith(b'\r\n'):
            value_bytes = value_bytes[:-2]
        if value_bytes.endswith(b'--\r\n'):
            value_bytes = value_bytes[:-4]
        headers_text = header_bytes.decode('utf-8', errors='replace')
        disp = None
        for line in headers_text.split('\r\n'):
            if line.lower().startswith('content-disposition:'):
                disp = line
        if not disp:
            continue
        name = None
        filename = None
        for attr in disp.split(';'):
            attr = attr.strip()
            if attr.startswith('name='):
                name = attr[5:].strip('"')
            elif attr.startswith('filename='):
                filename = attr[9:].strip('"')
        if name == 'file' and filename:
            result['file'] = {'filename': filename, 'data': value_bytes}
        elif name:
            result[name] = value_bytes.decode('utf-8', errors='replace')
    return result


def handle_upload_file(self):
    try:
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            return self.send_json_response({"error": "Content-Type must be multipart/form-data"}, 400)
        parsed = _parse_multipart(self)
        file_item = parsed.get('file')
        folder = parsed.get('folder')
        file_type = parsed.get('type')
        if not file_item or not folder or not file_type:
            return self.send_json_response({"error": "Missing file, folder, or type fields"}, 400)
        filename = file_item['filename']
        if '..' in folder or '..' in filename:
            return self.send_json_response({"error": "Invalid path"}, 400)
        if not self._is_path_allowed(folder):
            return self.send_json_response({"error": "Folder non consentito (deve essere in data/)"}, 400)
        if file_type == 'whitepaper':
            target_sub = 'docs'
            if not filename.upper().startswith('WHITEPAPER_'):
                filename = 'WHITEPAPER_' + filename
        else:
            target_sub = file_type
        dest_dir = os.path.join(folder, target_sub)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        with open(dest_path, 'wb') as f:
            f.write(file_item['data'])
        self.send_json_response({"success": True, "path": dest_path.replace('\\', '/')})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_run_test(self):
    try:
        p = self.read_json_body().get('script_path')
        if not p or not self._is_path_allowed(p):
            return self.send_json_response({"error": "Path invalido o non consentito"}, 400)
        if not os.path.exists(p):
            return self.send_json_response({"error": f"File non trovato: {p}"}, 400)
        cmd = ["python", "-u", p] if p.endswith('.py') else ["node", p]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        self.send_json_response({"stdout": res.stdout, "stderr": res.stderr, "exit_code": res.returncode})
    except Exception as exc:
        log.error("handle_run_test: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_api_action(self):
    try:
        import re
        from core.ai_providers import load_ai_config, resolve_provider_config, call_ai_model
        
        req = self.read_json_body()
        action = req.get("action", "create_file")
        path = req.get("path")
        model_name = req.get("model")
        role = req.get("role", "code_architect")
        prompt = req.get("prompt", "").strip()
        existing_content = req.get("existing_content", "").strip()
        
        if not path or not self._is_path_allowed(path):
            return self.send_json_response({"error": "Path invalido o non consentito"}, 400)
            
        if not prompt:
            return self.send_json_response({"error": "Prompt vuoto non consentito"}, 400)
            
        filename = os.path.basename(path)
        
        # Load AI configuration
        ai_cfg = load_ai_config()
        if not model_name:
            model_name = ai_cfg.get("active_model", "llama3.2")
            
        provider_key, ac = resolve_provider_config(model_name)
        
        endpoint = ac.get("endpoint", "http://localhost:11434/api/chat")
        api_url = ac.get("api_url", "")
        api_key = ac.get("api_key", "")
        temperature = ac.get("temperature", 0.7)
        max_tokens = ac.get("max_tokens", 4096)
        top_p = ac.get("top_p", 0.9)
        request_timeout = ac.get("timeout", 300)
        
        ROLE_PROMPTS = {
            "math1": "Sei Math Architect, un matematico esperto in logica formale e dimostrazioni. Usa LaTeX per formattare tutte le equazioni matematiche.",
            "code_architect": "Sei Code Architect, un ingegnere del software esperto in progettazione di sistemi, refactoring e scrittura di codice pulito ed efficiente.",
            "test-engineer": "Sei Test Engineer, un esperto in test di integrazione e unit test in Python e JavaScript. Concentrati sulla robustezza e sulla copertura del codice.",
            "viz-designer": "Sei Viz Designer, un esperto nello sviluppo di visualizzazioni interattive basate su HTML5 e D3.js. Usa sempre layout responsive e tema scuro.",
            "proof-reviewer": "Sei Proof Reviewer, un recensore critico che analizza codice e logiche matematiche alla ricerca di vulnerabilità, errori di calcolo e bug."
        }
        
        system_instruction = (
            f"{ROLE_PROMPTS.get(role, 'Sei un assistente esperto.')}\n"
            f"Il tuo compito è scrivere il contenuto per il file: '{filename}'.\n"
            f"RELEVANTE: Sei inserito all'interno della directory '{os.path.dirname(path)}'.\n"
            f"REGOLA FONDAMENTALE: Restituisci SOLO ed esclusivamente il contenuto grezzo del file. Non includere presentazioni, spiegazioni testuali all'inizio o alla fine, o delimitatori di blocco markdown (es. non racchiudere l'intero output in ``` o ```markdown). Scrivi direttamente il codice o il testo del file."
        )
        
        messages = [
            {"role": "system", "content": system_instruction},
        ]
        
        if existing_content:
            messages.append({"role": "user", "content": f"Contenuto attuale del file:\n{existing_content}\n\nIstruzioni per la modifica:\n{prompt}"})
        else:
            messages.append({"role": "user", "content": f"Istruzioni di creazione del file:\n{prompt}"})
            
        content, reasoning, error = call_ai_model(
            messages, ai_cfg, model_name, provider_key, endpoint,
            api_url, api_key, temperature, max_tokens, top_p, request_timeout
        )
        
        if error:
            return self.send_json_response({"error": f"Errore chiamata AI: {error}"}, 500)
            
        if not content:
            return self.send_json_response({"error": "Il modello AI ha restituito un output vuoto"}, 500)
            
        # Clean markdown code wrapper blocks if returned
        content = content.strip()
        match = re.match(r"^```[a-zA-Z0-9_-]*\n(.*)\n```$", content, re.DOTALL)
        if match:
            content = match.group(1).strip()
        elif content.startswith("```") and content.endswith("```"):
            content = content[3:-3].strip()
            
        # Write to destination
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
            
        self.send_json_response({"success": True, "path": path.replace('\\', '/')})
    except Exception as exc:
        log.error("handle_api_action: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_rename_file(self):
    try:
        import shutil
        req = self.read_json_body()
        old_path = req.get("old_path")
        new_path = req.get("new_path")
        
        if not old_path or not self._is_path_allowed(old_path) or not os.path.exists(old_path):
            return self.send_json_response({"error": "Sorgente non valida o non consentita"}, 400)
            
        if not new_path or not self._is_path_allowed(new_path):
            return self.send_json_response({"error": "Destinazione non valida o non consentita"}, 400)
            
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(os.path.abspath(new_path)), exist_ok=True)
        
        # Move file
        shutil.move(old_path, new_path)
        
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_rename_file: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)