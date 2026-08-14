# -*- coding: utf-8 -*-
"""
AudioStudioService — Station health monitor and catalog provider.
"""
import logging
from typing import Dict, List, Any

log = logging.getLogger("sigma.modules.audio_studio")

DEFAULT_STATIONS = [
    {
        "id": "fm-virgin-1",
        "title": "Virgin Radio Italia FM",
        "artist": "Virgin Radio Live (Style Rock)",
        "broadcaster": "mediaset",
        "broadcasterName": "Mediaset Radio",
        "genre": "radio_fm",
        "frequency": "FM 104.5",
        "url": "http://icecast.unitedradio.it/Virgin.mp3",
        "isLive": True,
        "instruments": ["guitar", "drums", "bass"],
        "moods": ["energy", "coding"]
    },
    {
        "id": "fm-virgin-classics",
        "title": "Virgin Radio Classic Rock",
        "artist": "Virgin Classic Rock Legends",
        "broadcaster": "mediaset",
        "broadcasterName": "Mediaset Radio",
        "genre": "radio_fm",
        "frequency": "FM Rock",
        "url": "http://icy.unitedradio.it/VirginRockClassics.mp3",
        "isLive": True,
        "instruments": ["guitar", "drums", "bass"],
        "moods": ["energy", "coding"]
    },
    {
        "id": "fm-105-1",
        "title": "Radio 105 Network FM",
        "artist": "Radio 105 FM Live (Hits & Urban)",
        "broadcaster": "mediaset",
        "broadcasterName": "Mediaset Radio",
        "genre": "radio_fm",
        "frequency": "FM 105.0",
        "url": "http://icecast.unitedradio.it/Radio105.mp3",
        "isLive": True,
        "instruments": ["drums", "synth", "vinyl"],
        "moods": ["energy", "relax"]
    },
    {
        "id": "fm-rmc-1",
        "title": "Radio Monte Carlo (RMC) FM",
        "artist": "RMC Live (Musica di Gran Classe)",
        "broadcaster": "mediaset",
        "broadcasterName": "Mediaset Radio",
        "genre": "radio_fm",
        "frequency": "FM 105.5",
        "url": "http://icecast.unitedradio.it/RMC.mp3",
        "isLive": True,
        "instruments": ["sax", "piano", "bass"],
        "moods": ["relax", "focus", "night"]
    },
    {
        "id": "fm-rai-1",
        "title": "Rai Radio 1 FM",
        "artist": "Rai Radio 1 Live (Giornale Radio & News)",
        "broadcaster": "rai",
        "broadcasterName": "Rai Radio",
        "genre": "radio_fm",
        "frequency": "FM 89.7",
        "url": "http://icestreaming.rai.it/1.mp3",
        "isLive": True,
        "instruments": ["synth"],
        "moods": ["focus", "coding"]
    },
    {
        "id": "fm-rai-2",
        "title": "Rai Radio 2 FM",
        "artist": "Rai Radio 2 Live (Intrattenimento & Musica)",
        "broadcaster": "rai",
        "broadcasterName": "Rai Radio",
        "genre": "radio_fm",
        "frequency": "FM 91.7",
        "url": "http://icestreaming.rai.it/2.mp3",
        "isLive": True,
        "instruments": ["drums", "guitar", "piano"],
        "moods": ["relax", "energy"]
    },
    {
        "id": "fm-rai-classica",
        "title": "Rai Radio 3 Classica Filodiffusione",
        "artist": "Rai Radio Classica Live (Grandi Maestri)",
        "broadcaster": "rai",
        "broadcasterName": "Rai Radio",
        "genre": "classical",
        "frequency": "FM Classica",
        "url": "http://icestreaming.rai.it/5.mp3",
        "isLive": True,
        "instruments": ["piano", "strings", "flute"],
        "moods": ["focus", "meditation", "night"]
    },
    {
        "id": "fm-radio24-1",
        "title": "Radio 24 Il Sole 24 Ore FM",
        "artist": "Radio 24 Live (News & Approfondimento)",
        "broadcaster": "sole24ore",
        "broadcasterName": "Gruppo 24 ORE",
        "genre": "radio_fm",
        "frequency": "FM 104.8",
        "url": "http://shoutcast2.radio24.it:8000/;",
        "isLive": True,
        "instruments": ["synth"],
        "moods": ["focus", "coding"]
    },
    {
        "id": "fm-kisskiss-1",
        "title": "Radio Kiss Kiss FM",
        "artist": "Radio Kiss Kiss Live (Play Everywhere)",
        "broadcaster": "kisskiss",
        "broadcasterName": "Kiss Kiss Network",
        "genre": "radio_fm",
        "frequency": "FM 97.0",
        "url": "http://wma08.fluidstream.net:4610/",
        "isLive": True,
        "instruments": ["drums", "synth"],
        "moods": ["energy", "relax"]
    },
    {
        "id": "fm-classic-uk",
        "title": "Classic FM UK (Londra)",
        "artist": "Classic FM London Live",
        "broadcaster": "uk_global",
        "broadcasterName": "Global UK",
        "genre": "classical",
        "frequency": "FM 100.0",
        "url": "https://media-ssl.musicradio.com/ClassicFM",
        "isLive": True,
        "instruments": ["piano", "strings", "flute"],
        "moods": ["focus", "meditation"]
    }
]

class AudioStudioService:
    """Business logic and stream discovery for Audio Studio Module."""

    @staticmethod
    def get_status() -> Dict[str, Any]:
        return {
            "module_id": "audio_studio",
            "name": "Hi-Fi Sound & FM Radio Studio",
            "status": "active",
            "version": "1.0.0",
            "active_streams": len(DEFAULT_STATIONS),
            "engine": "HTML5 Audio + WebAudio Synth DSP"
        }

    @staticmethod
    def get_stations() -> List[Dict[str, Any]]:
        return DEFAULT_STATIONS
