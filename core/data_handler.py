"""Data handlers for Sigma Studio — modules, topics, knowledge DB."""
import os
import glob
import json


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
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


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
            # Only include modules whose actual folder exists on disk
            seen_modules = set()
            for mod_num in topic_data.get("modules", []):
                if mod_num in seen_modules:
                    continue  # skip duplicates
                seen_modules.add(mod_num)
                mod_folder = None
                if os.path.isdir(topic_folder):
                    for d in sorted(os.listdir(topic_folder)):
                        if d.startswith(mod_num + "_"):
                            mod_folder = os.path.join(topic_folder, d)
                            break
                if mod_folder and os.path.isdir(mod_folder):
                    stored_name = meta.get("modules", {}).get(mod_num, "")
                    display_name = stored_name if stored_name else os.path.basename(mod_folder)[3:].replace('_', ' ').title()
                    mod_info = {
                        "number": mod_num,
                        "folder": mod_folder.replace('\\', '/'),
                        "name": display_name,
                        "description": stored_name,
                        "teoria": [], "test": [], "viz": [], "docs": [], "whitepapers": []
                    }
                    files_data = load_module_files(self, mod_folder)
                    mod_info.update(files_data)
                    topic_info["modules"].append(mod_info)
            result["topics"].append(topic_info)
        self.send_json_response(result)
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


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
        files = []
        if os.path.isdir(manifesto_dir):
            for f in sorted(os.listdir(manifesto_dir)):
                fpath = os.path.join(manifesto_dir, f)
                if os.path.isfile(fpath) and f.lower().endswith('.md'):
                    files.append({
                        "filename": f,
                        "path": fpath.replace('\\', '/'),
                        "name": f.replace('.md', '').replace('_', ' '),
                        "size": os.path.getsize(fpath)
                    })
        self.send_json_response({"success": True, "files": files})
    except Exception as e:
        self.send_json_response({"success": False, "error": str(e)}, 500)