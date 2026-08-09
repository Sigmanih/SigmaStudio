import time

import aiohttp

from core.logger import get_logger
from core.creative.model_registry import select_model, set_comfy_inventory

log = get_logger("creative_model_router")

class CreativeTask:
    def __init__(self, task_type: str, params: dict, priority: str = 'balanced'):
        self.task_type = task_type
        self.params = params
        self.priority = priority

class BackendStatus:
    def __init__(self, name: str, available: bool, capabilities: list, url: str, detected: bool = None):
        self.name = name
        self.available = available
        self.capabilities = capabilities
        self.url = url
        # `detected` distingue "spento in config" da "non raggiungibile": permette
        # alla UI di proporre «ComfyUI è in esecuzione, vuoi abilitarlo?».
        self.detected = available if detected is None else detected

    def to_dict(self):
        return {
            "name": self.name,
            "available": self.available,
            "detected": self.detected,
            "capabilities": self.capabilities,
            "url": self.url
        }

class ModelRouter:
    # I ping ai backend costano latenza: una pipeline con 6 nodi ne farebbe
    # decine identici. Lo stato viene ricalcolato al più ogni STATUS_TTL secondi.
    STATUS_TTL = 15.0

    def __init__(self, config: dict):
        self.config = config.get("creative", {})
        self.backends = self.config.get("backends", {})
        self.active_backends = {}
        self._status_cache = None
        self._status_at = 0.0
        self._status_fp = None
        self._names_cache = None
        self._names_at = 0.0
        self._names_fp = None

    def get_config(self) -> dict:
        return self.config

    def update_config(self, new_config: dict):
        self.config.update(new_config)
        self.backends = self.config.get("backends", {})
        self.invalidate_status()

    def invalidate_status(self):
        self._status_cache = None
        self._status_at = 0.0
        self._status_fp = None
        self._names_cache = None
        self._names_at = 0.0
        self._names_fp = None

    async def _ping_comfyui(self, url: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/system_stats", timeout=2) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _ping_sd_webui(self, url: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/sdapi/v1/sd-models", timeout=2) as resp:
                    return resp.status == 200
        except Exception:
            return False

    # Porte su cui girano le installazioni desktop/standalone più comuni.
    PROBE_URLS = {
        "comfyui": ("http://127.0.0.1:8188", "http://localhost:8000"),
        "sd_webui": ("http://127.0.0.1:7860",),
    }

    async def probe_backend(self, name: str) -> str:
        """URL su cui il backend risponde, anche se disabilitato in config."""
        cfg = self.backends.get(name, {})
        candidates = [cfg.get("url")] if cfg.get("url") else []
        candidates += [u for u in self.PROBE_URLS.get(name, ()) if u not in candidates]
        ping = self._ping_comfyui if name == "comfyui" else self._ping_sd_webui
        for url in candidates:
            if url and await ping(url):
                return url
        return ""

    async def check_backend(self, name: str) -> BackendStatus:
        backend_cfg = self.backends.get(name, {})
        if not backend_cfg.get("enabled", False):
            detected_url = await self.probe_backend(name) if name in self.PROBE_URLS else ""
            return BackendStatus(name, False, [], detected_url or backend_cfg.get("url", ""),
                                 detected=bool(detected_url))

        available = False
        capabilities = []
        url = backend_cfg.get("url", "")
        
        if name == "comfyui":
            available = await self._ping_comfyui(url)
            # 3D e video su ComfyUI richiedono nodi custom: li dichiara il registro,
            # non questa lista, altrimenti la UI prometterebbe ciò che non c'è.
            capabilities = ['text_to_image', 'img_to_img', 'inpaint', 'upscale']
        elif name == "sd_webui":
            available = await self._ping_sd_webui(url)
            capabilities = ['text_to_image', 'img_to_img', 'inpaint', 'upscale']
        elif name == "fal_ai":
            available = bool(backend_cfg.get("api_key"))
            capabilities = ['text_to_image', 'image_to_3d', 'multiview_to_3d']
        elif name == "stability":
            available = bool(backend_cfg.get("api_key"))
            capabilities = ['text_to_image', 'image_to_3d']
        elif name == "replicate":
            available = bool(backend_cfg.get("api_key"))
            capabilities = ['text_to_image', 'img_to_img']
        elif name == "blender":
            import os
            path = backend_cfg.get("path", "")
            available = bool(path) and os.path.isfile(path)
            if not available:
                # Auto-detect: se Blender è installato nei percorsi standard il
                # backend è utilizzabile anche senza path esplicito in config.
                from core.creative.three_d.blender_bridge import BlenderBridge
                detected = BlenderBridge()._find_blender()
                available = bool(detected)
                url = detected or url
            capabilities = ['render', 'mesh_cleanup', 'decimate', 'uv_unwrap', 'remesh', 'apply_material', 'export']
        elif name == "pollinations":
            available = True
            capabilities = ['text_to_image', 'img_to_img', 'upscale']

        return BackendStatus(name, available, capabilities, url)

    def _config_fingerprint(self) -> str:
        """Firma della configurazione backend: invalida la cache se cambia.

        Il config può essere modificato anche senza passare da `update_config`
        (test, hot-reload): senza fingerprint la cache servirebbe uno stato vecchio.
        """
        return repr(sorted(
            (name, cfg.get("enabled"), cfg.get("url"), bool(cfg.get("api_key")), cfg.get("path"))
            for name, cfg in (self.backends or {}).items()
        ))

    async def get_available_backends(self, refresh: bool = False) -> list[BackendStatus]:
        fingerprint = self._config_fingerprint()
        if (not refresh and self._status_cache is not None
                and self._status_fp == fingerprint
                and (time.monotonic() - self._status_at) < self.STATUS_TTL):
            return self._status_cache

        statuses = []
        for name in self.backends.keys():
            status = await self.check_backend(name)
            statuses.append(status)
        # Always include Pollinations AI zero-setup fallback
        if not any(s.name == "pollinations" for s in statuses):
            statuses.append(BackendStatus(
                "pollinations", True, ['text_to_image', 'img_to_img', 'upscale'],
                "https://image.pollinations.ai"
            ))

        self._status_cache = statuses
        self._status_at = time.monotonic()
        self._status_fp = fingerprint
        return statuses

    async def capabilities(self) -> dict:
        """Mappa capability → backend disponibili, per abilitare/disabilitare la UI."""
        result = {}
        for status in await self.get_available_backends():
            if not status.available:
                continue
            for cap in status.capabilities:
                result.setdefault(cap, []).append(status.name)
        return result

    async def available_backend_names(self) -> set:
        """Nomi dei backend realmente raggiungibili in questo momento."""
        fingerprint = self._config_fingerprint()
        if (self._names_cache is not None and self._names_fp == fingerprint
                and (time.monotonic() - self._names_at) < self.STATUS_TTL):
            return self._names_cache

        statuses = await self.get_available_backends()
        names = {s.name for s in statuses if s.available}
        # `local` copre le operazioni eseguite in-process (rembg, mappe PBR).
        names.add("local")
        if await self._ollama_available():
            names.add("ollama")

        # Aggiorna il registro con ciò che ComfyUI può davvero caricare.
        if "comfyui" in names:
            await self.refresh_comfy_inventory()
        else:
            set_comfy_inventory(None)

        self._names_cache = names
        self._names_at = time.monotonic()
        self._names_fp = fingerprint
        return names

    async def refresh_comfy_inventory(self) -> dict | None:
        """Interroga ComfyUI e passa l'inventario al registro modelli."""
        cfg = self.backends.get("comfyui", {})
        url = cfg.get("url") or await self.probe_backend("comfyui")
        if not url:
            set_comfy_inventory(None)
            return None
        try:
            from core.creative.generators.adapters.comfy_workflows import DEFAULT_CHECKPOINTS
            from core.creative.generators.adapters.comfyui_adapter import ComfyUIAdapter
            inventory = await ComfyUIAdapter(base_url=url, config=cfg).discover()
        except Exception as e:
            log.debug(f"Inventario ComfyUI non disponibile: {e}")
            return None

        # Il registro deve sapere quale file cercherebbe ciascuna famiglia.
        inventory["configured_checkpoints"] = {**DEFAULT_CHECKPOINTS, **(cfg.get("checkpoints") or {})}
        set_comfy_inventory(inventory)
        return inventory

    async def _ollama_available(self) -> bool:
        return await self.ollama_models() is not None

    async def ollama_models(self) -> set | None:
        """Tag installati su Ollama, o None se Ollama non risponde.

        Serve a distinguere «Ollama è acceso» da «il modello è scaricato»: senza
        questa distinzione la UI mostrerebbe come disponibile un VLM assente.
        """
        endpoint = (self.config.get("ollama_url") or "http://localhost:11434").rstrip("/")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{endpoint}/api/tags", timeout=3) as resp:
                    if resp.status != 200:
                        return None
                    return {m.get("name", "") for m in (await resp.json()).get("models", [])}
        except Exception:
            return None

    async def select(self, task: CreativeTask):
        """Sceglie modello+backend per il task consultando il registro.

        Ritorna `(ModelSpec | None, backend | None)`. Il modello è None quando il
        task non ha voci nel registro (es. capability legacy): in quel caso vale
        il solo backend, scelto per capability come prima.
        """
        available = await self.available_backend_names()
        params = task.params or {}
        model, backend = select_model(
            task.task_type,
            available_backends=available,
            priority=task.priority,
            prefer=tuple(params.get("prefer", ())),
            forced_model=params.get("model_id", "") or "",
        )
        if model:
            return model, backend

        # Il registro conosce questo task ma nessun modello è eseguibile: proporre
        # comunque un backend porterebbe a un fallimento annunciato.
        from core.creative.model_registry import models_for_task
        if models_for_task(task.task_type):
            return None, None

        # Task fuori dal registro: valgono le capability dichiarate dai backend.
        for status in await self.get_available_backends():
            if status.available and task.task_type in status.capabilities:
                return None, status.name
        return None, None

    async def route(self, task: CreativeTask) -> str:
        """Backend da usare per il task (compat: ritorna solo il nome)."""
        model, backend = await self.select(task)
        if backend:
            log.info(f"Routing task {task.task_type} a backend {backend}"
                     + (f" con modello {model.id}" if model else ""))
            return backend

        # Zero-setup fallback
        log.info(f"Nessun backend configurato per {task.task_type}: fallback su Pollinations AI")
        return "pollinations"

    def apply_model(self, params: dict, model, backend: str) -> dict:
        """Inietta nei params i riferimenti del modello scelto per quel backend.

        Gli adapter leggono `workflow`/`family` (ComfyUI) o `model` (API remote):
        è qui che la scelta dell'agente diventa una chiamata concreta.
        """
        if not model:
            return params
        params = dict(params)
        params.setdefault("model_id", model.id)
        if model.workflow:
            params.setdefault("workflow", model.workflow)
        params.setdefault("family", model.checkpoint_key)
        remote = model.remote_ids.get(backend)
        if remote:
            params["model"] = remote
        return params
