# Contributing to Sigma Studio

Grazie per l'interesse nel contribuire a Sigma Studio! 🎉

Questo documento spiega come partecipare allo sviluppo del progetto.

## 📋 Contributor License Agreement (CLA)

Prima che il tuo contributo possa essere accettato, devi firmare il nostro
**Contributor License Agreement (CLA)**. Questo è necessario perché Sigma Studio
è un progetto dual-licensed (AGPL v3 + Commercial) e ci serve il diritto di
includere il tuo contributo in entrambe le edizioni.

Al tuo primo Pull Request, un bot ti chiederà automaticamente di firmare il CLA.
È un'operazione rapida e una tantum.

### Cosa concedi con il CLA

- Una licenza perpetua, non esclusiva, per usare il tuo contributo sotto
  qualsiasi licenza (inclusa la licenza commerciale)
- **Non cedi il copyright**: mantieni tutti i diritti sul tuo codice
- Il tuo contributo sarà disponibile sia nella Community Edition (AGPL v3)
  sia nella Enterprise Edition

## 🚀 Come Contribuire

### Segnalare un Bug

1. Controlla che il bug non sia già stato segnalato nelle [Issues](https://github.com/Sigmanih/SigmaStudio/issues)
2. Apri una nuova Issue usando il template **Bug Report**
3. Includi: versione di Sigma Studio, sistema operativo, passi per riprodurre, comportamento atteso vs. effettivo

### Proporre una Funzionalità

1. Apri una Issue con il template **Feature Request**
2. Descrivi il caso d'uso, non solo la soluzione tecnica
3. Attendi feedback dal team prima di iniziare a scrivere codice

### Inviare un Pull Request

1. Forka il repository e crea un branch dal `main`:
   ```bash
   git checkout -b feature/nome-descrittivo
   ```
2. Scrivi il codice seguendo le convenzioni del progetto (vedi sotto)
3. Assicurati che i test passino:
   ```bash
   python -m pytest tests/ -q
   npm --prefix sigma_studio run lint:undef
   ```
4. Committa con messaggi in italiano, all'imperativo:
   ```
   Aggiungi endpoint per l'export dei modelli
   ```
5. Apri il PR verso `main` con una descrizione chiara

## 📐 Convenzioni di Codice

### Python (Backend)

- Python 3.10+, niente stub `pass` o segnaposto
- Logging via `from core.logger import get_logger`, mai `print`
- Percorsi con `pathlib.Path`, mai concatenazioni di stringhe
- Il codice deve girare su Windows 11 **e** Raspberry Pi 5 (aarch64, 8 GB RAM)
- Header SPDX obbligatorio in ogni nuovo file:
  ```python
  # SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Commercial
  # Copyright (c) 2024-2026 Diego Saitta
  ```

### React (Frontend)

- Solo React standard: `useState`, `useEffect`, `useCallback`
- Icone esclusivamente da `lucide-react`
- Niente librerie di componenti (`@mui`, `antd`, `bootstrap`, `tailwind`)
- Gli stili stanno in `sigma_studio/src/styles/`
- Header SPDX obbligatorio in ogni nuovo file:
  ```javascript
  // SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Commercial
  // Copyright (c) 2024-2026 Diego Saitta
  ```

### Commit

- Messaggi in italiano, all'imperativo
- Una modifica logica per commit
- Descrivere il **perché**, non il cosa

## 🏗️ Architettura

Prima di modificare il kernel, leggi [`architettura.md`](architettura.md) per
capire le regole fondamentali:

- **Le dipendenze puntano verso il basso**: il kernel non importa mai un modulo
- **Un percorso si chiede, non si ricostruisce**: tutto passa da `core/paths.py`
- **Ogni scansione ha un budget**: nessuna operazione sul filesystem è illimitata

## 🔒 Sicurezza

Se trovi una vulnerabilità, **non** aprire una Issue pubblica. Segui la procedura
in [`SECURITY.md`](SECURITY.md).

## 📜 Licenza

Contribuendo a Sigma Studio, accetti che il tuo contributo sia distribuito sotto
i termini della licenza AGPL v3 e, tramite il CLA, anche sotto la licenza
commerciale del progetto.

---

Grazie per rendere Sigma Studio migliore! 🧬
