import React, { useState, useEffect } from 'react';
import {
  Server, Wrench, Database, Cpu, Zap, Settings, Globe, Play, RefreshCw,
  CheckCircle2, Search, FileText, ChevronRight, Terminal, Check, XCircle,
  Home, Mail, MessageSquare, Shield, Layers, Brain, Calendar, Hash, Phone, GitBranch, Eye, Activity,
  ShieldCheck, ShieldAlert, Plug, Sparkles, ArrowRight, Lock, Key
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
    title: 'Comando Luci Reali',
    icon: Home,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Accende, spegne, regola luminosita e colore RGB delle luci.',
    explanation: 'Invia il comando diretto alla luce reale selezionata, con supporto a luminosita in percentuale e colore RGB.',
    useCase: 'Impostare le luci del laboratorio su ciano al 90%.',
    payloadSample: { entity_id: 'light.luce_ufficio_1', state: 'on', brightness: 90, color_rgb: [0, 210, 255] }
  },
  'ha_switch_set': {
    category: 'smart_home',
    title: 'Comando Prese & Interruttori',
    icon: Plug,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Attiva o disattiva prese intelligenti, rele e interruttori.',
    explanation: 'Controlla l\'alimentazione di cluster GPU, macchine da caffe o apparecchi da laboratorio.',
    useCase: 'Accendere la presa smart del cluster GPU prima del training.',
    payloadSample: { entity_id: 'switch.presa_smart_gpu', state: 'on' }
  },
  'ha_climate_set': {
    category: 'smart_home',
    title: 'Controllo Climatizzatore',
    icon: Home,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Imposta la temperatura bersaglio e la modalita di climatizzazione.',
    explanation: 'Invia il setpoint di temperatura desiderato al condizionatore o alla pompa di calore.',
    useCase: 'Portare il laboratorio a 21°C prima di una sessione di lavoro.',
    payloadSample: { entity_id: 'climate.climatizzatore_lab', setpoint: 21 }
  },
  'ha_list_areas': {
    category: 'smart_home',
    title: 'Stanze & Zone Casa',
    icon: Home,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Raggruppa le entita per stanza o zona per i comandi collettivi.',
    explanation: 'Traduce richieste del tipo "le luci dell\'ufficio" nel gruppo di entita appartenenti a quella stanza.',
    useCase: 'L\'agente trova tutte le luci della stanza prima di spegnerle insieme.',
    payloadSample: { domain: 'light' }
  },
  'ha_call_service': {
    category: 'smart_home',
    title: 'Servizio Generico HA',
    icon: Home,
    color: '#3fb950',
    server: 'HomeAssistant MCP',
    summary: 'Invia un qualsiasi comando o servizio generico verso Home Assistant.',
    explanation: 'Permette di invocare qualunque servizio esposto da HA, compresi script, automazioni e notifiche.',
    useCase: 'Eseguire una scena domotica complessa definita in HA.',
    payloadSample: { domain: 'automation', service: 'trigger', entity_id: 'automation.notte' }
  },
  'read_file': {
    category: 'dev_tools',
    title: 'Local File Reader',
    icon: FileText,
    color: '#d29922',
    server: 'Filesystem MCP',
    summary: 'Lettura sicura di file dal workspace locale.',
    explanation: 'Legge il contenuto di file di testo, script Python o configurazioni mantenendosi entro il perimetro del progetto.',
    useCase: 'Leggere un file per analizzarne la struttura prima di modificarlo.',
    payloadSample: { path: 'README_IT.md' }
  },
  'create_file': {
    category: 'dev_tools',
    title: 'File Creator & Writer',
    icon: FileText,
    color: '#d29922',
    server: 'Filesystem MCP',
    summary: 'Scrittura o creazione di nuovi file nel workspace.',
    explanation: 'Crea nuovi file di codice, documenti o configurazioni scrivendone direttamente il contenuto.',
    useCase: 'Generare un nuovo script Python per un test automatico.',
    payloadSample: { path: 'data/test_script.py', content: '# Automatic script' }
  },
  'execute_script': {
    category: 'dev_tools',
    title: 'Python Script Runner',
    icon: Terminal,
    color: '#d29922',
    server: 'Filesystem MCP',
    summary: 'Esecuzione sicura di script Python in sottoprocesso.',
    explanation: 'Esegue script Python locali catturando stdout, stderr e codice di uscita.',
    useCase: 'Eseguire uno script di test per verificare i calcoli matematici.',
    payloadSample: { script_path: 'data/test_script.py' }
  },
  'git_status': {
    category: 'dev_tools',
    title: 'Git Repository Status',
    icon: GitBranch,
    color: '#d29922',
    server: 'Git MCP',
    summary: 'Ispezione dello stato del repository Git locale.',
    explanation: 'Verifica i file modificati, stagiati o non tracciati nel repository.',
    useCase: 'Controllare le modifiche effettuate prima di creare un commit.',
    payloadSample: {}
  },
  'web_search': {
    category: 'web_intel',
    title: 'Brave Search Engine',
    icon: Globe,
    color: '#ff7b72',
    server: 'Search MCP',
    summary: 'Ricerca web in tempo reale via Brave Search API.',
    explanation: 'Recupera informazioni aggiornate dal web, documentazione recente o notizie di settore.',
    useCase: 'Cercare l\'ultima versione di una libreria Python rilasciata di recente.',
    payloadSample: { query: 'Unsloth QLoRA fine tuning benchmark 2026' }
  },
  'scrape_url': {
    category: 'web_intel',
    title: 'Playwright Page Scraper',
    icon: Globe,
    color: '#ff7b72',
    server: 'Playwright MCP',
    summary: 'Estrazione testo e pulizia HTML da pagine web via browser headless.',
    explanation: 'Carica una pagina web ed ne estrae il contenuto testuale pulito per l\'analisi dell\'AI.',
    useCase: 'Leggere un articolo o una documentazione online.',
    payloadSample: { url: 'https://docs.python.org/3/' }
  },
  'get_hardware_status': {
    category: 'hardware',
    title: 'GPU VRAM & Telemetry',
    icon: Cpu,
    color: '#00f2fe',
    server: 'Hardware MCP',
    summary: 'Misura VRAM occupata, temperatura e carica GPU NVIDIA.',
    explanation: 'Rileva in tempo reale le risorse di calcolo utilizzate prima di avviare job intensivi.',
    useCase: 'Verificare se c\'è abbastanza VRAM libera prima di caricare un modello.',
    payloadSample: {}
  },
  'restart_ollama_daemon': {
    category: 'hardware',
    title: 'Ollama Daemon Controller',
    icon: Zap,
    color: '#00f2fe',
    server: 'Hardware MCP',
    summary: 'Riavvio del servizio Ollama per liberare la memoria VRAM.',
    explanation: 'Resetta il processo di Ollama per scaricare i modelli non più in uso dalla VRAM.',
    useCase: 'Svuota la VRAM occupata da PyTorch dopo un processo di training.',
    payloadSample: {}
  }
};

// Standby / Inactive MCP Servers Definitions (Card Grigie)
const STANDBY_SERVERS = [
  {
    id: 'mcp_github',
    name: 'MCP GitHub & Repositories',
    statusBadge: 'INTEGRAZIONE DA ATTIVARE',
    icon: GitBranch,
    color: '#a78bfa',
    summary: 'Gestione repository Git, creazione Pull Request, ricerca codice e sincronizzazione commit automatica.',
    prerequisite: 'Personal Access Token GitHub (scope repo, workflow)',
    details: 'Connette lo Swarm di Sigma Studio a GitHub per consentire all\'Agente Developer di creare issue, aprire Pull Request e revisionare codice in remoto.'
  },
  {
    id: 'mcp_docker',
    name: 'MCP Docker & Container Bus',
    statusBadge: 'SOCKET DOCKER NON RILEVATO',
    icon: Terminal,
    color: '#00d2ff',
    summary: 'Gestione dei container local/remote, ispezione dei log in tempo reale e riavvio microservizi in sandbox.',
    prerequisite: 'Daemon Docker Local / Socket //./pipe/docker_engine',
    details: 'Fornisce un bus di controllo diretto sull\'engine Docker locale per compilare immagini, orchestrare container e gestire ambienti di test isolati.'
  },
  {
    id: 'mcp_postgresql',
    name: 'MCP PostgreSQL & pgvector Engine',
    statusBadge: 'POSTGRESQL STANDBY',
    icon: Database,
    color: '#3fb950',
    summary: 'Esecuzione di query SQL avanzate e ricerca vettoriale su database relazionale PostgreSQL distribuito.',
    prerequisite: 'Connection DSN (postgresql://user:pass@localhost:5432/db)',
    details: 'Espone gli strumenti di query ed indicizzazione vettoriale per integrarsi con database aziendali PostgreSQL e vector store distribuiti.'
  },
  {
    id: 'mcp_redis',
    name: 'MCP Redis Cache & PubSub Broker',
    statusBadge: 'REDIS DISCONNESSO',
    icon: Zap,
    color: '#ff5064',
    summary: 'Caching ad altissima frequenza per KV-Cache dei token, bus di messaggistica agentico Pub/Sub e broker di stato.',
    prerequisite: 'Istanza Redis v7+ (redis://localhost:6379)',
    details: 'Abilita la persistenza ultra-veloce della cache in memoria e la condivisione istantanea degli stati dei token tra nodi GPU distribuiti.'
  },
  {
    id: 'mcp_notion',
    name: 'MCP Notion & Knowledge Workspace',
    statusBadge: 'NOTION API KEY MANCANTE',
    icon: FileText,
    color: '#ffb86c',
    summary: 'Sincronizzazione automatica di documenti, roadmap, tabelle di task e note di ricerca dal workspace Notion.',
    prerequisite: 'Integration Secret Key + Database ID',
    details: 'Permette agli agenti AI di leggere e scrivere direttamente sulle pagine e sui database del tuo workspace Notion aziendale.'
  },
  {
    id: 'mcp_slack',
    name: 'MCP Slack & Teams Agent Dispatcher',
    statusBadge: 'WEBHOOK STANDBY',
    icon: MessageSquare,
    color: '#38bdf8',
    summary: 'Invio di report di audit, notifiche di completamento benchmark ed allerte di sistema nei canali di team.',
    prerequisite: 'Incoming Webhook URL / Bot User Token',
    details: 'Configura un canale di notifica diretto verso Slack o Microsoft Teams per informare l\'utente quando lo Swarm completa task o rileva anomalie.'
  }
];

export default function McpHubTab() {
  const [servers, setServers] = useState([]);
  const [tools, setTools] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTool, setSelectedTool] = useState(null);
  const [toolArgs, setToolArgs] = useState('{}');
  const [testResult, setTestResult] = useState(null);
  const [testingTool, setTestingTool] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('catalog'); // 'catalog' | 'integrations' | 'standby' | 'tester' | 'console' | 'resources'

  // Filtering & Search state
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [disabledTools, setDisabledTools] = useState({});
  const [autoApprove, setAutoApprove] = useState(false);

  // Standby activation modal states
  const [activeStandbyModal, setActiveStandbyModal] = useState(null);
  const [activatingStandby, setActivatingStandby] = useState(null);
  const [activatedStandby, setActivatedStandby] = useState({});

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

      let backendTools = [];
      if (resTools.ok) {
        const d = await resTools.json();
        backendTools = d.tools || [];
        setAutoApprove(!!d.auto_approve);
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
    const enabled = !!disabledTools[toolName];
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
      setDisabledTools(off);
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
    try {
      for (const tool of tools) {
        if (disabledTools[tool.name]) {
          setDiagnosticLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            message: `⏸️ [${tool.server}] Tool '${tool.name}' disabilitato (Saltato).`,
            type: 'warning'
          }]);
          continue;
        }

        const meta = TOOL_METADATA[tool.name];
        const args = meta?.payloadSample || {};

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);

        try {
          const res = await fetch('/api/mcp/rpc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: controller.signal,
            body: JSON.stringify({
              jsonrpc: '2.0',
              id: `diag-${Date.now()}`,
              method: 'tools/call',
              params: { name: tool.name, arguments: args }
            })
          });
          clearTimeout(timeoutId);
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
          clearTimeout(timeoutId);
          const isTimeout = err.name === 'AbortError';
          setDiagnosticLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            message: `❌ [${tool.server}] Tool '${tool.name}' ${isTimeout ? 'timeout (4s)' : 'errore: ' + err.message}`,
            type: 'error'
          }]);
        }
      }

      setDiagnosticLogs(prev => [...prev, {
        time: new Date().toLocaleTimeString(),
        message: `🎉 Collaudo Completato: ${passedCount}/${tools.length} MCP Tools verificate e pronte per gli Agenti AI!`,
        type: 'summary'
      }]);
    } catch (globalErr) {
      setDiagnosticLogs(prev => [...prev, {
        time: new Date().toLocaleTimeString(),
        message: `❌ Errore collaudo: ${globalErr.message}`,
        type: 'error'
      }]);
    } finally {
      setRunningFullTest(false);
    }
  };

  const handleActivateStandby = (srv) => {
    setActivatingStandby(srv.id);
    setTimeout(() => {
      setActivatedStandby(prev => ({ ...prev, [srv.id]: true }));
      setActivatingStandby(null);
      setActiveStandbyModal(null);
    }, 1200);
  };

  // Filter tools by Category and Search Keyword
  const filteredTools = tools.filter(tool => {
    const meta = TOOL_METADATA[tool.name] || {};
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
    <div style={{ padding: 0, background: '#0a0c14', color: '#e2e4eb', minHeight: '100%', display: 'flex', flexDirection: 'column', position: 'relative', overflowY: 'auto' }}>

      {/* Hero Visual Banner with Generated Graphic */}
      <div style={{
        position: 'relative',
        borderRadius: 0,
        overflow: 'hidden',
        padding: '20px 32px 18px 32px',
        minHeight: '100px',
        borderBottom: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: 'linear-gradient(to right, rgba(10, 12, 20, 0.98) 45%, rgba(10, 12, 20, 0.5) 100%), url("/images/mcp_protocol_hub.jpg")',
        backgroundSize: '360px auto',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right center',
        marginBottom: '20px',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.35)',
              color: '#00d2ff', fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <Zap size={14} /> MODEL CONTEXT PROTOCOL (MCP) BUS
            </div>
            <h1 style={{ margin: '0 0 4px 0', fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>
              MCP Tools & Protocol Server Hub
            </h1>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#a0aec0', lineHeight: 1.4 }}>
              Bus di I/O decentralizzato per integrare Filesystem, Memory, Home Assistant, SQLite e Microservizi direttamente con gli Agenti AI.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={toggleAutoApprove}
              title={autoApprove ? 'Gli agenti eseguono ogni strumento attivo senza chiedere.' : 'Gli strumenti che agiscono verso l\'esterno aspettano la tua conferma.'}
              style={{
                background: autoApprove ? 'rgba(210,153,34,0.14)' : 'rgba(63,185,80,0.12)',
                border: `1px solid ${autoApprove ? 'rgba(210,153,34,0.35)' : 'rgba(63,185,80,0.3)'}`,
                color: autoApprove ? '#d29922' : '#3fb950',
                padding: '10px 16px', borderRadius: '12px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', fontWeight: 800
              }}
            >
              {autoApprove ? <ShieldAlert size={16} /> : <ShieldCheck size={16} />}
              <span>{autoApprove ? 'Esecuzione Automatica' : 'Conferma Richiesta'}</span>
            </button>

            <button
              onClick={handleTestAllTools}
              disabled={runningFullTest}
              style={{
                background: 'linear-gradient(135deg, #00d2ff, #0072ff)',
                border: 'none', color: '#fff', padding: '10px 18px', borderRadius: '12px',
                fontWeight: 800, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px',
                fontSize: '0.82rem', boxShadow: '0 4px 16px rgba(0, 210, 255, 0.25)'
              }}
            >
              {runningFullTest ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
              <span>{runningFullTest ? 'Collaudo in corso...' : '⚡ Collauda Skills MCP'}</span>
            </button>

            <button
              onClick={loadMcpData}
              style={{
                background: 'rgba(255, 255, 255, 0.08)', border: '1px solid rgba(255, 255, 255, 0.12)',
                color: '#e2e4eb', padding: '10px 16px', borderRadius: '12px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', fontWeight: 700
              }}
            >
              <RefreshCw size={15} className={loading ? 'spin' : ''} />
              <span>Aggiorna Hub</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Workspace Body Wrapper */}
      <div style={{ padding: '0 24px 24px 24px', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>

        {/* Primary Sub Tabs Bar */}
      <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px', flexWrap: 'wrap' }}>
        {[
          { id: 'catalog', label: `🛠️ Catalogo Skills (${tools.length})` },
          { id: 'integrations', label: `🔌 Server Active (${servers.length})` },
          { id: 'standby', label: '⚡ Server MCP in Standby (6)' },
          { id: 'tester', label: '🧪 Collaudo RPC & Sandbox' },
          { id: 'console', label: '📊 Log Diagnostici Hub' },
          { id: 'resources', label: `📦 Risorse (${resources.length})` },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            style={{
              background: activeSubTab === tab.id ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
              border: activeSubTab === tab.id ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
              color: activeSubTab === tab.id ? '#00d2ff' : '#8b8fa3',
              padding: '8px 18px', borderRadius: '8px', cursor: 'pointer',
              fontWeight: 700, fontSize: '0.82rem', transition: 'all 0.15s ease'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── SUB TAB 1: CATALOGO SKILLS MCP ── */}
      {activeSubTab === 'catalog' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Category Filter Pills & Search */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
              {MCP_CATEGORIES.map(cat => {
                const isSel = selectedCategory === cat.id;
                return (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    style={{
                      padding: '5px 12px', borderRadius: '16px',
                      background: isSel ? cat.bg : 'rgba(255, 255, 255, 0.04)',
                      border: `1px solid ${isSel ? cat.color : 'rgba(255, 255, 255, 0.08)'}`,
                      color: isSel ? cat.color : '#8b8fa3', fontSize: '0.75rem', fontWeight: 700,
                      cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                    }}
                  >
                    <span>{cat.icon}</span>
                    <span>{cat.name}</span>
                  </button>
                );
              })}
            </div>

            <div style={{ position: 'relative', width: '260px' }}>
              <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#6b7080' }} />
              <input
                type="text" value={searchKeyword} onChange={e => setSearchKeyword(e.target.value)}
                placeholder="Cerca skill o tool MCP..."
                style={{
                  width: '100%', padding: '8px 14px 8px 36px', borderRadius: '10px',
                  background: 'rgba(14, 17, 25, 0.8)', border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#fff', fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box'
                }}
              />
            </div>
          </div>

          {/* Tools Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
            {filteredTools.map(tool => {
              const meta = TOOL_METADATA[tool.name] || {};
              const isOff = !!disabledTools[tool.name];
              const IconComp = meta.icon || Wrench;
              const color = meta.color || '#00d2ff';

              return (
                <div
                  key={tool.name}
                  onClick={() => selectToolWithDefaults(tool)}
                  onMouseEnter={e => handleMouseEnterCard(tool, e)}
                  onMouseLeave={() => setHoveredTool(null)}
                  style={{
                    padding: '20px', borderRadius: '16px',
                    background: selectedTool?.name === tool.name ? 'rgba(18, 22, 32, 0.95)' : 'rgba(14, 17, 25, 0.8)',
                    border: `1px solid ${selectedTool?.name === tool.name ? color : (isOff ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.08)')}`,
                    opacity: isOff ? 0.6 : 1, cursor: 'pointer',
                    display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '12px',
                    transition: 'all 0.2s ease', position: 'relative'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{
                          width: '36px', height: '36px', borderRadius: '10px',
                          background: `${color}18`, border: `1px solid ${color}35`,
                          color: color, display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}>
                          <IconComp size={18} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '0.92rem', color: '#fff' }}>{meta.title || tool.name}</div>
                          <div style={{ fontSize: '0.7rem', color: '#6b7080' }}>
                            <code style={{ color: color }}>{tool.name}</code> • {tool.server}
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={e => toggleToolStatus(tool.name, e)}
                        title={isOff ? 'Skill disattivata' : 'Skill attiva'}
                        style={{
                          background: isOff ? 'rgba(255,255,255,0.05)' : `${color}20`,
                          border: `1px solid ${isOff ? 'rgba(255,255,255,0.1)' : color}`,
                          color: isOff ? '#6b7080' : color,
                          padding: '4px 10px', borderRadius: '12px', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer'
                        }}
                      >
                        {isOff ? 'OFF' : 'ATTIVA'}
                      </button>
                    </div>

                    <p style={{ margin: 0, fontSize: '0.78rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                      {meta.summary || tool.description}
                    </p>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: '0.72rem', color: '#6b7080' }}>
                    <span>Parametri: {tool.inputSchema?.properties ? Object.keys(tool.inputSchema.properties).length : 0}</span>
                    <span style={{ color: color, fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                      Seleziona & Prova <ChevronRight size={12} />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── SUB TAB 2: SERVER MCP ATTIVI & INTEGRATION GOVERNANCE ── */}
      {activeSubTab === 'integrations' && (
        <McpIntegrationsPanel servers={servers} onChanged={loadMcpData} />
      )}

      {/* ── SUB TAB 3: SERVER MCP IN STANDBY / DA ATTIVARE (Card Grigie) ── */}
      {activeSubTab === 'standby' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 12px', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.1)', color: '#8b8fa3', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
              <Layers size={13} /> ESPANSIONI PROTOCOLLO PROTOCOL MCP IN ATTESA
            </div>
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900, color: '#fff' }}>
              ⚡ Server MCP in Standby Pronte per l'Attivazione
            </h2>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: '#8b8fa3' }}>
              Integrazioni ufficiali Model Context Protocol in attesa di credenziali API o socket locale:
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
            {STANDBY_SERVERS.map(srv => {
              const IconComp = srv.icon;
              const isActivated = activatedStandby[srv.id];

              return (
                <div
                  key={srv.id}
                  style={{
                    padding: '24px', borderRadius: '18px',
                    background: isActivated ? 'rgba(14, 17, 25, 0.85)' : 'rgba(14, 17, 25, 0.4)',
                    border: '1px solid ' + (isActivated ? `${srv.color}40` : 'rgba(255, 255, 255, 0.08)'),
                    boxShadow: isActivated ? `0 8px 32px ${srv.color}15` : 'none',
                    display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                    gap: '16px', opacity: isActivated ? 1 : 0.72,
                    filter: isActivated ? 'none' : 'grayscale(35%)',
                    transition: 'all 0.3s ease'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                      <div style={{
                        width: '44px', height: '44px', borderRadius: '12px',
                        background: isActivated ? `${srv.color}25` : 'rgba(255, 255, 255, 0.04)',
                        border: '1px solid ' + (isActivated ? srv.color : 'rgba(255,255,255,0.08)'),
                        color: isActivated ? srv.color : '#8b8fa3',
                        display: 'flex', alignItems: 'center', justifyContent: 'center'
                      }}>
                        <IconComp size={22} />
                      </div>

                      <span style={{
                        fontSize: '0.68rem', fontWeight: 800,
                        color: isActivated ? '#3fb950' : '#8b8fa3',
                        background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                        border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.1)'),
                        padding: '3px 10px', borderRadius: '20px', letterSpacing: '0.5px'
                      }}>
                        {isActivated ? 'SERVER MCP ATTIVO 🔌' : srv.statusBadge}
                      </span>
                    </div>

                    <h3 style={{ margin: '0 0 6px 0', fontSize: '1rem', fontWeight: 800, color: '#fff' }}>
                      {srv.name}
                    </h3>
                    <p style={{ margin: '0 0 12px 0', fontSize: '0.78rem', color: '#8b8fa3', lineHeight: 1.5 }}>
                      {srv.summary}
                    </p>
                    <div style={{ fontSize: '0.72rem', color: '#6b7080', background: 'rgba(8, 10, 16, 0.6)', padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)' }}>
                      <strong>Requisito:</strong> {srv.prerequisite}
                    </div>
                  </div>

                  <button
                    onClick={() => setActiveStandbyModal(srv)}
                    disabled={isActivated}
                    style={{
                      padding: '10px 16px', borderRadius: '10px',
                      background: isActivated ? 'rgba(63, 185, 80, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid ' + (isActivated ? 'rgba(63, 185, 80, 0.3)' : 'rgba(255, 255, 255, 0.12)'),
                      color: isActivated ? '#3fb950' : '#e2e8f0', fontSize: '0.8rem', fontWeight: 700,
                      cursor: isActivated ? 'default' : 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    {isActivated ? <CheckCircle2 size={15} /> : <ArrowRight size={15} />}
                    {isActivated ? 'Server MCP Collegato' : srv.summary.split(' ')[0] + ' ' + srv.name}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── SUB TAB 4: COLLAUDO RPC & SANDBOX ── */}
      {activeSubTab === 'tester' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          
          {/* Selected Tool Details & Sandbox Form */}
          <div style={{ padding: '24px', borderRadius: '18px', background: 'rgba(14, 17, 25, 0.85)', border: '1px solid rgba(255,255,255,0.08)' }}>
            {selectedTool ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.3)', color: '#00d2ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Wrench size={20} />
                  </div>
                  <div>
                    <h2 style={{ margin: 0, fontSize: '1.1rem', color: '#fff', fontWeight: 800 }}>
                      Collaudo RPC: <code style={{ color: '#00d2ff' }}>{selectedTool.name}</code>
                    </h2>
                    <div style={{ fontSize: '0.74rem', color: '#8b8fa3' }}>Server: {selectedTool.server}</div>
                  </div>
                </div>

                <p style={{ fontSize: '0.82rem', color: '#a0aec0', lineHeight: 1.5, marginBottom: '20px' }}>
                  {TOOL_METADATA[selectedTool.name]?.explanation || selectedTool.description}
                </p>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '0.76rem', fontWeight: 700, color: '#c0c4d0', marginBottom: '6px' }}>
                    Parametri JSON-RPC di Esecuzione:
                  </label>
                  <textarea
                    value={toolArgs} onChange={e => setToolArgs(e.target.value)}
                    rows={8}
                    style={{
                      width: '100%', padding: '12px', borderRadius: '10px',
                      background: 'rgba(8, 10, 16, 0.9)', border: '1px solid rgba(255,255,255,0.1)',
                      color: '#00d2ff', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8rem', boxSizing: 'border-box'
                    }}
                  />
                </div>

                <button
                  onClick={handleTestTool} disabled={testingTool}
                  style={{
                    width: '100%', padding: '12px', borderRadius: '12px',
                    background: 'linear-gradient(135deg, #00d2ff, #7c5bf0)', border: 'none',
                    color: '#fff', fontWeight: 800, fontSize: '0.85rem', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px'
                  }}
                >
                  {testingTool ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}
                  {testingTool ? 'Esecuzione in corso...' : 'Invia Chiamata RPC Sonda'}
                </button>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: '#6b7080', padding: '40px' }}>Seleziona una skill dal catalogo per collaudarla.</div>
            )}
          </div>

          {/* Execution Result Terminal Display */}
          <div style={{
            padding: '24px', borderRadius: '18px',
            background: 'rgba(8, 10, 16, 0.95)', border: '1px solid rgba(0, 210, 255, 0.2)',
            backgroundImage: 'linear-gradient(to bottom, rgba(8,10,16,0.92), rgba(8,10,16,0.98)), url("/images/mcp_tool_execution.jpg")',
            backgroundSize: 'cover', backgroundPosition: 'center',
            display: 'flex', flexDirection: 'column'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#00d2ff', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Terminal size={16} /> Esito Esecuzione JSON-RPC
              </span>
              {testResult && (
                <span style={{ fontSize: '0.7rem', color: testResult.isError ? '#ff5064' : '#3fb950', fontWeight: 700 }}>
                  {testResult.isError ? '❌ Errore Esecuzione' : '✅ Risposta OK'}
                </span>
              )}
            </div>

            <div style={{ flex: 1, minHeight: '300px', overflowY: 'auto', background: 'rgba(5, 6, 10, 0.85)', borderRadius: '10px', padding: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
              {testResult ? (
                <pre style={{ margin: 0, fontSize: '0.78rem', color: testResult.isError ? '#ff5064' : '#3fb950', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(testResult, null, 2)}
                </pre>
              ) : (
                <div style={{ color: '#555', fontSize: '0.78rem', fontFamily: 'monospace' }}>
                  // Premi "Invia Chiamata RPC Sonda" per visualizzare qui l'output in tempo reale dal server MCP...
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── SUB TAB 5: LOG DIAGNOSTICI HUB ── */}
      {activeSubTab === 'console' && (
        <div style={{ padding: '24px', borderRadius: '18px', background: 'rgba(8, 10, 16, 0.95)', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>📊</span> Console Diagnostica Collaudo Skills MCP
            </h3>
            <button
              onClick={() => setDiagnosticLogs([])}
              style={{ padding: '4px 10px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', border: 'none', color: '#8b8fa3', fontSize: '0.72rem', cursor: 'pointer' }}
            >
              Pulisci Console
            </button>
          </div>

          <div style={{ minHeight: '400px', maxHeight: '600px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {diagnosticLogs.length === 0 ? (
              <div style={{ color: '#555', fontSize: '0.8rem', padding: '20px', textAlign: 'center' }}>
                Nessun log recente. Clicca su "⚡ Collauda Skills MCP" per avviare il test automatico di tutte le competenze attive.
              </div>
            ) : (
              diagnosticLogs.map((log, idx) => (
                <div key={idx} style={{
                  padding: '10px 14px', borderRadius: '8px', background: 'rgba(14, 17, 25, 0.8)',
                  borderLeft: `3px solid ${log.type === 'success' ? '#3fb950' : (log.type === 'error' ? '#ff5064' : (log.type === 'warning' ? '#d29922' : '#00d2ff'))}`,
                  fontSize: '0.78rem', fontFamily: 'JetBrains Mono, monospace'
                }}>
                  <span style={{ color: '#555', marginRight: '10px' }}>{log.time}</span>
                  <span style={{ color: log.type === 'error' ? '#ff5064' : (log.type === 'success' ? '#3fb950' : '#e2e4eb') }}>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── SUB TAB 6: RISORSE MCP ── */}
      {activeSubTab === 'resources' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
          {resources.map((res, idx) => (
            <div key={idx} style={{ padding: '20px', borderRadius: '16px', background: 'rgba(14, 17, 25, 0.8)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontWeight: 800, fontSize: '0.9rem', color: '#00d2ff', marginBottom: '4px' }}>{res.name}</div>
              <div style={{ fontSize: '0.74rem', color: '#8b8fa3', marginBottom: '8px' }}><code>{res.uri}</code></div>
              <p style={{ fontSize: '0.78rem', color: '#c0c4d0', margin: 0 }}>{res.description || 'Risorsa di contesto esposta dal protocollo MCP.'}</p>
            </div>
          ))}
        </div>
      )}

      {/* Standby Server Activation Modal */}
      {activeStandbyModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10000,
          background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'
        }}>
          <div style={{
            width: '100%', maxWidth: '520px', background: 'rgba(18, 20, 28, 0.95)',
            border: `1px solid ${activeStandbyModal.color}40`, borderRadius: '20px',
            padding: '28px', boxShadow: '0 20px 60px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', color: activeStandbyModal.color }}>
              <activeStandbyModal.icon size={26} />
              <div>
                <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', fontWeight: 800 }}>
                  {activeStandbyModal.name}
                </h2>
                <div style={{ fontSize: '0.74rem', color: '#8b8fa3', marginTop: '2px' }}>
                  {activeStandbyModal.statusBadge}
                </div>
              </div>
            </div>

            <p style={{ fontSize: '0.84rem', color: '#c0c4d0', lineHeight: 1.6, marginBottom: '20px' }}>
              {activeStandbyModal.details}
            </p>

            <div style={{ padding: '12px 16px', borderRadius: '12px', background: 'rgba(8, 10, 16, 0.8)', border: '1px solid rgba(255,255,255,0.08)', marginBottom: '24px', fontSize: '0.78rem', color: '#8b8fa3' }}>
              <div style={{ fontWeight: 700, color: '#fff', marginBottom: '4px' }}>📋 Requisito di Collegamento:</div>
              {activeStandbyModal.prerequisite}
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setActiveStandbyModal(null)}
                style={{ padding: '10px 18px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#c0c4d0', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}
              >
                Annulla
              </button>
              <button
                onClick={() => handleActivateStandby(activeStandbyModal)}
                disabled={activatingStandby === activeStandbyModal.id}
                style={{
                  padding: '10px 22px', borderRadius: '10px',
                  background: `linear-gradient(135deg, ${activeStandbyModal.color}, #00d2ff)`, border: 'none',
                  color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 800,
                  display: 'flex', alignItems: 'center', gap: '8px'
                }}
              >
                {activatingStandby === activeStandbyModal.id ? <RefreshCw className="spin" size={15} /> : <Zap size={15} />}
                {activatingStandby === activeStandbyModal.id ? 'Attivazione...' : 'Connetti & Attiva Server MCP 🔌'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Hover popover tooltip */}
      {hoveredTool && (
        <div style={{
          position: 'fixed',
          top: tooltipPos.y,
          left: tooltipPos.x,
          transform: 'translate(-50%, -100%)',
          zIndex: 9999,
          background: 'rgba(10, 12, 18, 0.95)',
          border: '1px solid rgba(0, 210, 255, 0.35)',
          boxShadow: '0 10px 30px rgba(0,0,0,0.6)',
          borderRadius: '12px',
          padding: '12px 16px',
          maxWidth: '340px',
          pointerEvents: 'none',
          backdropFilter: 'blur(10px)',
          animation: 'fadeIn 0.15s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.88rem', fontWeight: 800, color: '#fff' }}>
              {TOOL_METADATA[hoveredTool.name]?.title || hoveredTool.name}
            </span>
          </div>
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#c0c4d0', lineHeight: 1.4 }}>
            {TOOL_METADATA[hoveredTool.name]?.explanation || hoveredTool.description}
          </p>
        </div>
      )}

      </div>
    </div>
  );
}
