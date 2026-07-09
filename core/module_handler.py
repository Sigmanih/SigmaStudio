"""Module and Topic CRUD handlers."""
import os
import shutil
import json


def handle_create_topic(self):
    try:
        req = self.read_json_body()
        topic_id = req.get('id', '').strip().lower().replace(' ', '_')
        name = req.get('name', '').strip()
        description = req.get('description', '')
        domain = req.get('domain', 'generale')
        manifesto_ref = req.get('manifesto_ref', '')
        parent_id = req.get('parent_id', None)

        if not topic_id or not name:
            return self.send_json_response({"error": "id e name sono obbligatori"}, 400)

        meta = self.get_module_meta()
        if "topics" not in meta:
            meta["topics"] = {}
        if topic_id in meta["topics"]:
            return self.send_json_response({"error": f"Argomento '{topic_id}' già esistente"}, 400)
        if parent_id and parent_id not in meta.get("topics", {}):
            return self.send_json_response({"error": f"Argomento padre '{parent_id}' non trovato"}, 400)

        topic_folder = os.path.join('data', topic_id)
        os.makedirs(topic_folder, exist_ok=True)

        meta["topics"][topic_id] = {
            "name": name, "description": description, "domain": domain,
            "manifesto_ref": manifesto_ref, "parent_id": parent_id,
            "folder": topic_folder.replace('\\', '/'), "modules": []
        }
        self.save_module_meta(meta)
        self.send_json_response({"success": True, "topic_id": topic_id})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_update_topic(self):
    try:
        req = self.read_json_body()
        topic_id = req.get('topic_id', '')
        if not topic_id:
            return self.send_json_response({"error": "topic_id required"}, 400)
        meta = self.get_module_meta()
        if topic_id not in meta.get("topics", {}):
            return self.send_json_response({"error": "Topic not found"}, 400)
        for k in ('name', 'description', 'domain'):
            if k in req:
                meta["topics"][topic_id][k] = req[k]
        if 'parent_id' in req:
            pid = req['parent_id']
            if pid and pid not in meta.get("topics", {}):
                return self.send_json_response({"error": f"Argomento padre '{pid}' non trovato"}, 400)
            meta["topics"][topic_id]["parent_id"] = pid
        self.save_module_meta(meta)
        self.send_json_response({"success": True})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_delete_topic(self):
    try:
        req = self.read_json_body()
        topic_id = req.get('topic_id', '')
        if not topic_id:
            return self.send_json_response({"error": "topic_id required"}, 400)
        meta = self.get_module_meta()
        if topic_id not in meta.get("topics", {}):
            return self.send_json_response({"error": "Topic not found"}, 400)
        topic_folder = meta["topics"][topic_id].get("folder", topic_id)
        if not self._is_path_allowed(topic_folder):
            return self.send_json_response({"error": "Folder non consentito (deve essere in data/)"}, 400)
        if os.path.isdir(topic_folder):
            shutil.rmtree(topic_folder, ignore_errors=True)
        for mod_num in meta["topics"][topic_id].get("modules", []):
            if mod_num in meta.get("modules", {}):
                del meta["modules"][mod_num]
        del meta["topics"][topic_id]
        self.save_module_meta(meta)
        self.send_json_response({"success": True})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_create_module(self):
    try:
        req = self.read_json_body()
        num = req.get('number', '00').zfill(2)
        original_name = req.get('name', 'nuovo')
        name = original_name.replace(' ', '_').lower()
        topic_id = req.get('topic_id', '')
        description = req.get('description', '')
        if not topic_id:
            return self.send_json_response({"error": "topic_id è obbligatorio"}, 400)
        meta = self.get_module_meta()
        topics = meta.get("topics", {})
        if topic_id not in topics:
            return self.send_json_response({"error": f"Topic '{topic_id}' non trovato"}, 400)
        topic_folder = topics[topic_id].get("folder", topic_id)
        folder_name = f"{num}_{name}"
        module_path = os.path.join(topic_folder, folder_name)
        if os.path.exists(module_path):
            return self.send_json_response({"error": "Modulo già esistente"}, 400)
        os.makedirs(module_path, exist_ok=True)
        for sub in ['teoria', 'test', 'viz', 'docs', 'whitepapers']:
            os.makedirs(os.path.join(module_path, sub), exist_ok=True)
        if "modules" not in meta:
            meta["modules"] = {}
        meta["modules"][num] = original_name
        if num not in topics[topic_id].get("modules", []):
            topics[topic_id].setdefault("modules", []).append(num)
        self.save_module_meta(meta)
        self.send_json_response({"success": True, "folder": module_path.replace('\\', '/')})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_delete_module(self):
    try:
        req = self.read_json_body()
        folder = req.get('folder')
        if not folder or '..' in folder or not self._is_path_allowed(folder):
            return self.send_json_response({"error": "Invalid folder"}, 400)
        shutil.rmtree(folder, ignore_errors=True)
        meta = self.get_module_meta()
        mod_num = os.path.basename(folder)[:2] if os.path.basename(folder)[:2].isdigit() else folder[:2]
        for topic_id, topic_data in meta.get("topics", {}).items():
            if mod_num in topic_data.get("modules", []):
                topic_data["modules"].remove(mod_num)
        if mod_num in meta.get("modules", {}):
            del meta["modules"][mod_num]
        self.save_module_meta(meta)
        self.send_json_response({"success": True})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_update_module(self):
    try:
        req = self.read_json_body()
        old_f, num = req.get('old_folder'), req.get('number', '').zfill(2)
        if not old_f or not self._is_path_allowed(old_f):
            return self.send_json_response({"error": "Folder invalido o non consentito"}, 400)
        name_part = req.get('name', '').replace(' ', '_').lower()
        topic_folder = os.path.dirname(old_f.rstrip('/\\')) if ('/' in old_f or '\\' in old_f) else '.'
        new_f_base = f"{num}_{name_part}"
        new_f = os.path.join(topic_folder, new_f_base) if topic_folder != '.' else new_f_base
        if old_f != new_f and os.path.exists(old_f):
            os.rename(old_f, new_f)
        meta = self.get_module_meta()
        old_num = os.path.basename(old_f.replace('\\', '/'))[:2] if os.path.basename(old_f.replace('\\', '/'))[:2].isdigit() else old_f[:2]
        meta["modules"][num] = req.get('name', '')
        if old_num != num and old_num in meta.get("modules", {}):
            del meta["modules"][old_num]
        for topic_data in meta.get("topics", {}).values():
            mods = topic_data.get("modules", [])
            if old_num in mods:
                mods.remove(old_num)
                if num not in mods:
                    mods.append(num)
        self.save_module_meta(meta)
        self.send_json_response({"success": True})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)