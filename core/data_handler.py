"""Data handlers for Sigma Studio — modules, topics, knowledge DB."""
import os
import glob
import json
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
    data_dir = "data"
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir, exist_ok=True)
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
                "path": f"data/{f_rel}",
                "type": f_meta.get("type", "text"),
                "is_entrypoint": f_meta.get("is_entrypoint", False)
            })

        existing_meta = existing_nodes.get(node_id, existing_topics.get(node_id, {}))

        nodes[node_id] = {
            "id": node_id,
            "name": existing_meta.get("name", node_name),
            "parent_id": parent_id,
            "folder": f"data/{rel_path}",
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
    try:
        meta = rebuild_modules_meta()
        result = {"topics": []}
        topics = meta.get("topics", {})
        for topic_id, topic_data in topics.items():
            topic_folder = topic_data.get("folder", os.path.join("data", topic_id))
            topic_info = {
                "id": topic_id,
                "name": topic_data.get("name", topic_id).replace("_", " ").title(),
                "description": topic_data.get("description", ""),
                "domain": topic_data.get("domain", ""),
                "manifesto_ref": topic_data.get("manifesto_ref", ""),
                "parent_id": topic_data.get("parent_id", None),
                "modules": []
            }
            seen_modules: set = set()
            if os.path.isdir(topic_folder):
                for d in sorted(os.listdir(topic_folder)):
                    mod_folder = os.path.join(topic_folder, d)
                    if os.path.isdir(mod_folder):
                        display_name = os.path.basename(mod_folder)[3:].replace('_', ' ').title() if d[:2].isdigit() else d.replace('_', ' ').title()
                        num = d[:2] if d[:2].isdigit() else "01"
                        mod_info = {
                            "number": num,
                            "folder": mod_folder.replace('\\', '/'),
                            "name": display_name,
                            "description": display_name,
                            "teoria": [], "scripts": [], "test": [], "viz": [], "docs": [], "whitepapers": []
                        }
                        mod_info.update(load_module_files(self, mod_folder))
                        topic_info["modules"].append(mod_info)
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


def handle_list_manifesti(self):
    """GET /api/list_manifesti — List all available agent manifests from manifesti/.
    
    Scans both manifesti/ root and manifesti/Private/ subdirectory for .md files.
    """
    try:
        manifesto_dir = 'manifesti'
        manifesti = []
        
        from core.agent_registry import load_agents_meta
        meta = load_agents_meta()
        manifesto_images = meta.get("manifesto_images", {})

        def get_fallback_image(filename):
            fn = filename.lower()
            if "math" in fn:
                return "/images/matematicoAi.png"
            if "code" in fn or "program" in fn or "dev" in fn:
                return "/images/programmatoreAi.png"
            if "architect" in fn or "admin" in fn:
                return "/images/agente0.png"
            return "/images/default.png"

        def add_manifesto(fpath, fname):
            norm_path = fpath.replace('\\', '/')
            img = manifesto_images.get(norm_path)
            if not img:
                for agent_id, agent_data in meta.get("agents", {}).items():
                    if agent_data.get("manifesto") == norm_path:
                        img = agent_data.get("image")
                        break
            if not img:
                img = get_fallback_image(fname)
            manifesti.append({
                "filename": fname,
                "path": norm_path,
                "name": fname.replace('.md', '').replace('_', ' ').title(),
                "size": os.path.getsize(fpath),
                "image": img
            })

        if os.path.isdir(manifesto_dir):
            # Scan main directory for official manifests
            for f in sorted(os.listdir(manifesto_dir)):
                fpath = os.path.join(manifesto_dir, f)
                if os.path.isfile(fpath) and f.lower().endswith('.md') and f.lower() != 'readme.md':
                    add_manifesto(fpath, f)
            # Scan Private/ subdirectory for personal manifests
            private_dir = os.path.join(manifesto_dir, 'Private')
            if os.path.isdir(private_dir):
                for f in sorted(os.listdir(private_dir)):
                    fpath = os.path.join(private_dir, f)
                    if os.path.isfile(fpath) and f.lower().endswith('.md'):
                        add_manifesto(fpath, f)
                        
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