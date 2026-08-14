# -*- coding: utf-8 -*-
"""
AudioStudioRouter — REST endpoints for sigma_audio_studio module.
"""
from typing import Dict, Any
from .service import AudioStudioService

class AudioStudioRouter:
    """Handles HTTP requests for Audio Studio module."""

    @staticmethod
    def handle_status(handler) -> None:
        """GET /api/modules/audio_studio/status"""
        try:
            status = AudioStudioService.get_status()
            handler.send_json_response({"success": True, "data": status})
        except Exception as e:
            handler.send_json_response({"success": False, "error": str(e)}, 500)

    @staticmethod
    def handle_stations(handler) -> None:
        """GET /api/modules/audio_studio/stations"""
        try:
            stations = AudioStudioService.get_stations()
            handler.send_json_response({"success": True, "stations": stations})
        except Exception as e:
            handler.send_json_response({"success": False, "error": str(e)}, 500)
