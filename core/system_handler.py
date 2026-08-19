# ==============================================================================
# core/system_handler.py — System Capabilities API Handlers
# ==============================================================================

def handle_system_capabilities(self):
    """GET /api/system/capabilities — Returns full system capability snapshot."""
    from core.capability_manager import detect_capabilities
    caps = detect_capabilities()
    self.send_json_response({"success": True, "capabilities": caps.to_dict()})

def handle_system_available_modules(self):
    """GET /api/system/available_modules — Returns module compatibility info."""
    from core.capability_manager import detect_capabilities, get_available_modules
    caps = detect_capabilities()
    modules = get_available_modules(caps)
    self.send_json_response({
        "success": True,
        "platform": {"os": caps.os, "arch": caps.arch},
        "modules": modules
    })
