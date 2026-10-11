---
name: design-engineer-patterns
description: Guida operativa per agenti di sviluppo per la progettazione e generazione di siti web, componenti interattivi ed estetica premium (OriginUI, 21st.dev, Aceternity UI, Transitions.dev, Agentation pattern).
---

# Design Engineer & Agentic UI Patterns Skill

Questa skill definisce la guida operativa e gli standard di progettazione per gli agenti di **Sigma Studio** nella creazione di applicazioni web, landing page e componenti di qualità professionale, integrando i pattern dell'ecosistema moderno del Design Engineering (**OriginUI**, **21st.dev**, **Aceternity UI**, **Transitions.dev**, **Component Gallery** e **Agentation**).

---

## 1. Principi Fondamentali di Design Engineering

Ogni interfaccia generata da un agente deve suscitare un immediato **effetto "Wow"** e trasmettere la sensazione di un prodotto maturo e rifinito:

1. **Aestetica d'Impatto & Dark Mode Raffinata**:
   - Palette scura sofisticata (es. toni ardesia/notte `#0a0e1a`, `#111827`, `#0f172a`), mai nero puro `#000` piatto.
   - Accenti cromatici calibrati: ciano neon (`#00d2ff`), viola elettrico (`#a855f7`), smeraldo vivido (`#10b981`), ambra calda (`#f59e0b`).
   - Profondità visiva: glassmorphism sottile (`backdrop-filter: blur(12px)`), bordi sfumati (`rgba(255, 255, 255, 0.08)`), glow localizzati.
2. **Tipografia Moderna**:
   - Utilizzare font ad alta leggibilità e modernità: *Inter*, *Plus Jakarta Sans*, *Outfit* o *Geist Sans*.
   - Gerarchia visiva netta tra titoli `H1`, `H2`, label descrittive e testi esplicativi.
3. **Micro-interazioni & Dinamismo**:
   - Feedback istantaneo a ogni interazione: stati `:hover`, `:focus-visible`, `:active`.
   - Transizioni morbide (`transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1)`).
4. **Nessun Mockup Spoglio**:
   - Includere sempre dataset di esempio ricchi, realistici e contestualizzati (nomi, avatar, metriche, grafici, badge di stato).
   - Mai testi placeholder come "Lorem ipsum" o contenitori vuoti.

---

## 2. Cataloghi di Riferimento & Come Applicarli

### A. OriginUI / OriginKit — Primitive Atomiche Eleganti
* **A cosa serve**: Componenti funzionali ad alta usabilità e accessibilità (WCAG).
* **Pattern chiave**:
  - *Input & Form Fields*: Campi di ricerca con scorciatoie tastiera badge (`Cmd + K`), toggle password animati, indicatori di validazione dinamica inline.
  - *Slider & Controlli*: Slider continui o discreti con tooltip reattivo in tempo reale e valori percentuali.
  - *Toggles & Segmented Controls*: Switch tattili con icone interne (`lucide-react`) e indicatori di selezione scivolanti.
  - *Stat Cards*: Card metriche con badge percentuale di variazione (`+12.4%`), mini sparkline SVG e icone coerenti.

### B. 21st.dev & Magic UI — Animazioni & Layout Interattivi
* **A cosa serve**: Componenti compositi e layout bento grid pensati specificamente per l'ecosistema AI.
* **Pattern chiave**:
  - *Bento Grid Layout*: Griglie a celle asimmetriche con card contenenti preview interattive, indicatori dinamici e gradient borders.
  - *Shimmer Buttons & Beam Borders*: Pulsanti call-to-action con luce radente animata lungo il perimetro per evidenziare le azioni chiave.
  - *Marquee & Carousel*: Scorrimento continuo orizzontale per loghi partner, recensioni o tecnologie senza salti visivi.
  - *Particle & Grid Canvas*: Sfondi a matrice di punti o vettori con interazione mouse opzionale.

### C. Aceternity UI — Landing Page & Storytelling Visivo
* **A cosa serve**: Impatto cinematografico e sezioni Hero di grande effetto.
* **Pattern chiave**:
  - *Hero Lamp / Spotlight*: Cono di luce sfumato dall'alto che illumina il titolo principale con gradiente metallico o neon.
  - *3D Card Tilt*: Prospettiva CSS 3D (`perspective: 1000px; transform: rotateX(...) rotateY(...)`) al movimento del mouse.
  - *Background Beams*: Fasci di luce sinusoidali che attraversano la pagina creando dinamismo spaziale.
  - *Text Generate Effect*: Apparizione progressiva delle parole con transizione di sfocatura e opacità per intro memorabili.

### D. Transitions.dev & Native View Transitions API
* **A cosa serve**: Navigazione fluida e animazioni fra stati senza caricamenti a scatti.
* **Pattern chiave**:
  - Utilizzare la nativa `document.startViewTransition(() => updateDOM())`.
  - Permette animazioni tra schede, cambi di vista o filtri istantanei con zero byte di overhead o librerie esterne pesanti.
  - Perfetto per garantire 60fps anche su macchine leggere come Raspberry Pi 5.

### E. The Component Gallery — Standard Universale dei Design System
* **A cosa serve**: Riferimento tassonomico per l'architettura dei componenti dai migliori sistemi del settore (IBM Carbon, GitHub Primer, Shopify Polaris, Atlassian).
* **Pattern chiave**:
  - Nomenclatura coerente delle proprietà (`variant`, `size`, `isOpen`, `isDisabled`).
  - Separazione pulita tra logica di stato e presentazione.
  - Gestione chiara degli stati limite: *Loading*, *Empty*, *Error*, *Success*.

---

## 3. Il Pattern "Agentation" per l'Editing Chirurgico

Uno dei maggiori ostacoli nella generazione assistita è la sovrascrittura distruttiva di interi file per modificare un piccolo dettaglio. Il pattern **Agentation** risolve questo problema dotando il DOM di coordinate semantiche esplicite:

### 1. Marcatura dei Componenti Generati
Nei file JSX o HTML generati, decorare sempre i blocchi funzionali con attributi semantici espliciti:
```jsx
<section 
  className="pricing-section"
  data-agent-component="PricingSection"
  data-agent-id="pricing-table"
>
  <div className="pricing-card" data-agent-part="tier-card-pro">
    <h3 data-agent-part="tier-title">Pro Plan</h3>
    <button 
      className="btn-primary" 
      data-agent-action="subscribe"
      data-agent-part="cta-button"
    >
      Inizia Subito
    </button>
  </div>
</section>
```

### 2. Vantaggi Operativi per gli Agenti
* Quando l'utente chiede: *"Modifica il bottone del piano Pro per renderlo ciano neon con badge 'Più Popolare'"*:
  - L'agente non deve riscrivere 500 righe di pagina!
  - Cerca `data-agent-part="cta-button"` o `tier-card-pro` nel file mirato.
  - Esegue un `edit_file` puntuale e chirurgico, risparmiando token, azzerando i rischi di regressione e mantenendo intatto tutto il resto.

---

## 4. Regole Architetturali Importanti

1. **Per i Progetti e Siti Generati per l'Utente**:
   - Piena libertà tecnologica: Tailwind CSS, modern Vanilla CSS, Framer Motion, React, Vite, librerie grafiche come Lucide o Radix.
   - Creare file modulari e ben suddivisi (es. `components/ui/`, `components/sections/`, `styles/theme.css`).
2. **Per il Core di Sigma Studio**:
   - Come prescritto da `AGENTS.md`, il kernel e la SPA interna di Sigma Studio usano **Standard React** (`useState`, `useEffect`, `useCallback`), icone `lucide-react` e Vanilla CSS in `sigma_studio/src/styles/`.
   - Pattern avanzati come il **Thinking Orb** e le **View Transitions** si implementano nel core tramite CSS nativo o Canvas 2D leggero per la massima velocità e affidabilità multi-piattaforma.
