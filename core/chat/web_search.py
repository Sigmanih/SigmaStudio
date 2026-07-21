# ==============================================================================
# core/chat/web_search.py — Web Search Integration
# Extracted from core/chat_handler.py for Single Responsibility
# ==============================================================================
"""Perform web searches and URL scraping for AI chat context enrichment.

Providers (in priority order):
    1. Direct URL scraping (if the query contains a URL).
    2. Known domain shortcuts (corriere, wikipedia, github …).
    3. DuckDuckGo HTML search.
    4. Wikipedia REST API fallback.

All functions return a list of result dicts:
    ``[{"title": str, "body": str, "href": str}]``
"""

import re
from core.logger import get_logger

log = get_logger(__name__)


def _scrape_url(url: str) -> dict:
    """Fetch and parse a single URL, returning a result dict."""
    try:
        import requests as req
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "it-IT,it;q=0.9",
        }
        resp = req.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        title = soup.title.get_text(strip=True) if soup.title else ""
        desc = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc = meta_desc["content"]

        texts: list[str] = []
        for tag in soup.find_all(["h1", "h2", "h3", "p"]):
            text = tag.get_text(strip=True)
            if len(text) > 30:
                texts.append(text)
            if len("\n".join(texts)) > 2000:
                break

        body = f"Titolo pagina: {title}\n"
        if desc:
            body += f"Descrizione: {desc}\n"
        body += "Contenuto:\n" + "\n".join(texts[:15])
        return {"title": title or url.split("/")[-1], "body": body[:2000], "href": url}

    except Exception as exc:
        log.debug("_scrape_url %s failed: %s", url, exc)
        return {"title": url, "body": f"Impossibile accedere a {url}: {exc}", "href": url}


def _clean_ddg_href(href: str) -> str:
    """Extract clean URL from DuckDuckGo redirect link if present."""
    if not href:
        return ""
    if "uddg=" in href:
        try:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if "uddg" in parsed and parsed["uddg"]:
                return parsed["uddg"][0]
        except Exception:
            pass
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://duckduckgo.com" + href
    return href


def _search_youtube(query: str) -> list[dict]:
    """Dedicated YouTube search helper generating direct video & search links."""
    import urllib.parse
    import requests as req

    clean_topic = re.sub(r"(?i)(fammi una ricerca su|cerca su|cerca|trova|video|youtube|per i|per il|per la|per|su|in italiano|italiano)", "", query).strip()
    if not clean_topic:
        clean_topic = query.strip()

    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_topic)}"

    results = [
        {
            "title": f"Ricerca YouTube: {clean_topic.title()}",
            "body": f"Risultati di ricerca video in tempo reale su YouTube per '{clean_topic}'",
            "href": search_url
        }
    ]

    # 1 — Direct YouTube HTML scraper
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"
        }
        resp = req.get(search_url, headers=headers, timeout=10)
        if resp.ok:
            video_blocks = re.findall(r'\"videoRenderer\":\{(.*?)\}\}\},\"touchResponse', resp.text)
            if not video_blocks:
                video_blocks = re.findall(r'\"videoRenderer\":\{(.*?)\}\}\}', resp.text)

            for block in video_blocks[:7]:
                id_m = re.search(r'\"videoId\":\"([a-zA-Z0-9_-]{11})\"', block)
                title_m = re.search(r'\"title\":\{\"runs\":\[\{\"text\":\"([^\"]+)\"\}', block) or re.search(r'\"title\":\{\"simpleText\":\"([^\"]+)\"\}', block)
                owner_m = re.search(r'\"ownerText\":\{\"runs\":\[\{\"text\":\"([^\"]+)\"', block)

                if id_m:
                    vid_id = id_m.group(1)
                    title = title_m.group(1) if title_m else "Video YouTube"
                    owner = owner_m.group(1) if owner_m else ""
                    href = f"https://www.youtube.com/watch?v={vid_id}"
                    full_title = f"{title} ({owner})" if owner else title
                    results.append({"title": full_title[:150], "body": f"Video YouTube: {title}", "href": href})
    except Exception as exc:
        log.debug("Direct YouTube scraping failed: %s", exc)

    # 2 — DDGS videos fallback
    if len(results) <= 1:
        try:
            from duckduckgo_search import DDGS
            yt_vids = list(DDGS().videos(clean_topic, max_results=5))
            for v in yt_vids:
                link = v.get("content") or v.get("href") or ""
                title = v.get("title", "")
                uploader = v.get("uploader", "")
                desc = v.get("description", "")
                if link and title:
                    full_title = f"{title} ({uploader})" if uploader else title
                    results.append({
                        "title": full_title[:150],
                        "body": desc[:300] if desc else f"Video YouTube: {title}",
                        "href": link
                    })
        except Exception as exc:
            log.debug("DDGS videos search failed: %s", exc)

    return results


def _search_duckduckgo(query: str) -> list[dict]:
    """Run a DuckDuckGo HTML search and return up to 5 results."""
    try:
        import requests as req
        from bs4 import BeautifulSoup

        session = req.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "it-IT,it;q=0.9",
        })
        try:
            session.get("https://duckduckgo.com/", timeout=10)
        except Exception:
            pass

        resp = session.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        results: list[dict] = []
        for result in soup.select(".result")[:7]:
            title_el = result.select_one(".result__title a, .result__a")
            snippet_el = result.select_one(".result__snippet")
            link_el = result.select_one("a.result__url, .result__title a, .result__a")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            raw_href = link_el.get("href", "") if link_el else ""
            href = _clean_ddg_href(raw_href)
            if title and href:
                results.append({"title": title[:150], "body": snippet[:300], "href": href})
        return results
    except Exception as exc:
        log.debug("DuckDuckGo search failed: %s", exc)
        return []


def _search_wikipedia(query: str) -> list[dict]:
    """Fallback: search Italian Wikipedia via the REST API."""
    try:
        import requests as req
        import urllib.parse

        r = req.get(
            "https://it.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": query, "format": "json", "srlimit": 5,
            },
            headers={"User-Agent": "SigmaStudio/7.0"},
            timeout=10,
        )
        results: list[dict] = []
        for page in r.json().get("query", {}).get("search", [])[:5]:
            t = page.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", page.get("snippet", ""))
            url = f"https://it.wikipedia.org/wiki/{urllib.parse.quote(t.replace(' ', '_'))}"
            results.append({"title": f"Wikipedia: {t}", "body": snippet[:300], "href": url})
        return results
    except Exception as exc:
        log.debug("Wikipedia search failed: %s", exc)
        return []


# Shortcut domains — checked before DuckDuckGo
_DOMAIN_SHORTCUTS: dict[str, str | None] = {
    "corriere":  "https://www.corriere.it/",
    "repubblica": "https://www.repubblica.it/",
    "ansa":      "https://www.ansa.it/",
    "gazzetta":  "https://www.gazzetta.it/",
    "il sole":   "https://www.ilsole24ore.com/",
    "wikipedia": "https://it.wikipedia.org/",
    "github":    "https://github.com/",
    "youtube":   "https://www.youtube.com/",
}


def _perform_web_search(query: str) -> list[dict]:
    """Entry point for all web search operations."""
    q_lower = query.lower()

    # 1 — Direct URL in query
    url_match = re.search(r"(https?://[^\s]+)", query)
    if url_match:
        url = url_match.group(1).rstrip(".,;:!?")
        result = _scrape_url(url)
        if result and "Impossibile accedere" not in result.get("body", ""):
            return [result]

    # 2 — YouTube specific query
    if "youtube" in q_lower or "video" in q_lower:
        yt_results = _search_youtube(query)
        if yt_results:
            return yt_results

    # 3 — Known domain shortcuts
    for keyword, domain_url in _DOMAIN_SHORTCUTS.items():
        if domain_url and keyword in q_lower:
            result = _scrape_url(domain_url)
            if result and "Impossibile accedere" not in result.get("body", ""):
                return [result]

    # 4 — DuckDuckGo
    ddg = _search_duckduckgo(query)
    if ddg:
        return ddg

    # 5 — Wikipedia fallback
    wiki = _search_wikipedia(query)
    if wiki:
        return wiki

    return [{"title": "Nessun risultato", "body": f"Nessun risultato per: {query}", "href": ""}]
