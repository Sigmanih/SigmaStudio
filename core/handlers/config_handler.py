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
    safe_cfg['active_provider'] = ai_cfg.get('active_provider', 'sigma_engine')
    safe_cfg['active_model'] = ai_cfg.get('active_model', 'sigma-native:latest')
    safe_cfg['favorite_model'] = ai_cfg.get('favorite_model', '')
    safe_cfg['favorite_models'] = ai_cfg.get('favorite_models', ([ai_cfg['favorite_model']] if ai_cfg.get('favorite_model') else []))
    
    # Proxy, Network & Port settings
    port_val = ai_cfg.get('provider_server_port') or ai_cfg.get('server_port') or 8000
    try:
        port_val = int(port_val)
    except (ValueError, TypeError):
        port_val = 8000
    host_val = str(ai_cfg.get('provider_server_host') or ai_cfg.get('server_host') or '0.0.0.0')

    safe_cfg['provider_server_port'] = port_val
    safe_cfg['provider_server_host'] = host_val
    safe_cfg['server_port'] = port_val
    safe_cfg['server_host'] = host_val
    safe_cfg['sigma_proxy_alias'] = str(ai_cfg.get('sigma_proxy_alias') or 'sigma')
    safe_cfg['sigma_proxy_model'] = str(ai_cfg.get('sigma_proxy_model') or '')
    
    # SSL / HTTPS settings
    safe_cfg['ssl_enabled'] = bool(ai_cfg.get('ssl_enabled', False))
    safe_cfg['ssl_certfile'] = str(ai_cfg.get('ssl_certfile') or '')
    safe_cfg['ssl_keyfile'] = str(ai_cfg.get('ssl_keyfile') or '')

    # LAN Network detection
    from core.ssl_manager import get_lan_ip, certs_dir
    lan_ip = get_lan_ip()
    safe_cfg['lan_ip'] = lan_ip
    is_ssl = safe_cfg['ssl_enabled']
    proto = "https" if is_ssl else "http"
    safe_cfg['lan_web_url'] = f"{proto}://{lan_ip}:{port_val}"
    safe_cfg['lan_api_url'] = f"{proto}://{lan_ip}:{port_val}/v1"
    
    # Check if SSL certs exist on disk
    default_cert = certs_dir() / "cert.pem"
    default_key = certs_dir() / "key.pem"
    safe_cfg['ssl_cert_exists'] = bool(default_cert.exists() and default_key.exists())

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
        safe_cfg[k] = active_prov.get(k, {'temperature': 0.7, 'max_tokens': 16384, 'top_p': 0.95,
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
        for k in ('active_provider', 'active_model', 'favorite_model', 'favorite_models'):
            if k in req:
                ai_cfg[k] = req[k]
        if 'favorite_models' in req and isinstance(req['favorite_models'], list):
            if req['favorite_models'] and not req.get('favorite_model'):
                ai_cfg['favorite_model'] = req['favorite_models'][0]
        if 'provider' in req and req['provider']:
            ai_cfg['active_provider'] = req['provider']
        if 'model' in req and req['model']:
            ai_cfg['active_model'] = req['model']

        # Persist Proxy, Network, Port & SSL settings
        if 'provider_server_port' in req or 'server_port' in req:
            p_val = req.get('provider_server_port') or req.get('server_port')
            try:
                p_int = int(p_val)
                ai_cfg['provider_server_port'] = p_int
                ai_cfg['server_port'] = p_int
            except (ValueError, TypeError):
                pass
        
        if 'provider_server_host' in req or 'server_host' in req:
            h_val = str(req.get('provider_server_host') or req.get('server_host'))
            ai_cfg['provider_server_host'] = h_val
            ai_cfg['server_host'] = h_val

        if 'sigma_proxy_alias' in req:
            ai_cfg['sigma_proxy_alias'] = str(req['sigma_proxy_alias'])
        if 'sigma_proxy_model' in req:
            ai_cfg['sigma_proxy_model'] = str(req['sigma_proxy_model'])

        if 'ssl_enabled' in req:
            ssl_on = bool(req['ssl_enabled'])
            ai_cfg['ssl_enabled'] = ssl_on
            if ssl_on:
                # Pre-generate SSL certificates if not already generated
                try:
                    from core.ssl_manager import ensure_ssl_certificates
                    ensure_ssl_certificates()
                except Exception as exc:
                    log.warning("Generazione automatica certificati SSL fallita: %s", exc)

        if 'ssl_certfile' in req:
            ai_cfg['ssl_certfile'] = str(req['ssl_certfile'])
        if 'ssl_keyfile' in req:
            ai_cfg['ssl_keyfile'] = str(req['ssl_keyfile'])

        active_provider = ai_cfg.get('active_provider', 'sigma_engine')
        if active_provider in ai_cfg.get('providers', {}):
            prov = ai_cfg['providers'][active_provider]
            for k in ('endpoint', 'api_url', 'temperature', 'max_tokens', 'top_p', 'top_k', 'repeat_penalty', 'num_ctx', 'seed'):
                if k in req:
                    prov[k] = req[k]
            if 'api_key' in req and req['api_key']:
                prov['api_key'] = req['api_key']
            if 'model' in req and req['model']:
                prov['model'] = req['model']

        # Persist to config.json
        save_ai_config(ai_cfg)

        # Also sync to config/provider.json if provider_config_file exists or is needed
        try:
            from core.paths import provider_config_file
            p_cfg_path = provider_config_file()
            p_data = {}
            if p_cfg_path.exists():
                try:
                    with open(p_cfg_path, "r", encoding="utf-8") as pf:
                        p_data = json.load(pf)
                except Exception:
                    pass
            p_data.update({
                "provider_server_port": ai_cfg.get("provider_server_port", 8000),
                "server_port": ai_cfg.get("server_port", 8000),
                "provider_server_host": ai_cfg.get("provider_server_host", "0.0.0.0"),
                "server_host": ai_cfg.get("server_host", "0.0.0.0"),
                "ssl_enabled": ai_cfg.get("ssl_enabled", False),
                "ssl_certfile": ai_cfg.get("ssl_certfile", ""),
                "ssl_keyfile": ai_cfg.get("ssl_keyfile", ""),
                "sigma_proxy_alias": ai_cfg.get("sigma_proxy_alias", "sigma"),
                "sigma_proxy_model": ai_cfg.get("sigma_proxy_model", ""),
            })
            p_cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with open(p_cfg_path, "w", encoding="utf-8") as pf:
                json.dump(p_data, pf, indent=4)
        except Exception as exc:
            log.warning("Sync to provider.json non riuscita: %s", exc)

        self.send_json_response({"success": True})
    except Exception as exc:
        log.error("handle_api_config_post: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_api_ollama_models(self):
    """List Ollama models via HTTP API ONLY if explicitly enabled (never spawns subprocesses/daemons)."""
    try:
        from core.ai_providers import load_ai_config
        ai_cfg = load_ai_config()
        ollama_cfg = ai_cfg.get("providers", {}).get("ollama", {})
        
        # If Ollama is not explicitly enabled by the user, return empty list without touching network/processes
        if ollama_cfg.get("enabled") is not True:
            return self.send_json_response({"success": True, "models": []})

        import urllib.request
        import json
        endpoint = ollama_cfg.get("endpoint", "http://localhost:11434/api/chat")
        base_url = endpoint.split("/api/")[0] if "/api/" in endpoint else "http://localhost:11434"
        tags_url = f"{base_url}/api/tags"
        
        req = urllib.request.Request(tags_url, headers={"User-Agent": "SigmaStudio"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            raw_models = data.get("models", [])
            models = []
            for m in raw_models:
                m_name = m.get("name", "")
                m_size_bytes = m.get("size", 0)
                m_size_str = f"{m_size_bytes / (1024**3):.1f} GB" if m_size_bytes else "?"
                if m_name:
                    models.append({"name": m_name, "size": m_size_str})
            return self.send_json_response({"success": True, "models": models})
    except Exception:
        # If daemon is not running or unreachable, return empty list without spawning any process
        return self.send_json_response({"success": True, "models": []})


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


def handle_hf_token_config(self):
    """
    POST /api/config/hf_token — Save the HuggingFace token.

    Kept for callers outside the Model Hub; the token itself is managed from the
    Model Hub "Directory & HF Token" tab, and both routes share the same write
    path so neither can leave a stale copy behind.
    """
    try:
        from core.modules.sigma_model_hub.backend.hf_client import persist_hf_token

        req = self.read_json_body() if hasattr(self, 'read_json_body') else {}
        token = (req.get('hf_token') or '').strip()
        result = persist_hf_token(token)
        return self.send_json_response({"success": True, "hf_has_token": result["hf_has_token"]})
    except Exception as exc:
        log.error("handle_hf_token_config error: %s", exc)
        return self.send_json_response({"success": False, "error": str(exc)}, 500)


def handle_hf_token_get(self):
    """GET /api/config/hf_token — Get HuggingFace token configured status and its origin."""
    try:
        from core.modules.sigma_model_hub.backend.hf_client import resolve_hf_token
        resolved = resolve_hf_token()
        return self.send_json_response({
            "success": True,
            "hf_has_token": bool(resolved["token"]),
            "hf_token_source": resolved["source"],
            "hf_token_source_detail": resolved["detail"],
        })
    except Exception as exc:
        return self.send_json_response({"success": False, "hf_has_token": False, "error": str(exc)})


def handle_tts_engines_fallback(self):
    """GET /api/tts/engines fallback returning empty engines list when sigma_voice_studio is not loaded."""
    return self.send_json_response({"engines": [], "default": {"engine": "browser", "voice": ""}})

