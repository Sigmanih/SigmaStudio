"""Data handlers for Sigma Studio — modules, topics, knowledge DB."""
import os
import glob
import json
from core import paths
from core.logger import get_logger
from core.store import modules_store

log = get_logger(__name__)


def _infer_file_type(filename: str) -> dict:
    """Infer file classification and entrypoint status."""
    ext = os.path.splitext(filename)[1].lower()
    base = os.path.basename(filename).lower()
    
    file_type = 'text'
    if ext == '.pdf':
        file_type = 'pdf'
    elif ext == '.md':
        file_type = 'markdown'
    elif ext in ['.py', '.pyw']:
        file_type = 'python'
    elif ext in ['.js', '.jsx', '.ts', '.tsx']:
        file_type = 'javascript'
    elif ext in ['.html', '.htm']:
        file_type = 'html'
    elif ext == '.json':
        file_type = 'json'
    elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']:
        file_type = 'image'
    elif ext in ['.mp3', '.wav', '.mp4', '.webm', '.ogg']:
        file_type = 'media'
    elif ext in ['.css', '.scss']:
        file_type = 'stylesheet'

    is_entrypoint = base in ['index.html', 'app.py', 'main.py', 'index.js', 'app.js']
    return {"type": file_type, "is_entrypoint": is_entrypoint}


def rebuild_modules_meta() -> dict:
    """
    Synchronise modules_meta.json from the filesystem in real time.
    Scans the entire ./data/ tree recursively into a Universal Knowledge Node Graph (TopicNodes).
    Supports arbitrary folder depth, attached multi-type files, and embedded web applications.
    """
    data_root = paths.workspace_dir()
    data_dir = str(data_root)
    prefix = data_root.name
    if not os.path.isdir(data_dir):
        paths.ensure(data_root)
        return {"topics": {}, "nodes": {}, "modules": {}}

    existing = modules_store.load()
    existing_topics = existing.get("topics", {})
    existing_nodes = existing.get("nodes", {})

    nodes: dict = {}
    topics: dict = {}
    modules: dict = {}

    for root, dirs, files in os.walk(data_dir):
        rel_path = os.path.relpath(root, data_dir).replace("\\", "/")
        if rel_path == ".":
            continue

        node_id = rel_path
        parent_id = os.path.dirname(rel_path).replace("\\", "/")
        if parent_id == "." or not parent_id:
            parent_id = None

        node_name = os.path.basename(root).replace("_", " ").title()

        # Classify files inside this node
        file_entries = []
        has_app = False
        app_entrypoint = None

        for f in sorted(files):
            f_rel = os.path.join(rel_path, f).replace("\\", "/")
            f_meta = _infer_file_type(f)
            if f_meta["file_type" if "file_type" in f_meta else "type"] in ['html', 'python', 'javascript'] and f_meta["is_entrypoint"]:
                has_app = True
                app_entrypoint = f_rel

            file_entries.append({
                "name": f,
                "path": f"{prefix}/{f_rel}",
                "type": f_meta.get("type", "text"),
                "is_entrypoint": f_meta.get("is_entrypoint", False)
            })

        existing_meta = existing_nodes.get(node_id, existing_topics.get(node_id, {}))

        nodes[node_id] = {
            "id": node_id,
            "name": existing_meta.get("name", node_name),
            "parent_id": parent_id,
            "folder": f"{prefix}/{rel_path}",
            "description": existing_meta.get("description", f"Nodo di conoscenza per {node_name}"),
            "files": file_entries,
            "has_app": has_app,
            "app_entrypoint": app_entrypoint,
            "children": [os.path.join(rel_path, d).replace("\\", "/") for d in sorted(dirs)]
        }

        # Backward compatibility for legacy topics structure
        if not parent_id:
            topics[node_id] = nodes[node_id].copy()
            topics[node_id]["modules"] = [f["name"] for f in file_entries]

    meta_data = {"topics": topics, "nodes": nodes, "modules": modules}
    modules_store.save(meta_data)
    log.info("modules_meta.json rebuilt (%d nodes, %d topics)", len(nodes), len(topics))
    return meta_data


def get_all_module_folders(self):
    """Scan topic folders for nested module folders."""
    meta = rebuild_modules_meta()
    topics = meta.get("topics", {})
    result = []
    for topic_id, topic_data in topics.items():
        topic_folder = topic_data.get("folder", os.path.join("data", topic_id))
        if os.path.isdir(topic_folder):
            for d in sorted(os.listdir(topic_folder)):
                full = os.path.join(topic_folder, d)
                if os.path.isdir(full):
                    result.append(full)
    return result


def get_topic_for_module(self, module_num):
    meta = self.get_module_meta()
    for topic_id, topic_data in meta.get("topics", {}).items():
        if module_num in topic_data.get("modules", []):
            return topic_id, topic_data.get("folder", topic_id)
    return None, None


def load_module_files(self, folder_path):
    """Load files from subfolders and direct files inside any module or node folder."""
    res = {"teoria": [], "scripts": [], "viz": [], "docs": [], "whitepapers": [], "pdf": [], "media": []}
    
    # 1. Standard subfolders
    for key in ['teoria', 'scripts', 'test', 'viz', 'docs', 'whitepapers', 'pdf', 'media']:
        p = os.path.join(folder_path, key)
        if os.path.isdir(p):
            files = [{"filename": os.path.basename(f), "path": f.replace('\\', '/')}
                     for f in glob.glob(os.path.join(p, "*")) if os.path.isfile(f)]
            if key == 'test':
                res['scripts'] = res.get('scripts', []) + files
            else:
                res[key] = res.get(key, []) + files

    # 2. Direct files inside the node folder
    if os.path.isdir(folder_path):
        for f in os.listdir(folder_path):
            full_f = os.path.join(folder_path, f)
            if os.path.isfile(full_f):
                rel_p = full_f.replace('\\', '/')
                ext = os.path.splitext(f)[1].lower()
                file_obj = {"filename": f, "path": rel_p}

                if ext == '.pdf':
                    res["pdf"].append(file_obj)
                    res["docs"].append(file_obj)
                elif ext == '.md':
                    if "WHITEPAPER" in f.upper():
                        res["whitepapers"].append(file_obj)
                    else:
                        res["teoria"].append(file_obj)
                elif ext in ['.py', '.js', '.jsx', '.ts', '.tsx']:
                    res["scripts"].append(file_obj)
                elif ext in ['.html', '.htm', '.png', '.jpg', '.jpeg', '.svg', '.webp']:
                    res["viz"].append(file_obj)
                elif ext in ['.mp3', '.wav', '.mp4', '.webm']:
                    res["media"].append(file_obj)
                elif ext in ['.json', '.txt']:
                    res["docs"].append(file_obj)

    wp_from_docs = [f for f in res["docs"] if "WHITEPAPER" in f["filename"].upper()]
    res["whitepapers"] = res["whitepapers"] + wp_from_docs
    res["docs"] = [f for f in res["docs"] if "WHITEPAPER" not in f["filename"].upper()]
    # Keep 'test' alias pointing to 'scripts' for full backward compatibility
    res["test"] = res["scripts"]
    return res


def handle_api_modules(self):
    try:
        meta = rebuild_modules_meta()
        data = {"modules": []}
        mod_folders = get_all_module_folders(self)
        for mod in mod_folders:
            basename = os.path.basename(mod)
            res = {
                "folder": mod.replace('\\', '/'),
                "number": basename[:2] if basename[:2].isdigit() else "01",
                "name": basename[3:].replace('_', ' ').title() if basename[:2].isdigit() else basename.replace('_', ' ').title(),
                "description": meta.get("modules", {}).get(basename[:2], ""),
                "teoria": [], "scripts": [], "test": [], "viz": [], "docs": [], "whitepapers": []
            }
            files_data = load_module_files(self, mod)
            res.update(files_data)
            data["modules"].append(res)
        self.send_json_response(data)
    except Exception as exc:
        log.error("handle_api_modules: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_api_topics(self):
    """
    POST / GET /api/topics — Return unified topic nodes for ALL folders and subfolders under ./data/.
    Eliminates the distinction between topics and subtopics: every subfolder is a topic node in the graph,
    and files are attached directly to the node that contains them.
    """
    try:
        meta = rebuild_modules_meta()
        result = {"topics": []}
        nodes = meta.get("nodes", {})
        
        for node_id, node_data in nodes.items():
            folder_path = node_data.get("folder", f"data/{node_id}")
            
            # Load files directly inside this topic folder
            files_dict = {"teoria": [], "scripts": [], "test": [], "viz": [], "docs": [], "whitepapers": [], "pdf": [], "media": []}
            if os.path.isdir(folder_path):
                files_dict.update(load_module_files(self, folder_path))

            topic_info = {
                "id": node_id,
                "name": node_data.get("name", os.path.basename(node_id).replace("_", " ").title()),
                "description": node_data.get("description", ""),
                "domain": node_data.get("domain", ""),
                "manifesto_ref": node_data.get("manifesto_ref", ""),
                "parent_id": node_data.get("parent_id"),
                "children": node_data.get("children", []),
                "folder": folder_path,
                # Direct file attachments on Topic / Subtopic Node
                "teoria": files_dict["teoria"],
                "scripts": files_dict["scripts"],
                "test": files_dict["test"],
                "viz": files_dict["viz"],
                "docs": files_dict["docs"],
                "whitepapers": files_dict["whitepapers"],
                "pdf": files_dict["pdf"],
                "media": files_dict["media"],
                "modules": [] # No synthetic duplicate subtopic module auto-created!
            }
            result["topics"].append(topic_info)

        self.send_json_response(result)
    except Exception as exc:
        log.error("handle_api_topics: %s", exc, exc_info=True)
        self.send_json_response({"error": str(exc)}, 500)


def handle_knowledge_db(self):
    try:
        meta = self.get_module_meta()
        nodes = [{"id": "Dashboard", "group": "core", "label": "Sigma Studio", "path": "/", "desc": "Root"}]
        links = []
        mod_folders = get_all_module_folders(self)
        for mod in mod_folders:
            basename = os.path.basename(mod)
            num = basename[:2]
            mod_id = f"M{num}"
            nodes.append({"id": mod_id, "group": "theory", "label": f"Mod {num}",
                          "path": f"module-{mod.replace(os.sep, '/')}",
                          "desc": meta.get("modules", {}).get(num, ""), "type": "module"})
            links.append({"source": "Dashboard", "target": mod_id})
            for folder_name in ['teoria', 'scripts', 'viz', 'docs']:
                fp = os.path.join(mod, folder_name)
                if os.path.isdir(fp):
                    for f in glob.glob(os.path.join(fp, "*")):
                        fname = os.path.basename(f)
                        group = "whitepaper" if folder_name == 'docs' and 'WHITEPAPER' in fname.upper() else folder_name
                        nodes.append({"id": f"{mod_id}_{fname}", "group": group, "label": fname,
                                      "path": f.replace('\\', '/'), "type": group})
                        links.append({"source": mod_id, "target": f"{mod_id}_{fname}"})
        self.send_json_response({"nodes": nodes, "links": links})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def _get_fallback_image(filename: str) -> str:
    fn = filename.lower()
    if "math" in fn:
        return "/images/matematicoAi.png"
    if "code" in fn or "program" in fn or "dev" in fn:
        return "/images/programmatoreAi.png"
    if "architect" in fn or "admin" in fn:
        return "/images/agente0.png"
    return "/images/default.png"


def _parse_manifesto_file(fpath: str, fname: str, meta: dict, manifesto_images: dict) -> dict:
    """Parse a manifesto Modelfile .md and extract all structured metadata, parameters, and system prompt."""
    import re
    norm_path = fpath.replace('\\', '/')
    img = manifesto_images.get(norm_path)
    if not img:
        for agent_id, agent_data in meta.get("agents", {}).items():
            if agent_data.get("manifesto") == norm_path:
                img = agent_data.get("image")
                break
    if not img:
        img = _get_fallback_image(fname)

    raw_text = ""
    try:
        with open(fpath, "r", encoding="utf-8") as fh:
            raw_text = fh.read()
    except Exception as e:
        log.warning(f"Failed to read {fpath}: {e}")

    # Defaults
    name = fname.replace('.md', '').replace('_', ' ').title()
    role = name
    category = "Architettura & Kernel"
    domain_color = "#00d2ff"
    icon = "Cpu"
    capabilities = []
    output_artifacts = "Documentazione & Codice"
    mcp_tools = []
    base_model = "llama3.2"
    temperature = 0.2
    top_p = 0.85
    num_ctx = 32768
    num_predict = 16384
    system_prompt = ""
    description = ""

    # Parse metadata lines and parameters
    for line in raw_text.splitlines():
        line_s = line.strip()
        if line_s.startswith("# Role:"):
            role = line_s.replace("# Role:", "").strip()
        elif line_s.startswith("# Category:"):
            category = line_s.replace("# Category:", "").strip()
        elif line_s.startswith("# DomainColor:"):
            domain_color = line_s.replace("# DomainColor:", "").strip()
        elif line_s.startswith("# Icon:"):
            icon = line_s.replace("# Icon:", "").strip()
        elif line_s.startswith("# Capabilities:"):
            caps = line_s.replace("# Capabilities:", "").strip()
            capabilities = [c.strip() for c in caps.split(",") if c.strip()]
        elif line_s.startswith("# OutputArtifacts:"):
            output_artifacts = line_s.replace("# OutputArtifacts:", "").strip()
        elif line_s.startswith("# McpTools:"):
            tools = line_s.replace("# McpTools:", "").strip()
            mcp_tools = [t.strip() for t in tools.split(",") if t.strip()]
        elif line_s.startswith("FROM "):
            base_model = line_s.replace("FROM ", "").strip()
        elif line_s.startswith("PARAMETER temperature "):
            try:
                temperature = float(line_s.split()[2])
            except (IndexError, ValueError):
                pass
        elif line_s.startswith("PARAMETER top_p "):
            try:
                top_p = float(line_s.split()[2])
            except (IndexError, ValueError):
                pass
        elif line_s.startswith("PARAMETER num_ctx "):
            try:
                num_ctx = int(line_s.split()[2])
            except (IndexError, ValueError):
                pass
        elif line_s.startswith("PARAMETER num_predict "):
            try:
                num_predict = int(line_s.split()[2])
            except (IndexError, ValueError):
                pass

    # Extract SYSTEM prompt block
    sys_match = re.search(r'SYSTEM\s+"""(.*?)"""', raw_text, re.DOTALL)
    if sys_match:
        system_prompt = sys_match.group(1).strip()
    else:
        system_prompt = raw_text

    # Extract description from system prompt
    desc_match = re.search(r'##\s*(?:🎯\s*)?IDENTITÀ(?:\s+E\s+OBIETTIVO)?.*?\n(.*?)(?=\n##|\Z)', system_prompt, re.DOTALL | re.IGNORECASE)
    if desc_match:
        desc_text = desc_match.group(1).strip()
        description = desc_text.split("\n\n")[0].replace("\n", " ").strip()
    elif system_prompt:
        first_p = system_prompt.split("\n\n")[0].replace("\n", " ").strip()
        description = first_p if len(first_p) < 300 else first_p[:297] + "..."

    return {
        "filename": fname,
        "path": norm_path,
        "name": name,
        "role": role,
        "category": category,
        "domainColor": domain_color,
        "icon": icon,
        "capabilities": capabilities,
        "outputArtifacts": output_artifacts,
        "mcpTools": mcp_tools,
        "baseModel": base_model,
        "temperature": temperature,
        "topP": top_p,
        "numCtx": num_ctx,
        "numPredict": num_predict,
        "description": description,
        "systemPrompt": system_prompt,
        "size": os.path.getsize(fpath) if os.path.exists(fpath) else 0,
        "image": img,
        "rawContent": raw_text
    }


def handle_list_manifesti(self):
    """GET /api/list_manifesti — List all available agent manifests with dynamic Modelfile metadata.
    
    Scans both manifesti/ root and manifesti/Private/ subdirectory for .md files.
    """
    try:
        manifesto_dir = 'manifesti'
        manifesti = []
        
        from core.agent_registry import load_agents_meta
        meta = load_agents_meta()
        manifesto_images = meta.get("manifesto_images", {})

        if os.path.isdir(manifesto_dir):
            # Scan main directory for official manifests
            for f in sorted(os.listdir(manifesto_dir)):
                fpath = os.path.join(manifesto_dir, f)
                if os.path.isfile(fpath) and f.lower().endswith('.md') and f.lower() != 'readme.md':
                    manifesti.append(_parse_manifesto_file(fpath, f, meta, manifesto_images))
            # Scan Private/ subdirectory for personal manifests
            private_dir = os.path.join(manifesto_dir, 'Private')
            if os.path.isdir(private_dir):
                for f in sorted(os.listdir(private_dir)):
                    fpath = os.path.join(private_dir, f)
                    if os.path.isfile(fpath) and f.lower().endswith('.md'):
                        manifesti.append(_parse_manifesto_file(fpath, f, meta, manifesto_images))
                        
        self.send_json_response({"success": True, "manifesti": manifesti, "files": manifesti})
    except Exception as exc:
        log.error("handle_list_manifesti: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_update_manifesto_image(self):
    try:
        req = self.read_json_body()
        manifesto_path = req.get("path", "")
        image_path = req.get("image", "")
        if not manifesto_path or not image_path:
            return self.send_json_response({"success": False, "error": "path e image sono richiesti"}, 400)
            
        manifesto_path = manifesto_path.replace('\\', '/')
        
        from core.agent_registry import load_agents_meta, save_agents_meta
        meta = load_agents_meta()
        manifesto_images = meta.setdefault("manifesto_images", {})
        manifesto_images[manifesto_path] = image_path
        
        for agent_id, agent_data in meta.setdefault("agents", {}).items():
            if agent_data.get("manifesto") == manifesto_path:
                agent_data["image"] = image_path
                
        save_agents_meta(meta)
        self.send_json_response({"success": True, "message": "Immagine associata correttamente al manifesto"})
    except Exception as exc:
        log.error("handle_update_manifesto_image: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_upload_agent_image(self):
    try:
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            return self.send_json_response({"error": "Content-Type must be multipart/form-data"}, 400)
            
        from core.file_handler import _parse_multipart
        parsed = _parse_multipart(self)
        file_item = parsed.get('file')
        manifesto_path = parsed.get('path')
        
        if not file_item or not manifesto_path:
            return self.send_json_response({"error": "Missing file or path fields"}, 400)
            
        filename = file_item['filename']
        if '..' in filename or '..' in manifesto_path:
            return self.send_json_response({"error": "Invalid path"}, 400)
            
        dest_dir = "images"
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        
        with open(dest_path, 'wb') as f:
            f.write(file_item['data'])
            
        image_url = f"/images/{filename}"
        manifesto_path = manifesto_path.replace('\\', '/')
        
        from core.agent_registry import load_agents_meta, save_agents_meta
        meta = load_agents_meta()
        manifesto_images = meta.setdefault("manifesto_images", {})
        manifesto_images[manifesto_path] = image_url
        
        for agent_id, agent_data in meta.setdefault("agents", {}).items():
            if agent_data.get("manifesto") == manifesto_path:
                agent_data["image"] = image_url
                
        save_agents_meta(meta)
        
        self.send_json_response({
            "success": True, 
            "image": image_url, 
            "message": f"Immagine caricata e associata a {manifesto_path}"
        })
    except Exception as exc:
        log.error("handle_upload_agent_image: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_upload_user_avatar(self):
    try:
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            return self.send_json_response({"error": "Content-Type must be multipart/form-data"}, 400)
            
        from core.file_handler import _parse_multipart
        parsed = _parse_multipart(self)
        file_item = parsed.get('file')
        
        if not file_item:
            return self.send_json_response({"error": "Missing file field"}, 400)
            
        filename = file_item.get('filename', 'avatar.png')
        ext = os.path.splitext(filename)[1].lower()
        if not ext or ext not in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']:
            ext = '.png'
            
        import time
        clean_name = f"user_avatar_{int(time.time())}{ext}"
        dest_dir = "images"
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, clean_name)
        
        with open(dest_path, 'wb') as f:
            f.write(file_item['data'])
            
        avatar_url = f"/images/{clean_name}"
        
        self.send_json_response({
            "success": True, 
            "avatar_url": avatar_url, 
            "message": "Foto profilata salvata con successo!"
        })
    except Exception as exc:
        log.error("handle_upload_user_avatar: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


# ==============================================================================
# Professions Hub & Remote Manifests Catalog (GitHub)
# ==============================================================================
from core.manifests_catalog import (
    MANIFESTS_CATALOG,
    GITHUB_REPO_URL,
    GITHUB_RAW_BASE_URL,
    get_manifesto_by_id_or_filename
)
from core.agent_registry import register_agent, unregister_agent, load_agents_meta, save_agents_meta


def handle_manifesti_hub(self):
    """GET /api/manifesti/hub — Returns the catalog of profession manifestos available for download."""
    try:
        # Check which ones are already installed in manifesti/ or manifesti/Private/
        manifesto_dir = 'manifesti'
        installed_files = set()
        if os.path.isdir(manifesto_dir):
            for f in os.listdir(manifesto_dir):
                if f.endswith('.md') and f.lower() != 'readme.md':
                    installed_files.add(f.lower())
            p_dir = os.path.join(manifesto_dir, 'Private')
            if os.path.isdir(p_dir):
                for f in os.listdir(p_dir):
                    if f.endswith('.md'):
                        installed_files.add(f.lower())

        catalog = []
        for item in MANIFESTS_CATALOG:
            item_copy = dict(item)
            item_copy["installed"] = item["filename"].lower() in installed_files
            catalog.append(item_copy)

        self.send_json_response({
            "success": True,
            "catalog": catalog,
            "repository": GITHUB_REPO_URL
        })
    except Exception as exc:
        log.error("handle_manifesti_hub: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_manifesti_install_from_hub(self):
    """POST /api/manifesti/install_from_hub — Install a profession manifesto from catalog or raw URL."""
    try:
        req = self.read_json_body()
        manifesto_id = req.get("manifesto_id", "")
        custom_url = req.get("url", "")
        custom_name = req.get("name", "")

        manifesto_dir = 'manifesti'
        os.makedirs(manifesto_dir, exist_ok=True)

        if manifesto_id:
            found = get_manifesto_by_id_or_filename(manifesto_id)
            if not found:
                return self.send_json_response({"success": False, "error": f"Manifesto '{manifesto_id}' non trovato nel catalogo"}, 404)
            
            dest_path = os.path.join(manifesto_dir, found["filename"])
            
            # Il corpo del manifesto arriva dal repository che lo possiede.
            # Non esiste piu' una copia di riserva dentro il kernel: era la
            # terza copia dello stesso testo, e una copia che nessuno aggiorna
            # finisce per installare un agente diverso da quello pubblicato.
            content = ""
            errore_rete = ""
            try:
                import urllib.request
                raw_url = f"{GITHUB_RAW_BASE_URL}/{found['filename']}"
                req_obj = urllib.request.Request(raw_url, headers={'User-Agent': 'SigmaStudio/8.0'})
                with urllib.request.urlopen(req_obj, timeout=10) as resp:
                    content = resp.read().decode('utf-8')
            except Exception as exc:
                errore_rete = str(exc)

            if not content:
                return self.send_json_response({
                    "success": False,
                    "error": (f"Impossibile scaricare '{found['filename']}' da "
                              f"{GITHUB_REPO_URL}: {errore_rete or 'risposta vuota'}"),
                }, 502)

            with open(dest_path, "w", encoding="utf-8") as fh:
                fh.write(content)

            # Auto-register agent in agents_meta.json
            aid = found["id"]
            register_agent(
                agent_id=aid,
                name=found["name"],
                manifesto=f"manifesti/{found['filename']}",
                specialization=found.get("role", aid),
                capabilities=found.get("capabilities", []),
                models=["llama3.2", "deepseek-v4-flash", "qwen3.6:35b"],
                temperature=found.get("temperature", 0.3),
                context_window=found.get("numCtx", 32768)
            )

            return self.send_json_response({
                "success": True,
                "message": f"Manifesto '{found['name']}' scaricato e attivato con successo nel Kernel!",
                "filename": found["filename"],
                "path": dest_path.replace('\\', '/'),
                "agent_id": aid
            })

        elif custom_url:
            # Fetch from raw URL
            import urllib.request
            fname = custom_name.strip() if custom_name.strip() else custom_url.split('/')[-1]
            if not fname.endswith('.md'):
                fname += '.md'
            dest_path = os.path.join(manifesto_dir, fname)

            req_obj = urllib.request.Request(custom_url, headers={'User-Agent': 'SigmaStudio/8.0'})
            with urllib.request.urlopen(req_obj, timeout=15) as resp:
                content = resp.read().decode('utf-8')

            with open(dest_path, "w", encoding="utf-8") as fh:
                fh.write(content)

            aid = fname[:-3].lower().replace(' ', '_').replace('-', '_')
            register_agent(
                agent_id=aid,
                name=custom_name.strip() if custom_name.strip() else aid.replace('_', ' ').title(),
                manifesto=f"manifesti/{fname}",
                specialization="custom_role",
                capabilities=["Custom Capability"],
                temperature=0.3,
                context_window=32768
            )

            return self.send_json_response({
                "success": True,
                "message": f"Manifesto importato con successo da {custom_url}!",
                "filename": fname,
                "path": dest_path.replace('\\', '/'),
                "agent_id": aid
            })

        else:
            return self.send_json_response({"success": False, "error": "Specificare 'manifesto_id' o 'url'"}, 400)

    except Exception as exc:
        log.error("handle_manifesti_install_from_hub: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)


def handle_manifesti_uninstall(self):
    """POST /api/manifesti/uninstall — Remove/uninstall an agent manifesto from local manifesti/."""
    try:
        req = self.read_json_body()
        manifesto_id = req.get("manifesto_id", "") or req.get("filename", "") or req.get("path", "")
        
        if not manifesto_id:
            return self.send_json_response({"success": False, "error": "Specificare 'manifesto_id' o 'filename'"}, 400)
            
        fname = os.path.basename(manifesto_id)
        if not fname.endswith('.md'):
            fname += '.md'
            
        aid = fname[:-3].lower()
        if aid == "sigma_assistant":
            return self.send_json_response({
                "success": False, 
                "error": "Sigma Assistant è l'assistente di default del sistema e non può essere disinstallato."
            }, 400)
            
        target_path = os.path.join('manifesti', fname)
        if os.path.exists(target_path):
            os.remove(target_path)
            
        # Also unregister from agent_registry
        unregister_agent(aid)
        
        return self.send_json_response({
            "success": True,
            "message": f"Manifesto '{fname}' disinstallato con successo dal Kernel.",
            "filename": fname
        })
    except Exception as exc:
        log.error("handle_manifesti_uninstall: %s", exc)
        self.send_json_response({"error": str(exc)}, 500)