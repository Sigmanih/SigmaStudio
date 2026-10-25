import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  Send, Bot, User, Sparkles, Brain, Check, Copy, RefreshCw,
  Terminal, FileCode, Trash2, ArrowRight, ShieldCheck, Zap,
  ChevronDown, ChevronUp, SplitSquareVertical, Layers, Folder,
  Plus, Edit2, Clock, Search, X, MessageSquare,
  Paperclip, Mic, MicOff, FileText, Upload,
  ListTodo, CheckCircle2, Circle, CircleDot, RotateCw, Award, Play, Pause, Square,
  Settings, Activity, AlertTriangle, AlertCircle, Cpu
} from 'lucide-react';
import DeveloperModelSelector from './DeveloperModelSelector';
import AgentWorkMonitor from './AgentWorkMonitor';
import ReviewProposal from './ReviewProposal';
import DockerViewerModal from './DockerViewerModal';
import ActivityBar from './ActivityBar';
import { renderMarkdownLatex } from '../../utils/markdownLatex';
import { normalizzaTestoAgente } from '../../utils/testoAgente';
import GoalCompletionCard from '../../components/Chat/ui/GoalCompletionCard';
import 'katex/dist/katex.min.css';
import Prism from 'prismjs';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-powershell';
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-yaml';
import 'prismjs/themes/prism-tomorrow.css';
import mermaid from 'mermaid';

try {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
    flowchart: { useMaxWidth: true, htmlLabels: true }
  });
} catch (e) { }

const STORAGE_TASKS_KEY = 'sigma_dev_tasks_v2';
const STORAGE_ACTIVE_TASK_KEY = 'sigma_dev_active_task_id_v2';

const isAutoLoopPrompt = (msg) => {
  if (!msg) return false;
  if (msg.isAutomatic || msg.isSystemPrompt || msg.author === 'system') return true;
  const content = typeof msg.content === 'string' ? msg.content.trim() : '';
  return (
    content.startsWith('Procedi con il task pianificato') ||
    content.startsWith('Tutti i task pianificati nella pipeline risultano completati') ||
    content.startsWith('Continua l\'implementazione: definisci o aggiorna la pipeline') ||
    content.startsWith('Procedi con il prossimo task pianificato') ||
    content.startsWith('Task riavviato su richiesta utente') ||
    content === 'Continua.'
  );
};

const getInitialModel = () => {
  try {
    const savedFavs = localStorage.getItem('sigma_favorite_models') || localStorage.getItem('sigma_developer_favorite_models');
    if (savedFavs) {
      const parsed = JSON.parse(savedFavs);
      if (Array.isArray(parsed) && parsed.length > 0 && parsed[0]) {
        return parsed[0];
      }
    }
    const lastSelected = localStorage.getItem('sigma_developer_last_model');
    if (lastSelected && lastSelected !== 'sigmaengine') return lastSelected;
  } catch (e) {}
  return '';
};

const createNewTask = (title = 'Nuovo Task') => ({
  id: `task_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
  title,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  model: getInitialModel(),
  autoExecuteTools: true,
  autoLoop: true,
  // Spenta di default: il comportamento storico resta quello, e un run
  // lasciato solo si fermerebbe alla prima scrittura senza nessuno che
  // guarda. Si accende quando si lavora su codice che conta.
  reviewWrites: false,
  // L'agente lavora in una copia fisica del repository. Spento di
  // default: serve un repo git, e per una modifica di due righe il costo
  // della copia non vale la rete di sicurezza.
  isolateWorktree: false,
  // La revisione di tutto il lavoro in una volta, alla fine. E' la forma
  // che regge quando il run tocca molti file; richiede l'isolamento.
  reviewRun: false,
  // Il tetto ai tool, scelto dall'utente: vuoto significa nessun limite
  // oltre a quelli del ruolo. E' un tetto, non una scelta alternativa —
  // in sola lettura nessun ruolo puo' scrivere, per quanti tool dichiari.
  profile: '',
  isGoalCompleted: false,
  pipeline: [],
  messages: [
    {
      role: 'assistant',
      content: '👋 Ciao! Sono il tuo **Admin AI Developer Agent** di Sigma Studio.\n\nHo permessi completi di amministrazione sul workspace: posso esplorare, modificare, creare ed eliminare file, ed eseguire comandi PowerShell/Bash direttamente nel terminale.\n\nCome posso aiutarti nello sviluppo?',
      tools: [],
      timestamp: new Date().toISOString()
    }
  ]
});

const formatMessageTimestamp = (isoString) => {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch (e) {
    return '';
  }
};

const formatTimeAgo = (isoString) => {
  if (!isoString) return '';
  try {
    const diffMs = Date.now() - new Date(isoString).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Adesso';
    if (diffMins < 60) return `${diffMins} min fa`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h fa`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}g fa`;
  } catch (e) {
    return '';
  }
};

// Il testo dell agente arriva a volte dentro un corpo JSON (il riepilogo di
// `complete_goal` e' il caso piu' frequente): `normalizzaTestoAgente` lo
// riporta alla luce prima del markdown, e si prova da solo con
// `node src/utils/testoAgente.prova.mjs`.

const cleanMessageText = (text) => {
  if (!text) return '';
  let cleaned = text;
  // Remove completed or in-progress tool code blocks
  cleaned = cleaned.replace(/```tool(?::\w+)?[\s\S]*?(?:```|$)/gi, '');
  cleaned = cleaned.replace(/```(?:json|bash|sh|powershell)?\s*\{[\s\S]*?"(?:tool|action|command|path|name|tasks)"[\s\S]*?(?:```|$)/gi, '');
  // Remove completed or in-progress XML tool tags
  cleaned = cleaned.replace(/<(?:tool_call|execute_command|shell|terminal|read_file|write_file|write_to_file|list_dir|search_code|tool|pipeline|complete_goal|finish_task|task_complete)>[\s\S]*?(?:<\/(?:tool_call|execute_command|shell|terminal|read_file|write_file|write_to_file|list_dir|search_code|tool|pipeline|complete_goal|finish_task|task_complete)>|$)/gi, '');

  // Deduplicazione di ripetizioni identiche in coda precedute da 🏆
  const trophyMatch = cleaned.match(/(?:\n|^)🏆\s*(?:##\s*Obiettivo\s+completato[\s\S]*)/i);
  if (trophyMatch && trophyMatch.index > 0) {
    const beforeTrophy = cleaned.substring(0, trophyMatch.index).trim();
    if (beforeTrophy.toLowerCase().includes('obiettivo completato')) {
      cleaned = beforeTrophy;
    }
  }

  // Se la pulizia ha svuotato completamente il testo ma c'erano token nel messaggio originale,
  // conserviamo il testo solo se non era esclusivamente un blocco tool/chiamata XML o JSON grezzo
  if (!cleaned.trim() && text.trim()) {
    const isPureToolBlock = /^\s*(?:<[^>]+>|```(?:json|tool|bash|sh|powershell)?\s*\{[\s\S]*\}?\s*```?|\{[\s\S]*"(?:tool|action|command)"[\s\S]*\})\s*$/i.test(text.trim());
    if (isPureToolBlock) {
      return '';
    }
    return text.trim();
  }

  return cleaned.trim();
};

if (typeof window !== 'undefined') {
  window.Prism = Prism;
}

function RichMessageContent({ content, isUser, onOpenFile, isLight, noBorder }) {
  const containerRef = useRef(null);

  const html = useMemo(() => {
    if (!content) return '';
    // Prima si riporta alla luce il testo sepolto in un corpo JSON, poi si
    // rende il markdown: l'ordine conta, perche' dentro una stringa JSON un
    // `##` non e' un titolo e un `\n` non e' un a capo.
    return renderMarkdownLatex(normalizzaTestoAgente(content));
  }, [content]);

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;

    // Render Mermaid diagrams safely without DOM thrashing on code blocks
    const mermaidBlocks = el.querySelectorAll('.language-mermaid');
    if (mermaidBlocks.length > 0) {
      mermaidBlocks.forEach(async (block, i) => {
        const raw = block.textContent;
        const pre = block.closest('.chat-code-block-wrapper') || block.closest('pre') || block;
        if (!pre || pre.dataset.mermaidDone) return;
        pre.dataset.mermaidDone = 'true';

        const wrapper = document.createElement('div');
        wrapper.className = 'mermaid-wrapper';
        wrapper.style.cssText = 'width:100%;margin:8px 0;overflow-x:auto;background:#0d1117;border:1px solid rgba(0,210,255,0.25);border-radius:6px;padding:8px;display:flex;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.3);';

        try {
          const id = `mermaid-admin-${Date.now()}-${i}`;
          const { svg } = await mermaid.render(id, raw);
          wrapper.innerHTML = svg;
          pre.parentNode?.replaceChild(wrapper, pre);
        } catch (err) {
          wrapper.innerHTML = `<div style="color:#ef4444;font-size:0.68rem;padding:6px;">Mermaid Error: ${err.message}</div>`;
          pre.parentNode?.replaceChild(wrapper, pre);
        }
      });
    }
  }, [html]);

  const handleClick = (e) => {
    // 1. Copy code button click via event delegation (zero DOM layout shifts)
    const copyBtn = e.target.closest('.chat-copy-code-btn');
    if (copyBtn) {
      e.preventDefault();
      e.stopPropagation();
      const wrapper = copyBtn.closest('.chat-code-block-wrapper') || copyBtn.closest('pre');
      const codeEl = wrapper?.querySelector('code');
      const textToCopy = codeEl?.textContent || '';
      if (textToCopy) {
        navigator.clipboard.writeText(textToCopy);
        const origHtml = copyBtn.innerHTML;
        copyBtn.innerHTML = '✓ Copiato!';
        copyBtn.classList.add('copied');
        setTimeout(() => {
          copyBtn.innerHTML = origHtml;
          copyBtn.classList.remove('copied');
        }, 2000);
      }
      return;
    }

    // 2. File link click
    const fileLink = e.target.closest('.chat-file-link');
    if (fileLink && onOpenFile) {
      e.preventDefault();
      const path = fileLink.dataset.path || fileLink.getAttribute('data-path') || fileLink.textContent.replace(/^📄\s*/, '').trim();
      if (path) onOpenFile(path);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`chat-content chat-md dev-chat-md ${isLight ? 'light-mode' : ''}`}
      onClick={handleClick}
      style={{
        padding: noBorder ? '4px 6px' : '6px 10px',
        borderRadius: noBorder ? '0' : '6px',
        fontSize: '0.74rem',
        lineHeight: 1.5,
        background: noBorder
          ? 'transparent'
          : (isUser
            ? (isLight ? 'rgba(0, 242, 254, 0.1)' : 'rgba(0, 242, 254, 0.08)')
            : (isLight ? '#ffffff' : '#161b22')),
        border: noBorder ? 'none' : (isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)'),
        color: isLight ? '#24292f' : '#e6edf3',
        wordBreak: 'break-word',
        boxShadow: !noBorder && isLight ? '0 1px 2px rgba(0,0,0,0.04)' : 'none'
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** La bolla dell'assistente puo' portare gia' la scheda dell'obiettivo: in quel
 *  caso la card del tool non ripete il riepilogo. */
function eBollaObiettivo(testo) {
  const t = String(testo || '').trim();
  if (!t) return false;
  return /^(?:🏆\s*)?##\s*Obiettivo\s+completato/i.test(t)
    || /^\s*Obiettivo\s+completato\s*[:—–\-]/i.test(t);
}

const sanitizeTasksForLocalStorage = (tasksList) => {
  return (tasksList || []).slice(0, 15).map(t => ({
    id: t.id,
    title: t.title,
    createdAt: t.createdAt,
    updatedAt: t.updatedAt,
    model: t.model,
    autoExecuteTools: t.autoExecuteTools,
    autoLoop: t.autoLoop ?? true,
    reviewWrites: t.reviewWrites ?? false,
    isolateWorktree: t.isolateWorktree ?? false,
    reviewRun: t.reviewRun ?? false,
    profile: t.profile ?? '',
    isGoalCompleted: t.isGoalCompleted ?? false,
    pipeline: (t.pipeline || []).slice(0, 30),
    messages: (t.messages || []).slice(-30).map(m => ({
      role: m.role,
      content: typeof m.content === 'string' ? m.content.slice(0, 50000) : m.content,
      thought: typeof m.thought === 'string' ? m.thought.slice(0, 10000) : m.thought,
      metrics: m.metrics,
      timestamp: m.timestamp,
      tools: (m.tools || []).map(tool => ({
        tool: tool.tool,
        status: tool.status,
        params: tool.params,
        result: tool.result ? {
          success: tool.result.success,
          message: tool.result.message,
          // La scheda di chiusura deve rileggere riepilogo e criteri dopo un reload.
          summary: typeof tool.result.summary === 'string' ? tool.result.summary.slice(0, 20000) : undefined,
          criteria: Array.isArray(tool.result.criteria) ? tool.result.criteria.slice(0, 40) : undefined,
          is_completed: tool.result.is_completed,
          diff: typeof tool.result.diff === 'string' ? tool.result.diff.slice(0, 10000) : undefined,
          path: tool.result.path,
          tasks: tool.result.tasks
        } : undefined
      }))
    }))
  }));
};

export default function AdminAgentChat({
  workspaceRoot,
  activeFilePath,
  activeFileContent,
  onApplyDiff,
  onOpenFile,
  onExecuteTerminalCommand,
  onRefreshTree,
  theme,
  isLight,
  headerPortalNode
}) {
  const [showDockerModal, setShowDockerModal] = useState(false);

  // 1. Persistent Tasks State
  const [tasks, setTasks] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_TASKS_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {
      console.debug('Error loading dev tasks from localStorage:', e);
    }
    return [createNewTask()];
  });

  const [activeTaskId, setActiveTaskId] = useState(() => {
    try {
      const savedActive = localStorage.getItem(STORAGE_ACTIVE_TASK_KEY);
      if (savedActive) return savedActive;
    } catch (e) { }
    return tasks[0]?.id || '';
  });

  // Load server-persisted tasks on initial mount
  useEffect(() => {
    fetch('/api/developer/tasks')
      .then(res => res.json())
      .then(data => {
        if (data.success && Array.isArray(data.tasks) && data.tasks.length > 0) {
          setTasks(data.tasks);
        }
      })
      .catch(err => console.debug('Could not load server tasks:', err));
  }, []);

  // Task selector UI state
  const [showTaskMenu, setShowTaskMenu] = useState(false);
  const [taskSearchQuery, setTaskSearchQuery] = useState('');
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editTitleInput, setEditTitleInput] = useState('');

  // Input, Auto-Scroll & Streaming State
  const [input, setInput] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [agentStatus, setAgentStatus] = useState('');
  const [expandedThoughts, setExpandedThoughts] = useState({});
  const [expandedTools, setExpandedTools] = useState({});

  // File attachments & Speech recognition state
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  const messagesContainerRef = useRef(null);
  const rafScrollRef = useRef(null);
  const isUserScrolledUpRef = useRef(false);
  const chatEndRef = useRef(null);
  const taskMenuRef = useRef(null);

  // Active Task Resolution
  const activeTask = tasks.find(t => t.id === activeTaskId) || tasks[0] || createNewTask();
  const messages = activeTask.messages || [];
  const selectedModel = activeTask.model || getInitialModel() || '';
  const autoExecuteTools = activeTask.autoExecuteTools ?? true;
  const autoLoop = activeTask.autoLoop ?? true;
  const reviewWrites = activeTask.reviewWrites ?? false;
  const isolateWorktree = activeTask.isolateWorktree ?? false;
  const reviewRun = activeTask.reviewRun ?? false;
  const profile = activeTask.profile ?? '';
  const isGoalCompleted = activeTask.isGoalCompleted ?? false;
  const pipeline = activeTask.pipeline || [];

  // Paginazione e Virtual Windowing dei messaggi per prestazioni ottimali del DOM
  const [visibleCount, setVisibleCount] = useState(40);
  useEffect(() => {
    setVisibleCount(40);
  }, [activeTaskId]);

  // Precalcolo lineare O(N) di relatedTaskTitle e slicing degli ultimi messaggi visibili
  const visibleMessages = useMemo(() => {
    let currentTaskTitle = '';
    const enriched = (messages || []).map((msg, idx) => {
      if (msg.role === 'user') {
        const match = msg.content?.match(/Procedi con il task pianificato(?:\s*#\d+)?:\s*"([^"]+)"/);
        if (match) {
          currentTaskTitle = match[1];
        }
      }
      const resolvedTitle = msg.taskTitle || (msg.role === 'assistant' ? currentTaskTitle : null);
      return { ...msg, resolvedTaskTitle: resolvedTitle, originalIndex: idx };
    });
    return enriched.slice(-visibleCount);
  }, [messages, visibleCount]);

  // Pipeline UI & Auto-Loop
  const [showPipeline, setShowPipeline] = useState(true);
  const [newPipelineInput, setNewPipelineInput] = useState('');
  const [newPipelineDesc, setNewPipelineDesc] = useState('');
  const [showNewTaskInline, setShowNewTaskInline] = useState(false);
  // Mini-tab attiva nella barra informativa: monitor, piano, attività
  const [activeInfoTab, setActiveInfoTab] = useState('piano');
  const [loopCountdown, setLoopCountdown] = useState(null);
  const autoLoopTimeoutRef = useRef(null);
  const abortControllerRef = useRef(null);
  // Il loop riparte solo dopo che l'utente ha mandato almeno un messaggio
  // nella sessione corrente: senza questo, riaprire la tab faceva ripartire
  // i task da soli.
  const userHasInteractedRef = useRef(false);

  // Context Length (RAM/VRAM Window) State
  const [contextTokens, setContextTokens] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_dev_context_tokens');
      return saved ? parseInt(saved, 10) : 32768;
    } catch {
      return 32768;
    }
  });
  const [contextMetrics, setContextMetrics] = useState(null);
  // Tetto dei turni di un run: lo stesso numero che il ciclo usa per decidere
  // quando proporre di spezzare la voce (meta dei turni senza scritture). Prima
  // di oggi il frontend non lo mandava e il server ripiegava su 30: chi
  // guardava non poteva sapere quanto tempo restava. Si cambia da console con
  // localStorage.setItem('sigma_dev_max_turns', '60').
  const maxTurns = (() => {
    try {
      const salvato = parseInt(localStorage.getItem('sigma_dev_max_turns'), 10);
      return Number.isFinite(salvato) && salvato > 0 ? salvato : 30;
    } catch {
      return 30;
    }
  })();
  const [sandboxConfig, setSandboxConfig] = useState({
    mode: 'host',
    image: 'python:3.12-slim',
    network: true,
    docker_available: false,
    docker_detail: '',
    active: false
  });
  const [sandboxLoading, setSandboxLoading] = useState(false);

  const fetchSandboxState = useCallback(async () => {
    try {
      const res = await fetch('/api/developer/sandbox');
      const data = await res.json();
      if (data && data.success) {
        setSandboxConfig(data);
      }
    } catch (err) {
      console.error('Errore recupero sandbox:', err);
    }
  }, []);

  useEffect(() => {
    fetchSandboxState();
  }, [fetchSandboxState]);
  // Mirror of the backend session ledger: exactly what the model sees as
  // its own working state, so the user and the agent never disagree about
  // what has already been done.
  const [ledgerState, setLedgerState] = useState(null);
  const [gateReason, setGateReason] = useState(null);
  // La modifica su cui il run e' fermo adesso. Finche' e' qui, l'agente
  // sta aspettando: non e' un avviso, e' un'attesa vera.
  const [pendingReview, setPendingReview] = useState(null);
  const [decidingReview, setDecidingReview] = useState(false);
  // Il branch su cui e' rimasto il lavoro di un run isolato che non ha
  // chiuso l'obiettivo. Un branch di cui nessuno sa il nome e' perso
  // quanto uno cancellato.
  const [preservedBranch, setPreservedBranch] = useState(null);
  // Il lavoro consegnato su dev, con dove andarlo ad accettare.
  const [deliveredWork, setDeliveredWork] = useState(null);
  const [truncationCount, setTruncationCount] = useState(0);
  // Il diario: cosa è stato fatto, una riga per fatto, mentre succede. Il
  // pannello tecnico mostra gli eventi grezzi; questo è il racconto.
  const [diario, setDiario] = useState([]);
  // Il consuntivo di fine run, costruito dal ledger e non dal modello.
  const [runReport, setRunReport] = useState(null);
  // Lo stato di lavoro ritrovato sul server all'inizio del run: dirlo evita
  // che l'utente si chieda perche' l'agente non stia rileggendo nulla.
  const [resumedFrom, setResumedFrom] = useState(null);
  // Consuntivo dell'ultimo run. Senza misure, ogni intervento sull'agente
  // resta un'impressione.
  const [runMetrics, setRunMetrics] = useState(null);

  const handleSelectContextTokens = (tokens) => {
    setContextTokens(tokens);
    try {
      localStorage.setItem('sigma_dev_context_tokens', String(tokens));
    } catch { }
  };

  // Keep a ref to always have the latest tasks state in async callbacks
  const latestTasksRef = useRef(tasks);
  useEffect(() => {
    latestTasksRef.current = tasks;
  }, [tasks]);

  const toggleAutoLoop = () => {
    const nextVal = !autoLoop;
    if (!nextVal && autoLoopTimeoutRef.current) {
      clearInterval(autoLoopTimeoutRef.current);
      autoLoopTimeoutRef.current = null;
      setLoopCountdown(null);
    }
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, autoLoop: nextVal } : t));
  };

  const stopAutoLoop = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    // 1. Arresta immediatamente il timer e il countdown
    if (autoLoopTimeoutRef.current) {
      clearInterval(autoLoopTimeoutRef.current);
      autoLoopTimeoutRef.current = null;
      setLoopCountdown(null);
    }
    // 2. Disattiva definitivamente il flag autoLoop sul task attivo
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, autoLoop: false } : t));

    // 3. Se c'è una generazione o chiamata in streaming attiva, abortiscila subito
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort();
      } catch (err) { }
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setAgentStatus('');
  };

  const handleStopGeneration = (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    // 1. Abort active network SSE stream
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort();
      } catch (err) { }
      abortControllerRef.current = null;
    }
    // 2. Stop Auto-Loop timer and permanently disable autoLoop
    if (autoLoopTimeoutRef.current) {
      clearInterval(autoLoopTimeoutRef.current);
      autoLoopTimeoutRef.current = null;
      setLoopCountdown(null);
    }

    // 3. Mark current streaming message as finished and autoLoop = false
    setIsStreaming(false);
    setAgentStatus('');
    setTasks(prev => prev.map(t => {
      if (t.id === activeTask.id) {
        const msgs = (t.messages || []).map(m => m.isStreaming ? { ...m, isStreaming: false } : m);
        return { ...t, autoLoop: false, messages: msgs, updatedAt: new Date().toISOString() };
      }
      return t;
    }));
  };

  const toggleTaskStatus = (taskId) => {
    setTasks(prev => prev.map(t => {
      if (t.id === activeTask.id) {
        const updated = (t.pipeline || []).map(item => {
          if (item.id === taskId) {
            const nextStatus = item.status === 'done' ? 'pending' : (item.status === 'pending' ? 'in_progress' : 'done');
            return { ...item, status: nextStatus };
          }
          return item;
        });
        return { ...t, pipeline: updated, updatedAt: new Date().toISOString() };
      }
      return t;
    }));
  };

  const removePipelineTask = (taskId) => {
    setTasks(prev => prev.map(t => {
      if (t.id === activeTask.id) {
        return { ...t, pipeline: (t.pipeline || []).filter(item => item.id !== taskId), updatedAt: new Date().toISOString() };
      }
      return t;
    }));
  };

  const handleAddPipelineTask = (e) => {
    if (e) e.preventDefault();
    if (!newPipelineInput.trim()) return;
    const newTaskObj = {
      id: `task_${Date.now()}_${Math.random().toString(36).substring(2, 5)}`,
      title: newPipelineInput.trim(),
      description: newPipelineDesc.trim() || undefined,
      status: 'pending'
    };
    setTasks(prev => prev.map(t => {
      if (t.id === activeTask.id) {
        return { ...t, pipeline: [...(t.pipeline || []), newTaskObj], updatedAt: new Date().toISOString() };
      }
      return t;
    }));
    setNewPipelineInput('');
    setNewPipelineDesc('');
    setShowNewTaskInline(false);
  };

  // 1. Sync full tasks to server file data/developer_tasks.json
  useEffect(() => {
    const timer = setTimeout(() => {
      fetch('/api/developer/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tasks })
      }).catch(err => console.debug('Server tasks sync error:', err));
    }, 500);
    return () => clearTimeout(timer);
  }, [tasks]);

  // 2. Persist sanitized lightweight tasks to localStorage
  useEffect(() => {
    try {
      const sanitized = sanitizeTasksForLocalStorage(tasks);
      localStorage.setItem(STORAGE_TASKS_KEY, JSON.stringify(sanitized));
      localStorage.setItem(STORAGE_ACTIVE_TASK_KEY, activeTask.id);
    } catch (e) {
      try {
        const minimal = sanitizeTasksForLocalStorage([activeTask]);
        localStorage.setItem(STORAGE_TASKS_KEY, JSON.stringify(minimal));
        localStorage.setItem(STORAGE_ACTIVE_TASK_KEY, activeTask.id);
      } catch (innerErr) {
        console.debug('LocalStorage quota reached; server persistence active.');
      }
    }
  }, [tasks, activeTask.id]);

  // Close task dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (taskMenuRef.current && !taskMenuRef.current.contains(e.target)) {
        setShowTaskMenu(false);
        setEditingTaskId(null);
      }
    };
    if (showTaskMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showTaskMenu]);

  const scrollToBottom = () => {
    if (!autoScroll || isUserScrolledUpRef.current || !messagesContainerRef.current) return;
    const container = messagesContainerRef.current;

    if (rafScrollRef.current) {
      cancelAnimationFrame(rafScrollRef.current);
    }

    rafScrollRef.current = requestAnimationFrame(() => {
      if (!container) return;
      container.scrollTop = container.scrollHeight;
    });
  };

  const handleWheel = (e) => {
    if (e.deltaY < 0) {
      isUserScrolledUpRef.current = true;
    } else if (e.deltaY > 0 && messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
      if (scrollHeight - scrollTop - clientHeight < 50) {
        isUserScrolledUpRef.current = false;
      }
    }
  };

  const handleScrollMessages = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight - scrollTop - clientHeight < 30) {
      isUserScrolledUpRef.current = false;
    }
  };

  // Una proposta di revisione lasciata in sospeso da un refresh.
  //
  // Il run vive sul server, non nella pagina: se si ricarica mentre l'agente
  // aspetta un giudizio, lo stream SSE muore ma il thread resta fermo sulla
  // sua proposta fino al timeout, e non c'e' piu' nessun evento che la
  // annunci. Chiederlo all'apertura del task e' l'unico modo per ritrovarla —
  // e per sbloccare chi sta aspettando.
  useEffect(() => {
    let annullato = false;
    if (!activeTaskId) return undefined;

    (async () => {
      try {
        const res = await fetch(
          `/api/developer/review/pending?session_id=${encodeURIComponent(activeTaskId)}`
        );
        if (!res.ok) return;
        const data = await res.json();
        const prima = (data.pending || [])[0];
        if (!annullato && prima) {
          setPendingReview({
            id: prima.id,
            path: prima.path,
            diff: prima.diff,
            tool: prima.tool
          });
        }
      } catch (e) {
        // Server spento o rotta assente: non c'e' niente da recuperare.
      }
    })();

    return () => { annullato = true; };
  }, [activeTaskId]);

  // Fluid Auto-scroll without animation conflicts
  useEffect(() => {
    if (autoScroll && !isUserScrolledUpRef.current) {
      scrollToBottom();
    }
  }, [messages, isStreaming, autoScroll]);

  // Task Management Handlers
  const handleCreateNewTask = () => {
    isUserScrolledUpRef.current = false;
    const newTask = createNewTask(`Task #${tasks.length + 1}`);
    setTasks(prev => [newTask, ...prev]);
    setActiveTaskId(newTask.id);
    setShowTaskMenu(false);
  };

  const handleSelectTask = (taskId) => {
    isUserScrolledUpRef.current = false;
    setActiveTaskId(taskId);
    setShowTaskMenu(false);
  };

  const handleDeleteTask = (taskId, e) => {
    e?.stopPropagation();
    if (tasks.length <= 1) {
      // If deleting the last task, replace with a fresh one
      const freshTask = createNewTask('Task #1');
      setTasks([freshTask]);
      setActiveTaskId(freshTask.id);
      return;
    }
    const remaining = tasks.filter(t => t.id !== taskId);
    setTasks(remaining);
    if (activeTaskId === taskId) {
      setActiveTaskId(remaining[0].id);
    }
  };

  const handleStartRename = (task, e) => {
    e?.stopPropagation();
    setEditingTaskId(task.id);
    setEditTitleInput(task.title);
  };

  const handleSaveRename = (taskId, e) => {
    e?.stopPropagation();
    if (!editTitleInput.trim()) {
      setEditingTaskId(null);
      return;
    }
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, title: editTitleInput.trim(), updatedAt: new Date().toISOString() } : t));
    setEditingTaskId(null);
  };

  const handleModelChange = (newModel) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, model: newModel, updatedAt: new Date().toISOString() } : t));
    try {
      if (newModel && newModel !== 'sigmaengine') {
        localStorage.setItem('sigma_developer_last_model', newModel);
      }
    } catch (e) {}
  };

  const handleToggleAutoExecute = (val) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, autoExecuteTools: val, updatedAt: new Date().toISOString() } : t));
  };

  const handleToggleReviewWrites = (val) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, reviewWrites: val, updatedAt: new Date().toISOString() } : t));
  };

  const handleToggleIsolateWorktree = (val) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id ? { ...t, isolateWorktree: val, updatedAt: new Date().toISOString() } : t));
  };

  // La revisione del run non ha senso senza isolamento: senza worktree le
  // modifiche sono già nell'albero vivo e «scarta» non avrebbe niente da
  // scartare. Accendendola si accende anche quello, invece di lasciare una
  // scelta che il server poi ignora.
  const handleSelectProfile = (val) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id
      ? { ...t, profile: val, updatedAt: new Date().toISOString() } : t));
  };

  const handleToggleReviewRun = (val) => {
    setTasks(prev => prev.map(t => t.id === activeTask.id
      ? { ...t, reviewRun: val, isolateWorktree: val ? true : t.isolateWorktree, updatedAt: new Date().toISOString() }
      : t));
  };

  // La decisione viaggia su una richiesta separata: lo stream SSE sta ancora
  // scaricando il run, ed e' proprio il thread che questa risposta sblocca.
  const handleReviewDecide = async (proposalId, decision) => {
    setDecidingReview(true);
    try {
      const res = await fetch('/api/developer/review/decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: activeTask.id,
          id: proposalId,
          decision
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!data.applied) {
        // Scaduta mentre la si leggeva: dirlo evita di credere di aver
        // approvato una modifica che era gia' stata annullata.
        setAgentStatus('La proposta non era piu in attesa: potrebbe essere scaduta.');
      }
    } catch (e) {
      setAgentStatus(`Errore nell'invio della decisione: ${e.message}`);
    } finally {
      setPendingReview(null);
      setDecidingReview(false);
    }
  };

  const handleToggleSandbox = async (targetMode) => {
    setSandboxLoading(true);
    try {
      const res = await fetch('/api/developer/sandbox', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: targetMode })
      });
      const data = await res.json();
      if (data && data.success) {
        setSandboxConfig(data);
      }
    } catch (err) {
      console.error('Errore toggle sandbox:', err);
    } finally {
      setSandboxLoading(false);
    }
  };

  const toggleThought = (idx) => {
    setExpandedThoughts(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const toggleTool = (toolKey) => {
    setExpandedTools(prev => ({
      ...prev,
      [toolKey]: prev[toolKey] === undefined ? false : !prev[toolKey]
    }));
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    files.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        setAttachedFiles(prev => [
          ...prev,
          {
            id: `att_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
            name: file.name,
            size: file.size,
            type: file.type,
            content: typeof ev.target.result === 'string' ? ev.target.result : ''
          }
        ]);
      };
      reader.readAsText(file);
    });

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachedFile = (fileId) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleDropFiles = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;

    files.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        setAttachedFiles(prev => [
          ...prev,
          {
            id: `att_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
            name: file.name,
            size: file.size,
            type: file.type,
            content: typeof ev.target.result === 'string' ? ev.target.result : ''
          }
        ]);
      };
      reader.readAsText(file);
    });
  };

  const toggleVoiceInput = () => {
    if (isListening) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) { }
      }
      setIsListening(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Il riconoscimento vocale non è supportato in questo browser.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'it-IT';

      let baseText = input ? input + ' ' : '';

      recognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        setInput(baseText + transcript);
      };

      recognition.onerror = (err) => {
        console.warn('SpeechRecognition error:', err);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
      recognitionRef.current = recognition;
      setIsListening(true);
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      setIsListening(false);
    }
  };

  // Filtered Tasks for Dropdown
  const filteredTasks = useMemo(() => {
    if (!taskSearchQuery.trim()) return tasks;
    return tasks.filter(t => t.title.toLowerCase().includes(taskSearchQuery.toLowerCase()));
  }, [tasks, taskSearchQuery]);

  // Send Message & Stream Response with clean turn-based step splitting
  const handleSendMessage = async (textToSend, isAuto = false) => {
    const userPrompt = textToSend !== undefined ? textToSend : input.trim();
    if (!userPrompt && attachedFiles.length === 0) return;

    // Se l'agente sta già elaborando (isStreaming):
    // Se la chiamata è un trigger automatico del loop (isAuto = true), evitiamo sovrapposizioni.
    // Se invece è l'UTENTE che invia un messaggio, interrompiamo lo stream in corso
    // per dare precedenza immediata all'istruzione dell'utente e reindirizzare l'agente!
    if (isStreaming) {
      if (isAuto) return;
      if (abortControllerRef.current) {
        try { abortControllerRef.current.abort(); } catch (err) { }
        abortControllerRef.current = null;
      }
      setIsStreaming(false);
    }

    // Da questo momento l'utente ha interagito: il loop può ripartire se non attivo.
    userHasInteractedRef.current = true;

    const currentAttachments = [...attachedFiles];
    setAttachedFiles([]);
    if (isListening && recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (e) { }
      setIsListening(false);
    }

    // Cancella eventuali countdown del loop precedenti: l'istruzione dell'utente ha priorità
    setLoopCountdown(null);
    if (autoLoopTimeoutRef.current) {
      clearInterval(autoLoopTimeoutRef.current);
      autoLoopTimeoutRef.current = null;
    }

    // Read the true latest task state from latestTasksRef to avoid stale closure
    const currentTasks = latestTasksRef.current || tasks;
    const currentTask = currentTasks.find(t => t.id === activeTaskId) || currentTasks[0] || activeTask;
    const currentTaskId = currentTask.id;
    // Se c'era un messaggio parziale rimasto in streaming, sigillalo prima di appendere il nuovo messaggio
    const existingMessages = (currentTask.messages || []).map(m => m.isStreaming ? { ...m, isStreaming: false } : m);

    // Auto-update task title from first user prompt if still generic
    const isGenericTitle = currentTask.title.startsWith('Nuovo Task') || currentTask.title.startsWith('Task #');
    const newTitle = isGenericTitle
      ? (userPrompt ? (userPrompt.slice(0, 36) + (userPrompt.length > 36 ? '...' : '')) : `Allegati (${currentAttachments.length})`)
      : currentTask.title;

    const activeSubTask = (currentTask.pipeline || []).find(p => p.status === 'in_progress') ||
      (currentTask.pipeline || []).find(p => p.status === 'pending');
    const taskTitleMatch = userPrompt.match(/Procedi con il task pianificato(?:\s*#\d+)?:\s*"([^"]+)"/);
    const activeTaskTitle = taskTitleMatch ? taskTitleMatch[1] : (activeSubTask?.title || '');

    const isAutomaticMessage = isAuto || (typeof textToSend === 'string' && (
      textToSend.startsWith('Procedi con il task pianificato') ||
      textToSend.startsWith('Tutti i task pianificati nella pipeline') ||
      textToSend.startsWith('Continua l\'implementazione:')
    ));

    const userMsgObj = {
      role: 'user',
      content: userPrompt || `Analizza i file allegati: ${currentAttachments.map(a => a.name).join(', ')}`,
      attachments: currentAttachments.length > 0 ? currentAttachments : undefined,
      timestamp: new Date().toISOString(),
      isAutomatic: isAutomaticMessage
    };

    const newMessages = [...existingMessages, userMsgObj];
    let activeMsgIndex = newMessages.length;

    // Append user message + first assistant turn placeholder and reset goal completion
    setTasks(prev => prev.map(t => {
      if (t.id === currentTaskId) {
        return {
          ...t,
          title: newTitle,
          isGoalCompleted: false, // Reset stato completamento per la nuova istruzione
          autoLoop: true, // Mantiene attivo l'auto-loop per l'avanzamento dei task
          updatedAt: new Date().toISOString(),
          messages: [
            ...newMessages,
            { role: 'assistant', content: '', thought: '', tools: [], isStreaming: true, model: selectedModel, taskTitle: activeTaskTitle, timestamp: new Date().toISOString() }
          ]
        };
      }
      return t;
    }));

    setInput('');
    setIsStreaming(true);
    // Il consuntivo appartiene al run che sta per cominciare, non al
    // precedente: lasciarlo in vista farebbe leggere numeri vecchi come nuovi.
    setRunMetrics(null);
    setResumedFrom(null);
    setAgentStatus(`⏳ Inizializzazione e caricamento pesi modello (${selectedModel})...`);

    if (abortControllerRef.current) {
      try { abortControllerRef.current.abort(); } catch (e) { }
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch('/api/developer/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          messages: newMessages.map(m => ({
            role: m.role,
            content: m.content,
            attachments: m.attachments
          })),
          pipeline: currentTask.pipeline || [],
          workspace_root: workspaceRoot,
          model: selectedModel,
          auto_execute_tools: autoExecuteTools,
          context_tokens: contextTokens,
          max_turns: maxTurns,
          // L'identita' del task e' anche quella della sessione di lavoro sul
          // server: e' cio' che permette all'agente di ritrovare i file che
          // aveva gia' letto dopo un refresh della pagina.
          session_id: currentTaskId,
          review_writes: reviewWrites,
          isolate_worktree: isolateWorktree,
          review_run: reviewRun,
          profile
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamStartTime = Date.now();
      let streamFirstTokenTime = null;
      let streamTokenCount = 0;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.replace(/^data: /, '').trim();
          if (!dataStr) continue;

          try {
            const event = JSON.parse(dataStr);

            // Handle context window metadata from engine
            if (event.type === 'context_info') {
              setContextMetrics({
                promptTokens: event.prompt_tokens,
                limit: event.context_limit,
                maxTokens: event.max_tokens
              });
              continue;
            }

            // Telemetria live di contesto: TPS, TTFT e token in ingresso.
            if (event.type === 'context_telemetry') {
              setContextMetrics({
                turn: event.turn,
                tps: event.tps,
                ttftMs: event.ttft_ms,
                promptTokens: event.prompt_tokens,
                generatedTokensLastTurn: event.generated_tokens_last_turn
              });
              continue;
            }

            // Metriche di fine turno: TPS e TTFT precisi misurati dopo la
            // generazione completa. Sovrascrivono i valori parziali di
            // context_telemetry con dati definitivi.
            if (event.type === 'metrics') {
              setContextMetrics(prev => ({
                ...prev,
                tps: event.tps,
                ttftMs: event.ttft_ms,
                turnTokens: event.tokens,
                totalTokens: event.total_tokens,
                turnDurationS: event.duration_s
              }));
              continue;
            }

            // Handle status notifications (e.g. Model loading into VRAM, Tool running)
            if (event.type === 'status') {
              setAgentStatus(event.text || '');
              continue;
            }

            // Working-state snapshot, emitted after every tool execution.
            if (event.type === 'ledger') {
              setLedgerState(event.state || null);
              continue;
            }

            // Lo stato salvato di questo task e' stato ritrovato sul server:
            // l'agente riparte da li' invece che da zero.
            if (event.type === 'session_resumed') {
              setResumedFrom({
                files: event.files_known || 0,
                commands: event.commands_known || 0
              });
              continue;
            }

            // Consuntivo del run: turni, token, esito dei tool.
            if (event.type === 'run_metrics') {
              setRunMetrics({
                turns: event.turns,
                generatedTokens: event.generated_tokens,
                toolCalls: event.tool_calls,
                toolFailures: event.tool_failures,
                toolRefusals: event.tool_refusals,
                elapsedS: event.elapsed_s,
                goalReached: event.goal_reached,
                exhaustedTurns: event.exhausted_turns
              });
              continue;
            }

            // Un tool vietato al ruolo: non e' un errore del modello, e la
            // distinzione conta quando si legge il perche' di un run fermo.
            if (event.type === 'tool_denied') {
              setAgentStatus(`⛔ ${event.tool} non permesso in questa fase`);
              continue;
            }

            // Il lavoro e' arrivato su dev: da li' si accetta.
            if (event.type === 'run_delivered') {
              setDeliveredWork({
                branch: event.branch,
                base: event.base,
                files: (event.files || []).length,
                url: event.pull_request_url || event.compare_url || '',
                opened: !!event.pull_request_url
              });
              setAgentStatus(`Lavoro consegnato su ${event.branch}`);
              continue;
            }

            if (event.type === 'delivery_failed') {
              setDeliveredWork(null);
              setAgentStatus(
                `Consegna non riuscita: ${event.error || 'motivo sconosciuto'}`
              );
              continue;
            }

            // Il run e' finito senza chiudere l'obiettivo e lavorava in un
            // worktree: il lavoro non e' perduto, ma serve saperne il branch.
            if (event.type === 'worktree_preserved') {
              setPreservedBranch({
                branch: event.branch,
                checkpoints: event.checkpoints || 0,
                applyFailed: !!event.apply_failed
              });
              continue;
            }

            // Tutto il lavoro del run, da rivedere in una volta sola.
            if (event.type === 'run_diff_proposed') {
              setPendingReview({
                id: event.id,
                path: event.branch,
                diff: `${event.stat || ''}
${event.diff || ''}`,
                tool: 'run',
                isRun: true,
                fileCount: event.file_count,
                truncated: !!event.truncated
              });
              setAgentStatus(`In attesa della tua revisione su ${event.file_count} file`);
              continue;
            }

            if (event.type === 'run_diff_decided') {
              setPendingReview(null);
              setAgentStatus(event.applied
                ? "Lavoro trasferito all'albero principale"
                : `Lavoro non applicato: resta sul branch ${event.branch}`);
              continue;
            }

            // Una modifica e' sul disco ma non e' ancora definitiva: il run
            // e' fermo qui finche' non arriva una decisione.
            if (event.type === 'write_proposed') {
              setPendingReview({
                id: event.id,
                path: event.path,
                diff: event.diff,
                tool: event.tool
              });
              setAgentStatus('In attesa della tua revisione sulla modifica proposta');
              continue;
            }

            // Rifiutata o scaduta: il file e' tornato com'era.
            if (event.type === 'write_reverted') {
              setPendingReview(null);
              setAgentStatus(
                event.reverted
                  ? `Modifica a ${event.path} annullata`
                  : `Modifica a ${event.path} NON annullata: controlla il file`
              );
              continue;
            }

            // The completion gate refused: show why, so a stalled run is
            // diagnosable without reading the transcript.
            if (event.type === 'completion_rejected') {
              const reason = event.reason || 'Criteri di accettazione o verifiche non soddisfatte';
              setGateReason(reason);
              setAgentStatus(`⚠️ Completamento respinto: ${reason}`);
              setTasks(prev => prev.map(t => {
                if (t.id === currentTaskId) {
                  const msgs = [...t.messages];
                  const cur = { ...msgs[activeMsgIndex] };
                  cur.gateRejected = true;
                  cur.gateReason = reason;
                  msgs[activeMsgIndex] = cur;
                  return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
                }
                return t;
              }));
              continue;
            }

            // Handle error event from harness/engine/model
            if (event.type === 'error') {
              const errMsg = event.error || event.message || 'Errore riscontrato';
              const errType = event.error_type || 'Errore';
              const tb = event.traceback || '';
              setAgentStatus(`❌ ${errType}: ${errMsg}`);
              setTasks(prev => prev.map(t => {
                if (t.id === currentTaskId) {
                  const msgs = [...t.messages];
                  const cur = { ...msgs[activeMsgIndex] };
                  cur.isError = true;
                  cur.errorType = errType;
                  cur.errorMessage = errMsg;
                  cur.traceback = tb;
                  if (!cur.content) {
                    cur.content = `⚠️ **[${errType}]**: ${errMsg}`;
                  }
                  msgs[activeMsgIndex] = cur;
                  return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
                }
                return t;
              }));
              continue;
            }

            // Una riga di diario: un fatto, non un evento tecnico.
            if (event.type === 'diario') {
              setDiario(prev => [...prev.slice(-199),
              { text: event.text, at: event.at || Date.now() / 1000 }]);
              continue;
            }

            // Il consuntivo: cosa è stato fatto, come funziona, come lo sappiamo.
            if (event.type === 'run_report') {
              setRunReport({ text: event.report, reached: !!event.goal_reached });
              continue;
            }

            // The model's output hit the token budget mid-tool-call.
            if (event.type === 'output_truncated') {
              setTruncationCount(n => n + 1);
              continue;
            }

            // Handle pipeline task updates from model
            if (event.type === 'pipeline_update' && Array.isArray(event.tasks)) {
              const hasPending = event.tasks.some(p => p.status !== 'done' && p.status !== 'completed');
              setTasks(prev => prev.map(t => {
                if (t.id === currentTaskId) {
                  return {
                    ...t,
                    pipeline: event.tasks,
                    // Se ci sono task ancora in sospeso, l'obiettivo non è concluso
                    isGoalCompleted: hasPending ? false : t.isGoalCompleted,
                    updatedAt: new Date().toISOString()
                  };
                }
                return t;
              }));
              continue;
            }

            // Handle final goal completion
            if (event.type === 'goal_complete') {
              setGateReason(null);
              setTasks(prev => prev.map(t => {
                if (t.id === currentTaskId) {
                  const updatedPipeline = (t.pipeline || []).map(p => ({ ...p, status: 'done' }));
                  return { ...t, isGoalCompleted: true, pipeline: updatedPipeline, updatedAt: new Date().toISOString() };
                }
                return t;
              }));
              continue;
            }

            // If a subsequent turn starts (e.g. after tool execution), seal previous message and start fresh step!
            if (event.type === 'turn_start') {
              if (event.turn > 1) {
                setTasks(prev => prev.map(t => {
                  if (t.id === currentTaskId) {
                    const msgs = [...t.messages];
                    if (msgs[activeMsgIndex]) {
                      msgs[activeMsgIndex].isStreaming = false;
                    }
                    const activeSubTask2 = (t.pipeline || []).find(p => p.status === 'in_progress') ||
                      (t.pipeline || []).find(p => p.status === 'pending');
                    msgs.push({
                      role: 'assistant',
                      content: '',
                      thought: '',
                      tools: [],
                      isStreaming: true,
                      model: selectedModel,
                      taskTitle: msgs[activeMsgIndex]?.taskTitle || activeSubTask2?.title || '',
                      timestamp: new Date().toISOString()
                    });
                    activeMsgIndex = msgs.length - 1;
                    return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
                  }
                  return t;
                }));
              }
              streamStartTime = Date.now();
              streamFirstTokenTime = null;
              streamTokenCount = 0;
              continue;
            }

            if (event.type === 'turn_end') {
              setAgentStatus('');
              setTasks(prev => prev.map(t => {
                if (t.id === currentTaskId) {
                  const msgs = [...t.messages];
                  if (msgs[activeMsgIndex]) {
                    msgs[activeMsgIndex].isStreaming = false;
                  }
                  return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
                }
                return t;
              }));
              continue;
            }

            setTasks(prev => prev.map(t => {
              if (t.id === currentTaskId) {
                const msgs = [...t.messages];
                const cur = { ...msgs[activeMsgIndex] };

                if (event.type === 'token' || event.type === 'thought') {
                  if (event.type === 'token') {
                    cur.content = (cur.content || '') + event.token;
                  } else {
                    cur.thought = (cur.thought || '') + event.token;
                  }
                  if (agentStatus) setAgentStatus('');

                  if (!streamFirstTokenTime) {
                    streamFirstTokenTime = Date.now();
                  }
                  streamTokenCount += 1;
                  const now = Date.now();
                  const liveDuration = Math.max((now - streamStartTime) / 1000, 0.05);
                  const genDuration = Math.max((now - streamFirstTokenTime) / 1000, 0.05);
                  const liveTps = streamTokenCount > 0 ? Math.round((streamTokenCount / genDuration) * 10) / 10 : 0;
                  const liveTtft = Math.round(streamFirstTokenTime - streamStartTime);

                  cur.metrics = {
                    tps: liveTps,
                    ttft_ms: liveTtft,
                    tokens: streamTokenCount,
                    total_tokens: streamTokenCount,
                    duration_s: Math.round(liveDuration * 10) / 10,
                    isLive: true
                  };
                } else if (event.type === 'metrics') {
                  cur.metrics = {
                    tps: event.tps,
                    ttft_ms: event.ttft_ms,
                    tokens: event.tokens,
                    total_tokens: event.total_tokens,
                    duration_s: event.duration_s,
                    isLive: false
                  };
                } else if (event.type === 'tool_start') {
                  cur.tools = [...(cur.tools || []), { tool: event.tool, params: event.params, status: 'running' }];
                } else if (event.type === 'tool_result') {
                  cur.tools = (cur.tools || []).map(toolItem =>
                    toolItem.tool === event.tool ? { ...toolItem, result: event.result, status: 'done' } : toolItem
                  );
                }

                msgs[activeMsgIndex] = cur;
                return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
              }
              return t;
            }));
          } catch (e) {
            console.error('Error parsing SSE event', e);
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        console.debug('Generation aborted by user');
        return;
      }
      setTasks(prev => prev.map(t => {
        if (t.id === currentTaskId) {
          const msgs = [...t.messages];
          msgs[activeMsgIndex] = {
            role: 'assistant',
            content: `❌ Errore durante l'elaborazione: ${err.message}`,
            tools: []
          };
          return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
        }
        return t;
      }));
    } finally {
      abortControllerRef.current = null;
      setIsStreaming(false);
      setAgentStatus('');
      onRefreshTree?.();
      setTasks(prev => prev.map(t => {
        if (t.id === currentTaskId) {
          const msgs = [...t.messages];
          if (msgs[activeMsgIndex]) {
            msgs[activeMsgIndex].isStreaming = false;
          }
          return { ...t, messages: msgs, updatedAt: new Date().toISOString() };
        }
        return t;
      }));

      // Check Auto-Loop Continuation Trigger
      setTimeout(() => {
        // Se l'utente non ha ancora interagito (es. mount dopo refresh),
        // non far partire il loop da solo.
        if (!userHasInteractedRef.current) return;

        setTasks(currentTasks => {
          const thisTask = currentTasks.find(t => t.id === currentTaskId);
          if (!thisTask) return currentTasks;

          const isLoopOn = thisTask.autoLoop ?? true;
          const pTasks = thisTask.pipeline || [];
          const hasPendingTasks = pTasks.length > 0 && pTasks.some(p => p.status !== 'done' && p.status !== 'completed');
          // L'obiettivo è considerato completato solo se non ci sono task ancora in sospeso
          const isCompleted = (thisTask.isGoalCompleted ?? false) && !hasPendingTasks;
          if (!isLoopOn || isCompleted) return currentTasks;

          const msgs = thisTask.messages || [];

          // Protezione Anti-Loop: verifichiamo se l'assistente risponde a vuoto o non produce modifiche
          const recentAssistant = msgs.filter(m => m.role === 'assistant').slice(-2);
          const isStuckEmpty = recentAssistant.length >= 2 && recentAssistant.every(m => {
            const hasContent = m.content && m.content.trim().length > 0;
            const hasTools = Array.isArray(m.tools) && m.tools.length > 0;
            return !hasContent && !hasTools;
          });

          // Se lo stesso identico prompt utente si ripete per 3 turni di fila
          const recentUsers = msgs.filter(m => m.role === 'user').slice(-3);
          const isPromptStuck = recentUsers.length >= 3 && recentUsers.every(m => m.content === recentUsers[0].content);

          if (isStuckEmpty || isPromptStuck) {
            console.warn('[AdminAgentChat] Auto-loop interrotto per mancato avanzamento o risposte vuote.');
            return currentTasks.map(t => t.id === currentTaskId ? { ...t, autoLoop: false } : t);
          }

          const pendingTask = pTasks.find(p => p.status === 'in_progress') || pTasks.find(p => p.status === 'pending');

          // Cosa e cambiato rispetto al giro precedente. Rimandare la stessa
          // stringa identica e il modo in cui questo loop ha bruciato trenta
          // turni su trenta: il modello rileggeva la stessa richiesta, con le
          // proprie risposte identiche in mezzo, e non aveva niente di nuovo su
          // cui lavorare. Una richiesta che dice cosa manca e una richiesta
          // diversa, e li vale il turno che costa.
          const ultimoTurno = [...msgs].reverse().find(
            m => m.role === 'assistant' && Array.isArray(m.tools) && m.tools.length > 0);
          const scritto = !!ultimoTurno && ultimoTurno.tools.some(
            t => ['write_file', 'edit_file', 'append_file'].includes(t.tool) && t.status === 'done');
          const usati = ultimoTurno ? [...new Set(ultimoTurno.tools.map(t => t.tool))].join(', ') : '';

          let nextPrompt = '';
          if (pendingTask) {
            const avanti = scritto ? '' : ` Nel turno precedente NON hai modificato nessun file${usati ? ` (strumenti usati: ${usati})` : ''}. Se il lavoro e piu grande di quanto sembrava, non insistere: spezza la voce con il blocco tool pipeline in due-quattro passi piu piccoli, ognuno con i file che tocca, e poi esegui il primo.`;
            nextPrompt = `Procedi con il task pianificato #${pendingTask.id || ''}: "${pendingTask.title}". Esegui i tool necessari (scrittura file con write_file/edit_file o comandi terminale) per completarlo. Al termine del lavoro su questo task, aggiorna la pipeline impostando lo status a "done" per questo task tramite il blocco tool pipeline.` + avanti;
          } else if (pTasks.length > 0 && pTasks.every(p => p.status === 'done' || p.status === 'completed')) {
            const msgs = thisTask.messages || [];
            const lastUserMsg = [...msgs].reverse().find(m => m.role === 'user');
            if (lastUserMsg && lastUserMsg.content.includes('Tutti i task pianificati nella pipeline risultano completati')) {
              // Verifica finale già richiesta nel turno precedente: fermiamo l'auto-loop per evitare chiamate infinite
              return currentTasks.map(t => t.id === currentTaskId ? { ...t, autoLoop: false, isGoalCompleted: true } : t);
            }
            nextPrompt = `Tutti i task pianificati nella pipeline risultano completati. Effettua una verifica finale o dichiara complete_goal con il riepilogo del lavoro svolto.`;
          } else {
            nextPrompt = `Continua l'implementazione: definisci o aggiorna la pipeline dei task tramite il blocco tool pipeline ed esegui le modifiche ai file del workspace.`;
          }

          setLoopCountdown(2);
          let count = 2;
          const timer = setInterval(() => {
            count -= 1;
            if (count <= 0) {
              clearInterval(timer);
              setLoopCountdown(null);
              handleSendMessage(nextPrompt, true);
            } else {
              setLoopCountdown(count);
            }
          }, 800);
          autoLoopTimeoutRef.current = timer;

          return currentTasks;
        });
      }, 400);
    }
  };

  const quickPrompts = [
    ...(pipeline && pipeline.length > 0 && pipeline.some(p => p.status !== 'done') && !isStreaming ? [{
      label: '▶️ Continua Task Pipeline',
      prompt: "Procedi con il prossimo task pianificato nella pipeline al fine di completare l'obiettivo.",
      highlight: true
    }] : []),
    ...(!isStreaming && messages.length > 1 && (!pipeline || pipeline.length === 0 || pipeline.some(p => p.status !== 'done')) ? [{
      label: '▶️ Continua',
      prompt: "Continua.",
      highlight: false
    }] : []),
    { label: '🔍 Analizza file attivo', prompt: `Analizza e descrivi l'architettura del file attivo (${activeFilePath || 'nessun file selezionato'}).` },
    { label: '🧪 Esegui test', prompt: 'Esegui i test unitari e verifica se ci sono errori da correggere.' },
    { label: '🧹 Pulisci cartella', prompt: 'Verifica la cartella data/ e rimuovi le cartelle temporanee o di prova.' }
  ];

  const renderMasterHeader = () => {
    const textPrimary = isLight ? '#24292f' : '#f0f6fc';
    const textMuted = isLight ? '#57606a' : '#8b949e';
    const borderCol = isLight ? '#d0d7de' : 'rgba(255,255,255,0.08)';
    const bgHeader = isLight ? '#ffffff' : '#0a0e14';
    const bgCard = isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.04)';

    const rootName = workspaceRoot ? workspaceRoot.replace(/\\/g, '/').split('/').filter(Boolean).pop() : 'Workspace';
    const activeFileName = activeFilePath ? activeFilePath.replace(/\\/g, '/').split('/').pop() : null;

    return (
      <div style={{
        padding: '6px 16px',
        borderBottom: `1px solid ${borderCol}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: bgHeader,
        position: 'relative',
        width: '100%',
        boxSizing: 'border-box',
        gap: '12px',
        flexWrap: 'nowrap',
        overflowX: 'auto',
        minHeight: '42px'
      }}>
        {/* Left Side (Spans Center Column): Brand + Full Workspace Access + Quick Path */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '26px',
              height: '26px',
              borderRadius: '7px',
              background: 'linear-gradient(135deg, #00f2fe, #0284c7)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0, 242, 254, 0.25)',
              flexShrink: 0
            }}>
              <Bot size={15} color="#000" />
            </div>
            <div>
              <div style={{ fontSize: '0.78rem', fontWeight: 800, color: textPrimary, letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>
                ADMIN AI DEVELOPER
              </div>
              <div style={{ fontSize: '0.62rem', color: '#22c55e', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap' }}>
                <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 6px #22c55e' }} />
                <span>Full Workspace Access</span>
              </div>
            </div>
          </div>

          <div style={{ width: '1px', height: '22px', background: borderCol }} />

          {/* Quick Breadcrumb / Active File Chip */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.68rem',
            padding: '2px 8px',
            borderRadius: '6px',
            background: bgCard,
            border: `1px solid ${borderCol}`,
            color: textMuted,
            whiteSpace: 'nowrap'
          }}>
            <span style={{ fontWeight: 700, color: textPrimary }}>📁 {rootName}</span>
            {activeFileName && (
              <>
                <span style={{ opacity: 0.4 }}>/</span>
                <span style={{ color: '#00d2ff', fontWeight: 600 }}>📄 {activeFileName}</span>
              </>
            )}
          </div>
        </div>

        {/* Right Side (Spacious Controls): Auto-Scroll, Auto-Exec, Revisione, Isolamento, Revisione run, Nessun limite, Docker, Loop, Nuovo Task */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
          {/* Controls Group 1: Auto-Scroll & Auto-Exec */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '3px 8px',
            borderRadius: '6px',
            background: bgCard,
            border: `1px solid ${borderCol}`
          }}>
            <label style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              color: autoScroll ? '#00d2ff' : textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              whiteSpace: 'nowrap'
            }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={e => setAutoScroll(e.target.checked)}
                style={{ accentColor: '#00d2ff' }}
              />
              Auto-Scroll
            </label>

            <div style={{ width: '1px', height: '14px', background: borderCol }} />

            <label style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              color: autoExecuteTools ? '#22c55e' : textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              whiteSpace: 'nowrap'
            }}>
              <input
                type="checkbox"
                checked={autoExecuteTools}
                onChange={e => handleToggleAutoExecute(e.target.checked)}
                style={{ accentColor: '#22c55e' }}
              />
              Auto-Exec
            </label>
          </div>

          {/* Controls Group 2: Revisione, Isolamento, Revisione run */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '3px 8px',
            borderRadius: '6px',
            background: bgCard,
            border: `1px solid ${borderCol}`
          }}>
            <label style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              color: reviewWrites ? '#f59e0b' : textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              whiteSpace: 'nowrap'
            }}
              title="Ogni modifica a un file viene mostrata con il suo diff e resta solo se la approvi"
            >
              <input
                type="checkbox"
                checked={reviewWrites}
                onChange={e => handleToggleReviewWrites(e.target.checked)}
                style={{ accentColor: '#f59e0b' }}
              />
              Revisione
            </label>

            <div style={{ width: '1px', height: '14px', background: borderCol }} />

            <label style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              color: isolateWorktree ? '#a855f7' : textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              whiteSpace: 'nowrap'
            }}
              title="L'agente lavora in una copia git isolata del progetto, con un checkpoint per turno. A obiettivo raggiunto le modifiche passano all'albero principale, altrimenti restano su un branch dedicato"
            >
              <input
                type="checkbox"
                checked={isolateWorktree}
                onChange={e => handleToggleIsolateWorktree(e.target.checked)}
                style={{ accentColor: '#a855f7' }}
              />
              Isolamento
            </label>

            <div style={{ width: '1px', height: '14px', background: borderCol }} />

            <label style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              color: reviewRun ? '#f59e0b' : textMuted,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              whiteSpace: 'nowrap'
            }}
              title="A fine run mostra il diff di tutto il lavoro e chiede una sola approvazione prima di trasferirlo. Accende anche l'isolamento, che è la sua precondizione"
            >
              <input
                type="checkbox"
                checked={reviewRun}
                onChange={e => handleToggleReviewRun(e.target.checked)}
                style={{ accentColor: '#f59e0b' }}
              />
              Revisione run
            </label>
          </div>

          {/* Profile Selector */}
          <select
            value={profile}
            onChange={e => handleSelectProfile(e.target.value)}
            title="Un tetto ai tool, indipendente dal ruolo: in sola lettura nessun ruolo può scrivere"
            style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '6px',
              cursor: 'pointer',
              color: profile ? '#f97316' : textMuted,
              background: isLight ? '#ffffff' : '#161b22',
              border: profile
                ? '1px solid rgba(249, 115, 22, 0.45)'
                : `1px solid ${borderCol}`
            }}
          >
            <option value="">Nessun limite</option>
            <option value="read_only">Sola Lettura</option>
            <option value="plan_only">Sola Pianificazione</option>
          </select>

          {/* Docker Sandbox Control Widget */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '3px 8px',
            borderRadius: '6px',
            background: sandboxConfig.active
              ? 'rgba(56, 189, 248, 0.12)'
              : bgCard,
            border: sandboxConfig.active
              ? '1px solid rgba(56, 189, 248, 0.4)'
              : `1px solid ${borderCol}`,
          }}
            title={
              sandboxConfig.docker_available
                ? `Docker: ${sandboxConfig.docker_detail}. Modalità corrente: ${sandboxConfig.mode}. Clicca per commutare tra Host e Container isolato.`
                : `Docker non disponibile: ${sandboxConfig.docker_detail}`
            }
          >
            <span style={{
              fontSize: '0.66rem',
              fontWeight: 700,
              color: sandboxConfig.active ? '#38bdf8' : textMuted,
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              whiteSpace: 'nowrap'
            }}>
              <span>🐳 Docker</span>
            </span>

            <button
              type="button"
              disabled={!sandboxConfig.docker_available || sandboxLoading}
              onClick={() => handleToggleSandbox(sandboxConfig.mode === 'container' ? 'host' : 'container')}
              style={{
                background: sandboxConfig.active ? '#0284c7' : (isLight ? '#e1e4e8' : 'rgba(255,255,255,0.08)'),
                color: sandboxConfig.active ? '#ffffff' : textPrimary,
                border: 'none',
                borderRadius: '4px',
                fontSize: '0.63rem',
                fontWeight: 700,
                padding: '2px 7px',
                cursor: sandboxConfig.docker_available ? 'pointer' : 'not-allowed',
                opacity: sandboxConfig.docker_available ? 1 : 0.5,
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap'
              }}
            >
              {sandboxConfig.mode === 'container' ? 'Sandbox Attiva' : 'Usa Docker'}
            </button>

            {/* Pulsante rapido per aprire la gestione completa Docker */}
            <button
              type="button"
              onClick={() => setShowDockerModal(true)}
              title="Apri Monitor & Gestione Container Docker"
              style={{
                background: 'transparent',
                border: 'none',
                color: textMuted,
                cursor: 'pointer',
                padding: '2px',
                display: 'flex',
                alignItems: 'center'
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#38bdf8'}
              onMouseLeave={e => e.currentTarget.style.color = textMuted}
            >
              <Settings size={12} />
            </button>
          </div>

          {/* Quick Active Container Web Ports Navigation */}
          {(() => {
            const runningContainers = (sandboxConfig.containers || []).filter(c => c.State === 'running' || c.Status?.startsWith('Up'));
            const activePorts = new Set();
            for (const c of runningContainers) {
              if (c.Ports) {
                const re = /(?:^|[,\s])(?:(?:\d{1,3}\.){3}\d{1,3}|\[::\]|::)?:?(\d+)->/g;
                let m;
                while ((m = re.exec(c.Ports)) !== null) {
                  if (m[1]) activePorts.add(m[1]);
                }
              }
            }
            if (activePorts.size === 0) return null;
            return (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                {Array.from(activePorts).map(port => (
                  <button
                    key={port}
                    type="button"
                    onClick={() => window.open(`http://localhost:${port}`, '_blank', 'noopener,noreferrer')}
                    title={`Apri applicazione web su http://localhost:${port}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '3px 8px',
                      borderRadius: '6px',
                      background: 'rgba(0, 242, 254, 0.15)',
                      border: '1px solid rgba(0, 242, 254, 0.4)',
                      color: '#00f2fe',
                      fontSize: '0.66rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    <span>🌐 :{port}</span>
                  </button>
                ))}
              </div>
            );
          })()}

          {/* "+ Nuovo Task" Button */}
          <button
            type="button"
            onClick={handleCreateNewTask}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 10px',
              borderRadius: '6px',
              background: 'linear-gradient(135deg, rgba(0, 242, 254, 0.2), rgba(2, 132, 199, 0.25))',
              border: '1px solid rgba(0, 242, 254, 0.4)',
              color: '#00f2fe',
              fontSize: '0.68rem',
              fontWeight: 800,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              whiteSpace: 'nowrap'
            }}
            title="Crea una nuova sessione di lavoro"
          >
            <Plus size={12} />
            <span>Nuovo Task</span>
          </button>
        </div>
      </div>
    );
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      minWidth: 0,
      flex: 1,
      background: isLight ? '#f6f8fa' : '#0d1117',
      overflow: 'hidden'
    }}>
      {/* Master Header: renderizzata nella barra superiore sopra la colonna centrale + destra */}
      {headerPortalNode
        ? createPortal(renderMasterHeader(), headerPortalNode)
        : renderMasterHeader()}

      {/* Task Switcher & History Bar */}
      <div style={{
        padding: '6px 12px',
        borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
        background: isLight ? '#ffffff' : '#0a0e14',
        position: 'relative'
      }}>
        <div style={{ position: 'relative' }} ref={taskMenuRef}>
          <div
            onClick={() => setShowTaskMenu(!showTaskMenu)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '5px 10px',
              borderRadius: '6px',
              background: isLight ? '#f6f8fa' : '#161b22',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
              cursor: 'pointer',
              fontSize: '0.70rem',
              color: isLight ? '#24292f' : '#f0f6fc'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
              <MessageSquare size={12} color="#00f2fe" style={{ flexShrink: 0 }} />
              <span style={{ fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {activeTask.title}
              </span>
              <span style={{ fontSize: '0.62rem', color: '#8b949e', flexShrink: 0 }}>
                • {messages.length} msg
              </span>
            </div>
            <ChevronDown size={12} color="#8b949e" style={{ transform: showTaskMenu ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
          </div>

          {/* Task Dropdown Menu / History List */}
          {showTaskMenu && (
            <div style={{
              position: 'absolute',
              top: 'calc(100% + 4px)',
              left: 0,
              right: 0,
              zIndex: 100,
              background: isLight ? '#ffffff' : '#0d1117',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.15)',
              borderRadius: '8px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              maxHeight: '280px',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden'
            }}>
              {/* Task Search Bar */}
              <div style={{
                padding: '6px 8px',
                borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}>
                <Search size={12} color="#8b949e" />
                <input
                  type="text"
                  placeholder="Cerca nei task salvati..."
                  value={taskSearchQuery}
                  onChange={e => setTaskSearchQuery(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    fontSize: '0.68rem',
                    color: isLight ? '#24292f' : '#f0f6fc'
                  }}
                  autoFocus
                />
              </div>

              {/* Task List */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '4px' }}>
                {filteredTasks.map(t => {
                  const isActive = t.id === activeTask.id;
                  const isEditing = editingTaskId === t.id;

                  return (
                    <div
                      key={t.id}
                      onClick={() => !isEditing && handleSelectTask(t.id)}
                      style={{
                        padding: '6px 8px',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        background: isActive ? 'rgba(0, 242, 254, 0.12)' : 'transparent',
                        cursor: 'pointer',
                        marginBottom: '2px',
                        fontSize: '0.68rem',
                        transition: 'background 0.1s'
                      }}
                      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = isLight ? '#f6f8fa' : 'rgba(255,255,255,0.05)'; }}
                      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                    >
                      {isEditing ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flex: 1 }} onClick={e => e.stopPropagation()}>
                          <input
                            type="text"
                            value={editTitleInput}
                            onChange={e => setEditTitleInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleSaveRename(t.id, e)}
                            style={{
                              flex: 1,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              border: '1px solid #00f2fe',
                              background: isLight ? '#fff' : '#161b22',
                              color: isLight ? '#000' : '#fff',
                              fontSize: '0.68rem',
                              outline: 'none'
                            }}
                            autoFocus
                          />
                          <button
                            type="button"
                            onClick={(e) => handleSaveRename(t.id, e)}
                            style={{ background: 'none', border: 'none', color: '#3fb950', cursor: 'pointer' }}
                          >
                            <Check size={12} />
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, paddingRight: '8px' }}>
                          <div style={{
                            fontWeight: isActive ? 800 : 500,
                            color: isActive ? '#00f2fe' : (isLight ? '#24292f' : '#f0f6fc'),
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {t.title}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.60rem', color: '#8b949e', marginTop: '1px' }}>
                            <span>{t.messages.length} msg</span>
                            <span>• {formatTimeAgo(t.updatedAt)}</span>
                          </div>
                        </div>
                      )}

                      {!isEditing && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <button
                            type="button"
                            onClick={(e) => handleStartRename(t, e)}
                            style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '2px' }}
                            title="Rinomina Task"
                          >
                            <Edit2 size={11} />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteTask(t.id, e)}
                            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px' }}
                            title="Elimina Task"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Row 3: Model Selector with Specs, Weights & Context Window Selector */}
        <DeveloperModelSelector
          selectedModel={selectedModel}
          onSelectModel={handleModelChange}
          contextTokens={contextTokens}
          onSelectContextTokens={handleSelectContextTokens}
          contextMetrics={contextMetrics}
          theme={theme}
          isLight={isLight}
        />

        {/* Notifiche sempre visibili: consegna, branch conservato, review, countdown */}
        {deliveredWork && (
          <div style={{
            margin: '6px 0',
            padding: '7px 10px',
            borderRadius: '8px',
            border: '1px solid rgba(63, 185, 80, 0.45)',
            background: isLight ? 'rgba(63, 185, 80, 0.08)' : 'rgba(63, 185, 80, 0.10)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexWrap: 'wrap'
          }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#3fb950' }}>
              Consegnato
            </span>
            <span style={{ fontSize: '0.66rem', color: isLight ? '#24292e' : '#c9d1d9' }}>
              {deliveredWork.files} file su <code style={{ color: '#3fb950' }}>{deliveredWork.branch}</code>,
              da accettare verso <code style={{ color: '#3fb950' }}>{deliveredWork.base}</code>
            </span>
            {deliveredWork.url && (
              <a
                href={deliveredWork.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: '0.66rem',
                  fontWeight: 700,
                  color: '#00f2fe',
                  textDecoration: 'none'
                }}
              >
                {deliveredWork.opened ? 'Apri la richiesta' : 'Apri la richiesta su GitHub'} →
              </a>
            )}
            <button
              onClick={() => setDeliveredWork(null)}
              style={{
                marginLeft: 'auto', background: 'transparent', border: 'none',
                color: '#8b949e', cursor: 'pointer', fontSize: '0.7rem'
              }}
            >
              ✕
            </button>
          </div>
        )}

        {preservedBranch && (
          <div style={{
            margin: '6px 0',
            padding: '7px 10px',
            borderRadius: '8px',
            border: '1px solid rgba(163, 113, 247, 0.45)',
            background: isLight ? 'rgba(163, 113, 247, 0.08)' : 'rgba(163, 113, 247, 0.10)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexWrap: 'wrap'
          }}>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 800,
              color: preservedBranch.applyFailed ? '#d29922' : '#a371f7'
            }}>
              {preservedBranch.applyFailed ? 'Trasferimento non riuscito' : 'Lavoro conservato'}
            </span>
            <span style={{ fontSize: '0.66rem', color: isLight ? '#24292e' : '#c9d1d9' }}>
              {preservedBranch.applyFailed
                ? `L'obiettivo e' stato raggiunto ma le modifiche non sono passate all'albero principale (probabile conflitto). Restano intatte sul branch`
                : `L'obiettivo non e' stato chiuso, ma ${preservedBranch.checkpoints} checkpoint restano sul branch`}
            </span>
            <code style={{ fontSize: '0.66rem', fontFamily: 'monospace', color: '#a371f7' }}>
              {preservedBranch.branch}
            </code>
            <button
              onClick={() => setPreservedBranch(null)}
              style={{
                marginLeft: 'auto',
                background: 'transparent',
                border: 'none',
                color: '#8b949e',
                cursor: 'pointer',
                fontSize: '0.7rem'
              }}
            >
              ✕
            </button>
          </div>
        )}

        <ReviewProposal
          proposal={pendingReview}
          onDecide={handleReviewDecide}
          deciding={decidingReview}
          isLight={isLight}
        />

        {/* Auto-Loop Countdown Alert Banner — sempre visibile */}
        {loopCountdown !== null && (
          <div style={{
            padding: '6px 12px',
            borderRadius: '8px',
            background: isLight ? 'rgba(0, 242, 254, 0.15)' : 'rgba(0, 242, 254, 0.1)',
            border: '1px solid #00f2fe',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 2px 10px rgba(0, 242, 254, 0.2)',
            marginTop: '2px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.70rem', fontWeight: 700, color: isLight ? '#0070f3' : '#00f2fe' }}>
              <RotateCw size={13} className="spin" />
              <span>🔁 Auto-Loop: prossimo step automatico tra {loopCountdown}s...</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                type="button"
                onClick={() => {
                  stopAutoLoop();
                  handleSendMessage("Procedi con il prossimo task pianificato nella pipeline al fine di completare l'obiettivo.");
                }}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  background: '#00f2fe',
                  border: 'none',
                  color: '#000',
                  fontSize: '0.62rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                ⚡ Esegui Ora
              </button>
              <button
                type="button"
                onClick={stopAutoLoop}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  background: 'rgba(239, 68, 68, 0.2)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  color: '#ef4444',
                  fontSize: '0.62rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                ⏹️ Ferma Loop
              </button>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            Mini-Tab Bar: organizza Monitor, Piano, Attività, Ventaglio
            ═══════════════════════════════════════════════════════════════════ */}
        {(() => {
          const borderCol = isLight ? '#d0d7de' : 'rgba(255,255,255,0.08)';
          const tabItems = [
            {
              id: 'piano', label: '📋 Piano', icon: ListTodo, color: '#00f2fe',
              badge: pipeline && pipeline.length > 0
                ? `${pipeline.filter(p => p.status === 'done').length}/${pipeline.length}`
                : null
            },
            {
              id: 'monitor', label: '📊 Monitor', icon: Activity, color: '#3fb950',
              badge: ledgerState ? `${(ledgerState.files || []).filter(f => f.edits > 0 || f.writes > 0).length} mod` : null
            },
            {
              id: 'attivita', label: '⚡ Attività', icon: Activity, color: '#a371f7',
              badge: null
            },
          ];

          return (
            <div style={{
              borderRadius: '8px',
              background: isLight ? '#ffffff' : '#111620',
              border: `1px solid ${borderCol}`,
              overflow: 'hidden',
              marginTop: '4px'
            }}>
              {/* La barra delle tab */}
              <div style={{
                display: 'flex',
                borderBottom: `1px solid ${borderCol}`,
                background: isLight ? '#f6f8fa' : '#0d1117'
              }}>
                {tabItems.map(tab => {
                  const isActive = activeInfoTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveInfoTab(isActive ? null : tab.id)}
                      style={{
                        flex: 1,
                        padding: '5px 6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px',
                        background: isActive
                          ? (isLight ? '#ffffff' : 'rgba(255,255,255,0.06)')
                          : 'transparent',
                        border: 'none',
                        borderBottom: isActive
                          ? `2px solid ${tab.color}`
                          : '2px solid transparent',
                        color: isActive ? tab.color : (isLight ? '#57606a' : '#8b949e'),
                        fontSize: '0.62rem',
                        fontWeight: isActive ? 800 : 600,
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      <span>{tab.label}</span>
                      {tab.badge && (
                        <span style={{
                          padding: '0 4px',
                          borderRadius: '6px',
                          background: `${tab.color}22`,
                          color: tab.color,
                          fontSize: '0.56rem',
                          fontWeight: 800
                        }}>
                          {tab.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Contenuto della tab attiva */}
              {activeInfoTab === 'piano' && (
                <div style={{ maxHeight: '260px', overflowY: 'auto' }}>
                  {/* Pipeline Header con stato obiettivo */}
                  <div
                    onClick={() => setShowPipeline(!showPipeline)}
                    style={{
                      padding: '6px 10px',
                      background: isGoalCompleted
                        ? (isLight ? 'rgba(63, 185, 80, 0.12)' : 'rgba(63, 185, 80, 0.08)')
                        : (pipeline && pipeline.length > 0
                          ? (isLight ? 'rgba(0, 242, 254, 0.08)' : 'rgba(0, 242, 254, 0.05)')
                          : 'transparent'),
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      userSelect: 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{
                        fontSize: '0.66rem',
                        fontWeight: 800,
                        color: isGoalCompleted ? '#3fb950' : (pipeline && pipeline.length > 0 ? (isLight ? '#24292f' : '#f0f6fc') : '#8b949e')
                      }}>
                        Piano d'Azione {pipeline && pipeline.length > 0 ? `(${pipeline.filter(p => p.status === 'done').length}/${pipeline.length})` : ''}
                      </span>
                      {isGoalCompleted && (
                        <span style={{ fontSize: '0.56rem', padding: '1px 5px', borderRadius: '8px', background: 'rgba(63, 185, 80, 0.2)', color: '#3fb950', fontWeight: 800 }}>
                          ✓ Obiettivo Raggiunto
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {pipeline && pipeline.length > 0 && (
                        <>
                          <div style={{
                            width: '60px', height: '4px', borderRadius: '2px',
                            background: isLight ? '#e1e4e8' : 'rgba(255,255,255,0.1)', overflow: 'hidden'
                          }}>
                            <div style={{
                              width: `${Math.round((pipeline.filter(p => p.status === 'done').length / Math.max(pipeline.length, 1)) * 100)}%`,
                              height: '100%',
                              background: isGoalCompleted ? '#3fb950' : 'linear-gradient(90deg, #00f2fe, #4facfe)',
                              transition: 'width 0.3s ease'
                            }} />
                          </div>
                          <span style={{ fontSize: '0.58rem', fontWeight: 700, color: '#8b949e' }}>
                            {Math.round((pipeline.filter(p => p.status === 'done').length / Math.max(pipeline.length, 1)) * 100)}%
                          </span>
                        </>
                      )}
                      {showPipeline ? <ChevronUp size={11} color="#8b949e" /> : <ChevronDown size={11} color="#8b949e" />}
                    </div>
                  </div>

                  {showPipeline && (
                    <div style={{ padding: '6px 10px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {(!pipeline || pipeline.length === 0) ? (
                        <div style={{
                          padding: '8px',
                          borderRadius: '6px',
                          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)',
                          fontSize: '0.64rem',
                          color: isLight ? '#57606a' : '#8b949e',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '6px'
                        }}>
                          <span>💡 Nessun task definito. L'agente creerà la scaletta al primo messaggio.</span>
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setShowNewTaskInline(true); }}
                            style={{
                              padding: '2px 6px', borderRadius: '4px',
                              background: 'rgba(0, 242, 254, 0.12)',
                              border: '1px solid rgba(0, 242, 254, 0.35)',
                              color: '#00f2fe', fontSize: '0.60rem',
                              fontWeight: 700, cursor: 'pointer', flexShrink: 0
                            }}
                          >
                            + Aggiungi
                          </button>
                        </div>
                      ) : (
                        pipeline.map((item) => {
                          const isDone = item.status === 'done';
                          const inProgress = item.status === 'in_progress';
                          return (
                            <div
                              key={item.id}
                              style={{
                                display: 'flex',
                                alignItems: 'flex-start',
                                justifyContent: 'space-between',
                                padding: '4px 6px',
                                borderRadius: '5px',
                                background: inProgress
                                  ? (isLight ? 'rgba(0, 242, 254, 0.10)' : 'rgba(0, 242, 254, 0.06)')
                                  : (isDone ? (isLight ? 'rgba(63, 185, 80, 0.06)' : 'rgba(63, 185, 80, 0.04)') : 'transparent'),
                                border: inProgress ? '1px solid rgba(0, 242, 254, 0.20)' : (isDone ? '1px solid rgba(63, 185, 80, 0.12)' : '1px solid transparent'),
                                fontSize: '0.64rem',
                                gap: '6px'
                              }}
                            >
                              <div
                                onClick={() => toggleTaskStatus(item.id)}
                                style={{ display: 'flex', alignItems: 'flex-start', gap: '5px', cursor: 'pointer', flex: 1, minWidth: 0 }}
                                title="Clicca per cambiare stato"
                              >
                                <div style={{ marginTop: '1px' }}>
                                  {isDone ? <CheckCircle2 size={12} color="#3fb950" />
                                    : inProgress ? <CircleDot size={12} color="#00f2fe" />
                                      : <Circle size={12} color="#8b949e" />}
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', flex: 1, minWidth: 0 }}>
                                  <span style={{
                                    color: isDone ? '#8b949e' : (inProgress ? '#00f2fe' : (isLight ? '#24292f' : '#e6edf3')),
                                    textDecoration: isDone ? 'line-through' : 'none',
                                    fontWeight: inProgress ? 800 : 600,
                                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                                  }}>
                                    {item.title}
                                  </span>
                                  {item.description && item.description !== item.title && (
                                    <span style={{ fontSize: '0.56rem', color: '#8b949e', lineHeight: 1.3 }}>
                                      {item.description}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '1px' }}>
                                <span
                                  onClick={() => toggleTaskStatus(item.id)}
                                  style={{
                                    fontSize: '0.54rem', padding: '1px 5px', borderRadius: '6px',
                                    fontWeight: 800, cursor: 'pointer',
                                    background: isDone ? 'rgba(63, 185, 80, 0.2)' : (inProgress ? 'rgba(0, 242, 254, 0.2)' : 'rgba(255,255,255,0.08)'),
                                    color: isDone ? '#3fb950' : (inProgress ? '#00f2fe' : '#8b949e')
                                  }}
                                  title="Cambia stato"
                                >
                                  {isDone ? '✓' : (inProgress ? '⚡' : '⏳')}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => removePipelineTask(item.id)}
                                  style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '1px' }}
                                  title="Rimuovi"
                                >
                                  <X size={10} />
                                </button>
                              </div>
                            </div>
                          );
                        })
                      )}

                      {showNewTaskInline ? (
                        <form onSubmit={handleAddPipelineTask} style={{
                          display: 'flex', flexDirection: 'column', gap: '4px',
                          marginTop: '3px', padding: '5px', borderRadius: '5px',
                          background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
                          border: '1px solid rgba(0, 242, 254, 0.3)'
                        }}>
                          <input type="text" placeholder="Titolo sotto-task..."
                            value={newPipelineInput} onChange={e => setNewPipelineInput(e.target.value)}
                            style={{
                              padding: '3px 6px', borderRadius: '4px', border: '1px solid #00f2fe',
                              background: isLight ? '#fff' : '#07090e', color: isLight ? '#000' : '#fff',
                              fontSize: '0.64rem', outline: 'none'
                            }}
                            autoFocus
                          />
                          <input type="text" placeholder="Dettagli opzionali..."
                            value={newPipelineDesc} onChange={e => setNewPipelineDesc(e.target.value)}
                            style={{
                              padding: '3px 6px', borderRadius: '4px',
                              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)',
                              background: isLight ? '#fff' : '#07090e', color: isLight ? '#000' : '#fff',
                              fontSize: '0.60rem', outline: 'none'
                            }}
                          />
                          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '5px' }}>
                            <button type="button"
                              onClick={() => { setShowNewTaskInline(false); setNewPipelineInput(''); setNewPipelineDesc(''); }}
                              style={{ background: 'none', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: '0.58rem' }}>
                              Annulla
                            </button>
                            <button type="submit" disabled={!newPipelineInput.trim()}
                              style={{
                                padding: '2px 6px', borderRadius: '4px', background: '#00f2fe',
                                border: 'none', color: '#000', fontSize: '0.60rem', fontWeight: 700, cursor: 'pointer'
                              }}>
                              Salva
                            </button>
                          </div>
                        </form>
                      ) : (
                        <button type="button" onClick={() => setShowNewTaskInline(true)}
                          style={{
                            background: 'none', border: 'none', color: '#00f2fe',
                            fontSize: '0.60rem', fontWeight: 700, cursor: 'pointer',
                            display: 'inline-flex', alignItems: 'center', gap: '3px',
                            padding: '3px 0', marginTop: '2px'
                          }}>
                          <Plus size={10} /> Aggiungi sotto-task
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {activeInfoTab === 'monitor' && (
                <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  <AgentWorkMonitor
                    ledger={ledgerState}
                    isLight={isLight}
                    gateReason={gateReason}
                    truncationCount={truncationCount}
                    resumedFrom={resumedFrom}
                    runMetrics={runMetrics}
                    diario={diario}
                    runReport={runReport}
                  />
                </div>
              )}

              {activeInfoTab === 'attivita' && (
                <div style={{ maxHeight: '260px', overflowY: 'auto' }}>
                  <ActivityBar isLight={isLight} inline />
                </div>
              )}
            </div>
          );
        })()}
      </div>

      {/* Sticky Active Execution Bar quando l'agente sta lavorando */}
      {isStreaming && (
        <div style={{
          padding: '6px 12px',
          background: isLight ? 'rgba(0, 112, 243, 0.08)' : 'rgba(0, 242, 254, 0.08)',
          borderBottom: isLight ? '1px solid rgba(0, 112, 243, 0.25)' : '1px solid rgba(0, 242, 254, 0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          flexWrap: 'wrap',
          fontSize: '0.66rem',
          fontWeight: 700,
          color: isLight ? '#0070f3' : '#00f2fe'
        }}>
          {/* Left: Spinner + Agent status & current action */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
            <RefreshCw size={13} className="spin" style={{ flexShrink: 0 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
              <span style={{ fontWeight: 800, whiteSpace: 'nowrap' }}>
                Autocoder:
              </span>
              <span style={{
                color: isLight ? '#24292f' : '#f0f6fc',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {agentStatus || (() => {
                  const runningTask = pipeline.find(p => p.status === 'in_progress') || pipeline.find(p => p.status !== 'done');
                  return runningTask ? `Task in corso: "${runningTask.title}"` : "Elaborazione in corso...";
                })()}
              </span>
            </div>
          </div>

          {/* Right: Disclosed Model & Engine + Live Speed + Stop Button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
            {/* Model Badge */}
            <span
              title={`Modello attualmente in uso: ${selectedModel}`}
              style={{
                fontSize: '0.58rem',
                fontWeight: 800,
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(0, 242, 254, 0.15)',
                border: '1px solid rgba(0, 242, 254, 0.35)',
                color: '#00f2fe',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px'
              }}
            >
              <Cpu size={10} color="#00f2fe" />
              <span>{String(selectedModel || 'sigmaengine').replace(/--/g, '/').split('/').pop().replace(/\.gguf$/i, '')}</span>
            </span>

            {/* Engine Badge */}
            <span
              title="Backend nativo di esecuzione"
              style={{
                fontSize: '0.58rem',
                fontWeight: 800,
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(63, 185, 80, 0.15)',
                border: '1px solid rgba(63, 185, 80, 0.35)',
                color: '#3fb950',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px'
              }}
            >
              <Zap size={10} color="#3fb950" />
              <span>SigmaEngine O(1)</span>
            </span>

            {/* Flash Attention Badge */}
            <span
              title="Flash Attention (FA-2/FA-3) abilitato su GPU: accelerazione calcolo KV-Cache"
              style={{
                fontSize: '0.58rem',
                fontWeight: 800,
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(0, 242, 254, 0.15)',
                border: '1px solid rgba(0, 242, 254, 0.35)',
                color: '#00f2fe',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px'
              }}
            >
              <Zap size={10} color="#00f2fe" />
              <span>FA: ON</span>
            </span>

            {/* Context Window Badge */}
            <span
              title={`Finestra di Contesto allocata: ${contextTokens.toLocaleString()} token`}
              style={{
                fontSize: '0.58rem',
                fontWeight: 800,
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(163, 113, 247, 0.15)',
                border: '1px solid rgba(163, 113, 247, 0.35)',
                color: '#a371f7',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px'
              }}
            >
              <Brain size={10} color="#a371f7" />
              <span>{contextTokens >= 1024 ? `${Math.round(contextTokens / 1024)}K Ctx` : `${contextTokens} tok`}</span>
            </span>

            {/* Live TPS if active */}
            {contextMetrics?.tps != null && contextMetrics.tps > 0 && (
              <span
                style={{
                  fontSize: '0.58rem',
                  fontWeight: 800,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: 'rgba(210, 153, 34, 0.15)',
                  border: '1px solid rgba(210, 153, 34, 0.35)',
                  color: '#d29922'
                }}
              >
                ⚡ {contextMetrics.tps} t/s
              </span>
            )}

            <button
              type="button"
              onClick={stopAutoLoop}
              style={{
                padding: '3px 8px',
                borderRadius: '4px',
                background: '#ef4444',
                color: '#fff',
                border: 'none',
                fontSize: '0.60rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              Ferma Loop
            </button>
          </div>
        </div>
      )}

      {/* Messages List */}
      <div
        ref={messagesContainerRef}
        onWheel={handleWheel}
        onScroll={handleScrollMessages}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          scrollBehavior: 'auto'
        }}
      >
        {/* Paginazione: Carica messaggi precedenti */}
        {messages.length > visibleCount && (
          <div style={{
            textAlign: 'center',
            padding: '8px 0',
            marginBottom: '4px',
            borderBottom: isLight ? '1px dashed #d0d7de' : '1px dashed rgba(255,255,255,0.1)'
          }}>
            <button
              onClick={() => setVisibleCount(prev => prev + 40)}
              style={{
                background: isLight ? 'rgba(0, 112, 243, 0.08)' : 'rgba(0, 242, 254, 0.08)',
                border: isLight ? '1px solid rgba(0, 112, 243, 0.25)' : '1px solid rgba(0, 242, 254, 0.25)',
                color: isLight ? '#0070f3' : '#00f2fe',
                padding: '5px 14px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.70rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Clock size={12} />
              <span>Carica messaggi precedenti (mostrati {visibleMessages.length} di {messages.length})</span>
            </button>
          </div>
        )}

        {visibleMessages.map((msg, idx) => {
          const relatedTaskTitle = msg.resolvedTaskTitle;
          const prevMsg = idx > 0 ? visibleMessages[idx - 1] : null;
          const isConsecutiveAssistant = prevMsg && prevMsg.role === msg.role && msg.role === 'assistant';
          const isSameTask = isConsecutiveAssistant && (prevMsg.resolvedTaskTitle === relatedTaskTitle);
          const showAgentHeader = !isConsecutiveAssistant;
          const showTaskBadge = msg.role === 'assistant' && relatedTaskTitle && (!isConsecutiveAssistant || !isSameTask);

          return (
            <div
              key={msg.originalIndex ?? idx}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: isConsecutiveAssistant ? '3px' : '5px',
                paddingLeft: isConsecutiveAssistant ? '10px' : 0,
                borderLeft: isConsecutiveAssistant
                  ? (isLight ? '2px solid rgba(0, 112, 243, 0.2)' : '2px solid rgba(0, 242, 254, 0.2)')
                  : 'none',
                marginLeft: isConsecutiveAssistant ? '4px' : 0,
                marginTop: isConsecutiveAssistant ? '2px' : (idx > 0 ? '8px' : '2px'),
                marginBottom: isConsecutiveAssistant ? '3px' : '6px'
              }}
            >
              {showAgentHeader && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  color: msg.role === 'user'
                    ? (isAutoLoopPrompt(msg) ? (isLight ? '#6366f1' : '#a78bfa') : '#00f2fe')
                    : (isLight ? '#57606a' : '#8b949e')
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {msg.role === 'user' ? (
                      isAutoLoopPrompt(msg) ? (
                        <Cpu size={12} style={{ color: isLight ? '#6366f1' : '#a78bfa' }} />
                      ) : (
                        <User size={12} />
                      )
                    ) : (
                      <Bot size={12} />
                    )}
                    <span>{msg.role === 'user' ? (isAutoLoopPrompt(msg) ? 'Sistema' : 'Tu') : 'Admin AI Agent'}</span>
                    {msg.role !== 'user' && (
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', marginLeft: '4px' }}>
                        <span
                          title={`Modello usato: ${msg.model || selectedModel}`}
                          style={{
                            fontSize: '0.56rem',
                            fontWeight: 800,
                            padding: '1px 5px',
                            borderRadius: '4px',
                            background: 'rgba(0, 242, 254, 0.12)',
                            border: '1px solid rgba(0, 242, 254, 0.3)',
                            color: '#00f2fe'
                          }}
                        >
                          ⚡ {String(msg.model || selectedModel).replace(/--/g, '/').split('/').pop().replace(/\.gguf$/i, '')}
                        </span>
                        <span
                          title="Backend di inferenza SigmaEngine Rust O(1)"
                          style={{
                            fontSize: '0.54rem',
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: '4px',
                            background: 'rgba(63, 185, 80, 0.12)',
                            border: '1px solid rgba(63, 185, 80, 0.25)',
                            color: '#3fb950'
                          }}
                        >
                          🦀 SigmaEngine O(1)
                        </span>
                      </div>
                    )}
                    {msg.role === 'user' && isAutoLoopPrompt(msg) && (
                      <span style={{
                        fontSize: '0.58rem',
                        padding: '1px 5px',
                        borderRadius: '4px',
                        background: isLight ? 'rgba(99, 102, 241, 0.1)' : 'rgba(167, 139, 250, 0.15)',
                        color: isLight ? '#4f46e5' : '#c4b5fd',
                        fontWeight: 600,
                        marginLeft: '2px'
                      }}>
                        Auto
                      </span>
                    )}
                  </div>
                  <span style={{
                    fontSize: '0.60rem',
                    fontWeight: 500,
                    color: isLight ? '#8c959f' : '#6e7681',
                    fontFamily: 'monospace'
                  }}>
                    {formatMessageTimestamp(msg.timestamp || new Date().toISOString())}
                  </span>
                </div>
              )}

              {/* Badge Identificativo Sotto-Task Corrente (mostrato solo al cambio di task) */}
              {showTaskBadge && (
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  background: isLight ? 'rgba(0, 242, 254, 0.1)' : 'rgba(0, 242, 254, 0.08)',
                  border: '1px solid rgba(0, 242, 254, 0.25)',
                  color: isLight ? '#0070f3' : '#00f2fe',
                  fontSize: '0.64rem',
                  fontWeight: 700,
                  width: 'fit-content',
                  marginTop: '1px',
                  marginBottom: '2px'
                }}>
                  <CircleDot size={11} color="#00f2fe" />
                  <span>Task in corso: {relatedTaskTitle}</span>
                </div>
              )}

              {/* Collapsible Thinking Bubble */}
              {msg.thought && (
                <div style={{
                  borderRadius: '8px',
                  background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
                  border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)',
                  overflow: 'hidden'
                }}>
                  <div
                    onClick={() => toggleThought(idx)}
                    style={{
                      padding: '4px 8px',
                      fontSize: '0.66rem',
                      fontWeight: 700,
                      color: '#8b949e',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      userSelect: 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Brain size={12} color="#00f2fe" />
                      <span>Catena di Ragionamento ({msg.thought.length} caratteri)</span>
                    </div>
                    {expandedThoughts[idx] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </div>

                  {expandedThoughts[idx] && (
                    <div style={{
                      padding: '6px 10px',
                      fontSize: '0.7rem',
                      fontFamily: 'Consolas, monospace',
                      color: isLight ? '#57606a' : '#8b949e',
                      borderTop: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)',
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.4
                    }}>
                      {msg.thought}
                    </div>
                  )}
                </div>
              )}

              {/* Message Bubble Content */}
              {(() => {
                const hasGoalTool = (msg.tools || []).some(t => ['complete_goal', 'finish_task', 'task_complete'].includes(t.tool) && t.result);
                let contentText = msg.role === 'user' ? msg.content : cleanMessageText(msg.content);
                if (hasGoalTool && contentText) {
                  // Quando il tool complete_goal è presente con il suo risultato formattato,
                  // sopprimiamo la duplicazione testuale o la proclamazione grezza dell'obiettivo
                  // nella bolla: la GoalCompletionCard sottostante mostrerà criteri, prove e riepilogo puliti.
                  contentText = contentText.replace(/(?:🏆\s*)?##\s*Obiettivo\s+completato[\s\S]*/i, '').trim();
                  contentText = contentText.replace(/^\s*Obiettivo\s+completato[\s\S]*/i, '').trim();
                  const goalTool = (msg.tools || []).find(t => ['complete_goal', 'finish_task', 'task_complete'].includes(t.tool) && t.result);
                  const toolSummary = goalTool?.result?.summary || goalTool?.result?.message || '';
                  if (toolSummary && contentText.includes(toolSummary.trim().slice(0, 50))) {
                    contentText = '';
                  }
                }
                const showLoadingBanner = msg.isStreaming && msg.role === 'assistant' && !contentText && (!msg.thought || !msg.thought.trim());

                if (!contentText && (!msg.attachments || msg.attachments.length === 0) && !showLoadingBanner) {
                  // Se non c'è testo ma il turno ha registrato token ed è privo di tool visualizzati,
                  // mostriamo un messaggio sobrio indicante l'azione o lo stato
                  if (msg.role === 'assistant' && (!msg.tools || msg.tools.length === 0) && msg.metrics?.tokens > 0 && !msg.isStreaming) {
                    return (
                      <div style={{
                        padding: '4px 8px',
                        borderRadius: '5px',
                        background: isLight ? '#f6f8fa' : '#161b22',
                        border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)',
                        color: isLight ? '#57606a' : '#8b949e',
                        fontSize: '0.66rem',
                        fontStyle: 'italic'
                      }}>
                        {msg.content?.trim() || "Analisi interna completata: passaggio alla fase successiva."}
                      </div>
                    );
                  }
                  return null;
                }
                return (
                  <div>
                    {/* Model Loading / Inference Alert Card */}
                    {showLoadingBanner && (
                      <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        background: isLight ? 'rgba(0, 242, 254, 0.12)' : 'rgba(0, 242, 254, 0.08)',
                        border: '1px solid rgba(0, 242, 254, 0.35)',
                        color: isLight ? '#0070f3' : '#00f2fe',
                        fontSize: '0.74rem',
                        fontWeight: 600,
                        boxShadow: '0 2px 8px rgba(0, 242, 254, 0.15)',
                        marginBottom: '4px'
                      }}>
                        <RefreshCw size={13} className="spin" />
                        <span>{agentStatus || `⏳ Inizializzazione e caricamento pesi modello (${selectedModel})...`}</span>
                      </div>
                    )}

                    {msg.attachments && msg.attachments.length > 0 && (
                      <div style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '5px',
                        marginBottom: contentText ? '6px' : 0
                      }}>
                        {msg.attachments.map((att, attIdx) => (
                          <div
                            key={attIdx}
                            onClick={() => onOpenFile && onOpenFile(att.name || att.path)}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontSize: '0.66rem',
                              fontWeight: 600,
                              background: isLight ? 'rgba(0, 242, 254, 0.15)' : 'rgba(0, 242, 254, 0.1)',
                              border: '1px solid rgba(0, 242, 254, 0.3)',
                              color: isLight ? '#0366d6' : '#00f2fe',
                              cursor: onOpenFile ? 'pointer' : 'default'
                            }}
                            title={att.name || att.path}
                          >
                            <FileText size={11} />
                            <span style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {att.name || att.path}
                            </span>
                            {att.size && (
                              <span style={{ opacity: 0.65, fontSize: '0.60rem' }}>
                                ({(att.size / 1024).toFixed(1)} KB)
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {contentText && (() => {
                      const isGoalCompletion = msg.role === 'assistant' && !hasGoalTool && eBollaObiettivo(contentText);

                      if (isGoalCompletion) {
                        let goalTitle = '';
                        let goalBody = contentText;
                        const titleMatch = contentText.match(/^(?:🏆\s*)?##\s*Obiettivo\s+completato(?:\s*[:—–\-]\s*([^\n]+))?/i) ||
                          contentText.match(/^\s*Obiettivo\s+completato(?:\s*[:—–\-]\s*([^\n]+))?/i);
                        if (titleMatch) {
                          goalTitle = (titleMatch[1] || '').trim();
                          goalBody = contentText.replace(titleMatch[0], '').trim();
                        }
                        return (
                          <GoalCompletionCard
                            title={goalTitle || 'Obiettivo di Sviluppo Raggiunto'}
                            summary={goalBody}
                            isLight={isLight}
                            onOpenFile={onOpenFile}
                          />
                        );
                      }

                      return (
                        <RichMessageContent
                          content={contentText}
                          isUser={msg.role === 'user'}
                          onOpenFile={onOpenFile}
                          isLight={isLight}
                        />
                      );
                    })()}

                    {/* Card Notifica Eccezione / Errore Runtime Esplicito */}
                    {msg.isError && (
                      <div style={{
                        marginTop: '8px',
                        padding: '10px 14px',
                        borderRadius: '8px',
                        background: isLight ? 'rgba(239, 68, 68, 0.08)' : 'rgba(239, 68, 68, 0.12)',
                        border: '1px solid rgba(239, 68, 68, 0.45)',
                        boxShadow: '0 2px 10px rgba(239, 68, 68, 0.15)',
                        fontSize: '0.72rem'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 800, color: '#ef4444', marginBottom: '4px' }}>
                          <AlertTriangle size={15} color="#ef4444" />
                          <span>{msg.errorType ? `Eccezione / Errore Rilevato: ${msg.errorType}` : 'Errore durante l\'elaborazione'}</span>
                        </div>
                        <div style={{ color: isLight ? '#991b1b' : '#fca5a5', lineHeight: 1.45, fontWeight: 500 }}>
                          {msg.errorMessage || 'Si è verificato un errore nel flusso di esecuzione.'}
                        </div>
                        {msg.traceback && (
                          <details style={{ marginTop: '8px', fontSize: '0.66rem' }}>
                            <summary style={{ cursor: 'pointer', fontWeight: 700, color: '#ef4444' }}>
                              Visualizza Dettagli Tecnici & Traceback
                            </summary>
                            <pre style={{
                              margin: '6px 0 0 0',
                              padding: '8px',
                              background: isLight ? '#f8fafc' : '#090d13',
                              border: '1px solid rgba(239, 68, 68, 0.2)',
                              borderRadius: '6px',
                              overflowX: 'auto',
                              fontFamily: 'Consolas, monospace',
                              whiteSpace: 'pre-wrap',
                              color: isLight ? '#334155' : '#94a3b8',
                              lineHeight: 1.35
                            }}>
                              {msg.traceback}
                            </pre>
                          </details>
                        )}
                      </div>
                    )}

                    {/* Card Notifica Rifiuto Completamento Obiettivo (Gate Reason) */}
                    {msg.gateRejected && (
                      <div style={{
                        marginTop: '8px',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        background: isLight ? 'rgba(245, 158, 11, 0.1)' : 'rgba(245, 158, 11, 0.12)',
                        border: '1px solid rgba(245, 158, 11, 0.4)',
                        fontSize: '0.70rem',
                        color: isLight ? '#b45309' : '#fcd34d'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, marginBottom: '2px' }}>
                          <AlertCircle size={14} color="#f59e0b" />
                          <span>Completamento respinto dal sistema di verifica</span>
                        </div>
                        <div style={{ lineHeight: 1.4 }}>
                          {msg.gateReason}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}


              {/* Tool Execution Badges & Sealed Action Alert Cards */}
              {msg.tools && msg.tools.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
                  {msg.tools.map((t, tIdx) => {
                    const isDone = t.status === 'done';
                    const isSuccess = t.result ? t.result.success !== false : true;
                    const hasDiff = !!t.result?.diff;
                    const toolKey = `${idx}_${tIdx}_${t.tool}`;
                    const isExpanded = expandedTools[toolKey] ?? true;

                    return (
                      <div
                        key={tIdx}
                        style={{
                          borderRadius: '6px',
                          background: isLight ? '#ffffff' : '#0d1117',
                          border: isLight
                            ? '1px solid #e1e4e8'
                            : (isDone ? (isSuccess ? '1px solid rgba(63, 185, 80, 0.22)' : '1px solid rgba(239, 68, 68, 0.22)') : '1px solid rgba(0, 242, 254, 0.3)'),
                          overflow: 'hidden',
                          fontSize: '0.67rem',
                          marginBottom: '2px'
                        }}
                      >
                        {/* Action Header Alert Banner (compatto e snello) */}
                        <div
                          onClick={() => toggleTool(toolKey)}
                          style={{
                            padding: '3px 8px',
                            background: isDone
                              ? (isSuccess
                                ? (isLight ? 'rgba(63, 185, 80, 0.06)' : 'rgba(63, 185, 80, 0.06)')
                                : (isLight ? 'rgba(239, 68, 68, 0.06)' : 'rgba(239, 68, 68, 0.06)'))
                              : (isLight ? 'rgba(0, 242, 254, 0.06)' : 'rgba(0, 242, 254, 0.06)'),
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            borderBottom: isExpanded ? (isLight ? '1px solid rgba(0,0,0,0.05)' : '1px solid rgba(255,255,255,0.05)') : 'none',
                            cursor: 'pointer',
                            userSelect: 'none'
                          }}
                        >
                          <span style={{
                            fontWeight: 700,
                            color: isDone ? (isSuccess ? '#3fb950' : '#ef4444') : '#00f2fe',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '5px',
                            fontFamily: 'Consolas, monospace'
                          }}>
                            {t.tool === 'terminal' && <Terminal size={12} />}
                            {t.tool === 'read_file' && <FileCode size={12} />}
                            {t.tool === 'write_file' && <SplitSquareVertical size={12} />}
                            {t.tool === 'edit_file' && <Edit2 size={12} />}
                            {t.tool === 'glob' && <Search size={12} />}
                            {t.tool === 'delete' && <Trash2 size={12} />}
                            {t.tool === 'list_dir' && <Layers size={12} />}
                            {(t.tool === 'search_code' || t.tool === 'grep') && <Search size={12} />}
                            {(t.tool === 'pipeline' || t.tool === 'tasks' || t.tool === 'set_tasks') && <ListTodo size={12} />}
                            {(t.tool === 'complete_goal' || t.tool === 'finish_task') && <Award size={12} />}
                            <span>
                              {t.tool === 'edit_file' ? 'MODIFICA MIRATA FILE' :
                                t.tool === 'glob' ? 'RICERCA FILE PER PATTERN' :
                                  t.tool === 'write_file' ? 'MODIFICA / SCRITTURA FILE' :
                                    t.tool === 'terminal' ? 'ESECUZIONE TERMINALE' :
                                      t.tool === 'delete' ? 'ELIMINAZIONE FILE / CARTELLA' :
                                        t.tool === 'read_file' ? 'LETTURA FILE' :
                                          t.tool === 'list_dir' ? 'ESPLORAZIONE DIRECTORY' :
                                            (t.tool === 'search_code' || t.tool === 'grep') ? 'RICERCA NEL CODICE' :
                                              (t.tool === 'pipeline' || t.tool === 'tasks' || t.tool === 'set_tasks') ? 'AGGIORNAMENTO PIPELINE TASK' :
                                                (t.tool === 'complete_goal' || t.tool === 'finish_task') ? 'OBIETTIVO COMPLETATO' :
                                                  `AZIONE: ${t.tool.toUpperCase()}`}
                            </span>
                          </span>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                            <span style={{
                              fontSize: '0.58rem',
                              padding: '1px 6px',
                              borderRadius: '4px',
                              background: isDone
                                ? (isSuccess ? 'rgba(63, 185, 80, 0.15)' : 'rgba(239, 68, 68, 0.15)')
                                : 'rgba(0, 242, 254, 0.15)',
                              color: isDone ? (isSuccess ? '#3fb950' : '#ef4444') : '#00f2fe',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}>
                              {isDone ? (isSuccess ? '✓ OK' : '✕ Errore') : '⏳ In corso'}
                            </span>
                            {isExpanded ? <ChevronUp size={11} color="#8b949e" /> : <ChevronDown size={11} color="#8b949e" />}
                          </div>
                        </div>

                        {/* Action Details Body */}
                        {isExpanded && (
                          <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {t.params?.command && (
                              <div style={{
                                fontFamily: '"JetBrains Mono", Consolas, monospace',
                                color: '#3fb950',
                                fontSize: '0.68rem',
                                background: isLight ? '#f6f8fa' : '#161b22',
                                padding: '4px 8px',
                                borderRadius: '5px',
                                border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)'
                              }}>
                                $ {t.params.command}
                              </div>
                            )}

                            {t.params?.path && (
                              <div style={{ fontFamily: 'monospace', color: isLight ? '#57606a' : '#8b949e', fontSize: '0.66rem' }}>
                                📂 Percorso: <strong>{t.params.path}</strong>
                              </div>
                            )}

                            {/* Dettagli finestra/righe per lettura file */}
                            {(t.params?.offset || t.params?.start_line || t.params?.limit) && (
                              <div style={{ fontFamily: 'monospace', color: isLight ? '#57606a' : '#8b949e', fontSize: '0.66rem' }}>
                                📑 Righe: <strong>da riga {t.params.offset || t.params.start_line || 1} {t.params.limit ? `(${t.params.limit} righe max)` : ''}</strong>
                              </div>
                            )}

                            {/* Una ricerca senza il termine cercato e' una
                              scheda che dice "ho cercato" e non dice cosa. */}
                            {(t.params?.query || t.params?.pattern) && (
                              <div style={{ fontFamily: 'monospace', color: isLight ? '#57606a' : '#8b949e', fontSize: '0.66rem' }}>
                                🔎 Cerca: <strong>{t.params.query || t.params.pattern}</strong>
                              </div>
                            )}

                            {/* Messaggio o Errore dell'azione */}
                            {(t.result?.error || t.error || t.result?.message) && (
                              <div style={{
                                color: (isSuccess && !t.result?.error && !t.error) ? (isLight ? '#24292f' : '#e6edf3') : '#ef4444',
                                fontSize: '0.68rem',
                                lineHeight: 1.4,
                                marginTop: '4px',
                                padding: (isSuccess && !t.result?.error && !t.error) ? '0' : '5px 8px',
                                borderRadius: '4px',
                                background: (isSuccess && !t.result?.error && !t.error) ? 'transparent' : (isLight ? '#fff1f0' : 'rgba(239, 68, 68, 0.1)'),
                                border: (isSuccess && !t.result?.error && !t.error) ? 'none' : '1px solid rgba(239, 68, 68, 0.25)',
                                fontWeight: (isSuccess && !t.result?.error && !t.error) ? 500 : 600
                              }}>
                                {t.result?.error || t.error || t.result?.message}
                              </div>
                            )}

                            {/* Pipeline Task Preview inside Tool Card */}
                            {(t.tool === 'pipeline' || t.tool === 'tasks' || t.tool === 'set_tasks') && Array.isArray(t.result?.tasks) && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginTop: '4px' }}>
                                {t.result.tasks.map((taskItem, tIdx2) => (
                                  <div key={tIdx2} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.66rem' }}>
                                    {taskItem.status === 'done' ? (
                                      <CheckCircle2 size={12} color="#3fb950" />
                                    ) : taskItem.status === 'in_progress' ? (
                                      <CircleDot size={12} color="#00f2fe" />
                                    ) : (
                                      <Circle size={12} color="#8b949e" />
                                    )}
                                    <span style={{
                                      color: taskItem.status === 'done' ? '#8b949e' : (taskItem.status === 'in_progress' ? '#00f2fe' : (isLight ? '#24292f' : '#e6edf3')),
                                      textDecoration: taskItem.status === 'done' ? 'line-through' : 'none'
                                    }}>
                                      {taskItem.title}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* La chiusura dell'obiettivo si legge come una scheda:
                              riepilogo, criteri e prove, non una pastiglia. */}
                            {(t.tool === 'complete_goal' || t.tool === 'finish_task' || t.tool === 'task_complete') && t.result && (
                              <GoalCompletionCard
                                result={t.result}
                                isLight={isLight}
                                onOpenFile={onOpenFile}
                                mostraRiepilogo={true}
                              />
                            )}

                            {/* Diff Preview & Apply button */}
                            {hasDiff && (
                              <div style={{ marginTop: '6px', borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)', paddingTop: '6px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                                  <span style={{ fontSize: '0.64rem', fontWeight: 700, color: '#00f2fe' }}>
                                    ⚡ Modifiche Proposte nel File
                                  </span>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onApplyDiff?.(t.result.diff, t.result.path, t.result.content);
                                    }}
                                    style={{
                                      padding: '3px 10px',
                                      borderRadius: '5px',
                                      background: '#3fb950',
                                      border: 'none',
                                      color: '#fff',
                                      fontSize: '0.64rem',
                                      fontWeight: 800,
                                      cursor: 'pointer'
                                    }}
                                  >
                                    Visualizza / Applica Diff
                                  </button>
                                </div>
                                <pre style={{
                                  margin: 0,
                                  padding: '6px 8px',
                                  maxHeight: '120px',
                                  overflowY: 'auto',
                                  background: '#07090e',
                                  borderRadius: '4px',
                                  fontSize: '0.64rem',
                                  fontFamily: 'Consolas, monospace',
                                  lineHeight: 1.35
                                }}>
                                  {t.result.diff.split('\n').slice(0, 15).map((line, dIdx) => (
                                    <div key={dIdx} style={{
                                      color: line.startsWith('+') ? '#3fb950' : (line.startsWith('-') ? '#ef4444' : '#8b949e')
                                    }}>
                                      {line}
                                    </div>
                                  ))}
                                </pre>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
              {/* Generation Metrics Bar (t/s, TTFT, Tokens, Duration, Datastamp posizionate sotto le azioni) */}
              {msg.metrics && msg.role === 'assistant' && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.62rem',
                  padding: '3px 4px',
                  color: isLight ? '#57606a' : '#8b949e',
                  flexWrap: 'wrap',
                  marginTop: '2px',
                  marginBottom: isConsecutiveAssistant ? '2px' : '4px'
                }}>
                  {msg.metrics.tps > 0 && (
                    <span style={{
                      color: msg.metrics.isLive ? '#00f2fe' : '#3fb950',
                      fontWeight: 800,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      ⚡ {msg.metrics.tps} t/s
                      {msg.metrics.isLive && (
                        <span style={{
                          display: 'inline-block',
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          background: '#00f2fe',
                          boxShadow: '0 0 6px #00f2fe'
                        }} />
                      )}
                    </span>
                  )}
                  {msg.metrics.speculative_speedup > 1.0 && (
                    <span style={{
                      color: '#34d399',
                      fontWeight: 700,
                      background: 'rgba(16, 185, 129, 0.1)',
                      padding: '1px 5px',
                      borderRadius: '4px',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '3px'
                    }}>
                      🚀 {msg.metrics.speculative_speedup}x Speculative{msg.metrics.speculative_acceptance_rate ? ` (${msg.metrics.speculative_acceptance_rate}%)` : ''}
                    </span>
                  )}
                  {msg.metrics.grammar_constrained && (
                    <span style={{
                      color: '#00f2fe',
                      fontWeight: 700,
                      background: 'rgba(0, 242, 254, 0.08)',
                      padding: '1px 5px',
                      borderRadius: '4px',
                      border: '1px solid rgba(0, 242, 254, 0.22)'
                    }}>
                      JSON-FSM ✓
                    </span>
                  )}
                  {msg.metrics.ttft_ms > 0 && (
                    <span>⏱️ TTFT {msg.metrics.ttft_ms}ms</span>
                  )}
                  {msg.metrics.tokens > 0 && (
                    <span>• {msg.metrics.tokens} tokens</span>
                  )}
                  {msg.metrics.duration_s > 0 && (
                    <span>• {msg.metrics.duration_s}s</span>
                  )}
                  <span style={{ marginLeft: 'auto', opacity: 0.75 }}>
                    🕒 {formatMessageTimestamp(msg.timestamp || new Date().toISOString())}
                  </span>
                </div>
              )}
            </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>

      {/* Quick Prompts */}
      <div style={{
        padding: '6px 10px',
        display: 'flex',
        gap: '4px',
        overflowX: 'auto',
        borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.06)'
      }}>
        {quickPrompts.map(qp => (
          <button
            key={qp.label}
            onClick={() => handleSendMessage(qp.prompt)}
            disabled={isStreaming}
            style={{
              padding: '2px 6px',
              borderRadius: '6px',
              fontSize: '0.62rem',
              fontWeight: 600,
              background: isLight ? '#ffffff' : '#161b22',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.1)',
              color: isLight ? '#24292f' : '#c9d1d9',
              cursor: 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            {qp.label}
          </button>
        ))}
      </div>

      {/* Attached Files Bar (Preview before sending) */}
      {attachedFiles.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
          padding: '6px 10px',
          background: isLight ? '#f0f3f6' : '#0e121a',
          borderTop: isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.06)'
        }}>
          {attachedFiles.map((file) => (
            <div
              key={file.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '3px 8px',
                borderRadius: '6px',
                fontSize: '0.68rem',
                background: isLight ? '#ffffff' : '#1b222d',
                border: '1px solid rgba(0, 242, 254, 0.3)',
                color: isLight ? '#24292f' : '#e6edf3'
              }}
            >
              <FileText size={12} color="#00f2fe" />
              <span style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {file.name}
              </span>
              <span style={{ opacity: 0.6, fontSize: '0.60rem' }}>
                ({(file.size / 1024).toFixed(1)} KB)
              </span>
              <button
                type="button"
                onClick={() => removeAttachedFile(file.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#8b949e',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Live Agent / Engine Status Banner */}
      {isStreaming && (
        <div style={{
          padding: '6px 12px',
          background: isLight ? 'rgba(0, 242, 254, 0.12)' : 'rgba(0, 242, 254, 0.08)',
          borderTop: isLight ? '1px solid rgba(0, 242, 254, 0.25)' : '1px solid rgba(0, 242, 254, 0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.70rem',
          fontWeight: 600,
          color: isLight ? '#0070f3' : '#00f2fe',
          boxShadow: '0 -2px 10px rgba(0, 242, 254, 0.06)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, overflow: 'hidden' }}>
            <RefreshCw size={12} className="spin" />
            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {agentStatus || (
                (() => {
                  const lastMsg = activeTask?.messages?.[activeTask?.messages?.length - 1];
                  if (lastMsg?.metrics?.tps > 0) {
                    return `⚡ Generazione in tempo reale: ${lastMsg.metrics.tps} t/s • ${lastMsg.metrics.tokens} tokens • ${lastMsg.metrics.duration_s}s`;
                  }
                  return "L'agente sta elaborando la risposta...";
                })()
              )}
            </span>
          </div>
          <button
            type="button"
            onClick={handleStopGeneration}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '3px 8px',
              borderRadius: '5px',
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              border: '1px solid #b91c1c',
              color: '#ffffff',
              fontSize: '0.64rem',
              fontWeight: 800,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              boxShadow: '0 2px 6px rgba(239, 68, 68, 0.3)',
              transition: 'all 0.15s ease'
            }}
            title="Ferma immediatamente la generazione"
          >
            <Square size={10} fill="#ffffff" />
            <span>Ferma</span>
          </button>
        </div>
      )}

      {/* Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDropFiles}
        style={{
          padding: '8px 10px',
          borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: isDragOver
            ? (isLight ? 'rgba(0, 242, 254, 0.1)' : 'rgba(0, 242, 254, 0.08)')
            : (isLight ? '#f6f8fa' : '#0a0e14'),
          transition: 'background 0.2s ease'
        }}
      >
        {/* Hidden File Input */}
        <input
          type="file"
          multiple
          ref={fileInputRef}
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {/* Paperclip / Attach File Button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          title="Allega file (testo, codice, configurazioni)"
          style={{
            padding: '6px 8px',
            borderRadius: '8px',
            background: attachedFiles.length > 0 ? 'rgba(0, 242, 254, 0.2)' : (isLight ? '#ffffff' : '#161b22'),
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
            color: attachedFiles.length > 0 ? '#00f2fe' : (isLight ? '#57606a' : '#8b949e'),
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.15s ease'
          }}
        >
          <Paperclip size={14} />
        </button>

        {/* Microphone / Speech-to-Text Button */}
        <button
          type="button"
          onClick={toggleVoiceInput}
          title={isListening ? "Ferma registrazione vocale" : "Dettatura vocale (Microfono)"}
          style={{
            padding: '6px 8px',
            borderRadius: '8px',
            background: isListening
              ? 'rgba(239, 68, 68, 0.25)'
              : (isLight ? '#ffffff' : '#161b22'),
            border: isListening
              ? '1px solid rgba(239, 68, 68, 0.5)'
              : (isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)'),
            color: isListening ? '#ef4444' : (isLight ? '#57606a' : '#8b949e'),
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.15s ease'
          }}
        >
          {isListening ? <MicOff size={14} /> : <Mic size={14} />}
        </button>

        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={
            isListening
              ? "🎤 Ascolto in corso..."
              : isStreaming
                ? "Scrivi un'istruzione per intervenire nel loop (premi Invio per inviare)..."
                : loopCountdown !== null
                  ? `Loop in corso (${loopCountdown}s)... Scrivi un'istruzione per indirizzare l'agente...`
                  : "Chiedi all'AI Developer Agent... (puoi allegare o trascinare file)"
          }
          style={{
            flex: 1,
            padding: '6px 10px',
            borderRadius: '8px',
            fontSize: '0.74rem',
            background: isLight ? '#ffffff' : '#161b22',
            border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
            color: isLight ? '#24292f' : '#f0f6fc',
            outline: 'none'
          }}
        />

        {/* Pulsante Ferma Loop (visibile sempre durante lo streaming o il countdown) */}
        {(isStreaming || loopCountdown !== null) && (
          <button
            type="button"
            onClick={handleStopGeneration}
            title="Ferma il loop e l'elaborazione dell'agente"
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              border: '1px solid #b91c1c',
              color: '#ffffff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontWeight: 800,
              fontSize: '0.72rem',
              boxShadow: '0 2px 10px rgba(239, 68, 68, 0.45)',
              transition: 'all 0.15s ease',
              whiteSpace: 'nowrap'
            }}
          >
            <Square size={12} fill="#ffffff" />
            <span>Ferma Loop</span>
          </button>
        )}

        {/* Pulsante Invia: sempre accessibile, abilitato se c'è testo o file da inviare */}
        <button
          type="submit"
          disabled={!input.trim() && attachedFiles.length === 0}
          title={
            isStreaming
              ? "Intervieni subito e invia la nuova istruzione all'agente"
              : loopCountdown !== null
                ? "Invia subito l'istruzione e avvia il task"
                : "Invia messaggio all'agente"
          }
          style={{
            padding: '6px 14px',
            borderRadius: '8px',
            background: (input.trim() || attachedFiles.length > 0)
              ? 'linear-gradient(135deg, #00f2fe, #4facfe)'
              : (isLight ? '#e1e4e8' : '#21262d'),
            border: 'none',
            color: (input.trim() || attachedFiles.length > 0) ? '#000000' : '#8b949e',
            cursor: (input.trim() || attachedFiles.length > 0) ? 'pointer' : 'default',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            fontWeight: 700,
            fontSize: '0.72rem',
            transition: 'all 0.15s ease',
            whiteSpace: 'nowrap'
          }}
        >
          <Send size={13} />
          <span>Invia</span>
        </button>
      </form>

      <style>{`
        .dev-chat-md {
          line-height: 1.6;
          color: #e6edf3;
        }
        .dev-chat-md.light-mode {
          color: #24292f;
        }
        .dev-chat-md h1 {
          font-size: 1.05rem;
          font-weight: 800;
          color: #00f2fe;
          margin: 12px 0 6px 0;
          border-bottom: 1px solid rgba(0, 242, 254, 0.25);
          padding-bottom: 4px;
        }
        .dev-chat-md h2 {
          font-size: 0.94rem;
          font-weight: 700;
          color: #38bdf8;
          margin: 10px 0 4px 0;
          border-bottom: 1px solid rgba(56, 189, 248, 0.15);
          padding-bottom: 3px;
        }
        .dev-chat-md h3 {
          font-size: 0.86rem;
          font-weight: 700;
          color: #7dd3fc;
          margin: 8px 0 3px 0;
        }
        .dev-chat-md h4 {
          font-size: 0.78rem;
          font-weight: 700;
          color: #bae6fd;
          margin: 6px 0 2px 0;
        }
        .dev-chat-md p {
          margin: 6px 0;
        }
        .dev-chat-md ul, .dev-chat-md ol {
          margin: 6px 0 6px 18px;
          padding: 0;
        }
        .dev-chat-md li {
          margin: 2px 0;
        }
        .dev-chat-md blockquote {
          border-left: 3px solid #00f2fe;
          background: rgba(0, 242, 254, 0.05);
          padding: 6px 12px;
          margin: 8px 0;
          border-radius: 0 6px 6px 0;
          color: #94a3b8;
          font-style: italic;
        }
        .dev-chat-md hr {
          border: none;
          height: 1px;
          background: linear-gradient(90deg, transparent, rgba(0, 242, 254, 0.3), transparent);
          margin: 12px 0;
        }
        .dev-chat-md .chat-table-wrapper {
          margin: 10px 0;
          overflow-x: auto;
          border-radius: 8px;
          border: 1px solid rgba(0, 242, 254, 0.25);
          background: #090d13;
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
        }
        .dev-chat-md table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.72rem;
        }
        .dev-chat-md th {
          background: linear-gradient(135deg, rgba(0, 242, 254, 0.15), rgba(124, 91, 240, 0.12));
          color: #00f2fe;
          padding: 8px 12px;
          font-weight: 700;
          text-align: left;
          border-bottom: 1px solid rgba(0, 242, 254, 0.3);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-size: 0.66rem;
        }
        .dev-chat-md td {
          padding: 7px 12px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          color: #d1d5db;
        }
        .dev-chat-md tr:nth-child(even) td {
          background: rgba(255, 255, 255, 0.02);
        }
        .dev-chat-md tr:hover td {
          background: rgba(0, 242, 254, 0.06);
        }
        .dev-chat-md pre {
          background: #0b0f17 !important;
          border: 1px solid rgba(0, 242, 254, 0.2) !important;
          border-radius: 8px !important;
          padding: 12px 14px !important;
          margin: 8px 0 !important;
          overflow-x: auto !important;
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25) !important;
        }
        .dev-chat-md pre code {
          background: transparent !important;
          padding: 0 !important;
          font-family: 'JetBrains Mono', Consolas, monospace !important;
          font-size: 0.72rem !important;
          color: #e6edf3 !important;
        }
        .dev-chat-md code:not(pre code) {
          background: rgba(0, 242, 254, 0.1) !important;
          color: #00f2fe !important;
          padding: 1px 5px !important;
          border-radius: 4px !important;
          font-family: 'JetBrains Mono', Consolas, monospace !important;
          font-size: 0.72rem !important;
          border: 1px solid rgba(0, 242, 254, 0.2) !important;
        }
        .dev-chat-md .chat-file-link {
          color: #00f2fe;
          text-decoration: underline;
          text-underline-offset: 3px;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.15s ease;
        }
        .dev-chat-md .chat-file-link:hover {
          color: #ffffff;
          text-shadow: 0 0 10px rgba(0, 242, 254, 0.5);
        }
        .dev-chat-md .katex-display {
          padding: 8px 12px;
          margin: 8px 0;
          background: rgba(11, 15, 23, 0.7);
          border-radius: 8px;
          border: 1px solid rgba(0, 242, 254, 0.2);
          overflow-x: auto;
        }
      `}</style>

      {/* Modale di Gestione Docker aperta dal widget nella Header */}
      <DockerViewerModal
        isOpen={showDockerModal}
        onClose={() => setShowDockerModal(false)}
        isLight={isLight}
        onSelectContainer={(cid) => {
          if (onOpenFile) {
            onOpenFile(`docker://${cid}/`);
          }
          setShowDockerModal(false);
        }}
      />
    </div>
  );
}
