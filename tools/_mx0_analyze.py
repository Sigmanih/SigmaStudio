import urllib.request
import re
import json

url = 'https://www.mangaworld.mx/manga/933/mx0/read/5f7b9f51fd59c26384219a95/1'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}
req = urllib.request.Request(url, headers=headers)
r = urllib.request.urlopen(req, timeout=30)
html = r.read().decode('utf-8')

# Cerca pattern di URL immagini
img_patterns = re.findall(r'https?://[^"\s<>]+\.(?:png|jpe?g|webp|gif)', html, re.I)
print(f'=== URL immagini trovate: {len(img_patterns)} ===')
for u in img_patterns[:20]:
    print(u)

# Cerca pattern PDF
pdf_patterns = re.findall(r'https?://[^"\s<>]+\.pdf', html, re.I)
print(f'\n=== URL PDF trovate: {len(pdf_patterns)} ===')
for u in pdf_patterns[:10]:
    print(u)

# Cerca tag img
img_tags = re.findall(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html, re.I)
print(f'\n=== Tag <img> con src: {len(img_tags)} ===')
for u in img_tags[:20]:
    print(u)

# Cerca data-src o lazy loading
lazy = re.findall(r'data-src=["\']([^"\']+)["\']', html, re.I)
print(f'\n=== data-src: {len(lazy)} ===')
for u in lazy[:20]:
    print(u)

# Cerca JSON embedded con pagine
json_blocks = re.findall(r'\[\s*\{[^\]]+"(?:page|image|src|url)"[^\]]+\]\s*', html, re.I)
print(f'\n=== Blocchi JSON con page/image/src: {len(json_blocks)} ===')
for b in json_blocks[:5]:
    print(b[:300])

# Cerca 'pages' o 'chapters' nel testo
text_matches = re.findall(r'["\'](?:pages|chapters|images)["\']\s*:\s*[\[\{][^\]\}]*[\]\}]', html, re.I)
print(f'\n=== Chiavi pages/chapters/images: {len(text_matches)} ===')
for m in text_matches[:5]:
    print(m[:300])

# Stampa porzioni del HTML che contengono 'reader' o 'page'
reader_sections = re.findall(r'.{0,100}(?:reader|page-image|chapter-page).{0,200}', html, re.I)
print(f'\n=== Sezioni reader/page: {len(reader_sections)} ===')
for s in reader_sections[:10]:
    print(s.strip()[:300])
