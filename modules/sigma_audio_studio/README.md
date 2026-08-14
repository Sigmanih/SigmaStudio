# 📻 Sigma Studio — Modulo Hi-Fi Sound & FM Radio Studio

Modulo ufficiale open-source isolato per **Sigma Studio**, disponibile nel repository comunitario [Sigmanih/SigmaStudio-Moduli](https://github.com/Sigmanih/SigmaStudio-Moduli).

---

## 🌟 Caratteristiche Principali

- 📻 **Dirette Radio FM Nazionali & Internazionali**:
  - **Mediaset / United Radio**: Virgin Radio Italia (FM 104.5), Virgin Classic Rock, Virgin Hard Rock, Radio 105 FM (FM 105.0), 105 Dance 90, 105 Miami Beats, 105 Hip Hop, Radio Monte Carlo (FM 105.5), RMC Buddha-Bar Lounge, R101 (FM 101.0).
  - **Rai Radio (Servizio Pubblico)**: Rai Radio 1 (FM 89.7), Rai Radio 2 (FM 91.7), Rai Radio 3 Classica Filodiffusione.
  - **Gruppo 24 ORE**: Radio 24 Il Sole 24 Ore (FM 104.8).
  - **Kiss Kiss Network**: Radio Kiss Kiss FM (FM 97.0).
  - **Global UK Broadcasting**: Classic FM UK Londra (FM 100.0).
  - **Indie & Lofi Web Streams**: Lofi Chillhop 24/7, Jazz Bebop Saxophone, 70-80s Rock Hits.
- 🔴 **Motore YouTube Live Integrato**: Riproduzione in background persistente tra i tab (Lofi Girl, Synthwave Radio, ecc.).
- 📁 **Lettore Locale**: Importazione e riproduzione di file `.mp3` e `.wav` direttamente dal proprio computer.
- ⚡ **Sintetizzatore DSP Procedurale a 432Hz**: Generatore nativo di frequenze binaurali e onde Alpha per il Deep Work e la concentrazione.
- 🎛️ **Equalizzatore DSP a 5 Preset**: Flat, Bass Boost, Rock Punch, Vocal Clarity, Acoustic Hall.
- 🧠 **AI Taste Profiler**: Motore di raccomandazione intelligente che adatta i suggerimenti in base all'emittente, agli strumenti e al genere ascoltato.
- 📱 **Mini-Player Fluttuante (Speed-Dial)**: Widget compatto sempre accessibile in basso a destra.
- ☀️ **Supporto Pieno Tema Chiaro & Scuro**.

---

## 📦 Struttura del Modulo

```
modules/sigma_audio_studio/
├── manifest.json                  # Definizione metadati, rotte e componenti
├── README.md                      # Questa documentazione
├── backend/                       # Endpoint e logica Python per Sigma Studio
│   ├── __init__.py
│   ├── service.py                 # Risoluzione stream e health-check stazioni
│   └── router.py                  # Router REST API (/api/modules/audio_studio/...)
└── frontend/                      # Componenti React per la UI di Sigma Studio
    ├── index.js                   # Entrypoint di esportazione componenti
    ├── AudioStudioTab.jsx         # Scheda completa Audio Studio & FM Radio
    ├── AudioFloatingWidget.jsx    # Mini-player fluttuante speed-dial
    ├── AudioContext.jsx           # Provider globale stato audio background
    └── services/
        └── musicRecommendation.js # Catalogo stazioni, broadcaster e profiler AI
```

---

## 🚀 Installazione & Disinstallazione

### Tramite interfaccia grafica (Marketplace di Sigma Studio):
1. Apri la scheda **"📦 Hub Moduli & Estensioni"** (Marketplace).
2. Individua **"Hi-Fi Sound & FM Radio Studio"**.
3. Clicca su **"📥 Installa Modulo"** (scaricherà il modulo da `Sigmanih/SigmaStudio-Moduli`).
4. La scheda `📻 Musica & Focus` apparirà immediatamente nella barra laterale sinistra.
5. Per disinstallare, clicca su **"🗑️ Disinstalla Modulo"** nel Marketplace.

### Tramite API REST:
- **Installazione**: `POST /api/marketplace/install` con `{"module_id": "audio_studio", "repo_url": "https://github.com/Sigmanih/SigmaStudio-Moduli"}`
- **Disinstallazione**: `POST /api/marketplace/uninstall` con `{"module_id": "audio_studio"}`
- **Stato Stazioni**: `GET /api/modules/audio_studio/stations`
