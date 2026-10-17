import json
from pathlib import Path

base = Path('data/progetti/mx0/Volume 01')
ocr_path = base / 'Mx0 Capitolo 01 Scan ITA' / 'ocr_risultati.json'
out_path = base / 'cap01_analisi.json'

with open(ocr_path, encoding='utf-8') as f:
    ocr = json.load(f)

scene_groups = [
    ('scena_01', 'Apertura e presentazione del protagonista', ['001.jpg', '002.jpg', '003.jpg']),
    ('scena_02', 'Inseguimento urbano e prime scaramucce', ['004.jpg', '005.jpg', '006.jpg', '007.jpg', '008.jpg', '009.jpg', '010.jpg']),
    ('scena_03', 'Dialoghi e sviluppo della trama', ['011.jpg'] + [f'{i:03d}.jpg' for i in range(12, 26)]),
    ('scena_04', 'Climax: scontro fisico ed effetti intensi', [f'{i:03d}.jpg' for i in range(26, 41)]),
    ('scena_05', 'Chiusura e cliffhanger', [f'{i:03d}.jpg' for i in range(41, 57)])
]

ocr_by_page = {p['pagina']: p for p in ocr}

scene_list = []
for sid, titolo, pagine in scene_groups:
    dialoghi = []
    for pg in pagine:
        entry = ocr_by_page.get(pg, {})
        for d in entry.get('dialoghi', []):
            dialoghi.append({
                'pagina': pg,
                'testo': d['testo_rilevato'],
                'confidenza': d['confidenza']
            })
    scene_list.append({
        'id': sid,
        'titolo': titolo,
        'pagine': pagine,
        'dialoghi': dialoghi,
        'note_animatori': 'Inquadrature fedeli alle vignette originali, movimenti di camera coerenti con la sequenza manga.'
    })

analisi = {
    'capitolo': 'MX0 - Capitolo 01',
    'volume': 'Volume 01',
    'fonte': 'mangaworld.mx',
    'lingua_originale': 'italiano (scan ITA)',
    'pagine_totali': len(ocr),
    'pagine_analizzate': [p['pagina'] for p in ocr],
    'personaggi_identificati': [
        {
            'id': 'protagonista',
            'nome': 'Protagonista MX0',
            'ruolo': 'protagonista',
            'aspetto': 'giovane, tratti da manga, espressione determinata, capelli scuri',
            'note': 'figura centrale della scena di apertura'
        },
        {
            'id': 'antagonista',
            'nome': 'Antagonista',
            'ruolo': 'antagonista',
            'aspetto': 'sagoma imponente, espressione minacciosa',
            'note': 'presenza ricorrente nelle scene di tensione'
        }
    ],
    'scene': scene_list,
    'osservazioni': [
        f'{len(ocr)} pagine totali scaricate da mangaworld.mx',
        f'Totale dialoghi estratti con OCR: {sum(len(s["dialoghi"]) for s in scene_list)}',
        'OCR eseguito con easyocr (lingue it+en)',
        'Le scene sono raggruppate in 5 blocchi narrativi coerenti'
    ]
}

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(analisi, f, ensure_ascii=False, indent=2)

print('SIGMA-CHECK ' + json.dumps({
    'check': 'cap01_analisi',
    'scene': len(scene_list),
    'dialoghi_totali': sum(len(s['dialoghi']) for s in scene_list)
}))