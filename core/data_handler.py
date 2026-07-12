"""Data handlers for Sigma Studio — modules, topics, knowledge DB."""
import os
import glob
import json
from core.logger import get_logger

log = get_logger(__name__)

def get_all_module_folders(self):
    """Scan topic folders for nested module folders."""
    meta = self.get_module_meta()
    topics = meta.get("topics", {})
    result = []
    for topic_id, topic_data in topics.items():
        topic_folder = topic_data.get("folder", topic_id)
        if os.path.isdir(topic_folder):
            for d in sorted(os.listdir(topic_folder)):
                full = os.path.join(topic_folder, d)
                if os.path.isdir(full) and d[:2].isdigit():
                    result.append(full)
    return result


def get_topic_for_module(self, module_num):
    meta = self.get_module_meta()
    for topic_id, topic_data in meta.get("topics", {}).items():
        if module_num in topic_data.get("modules", []):
            return topic_id, topic_data.get("folder", topic_id)
    return None, None


def load_module_files(self, folder_path):
    """Load files from subfolders of a module folder."""
    res = {"teoria": [], "test": [], "viz": [], "docs": [], "whitepapers": []}
    for key in ['teoria', 'test', 'viz', 'docs', 'whitepapers']:
        p = os.path.join(folder_path, key)
        if os.path.isdir(p):
            files = [{"filename": os.path.basename(f), "path": f.replace('\\', '/')}
                     for f in glob.glob(os.path.join(p, "*")) if os.path.isfile(f)]
            res[key] = files
    wp_from_docs = [f for f in res["docs"] if "WHITEPAPER" in f["filename"].upper()]
    res["whitepapers"] = res["whitepapers"] + wp_from_docs
    res["docs"] = [f for f in res["docs"] if "WHITEPAPER" not in f["filename"].upper()]
    return res


def handle_api_modules(self):
    try:
        meta = self.get_module_meta()
        data = {"modules": []}
        mod_folders = get_all_module_folders(self)
        for mod in mod_folders:
            basename = os.path.basename(mod)
            res = {
                "folder": mod.replace('\\', '/'),
                "number": basename[:2],
                "name": basename[3:].replace('_', ' ').title(),
                "description": meta.get("modules", {}).get(basename[:2], ""),
                "teoria": [], "test": [], "viz": [], "docs": [], "whitepapers": []
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
        meta = self.get_module_meta()
        result = {"topics": []}
        topics = meta.get("topics", {})
        for topic_id, topic_data in topics.items():
            topic_folder = topic_data.get("folder", topic_id)
            topic_info = {
                "id": topic_id,
                "name": topic_data.get("name", topic_id),
                "description": topic_data.get("description", ""),
                "domain": topic_data.get("domain", ""),
                "manifesto_ref": topic_data.get("manifesto_ref", ""),
                "parent_id": topic_data.get("parent_id", None),
                "modules": []
            }
            seen_modules: set = set()
            for mod_num in topic_data.get("modules", []):
                if mod_num in seen_modules:
                    continue
                seen_modules.add(mod_num)
                mod_folder = None
                if os.path.isdir(topic_folder):
                    for d in sorted(os.listdir(topic_folder)):
                        if d.startswith(mod_num + "_"):
                            mod_folder = os.path.join(topic_folder, d)
                            break
                if mod_folder and os.path.isdir(mod_folder):
                    stored_name = meta.get("modules", {}).get(mod_num, "")
                    display_name = stored_name or os.path.basename(mod_folder)[3:].replace('_', ' ').title()
                    mod_info = {
                        "number": mod_num,
                        "folder": mod_folder.replace('\\', '/'),
                        "name": display_name,
                        "description": stored_name,
                        "teoria": [], "test": [], "viz": [], "docs": [], "whitepapers": []
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
            for folder_name in ['teoria', 'test', 'viz', 'docs']:
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
            if "architect" in fn or "agente0" in fn:
                return "/images/agente0.png"
            return "/images/default.png"

        if os.path.isdir(manifesto_dir):
            for f in sorted(os.listdir(manifesto_dir)):
                fpath = os.path.join(manifesto_dir, f)
                if os.path.isfile(fpath) and f.lower().endswith('.md') and f.lower() != 'readme.md':
                    norm_path = fpath.replace('\\', '/')
                    
                    img = manifesto_images.get(norm_path)
                    
                    if not img:
                        for agent_id, agent_data in meta.get("agents", {}).items():
                            if agent_data.get("manifesto") == norm_path:
                                img = agent_data.get("image")
                                break
                                
                    if not img:
                        img = get_fallback_image(f)

                    manifesti.append({
                        "filename": f,
                        "path": norm_path,
                        "name": f.replace('.md', '').replace('_', ' ').title(),
                        "size": os.path.getsize(fpath),
                        "image": img
                    })
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
        manifesto_path = parsed.get('path') # il percorso del manifesto a cui associare l'immagine
        
        if not file_item or not manifesto_path:
            return self.send_json_response({"error": "Missing file or path fields"}, 400)
            
        filename = file_item['filename']
        if '..' in filename or '..' in manifesto_path:
            return self.send_json_response({"error": "Invalid path"}, 400)
            
        # Percorso di destinazione: images/
        dest_dir = "images"
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        
        # Salva il file immagine
        with open(dest_path, 'wb') as f:
            f.write(file_item['data'])
            
        # Associa l'immagine al manifesto nel file agents_meta.json
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

