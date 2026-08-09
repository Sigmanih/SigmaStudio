import React, { useState, useEffect } from 'react';
import {
  Server, Wrench, Database, Cpu, Zap, Settings, Globe, Play, RefreshCw,
  CheckCircle2, Search, FileText, ChevronRight, Terminal, Check, XCircle,
  Home, Mail, MessageSquare, Shield, Layers, Brain, Calendar, Hash, Phone, GitBranch, Eye, Activity,
  ShieldCheck, ShieldAlert, Plug
} from 'lucide-react';
import McpIntegrationsPanel from './McpIntegrationsPanel';

// MCP Category System & Theme Badges
const MCP_CATEGORIES = [
  { id: 'all', name: 'Tutte le Skills', icon: '⚡', color: '#00d2ff', bg: 'rgba(0, 210, 255, 0.12)' },
  { id: 'memory', name: 'Memoria & Context', icon: '🧠', color: '#bc8cff', bg: 'rgba(188, 140, 255, 0.12)' },
  { id: 'smart_home', name: 'Domotica & Smart Home', icon: '🏠', color: '#3fb950', bg: 'rgba(63, 185, 80, 0.12)' },
  { id: 'email', name: 'Email & Produttività', icon: '📧', color: '#58a6ff', bg: 'rgba(88, 166, 255, 0.12)' },
  { id: 'calendar', name: 'Calendario & Agenda', icon: '📅', color: '#58a6ff', bg: 'rgba(88, 166, 255, 0.12)' },
  { id: 'messaging', name: 'Messaggistica & Notifiche', icon: '💬', color: '#25d366', bg: 'rgba(37, 211, 102, 0.12)' },
  { id: 'dev_tools', name: 'Developer & Code Tools', icon: '🛠️', color: '#d29922', bg: 'rgba(210, 153, 34, 0.12)' },
  { id: 'web_intel', name: 'Web & Ricerca Intelligence', icon: '🌐', color: '#ff7b72', bg: 'rgba(255, 123, 114, 0.12)' },
  { id: 'hardware', name: 'Hardware & GPU Compute', icon: '⚡', color: '#00f2fe', bg: 'rgba(0, 242, 254, 0.12)' },
  { id: 'training', name: 'Training & Modelli', icon: '🎓', color: '#bc8cff', bg: 'rgba(188, 140, 255, 0.12)' },
  { id: 'inference', name: 'Inferenza & Routing', icon: '🧭', color: '#00d2ff', bg: 'rgba(0, 210, 255, 0.12)' },
  { id: 'benchmark', name: 'Benchmark & Valutazione', icon: '📊', color: '#d29922', bg: 'rgba(210, 153, 34, 0.12)' },
  { id: 'external', name: 'Server MCP Esterni', icon: '🔌', color: '#ff7b72', bg: 'rgba(255, 123, 114, 0.12)' },
];

// Rich Tool Metadata Catalog for Builtin & Extended MCP Skills
const TOOL_METADATA = {
  // --- Memoria & Context ---
  'query_vector_db': {
    category: 'memory',
    title: 'Vector Memory RAG',
    icon: Database,
    color: '#bc8cff',
    server: 'Memory MCP',
    summary: 'Ricerca semantica FAISS/Chroma nel vector store di conoscenza.',
    explanation: 'Interroga il database vettoriale per recuperare frammenti di codice, whitepaper o documentazione ad alta pertinenza semantica.',
    useCase: 'L\'agente AI cerca concetti matematici o architetture di codice pertinenti alla richiesta dell\'utente.',
    payloadSample: { query: 'Sigma Studio RAG architecture', limit: 5 }
  },
  'save_episodic_memory': {
    category: 'memory',
    title: 'Episodic Memory Manager',
    icon: Brain,
    color: '#bc8cff',
    server: 'Memory MCP',
    summary: 'Salvataggio permanente di fatti e preferenze utente tra sessioni.',
    explanation: 'Conserva nella memoria a lungo termine le preferenze espresse dall\'utente, direttive di stile o note importanti.',
    useCase: 'Registra che l\'utente preferisce lo stile scuro glassmorphism per le interfacce.',
    payloadSample: { session_id: 'active_session', memory_key: 'user_pref', content: 'Preferisco il tema scuro' }
  },
  'search_knowledge_graph': {
    category: 'memory',
    title: 'Knowledge Graph Search',
    icon: Layers,
    color: '#bc8cff',
    server: 'Memory MCP',
    summary: 'Navigazione delle entità concettuali e relazioni nel grafo di memoria.',
    explanation: 'Scansiona i collegamenti tra argomenti principali e sottoargomenti per individuare dipendenze concettuali.',
    useCase: 'Scoprire quali sottoargomenti sono collegati a un manifesto teorico.',
    payloadSample: { topic: 'matematica' }
  },
  'swap_kv_cache': {
    category: 'memory',
    title: 'KV-Cache Context Swapper',
    icon: Cpu,
    color: '#bc8cff',
    server: 'Inference MCP',
    summary: 'Trasferimento al volo dello stato della cache dei token tra Agenti.',
    explanation: 'Consente lo scambio ad altissima frequenza della cache dei token tra Agenti AI senza dover rielaborare il contesto da zero.',
    useCase: 'Passaggio istantaneo del contesto tra l\'agente Ricercatore e il Code Architect.',
    payloadSample: { session_id: 'swarm_session_1', target_agent: 'code_architect' }
  },

  // --- Domotica & Smart Home ---
  // Nomi allineati agli strumenti che l'hub registra davvero: le voci che
  // stavano qui prima ('ha_entity_control', 'whatsapp_notify', ...) non avevano
  // nessun server dietro e rispondevano "Tool not found" al collaudo.
  'ha_list_entities': {
    category: 'smart_home',
    title: 'Inventario Casa',
    icon: Home,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Elenca luci, prese, sensori e termostati con il loro stato attuale.',
    explanation: 'Legge da Home Assistant le entita della casa, comprese quelle Zigbee, Matter e Bluetooth gia integrate li.',
    useCase: 'L\'agente scopre quali luci esistono prima di poterle comandare.',
    payloadSample: { domain: 'light', limit: 20 }
  },
  'ha_entity_state': {
    category: 'smart_home',
    title: 'Stato Entita & Sensori',
    icon: Activity,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Legge stato e attributi di una singola entita, sensori compresi.',
    explanation: 'Ottiene temperatura, consumo elettrico, presenza o qualunque altro valore esposto da un dispositivo.',
    useCase: 'Verifica il consumo elettrico prima di avviare un training lungo.',
    payloadSample: { entity_id: 'sensor.power_consumption' }
  },
  'ha_light_set': {
    category: 'smart_home',
    title: 'Controllo Luci',
    icon: Home,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Comanda una o piu luci: stato, luminosita, colore, temperatura, effetti e dissolvenza.',
    explanation: 'Accetta una entita, un elenco o un\'intera area: "spegni le luci dell\'ufficio" e una sola chiamata e una sola conferma, non una per lampada.',
    useCase: 'Spegne tutte le luci dell\'ufficio al termine dell\'elaborazione notturna.',
    payloadSample: { area: 'ufficio', state: 'off', transition: 2 }
  },
  'ha_list_areas': {
    category: 'smart_home',
    title: 'Stanze & Aree',
    icon: Layers,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Elenca le stanze configurate e le entita di ciascuna.',
    explanation: 'Dice quale nome passare al parametro area degli altri strumenti, senza tirare a indovinare.',
    useCase: 'Scopre come si chiama davvero la stanza prima di comandarla.',
    payloadSample: { domain: 'light' }
  },
  'ha_switch_set': {
    category: 'smart_home',
    title: 'Prese e Interruttori',
    icon: Zap,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Accende o spegne prese intelligenti, una alla volta o per stanza.',
    explanation: 'Comanda prese e interruttori smart, utile per staccare corrente a periferiche e stampanti.',
    useCase: 'Stacca la presa della stampante 3D a stampa finita.',
    payloadSample: { entity_id: 'switch.stampante_3d', state: 'off' }
  },
  'ha_climate_set': {
    category: 'smart_home',
    title: 'Termostato & Clima',
    icon: Zap,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Imposta temperatura obiettivo e modalita di un climatizzatore.',
    explanation: 'Regola riscaldamento e raffrescamento, utile per tenere a bada la temperatura durante i carichi GPU.',
    useCase: 'Porta il condizionatore a 22 gradi quando parte un training lungo.',
    payloadSample: { entity_id: 'climate.studio', temperature: 22, hvac_mode: 'cool' }
  },
  'ha_call_service': {
    category: 'smart_home',
    title: 'Servizio Home Assistant',
    icon: Settings,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Chiama qualunque servizio Home Assistant, per i dispositivi fuori dagli altri strumenti.',
    explanation: 'Via di fuga generica: tapparelle, media player, aspirapolvere, tutto cio che espone un servizio.',
    useCase: 'Abbassa le tapparelle dello studio al tramonto.',
    payloadSample: { domain: 'cover', service: 'close_cover', entity_id: 'cover.studio' }
  },

  // --- Email & Produttivita ---
  'send_email': {
    category: 'email',
    title: 'Invio Email SMTP',
    icon: Mail,
    color: '#58a6ff',
    server: 'Email MCP',
    summary: 'Spedisce report, notifiche e risposte dall\'indirizzo configurato.',
    explanation: 'Invia email di testo o HTML. Parte a nome dell\'operatore, quindi richiede sempre conferma.',
    useCase: 'Spedisce il report di collaudo al team a fine pipeline.',
    payloadSample: { to: 'destinatario@esempio.it', subject: 'Report task completato', body: 'La pipeline e stata completata.' }
  },
  'read_inbox': {
    category: 'email',
    title: 'Lettura Posta',
    icon: FileText,
    color: '#58a6ff',
    server: 'Email MCP',
    summary: 'Legge i messaggi piu recenti con anteprima del corpo.',
    explanation: 'Scansiona la casella in sola lettura: consultare la posta non la segna come letta.',
    useCase: 'Riassume le email non lette dell\'ultima ora.',
    payloadSample: { folder: 'INBOX', unread_only: true, limit: 5 }
  },
  'search_email': {
    category: 'email',
    title: 'Ricerca Messaggi',
    icon: Search,
    color: '#58a6ff',
    server: 'Email MCP',
    summary: 'Cerca messaggi per mittente o per oggetto.',
    explanation: 'Filtra la casella su criteri IMAP, per ritrovare una conversazione senza scorrerla a mano.',
    useCase: 'Trova le email di un cliente sul progetto in corso.',
    payloadSample: { sender: 'cliente@esempio.it', limit: 10 }
  },
  'calendar_list_events': {
    category: 'calendar',
    title: 'Agenda & Eventi',
    icon: Calendar,
    color: '#58a6ff',
    server: 'Calendar MCP',
    summary: 'Elenca gli eventi del calendario in una finestra temporale.',
    explanation: 'Legge da un calendario CalDAV, quindi funziona con Google, Nextcloud, iCloud e Fastmail.',
    useCase: 'Verifica gli impegni prima di programmare un training notturno.',
    payloadSample: { days_ahead: 7, limit: 20 }
  },
  'calendar_create_event': {
    category: 'calendar',
    title: 'Creazione Evento',
    icon: Calendar,
    color: '#58a6ff',
    server: 'Calendar MCP',
    summary: 'Crea un evento nel calendario configurato.',
    explanation: 'Aggiunge un appuntamento con titolo, orari, luogo e note. Scrive sul calendario, quindi chiede conferma.',
    useCase: 'Fissa la revisione dell\'architettura per domani alle 15.',
    payloadSample: { summary: 'Revisione architettura MCP', start: '2026-08-09T15:00:00' }
  },
  'calendar_list_calendars': {
    category: 'calendar',
    title: 'Calendari Disponibili',
    icon: Calendar,
    color: '#58a6ff',
    server: 'Calendar MCP',
    summary: 'Elenca i calendari raggiungibili con le credenziali configurate.',
    explanation: 'Serve in fase di configurazione, per sapere quale nome scrivere nelle impostazioni.',
    useCase: 'Scopre il nome esatto del calendario di lavoro.',
    payloadSample: {}
  },

  // --- Messaggistica & Notifiche ---
  'telegram_send_message': {
    category: 'messaging',
    title: 'Notifica Telegram',
    icon: MessageSquare,
    color: '#25d366',
    server: 'Messaging MCP',
    summary: 'Invia un messaggio Telegram alla chat configurata.',
    explanation: 'Il canale con cui un lavoro lungo avvisa che e finito senza tenere l\'operatore davanti allo schermo.',
    useCase: 'Avvisa su Telegram quando il training del modello e completato.',
    payloadSample: { text: 'Training completato: loss finale 0.42' }
  },
  'telegram_get_chat_id': {
    category: 'messaging',
    title: 'Scopri Chat ID',
    icon: Hash,
    color: '#25d366',
    server: 'Messaging MCP',
    summary: 'Legge gli aggiornamenti del bot per trovare il chat id da configurare.',
    explanation: 'Serve una volta sola, in fase di configurazione: scrivi al bot e poi esegui questo strumento.',
    useCase: 'Recupera il chat id senza doverlo cercare a mano.',
    payloadSample: {}
  },
  'slack_post_message': {
    category: 'messaging',
    title: 'Messaggio Slack',
    icon: Hash,
    color: '#25d366',
    server: 'Messaging MCP',
    summary: 'Pubblica un messaggio nel canale collegato al webhook.',
    explanation: 'Spedisce alert e log di build nei canali di squadra tramite un webhook in ingresso.',
    useCase: 'Aggiorna il canale della squadra a fine deploy.',
    payloadSample: { text: 'Deploy completato su Sigma Studio' }
  },

  // --- Developer & Code Tools ---
  'run_pytest': {
    category: 'dev_tools',
    title: 'Pytest Suite Runner',
    icon: CheckCircle2,
    color: '#d29922',
    server: 'Developer MCP',
    summary: 'Esecuzione automatizzata della test suite Python pytest.',
    explanation: 'Esegue i test unitari e di integrazione Python nella workspace, restituendo lo stack trace degli errori.',
    useCase: 'Verifica che tutte le funzioni del backend superino i test prima del commit.',
    payloadSample: { test_path: 'tests/test_mcp_servers.py' }
  },
  'create_workspace_file': {
    category: 'dev_tools',
    title: 'Workspace File Manager',
    icon: FileText,
    color: '#d29922',
    server: 'Developer MCP',
    summary: 'Creazione e scrittura di file sorgente e documentazione.',
    explanation: 'Crea o aggiorna in modo sicuro file di codice, note in markdown o configurazioni nella cartella del progetto.',
    useCase: 'Genera automaticamente un nuovo script Python per l\'elaborazione dei dati.',
    payloadSample: { path: 'data/notes.md', content: '# Note di ricerca' }
  },
  'execute_sandbox_code': {
    category: 'dev_tools',
    title: 'Python Code Sandbox',
    icon: Terminal,
    color: '#d29922',
    server: 'Developer MCP',
    summary: 'Esecuzione isolata di codice in ambiente sandbox protetto.',
    explanation: 'Esegue frammenti di codice Python in un ambiente isolato senza rischi per il sistema principale.',
    useCase: 'Calcolo di matrici e verifica matematica di algoritmi al volo.',
    payloadSample: { code: 'print("MCP Sandbox test OK")' }
  },
  'git_status': {
    category: 'dev_tools',
    title: 'Git Repository Inspector',
    icon: GitBranch,
    color: '#d29922',
    server: 'Developer MCP',
    summary: 'Ispezione dello stato Git, modifiche e file staging.',
    explanation: 'Scansiona lo stato dei file modificati, staged o non tracciati all\'interno del repository del progetto.',
    useCase: 'Controlla quali file sono stati modificati prima di effettuare un commit.',
    payloadSample: {}
  },

  // --- Web & Ricerca Intelligence ---
  'search_web': {
    category: 'web_intel',
    title: 'Brave Web Search API',
    icon: Search,
    color: '#ff7b72',
    server: 'Network MCP',
    summary: 'Ricerca web in tempo reale via Brave Search per dati aggiornati.',
    explanation: 'Effettua query sui motori di ricerca per estrarre informazioni aggiornate in tempo reale sul Web.',
    useCase: 'Trova le ultime novità ufficiali su librerie o framework di AI.',
    payloadSample: { query: 'Sigma Studio AI', max_results: 3 }
  },
  'fetch_web_page': {
    category: 'web_intel',
    title: 'Web Scraper & Markdown Extractor',
    icon: Globe,
    color: '#ff7b72',
    server: 'Network MCP',
    summary: 'Estrazione HTML da pagine web convertiti in Markdown pulito.',
    explanation: 'Scarica il contenuto di qualsiasi pagina web, rimuove script/pubblicità e converte il testo in Markdown snello.',
    useCase: 'Legge una pagina di documentazione online per integrarla nel contesto dell\'agente.',
    payloadSample: { url: 'https://wikipedia.org' }
  },

  // --- Hardware & GPU Compute ---
  'get_hardware_status': {
    category: 'hardware',
    title: 'GPU & VRAM Telemetry',
    icon: Cpu,
    color: '#00f2fe',
    server: 'Hardware MCP',
    summary: 'Monitoraggio carico GPU NVIDIA, VRAM e temperatura.',
    explanation: 'Legge in tempo reale la telemetria dell\'hardware (temperatura GPU, memoria VRAM utilizzata, utilizzo CPU).',
    useCase: 'Verifica la VRAM disponibile prima di allocare un nuovo modello LLM pesante.',
    payloadSample: {}
  },
  'clear_vram_cache': {
    category: 'hardware',
    title: 'VRAM Cache Cleaner',
    icon: RefreshCw,
    color: '#00f2fe',
    server: 'Hardware MCP',
    summary: 'Liberazione immediata della memoria VRAM allocata.',
    explanation: 'Forza la pulizia della cache della memoria video per evitare errori di Out-Of-Memory (OOM).',
    useCase: 'Svuota la VRAM occupata da PyTorch dopo un processo di training o inferenza.',
    payloadSample: {}
  }
};

export default function McpHubTab() {
  const [servers, setServers] = useState([]);
  const [tools, setTools] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTool, setSelectedTool] = useState(null);
  const [toolArgs, setToolArgs] = useState('{}');
  const [testResult, setTestResult] = useState(null);
  const [testingTool, setTestingTool] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('catalog'); // 'catalog' | 'tester' | 'console' | 'resources'

  // Filtering & Search state
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchKeyword, setSearchKeyword] = useState('');
  // Mirrors the server-side policy; refilled from /api/mcp/tools on every load.
  const [disabledTools, setDisabledTools] = useState({});
  const [autoApprove, setAutoApprove] = useState(false);

  // Hover popover tooltip state
  const [hoveredTool, setHoveredTool] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // Diagnostic Console State
  const [diagnosticLogs, setDiagnosticLogs] = useState([]);
  const [runningFullTest, setRunningFullTest] = useState(false);

  const loadMcpData = async () => {
    setLoading(true);
    try {
      const [resServers, resTools, resResources] = await Promise.all([
        fetch('/api/mcp/servers'),
        fetch('/api/mcp/tools'),
        fetch('/api/mcp/resources')
      ]);

      // The hub is the only source of truth for what exists. The tab used to
      // pad this list with catalogue entries that had no server behind them,
      // so nine skills sat in the window answering "Tool not found" on click.
      let backendTools = [];
      if (resTools.ok) {
        const d = await resTools.json();
        backendTools = d.tools || [];
        setAutoApprove(!!d.auto_approve);
        // The switches live on the server: a rule the browser keeps to itself
        // is not a rule the agents obey.
        // `enabled === false` e non `!enabled`: contro un backend non ancora
        // riavviato il campo manca, e la seconda forma spegnerebbe tutto.
        const off = {};
        backendTools.forEach(t => { if (t.enabled === false) off[t.name] = true; });
        setDisabledTools(off);
      }
      setTools(backendTools);

      if (resServers.ok) {
        const d = await resServers.json();
        setServers(d.servers || []);
      }

      if (resResources.ok) {
        const d = await resResources.json();
        setResources(d.resources || []);
      }

      if (backendTools.length > 0 && !selectedTool) {
        const first = backendTools[0];
        setSelectedTool(first);
        const meta = TOOL_METADATA[first.name];
        setToolArgs(JSON.stringify(meta?.payloadSample || {}, null, 2));
      }
    } catch (e) {
      console.error("Error loading MCP data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMcpData();
  }, []);

  const toggleToolStatus = async (toolName, e) => {
    e.stopPropagation();
    const enabled = !!disabledTools[toolName];        // currently off → turning on
    setDisabledTools(prev => ({ ...prev, [toolName]: !prev[toolName] }));
    try {
      const res = await fetch('/api/mcp/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: toolName, enabled })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const off = {};
      (data.disabled_tools || []).forEach(name => { off[name] = true; });
      setDisabledTools(off);                          // server state wins
    } catch (err) {
      console.error('Salvataggio interruttore MCP fallito:', err);
      setDisabledTools(prev => ({ ...prev, [toolName]: !prev[toolName] }));
    }
  };

  const toggleAutoApprove = async () => {
    const next = !autoApprove;
    setAutoApprove(next);
    try {
      await fetch('/api/mcp/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_approve: next })
      });
    } catch (err) {
      console.error('Cambio modalità approvazione fallito:', err);
      setAutoApprove(!next);
    }
  };

  const selectToolWithDefaults = (tool) => {
    setSelectedTool(tool);
    const meta = TOOL_METADATA[tool.name];
    const sample = meta?.payloadSample || {};
    setToolArgs(JSON.stringify(sample, null, 2));
    setTestResult(null);
  };

  const handleMouseEnterCard = (tool, e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPos({
      x: rect.left + rect.width / 2,
      y: rect.top - 8
    });
    setHoveredTool(tool);
  };

  const handleTestTool = async () => {
    if (!selectedTool) return;
    setTestingTool(true);
    setTestResult(null);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(toolArgs);
      } catch {
        parsedArgs = { query: toolArgs };
      }

      const res = await fetch('/api/mcp/rpc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: `test-${Date.now()}`,
          method: 'tools/call',
          params: {
            name: selectedTool.name,
            arguments: parsedArgs
          }
        })
      });
      const data = await res.json();
      setTestResult(data.result || data);
    } catch (e) {
      setTestResult({ isError: true, content: [{ type: 'text', text: e.message }] });
    } finally {
      setTestingTool(false);
    }
  };

  const handleTestAllTools = async () => {
    setRunningFullTest(true);
    setActiveSubTab('console');
    setDiagnosticLogs([{ time: new Date().toLocaleTimeString(), message: '🚀 Avvio Collaudo Diagnostico Integrale delle MCP Skills...', type: 'info' }]);

    let passedCount = 0;
    for (const tool of tools) {
      if (disabledTools[tool.name]) {
        setDiagnosticLogs(prev => [...prev, {
          time: new Date().toLocaleTimeString(),
          message: `⏸️ [${tool.server}] Tool '${tool.name}' disabilitato dall'utente (Saltato).`,
          type: 'warning'
        }]);
        continue;
      }

      const meta = TOOL_METADATA[tool.name];
      const args = meta?.payloadSample || {};
      try {
        const res = await fetch('/api/mcp/rpc', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: `diag-${Date.now()}`,
            method: 'tools/call',
            params: { name: tool.name, arguments: args }
          })
        });
        const data = await res.json();
        const isErr = data.error || (data.result && data.result.isError);
        if (!isErr) {
          passedCount++;
          setDiagnosticLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            message: `✅ [${tool.server}] Tool '${tool.name}' superato con successo.`,
            type: 'success'
          }]);
        } else {
          setDiagnosticLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            message: `❌ [${tool.server}] Tool '${tool.name}' risposto: ${JSON.stringify(data.error || data.result)}`,
            type: 'error'
          }]);
        }
      } catch (err) {
        setDiagnosticLogs(prev => [...prev, {
          time: new Date().toLocaleTimeString(),
          message: `❌ [${tool.server}] Tool '${tool.name}' errore rete: ${err.message}`,
          type: 'error'
        }]);
      }
    }

    setDiagnosticLogs(prev => [...prev, {
      time: new Date().toLocaleTimeString(),
      message: `🎉 Collaudo Completato: ${passedCount}/${tools.length} MCP Tools verificate e pronte per gli Agenti AI!`,
      type: 'summary'
    }]);
    setRunningFullTest(false);
  };

  // Filter tools by Category and Search Keyword
  const filteredTools = tools.filter(tool => {
    const meta = TOOL_METADATA[tool.name] || {};
    // Il server sa dove sta ogni strumento; la scheda descrittiva è solo la
    // presentazione, e la sua categoria è rimasta indietro rispetto all'hub.
    const cat = tool.category || meta.category || 'dev_tools';
    const matchesCat = selectedCategory === 'all' || cat === selectedCategory;
    const searchLower = searchKeyword.toLowerCase();
    const matchesSearch = !searchKeyword || 
      tool.name.toLowerCase().includes(searchLower) ||
      (meta.title && meta.title.toLowerCase().includes(searchLower)) ||
      (tool.description && tool.description.toLowerCase().includes(searchLower)) ||
      (tool.server && tool.server.toLowerCase().includes(searchLower));

    return matchesCat && matchesSearch;
  });

  const enabledCount = tools.filter(t => !disabledTools[t.name]).length;

  return (
    <div style={{ padding: '24px', background: '#0a0c14', color: '#e2e4eb', minHeight: '100%', display: 'flex', flexDirection: 'column', gap: '20px', position: 'relative' }}>
      
      {/* Header coordinato MCP Tools & Skills */}
      <div className="app-page-header">
        <div className="app-page-header-title">
          <div className="app-page-header-icon">
            <Wrench size={22} color="#00f2fe" />
          </div>
          <div>
            <h1>MCP Tools & Skills Hub</h1>
            <div className="app-page-header-subtitle">
              <span>Catalogo e orchestrazione delle competenze estese via Model Context Protocol</span>
              <span>•</span>
              <span style={{ color: '#3fb950', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>
                {enabledCount}/{tools.length} Skills Attive
              </span>
            </div>
          </div>
        </div>
        <div className="app-page-header-actions">
          {/* Modalità di approvazione. Gli strumenti che agiscono sul mondo reale
              si fermano davanti all'operatore, a meno che non scelga il contrario. */}
          <button
            onClick={toggleAutoApprove}
            title={autoApprove
              ? 'Gli agenti eseguono ogni strumento attivo senza chiedere.'
              : 'Gli strumenti che agiscono verso l\'esterno aspettano la tua conferma.'}
            style={{
              background: autoApprove ? 'rgba(210,153,34,0.14)' : 'rgba(63,185,80,0.12)',
              border: `1px solid ${autoApprove ? 'rgba(210,153,34,0.35)' : 'rgba(63,185,80,0.3)'}`,
              color: autoApprove ? '#d29922' : '#3fb950',
              padding: '8px 14px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '7px',
              fontSize: '0.78rem',
              fontWeight: 700
            }}
          >
            {autoApprove ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
            <span>{autoApprove ? 'Automatico' : 'Conferma richiesta'}</span>
          </button>
          <button
            onClick={handleTestAllTools}
            disabled={runningFullTest}
            style={{
              background: 'linear-gradient(135deg, #00d2ff, #0072ff)',
              border: 'none',
              color: '#fff',
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.78rem',
              boxShadow: '0 4px 14px rgba(0, 210, 255, 0.25)'
            }}
          >
            {runningFullTest ? <RefreshCw className="spin" size={14} /> : <Play size={14} />}
            <span>{runningFullTest ? 'Collaudo in corso...' : '⚡ Collauda Skills MCP'}</span>
          </button>
          <button
            onClick={loadMcpData}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#e2e4eb',
              padding: '8px 14px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.82rem'
            }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Aggiorna Hub</span>
          </button>
        </div>
      </div>

      {/* Primary Sub Tabs */}
      <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
        <button
          onClick={() => setActiveSubTab('catalog')}
          style={{
            background: activeSubTab === 'catalog' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'catalog' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'catalog' ? '#00d2ff' : '#8b8fa3',
            padding: '8px 18px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Wrench size={16} />
          <span>📦 Skills & Catalogo ({tools.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('tester')}
          style={{
            background: activeSubTab === 'tester' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'tester' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'tester' ? '#00d2ff' : '#8b8fa3',
            padding: '8px 18px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Play size={16} />
          <span>🧪 Collaudo Interattivo JSON-RPC</span>
        </button>

        <button
          onClick={() => setActiveSubTab('console')}
          style={{
            background: activeSubTab === 'console' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'console' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'console' ? '#00d2ff' : '#8b8fa3',
            padding: '8px 18px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Terminal size={16} />
          <span>📜 Console Log Diagnostica ({diagnosticLogs.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('connections')}
          style={{
            background: activeSubTab === 'connections' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'connections' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'connections' ? '#00d2ff' : '#8b8fa3',
            padding: '8px 18px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Plug size={16} />
          <span>🔌 Integrazioni & Server ({servers.filter(s => !s.configured).length > 0
            ? `${servers.filter(s => s.configured).length}/${servers.length}`
            : servers.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('resources')}
          style={{
            background: activeSubTab === 'resources' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'resources' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'resources' ? '#00d2ff' : '#8b8fa3',
            padding: '8px 18px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <FileText size={16} />
          <span>🔗 Risorse & URIs ({resources.length})</span>
        </button>
      </div>

      {/* Main Tab Content */}
      {activeSubTab === 'catalog' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          
          {/* Filter Pills Bar & Search Bar */}
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            
            {/* Category Filter Pills */}
            <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px', maxWidth: '100%' }}>
              {MCP_CATEGORIES.map(cat => {
                const isSelected = selectedCategory === cat.id;
                // Stessa precedenza del filtro qui sotto, altrimenti il numero
                // sul gruppo non corrisponde alle schede che poi si aprono.
                const count = cat.id === 'all'
                  ? tools.length
                  : tools.filter(t => (t.category || TOOL_METADATA[t.name]?.category || 'dev_tools') === cat.id).length;

                return (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    style={{
                      background: isSelected ? cat.bg : 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid ' + (isSelected ? cat.color : 'rgba(255, 255, 255, 0.08)'),
                      color: isSelected ? cat.color : '#8b8fa3',
                      padding: '6px 14px',
                      borderRadius: '20px',
                      cursor: 'pointer',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <span>{cat.icon}</span>
                    <span>{cat.name}</span>
                    <span style={{ fontSize: '0.68rem', padding: '1px 6px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)' }}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Search Input */}
            <div style={{ position: 'relative', minWidth: '240px' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#5a5e72' }} />
              <input
                type="text"
                placeholder="Cerca skill MCP per nome o parola chiave..."
                value={searchKeyword}
                onChange={e => setSearchKeyword(e.target.value)}
                style={{
                  width: '100%',
                  background: '#090b14',
                  border: '1px solid rgba(0, 210, 255, 0.25)',
                  borderRadius: '8px',
                  padding: '7px 10px 7px 30px',
                  color: '#e2e4eb',
                  fontSize: '0.78rem',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
              {searchKeyword && (
                <button
                  onClick={() => setSearchKeyword('')}
                  style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#8b8fa3', cursor: 'pointer', fontSize: '0.75rem' }}
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Cards Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {filteredTools.map(tool => {
              // Senza scheda descrittiva la categoria arriva comunque dal server,
              // che è quello che sa dove sta ogni strumento: la vecchia riserva
              // fissa a 'dev_tools' ne ammassava ventuno nel gruppo sbagliato.
              const meta = TOOL_METADATA[tool.name] || {
                category: tool.category || 'dev_tools',
                title: tool.name,
                icon: Wrench,
                color: '#00d2ff',
                server: tool.server || 'MCP Server',
                summary: tool.description || 'Skill MCP configurata',
                explanation: tool.description || 'Nessuna spiegazione dettagliata disponibile per questo tool.',
                useCase: 'Utilizzato dall\'Agente AI per eseguire operazioni di sistema o di memoria.'
              };

              const IconComponent = meta.icon || Wrench;
              const isDisabled = !!disabledTools[tool.name];

              return (
                <div
                  key={tool.name}
                  onMouseEnter={(e) => handleMouseEnterCard(tool, e)}
                  onMouseLeave={() => setHoveredTool(null)}
                  onClick={() => {
                    selectToolWithDefaults(tool);
                    setActiveSubTab('tester');
                  }}
                  style={{
                    background: isDisabled ? 'rgba(15, 17, 26, 0.3)' : 'rgba(15, 17, 26, 0.75)',
                    border: '1px solid ' + (isDisabled ? 'rgba(255, 255, 255, 0.04)' : meta.color + '33'),
                    borderRadius: '14px',
                    padding: '16px',
                    cursor: 'pointer',
                    position: 'relative',
                    transition: 'all 0.2s ease',
                    boxShadow: isDisabled ? 'none' : `0 4px 20px rgba(0, 0, 0, 0.25)`,
                    opacity: isDisabled ? 0.6 : 1
                  }}
                >
                  {/* Card Header */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{
                        padding: '10px',
                        background: meta.color + '18',
                        border: '1px solid ' + meta.color + '40',
                        borderRadius: '10px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <IconComponent size={20} color={meta.color} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '0.92rem', color: '#ffffff' }}>
                          {meta.title}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: meta.color, fontFamily: 'monospace', fontWeight: 600 }}>
                          tools/call → {tool.name}
                        </div>
                      </div>
                    </div>

                    {/* Enable/Disable Toggle Switch */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        onClick={(e) => toggleToolStatus(tool.name, e)}
                        title={isDisabled ? 'Abilita Skill MCP' : 'Disabilita Skill MCP'}
                        style={{
                          background: isDisabled ? 'rgba(255,255,255,0.06)' : 'rgba(63, 185, 80, 0.2)',
                          border: '1px solid ' + (isDisabled ? 'rgba(255,255,255,0.1)' : 'rgba(63, 185, 80, 0.5)'),
                          color: isDisabled ? '#8b8fa3' : '#3fb950',
                          padding: '3px 8px',
                          borderRadius: '12px',
                          fontSize: '0.62rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isDisabled ? '#8b8fa3' : '#3fb950' }}></span>
                        {isDisabled ? 'Inattiva' : 'Attiva'}
                      </button>
                    </div>
                  </div>

                  {/* Summary */}
                  <div style={{ fontSize: '0.76rem', color: '#a0a5b8', lineHeight: '1.4', marginBottom: '12px' }}>
                    {meta.summary}
                  </div>

                  {/* Footer Badges */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px solid rgba(255, 255, 255, 0.05)', gap: '6px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.65rem', padding: '2px 8px', borderRadius: '6px', background: 'rgba(255,255,255,0.04)', color: '#8b8fa3' }}>
                      {tool.server || meta.server}
                    </span>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {/* Uno strumento il cui server non è ancora configurato resta
                          visibile ma non parte: dirlo qui evita un collaudo a vuoto. */}
                      {tool.ready === false && (
                        <span style={{
                          fontSize: '0.62rem', padding: '2px 8px', borderRadius: '6px', fontWeight: 700,
                          background: 'rgba(210,153,34,0.14)', color: '#d29922',
                          border: '1px solid rgba(210,153,34,0.3)'
                        }}>
                          da configurare
                        </span>
                      )}
                      <span style={{
                        fontSize: '0.62rem', padding: '2px 8px', borderRadius: '6px', fontWeight: 700,
                        display: 'flex', alignItems: 'center', gap: '4px',
                        background: tool.safety === 'sensitive' ? 'rgba(248,81,73,0.12)' : 'rgba(63,185,80,0.12)',
                        color: tool.safety === 'sensitive' ? '#f85149' : '#3fb950',
                        border: `1px solid ${tool.safety === 'sensitive' ? 'rgba(248,81,73,0.28)' : 'rgba(63,185,80,0.28)'}`
                      }}
                        title={tool.safety === 'sensitive'
                          ? 'Agisce fuori da Sigma Studio: chiede conferma prima di partire, se non è attiva la modalità automatica.'
                          : 'Sola lettura: gli agenti possono eseguirlo da soli.'}
                      >
                        {tool.safety === 'sensitive' ? <ShieldAlert size={10} /> : <ShieldCheck size={10} />}
                        {tool.safety === 'sensitive' ? 'conferma' : 'sicuro'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Interactive Tool Tester */}
      {activeSubTab === 'tester' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Tools Selection Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h3 style={{ fontSize: '0.95rem', margin: 0, color: '#fff' }}>Seleziona Tool MCP da Collaudare</h3>
            <div style={{ maxHeight: '520px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', paddingRight: '4px' }}>
              {tools.map(tool => {
                const meta = TOOL_METADATA[tool.name] || {};
                const isSelected = selectedTool?.name === tool.name;
                const IconComponent = meta.icon || Wrench;

                return (
                  <div
                    key={tool.name}
                    onClick={() => selectToolWithDefaults(tool)}
                    style={{
                      background: isSelected ? 'rgba(0, 210, 255, 0.12)' : 'rgba(15, 17, 26, 0.6)',
                      border: isSelected ? '1px solid #00d2ff' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '10px',
                      padding: '12px 14px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <IconComponent size={18} color={meta.color || '#00d2ff'} />
                      <div>
                        <div style={{ fontWeight: 700, color: isSelected ? '#00d2ff' : '#fff', fontSize: '0.85rem' }}>
                          {meta.title || tool.name}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: '#8b8fa3', fontFamily: 'monospace' }}>
                          {tool.name}
                        </div>
                      </div>
                    </div>
                    {isSelected && <span style={{ color: '#00d2ff', fontSize: '0.8rem' }}>✓</span>}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Execution Panel */}
          <div style={{ background: 'rgba(15, 17, 26, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '14px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <h3 style={{ fontSize: '0.95rem', margin: 0, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Terminal size={16} color="#00d2ff" />
              <span>Collaudo Interattivo JSON-RPC</span>
            </h3>

            {selectedTool ? (
              <>
                <div>
                  <div style={{ fontSize: '0.88rem', color: '#00d2ff', fontWeight: 700 }}>
                    {TOOL_METADATA[selectedTool.name]?.title || selectedTool.name}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#8b8fa3', marginTop: '2px' }}>
                    {selectedTool.description || TOOL_METADATA[selectedTool.name]?.explanation}
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.72rem', color: '#8b8fa3', display: 'block', marginBottom: '6px' }}>Argomenti JSON Input:</label>
                  <textarea
                    rows={6}
                    value={toolArgs}
                    onChange={(e) => setToolArgs(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(0, 0, 0, 0.5)',
                      border: '1px solid rgba(0, 210, 255, 0.25)',
                      borderRadius: '8px',
                      color: '#00d2ff',
                      fontFamily: 'JetBrains Mono, monospace',
                      padding: '10px',
                      fontSize: '0.8rem',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <button
                  onClick={handleTestTool}
                  disabled={testingTool}
                  style={{
                    background: 'linear-gradient(135deg, #00d2ff, #0072ff)',
                    border: 'none',
                    color: '#fff',
                    padding: '10px 16px',
                    borderRadius: '8px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    fontSize: '0.85rem'
                  }}
                >
                  {testingTool ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
                  <span>{testingTool ? 'Esecuzione in corso...' : 'Esegui Tool MCP via JSON-RPC'}</span>
                </button>

                {testResult && (
                  <div style={{ marginTop: '8px' }}>
                    <div style={{ fontSize: '0.72rem', color: '#8b8fa3', marginBottom: '4px' }}>Risultato Output:</div>
                    <pre
                      style={{
                        background: '#05060a',
                        padding: '12px',
                        borderRadius: '8px',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        color: testResult.isError ? '#ff5555' : '#50fa7b',
                        fontSize: '0.75rem',
                        overflowX: 'auto',
                        maxHeight: '200px'
                      }}
                    >
                      {JSON.stringify(testResult, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: '#8b8fa3', fontSize: '0.85rem', textAlign: 'center', padding: '40px 0' }}>
                Seleziona uno strumento dal catalogo per testarlo in tempo reale.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Diagnostic Console */}
      {activeSubTab === 'console' && (
        <div style={{ background: '#05060a', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '14px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.92rem', fontWeight: 700, color: '#00d2ff' }}>
              <Terminal size={18} />
              <span>Console Log Diagnostico integrato MCP Tools</span>
            </div>
            <button
              onClick={() => setDiagnosticLogs([])}
              style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', color: '#8b8fa3', borderRadius: '6px', padding: '4px 10px', fontSize: '0.75rem', cursor: 'pointer' }}
            >
              Pulisci Console
            </button>
          </div>

          <div style={{ fontFamily: 'monospace', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '420px', overflowY: 'auto' }}>
            {diagnosticLogs.length === 0 ? (
              <div style={{ color: '#8b8fa3', padding: '30px 0', textAlign: 'center' }}>
                Premere "⚡ Collauda Skills MCP" per avviare il test automatizzato di tutte le competenze registrate.
              </div>
            ) : (
              diagnosticLogs.map((log, idx) => (
                <div
                  key={idx}
                  style={{
                    color: log.type === 'success' ? '#50fa7b' : log.type === 'error' ? '#ff5555' : log.type === 'summary' ? '#00d2ff' : '#f1fa8c',
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                    paddingBottom: '4px'
                  }}
                >
                  <span style={{ color: '#8b8fa3', marginRight: '8px' }}>[{log.time}]</span>
                  <span>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Integrazioni native e server MCP di terze parti */}
      {activeSubTab === 'connections' && (
        <McpIntegrationsPanel servers={servers} onChanged={loadMcpData} />
      )}

      {/* Resources & URIs Tab */}
      {activeSubTab === 'resources' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
          {resources.map(res => (
            <div
              key={res.uri}
              style={{
                background: 'rgba(15, 17, 26, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                padding: '16px'
              }}
            >
              <div style={{ fontWeight: 700, color: '#00d2ff', fontSize: '0.9rem', marginBottom: '4px' }}>{res.name}</div>
              <div style={{ fontSize: '0.75rem', color: '#3fb950', fontFamily: 'monospace', marginBottom: '8px' }}>{res.uri}</div>
              <div style={{ fontSize: '0.75rem', color: '#8b8fa3' }}>{res.description}</div>
            </div>
          ))}
        </div>
      )}

      {/* FLOATING HOVER EXPLANATION POPOVER TOOLTIP */}
      {hoveredTool && (() => {
        const meta = TOOL_METADATA[hoveredTool.name] || {};
        const IconComp = meta.icon || Wrench;
        const isDisabled = !!disabledTools[hoveredTool.name];

        return (
          <div
            style={{
              position: 'fixed',
              left: Math.min(window.innerWidth - 360, Math.max(20, tooltipPos.x - 170)),
              top: Math.max(20, tooltipPos.y - 210),
              width: '340px',
              background: 'linear-gradient(145deg, #121424, #1a1d33)',
              border: '1px solid ' + (meta.color || '#00d2ff'),
              borderRadius: '14px',
              padding: '16px',
              boxShadow: '0 12px 36px rgba(0, 0, 0, 0.7), 0 0 20px ' + (meta.color || '#00d2ff') + '33',
              zIndex: 99999,
              pointerEvents: 'none',
              color: '#e2e4eb',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <IconComp size={18} color={meta.color || '#00d2ff'} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#ffffff' }}>{meta.title || hoveredTool.name}</div>
                  <div style={{ fontSize: '0.62rem', color: meta.color || '#00d2ff', fontFamily: 'monospace' }}>
                    {hoveredTool.server || meta.server}
                  </div>
                </div>
              </div>
              <span style={{
                fontSize: '0.6rem',
                padding: '2px 8px',
                borderRadius: '10px',
                background: isDisabled ? 'rgba(255,85,85,0.15)' : 'rgba(63,185,80,0.15)',
                color: isDisabled ? '#ff5555' : '#3fb950',
                fontWeight: 700
              }}>
                {isDisabled ? '● Disabilitata' : '● Attiva'}
              </span>
            </div>

            {/* Detailed Explanation */}
            <div>
              <div style={{ fontSize: '0.65rem', fontWeight: 700, color: '#8b8fa3', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '2px' }}>
                📖 Spiegazione & Funzionamento:
              </div>
              <div style={{ fontSize: '0.75rem', color: '#e2e4eb', lineHeight: '1.4' }}>
                {meta.explanation || hoveredTool.description}
              </div>
            </div>

            {/* Agent AI Use Case */}
            {meta.useCase && (
              <div style={{ background: 'rgba(0, 210, 255, 0.06)', border: '1px solid rgba(0, 210, 255, 0.15)', borderRadius: '8px', padding: '8px 10px' }}>
                <div style={{ fontSize: '0.62rem', fontWeight: 700, color: '#00d2ff', textTransform: 'uppercase', marginBottom: '2px' }}>
                  💡 Caso d'Uso Agente AI:
                </div>
                <div style={{ fontSize: '0.72rem', color: '#b0e7ff', fontStyle: 'italic', lineHeight: '1.3' }}>
                  "{meta.useCase}"
                </div>
              </div>
            )}

            {/* JSON-RPC Signature */}
            <div style={{ fontSize: '0.65rem', color: '#8b8fa3', fontFamily: 'monospace', display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '6px' }}>
              <span>JSON-RPC: tools/call</span>
              <span style={{ color: '#00d2ff' }}>{hoveredTool.name}</span>
            </div>
          </div>
        );
      })()}

    </div>
  );
}
