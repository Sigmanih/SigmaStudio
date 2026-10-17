import json
import os
from pathlib import Path

import easyocr

reader = easyocr.Reader(['it', 'en'], gpu=False, verbose=False)

base = Path('data/progetti/mx0/Volume 01/Mx0 Capitolo 01 Scan ITA')
pages = sorted([f for f in os.listdir(base) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

risultati = []
for nome in pages:
    percorso = base / nome
    try:
        risultati_pagina = reader.readtext(str(percorso), detail=1, paragraph=False)
        dialoghi = []
        for idx, (bbox, testo, conf) in enumerate(risultati_pagina, 1):
            if conf < 0.3 or not testo.strip():
                continue
            x_min = int(min(p[0] for p in bbox))
            y_min = int(min(p[1] for p in bbox))
            x_max = int(max(p[0] for p in bbox))
            y_max = int(max(p[1] for p in bbox))
            dialoghi.append({
                'indice': idx,
                'posizione': [x_min, y_min, x_max, y_max],
                'testo_rilevato': testo.strip(),
                'confidenza': round(float(conf), 3)
            })
        risultati.append({
            'pagina': nome,
            'nuvolette_trovate': len(dialoghi),
            'dialoghi': dialoghi
        })
    except Exception as e:
        risultati.append({'pagina': nome, 'errore': str(e), 'dialoghi': []})

out = base / 'ocr_risultati.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(risultati, f, ensure_ascii=False, indent=2)

totale = sum(p.get('nuvolette_trovate', 0) for p in risultati)
print('SIGMA-CHECK ' + json.dumps({'check': 'ocr_mx0', 'pagine': len(risultati), 'dialoghi': totale}))