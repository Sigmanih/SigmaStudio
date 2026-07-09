"""File CRUD handlers."""
import os
import json


def handle_get_file(self):
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        path = query.get('path', [None])[0]
        if not path or not self._is_path_allowed(path) or not os.path.exists(path):
            return self.send_json_response({"success": False, "error": "Path invalido o non consentito"}, 400)
        with open(path, 'r', encoding='utf-8') as f:
            self.send_json_response({"success": True, "content": f.read()})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_create_file(self):
    try:
        req = self.read_json_body()
        path = req.get('path')
        if not path or '..' in path or not self._is_path_allowed(path):
            return self.send_json_response({"error": "Path invalido o non consentito"}, 400)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(req.get('content', ''))
        self.send_json_response({"success": True})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


def handle_delete_file(self):
    try:
        req = self.read_json_body()
        path = req.get('path')
        if not path or '..' in path or not self._is_path_allowed(path) or not os.path.exists(path):
            return self.send_json_response({"error": "Path invalido o non consentito"}, 400)
        os.remove(path)
        self.send_json_response({"success": True})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)


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
    import subprocess
    try:
        p = self.read_json_body().get('script_path')
        if not p or not self._is_path_allowed(p) or ('..' in p):
            return self.send_json_response({"error": "Path invalido o non consentito"}, 400)
        if not os.path.exists(p):
            return self.send_json_response({"error": f"File non trovato: {p}"}, 400)
        cmd = ["python", "-u", p] if p.endswith('.py') else ["node", p]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        self.send_json_response({"stdout": res.stdout, "stderr": res.stderr, "exit_code": res.returncode})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)