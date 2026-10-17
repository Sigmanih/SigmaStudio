#!/usr/bin/env python3
"""Downloader per fumetti da mangaworld.mx.

Estrae gli URL delle pagine (immagini JPG) dalla pagina di lettura e li
scarica in data/progetti/<manga>/<volume>/<capitolo>/N.jpg.

Uso:
    python tools/mx0_downloader.py <url_capitolo> [--out DIR] [--manga NOME]
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE_CDN = "https://cdn.mangaworld.mx"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Referer": "https://www.mangaworld.mx/",
}


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def extract_chapter_data(html: str):
    """Estrae dal JSON embedded il percorso base del capitolo e la lista pagine.

    Il pattern nel HTML e' della forma:
      "chapters":[{"_id":"...","pages":["1.jpg",...], ...}]
    e l'URL base completo appare come:
      https://cdn.mangaworld.mx/chapters/<manga-slug>/<volume-slug>/<capitolo-slug>/1.jpg
    """
    # 1) Trova l'URL base del capitolo (prima immagine completa)
    m = re.search(
        r'(https?://cdn\.mangaworld\.mx/chapters/[^/"]+/[^/"]+/[^/"]+)/\d+\.jpg',
        html,
    )
    if not m:
        raise ValueError("Non trovato l'URL base del capitolo nell'HTML")
    base_url = m.group(1).rstrip('/')

    # 2) Trova la lista delle pagine nel JSON embedded
    pm = re.search(r'"pages"\s*:\s*(\["[^"]+\.jpg"(?:,\s*"[^"]+\.jpg")*\])', html)
    if not pm:
        raise ValueError("Non trovata la lista 'pages' nell'HTML")
    pages = json.loads(pm.group(1))

    # 3) Estrai nomi volume/capitolo per la struttura cartelle
    vol_m = re.search(r'"name"\s*:\s*"(Volume[^"\]]*)"', html)
    chap_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    volume_name = (vol_m.group(1).strip() if vol_m else "volume")
    chapter_title = (chap_m.group(1).strip() if chap_m else "capitolo")

    return base_url, pages, volume_name, chapter_title


def sanitize(name: str) -> str:
    """Rende una stringa sicura come nome di cartella/file."""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:80] or "senza_nome"


def download_page(url: str, dest: Path, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        try:
            data = fetch(url)
            if len(data) < 100:
                raise ValueError(f"Risposta troppo piccola ({len(data)} byte)")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return True
        except Exception as e:
            print(f"  [retry {attempt}/{retries}] {url} -> {e}", file=sys.stderr)
            time.sleep(1.5 * attempt)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Scarica un capitolo da mangaworld.mx")
    ap.add_argument("url", help="URL della pagina di lettura del capitolo")
    ap.add_argument("--out", default=None, help="Cartella di destinazione (default: data/progetti/<manga>)")
    ap.add_argument("--manga", default=None, help="Nome manga per la cartella (default: estratto dall'URL)")
    args = ap.parse_args()

    print(f"[1/3] Recupero pagina: {args.url}")
    html = fetch(args.url).decode("utf-8", errors="replace")

    base_url, pages, volume_name, chapter_title = extract_chapter_data(html)
    print(f"      Base URL : {base_url}")
    print(f"      Pagine   : {len(pages)}")
    print(f"      Volume   : {volume_name}")
    print(f"      Capitolo : {chapter_title}")

    # Nome manga: dall'URL /manga/<id>/<slug>/read/...
    manga_slug = args.manga
    if not manga_slug:
        um = re.search(r'/manga/\d+/([^/]+)/read/', args.url)
        manga_slug = um.group(1) if um else "manga"
    manga_slug = sanitize(manga_slug)

    out_root = Path(args.out) if args.out else Path("data") / "progetti" / manga_slug
    chap_dir = out_root / sanitize(volume_name) / sanitize(chapter_title)
    print(f"[2/3] Cartella : {chap_dir}")

    ok = 0
    for i, page in enumerate(pages, start=1):
        url = f"{base_url}/{page}"
        dest = chap_dir / f"{i:03d}.jpg"
        if dest.exists() and dest.stat().st_size > 100:
            ok += 1
            continue
        if download_page(url, dest):
            ok += 1
            print(f"      {i:3d}/{len(pages)}  OK  {dest.name}")
        else:
            print(f"      {i:3d}/{len(pages)}  FAIL {url}", file=sys.stderr)
        time.sleep(0.25)  # cortesia verso il server

    print(f"[3/3] Fatto: {ok}/{len(pages)} pagine salvate in {chap_dir}")
    return 0 if ok == len(pages) else 1


if __name__ == "__main__":
    sys.exit(main())
