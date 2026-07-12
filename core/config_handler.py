"""AI Config handlers for Sigma Studio."""
import os
import json
import subprocess
import tempfile
import re
import shutil
from core.ai_providers import load_ai_config, save_ai_config
from core.logger import get_logger

log = get_logger(__name__)


def handle_api_config_get(self):
    ai_cfg = load_ai_config()
    safe_cfg = {}
    safe_cfg['active_provider'] = ai_cfg.get('active_provider', 'ollama')
    safe_cfg['active_model'] = ai_cfg.get('active_model', 'llama3.2')
    safe_cfg['providers'] = {}
    for pk, pv in ai_cfg.get('providers', {}).items():
        safe_cfg['providers'][pk] = {k: v for k, v in pv.items() if k != 'api_key'}
        safe_cfg['providers'][pk]['has_api_key'] = bool(pv.get('api_key'))
    active_prov = safe_cfg['providers'].get(safe_cfg['active_provider'], {})
    safe_cfg['provider'] = safe_cfg['active_provider']
    safe_cfg['model'] = safe_cfg['active_model']
    safe_cfg['endpoint'] = active_prov.get('endpoint', '')
    safe_cfg['api_url'] = active_prov.get('api_url', '')
    safe_cfg['has_api_key'] = active_prov.get('has_api_key', False)
    for k in ('temperature', 'max_tokens', 'top_p', 'top_k', 'repeat_penalty', 'num_ctx', 'seed'):
        safe_cfg[k] = active_prov.get(k, {'temperature': 0.7, 'max_tokens': 8192, 'top_p': 0.9,
                'top_k': 40, 'repeat_penalty': 1.1, 'num_ctx': 32768, 'seed': 0}[k])
    # Resolve manifesto for the active model
    from core.chat_handler import _resolve_manifesto_for_model
    manifesto_path = _resolve_manifesto_for_model(safe_cfg.get('active_model', ''))
    safe_cfg['manifesto'] = {
        'path': manifesto_path.replace('\\', '/'),
        'name': os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else '',
        'exists': bool(manifesto_path) and os.path.exists(manifesto_path)
    }
    self.send_json_response({"success": True, "config": safe_cfg})


def handle_api_config_post(self):
    try:
        req = self.read_json_body()
        ai_cfg = load_ai_config()
        if 'providers' in req:
            for pk, pv in req['providers'].items():
                if pk in ai_cfg.get('providers', {}):
                    for k, v in pv.items():
                        if k == 'api_key' and not v:
                            continue
                        ai_cfg['providers'][pk][k] = v
        for k in ('active_provider', 'active_model'):
            if k in req:
                ai_cfg[k] = req[k]
        if 'provider' in req and req['provider']:
            ai_cfg['active_provider'] = req['provider']
        if 'model' in req and req['model']:
            ai_cfg['active_model'] = req['model']
        active_provider = ai_cfg.get('active_provider', 'ollama')
        if active_provider in ai_cfg.get('providers', {}):
            prov = ai_cfg['providers'][active_provider]
            for k in ('endpoint', 'api_url', 'temperature', 'max_tokens', 'top_p', 'top_k', 'repeat_penalty', 'num_ctx', 'seed'):
                if k in req:
                    prov[k] = req[k]
            if 'api_key' in req and req['api_key']:
                prov['api_key'] = req['api_key']
            if 'model' in req and req['model']:
                prov['model'] = req['model']
        save_ai_config(ai_cfg)
        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_api_config_post: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_api_ollama_models(self):
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        models = []
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:
                if line.strip():
                    parts = line.split()
                    if parts:
                        name = parts[0]
                        size_str = parts[2] if len(parts) > 2 else '?'
                        models.append({"name": name, "size": size_str})
        self.send_json_response({"success": True, "models": models})
    except FileNotFoundError:
        return self.send_json_response({"success": False, "models": [], "error": "ollama not found"})
    except Exception as e:
        self.send_json_response({"success": False, "models": [], "error": str(e)})


def handle_api_create_model(self):
    try:
        req = self.read_json_body()
        model_name = req.get("name", "").strip()
        modelfile_content = req.get("modelfile", "").strip()
        if not model_name or not modelfile_content:
            return self.send_json_response({"error": "name e modelfile sono obbligatori"}, 400)
        if not re.match(r'^[a-zA-Z0-9_-]+$', model_name):
            return self.send_json_response({"error": "Nome modello non valido. Usa solo lettere, numeri, trattini e underscore."}, 400)
        tmp_dir = tempfile.mkdtemp(prefix='sigma_modelfile_')
        mf_path = os.path.join(tmp_dir, 'Modelfile')
        try:
            with open(mf_path, 'w', encoding='utf-8') as f:
                f.write(modelfile_content)
            result = subprocess.run(['ollama', 'create', model_name, '-f', mf_path],
                                    capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace')
            if result.returncode == 0:
                return self.send_json_response({"success": True, "model": model_name, "message": f"Modello '{model_name}' creato!"})
            return self.send_json_response({"error": f"Ollama error: {result.stderr or result.stdout}"}, 500)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except FileNotFoundError as exc:
        log.error("handle_api_create_model: %s", exc)
        return self.send_json_response({"error": "Ollama non trovato."}, 500)
    except subprocess.TimeoutExpired as exc:
        log.error("handle_api_create_model: %s", exc)
        return self.send_json_response({"error": "Timeout (120s)."}, 500)
    except Exception as exc:
        log.error("handle_api_create_model: %s", exc)
        return self.send_json_response({"error": str(exc)}, 500)