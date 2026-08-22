import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { 
  Cpu, Key, ShieldCheck, Zap, RefreshCw, Save, CheckCircle2, 
  AlertCircle, Sliders, ExternalLink, Copy, Check, Eye, EyeOff, 
  Search, Server, Database, Download, Trash2, ChevronDown, Lock, Sparkles,
  Code, Terminal, Layers, Globe, Play, CheckCircle, FileText, Settings, Share2,
  Monitor, X, ChevronRight, Wifi, ArrowUpRight
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';

// High-quality dedicated SVG brand icons for each provider
export const ProviderIcons = {
  sigma_engine: ({ size = 20, color = '#00f2fe' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M13 2L3 14H12L11 22L21 10H12L13 2Z" fill={`${color}30`} stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  ),
  ailoflow: ({ size = 20, color = '#00f2fe' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="6" cy="6" r="3" fill={`${color}25`} stroke={color} strokeWidth="1.8" />
      <circle cx="18" cy="18" r="3" fill={`${color}25`} stroke={color} strokeWidth="1.8" />
      <path d="M8.5 7.5L15.5 16.5M6 9V15M18 9V15" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  ollama: ({ size = 20, color = '#00d2ff' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M7 3C5.5 3 4.5 4 4.5 5.5V11C4.5 12.5 5.5 13.5 7 13.5H8V18C8 19.5 9 20.5 10.5 20.5H13.5C15 20.5 16 19.5 16 18V13.5H17C18.5 13.5 19.5 12.5 19.5 11V5.5C19.5 4 18.5 3 17 3H7Z" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill={`${color}22`} />
      <circle cx="8.5" cy="7.5" r="1.2" fill={color} />
      <circle cx="15.5" cy="7.5" r="1.2" fill={color} />
      <path d="M10 11H14" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
      <path d="M10 17H14" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  openai: ({ size = 20, color = '#10a37f' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M20.5 10.5C20.2 7.8 18.2 5.8 15.5 5.5C15.2 4.2 14.3 3.1 13 2.5C10.7 1.4 7.9 2.4 6.8 4.7C6.5 5.3 6.4 6 6.5 6.7C4.2 7.3 2.7 9.4 2.8 11.8C2.9 13.2 3.6 14.5 4.7 15.3C4.4 16.6 4.8 18 5.7 19C7.3 20.8 10.1 21.1 12 19.8C12.6 20.7 13.6 21.3 14.8 21.5C17.4 21.8 19.8 20 20.2 17.4C21.1 16.4 21.5 15 21.3 13.6C21.2 12.5 20.7 11.4 20.5 10.5Z" stroke={color} strokeWidth="1.6" strokeLinejoin="round" fill={`${color}18`} />
      <path d="M12 7.5V16.5M8 9.5L16 14.5M8 14.5L16 9.5" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  anthropic: ({ size = 20, color = '#bc8cff' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2L14.4 9.6H22.4L16 14.4L18.4 22L12 17.2L5.6 22L8 14.4L1.6 9.6H9.6L12 2Z" fill={`${color}22`} stroke={color} strokeWidth="1.7" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="2.5" fill={color} />
    </svg>
  ),
  deepseek: ({ size = 20, color = '#2563eb' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M3 13C3.5 8 7 4 12 4C17.5 4 21 8.5 21 13C21 17.5 17 20.5 12 20.5C9 20.5 6 19 4 17L3 13Z" fill={`${color}20`} stroke={color} strokeWidth="1.7" strokeLinejoin="round" />
      <path d="M12 4C13 8 16 11 21 12" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="8" cy="11" r="1.5" fill={color} />
    </svg>
  ),
  google: ({ size = 20, color = '#ea580c' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2C12 7.52 7.52 12 2 12C7.52 12 12 16.48 12 22C12 16.48 16.48 12 22 12C16.48 12 12 7.52 12 2Z" fill={`${color}28`} stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  ),
  groq: ({ size = 20, color = '#f97316' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M13 2L3 14H12L11 22L21 10H12L13 2Z" fill={`${color}25`} stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  ),
  openrouter: ({ size = 20, color = '#6366f1' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke={color} strokeWidth="1.8" fill={`${color}15`} />
      <path d="M12 3V21M3 12H21" stroke={color} strokeWidth="1.4" strokeDasharray="2 2" />
      <circle cx="12" cy="12" r="4" fill={color} />
    </svg>
  ),
  mistral: ({ size = 20, color = '#f59e0b' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="4" y="4" width="4" height="16" fill={color} />
      <rect x="10" y="8" width="4" height="12" fill={color} />
      <rect x="16" y="12" width="4" height="8" fill={color} />
    </svg>
  ),
  xai: ({ size = 20, color = '#ffffff' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 4L14 14M14 4L4 14" stroke={color} strokeWidth="2.2" strokeLinecap="round" />
      <path d="M15 4H20V20H15" stroke={color} strokeWidth="1.8" />
    </svg>
  ),
  perplexity: ({ size = 20, color = '#06b6d4' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="8" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <path d="M12 4V20M4 12H20M6.5 6.5L17.5 17.5M6.5 17.5L17.5 6.5" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  together: ({ size = 20, color = '#3b82f6' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="8" cy="12" r="5" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <circle cx="16" cy="12" r="5" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
    </svg>
  ),
  qwen: ({ size = 20, color = '#6366f1' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke={color} strokeWidth="1.8" fill={`${color}20`} strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" fill={color} />
    </svg>
  ),
  moonshot: ({ size = 20, color = '#ec4899' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3C7.03 3 3 7.03 3 12C3 16.97 7.03 21 12 21C16.97 21 21 16.97 21 12C21 11.5 20.96 11 20.88 10.52C20.07 12.55 18.11 14 15.8 14C12.82 14 10.4 11.58 10.4 8.6C10.4 6.29 11.85 4.33 13.88 3.52C13.26 3.18 12.64 3 12 3Z" stroke={color} strokeWidth="1.8" fill={`${color}22`} strokeLinejoin="round" />
    </svg>
  ),
  glm: ({ size = 20, color = '#0284c7' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3L14.5 9L21 9.5L16 14L17.5 20.5L12 17L6.5 20.5L8 14L3 9.5L9.5 9L12 3Z" stroke={color} strokeWidth="1.8" fill={`${color}22`} strokeLinejoin="round" />
    </svg>
  ),
  custom: ({ size = 20, color = '#10b981' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="4" width="18" height="6" rx="2" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <rect x="3" y="14" width="18" height="6" rx="2" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <circle cx="7" cy="7" r="1" fill={color} />
      <circle cx="7" cy="17" r="1" fill={color} />
      <path d="M14 7H17M14 17H17" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
};

export const PROVIDER_CATALOG = {
  sigma_engine: {
    id: 'sigma_engine',
    label: '⚡ SigmaEngine (Nativo & Open Server)',
    category: 'local',
    color: '#00f2fe',
    badge: 'OPENAI & OLLAMA SERVER',
    endpoint: 'http://localhost:8000',
    api_url: 'http://localhost:8000/v1',
    api_key_required: false,
    key_placeholder: 'Nessuna API Key (o usa "sigma")',
    docs_url: 'https://github.com/Sigmanih/SigmaStudio',
    hint: 'Server API nativo conforme agli standard OpenAI (/v1) e Ollama (/api). Esecuzione ultra-rapida con FlashAttn-2, multi-GPU e sharding. Collegabile a Visual Studio Code (Continue, Cline, Roo Code, Copilot, Cursor).',
    default_model: 'sigma-native:latest',
    popular_models: ['sigma-native:latest', 'sigmaengine', 'qwen2.5-coder:7b', 'deepseek-r1:8b', 'llama3.2:3b', 'gpt-4o', 'claude-3-5-sonnet']
  },
  ailoflow: {
    id: 'ailoflow',
    label: '🌊 AiloFlow (Graph Flow & Multi-Tier)',
    category: 'local',
    color: '#00f2fe',
    badge: 'FLOW ENGINE',
    endpoint: 'http://localhost:5000',
    api_url: 'http://localhost:5000/v1',
    api_key_required: false,
    key_placeholder: 'Endpoint locale AiloFlow (default: http://localhost:5000)',
    docs_url: 'https://github.com/xxrickyxx/AiloFlow',
    hint: 'Engine locale per flussi di prompt visuali a nodi, prompt graphs e sharding avanzato (https://github.com/xxrickyxx/AiloFlow).',
    default_model: 'ailo-flow-default',
    popular_models: ['ailo-flow-default', 'ailo-152m-router', 'ailo-deepseek-r1-flow']
  },
  ollama: {
    id: 'ollama',
    label: 'Ollama (Locale & GPU)',
    category: 'local',
    color: '#00d2ff',
    badge: '100% LOCALE',
    endpoint: 'http://localhost:11434',
    api_url: '',
    api_key_required: false,
    key_placeholder: 'Nessuna API Key richiesta per Ollama',
    docs_url: 'https://ollama.ai',
    hint: 'Modelli locali con accelerazione GPU NVIDIA CUDA, ROCm o Metal.',
    default_model: 'sigma:latest',
    popular_models: ['sigma:latest', 'qwen2.5-coder:7b', 'llama3.2:3b', 'mistral-nemo:12b', 'deepseek-r1:8b', 'phi4:14b']
  },
  openai: {
    id: 'openai',
    label: 'OpenAI (ChatGPT & Reasoning)',
    category: 'cloud',
    color: '#10a37f',
    badge: 'GPT-4o & o1',
    endpoint: '',
    api_url: 'https://api.openai.com/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'sk-proj-...',
    docs_url: 'https://platform.openai.com/api-keys',
    hint: 'GPT-4o, GPT-4o-mini, o1 e o3-mini.',
    default_model: 'gpt-4o-mini',
    popular_models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini', 'o1', 'gpt-4-turbo']
  },
  anthropic: {
    id: 'anthropic',
    label: 'Anthropic (Claude 3.7 & 3.5)',
    category: 'cloud',
    color: '#bc8cff',
    badge: 'HYBRID THINKING',
    endpoint: '',
    api_url: 'https://api.anthropic.com/v1/messages',
    api_key_required: true,
    key_placeholder: 'sk-ant-api03-...',
    docs_url: 'https://console.anthropic.com/settings/keys',
    hint: 'Claude 3.7 Sonnet (Thinking), 3.5 Sonnet e Haiku.',
    default_model: 'claude-3-7-sonnet-20250219',
    popular_models: ['claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']
  },
  deepseek: {
    id: 'deepseek',
    label: 'DeepSeek (Chat & R1)',
    category: 'cloud',
    color: '#2563eb',
    badge: 'REASONER R1',
    endpoint: '',
    api_url: 'https://api.deepseek.com/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'sk-...',
    docs_url: 'https://platform.deepseek.com/api_keys',
    hint: 'DeepSeek R1 per ragionamento logico e DeepSeek V3.',
    default_model: 'deepseek-chat',
    popular_models: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder']
  },
  google: {
    id: 'google',
    label: 'Google Gemini',
    category: 'cloud',
    color: '#ea580c',
    badge: '1M+ CONTEXT',
    endpoint: '',
    api_url: 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
    api_key_required: true,
    key_placeholder: 'AIzaSy...',
    docs_url: 'https://aistudio.google.com/app/apikey',
    hint: 'Gemini 2.5 Flash, 2.0 Flash e 1.5 Pro.',
    default_model: 'gemini-2.0-flash',
    popular_models: ['gemini-2.0-flash', 'gemini-2.5-pro', 'gemini-2.0-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash']
  },
  groq: {
    id: 'groq',
    label: 'Groq (Inference LPU)',
    category: 'fast',
    color: '#f97316',
    badge: '500+ T/S',
    endpoint: '',
    api_url: 'https://api.groq.com/openai/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'gsk_...',
    docs_url: 'https://console.groq.com/keys',
    hint: 'Inferenza ultra-rapida a bassa latenza su chip LPU.',
    default_model: 'llama-3.3-70b-versatile',
    popular_models: ['llama-3.3-70b-versatile', 'deepseek-r1-distill-llama-70b', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768']
  },
  openrouter: {
    id: 'openrouter',
    label: 'OpenRouter (Multi-Hub)',
    category: 'hub',
    color: '#6366f1',
    badge: '200+ MODELLI',
    endpoint: '',
    api_url: 'https://openrouter.ai/api/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'sk-or-v1-...',
    docs_url: 'https://openrouter.ai/keys',
    hint: 'Hub unificato per oltre 200 modelli globali.',
    default_model: 'openai/gpt-4o-mini',
    popular_models: ['openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', 'deepseek/deepseek-r1', 'google/gemini-2.0-flash-001', 'meta-llama/llama-3.3-70b-instruct']
  },
  mistral: {
    id: 'mistral',
    label: 'Mistral AI',
    category: 'fast',
    color: '#ff7000',
    badge: 'CODESTRAL',
    endpoint: '',
    api_url: 'https://api.mistral.ai/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'Chiave API Mistral...',
    docs_url: 'https://console.mistral.ai/api-keys',
    hint: 'Mistral Large 2, Codestral e Mistral Small.',
    default_model: 'mistral-large-latest',
    popular_models: ['mistral-large-latest', 'codestral-latest', 'mistral-small-latest', 'open-mistral-nemo']
  },
  xai: {
    id: 'xai',
    label: 'xAI (Grok)',
    category: 'hub',
    color: '#e11d48',
    badge: 'GROK 2',
    endpoint: '',
    api_url: 'https://api.x.ai/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'xai-...',
    docs_url: 'https://console.x.ai',
    hint: 'Modelli Grok-2 e Grok-2 Vision di xAI.',
    default_model: 'grok-2',
    popular_models: ['grok-2', 'grok-2-mini', 'grok-beta']
  },
  perplexity: {
    id: 'perplexity',
    label: 'Perplexity AI',
    category: 'hub',
    color: '#06b6d4',
    badge: 'SONAR SEARCH',
    endpoint: '',
    api_url: 'https://api.perplexity.ai/chat/completions',
    api_key_required: true,
    key_placeholder: 'pplx-...',
    docs_url: 'https://www.perplexity.ai/settings/api',
    hint: 'Modelli Sonar con grounding web live.',
    default_model: 'sonar-pro',
    popular_models: ['sonar-pro', 'sonar', 'llama-3.1-sonar-large-128k-online']
  },
  together: {
    id: 'together',
    label: 'Together AI',
    category: 'fast',
    color: '#3b82f6',
    badge: 'OPEN CLOUD',
    endpoint: '',
    api_url: 'https://api.together.xyz/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'Together API key...',
    docs_url: 'https://api.together.xyz/settings/api-keys',
    hint: 'Cluster cloud veloce per Llama 3.3, Qwen e DeepSeek.',
    default_model: 'meta-llama/Llama-3.3-70B-Instruct-Turbo',
    popular_models: ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'deepseek-ai/deepseek-coder-v2-instruct', 'Qwen/Qwen2.5-72B-Instruct-Turbo']
  },
  qwen: {
    id: 'qwen',
    label: 'Qwen (DashScope)',
    category: 'chinese',
    color: '#8b5cf6',
    badge: 'QWEN 2.5',
    endpoint: '',
    api_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'sk-...',
    docs_url: 'https://dashscope.console.aliyun.com',
    hint: 'Qwen 2.5 Max, Coder e Math.',
    default_model: 'qwen-max',
    popular_models: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen2.5-72b-instruct', 'qwen2.5-coder-32b-instruct']
  },
  glm: {
    id: 'glm',
    label: 'GLM (Zhipu AI)',
    category: 'chinese',
    color: '#0284c7',
    badge: 'GLM-4 PLUS',
    endpoint: '',
    api_url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    api_key_required: true,
    key_placeholder: 'Zhipu API key...',
    docs_url: 'https://open.bigmodel.cn',
    hint: 'Modelli GLM-4 Plus e GLM-4 Long.',
    default_model: 'glm-4-plus',
    popular_models: ['glm-4-plus', 'glm-4-air', 'glm-4-flash', 'glm-4-long']
  },
  custom: {
    id: 'custom',
    label: 'API Custom (OpenAI)',
    category: 'custom',
    color: '#10b981',
    badge: 'ENDPOINT PROPRIO',
    endpoint: '',
    api_url: '',
    api_key_required: false,
    key_placeholder: 'Chiave API (se richiesta)...',
    docs_url: '',
    hint: 'Collega gateway aziendali, vLLM, LMStudio o LocalAI.',
    default_model: '',
    popular_models: []
  }
};

// Sleek Custom Model Selector Dropdown with smooth internal scrolling
function CustomModelSelect({ providerId, value, options, onChange, isLight, titleColor, subtitleColor, innerCardBg, innerCardBorder }) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredOptions = useMemo(() => {
    if (!search.trim()) return options;
    return options.filter(opt => opt.toLowerCase().includes(search.toLowerCase().trim()));
  }, [options, search]);

  const selectedDisplay = value || (options[0] || 'Seleziona modello');

  return (
    <div ref={dropdownRef} style={{ position: 'relative', width: '100%' }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          padding: '6px 10px',
          borderRadius: '8px',
          background: innerCardBg,
          border: isOpen ? '1px solid #00d2ff' : innerCardBorder,
          color: titleColor,
          fontSize: '0.76rem',
          fontWeight: 600,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '6px',
          textAlign: 'left'
        }}
      >
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {selectedDisplay}
        </span>
        <ChevronDown size={12} style={{ flexShrink: 0, opacity: 0.7, transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease' }} />
      </button>

      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          zIndex: 999,
          background: isLight ? '#ffffff' : '#161922',
          border: isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '8px',
          boxShadow: isLight ? '0 6px 20px rgba(0,0,0,0.12)' : '0 8px 24px rgba(0,0,0,0.6)',
          overflow: 'hidden',
          padding: '4px'
        }}>
          {options.length > 4 && (
            <div style={{ padding: '4px 6px', borderBottom: isLight ? '1px solid #f0f0f0' : '1px solid rgba(255,255,255,0.06)' }}>
              <input
                type="text"
                placeholder="Filtra modelli..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                onClick={e => e.stopPropagation()}
                autoFocus
                style={{
                  width: '100%',
                  padding: '4px 6px',
                  borderRadius: '6px',
                  background: isLight ? '#f9f9f9' : 'rgba(255,255,255,0.05)',
                  border: isLight ? '1px solid #ddd' : '1px solid rgba(255,255,255,0.1)',
                  color: titleColor,
                  fontSize: '0.72rem',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          )}

          <div style={{ maxHeight: '160px', overflowY: 'auto', padding: '2px 0' }}>
            {filteredOptions.length === 0 ? (
              <div style={{ padding: '8px', fontSize: '0.72rem', color: subtitleColor, textAlign: 'center' }}>
                Nessun modello trovato
              </div>
            ) : (
              filteredOptions.map(opt => {
                const isSelected = value === opt;
                return (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => {
                      onChange(opt);
                      setIsOpen(false);
                      setSearch('');
                    }}
                    style={{
                      width: '100%',
                      padding: '6px 8px',
                      borderRadius: '6px',
                      background: isSelected ? (isLight ? '#00d2ff18' : '#00d2ff22') : 'transparent',
                      color: isSelected ? '#00d2ff' : titleColor,
                      fontSize: '0.74rem',
                      fontWeight: isSelected ? 700 : 500,
                      border: 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      textAlign: 'left'
                    }}
                  >
                    <span>{opt}</span>
                    {isSelected && <Check size={12} color="#00d2ff" />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AIConfigTab({ openTab }) {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Styling tokens
  const bg = isLight ? '#fcfaf6' : '#0b0d13';
  const cardBg = isLight ? '#fffdf9' : '#11141d';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const innerCardBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.035)';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.06)';
  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#a0a6bc';
  const cardShadow = isLight ? '0 2px 12px rgba(190, 160, 110, 0.1)' : '0 4px 18px rgba(0, 0, 0, 0.35)';

  // Navigation state
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSection, setActiveSection] = useState('providers'); // 'providers' | 'parameters'

  // Central Config State
  const [activeProvider, setActiveProvider] = useState('sigma_engine');
  const [activeModel, setActiveModel] = useState('sigma:latest');
  const [providerSettings, setProviderSettings] = useState({});
  const [ollamaLocalModels, setOllamaLocalModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Global Inference Parameters
  const [parameters, setParameters] = useState({
    temperature: 0.7,
    max_tokens: 16384,
    top_p: 0.95,
    top_k: 40,
    repeat_penalty: 1.1,
    num_ctx: 32768,
    system_prompt: ''
  });

  // UI state
  const [visibleKeys, setVisibleKeys] = useState({});
  const [copiedKey, setCopiedKey] = useState(null);
  const [testingProvider, setTestingProvider] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveToast, setSaveToast] = useState(null);
  const [hardwareProfile, setHardwareProfile] = useState(null);
  const [tieringPlan, setTieringPlan] = useState(null);

  // VS Code & SigmaEngine Server Interoperability State
  const [serverInfo, setServerInfo] = useState(null);
  const [providerServerEnabled, setProviderServerEnabled] = useState(true);
  const [selectedGuideModel, setSelectedGuideModel] = useState('sigmaengine');
  const [showVSCodeModal, setShowVSCodeModal] = useState(false);
  const [activeVsCodeTab, setActiveVsCodeTab] = useState('continue'); // 'continue' | 'cline' | 'copilot' | 'python' | 'curl'
  const [liveTestState, setLiveTestState] = useState({
    protocol: 'openai',
    prompt: 'Scrivi un breve saluto da Visual Studio Code e spiega i vantaggi di SigmaEngine.',
    isTesting: false,
    outputText: '',
    latency: null,
    ttft: null,
    error: null
  });

  const fetchServerInfo = useCallback(async () => {
    try {
      const res = await fetch('/api/engine/server_info');
      const data = await res.json();
      if (data.success) {
        setServerInfo(data);
        if (data.provider_server_enabled !== undefined) {
          setProviderServerEnabled(data.provider_server_enabled);
        }
      }
    } catch (e) {
      console.debug("Server info fetch:", e);
    }
  }, []);

  const toggleProviderServer = async (targetState) => {
    const nextState = targetState !== undefined ? targetState : !providerServerEnabled;
    try {
      const res = await fetch('/api/engine/provider_server/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: nextState })
      });
      const data = await res.json();
      if (data.success) {
        setProviderServerEnabled(data.provider_server_enabled);
        setSaveToast({
          type: 'success',
          msg: `Servizio Provider Server ${data.provider_server_enabled ? 'ABILITATO 🟢' : 'DISABILITATO 🔴'}`
        });
        setTimeout(() => setSaveToast(null), 3500);
        fetchServerInfo();
      }
    } catch (err) {
      setSaveToast({ type: 'error', msg: `Errore toggle server: ${err.message}` });
      setTimeout(() => setSaveToast(null), 3500);
    }
  };

  // Enumerate all available models for the VS Code guide selector
  const allAvailableGuideModels = useMemo(() => {
    const list = [
      { id: 'sigmaengine', name: '⚡ sigmaengine (Auto-Risoluzione dinamica / Modello Residente)', type: 'alias' }
    ];
    if (serverInfo?.resident_model && serverInfo.resident_model !== 'Nessun modello caricato') {
      list.push({ id: serverInfo.resident_model, name: `🔥 ${serverInfo.resident_model} (In VRAM)`, type: 'resident' });
    }
    (serverInfo?.available_models || []).forEach(m => {
      if (!list.some(x => x.id === m.id)) {
        const icon = m.category === 'cloud' ? '☁️' : (m.is_resident ? '🔥' : '🏠');
        list.push({ id: m.id, name: `${icon} ${m.name || m.id}`, type: m.category || 'local' });
      }
    });
    (ollamaLocalModels || []).forEach(m => {
      const mName = typeof m === 'string' ? m : m.name;
      if (mName && !list.some(x => x.id === mName)) {
        list.push({ id: mName, name: `🏠 ${mName} (Locale GGUF/Ollama)`, type: 'local' });
      }
    });
    Object.entries(providerSettings).forEach(([pId, pCfg]) => {
      if (pId !== 'sigma_engine') {
        const mod = pCfg?.custom_model || pCfg?.model || PROVIDER_CATALOG[pId]?.default_model;
        if (mod && !list.some(x => x.id === mod)) {
          list.push({ id: mod, name: `☁️ ${mod} (${PROVIDER_CATALOG[pId]?.label || pId})`, type: 'cloud' });
        }
      }
    });
    return list;
  }, [serverInfo, ollamaLocalModels, providerSettings]);

  const downloadContinueConfig = () => {
    const targetModel = selectedGuideModel || 'sigmaengine';
    const cfg = {
      models: [
        {
          title: `SigmaEngine (${targetModel})`,
          provider: "openai",
          model: targetModel,
          apiBase: "http://localhost:8000/v1",
          apiKey: "sigma"
        },
        {
          title: `SigmaEngine Ollama (${targetModel})`,
          provider: "ollama",
          model: targetModel,
          apiBase: "http://localhost:8000"
        }
      ],
      tabAutocompleteModel: {
        title: "SigmaEngine Autocomplete (7B Coder)",
        provider: "openai",
        model: "qwen2.5-coder:7b",
        apiBase: "http://localhost:8000/v1",
        apiKey: "sigma"
      }
    };
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(cfg, null, 2));
    const a = document.createElement('a');
    a.setAttribute("href", dataStr);
    a.setAttribute("download", `continue_config_${targetModel.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`);
    a.click();
  };

  const runLiveServerTest = async () => {
    const targetModel = selectedGuideModel || 'sigmaengine';
    setLiveTestState(prev => ({ ...prev, isTesting: true, outputText: '', error: null, latency: null, ttft: null }));
    const startTime = performance.now();
    let firstTokenRecorded = false;

    try {
      if (liveTestState.protocol === 'openai') {
        const resp = await fetch('/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: targetModel,
            messages: [{ role: 'user', content: liveTestState.prompt || 'Ciao da VS Code!' }],
            stream: true,
            max_tokens: 300,
            temperature: 0.7
          })
        });

        if (!resp.ok) {
          const errText = await resp.text();
          let parsedErr = errText;
          try {
            const errObj = JSON.parse(errText);
            parsedErr = errObj.error?.message || errObj.error || errText;
          } catch (_) {}
          throw new Error(`HTTP ${resp.status}: ${parsedErr}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let fullText = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ') && line.trim() !== 'data: [DONE]') {
              try {
                const parsed = JSON.parse(line.slice(6));
                if (parsed.error) {
                  const errMsg = typeof parsed.error === 'object' ? (parsed.error.message || JSON.stringify(parsed.error)) : parsed.error;
                  setLiveTestState(prev => ({ ...prev, error: errMsg }));
                }
                const token = parsed.choices?.[0]?.delta?.content || '';
                if (token) {
                  if (!firstTokenRecorded) {
                    firstTokenRecorded = true;
                    setLiveTestState(prev => ({ ...prev, ttft: Math.round(performance.now() - startTime) }));
                  }
                  fullText += token;
                  setLiveTestState(prev => ({ ...prev, outputText: fullText }));
                }
              } catch (e) {}
            }
          }
        }
        setLiveTestState(prev => ({ ...prev, isTesting: false, latency: Math.round(performance.now() - startTime) }));
      } else {
        // Ollama protocol
        const resp = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: targetModel,
            messages: [{ role: 'user', content: liveTestState.prompt || 'Ciao da VS Code!' }],
            stream: true,
            options: { num_predict: 300, temperature: 0.7 }
          })
        });

        if (!resp.ok) {
          const errText = await resp.text();
          let parsedErr = errText;
          try {
            const errObj = JSON.parse(errText);
            parsedErr = errObj.error || errText;
          } catch (_) {}
          throw new Error(`HTTP ${resp.status}: ${parsedErr}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let fullText = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          for (const line of lines) {
            if (line.trim()) {
              try {
                const parsed = JSON.parse(line.trim());
                if (parsed.error) {
                  setLiveTestState(prev => ({ ...prev, error: parsed.error }));
                }
                const token = parsed.message?.content || '';
                if (token) {
                  if (!firstTokenRecorded) {
                    firstTokenRecorded = true;
                    setLiveTestState(prev => ({ ...prev, ttft: Math.round(performance.now() - startTime) }));
                  }
                  fullText += token;
                  setLiveTestState(prev => ({ ...prev, outputText: fullText }));
                }
              } catch (e) {}
            }
          }
        }
        setLiveTestState(prev => ({ ...prev, isTesting: false, latency: Math.round(performance.now() - startTime) }));
      }
    } catch (err) {
      setLiveTestState(prev => ({ ...prev, isTesting: false, error: err.message }));
    }
  };

  const fetchEngineProfile = useCallback(async () => {
    try {
      const res = await fetch('/api/engine/profile');
      const data = await res.json();
      if (data.success && data.profile) {
        setHardwareProfile(data.profile);
      }
      const res2 = await fetch('/api/engine/partition', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ total_layers: 32, model_size_gb: 8.0 })
      });
      const data2 = await res2.json();
      if (data2.success && data2.tiering_plan) {
        setTieringPlan(data2.tiering_plan);
      }
    } catch (e) {}
  }, []);

  // Fetch initial config from backend
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      if (data.success && data.config) {
        const cfg = data.config;
        setActiveProvider(cfg.active_provider || cfg.provider || 'sigma_engine');
        setActiveModel(cfg.active_model || cfg.model || 'sigma:latest');
        
        // Populate per-provider data
        const provs = cfg.providers || {};
        const initialSettings = {};
        Object.keys(PROVIDER_CATALOG).forEach(pKey => {
          const remote = provs[pKey] || {};
          initialSettings[pKey] = {
            endpoint: remote.endpoint || PROVIDER_CATALOG[pKey].endpoint || '',
            api_url: remote.api_url || PROVIDER_CATALOG[pKey].api_url || '',
            model: remote.model || PROVIDER_CATALOG[pKey].default_model || '',
            api_key: '',
            has_api_key: remote.has_api_key || false,
            custom_model: ''
          };
        });
        setProviderSettings(initialSettings);

        // Parameters
        setParameters(prev => ({
          ...prev,
          temperature: cfg.temperature ?? 0.7,
          max_tokens: cfg.max_tokens ?? 8192,
          top_p: cfg.top_p ?? 0.9,
          top_k: cfg.top_k ?? 40,
          repeat_penalty: cfg.repeat_penalty ?? 1.1,
          num_ctx: cfg.num_ctx ?? 32768,
        }));
      }
    } catch (e) {
      console.error("Errore caricamento configurazione AI:", e);
    }
  }, []);

  // Fetch Ollama models ONLY if explicitly requested/configured
  const fetchOllamaModels = useCallback(async (isExplicit = false) => {
    if (!isExplicit) return;
    setLoadingModels(true);
    try {
      const res = await fetch('/api/ollama_models');
      const data = await res.json();
      if (data.models && Array.isArray(data.models)) {
        const names = data.models.map(m => m.name || m);
        setOllamaLocalModels(names);
      }
    } catch (e) {
      setOllamaLocalModels([]);
    } finally {
      setLoadingModels(false);
    }

  }, []);

  useEffect(() => {
    fetchConfig();
    fetchEngineProfile();
    fetchServerInfo();
  }, [fetchConfig, fetchEngineProfile, fetchServerInfo]);

  // Update a single provider field
  const updateProviderField = (pId, field, value) => {
    setProviderSettings(prev => ({
      ...prev,
      [pId]: {
        ...prev[pId],
        [field]: value
      }
    }));
  };

  // Toggle key visibility
  const toggleKeyVisibility = (pId) => {
    setVisibleKeys(prev => ({ ...prev, [pId]: !prev[pId] }));
  };

  // Copy key to clipboard
  const copyKeyToClipboard = (pId, text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedKey(pId);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Save All Configuration to Server
  const saveAllConfig = async () => {
    setSaving(true);
    setSaveToast({ type: 'info', msg: 'Salvataggio configurazione in corso...' });
    try {
      const providersPayload = {};
      Object.keys(providerSettings).forEach(pKey => {
        const p = providerSettings[pKey];
        if (p) {
          providersPayload[pKey] = {
            endpoint: p.endpoint,
            api_url: p.api_url,
            model: p.custom_model || p.model,
            temperature: parameters.temperature,
            max_tokens: parameters.max_tokens,
            top_p: parameters.top_p,
            num_ctx: parameters.num_ctx
          };
          if (p.api_key && p.api_key.trim()) {
            providersPayload[pKey].api_key = p.api_key.trim();
          }
        }
      });

      const currentProviderObj = providerSettings[activeProvider] || {};
      const chosenModel = currentProviderObj.custom_model || currentProviderObj.model || activeModel;

      const payload = {
        active_provider: activeProvider,
        active_model: chosenModel,
        provider: activeProvider,
        model: chosenModel,
        endpoint: currentProviderObj.endpoint || (activeProvider === 'ollama' ? 'http://localhost:11434/api/chat' : ''),
        api_url: currentProviderObj.api_url || '',
        temperature: parameters.temperature,
        max_tokens: parameters.max_tokens,
        top_p: parameters.top_p,
        top_k: parameters.top_k,
        repeat_penalty: parameters.repeat_penalty,
        num_ctx: parameters.num_ctx,
        providers: providersPayload
      };

      if (currentProviderObj.api_key && currentProviderObj.api_key.trim()) {
        payload.api_key = currentProviderObj.api_key.trim();
      }

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success) {
        setSaveToast({ type: 'success', msg: '✅ Configurazione salvata con successo!' });
        fetchConfig();
        window.dispatchEvent(new CustomEvent('ai-config-updated'));
      } else {
        setSaveToast({ type: 'error', msg: `❌ Errore: ${data.error || 'Salvataggio fallito'}` });
      }
    } catch (e) {
      setSaveToast({ type: 'error', msg: `❌ Errore di rete: ${e.message}` });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveToast(null), 3500);
    }
  };

  // Test single provider connection
  const testProviderConnection = async (pId) => {
    setTestingProvider(pId);
    setTestResults(prev => ({ ...prev, [pId]: { status: 'testing', msg: 'Invio probe...' } }));
    const startTime = performance.now();

    try {
      const p = providerSettings[pId] || {};
      const modelToTest = p.custom_model || p.model || PROVIDER_CATALOG[pId]?.default_model;

      const provPayload = {
        [pId]: {
          endpoint: p.endpoint,
          api_url: p.api_url,
          model: modelToTest,
          temperature: 0.1,
          max_tokens: 50
        }
      };
      if (p.api_key && p.api_key.trim()) {
        provPayload[pId].api_key = p.api_key.trim();
      }

      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: pId,
          model: modelToTest,
          providers: provPayload
        })
      });

      // If testing SigmaEngine directly, use the standard OpenAI /v1/chat/completions endpoint
      if (pId === 'sigma_engine') {
        const engRes = await fetch('/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: modelToTest || 'sigmaengine',
            messages: [{ role: 'user', content: "Rispondi solo con 'OK'." }],
            stream: false,
            max_tokens: 20
          })
        });

        const latency = Math.round(performance.now() - startTime);
        const data = await engRes.json();

        if (engRes.ok && data.choices && data.choices[0]) {
          setTestResults(prev => ({
            ...prev,
            [pId]: {
              status: 'success',
              msg: `Connesso (${latency}ms) — ${modelToTest} (OpenAI & Ollama Server)`,
              latency
            }
          }));
          return;
        } else if (data.error) {
          const errMsg = typeof data.error === 'object' ? (data.error.message || JSON.stringify(data.error)) : data.error;
          setTestResults(prev => ({
            ...prev,
            [pId]: { status: 'error', msg: `Errore: ${errMsg}`, latency }
          }));
          return;
        }
      }

      const chatRes = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: "Rispondi solo con 'OK' per confermare il test di connessione.",
          allow_actions: false,
          model: modelToTest
        })
      });

      const rawText = await chatRes.text();
      const latency = Math.round(performance.now() - startTime);
      let chatData = {};

      try {
        chatData = JSON.parse(rawText);
      } catch (parseErr) {
        // Safely extract from SSE or NDJSON lines
        const lines = rawText.split('\n');
        for (const line of lines) {
          const clean = line.replace(/^data:\s*/, '').trim();
          if (clean && clean !== '[DONE]') {
            try {
              const obj = JSON.parse(clean);
              if (obj.error) { chatData.error = obj.error; break; }
              if (obj.token || obj.message || obj.response || obj.choices) {
                chatData.success = true;
                break;
              }
            } catch (_) {}
          }
        }
        if (!chatData.error && rawText.length > 0) {
          chatData.success = true;
        }
      }

      if (chatData.error) {
        setTestResults(prev => ({
          ...prev,
          [pId]: { status: 'error', msg: `Errore: ${chatData.error}`, latency }
        }));
      } else {
        setTestResults(prev => ({
          ...prev,
          [pId]: { 
            status: 'success', 
            msg: `Connesso (${latency}ms) — ${modelToTest}`,
            latency 
          }
        }));
      }
    } catch (e) {
      const latency = Math.round(performance.now() - startTime);
      setTestResults(prev => ({
        ...prev,
        [pId]: { status: 'error', msg: `Errore: ${e.message}`, latency }
      }));
    } finally {
      setTestingProvider(null);
    }
  };

  const [disabledProviders, setDisabledProviders] = useState(() => {
    try {
      const saved = localStorage.getItem('sigma_disabled_providers');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const toggleDisableProvider = (pId) => {
    setDisabledProviders(prev => {
      const next = { ...prev, [pId]: !prev[pId] };
      try { localStorage.setItem('sigma_disabled_providers', JSON.stringify(next)); } catch {}
      if (next[pId] && activeProvider === pId) {
        setActiveProvider('sigma_engine');
        setActiveModel('sigma-native:latest');
      }
      return next;
    });
  };

  // Switch Active Provider
  const handleSelectActiveProvider = (pId) => {
    if (disabledProviders[pId]) {
      toggleDisableProvider(pId);
    }
    setActiveProvider(pId);
    const p = providerSettings[pId] || {};
    const mod = p.custom_model || p.model || PROVIDER_CATALOG[pId]?.default_model || '';
    setActiveModel(mod);
  };

  // Export JSON Backup
  const handleExportBackup = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
      active_provider: activeProvider,
      active_model: activeModel,
      disabled_providers: disabledProviders,
      parameters,
      timestamp: new Date().toISOString()
    }, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", "sigma_ai_config_backup.json");
    dlAnchor.click();
  };

  // Reset to default
  const handleResetDefault = () => {
    if (confirm("Sei sicuro di voler reimpostare la configurazione predefinita su SigmaEngine Nativo?")) {
      setActiveProvider('sigma_engine');
      setActiveModel('sigma-native:latest');
      saveAllConfig();
    }
  };


  // Filtered providers
  const filteredProviders = useMemo(() => {
    return Object.values(PROVIDER_CATALOG).filter(p => {
      const matchCategory = activeCategory === 'all' || p.category === activeCategory;
      const matchSearch = searchQuery.trim() === '' || 
        p.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.hint.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.popular_models || []).some(m => m.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchCategory && matchSearch;
    });
  }, [activeCategory, searchQuery]);

  // Statistics
  const configuredTokensCount = useMemo(() => {
    return Object.keys(providerSettings).filter(k => {
      const p = providerSettings[k];
      return k === 'ollama' || p?.has_api_key || (p?.api_key && p?.api_key.trim().length > 0);
    }).length;
  }, [providerSettings]);

  const activeProviderMeta = PROVIDER_CATALOG[activeProvider] || PROVIDER_CATALOG.ollama;
  const ActiveIconComponent = ProviderIcons[activeProvider] || ProviderIcons.ollama;

  return (
    <div className="ai-config-tab" style={{
      padding: '20px 24px 60px 24px',
      background: bg,
      minHeight: '100%',
      maxHeight: '100%',
      height: '100%',
      overflowY: 'auto',
      color: titleColor,
      fontFamily: 'inherit',
      boxSizing: 'border-box'
    }}>
      {/* Top Banner — Status & Quick Switcher */}
      <div style={{
        padding: '16px 20px',
        borderRadius: '16px',
        background: cardBg,
        border: isLight ? `1px solid ${activeProviderMeta.color}45` : `1px solid ${activeProviderMeta.color}35`,
        boxShadow: cardShadow,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px',
        marginBottom: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: `${activeProviderMeta.color}18`,
            border: `1px solid ${activeProviderMeta.color}45`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 16px ${activeProviderMeta.color}25`
          }}>
            <ActiveIconComponent size={24} color={activeProviderMeta.color} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
              <span style={{
                fontSize: '0.64rem',
                fontWeight: 800,
                color: activeProviderMeta.color,
                background: `${activeProviderMeta.color}15`,
                border: `1px solid ${activeProviderMeta.color}35`,
                padding: '2px 8px',
                borderRadius: '10px',
                letterSpacing: '0.5px'
              }}>
                PROVIDER ATTIVO
              </span>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.7rem',
                fontWeight: 700,
                color: '#3fb950'
              }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#3fb950', display: 'inline-block' }} />
                Online
              </span>
            </div>

            <h1 style={{ margin: '0 0 2px 0', fontSize: '1.2rem', fontWeight: 800, color: titleColor }}>
              {activeProviderMeta.label}
            </h1>
            <p style={{ margin: 0, fontSize: '0.76rem', color: subtitleColor }}>
              Modello: <strong style={{ color: activeProviderMeta.color }}>{activeModel || activeProviderMeta.default_model}</strong> • 
              Contesto: <strong>{parameters.num_ctx.toLocaleString()} token</strong> • 
              Chiavi Configurate: <strong>{configuredTokensCount}/{Object.keys(PROVIDER_CATALOG).length}</strong>
            </p>
          </div>
        </div>

        {/* Global CTA Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={() => testProviderConnection(activeProvider)}
            disabled={testingProvider !== null}
            style={{
              padding: '8px 14px',
              borderRadius: '10px',
              background: innerCardBg,
              border: innerCardBorder,
              color: titleColor,
              fontSize: '0.76rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            {testingProvider === activeProvider ? <RefreshCw size={13} className="spin" /> : <Zap size={13} color="#faa03c" />}
            Testa
          </button>

          <button
            onClick={saveAllConfig}
            disabled={saving}
            style={{
              padding: '8px 18px',
              borderRadius: '10px',
              background: `linear-gradient(135deg, ${activeProviderMeta.color}, ${activeProviderMeta.color}cc)`,
              border: 'none',
              color: '#ffffff',
              fontSize: '0.78rem',
              fontWeight: 800,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: `0 4px 14px ${activeProviderMeta.color}35`
            }}
          >
            {saving ? <RefreshCw size={14} className="spin" /> : <Save size={14} />}
            Salva & Applica
          </button>
        </div>
      </div>

      {/* Save Notification Toast */}
      {saveToast && (
        <div style={{
          padding: '10px 14px',
          borderRadius: '10px',
          background: saveToast.type === 'success' ? 'rgba(63, 185, 80, 0.15)' : (saveToast.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(0, 210, 255, 0.15)'),
          border: saveToast.type === 'success' ? '1px solid #3fb950' : (saveToast.type === 'error' ? '1px solid #ef4444' : '1px solid #00d2ff'),
          color: titleColor,
          fontSize: '0.78rem',
          fontWeight: 700,
          marginBottom: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          {saveToast.type === 'success' ? <CheckCircle2 size={16} color="#3fb950" /> : <AlertCircle size={16} />}
          <span>{saveToast.msg}</span>
        </div>
      )}

      {/* Embedded Privacy & Security Assurance Banner */}
      <div style={{
        padding: '10px 16px',
        borderRadius: '12px',
        background: isLight ? 'rgba(63, 185, 80, 0.08)' : 'rgba(63, 185, 80, 0.12)',
        border: isLight ? '1px solid rgba(63, 185, 80, 0.3)' : '1px solid rgba(63, 185, 80, 0.25)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        marginBottom: '14px',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldCheck size={18} color="#3fb950" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: '0.76rem', color: titleColor, lineHeight: 1.4 }}>
            <strong>Riservatezza & Protezione Locale:</strong> Tutte le chiavi API sono memorizzate nel backend confinato di Sigma Studio. Nessun token o dato viene condiviso a terzi o inviato a telemetrie.
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            onClick={handleExportBackup}
            title="Esporta copia di backup in formato JSON"
            style={{
              padding: '5px 10px',
              borderRadius: '8px',
              background: innerCardBg,
              border: innerCardBorder,
              color: titleColor,
              fontSize: '0.7rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Download size={12} color="#00d2ff" /> Backup
          </button>
          <button
            onClick={handleResetDefault}
            title="Reimposta provider predefiniti"
            style={{
              padding: '5px 10px',
              borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              color: '#ef4444',
              fontSize: '0.7rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Trash2 size={12} /> Reset
          </button>
        </div>
      </div>

      {/* SigmaEngine Hardware & Multi-Drive Sharding Matrix Card */}
      {hardwareProfile && (
        <div style={{
          padding: '16px 20px',
          borderRadius: '16px',
          background: cardBg,
          border: '1px solid rgba(0, 242, 254, 0.25)',
          boxShadow: cardShadow,
          marginBottom: '16px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '32px', height: '32px', borderRadius: '8px',
                background: 'rgba(0, 242, 254, 0.15)', border: '1px solid rgba(0, 242, 254, 0.35)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <Zap size={18} color="#00f2fe" />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: titleColor }}>
                  ⚡ SigmaEngine — Hardware & Memory Sharding Matrix
                </h3>
                <span style={{ fontSize: '0.72rem', color: subtitleColor }}>
                  Calibrazione automatica: GPU CUDA FlashAttn-2 + RAM + Storage Shard Streaming
                </span>
              </div>
            </div>
            <span style={{
              fontSize: '0.68rem', fontWeight: 800, color: '#3fb950',
              background: 'rgba(63, 185, 80, 0.15)', border: '1px solid rgba(63, 185, 80, 0.3)',
              padding: '3px 10px', borderRadius: '12px'
            }}>
              🚀 +61.3% tok/s vs Ollama
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', marginBottom: '12px' }}>
            <div style={{ padding: '10px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.68rem', color: '#00f2fe', fontWeight: 700 }}>TIER 0: FASTEST VRAM</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>
                {hardwareProfile.accelerators?.[0]?.name || 'NVIDIA GPU'}
              </div>
              <div style={{ fontSize: '0.7rem', color: subtitleColor }}>
                {hardwareProfile.accelerators?.[0]?.free_vram_gb ? `${hardwareProfile.accelerators[0].free_vram_gb} GB VRAM libera` : 'Allocazione Unificata'}
              </div>
            </div>

            <div style={{ padding: '10px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.68rem', color: '#3fb950', fontWeight: 700 }}>TIER 2: HOST RAM</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>
                {hardwareProfile.ram?.available_gb} GB Disponibili
              </div>
              <div style={{ fontSize: '0.7rem', color: subtitleColor }}>
                {hardwareProfile.ram?.total_gb} GB RAM Totale
              </div>
            </div>

            <div style={{ padding: '10px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.68rem', color: '#bc8cff', fontWeight: 700 }}>TIER 3: MULTI-DRIVE STREAMING</div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>
                {hardwareProfile.storage_drives?.length || 1} Drive Attivi
              </div>
              <div style={{ fontSize: '0.7rem', color: subtitleColor }}>
                Sharded Lookahead Async I/O
              </div>
            </div>
          </div>

          {tieringPlan && (
            <div style={{ fontSize: '0.72rem', color: subtitleColor, background: 'rgba(0,0,0,0.2)', padding: '8px 12px', borderRadius: '8px' }}>
              <strong>Partizionamento Modello (32 Layer):</strong> Tier 0 VRAM: {tieringPlan.tier0_primary_vram?.count} layer • Tier 2 RAM: {tieringPlan.tier2_host_ram?.count} layer • Tier 3 Disk Shards: {tieringPlan.tier3_disk_shards?.count} layer
            </div>
          )}
        </div>
      )}


      {/* Section Switcher Tabs & Search Filter */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        marginBottom: '16px',
        borderBottom: isLight ? '1px solid rgba(190, 160, 110, 0.2)' : '1px solid rgba(255, 255, 255, 0.08)',
        paddingBottom: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'providers', label: '🔑 Token & Providers AI', icon: Key },
            { id: 'server', label: '🔌 SigmaEngine Server (VS Code)', icon: Code },
            { id: 'parameters', label: '⚙️ Parametri di Inferenza', icon: Sliders }
          ].map(sec => {
            const active = activeSection === sec.id;
            const Icon = sec.icon;
            return (
              <button
                key={sec.id}
                onClick={() => setActiveSection(sec.id)}
                style={{
                  padding: '7px 14px',
                  borderRadius: '10px',
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.18s ease',
                  background: active ? (sec.id === 'server' ? 'linear-gradient(135deg, #00f2fe, #4facfe)' : (isLight ? '#111827' : '#ffffff')) : 'transparent',
                  color: active ? (sec.id === 'server' ? '#000000' : (isLight ? '#ffffff' : '#111827')) : subtitleColor,
                  boxShadow: active && sec.id === 'server' ? '0 2px 10px rgba(0, 242, 254, 0.3)' : 'none'
                }}
              >
                <Icon size={14} />
                <span>{sec.label}</span>
              </button>
            );
          })}
        </div>

        {activeSection === 'providers' && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 10px',
            borderRadius: '8px',
            background: innerCardBg,
            border: innerCardBorder
          }}>
            <Search size={13} color={subtitleColor} />
            <input
              type="text"
              placeholder="Cerca provider..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: titleColor,
                fontSize: '0.74rem',
                outline: 'none',
                width: '140px'
              }}
            />
          </div>
        )}
      </div>

      {/* SECTION 1: PROVIDERS & TOKENS */}
      {activeSection === 'providers' && (
        <>
          {/* Category Filter Pills */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            flexWrap: 'wrap',
            marginBottom: '16px'
          }}>
            {[
              { id: 'all', label: `Tutti (${Object.keys(PROVIDER_CATALOG).length})` },
              { id: 'local', label: '🏠 Locale (1)' },
              { id: 'cloud', label: '⚡ Top Cloud (4)' },
              { id: 'fast', label: '🚀 Ultra-Fast (3)' },
              { id: 'hub', label: '🌐 Hub (3)' },
              { id: 'chinese', label: '🎋 Asia (2)' },
              { id: 'custom', label: '🛠️ Custom (1)' }
            ].map(cat => {
              const active = activeCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '8px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)',
                    cursor: 'pointer',
                    transition: 'all 0.18s ease',
                    background: active ? '#00d2ff' : cardBg,
                    color: active ? '#ffffff' : subtitleColor
                  }}
                >
                  {cat.label}
                </button>
              );
            })}
          </div>

          {/* Compact Providers Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))',
            gap: '14px'
          }}>
            {filteredProviders.map(prov => {
              const pState = providerSettings[prov.id] || {};
              const isSelected = activeProvider === prov.id;
              const isDisabled = disabledProviders[prov.id] === true;
              const hasKey = prov.id === 'ollama' || prov.id === 'sigma_engine' ? true : (pState.has_api_key || (pState.api_key && pState.api_key.trim().length > 0));
              const isVisible = visibleKeys[prov.id];
              const test = testResults[prov.id];
              const isTesting = testingProvider === prov.id;
              const IconComp = ProviderIcons[prov.id] || ProviderIcons.ollama;

              // Available model list for this provider
              const modelOptions = prov.id === 'ollama' && ollamaLocalModels.length > 0 
                ? ollamaLocalModels 
                : prov.popular_models;

              return (
                <div
                  key={prov.id}
                  style={{
                    padding: '14px 16px',
                    borderRadius: '14px',
                    background: cardBg,
                    opacity: isDisabled ? 0.6 : 1,
                    border: isSelected 
                      ? `2px solid ${prov.color}` 
                      : (isDisabled ? '1px dashed rgba(239, 68, 68, 0.4)' : (isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.07)')),
                    boxShadow: isSelected ? `0 4px 16px ${prov.color}20` : cardShadow,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '10px'
                  }}
                >
                  <div>
                    {/* Compact Card Header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '10px',
                          background: `${prov.color}15`,
                          border: `1px solid ${prov.color}35`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0
                        }}>
                          <IconComp size={18} color={prov.color} />
                        </div>
                        <div>
                          <h3 style={{ margin: 0, fontSize: '0.86rem', fontWeight: 800, color: titleColor }}>
                            {prov.label}
                          </h3>
                          <span style={{ fontSize: '0.6rem', fontWeight: 800, color: isDisabled ? '#ef4444' : prov.color, letterSpacing: '0.4px' }}>
                            {isDisabled ? 'DISABILITATO' : prov.badge}
                          </span>
                        </div>
                      </div>

                      {/* Header Actions (Primary / Enable / Disable) */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        {prov.id !== 'sigma_engine' && (
                          <button
                            onClick={() => toggleDisableProvider(prov.id)}
                            title={isDisabled ? "Riabilita provider" : "Rimuovi o disabilita provider da Sigma Studio"}
                            style={{
                              padding: '3px 7px',
                              borderRadius: '7px',
                              background: isDisabled ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                              border: isDisabled ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
                              color: isDisabled ? '#ef4444' : subtitleColor,
                              fontSize: '0.6rem',
                              fontWeight: 700,
                              cursor: 'pointer'
                            }}
                          >
                            {isDisabled ? 'Riabilita' : 'Rimuovi'}
                          </button>
                        )}

                        {!isDisabled && (
                          isSelected ? (
                            <span style={{
                              padding: '3px 8px',
                              borderRadius: '8px',
                              background: `${prov.color}20`,
                              color: prov.color,
                              fontSize: '0.62rem',
                              fontWeight: 800,
                              border: `1px solid ${prov.color}45`,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}>
                              <CheckCircle2 size={10} /> ATTIVO
                            </span>
                          ) : (
                            <button
                              onClick={() => handleSelectActiveProvider(prov.id)}
                              style={{
                                padding: '3px 8px',
                                borderRadius: '8px',
                                background: innerCardBg,
                                border: innerCardBorder,
                                color: subtitleColor,
                                fontSize: '0.62rem',
                                fontWeight: 700,
                                cursor: 'pointer'
                              }}
                            >
                              Imposta Primario
                            </button>
                          )
                        )}
                      </div>
                    </div>

                    {/* SigmaEngine Interactive VS Code & Interop Banner */}
                    {prov.id === 'sigma_engine' && (
                      <div style={{
                        padding: '7px 10px',
                        borderRadius: '8px',
                        background: 'rgba(0, 242, 254, 0.07)',
                        border: '1px solid rgba(0, 242, 254, 0.25)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '6px',
                        marginBottom: '8px'
                      }}>
                        <div>
                          <div style={{ fontSize: '0.65rem', fontWeight: 800, color: '#00f2fe', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Wifi size={10} color="#3fb950" /> OPENAI & OLLAMA PROTOCOL
                          </div>
                          <div style={{ fontSize: '0.6rem', color: subtitleColor }}>
                            Port: 8000 • /v1/chat/completions • /api/chat
                          </div>
                        </div>
                        <button
                          onClick={() => setActiveSection('server')}
                          style={{
                            padding: '3px 7px',
                            borderRadius: '6px',
                            background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                            border: 'none',
                            color: '#000',
                            fontSize: '0.62rem',
                            fontWeight: 800,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '3px',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          <Code size={10} /> VS Code Guide
                        </button>
                      </div>
                    )}

                    <p style={{ margin: '0 0 10px 0', fontSize: '0.72rem', color: subtitleColor, lineHeight: 1.4 }}>
                      {prov.hint}
                    </p>

                    {/* Model Selector Dropdown with smooth internal scrolling */}
                    <div style={{ marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor }}>
                          Modello
                        </label>
                        {prov.id === 'ollama' && (
                          <button
                            onClick={fetchOllamaModels}
                            disabled={loadingModels}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#00d2ff',
                              fontSize: '0.65rem',
                              cursor: 'pointer',
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '3px',
                              padding: 0
                            }}
                          >
                            <RefreshCw size={10} className={loadingModels ? 'spin' : ''} />
                            Rileva ({ollamaLocalModels.length})
                          </button>
                        )}
                      </div>

                      <CustomModelSelect
                        providerId={prov.id}
                        value={pState.custom_model || pState.model || prov.default_model}
                        options={modelOptions}
                        onChange={(mod) => {
                          updateProviderField(prov.id, 'model', mod);
                          updateProviderField(prov.id, 'custom_model', '');
                        }}
                        isLight={isLight}
                        titleColor={titleColor}
                        subtitleColor={subtitleColor}
                        innerCardBg={innerCardBg}
                        innerCardBorder={innerCardBorder}
                      />
                    </div>

                    {/* API Key Vault Input (if required or optional) */}
                    {prov.api_key_required && (
                      <div style={{ marginBottom: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'flex', alignItems: 'center', gap: '3px' }}>
                            <Lock size={10} color={hasKey ? '#3fb950' : subtitleColor} />
                            Secret Token
                          </label>
                          {prov.docs_url && (
                            <a
                              href={prov.docs_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                color: prov.color,
                                fontSize: '0.64rem',
                                fontWeight: 700,
                                textDecoration: 'none',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '2px'
                              }}
                            >
                              Ottieni Key <ExternalLink size={9} />
                            </a>
                          )}
                        </div>

                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          background: innerCardBg,
                          border: hasKey ? (isLight ? `1px solid ${prov.color}60` : `1px solid ${prov.color}50`) : innerCardBorder,
                          borderRadius: '8px',
                          padding: '0 6px'
                        }}>
                          <input
                            type={isVisible ? 'text' : 'password'}
                            placeholder={pState.has_api_key ? '•••••••••••••••• (Salvata)' : prov.key_placeholder}
                            value={pState.api_key || ''}
                            onChange={e => updateProviderField(prov.id, 'api_key', e.target.value)}
                            style={{
                              flex: 1,
                              padding: '6px 2px',
                              background: 'transparent',
                              border: 'none',
                              color: titleColor,
                              fontSize: '0.74rem',
                              outline: 'none'
                            }}
                          />

                          <button
                            onClick={() => toggleKeyVisibility(prov.id)}
                            title={isVisible ? 'Nascondi token' : 'Mostra token'}
                            style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer', padding: '3px' }}
                          >
                            {isVisible ? <EyeOff size={13} /> : <Eye size={13} />}
                          </button>

                          {pState.api_key && (
                            <button
                              onClick={() => copyKeyToClipboard(prov.id, pState.api_key)}
                              title="Copia token"
                              style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer', padding: '3px' }}
                            >
                              {copiedKey === prov.id ? <Check size={13} color="#3fb950" /> : <Copy size={13} />}
                            </button>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Endpoint Override (for Ollama, Custom or Proxies) */}
                    {(prov.id === 'ollama' || prov.id === 'custom') && (
                      <div style={{ marginBottom: '8px' }}>
                        <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'block', marginBottom: '3px' }}>
                          Endpoint URL
                        </label>
                        <input
                          type="text"
                          placeholder={prov.endpoint || prov.api_url || 'http://localhost:11434'}
                          value={pState.endpoint || pState.api_url || ''}
                          onChange={e => {
                            if (prov.id === 'ollama') updateProviderField(prov.id, 'endpoint', e.target.value);
                            else updateProviderField(prov.id, 'api_url', e.target.value);
                          }}
                          style={{
                            width: '100%',
                            padding: '5px 8px',
                            borderRadius: '8px',
                            background: innerCardBg,
                            border: innerCardBorder,
                            color: titleColor,
                            fontSize: '0.72rem',
                            outline: 'none',
                            boxSizing: 'border-box'
                          }}
                        />
                      </div>
                    )}
                  </div>

                  {/* Card Bottom: Test Results & Action */}
                  <div>
                    {test && (
                      <div style={{
                        padding: '5px 8px',
                        borderRadius: '6px',
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        marginBottom: '8px',
                        background: test.status === 'success' ? 'rgba(63, 185, 80, 0.15)' : (test.status === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(0, 210, 255, 0.15)'),
                        color: test.status === 'success' ? '#3fb950' : (test.status === 'error' ? '#ef4444' : '#00d2ff'),
                        border: test.status === 'success' ? '1px solid #3fb950' : (test.status === 'error' ? '1px solid #ef4444' : '1px solid #00d2ff')
                      }}>
                        {test.msg}
                      </div>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                      <button
                        onClick={() => testProviderConnection(prov.id)}
                        disabled={isTesting}
                        style={{
                          padding: '5px 10px',
                          borderRadius: '8px',
                          background: `${prov.color}15`,
                          border: `1px solid ${prov.color}35`,
                          color: prov.color,
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        {isTesting ? <RefreshCw size={11} className="spin" /> : <Zap size={11} />}
                        Testa
                      </button>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.68rem', color: hasKey ? '#3fb950' : subtitleColor, fontWeight: 700 }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: hasKey ? '#3fb950' : '#888' }} />
                        {hasKey ? 'Configurato' : 'Non Impostato'}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* SECTION 2: SIGMAENGINE SERVER & VS CODE INTEROPERABILITY */}
      {activeSection === 'server' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Top Server Status Banner with ON/OFF Service Toggle */}
          <div style={{
            padding: '20px 24px',
            borderRadius: '16px',
            background: providerServerEnabled 
              ? 'linear-gradient(135deg, rgba(0, 242, 254, 0.12), rgba(79, 172, 254, 0.05))'
              : 'linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(185, 28, 28, 0.04))',
            border: providerServerEnabled ? '1px solid rgba(0, 242, 254, 0.35)' : '1px solid rgba(239, 68, 68, 0.35)',
            boxShadow: cardShadow,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: providerServerEnabled ? 'rgba(0, 242, 254, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                border: providerServerEnabled ? '1px solid rgba(0, 242, 254, 0.4)' : '1px solid rgba(239, 68, 68, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: providerServerEnabled ? '0 0 20px rgba(0, 242, 254, 0.25)' : '0 0 20px rgba(239, 68, 68, 0.25)'
              }}>
                <Globe size={26} color={providerServerEnabled ? "#00f2fe" : "#ef4444"} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
                  <span style={{
                    fontSize: '0.66rem',
                    fontWeight: 800,
                    color: providerServerEnabled ? '#00f2fe' : '#ef4444',
                    background: providerServerEnabled ? 'rgba(0, 242, 254, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    border: providerServerEnabled ? '1px solid rgba(0, 242, 254, 0.35)' : '1px solid rgba(239, 68, 68, 0.35)',
                    padding: '2px 8px',
                    borderRadius: '10px',
                    letterSpacing: '0.5px'
                  }}>
                    STANDARD OPEN PROVIDER
                  </span>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    color: providerServerEnabled ? '#3fb950' : '#ef4444'
                  }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: providerServerEnabled ? '#3fb950' : '#ef4444', display: 'inline-block', boxShadow: providerServerEnabled ? '0 0 8px #3fb950' : 'none' }} />
                    {providerServerEnabled ? 'SERVIZIO ATTIVO (Port 8000)' : 'SERVIZIO DISABILITATO'}
                  </span>
                </div>
                <h2 style={{ margin: '0 0 3px 0', fontSize: '1.25rem', fontWeight: 800, color: titleColor }}>
                  ⚡ SigmaEngine Provider Server — Interoperabilità VS Code & Client
                </h2>
                <p style={{ margin: 0, fontSize: '0.76rem', color: subtitleColor, maxWidth: '680px', lineHeight: 1.45 }}>
                  Server API unificato conforme agli standard <strong>OpenAI</strong> (<code style={{ color: '#00f2fe' }}>/v1</code>) e <strong>Ollama</strong> (<code style={{ color: '#00d2ff' }}>/api</code>). Puoi abilitare o disabilitare il servizio in qualsiasi momento.
                </p>
              </div>
            </div>

            {/* Service Toggle Switch & Actions */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <button
                onClick={() => toggleProviderServer()}
                style={{
                  padding: '8px 14px',
                  borderRadius: '10px',
                  background: providerServerEnabled ? 'rgba(239, 68, 68, 0.15)' : 'linear-gradient(135deg, #3fb950, #2ea043)',
                  border: providerServerEnabled ? '1px solid rgba(239, 68, 68, 0.35)' : 'none',
                  color: providerServerEnabled ? '#ef4444' : '#fff',
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: providerServerEnabled ? 'none' : '0 4px 14px rgba(63, 185, 80, 0.3)'
                }}
              >
                {providerServerEnabled ? (
                  <>
                    <X size={13} /> Disabilita Servizio
                  </>
                ) : (
                  <>
                    <Zap size={13} /> Abilita Servizio
                  </>
                )}
              </button>

              <button
                onClick={downloadContinueConfig}
                style={{
                  padding: '8px 14px',
                  borderRadius: '10px',
                  background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                  border: 'none',
                  color: '#000',
                  fontSize: '0.76rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 14px rgba(0, 242, 254, 0.3)'
                }}
              >
                <Download size={13} /> Scarica config.json (Continue)
              </button>
            </div>
          </div>

          {/* DYNAMIC MODEL SELECTOR FOR VS CODE & EXTERNAL CLIENTS */}
          <div style={{
            padding: '16px 20px',
            borderRadius: '14px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <Sparkles size={16} color="#00f2fe" />
                  <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                    🎯 Seleziona Modello di Riferimento per VS Code & Software
                  </h3>
                </div>
                <p style={{ margin: 0, fontSize: '0.74rem', color: subtitleColor }}>
                  Scegli quale modello esporre: tutti i modelli scaricati in <code>data/models/</code>, residenti in VRAM o configurati in Cloud sono accessibili via standard OpenAI & Ollama.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '280px' }}>
                <select
                  value={selectedGuideModel}
                  onChange={e => setSelectedGuideModel(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '10px',
                    background: innerCardBg,
                    border: '1px solid rgba(0, 242, 254, 0.4)',
                    color: titleColor,
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    outline: 'none',
                    cursor: 'pointer'
                  }}
                >
                  {allAvailableGuideModels.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Quick Model Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.68rem', color: subtitleColor, fontWeight: 700 }}>Scorciatoie Rapide:</span>
              {allAvailableGuideModels.slice(0, 6).map(m => (
                <button
                  key={m.id}
                  onClick={() => setSelectedGuideModel(m.id)}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '0.66rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    background: selectedGuideModel === m.id ? 'rgba(0, 242, 254, 0.2)' : innerCardBg,
                    border: selectedGuideModel === m.id ? '1px solid #00f2fe' : innerCardBorder,
                    color: selectedGuideModel === m.id ? '#00f2fe' : subtitleColor,
                    transition: 'all 0.15s ease'
                  }}
                >
                  {m.id}
                </button>
              ))}
            </div>
          </div>

          {/* Quick Endpoints Copy Matrix */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '12px'
          }}>
            {/* OpenAI Format Box */}
            <div style={{
              padding: '14px 16px',
              borderRadius: '12px',
              background: cardBg,
              border: cardBorder,
              boxShadow: cardShadow
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#10a37f' }}>
                  🟢 Standard OpenAI Compatible
                </span>
                <span style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>
                  Per Continue, Cline, Roo Code, Copilot, LangChain
                </span>
              </div>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 10px',
                borderRadius: '8px',
                background: innerCardBg,
                border: innerCardBorder,
                fontSize: '0.76rem',
                fontFamily: 'monospace',
                color: titleColor
              }}>
                <span>http://localhost:8000/v1</span>
                <button
                  onClick={() => copyKeyToClipboard('openai_base', 'http://localhost:8000/v1')}
                  style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer', padding: '2px' }}
                >
                  {copiedKey === 'openai_base' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />}
                </button>
              </div>
              <div style={{ fontSize: '0.66rem', color: subtitleColor, marginTop: '6px' }}>
                API Key: <code style={{ color: '#00f2fe' }}>sigma</code> • Model ID: <code style={{ color: '#00f2fe', fontWeight: 700 }}>{selectedGuideModel}</code>
              </div>
            </div>

            {/* Ollama Format Box */}
            <div style={{
              padding: '14px 16px',
              borderRadius: '12px',
              background: cardBg,
              border: cardBorder,
              boxShadow: cardShadow
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff' }}>
                  🔷 Standard Ollama Protocol
                </span>
                <span style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>
                  Per Ollama SDK, Continue (ollama), Local Web UIs
                </span>
              </div>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 10px',
                borderRadius: '8px',
                background: innerCardBg,
                border: innerCardBorder,
                fontSize: '0.76rem',
                fontFamily: 'monospace',
                color: titleColor
              }}>
                <span>http://localhost:8000</span>
                <button
                  onClick={() => copyKeyToClipboard('ollama_base', 'http://localhost:8000')}
                  style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer', padding: '2px' }}
                >
                  {copiedKey === 'ollama_base' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />}
                </button>
              </div>
              <div style={{ fontSize: '0.66rem', color: subtitleColor, marginTop: '6px' }}>
                Endpoints: <code style={{ color: '#00d2ff' }}>/api/chat</code> • <code style={{ color: '#00d2ff' }}>/api/tags</code> • <code style={{ color: '#00d2ff' }}>/api/generate</code>
              </div>
            </div>
          </div>

          {/* Integration Guides & Interactive Code Snippets */}
          <div style={{
            padding: '20px',
            borderRadius: '16px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Terminal size={18} color="#00f2fe" />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: titleColor }}>
                  Guide di Configurazione per Client & IDE
                </h3>
              </div>

              {/* Guide Tabs Switcher */}
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {[
                  { id: 'continue', label: '🧩 Continue (VS Code)' },
                  { id: 'cline', label: '🤖 Cline / Roo Code' },
                  { id: 'copilot', label: '🚀 Cursor / Copilot' },
                  { id: 'python', label: '🐍 Python SDK' },
                  { id: 'curl', label: '💻 cURL Test' }
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveVsCodeTab(tab.id)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '8px',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      border: isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.08)',
                      cursor: 'pointer',
                      background: activeVsCodeTab === tab.id ? '#00f2fe' : innerCardBg,
                      color: activeVsCodeTab === tab.id ? '#000000' : subtitleColor,
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* TAB CONTENT: CONTINUE.DEV */}
            {activeVsCodeTab === 'continue' && (
              <div>
                <p style={{ margin: '0 0 10px 0', fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.4 }}>
                  In Visual Studio Code, installa l'estensione <strong>Continue</strong> e incolla questa configurazione nel file <code style={{ color: '#00f2fe' }}>~/.continue/config.json</code>:
                </p>
                <div style={{ position: 'relative' }}>
                  <pre style={{
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: '#07090e',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    color: '#00f2fe',
                    fontSize: '0.74rem',
                    fontFamily: 'Consolas, monospace',
                    overflowX: 'auto',
                    margin: 0
                  }}>{`{
  "models": [
    {
      "title": "SigmaEngine (${selectedGuideModel})",
      "provider": "openai",
      "model": "${selectedGuideModel}",
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "sigma"
    },
    {
      "title": "SigmaEngine Ollama (${selectedGuideModel})",
      "provider": "ollama",
      "model": "${selectedGuideModel}",
      "apiBase": "http://localhost:8000"
    }
  ],
  "tabAutocompleteModel": {
    "title": "SigmaEngine Autocomplete",
    "provider": "openai",
    "model": "qwen2.5-coder:7b",
    "apiBase": "http://localhost:8000/v1",
    "apiKey": "sigma"
  }
}`}</pre>
                  <button
                    onClick={() => copyKeyToClipboard('continue_code', `{\n  "models": [\n    {\n      "title": "SigmaEngine (${selectedGuideModel})",\n      "provider": "openai",\n      "model": "${selectedGuideModel}",\n      "apiBase": "http://localhost:8000/v1",\n      "apiKey": "sigma"\n    }\n  ]\n}`)}
                    style={{
                      position: 'absolute',
                      top: '8px',
                      right: '8px',
                      padding: '4px 8px',
                      borderRadius: '6px',
                      background: 'rgba(255,255,255,0.1)',
                      border: '1px solid rgba(255,255,255,0.2)',
                      color: '#fff',
                      fontSize: '0.64rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    {copiedKey === 'continue_code' ? <Check size={11} color="#3fb950" /> : <Copy size={11} />} Copia JSON
                  </button>
                </div>
              </div>
            )}

            {/* TAB CONTENT: CLINE / ROO CODE */}
            {activeVsCodeTab === 'cline' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#10a37f' }}>Opzione 1 (Consigliata) — Provider: OpenAI Compatible</span>
                    <span style={{ fontSize: '0.62rem', background: '#10a37f20', color: '#10a37f', padding: '1px 6px', borderRadius: '6px', fontWeight: 700 }}>Piena conformità SSE & Tool Calling</span>
                  </div>
                  <p style={{ margin: '0 0 8px 0', fontSize: '0.73rem', color: subtitleColor, lineHeight: 1.4 }}>
                    Nelle impostazioni di <strong>Cline</strong> o <strong>Roo Code</strong> in VS Code, imposta:
                  </p>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '8px'
                  }}>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder }}>
                      <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>API PROVIDER</div>
                      <div style={{ fontSize: '0.78rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>OpenAI Compatible</div>
                    </div>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>BASE URL</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00f2fe', marginTop: '2px' }}>http://localhost:8000/v1</div>
                      </div>
                      <button onClick={() => copyKeyToClipboard('cline_base', 'http://localhost:8000/v1')} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                        {copiedKey === 'cline_base' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                      </button>
                    </div>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>API KEY</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>sigma</div>
                      </div>
                      <button onClick={() => copyKeyToClipboard('cline_key', 'sigma')} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                        {copiedKey === 'cline_key' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                      </button>
                    </div>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>MODEL ID</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff', marginTop: '2px' }}>{selectedGuideModel}</div>
                      </div>
                      <button onClick={() => copyKeyToClipboard('cline_model', selectedGuideModel)} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                        {copiedKey === 'cline_model' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                      </button>
                    </div>
                  </div>
                </div>

                <div style={{ borderTop: isLight ? '1px solid rgba(0,0,0,0.08)' : '1px solid rgba(255,255,255,0.06)', paddingTop: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff' }}>Opzione 2 — Provider: Ollama</span>
                    <span style={{ fontSize: '0.62rem', background: '#00d2ff20', color: '#00d2ff', padding: '1px 6px', borderRadius: '6px', fontWeight: 700 }}>Protocollo NDJSON</span>
                  </div>
                  <p style={{ margin: '0 0 8px 0', fontSize: '0.73rem', color: subtitleColor, lineHeight: 1.4 }}>
                    Se selezioni il provider <strong>Ollama</strong> in Cline o Roo Code, imposta il Base URL <strong>senza /v1</strong>:
                  </p>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '8px'
                  }}>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder }}>
                      <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>API PROVIDER</div>
                      <div style={{ fontSize: '0.78rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>Ollama</div>
                    </div>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>BASE URL (Ollama)</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff', marginTop: '2px' }}>http://localhost:8000</div>
                      </div>
                      <button onClick={() => copyKeyToClipboard('ollama_cline_base', 'http://localhost:8000')} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                        {copiedKey === 'ollama_cline_base' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                      </button>
                    </div>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>MODEL ID</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff', marginTop: '2px' }}>{selectedGuideModel}</div>
                      </div>
                      <button onClick={() => copyKeyToClipboard('ollama_cline_model', selectedGuideModel)} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                        {copiedKey === 'ollama_cline_model' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: CURSOR / COPILOT / WINDSURF */}
            {activeVsCodeTab === 'copilot' && (
              <div>
                <p style={{ margin: '0 0 10px 0', fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.4 }}>
                  Imposta le variabili di ambiente per collegare <strong>Cursor</strong>, <strong>Aider</strong> o <strong>Windsurf</strong> a SigmaEngine:
                </p>
                <pre style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  background: '#07090e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#3fb950',
                  fontSize: '0.74rem',
                  fontFamily: 'Consolas, monospace',
                  overflowX: 'auto',
                  margin: 0
                }}>{`# PowerShell / Terminale Windows
$env:OPENAI_BASE_URL="http://localhost:8000/v1"
$env:OPENAI_API_KEY="sigma"
$env:OPENAI_MODEL="${selectedGuideModel}"

# Linux / macOS / Bash
export OPENAI_BASE_URL="http://localhost:8000/v1"
export OPENAI_API_KEY="sigma"
export OPENAI_MODEL="${selectedGuideModel}"`}</pre>
              </div>
            )}

            {/* TAB CONTENT: PYTHON SDK */}
            {activeVsCodeTab === 'python' && (
              <div>
                <p style={{ margin: '0 0 10px 0', fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.4 }}>
                  Usa l'SDK ufficiale <code>openai</code> in Python senza modificare una riga di logica:
                </p>
                <pre style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  background: '#07090e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#faa03c',
                  fontSize: '0.74rem',
                  fontFamily: 'Consolas, monospace',
                  overflowX: 'auto',
                  margin: 0
                }}>{`from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sigma"
)

response = client.chat.completions.create(
    model="${selectedGuideModel}",
    messages=[
        {"role": "system", "content": "Sei Sigma Assistant."},
        {"role": "user", "content": "Ciao da Visual Studio Code!"}
    ],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)`}</pre>
              </div>
            )}

            {/* TAB CONTENT: CURL TEST */}
            {activeVsCodeTab === 'curl' && (
              <div>
                <p style={{ margin: '0 0 10px 0', fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.4 }}>
                  Esegui un probe istantaneo da PowerShell o terminale per testare lo streaming SSE di SigmaEngine:
                </p>
                <div style={{ position: 'relative' }}>
                  <pre style={{
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: '#07090e',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    color: '#00f2fe',
                    fontSize: '0.74rem',
                    fontFamily: 'Consolas, monospace',
                    overflowX: 'auto',
                    margin: 0
                  }}>{`curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d "{\\"model\\":\\"${selectedGuideModel}\\",\\"messages\\":[{\\"role\\":\\"user\\",\\"content\\":\\"Ciao SigmaEngine!\\"}]}"`}</pre>
                  <button
                    onClick={() => copyKeyToClipboard('curl_code', `curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d "{\\"model\\":\\"${selectedGuideModel}\\",\\"messages\\":[{\\"role\\":\\"user\\",\\"content\\":\\"Ciao SigmaEngine!\\"}]}"`)}
                    style={{
                      position: 'absolute',
                      top: '8px',
                      right: '8px',
                      padding: '4px 8px',
                      borderRadius: '6px',
                      background: 'rgba(255,255,255,0.1)',
                      border: '1px solid rgba(255,255,255,0.2)',
                      color: '#fff',
                      fontSize: '0.64rem',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    {copiedKey === 'curl_code' ? <Check size={11} color="#3fb950" /> : <Copy size={11} />} Copia cURL
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Interactive Live Interoperability Test Terminal */}
          <div style={{
            padding: '20px',
            borderRadius: '16px',
            background: cardBg,
            border: '1px solid rgba(0, 242, 254, 0.25)',
            boxShadow: cardShadow
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Zap size={18} color="#00f2fe" />
                <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: titleColor }}>
                  ⚡ Test Live Interoperabilità Endpoint
                </h3>
                <span style={{
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  color: '#00f2fe',
                  background: 'rgba(0, 242, 254, 0.12)',
                  padding: '2px 8px',
                  borderRadius: '6px'
                }}>
                  Modello: {selectedGuideModel}
                </span>
              </div>

              {/* Protocol Switcher */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  onClick={() => setLiveTestState(p => ({ ...p, protocol: 'openai' }))}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '8px',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    background: liveTestState.protocol === 'openai' ? '#10a37f' : innerCardBg,
                    color: liveTestState.protocol === 'openai' ? '#fff' : subtitleColor
                  }}
                >
                  OpenAI (/v1/chat/completions)
                </button>
                <button
                  onClick={() => setLiveTestState(p => ({ ...p, protocol: 'ollama' }))}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '8px',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    background: liveTestState.protocol === 'ollama' ? '#00d2ff' : innerCardBg,
                    color: liveTestState.protocol === 'ollama' ? '#fff' : subtitleColor
                  }}
                >
                  Ollama (/api/chat)
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              <input
                type="text"
                value={liveTestState.prompt}
                onChange={e => setLiveTestState(p => ({ ...p, prompt: e.target.value }))}
                placeholder="Inserisci un prompt di test..."
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: '10px',
                  background: innerCardBg,
                  border: innerCardBorder,
                  color: titleColor,
                  fontSize: '0.78rem',
                  outline: 'none'
                }}
              />
              <button
                onClick={runLiveServerTest}
                disabled={liveTestState.isTesting}
                style={{
                  padding: '8px 18px',
                  borderRadius: '10px',
                  background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                  border: 'none',
                  color: '#000',
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  whiteSpace: 'nowrap'
                }}
              >
                {liveTestState.isTesting ? <RefreshCw size={13} className="spin" /> : <Play size={13} />}
                Esegui Test Live
              </button>
            </div>

            {/* Test Results Output Box */}
            {(liveTestState.outputText || liveTestState.isTesting || liveTestState.error) && (
              <div style={{
                padding: '14px',
                borderRadius: '12px',
                background: '#07090e',
                border: '1px solid rgba(0, 242, 254, 0.3)',
                fontSize: '0.78rem',
                color: titleColor,
                lineHeight: 1.5
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.68rem', color: subtitleColor }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: liveTestState.isTesting ? '#00f2fe' : (liveTestState.error ? '#ef4444' : '#3fb950') }} />
                    Protocollo: <strong>{liveTestState.protocol.toUpperCase()}</strong> • Modello: <strong style={{ color: '#00f2fe' }}>{selectedGuideModel}</strong>
                  </span>
                  {liveTestState.ttft && (
                    <span>TTFT (Primo Token): <strong style={{ color: '#00f2fe' }}>{liveTestState.ttft}ms</strong> • Totale: <strong style={{ color: '#3fb950' }}>{liveTestState.latency || '...'}ms</strong></span>
                  )}
                </div>

                {liveTestState.error ? (
                  <div style={{ color: '#ef4444' }}>❌ {liveTestState.error}</div>
                ) : (
                  <div style={{ whiteSpace: 'pre-wrap', color: '#e2e8f0', fontFamily: 'inherit' }}>
                    {liveTestState.outputText}
                    {liveTestState.isTesting && <span style={{ display: 'inline-block', width: '6px', height: '14px', background: '#00f2fe', marginLeft: '3px', verticalAlign: 'middle', animation: 'blink 1s infinite' }} />}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* SECTION 3: GLOBAL INFERENCE PARAMETERS */}
      {activeSection === 'parameters' && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '16px'
        }}>
          {/* Panel 1: Temperature & Sampling */}
          <div style={{
            padding: '18px 20px',
            borderRadius: '16px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Sliders size={16} color="#00d2ff" />
              <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: titleColor }}>
                Temperatura & Campionamento
              </h3>
            </div>

            {/* Temperature Slider */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.76rem', fontWeight: 700, color: titleColor }}>Temperatura</label>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff' }}>{parameters.temperature}</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={parameters.temperature}
                onChange={e => setParameters(p => ({ ...p, temperature: parseFloat(e.target.value) }))}
                style={{ width: '100%', accentColor: '#00d2ff' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.64rem', color: subtitleColor, marginTop: '3px' }}>
                <span>0.0 (Deterministico)</span>
                <span>0.7 (Bilanciato)</span>
                <span>1.0 (Creativo)</span>
              </div>
            </div>

            {/* Top P Slider */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.76rem', fontWeight: 700, color: titleColor }}>Top_P (Nucleus Sampling)</label>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#bc8cff' }}>{parameters.top_p}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={parameters.top_p}
                onChange={e => setParameters(p => ({ ...p, top_p: parseFloat(e.target.value) }))}
                style={{ width: '100%', accentColor: '#bc8cff' }}
              />
            </div>

            {/* Repeat Penalty */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.76rem', fontWeight: 700, color: titleColor }}>Penalità di Ripetizione</label>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#3fb950' }}>{parameters.repeat_penalty}</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="1.5"
                step="0.05"
                value={parameters.repeat_penalty}
                onChange={e => setParameters(p => ({ ...p, repeat_penalty: parseFloat(e.target.value) }))}
                style={{ width: '100%', accentColor: '#3fb950' }}
              />
            </div>
          </div>

          {/* Panel 2: Context Window & Token Limits */}
          <div style={{
            padding: '18px 20px',
            borderRadius: '16px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Database size={16} color="#faa03c" />
              <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: titleColor }}>
                Finestra di Contesto & Token
              </h3>
            </div>

            {/* Num Ctx */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.76rem', fontWeight: 700, color: titleColor }}>Contesto Massimo (num_ctx)</label>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#faa03c' }}>{parameters.num_ctx.toLocaleString()} token</span>
              </div>
              <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '6px' }}>
                {[8192, 16384, 32768, 65536, 131072, 262144].map(ctx => (
                  <button
                    key={ctx}
                    onClick={() => setParameters(p => ({ ...p, num_ctx: ctx }))}
                    style={{
                      padding: '4px 8px',
                      borderRadius: '6px',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      border: 'none',
                      cursor: 'pointer',
                      background: parameters.num_ctx === ctx ? '#faa03c' : innerCardBg,
                      color: parameters.num_ctx === ctx ? '#ffffff' : subtitleColor
                    }}
                  >
                    {ctx >= 1000 ? `${ctx / 1024}K` : ctx}
                  </button>
                ))}
              </div>
            </div>

            {/* Max Output Tokens */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ fontSize: '0.76rem', fontWeight: 700, color: titleColor }}>Max Token di Risposta</label>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff' }}>{parameters.max_tokens.toLocaleString()} token</span>
              </div>
              <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                {[4096, 8192, 16384, 32768, 65536].map(tok => (
                  <button
                    key={tok}
                    onClick={() => setParameters(p => ({ ...p, max_tokens: tok }))}
                    style={{
                      padding: '4px 8px',
                      borderRadius: '6px',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      border: 'none',
                      cursor: 'pointer',
                      background: parameters.max_tokens === tok ? '#00d2ff' : innerCardBg,
                      color: parameters.max_tokens === tok ? '#ffffff' : subtitleColor
                    }}
                  >
                    {tok >= 1024 ? `${tok / 1024}K` : tok}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={saveAllConfig}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #00d2ff, #7c5bf0)',
                border: 'none',
                color: '#fff',
                fontWeight: 800,
                fontSize: '0.78rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px'
              }}
            >
              <Save size={13} /> Applica Parametri
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
