import urllib.request
import sys

url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.mangaworld.mx/manga/933/mx0/read/5f7b9f51fd59c26384219a95/1'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
}
req = urllib.request.Request(url, headers=headers)
r = urllib.request.urlopen(req, timeout=30)
html = r.read().decode('utf-8')
print(f'HTML length: {len(html)}')
# Stampa solo le righe che contengono 'img' o 'pdf' o 'chapter' per analisi rapida
for i, line in enumerate(html.split('\n')):
    low = line.lower()
    if ('<img' in low or '.pdf' in low or 'chapter' in low or 'page' in low) and len(line.strip()) > 10:
        print(f'{i:4d}: {line.strip()[:200]}')
