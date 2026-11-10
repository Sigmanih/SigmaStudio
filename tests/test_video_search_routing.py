"""Verifica che la ricerca video non venga confusa con YouTube."""


def test_video_generico_non_attiva_youtube(monkeypatch):
    from core.chat import web_search

    chiamate = []
    monkeypatch.setattr(web_search, "_search_youtube", lambda query: chiamate.append(query) or [])
    monkeypatch.setattr(web_search, "_search_duckduckgo", lambda query, max_results=5: [])
    monkeypatch.setattr(web_search, "_search_duckduckgo_lite", lambda query, max_results=5: [])
    monkeypatch.setattr(web_search, "_search_wikipedia", lambda query, max_results=5: [])

    web_search._perform_web_search("cerca un video sulla fotosintesi")

    assert chiamate == []


def test_youtube_viene_usato_solo_se_nominato(monkeypatch):
    from core.chat import web_search

    chiamate = []
    monkeypatch.setattr(web_search, "_search_youtube", lambda query: chiamate.append(query) or [{"title": "ok"}])

    risultati = web_search._perform_web_search("cerca un video sulla fotosintesi su YouTube")

    assert chiamate == ["cerca un video sulla fotosintesi su YouTube"]
    assert risultati == [{"title": "ok"}]


def test_fast_search_non_intercetta_richieste_di_produzione_video():
    from core.chat.chat_runner import _try_fast_web_search

    assert _try_fast_web_search("Aiutami a creare un video con VideoStudio") is None
