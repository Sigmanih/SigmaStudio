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
import urllib.parse
import subprocess
import shutil
import os
import platform
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.logger import get_logger

log = get_logger(__name__)


# ==============================================================================
# Browser Discovery & Headless Engine
# ==============================================================================

def _candidate_browsers() -> list[str]:
    """Trova browser Chromium disponibili (Chrome, Edge, Chromium)."""
    dal_path = [
        shutil.which(nome)
        for nome in ("chrome", "chromium", "chromium-browser", "google-chrome", "msedge")
    ]
    candidati = [p for p in dal_path if p]

    sistema = platform.system()
    if sistema == "Windows":
        for base in (
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if not base:
                continue
            candidati += [
                str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                str(Path(base) / "Microsoft/Edge/Application/msedge.exe"),
            ]
    elif sistema == "Darwin":
        candidati += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        candidati += [
            "/usr/bin/chromium-browser", "/usr/bin/chromium",
            "/usr/bin/google-chrome", "/snap/bin/chromium",
        ]
    return candidati


def _find_browser() -> str | None:
    """Restituisce il percorso del primo browser Chromium utilizzabile."""
    for percorso in _candidate_browsers():
        if percorso and os.path.isfile(percorso):
            return percorso
    return None


def _scrape_headless(url: str, timeout: int = 15) -> str:
    """Esegue un browser headless Chromium con --dump-dom per ottenere il DOM rendersizzato (SPA)."""
    browser = _find_browser()
    if not browser:
        return ""
    try:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--dump-dom",
            url,
        ]
        res = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return res.stdout or ""
    except Exception as exc:
        log.debug("_scrape_headless per %s fallito: %s", url, exc)
        return ""


# ==============================================================================
# HTML to Clean Markdown Conversion
# ==============================================================================

def _extract_clean_markdown(html_text: str, base_url: str = "", max_chars: int = 8000) -> dict:
    """Estrae titolo, metadati, testo strutturato in Markdown e link utili da HTML grezzo."""
    if not html_text:
        return {"title": "", "description": "", "markdown": "", "links": [], "headings": []}

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, "lxml" if "lxml" in BeautifulSoup.__module__ else "html.parser")
    except Exception:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
        except Exception:
            clean = re.sub(r"<[^>]+>", " ", html_text)
            clean = re.sub(r"\s+", " ", clean).strip()
            return {"title": base_url, "description": "", "markdown": clean[:max_chars], "links": [], "headings": []}

    title = soup.title.get_text(strip=True) if soup.title else ""
    desc = ""
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if meta_desc and meta_desc.get("content"):
        desc = meta_desc["content"].strip()

    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "form", "dialog"]):
        tag.decompose()

    headings: list[str] = []
    links: list[dict] = []
    lines: list[str] = []

    for a in soup.find_all("a", href=True):
        a_text = a.get_text(strip=True)
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        if len(a_text) >= 3 and not re.match(r"^(privacy|cookie|termini|accedi|login|signup|menu)$", a_text, re.I):
            abs_url = urllib.parse.urljoin(base_url, href)
            links.append({"text": a_text[:80], "url": abs_url})
            if len(links) >= 20:
                break

    main_el = soup.find("article") or soup.find("main") or soup.find("body") or soup

    for el in main_el.find_all(["h1", "h2", "h3", "h4", "p", "pre", "ul", "ol", "table", "blockquote"]):
        name = el.name.lower()
        if name in ("h1", "h2", "h3", "h4"):
            txt = el.get_text(strip=True)
            if txt:
                level = int(name[1])
                prefix = "#" * level + " "
                lines.append(f"\n{prefix}{txt}\n")
                headings.append(txt)
        elif name == "p":
            txt = el.get_text(strip=True)
            if len(txt) > 25:
                lines.append(txt)
        elif name == "pre":
            code_txt = el.get_text()
            if code_txt.strip():
                lines.append(f"\n```\n{code_txt.strip()[:1500]}\n```\n")
        elif name in ("ul", "ol"):
            for li in el.find_all("li", recursive=False):
                li_txt = li.get_text(strip=True)
                if li_txt:
                    lines.append(f"- {li_txt}")
        elif name == "table":
            rows = []
            for tr in el.find_all("tr")[:10]:
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                if cells:
                    rows.append("| " + " | ".join(cells) + " |")
            if len(rows) >= 2:
                header_sep = "| " + " | ".join(["---"] * len(rows[0].split("|")[1:-1])) + " |"
                lines.append("\n" + rows[0] + "\n" + header_sep + "\n" + "\n".join(rows[1:]) + "\n")
        elif name == "blockquote":
            bq_txt = el.get_text(strip=True)
            if bq_txt:
                lines.append(f"> {bq_txt}")

        if sum(len(x) for x in lines) >= max_chars:
            break

    markdown_body = "\n\n".join(line for line in lines if line.strip())
    if len(markdown_body) < 100:
        raw_text = soup.get_text(separator="\n", strip=True)
        markdown_body = "\n".join(p for p in raw_text.splitlines() if len(p) > 20)[:max_chars]

    return {
        "title": title or (base_url.split("/")[-1] if base_url else "Pagina Web"),
        "description": desc,
        "markdown": markdown_body[:max_chars],
        "links": links[:12],
        "headings": headings[:15],
    }


def deep_scan_page(url: str, max_chars: int = 8000, extract_links: bool = True) -> dict:
    """Scannerizza a fondo una pagina web (con fallback su Chromium headless)."""
    import requests as req

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    html = ""
    engine_used = "http"
    try:
        resp = req.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
    except Exception as exc:
        log.debug("Richiesta HTTP diretta per %s fallita: %s. Provo headless...", url, exc)

    is_spa_skeleton = bool(re.search(r'<div\s+id=[\'"](?:root|__next|app)[\'"]\s*>\s*</div>', html, re.I))
    if (len(html) < 600 or is_spa_skeleton) and _find_browser():
        headless_html = _scrape_headless(url)
        if len(headless_html) > len(html):
            html = headless_html
            engine_used = "headless_chromium"

    if not html:
        return {
            "title": url,
            "description": "",
            "markdown": f"Impossibile accedere o scannerizzare la pagina {url}.",
            "links": [],
            "headings": [],
            "success": False,
            "engine": "failed",
        }

    parsed = _extract_clean_markdown(html, base_url=url, max_chars=max_chars)
    return {
        "title": parsed["title"],
        "description": parsed["description"],
        "markdown": parsed["markdown"],
        "links": parsed["links"] if extract_links else [],
        "headings": parsed["headings"],
        "success": True,
        "engine": engine_used,
        "url": url,
    }


def _scrape_url(url: str) -> dict:
    """Fetch and parse a single URL, returning a backward-compatible result dict."""
    scanned = deep_scan_page(url, max_chars=4000)
    body_parts = []
    if scanned.get("title"):
        body_parts.append(f"**Titolo:** {scanned['title']}")
    if scanned.get("description"):
        body_parts.append(f"**Descrizione:** {scanned['description']}")
    if scanned.get("markdown"):
        body_parts.append(f"**Contenuto:**\n{scanned['markdown']}")

    return {
        "title": scanned.get("title") or url,
        "body": "\n\n".join(body_parts) if body_parts else f"Nessun contenuto leggibile su {url}",
        "href": url,
        "headings": scanned.get("headings", []),
        "links": scanned.get("links", []),
    }


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
    import requests as req

    clean_topic = re.sub(
        r"(?i)(fammi una ricerca su|cerca su|cerca|trova|video|youtube|per i|per il|per la|per|su|in italiano|italiano)",
        "",
        query,
    ).strip()
    if not clean_topic:
        clean_topic = query.strip()

    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_topic)}"

    results = [
        {
            "title": f"Ricerca YouTube: {clean_topic.title()}",
            "body": f"Risultati di ricerca video in tempo reale su YouTube per '{clean_topic}'",
            "href": search_url,
        }
    ]

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
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

    return results


def _search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """Run a DuckDuckGo HTML search and return results."""
    try:
        import requests as req
        from bs4 import BeautifulSoup

        session = req.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        })
        try:
            session.get("https://duckduckgo.com/", timeout=6)
        except Exception:
            pass

        resp = session.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "lxml" if "lxml" in BeautifulSoup.__module__ else "html.parser")
        results: list[dict] = []
        for result in soup.select(".result")[:max_results + 3]:
            title_el = result.select_one(".result__title a, .result__a")
            snippet_el = result.select_one(".result__snippet")
            link_el = result.select_one("a.result__url, .result__title a, .result__a")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            raw_href = link_el.get("href", "") if link_el else ""
            href = _clean_ddg_href(raw_href)
            if title and href:
                results.append({"title": title[:150], "body": snippet[:350], "href": href})
                if len(results) >= max_results:
                    break
        return results
    except Exception as exc:
        log.debug("DuckDuckGo search failed: %s", exc)
        return []


def _search_duckduckgo_lite(query: str, max_results: int = 5) -> list[dict]:
    """Fallback search on DuckDuckGo Lite."""
    try:
        import requests as req
        from bs4 import BeautifulSoup

        resp = req.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        rows = soup.select("table tbody tr")
        for i in range(0, len(rows), 2):
            link_a = rows[i].select_one("a.result-link")
            snippet_td = rows[i + 1].select_one("td.result-snippet") if i + 1 < len(rows) else None
            if link_a:
                title = link_a.get_text(strip=True)
                href = _clean_ddg_href(link_a.get("href", ""))
                snippet = snippet_td.get_text(strip=True) if snippet_td else ""
                if title and href:
                    results.append({"title": title[:150], "body": snippet[:350], "href": href})
                    if len(results) >= max_results:
                        break
        return results
    except Exception as exc:
        log.debug("DuckDuckGo Lite fallback failed: %s", exc)
        return []


def _search_wikipedia(query: str, max_results: int = 5) -> list[dict]:
    """Fallback: search Italian Wikipedia via the REST API."""
    try:
        import requests as req

        r = req.get(
            "https://it.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": query, "format": "json", "srlimit": max_results,
            },
            headers={"User-Agent": "SigmaStudio/8.0"},
            timeout=10,
        )
        results: list[dict] = []
        for page in r.json().get("query", {}).get("search", [])[:max_results]:
            t = page.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", page.get("snippet", ""))
            url = f"https://it.wikipedia.org/wiki/{urllib.parse.quote(t.replace(' ', '_'))}"
            results.append({"title": f"Wikipedia: {t}", "body": snippet[:350], "href": url})
        return results
    except Exception as exc:
        log.debug("Wikipedia search failed: %s", exc)
        return []


# Shortcut domains — checked before general search
_DOMAIN_SHORTCUTS: dict[str, str | None] = {
    "corriere":   "https://www.corriere.it/",
    "repubblica": "https://www.repubblica.it/",
    "ansa":       "https://www.ansa.it/",
    "gazzetta":   "https://www.gazzetta.it/",
    "il sole":    "https://www.ilsole24ore.com/",
    "wikipedia":  "https://it.wikipedia.org/",
    "github":     "https://github.com/",
    "youtube":    "https://www.youtube.com/",
}


# ==============================================================================
# Deep Intelligence Engine & Multi-Hop Scanner
# ==============================================================================

def deep_web_search(query: str, max_results: int = 5, deep_scan_top_n: int = 3) -> dict:
    """Esegue una ricerca web multi-motore e scannerizza in profondità le prime pagine."""
    raw_results = _search_duckduckgo(query, max_results=max_results)
    if not raw_results:
        raw_results = _search_duckduckgo_lite(query, max_results=max_results)
    if not raw_results:
        raw_results = _search_wikipedia(query, max_results=max_results)

    if not raw_results:
        return {
            "query": query,
            "results_count": 0,
            "results": [],
            "summary": f"Nessun risultato trovato per: {query}",
            "formatted_markdown": f"🔍 **Nessun risultato trovato per:** `{query}`",
        }

    scanned_pages: dict[str, dict] = {}
    top_targets = [r["href"] for r in raw_results[:deep_scan_top_n] if r.get("href")]

    if top_targets:
        with ThreadPoolExecutor(max_workers=min(4, len(top_targets))) as executor:
            future_to_url = {
                executor.submit(deep_scan_page, url, 4000, True): url
                for url in top_targets
            }
            for future in as_completed(future_to_url):
                target_url = future_to_url[future]
                try:
                    scanned_pages[target_url] = future.result()
                except Exception as exc:
                    log.debug("Deep scan of %s failed: %s", target_url, exc)

    enriched_results = []
    for r in raw_results:
        url = r.get("href", "")
        scan_info = scanned_pages.get(url)
        item = {
            "title": r.get("title", ""),
            "href": url,
            "snippet": r.get("body", ""),
            "scanned": bool(scan_info and scan_info.get("success")),
            "extracted_markdown": scan_info.get("markdown", "") if scan_info else "",
            "headings": scan_info.get("headings", []) if scan_info else [],
            "outbound_links": scan_info.get("links", []) if scan_info else [],
        }
        enriched_results.append(item)

    lines = [f"### 🌐 Ricerca Approfondita: {query}\n"]
    for i, item in enumerate(enriched_results, 1):
        title = item["title"]
        href = item["href"]
        lines.append(f"#### {i}. [{title}]({href})")
        if item["snippet"]:
            lines.append(f"*{item['snippet']}*\n")
        if item.get("extracted_markdown"):
            lines.append("**Estratto analitico della pagina:**")
            lines.append(f"> {item['extracted_markdown'][:1200].replace(chr(10), chr(10) + '> ')}\n")
        if item.get("headings"):
            lines.append(f"*Sezioni chiave rilevate:* `{'` • `'.join(item['headings'][:5])}`\n")
        lines.append("---")

    return {
        "query": query,
        "results_count": len(enriched_results),
        "results": enriched_results,
        "summary": f"Trovati {len(enriched_results)} risultati con scansione profonda di {len(scanned_pages)} pagine.",
        "formatted_markdown": "\n\n".join(lines),
    }


def _perform_web_search(query: str, max_results: int = 5, deep_scan: bool = False) -> list[dict]:
    """Entry point per tutte le operazioni di ricerca web (compatibile con chat e MCP)."""
    q_lower = query.lower()

    # 1 — URL diretto nella query
    url_match = re.search(r"(https?://[^\s]+)", query)
    if url_match:
        url = url_match.group(1).rstrip(".,;:!?")
        result = _scrape_url(url)
        if result and "Impossibile accedere" not in result.get("body", ""):
            return [result]

    # 2 — Query specifica per YouTube
    if "youtube" in q_lower or "video" in q_lower:
        yt_results = _search_youtube(query)
        if yt_results:
            return yt_results

    # 3 — Scorciatoie di dominio note
    for keyword, domain_url in _DOMAIN_SHORTCUTS.items():
        if domain_url and keyword in q_lower:
            result = _scrape_url(domain_url)
            if result and "Impossibile accedere" not in result.get("body", ""):
                return [result]

    # 4 — Scansione profonda esplicita
    wants_deep = deep_scan or any(kw in q_lower for kw in ("approfondisci", "esplora", "scannerizza", "dettagliata", "documentazione"))
    if wants_deep:
        dossier = deep_web_search(query, max_results=max_results, deep_scan_top_n=2)
        if dossier.get("results"):
            return [
                {
                    "title": r["title"],
                    "body": r["extracted_markdown"][:1500] if r.get("extracted_markdown") else r["snippet"],
                    "href": r["href"],
                }
                for r in dossier["results"]
            ]

    # 5 — DuckDuckGo standard + Lite fallback
    ddg = _search_duckduckgo(query, max_results=max_results)
    if not ddg:
        ddg = _search_duckduckgo_lite(query, max_results=max_results)
    if ddg:
        return ddg

    # 6 — Wikipedia fallback
    wiki = _search_wikipedia(query, max_results=max_results)
    if wiki:
        return wiki

    return [{"title": "Nessun risultato", "body": f"Nessun risultato per: {query}", "href": ""}]
