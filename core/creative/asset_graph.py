import os
import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from core.logger import get_logger

log = get_logger("creative_asset_graph")

class AssetType(Enum):
    IMAGE = 'image'
    MESH = 'mesh'
    MODEL_3D = 'model_3d'
    TEXTURE = 'texture'
    MATERIAL = 'material'
    SCENE = 'scene'
    RENDER = 'render'
    VIDEO = 'video'
    PROMPT = 'prompt'

# Alias tollerati in ingresso (UI, pipeline JSON, API esterne)
_TYPE_ALIASES = {
    '3d': AssetType.MODEL_3D,
    'model3d': AssetType.MODEL_3D,
    '3d_model': AssetType.MODEL_3D,
    'img': AssetType.IMAGE,
}

# Ruoli di file che rappresentano la geometria di un asset 3D
MODEL_FILE_ROLES = ('model', 'mesh', 'glb', 'gltf', 'obj', 'fbx')
VIDEO_FILE_ROLES = ('video', 'mp4', 'webm')


def coerce_asset_type(type_val) -> AssetType:
    """Converte stringhe/alias in AssetType senza mai sollevare eccezioni.

    Un tipo sconosciuto salvato a DB non deve rendere illeggibile l'intero vault.
    """
    if isinstance(type_val, AssetType):
        return type_val
    key = str(type_val or '').strip().lower()
    if key in _TYPE_ALIASES:
        return _TYPE_ALIASES[key]
    try:
        return AssetType(key)
    except ValueError:
        log.warning(f"Tipo asset sconosciuto '{type_val}', fallback su 'image'")
        return AssetType.IMAGE


def to_public_url(path_str) -> str | None:
    """Trasforma un percorso su disco nell'URL servito dal server (`/data/...`).

    Ritorna None se il file non esiste o è fuori dalla working dir del server.
    """
    if not path_str:
        return None
    p = Path(str(path_str))
    if not p.exists() or not p.is_file():
        return None
    try:
        rel = p.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return None
    return '/' + rel.as_posix()


class Asset:
    def __init__(self, asset_id, type_val, name, source_assets, current_version, metadata, files, tags, thumbnail, created_at, updated_at):
        self.asset_id = asset_id
        self.type = coerce_asset_type(type_val)
        self.name = name
        self.source_assets = source_assets or []
        self.current_version = current_version
        self.metadata = metadata or {}
        self.files = files or {}
        self.tags = tags or []
        self.thumbnail = thumbnail
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        file_urls = {role: to_public_url(path) for role, path in self.files.items()}
        file_urls = {role: url for role, url in file_urls.items() if url}

        model_url = next((file_urls[r] for r in MODEL_FILE_ROLES if r in file_urls), None)
        video_url = next((file_urls[r] for r in VIDEO_FILE_ROLES if r in file_urls), None)
        url = to_public_url(self.thumbnail) or file_urls.get("image") or model_url or video_url

        return {
            "asset_id": self.asset_id,
            "id": self.asset_id,
            "type": self.type.value,
            "name": self.name,
            "url": url,
            "model_url": model_url,
            "video_url": video_url,
            "model": self.metadata.get("model"),
            "file_urls": file_urls,
            "generator": self.metadata.get("generator"),
            "quality_score": self.metadata.get("quality_score"),
            "source_assets": self.source_assets,
            "current_version": self.current_version,
            "metadata": self.metadata,
            "files": self.files,
            "tags": self.tags,
            "thumbnail": self.thumbnail,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class AssetGraph:
    def __init__(self, db_path='data/creative/creative_assets.db'):
        self.db_path = Path(db_path)
        self.assets_dir = Path('data/creative/assets')
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    current_version INTEGER DEFAULT 1,
                    metadata TEXT,
                    files TEXT,
                    tags TEXT,
                    thumbnail TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_versions (
                    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    metadata TEXT,
                    files TEXT,
                    created_at TEXT,
                    FOREIGN KEY (asset_id) REFERENCES assets (asset_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_relations (
                    parent_id TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    PRIMARY KEY (parent_id, child_id),
                    FOREIGN KEY (parent_id) REFERENCES assets (asset_id),
                    FOREIGN KEY (child_id) REFERENCES assets (asset_id)
                )
            ''')
            conn.commit()

    def _row_to_asset(self, row, source_assets=None):
        asset_id, type_val, name, current_version, metadata_json, files_json, tags_json, thumbnail, created_at, updated_at = row
        metadata = json.loads(metadata_json) if metadata_json else {}
        files = json.loads(files_json) if files_json else {}
        tags = json.loads(tags_json) if tags_json else []
        if source_assets is None:
            source_assets = self._get_parents(asset_id)
        return Asset(asset_id, type_val, name, source_assets, current_version, metadata, files, tags, thumbnail, created_at, updated_at)

    def _get_parents(self, asset_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT parent_id FROM asset_relations WHERE child_id = ?', (asset_id,))
            return [row[0] for row in cursor.fetchall()]

    def create_asset(self, type_val, name, files=None, metadata=None, source_assets=None, tags=None) -> Asset:
        asset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # La directory dell'asset è la sua unica home su disco.
        # La thumbnail resta None finché non viene realmente generata: un percorso
        # che punta a un file inesistente si traduce in immagini rotte nella UI.
        asset_dir = self.assets_dir / asset_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        thumbnail = None

        metadata_json = json.dumps(metadata or {})
        files_json = json.dumps(files or {})
        tags_json = json.dumps(tags or [])
        source_assets = source_assets or []

        type_str = coerce_asset_type(type_val).value

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO assets (asset_id, type, name, current_version, metadata, files, tags, thumbnail, created_at, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                ''', (asset_id, type_str, name, metadata_json, files_json, tags_json, thumbnail, now, now))
                
                cursor.execute('''
                    INSERT INTO asset_versions (asset_id, version_number, metadata, files, created_at)
                    VALUES (?, 1, ?, ?, ?)
                ''', (asset_id, metadata_json, files_json, now))

                for parent_id in source_assets:
                    cursor.execute('INSERT INTO asset_relations (parent_id, child_id) VALUES (?, ?)', (parent_id, asset_id))
                    
                conn.commit()
                log.info(f"Creato asset {asset_id} di tipo {type_str}")
        except Exception as e:
            log.error(f"Errore creazione asset: {e}")
            raise
            
        return self.get_asset(asset_id)

    # ------------------------------------------------------------------
    # Gestione file su disco
    # ------------------------------------------------------------------

    def asset_dir(self, asset_id) -> Path:
        d = self.assets_dir / asset_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_file(self, asset_id, filename: str, data: bytes) -> str:
        """Scrive un file nella directory dell'asset e ne ritorna il path relativo."""
        path = self.asset_dir(asset_id) / filename
        with open(path, "wb") as f:
            f.write(data)
        return path.as_posix()

    def attach_file(self, asset_id, role: str, filename: str, data: bytes) -> Asset:
        """Salva i bytes, li registra nei `files` dell'asset e aggiorna la thumbnail."""
        path = self.save_file(asset_id, filename, data)
        asset = self.get_asset(asset_id)
        files = dict(asset.files) if asset else {}
        files[role] = path
        asset = self.update_asset(asset_id, files=files)
        if role in ("image", "albedo", "render"):
            self.generate_thumbnail(asset_id, path)
            asset = self.get_asset(asset_id)
        return asset

    def generate_thumbnail(self, asset_id, image_path: str, size: int = 384) -> str | None:
        """Genera una thumbnail quadrata-contenuta dall'immagine indicata."""
        try:
            from PIL import Image
        except ImportError:
            log.debug("Pillow non disponibile: thumbnail saltata")
            return None
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGBA")
                img.thumbnail((size, size), Image.LANCZOS)
                thumb_path = self.asset_dir(asset_id) / "thumbnail.png"
                img.save(thumb_path, "PNG")
            rel = thumb_path.as_posix()
            self.update_asset(asset_id, thumbnail=rel)
            return rel
        except Exception as e:
            log.warning(f"Thumbnail non generata per {asset_id}: {e}")
            return None

    def get_asset(self, asset_id) -> Asset:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM assets WHERE asset_id = ?', (asset_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_asset(row)

    def update_asset(self, asset_id, **kwargs) -> Asset:
        now = datetime.now(timezone.utc).isoformat()
        asset = self.get_asset(asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} non trovato")

        update_fields = []
        params = []
        
        if 'name' in kwargs:
            update_fields.append("name = ?")
            params.append(kwargs['name'])
        if 'metadata' in kwargs:
            update_fields.append("metadata = ?")
            params.append(json.dumps(kwargs['metadata']))
        if 'files' in kwargs:
            update_fields.append("files = ?")
            params.append(json.dumps(kwargs['files']))
        if 'tags' in kwargs:
            update_fields.append("tags = ?")
            params.append(json.dumps(kwargs['tags']))
        if 'thumbnail' in kwargs:
            update_fields.append("thumbnail = ?")
            params.append(kwargs['thumbnail'])

        if update_fields:
            update_fields.append("updated_at = ?")
            params.append(now)
            params.append(asset_id)
            query = f"UPDATE assets SET {', '.join(update_fields)} WHERE asset_id = ?"
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(query, params)
                conn.commit()
                
        return self.get_asset(asset_id)

    def delete_asset(self, asset_id) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM asset_relations WHERE parent_id = ? OR child_id = ?', (asset_id, asset_id))
                conn.execute('DELETE FROM asset_versions WHERE asset_id = ?', (asset_id,))
                conn.execute('DELETE FROM assets WHERE asset_id = ?', (asset_id,))
                conn.commit()
            shutil.rmtree(self.assets_dir / asset_id, ignore_errors=True)
            return True
        except Exception as e:
            log.error(f"Errore cancellazione asset: {e}")
            return False

    def list_assets(self, type_filter=None, tag_filter=None, limit=50, offset=0) -> list[Asset]:
        query = "SELECT * FROM assets"
        params = []
        conditions = []
        
        if type_filter:
            conditions.append("type = ?")
            params.append(coerce_asset_type(type_filter).value)
        if tag_filter:
            # Ricerca approssimativa nei tag
            conditions.append("tags LIKE ?")
            params.append(f"%\"{tag_filter}\"%")
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        assets = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                assets.append(self._row_to_asset(row))
        return assets

    def create_version(self, asset_id, files, metadata=None) -> Asset:
        asset = self.get_asset(asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} non trovato")
            
        new_version = asset.current_version + 1
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata or asset.metadata)
        files_json = json.dumps(files)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO asset_versions (asset_id, version_number, metadata, files, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (asset_id, new_version, metadata_json, files_json, now))
            
            conn.execute('''
                UPDATE assets SET current_version = ?, metadata = ?, files = ?, updated_at = ?
                WHERE asset_id = ?
            ''', (new_version, metadata_json, files_json, now, asset_id))
            conn.commit()
            
        return self.get_asset(asset_id)

    def get_versions(self, asset_id) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT version_number, metadata, files, created_at FROM asset_versions WHERE asset_id = ? ORDER BY version_number DESC', (asset_id,))
            return [{"version": row[0], "metadata": json.loads(row[1] or '{}'), "files": json.loads(row[2] or '{}'), "created_at": row[3]} for row in cursor.fetchall()]

    def get_lineage(self, asset_id, _seen=None) -> dict:
        """Albero di provenienza dell'asset, arricchito con nome/tipo per la UI."""
        _seen = _seen or set()
        asset = self.get_asset(asset_id)
        node = {
            "asset_id": asset_id,
            "name": asset.name if asset else None,
            "type": asset.type.value if asset else None,
            "version": asset.current_version if asset else None,
            "generator": asset.metadata.get("generator") if asset else None,
            "operation": asset.metadata.get("operation") if asset else None,
            "parents": [],
        }
        if asset_id in _seen:
            return node
        _seen.add(asset_id)
        node["parents"] = [self.get_lineage(pid, _seen) for pid in self._get_parents(asset_id)]
        return node

    def get_descendants(self, asset_id, _seen=None) -> list:
        _seen = _seen if _seen is not None else set()
        if asset_id in _seen:
            return []
        _seen.add(asset_id)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT child_id FROM asset_relations WHERE parent_id = ?', (asset_id,))
            children = [row[0] for row in cursor.fetchall()]

        descendants = list(children)
        for child in children:
            descendants.extend(self.get_descendants(child, _seen))
        return list(set(descendants))

    def search_assets(self, query) -> list:
        # Ricerca testo su nome, metadata o tag
        sql = "SELECT * FROM assets WHERE name LIKE ? OR tags LIKE ? OR metadata LIKE ? ORDER BY updated_at DESC"
        term = f"%{query}%"
        assets = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (term, term, term))
            for row in cursor.fetchall():
                assets.append(self._row_to_asset(row))
        return assets

    def get_stats(self) -> dict:
        stats = {"total": 0, "by_type": {}}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT type, COUNT(*) FROM assets GROUP BY type')
            for type_val, count in cursor.fetchall():
                stats["by_type"][type_val] = count
                stats["total"] += count
        return stats
