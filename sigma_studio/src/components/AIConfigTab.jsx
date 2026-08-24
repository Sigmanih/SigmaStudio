import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { 
  Cpu, Key, ShieldCheck, Zap, RefreshCw, Save, CheckCircle2, 
  AlertCircle, Sliders, ExternalLink, Copy, Check, Eye, EyeOff, 
  Search, Server, Database, Download, Trash2, ChevronDown, Lock, Sparkles,
  Code, Terminal, Layers, Globe, Play, CheckCircle, FileText, Settings, Share2,
  Monitor, X, ChevronRight, Wifi, ArrowUpRight, HardDrive, Box,
  Activity, ArrowRight, CornerDownRight, CheckSquare, Power, Radio,
  Maximize2, SlidersHorizontal, CheckCheck
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';

// Dedicated SVG Github Icon
const GithubIcon = ({ size = 16, color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
  </svg>
);

// High-quality dedicated SVG brand icons for providers & GitHub engines
export const ProviderIcons = {
  sigma_engine: ({ size = 20, color = '#00f2fe' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M13 2L3 14H12L11 22L21 10H12L13 2Z" fill={`${color}30`} stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  ),
  lmstudio: ({ size = 20, color = '#6366f1' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="5" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <circle cx="8.5" cy="8.5" r="2" fill={color} />
      <path d="M13.5 7H17M13.5 10H17M7 14H17M7 17H13" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
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
  llamacpp: ({ size = 20, color = '#f59e0b' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="4" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <path d="M7 8L12 12L7 16" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13 16H17" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
  vllm: ({ size = 20, color = '#38bdf8' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 4L12 20L20 4L15 4L12 13L9 4H4Z" fill={`${color}28`} stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  localai: ({ size = 20, color = '#10b981' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M3 9L12 3L21 9V19C21 20.1 20.1 21 19 21H5C3.9 21 3 20.1 3 19V9Z" fill={`${color}20`} stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M9 21V12H15V21" stroke={color} strokeWidth="1.6" />
    </svg>
  ),
  koboldcpp: ({ size = 20, color = '#ec4899' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="4" y="4" width="16" height="16" rx="4" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <circle cx="8.5" cy="8.5" r="1.5" fill={color} />
      <circle cx="15.5" cy="8.5" r="1.5" fill={color} />
      <circle cx="12" cy="12" r="1.5" fill={color} />
      <circle cx="8.5" cy="15.5" r="1.5" fill={color} />
      <circle cx="15.5" cy="15.5" r="1.5" fill={color} />
    </svg>
  ),
  tabby: ({ size = 20, color = '#a855f7' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 19C4 19 6 12 12 12C18 12 20 19 20 19M12 4V12M7 7L12 12L17 7" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill={`${color}20`} />
    </svg>
  ),
  oobabooga: ({ size = 20, color = '#f97316' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke={color} strokeWidth="1.8" fill={`${color}20`} />
      <circle cx="9" cy="10" r="1.5" fill={color} />
      <circle cx="15" cy="10" r="1.5" fill={color} />
      <path d="M8 15C9.5 17 14.5 17 16 15" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
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
  mistral: ({ size = 20, color = '#ff7000' }) => (
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
  qwen: ({ size = 20, color = '#8b5cf6' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" stroke={color} strokeWidth="1.8" fill={`${color}20`} strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" fill={color} />
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

// Curated Open-Source Inference Engines & Providers Downloadable from GitHub & Official Portals
export const GITHUB_ENGINES = [
  {
    id: 'lmstudio',
    name: 'LM Studio',
    badge: 'DESKTOP & SERVER',
    color: '#6366f1',
    iconKey: 'lmstudio',
    tagline: 'L\'app desktop più celebre per scoprire, scaricare ed eseguire modelli GGUF locali.',
    description: 'Scarica modelli da Hugging Face con 1 clic, chatta con accelerazione GPU CUDA/Metal e avvia il server locale OpenAI-compatibile su porta :1234.',
    repoUrl: 'https://github.com/lmstudio-ai',
    releasesUrl: 'https://lmstudio.ai',
    defaultPort: '1234',
    defaultEndpoint: 'http://localhost:1234/v1',
    protocol: 'OpenAI Compatible (/v1)',
    providerId: 'lmstudio'
  },
  {
    id: 'ollama',
    name: 'Ollama',
    badge: '100% LOCALE',
    color: '#00d2ff',
    iconKey: 'ollama',
    tagline: 'Il framework più diffuso per eseguire Llama, Qwen, DeepSeek e Gemma in locale.',
    description: 'Esegui modelli quantizzati con supporto automatico GPU (NVIDIA CUDA, Apple Silicon Metal, AMD ROCm) e gestione Modelfile.',
    repoUrl: 'https://github.com/ollama/ollama',
    releasesUrl: 'https://github.com/ollama/ollama/releases',
    defaultPort: '11434',
    defaultEndpoint: 'http://localhost:11434',
    protocol: 'Ollama API & OpenAI (/v1)',
    providerId: 'ollama'
  },
  {
    id: 'ailoflow',
    name: 'AiloFlow',
    badge: 'FLOW ENGINE',
    color: '#00f2fe',
    iconKey: 'ailoflow',
    tagline: 'Engine a nodi per flussi di prompt visivi e prompt graphs multi-tier.',
    description: 'Framework locale ad alte prestazioni per orchestrazione di prompt strutturati, routing dinamico e sharding neurale multi-tier.',
    repoUrl: 'https://github.com/xxrickyxx/AiloFlow',
    releasesUrl: 'https://github.com/xxrickyxx/AiloFlow/releases',
    defaultPort: '5000',
    defaultEndpoint: 'http://localhost:5000/v1',
    protocol: 'OpenAI (/v1) & Graph API',
    providerId: 'ailoflow'
  },
  {
    id: 'llamacpp',
    name: 'llama.cpp',
    badge: 'C++ PURE SPEED',
    color: '#f59e0b',
    iconKey: 'llamacpp',
    tagline: 'Il motore C/C++ di riferimento per inferenza quantizzata GGUF ultra-efficiente.',
    description: 'Esecuzione ad altissima velocità su CPU e GPU. Include il binario standalone `llama-server` conforme alle specifiche OpenAI.',
    repoUrl: 'https://github.com/ggerganov/llama.cpp',
    releasesUrl: 'https://github.com/ggerganov/llama.cpp/releases',
    defaultPort: '8080',
    defaultEndpoint: 'http://localhost:8080/v1',
    protocol: 'OpenAI Compatible (/v1)',
    providerId: 'custom'
  },
  {
    id: 'vllm',
    name: 'vLLM',
    badge: 'PAGED ATTENTION',
    color: '#38bdf8',
    iconKey: 'vllm',
    tagline: 'Libreria di inferenza ad alto throughput con continuous batching e PagedAttention.',
    description: 'Ideale per server di produzione e GPU con elevata VRAM. Fornisce un server API OpenAI nativo ultra-performante.',
    repoUrl: 'https://github.com/vllm-project/vllm',
    releasesUrl: 'https://github.com/vllm-project/vllm/releases',
    defaultPort: '8000',
    defaultEndpoint: 'http://localhost:8000/v1',
    protocol: 'OpenAI Compatible (/v1)',
    providerId: 'custom'
  },
  {
    id: 'localai',
    name: 'LocalAI',
    badge: 'SELF-HOSTED HUB',
    color: '#10b981',
    iconKey: 'localai',
    tagline: 'Sostituto drop-in self-hosted e gratuito di OpenAI per testo, audio e immagini.',
    description: 'Supporta molteplici backend (llama.cpp, Transformers, Piper TTS, Whisper) senza richiedere account o dipendenze cloud.',
    repoUrl: 'https://github.com/mudler/LocalAI',
    releasesUrl: 'https://github.com/mudler/LocalAI/releases',
    defaultPort: '8080',
    defaultEndpoint: 'http://localhost:8080/v1',
    protocol: 'OpenAI Compatible (/v1)',
    providerId: 'custom'
  },
  {
    id: 'koboldcpp',
    name: 'KoboldCpp',
    badge: 'STANDALONE GUI',
    color: '#ec4899',
    iconKey: 'koboldcpp',
    tagline: 'Distribuzione single-file per modelli GGUF con UI web per scrittura creativa.',
    description: 'Zero configurazioni: un solo eseguibile `.exe` con interfaccia web interattiva ed endpoint compatibili Kobold & OpenAI.',
    repoUrl: 'https://github.com/LostRuins/koboldcpp',
    releasesUrl: 'https://github.com/LostRuins/koboldcpp/releases',
    defaultPort: '5001',
    defaultEndpoint: 'http://localhost:5001/v1',
    protocol: 'OpenAI Compatible & Kobold API',
    providerId: 'custom'
  },
  {
    id: 'tabby',
    name: 'Tabby',
    badge: 'AI CODE ASSISTANT',
    color: '#a855f7',
    iconKey: 'tabby',
    tagline: 'Server di completamento codice self-hosted open-source alternativo a GitHub Copilot.',
    description: 'Ottimizzato per autocomplete multi-riga e chat contestuale del repository su VS Code, JetBrains e Neovim.',
    repoUrl: 'https://github.com/TabbyML/tabby',
    releasesUrl: 'https://github.com/TabbyML/tabby/releases',
    defaultPort: '8080',
    defaultEndpoint: 'http://localhost:8080/v1',
    protocol: 'OpenAI Compatible (/v1)',
    providerId: 'custom'
  },
  {
    id: 'oobabooga',
    name: 'Text Generation WebUI',
    badge: 'MULTI-BACKEND UI',
    color: '#f97316',
    iconKey: 'oobabooga',
    tagline: 'La celebre interfaccia Gradio multi-backend per Transformers, ExLlamaV2 e GGUF.',
    description: 'Ampia suite di estensioni, supporto LoRA, caricamento dinamico di modelli e server API OpenAI integrato.',
    repoUrl: 'https://github.com/oobabooga/text-generation-webui',
    releasesUrl: 'https://github.com/oobabooga/text-generation-webui/releases',
    defaultPort: '5000',
    defaultEndpoint: 'http://localhost:5000/v1',
    protocol: 'OpenAI Compatible (/v1)',
    providerId: 'custom'
  }
];

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
  lmstudio: {
    id: 'lmstudio',
    label: 'LM Studio (Server Locale :1234)',
    category: 'local',
    color: '#6366f1',
    badge: 'DESKTOP & SERVER',
    endpoint: 'http://localhost:1234',
    api_url: 'http://localhost:1234/v1',
    api_key_required: false,
    key_placeholder: 'Nessuna API Key (o usa "lm-studio")',
    docs_url: 'https://lmstudio.ai',
    hint: 'Server locale integrato di LM Studio conforme allo standard OpenAI (/v1). Esegui qualsiasi modello GGUF da Hugging Face su porta 1234.',
    default_model: 'local-model',
    popular_models: ['local-model', 'qwen2.5-coder-7b-instruct', 'deepseek-r1-distill-qwen-8b', 'llama-3.2-3b-instruct', 'mistral-nemo-instruct-2407']
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
    hint: 'Collega gateway aziendali, vLLM, llama.cpp, LM Studio o LocalAI.',
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
    if (!options || options.length === 0) return [];
    if (!search.trim()) return options;
    return options.filter(opt => {
      const optStr = typeof opt === 'string' ? opt : (opt?.name || opt?.id || '');
      return optStr.toLowerCase().includes(search.toLowerCase().trim());
    });
  }, [options, search]);

  const selectedDisplay = value || (options?.[0] ? (typeof options[0] === 'string' ? options[0] : options[0]?.name) : 'Seleziona modello');

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
          {options && options.length > 4 && (
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
                const optStr = typeof opt === 'string' ? opt : (opt?.name || opt?.id || '');
                const isSelected = value === optStr;
                return (
                  <button
                    key={optStr}
                    type="button"
                    onClick={() => {
                      onChange(optStr);
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
                    <span>{optStr}</span>
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

  // Styling tokens (Modern Glassmorphism & Cyber Luxe Dark Mode)
  const bg = isLight ? '#fcfaf6' : '#080a0f';
  const cardBg = isLight ? '#fffdf9' : '#10131c';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const innerCardBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.035)';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.06)';
  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#a0a6bc';
  const cardShadow = isLight ? '0 2px 12px rgba(190, 160, 110, 0.1)' : '0 6px 24px rgba(0, 0, 0, 0.45)';

  // Navigation state (Single-page with smooth scroll anchors)
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSectionAnchor, setActiveSectionAnchor] = useState('engine'); // 'engine' | 'github' | 'cloud'

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
  const [activeVsCodeTab, setActiveVsCodeTab] = useState('continue'); // 'continue' | 'cline' | 'copilot' | 'python' | 'node' | 'curl'
  const [liveTestState, setLiveTestState] = useState({
    protocol: 'openai',
    prompt: 'Scrivi un breve saluto e spiega la potenza del motore interno SigmaEngine.',
    isTesting: false,
    outputText: '',
    latency: null,
    ttft: null,
    error: null
  });

  // Smooth scroll to section in single page
  const scrollToSection = (sectionId) => {
    setActiveSectionAnchor(sectionId);
    const el = document.getElementById(`section-${sectionId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

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
          msg: `SigmaEngine Provider Server ${data.provider_server_enabled ? 'ABILITATO 🟢 (Port 8000)' : 'DISABILITATO 🔴'}`
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
            temperature: parameters.temperature || 0.7
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
            options: { num_predict: 300, temperature: parameters.temperature || 0.7 }
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
          max_tokens: cfg.max_tokens ?? 16384,
          top_p: cfg.top_p ?? 0.95,
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
      const res = await fetch('/api/tags');
      const data = await res.json();
      if (data.models && Array.isArray(data.models)) {
        setOllamaLocalModels(data.models.map(m => m.name));
      }
    } catch (e) {
      console.debug("Ollama models query offline:", e);
    } finally {
      setLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchServerInfo();
    fetchEngineProfile();
  }, [fetchConfig, fetchServerInfo, fetchEngineProfile]);

  // Save All Configuration to Server
  const saveAllConfig = async () => {
    setSaving(true);
    try {
      const payload = {
        active_provider: activeProvider,
        active_model: activeModel,
        provider: activeProvider,
        model: activeModel,
        temperature: parameters.temperature,
        max_tokens: parameters.max_tokens,
        top_p: parameters.top_p,
        top_k: parameters.top_k,
        repeat_penalty: parameters.repeat_penalty,
        num_ctx: parameters.num_ctx,
        providers: {}
      };

      Object.entries(providerSettings).forEach(([pId, pCfg]) => {
        payload.providers[pId] = {
          endpoint: pCfg.endpoint || '',
          api_url: pCfg.api_url || '',
          model: pCfg.custom_model || pCfg.model || PROVIDER_CATALOG[pId]?.default_model || '',
          api_key: pCfg.api_key || undefined
        };
      });

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (data.success) {
        setSaveToast({ type: 'success', msg: 'Configurazione salvata con successo!' });
        fetchConfig();
      } else {
        setSaveToast({ type: 'error', msg: data.error || 'Errore salvataggio' });
      }
    } catch (err) {
      setSaveToast({ type: 'error', msg: err.message });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveToast(null), 4000);
    }
  };

  // Test single provider connection
  const testProviderConnection = async (pId) => {
    setTestingProvider(pId);
    setTestResults(prev => ({ ...prev, [pId]: { status: 'testing', msg: 'Test connessione in corso...' } }));

    const p = providerSettings[pId] || {};
    const modelToTest = p.custom_model || p.model || PROVIDER_CATALOG[pId]?.default_model;

    try {
      let url = '/v1/chat/completions';
      let headers = { 'Content-Type': 'application/json' };
      let body = {
        model: modelToTest,
        messages: [{ role: 'user', content: 'Ping connection test' }],
        max_tokens: 10
      };

      if (pId === 'sigma_engine') {
        url = '/v1/chat/completions';
      }

      const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });

      if (res.ok) {
        setTestResults(prev => ({ ...prev, [pId]: { status: 'success', msg: '🟢 Connessione attiva e rispondente!' } }));
      } else {
        const txt = await res.text();
        setTestResults(prev => ({ ...prev, [pId]: { status: 'error', msg: `🔴 Errore HTTP ${res.status}: ${txt.slice(0, 80)}` } }));
      }
    } catch (err) {
      setTestResults(prev => ({ ...prev, [pId]: { status: 'error', msg: `🔴 Connessione fallita: ${err.message}` } }));
    } finally {
      setTestingProvider(null);
    }
  };

  // One-click Connect for GitHub Engines & Local Runtimes
  const handleConnectGitHubEngine = (engine) => {
    if (engine.providerId === 'ailoflow') {
      setActiveProvider('ailoflow');
      setProviderSettings(prev => ({
        ...prev,
        ailoflow: {
          ...prev.ailoflow,
          endpoint: engine.defaultEndpoint,
          api_url: engine.defaultEndpoint
        }
      }));
    } else if (engine.providerId === 'ollama') {
      setActiveProvider('ollama');
      setProviderSettings(prev => ({
        ...prev,
        ollama: {
          ...prev.ollama,
          endpoint: engine.defaultEndpoint
        }
      }));
      fetchOllamaModels(true);
    } else if (engine.providerId === 'lmstudio') {
      setActiveProvider('lmstudio');
      setProviderSettings(prev => ({
        ...prev,
        lmstudio: {
          ...prev.lmstudio,
          endpoint: 'http://localhost:1234',
          api_url: engine.defaultEndpoint
        }
      }));
    } else {
      // Custom OpenAI Compatible endpoint
      setActiveProvider('custom');
      setProviderSettings(prev => ({
        ...prev,
        custom: {
          ...prev.custom,
          api_url: engine.defaultEndpoint,
          model: engine.name.toLowerCase().replace(/[^a-z0-9]/g, '')
        }
      }));
    }

    setSaveToast({
      type: 'success',
      msg: `Configurato ${engine.name} (${engine.defaultEndpoint}) come provider attivo! Clicca "Salva & Applica" per confermare.`
    });
    setTimeout(() => setSaveToast(null), 4500);

    // Scroll to cloud/custom section
    scrollToSection('cloud');
  };

  const copyKeyToClipboard = (keyId, text) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyId);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const toggleKeyVisibility = (pId) => {
    setVisibleKeys(prev => ({ ...prev, [pId]: !prev[pId] }));
  };

  const updateProviderField = (pId, field, val) => {
    setProviderSettings(prev => ({
      ...prev,
      [pId]: {
        ...(prev[pId] || {}),
        [field]: val
      }
    }));
  };

  const handleExportBackup = () => {
    const backupData = {
      timestamp: new Date().toISOString(),
      active_provider: activeProvider,
      active_model: activeModel,
      parameters,
      providers: providerSettings
    };
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(backupData, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", "sigma_providers_backup.json");
    dlAnchor.click();
  };

  const handleResetDefault = () => {
    if (window.confirm("Vuoi ripristinare le impostazioni predefinite dei provider?")) {
      setActiveProvider('sigma_engine');
      setActiveModel('sigma:latest');
      fetchConfig();
    }
  };

  // Filtered cloud & general providers
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

  const configuredTokensCount = useMemo(() => {
    return Object.keys(providerSettings).filter(k => {
      const p = providerSettings[k];
      return k === 'ollama' || k === 'sigma_engine' || k === 'lmstudio' || p?.has_api_key || (p?.api_key && p?.api_key.trim().length > 0);
    }).length;
  }, [providerSettings]);

  const activeProviderMeta = PROVIDER_CATALOG[activeProvider] || PROVIDER_CATALOG.sigma_engine;
  const ActiveIconComponent = ProviderIcons[activeProvider] || ProviderIcons.sigma_engine;

  return (
    <div className="providers-hub-page" style={{
      padding: '24px 32px 80px 32px',
      background: bg,
      minHeight: '100%',
      maxHeight: '100%',
      height: '100%',
      overflowY: 'auto',
      color: titleColor,
      fontFamily: 'inherit',
      boxSizing: 'border-box',
      scrollBehavior: 'smooth'
    }}>
      {/* ========================================================================= */}
      {/* TOP HERO STATUS BAR */}
      {/* ========================================================================= */}
      <div style={{
        padding: '20px 24px',
        borderRadius: '18px',
        background: isLight ? '#ffffff' : 'linear-gradient(135deg, #111522, #0c0e15)',
        border: isLight ? `1px solid ${activeProviderMeta.color}50` : `1px solid ${activeProviderMeta.color}40`,
        boxShadow: cardShadow,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '16px',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{
          position: 'absolute',
          top: '-40px',
          right: '-40px',
          width: '180px',
          height: '180px',
          background: `radial-gradient(circle, ${activeProviderMeta.color}25 0%, transparent 70%)`,
          pointerEvents: 'none',
          borderRadius: '50%'
        }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', zIndex: 1 }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '14px',
            background: `${activeProviderMeta.color}18`,
            border: `1px solid ${activeProviderMeta.color}45`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 20px ${activeProviderMeta.color}30`
          }}>
            <ActiveIconComponent size={26} color={activeProviderMeta.color} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
              <span style={{
                fontSize: '0.64rem',
                fontWeight: 800,
                color: activeProviderMeta.color,
                background: `${activeProviderMeta.color}15`,
                border: `1px solid ${activeProviderMeta.color}35`,
                padding: '2px 8px',
                borderRadius: '8px',
                letterSpacing: '0.5px'
              }}>
                PROVIDER ATTIVO SIGMA STUDIO
              </span>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.7rem',
                fontWeight: 800,
                color: '#3fb950'
              }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#3fb950', display: 'inline-block', boxShadow: '0 0 8px #3fb950' }} />
                Online
              </span>
            </div>

            <h1 style={{ margin: '0 0 3px 0', fontSize: '1.35rem', fontWeight: 800, color: titleColor }}>
              ⚙️ Providers Hub & Local Server Gateway
            </h1>
            <p style={{ margin: 0, fontSize: '0.76rem', color: subtitleColor }}>
              Motore: <strong style={{ color: activeProviderMeta.color }}>{activeProviderMeta.label}</strong> • 
              Modello: <strong>{activeModel || activeProviderMeta.default_model}</strong> • 
              Server Esterno: <strong style={{ color: providerServerEnabled ? '#3fb950' : '#ef4444' }}>{providerServerEnabled ? 'Port :8000 ATTIVO 🟢' : 'DISABILITATO 🔴'}</strong> • 
              Chiavi Configurate: <strong>{configuredTokensCount}/{Object.keys(PROVIDER_CATALOG).length}</strong>
            </p>
          </div>
        </div>

        {/* Global CTA Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', zIndex: 1 }}>
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
            Testa Provider
          </button>

          <button
            onClick={saveAllConfig}
            disabled={saving}
            style={{
              padding: '8px 18px',
              borderRadius: '10px',
              background: `linear-gradient(135deg, ${activeProviderMeta.color}, #00a8ff)`,
              border: 'none',
              color: '#000000',
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

      {/* ========================================================================= */}
      {/* STICKY QUICK NAVIGATION BAR (3 LOGICAL PILLARS) */}
      {/* ========================================================================= */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '10px',
        padding: '8px 14px',
        borderRadius: '12px',
        background: cardBg,
        border: cardBorder,
        boxShadow: cardShadow,
        marginBottom: '20px',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        backdropFilter: 'blur(12px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'engine', label: '⚡ 1. SigmaEngine (Server :8000 & Parametri)', color: '#00f2fe' },
            { id: 'github', label: '🐙 2. Motori Open-Source & LM Studio', color: '#6366f1' },
            { id: 'cloud', label: '☁️ 3. Cloud Providers & API Vault', color: '#10a37f' }
          ].map(sec => {
            const active = activeSectionAnchor === sec.id;
            return (
              <button
                key={sec.id}
                onClick={() => scrollToSection(sec.id)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  border: active ? `1px solid ${sec.color}60` : '1px solid transparent',
                  cursor: 'pointer',
                  background: active ? `${sec.color}20` : 'transparent',
                  color: active ? sec.color : subtitleColor,
                  transition: 'all 0.15s ease'
                }}
              >
                {sec.label}
              </button>
            );
          })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            onClick={handleExportBackup}
            title="Esporta copia di backup JSON"
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
            title="Ripristina valori predefiniti"
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

      {/* ========================================================================= */}
      {/* SECTION 1: ⚡ SIGMAENGINE — LOCAL SERVER CONSOLE & DUAL ARCHITECTURE */}
      {/* ========================================================================= */}
      <div id="section-engine" style={{ marginBottom: '36px', scrollMarginTop: '65px' }}>
        
        {/* Section Heading */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'rgba(0, 242, 254, 0.15)',
              border: '1px solid rgba(0, 242, 254, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(0, 242, 254, 0.2)'
            }}>
              <Zap size={20} color="#00f2fe" />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: titleColor }}>
                1. ⚡ SigmaEngine — Server Locale & Architettura Duale
              </h2>
              <p style={{ margin: 0, fontSize: '0.76rem', color: subtitleColor }}>
                Motore ad alte prestazioni integrato in Sigma Studio ed esposto come Server API compatibile OpenAI / Ollama per qualsiasi client esterno.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 800,
              color: providerServerEnabled ? '#3fb950' : '#ef4444',
              background: providerServerEnabled ? 'rgba(63, 185, 80, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              border: providerServerEnabled ? '1px solid rgba(63, 185, 80, 0.35)' : '1px solid rgba(239, 68, 68, 0.35)',
              padding: '4px 10px',
              borderRadius: '8px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: providerServerEnabled ? '#3fb950' : '#ef4444',
                boxShadow: providerServerEnabled ? '0 0 8px #3fb950' : 'none'
              }} />
              {providerServerEnabled ? 'SERVER ATTIVO (Port :8000)' : 'SERVER DISABILITATO'}
            </span>

            <button
              onClick={() => toggleProviderServer()}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                background: providerServerEnabled ? 'rgba(239, 68, 68, 0.15)' : 'linear-gradient(135deg, #3fb950, #2ea043)',
                border: providerServerEnabled ? '1px solid rgba(239, 68, 68, 0.35)' : 'none',
                color: providerServerEnabled ? '#ef4444' : '#fff',
                fontSize: '0.74rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Power size={13} />
              {providerServerEnabled ? 'Arresta Server' : 'Avvia Server :8000'}
            </button>
          </div>
        </div>

        {/* LM Studio-style Local Server Control Dashboard Card */}
        <div style={{
          padding: '20px',
          borderRadius: '16px',
          background: cardBg,
          border: '1px solid rgba(0, 242, 254, 0.3)',
          boxShadow: cardShadow,
          marginBottom: '16px'
        }}>
          {/* Top Status & Specs Strip */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '10px',
            marginBottom: '16px'
          }}>
            <div style={{ padding: '10px 12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>SERVER BASE URL</div>
              <div style={{ fontSize: '0.86rem', fontWeight: 800, color: '#00f2fe', marginTop: '2px', fontFamily: 'monospace' }}>
                http://localhost:8000
              </div>
            </div>

            <div style={{ padding: '10px 12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>PROTOCOLLI ESPOSTI</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>
                OpenAI (/v1) + Ollama (/api)
              </div>
            </div>

            <div style={{ padding: '10px 12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>MODELLO RESIDENTE VRAM</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#faa03c', marginTop: '2px' }}>
                {serverInfo?.resident_model || 'sigmaengine (Auto-Load)'}
              </div>
            </div>

            <div style={{ padding: '10px 12px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>SICUREZZA & CORS</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#3fb950', marginTop: '2px' }}>
                CORS * (Tutti i client abilitati)
              </div>
            </div>
          </div>

          {/* Dual Architecture Blueprint (Ruolo 1 vs Ruolo 2) */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))',
            gap: '12px',
            marginBottom: '16px'
          }}>
            {/* Ruolo 1: Motore Interno */}
            <div style={{
              padding: '16px',
              borderRadius: '12px',
              background: isLight ? '#fbf8f0' : 'rgba(0, 242, 254, 0.04)',
              border: '1px solid rgba(0, 242, 254, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <Cpu size={16} color="#00f2fe" />
                  <span style={{ fontSize: '0.66rem', fontWeight: 800, color: '#00f2fe', letterSpacing: '0.5px' }}>
                    RUOLO 1: MOTORE INTERNO SIGMA STUDIO
                  </span>
                </div>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  ⚡ Inferenza Locale Diretta in-Memory
                </h4>
                <p style={{ margin: 0, fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.45 }}>
                  SigmaEngine è il motore neurale integrato in Sigma Studio. Esegue modelli residenti (GGUF, Safetensors) sfruttando <strong>CUDA FlashAttention-2</strong>, <strong>partizionamento dinamico della VRAM</strong> e <strong>Multi-Drive Sharding Lookahead</strong>, garantendo massima privacy e zero dipendenze dal cloud.
                </p>
              </div>
              <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.7rem', color: '#3fb950', fontWeight: 700 }}>
                <CheckCheck size={14} color="#3fb950" />
                <span>Attivo per tutte le chat, task di coding ed agent interni di Sigma Studio.</span>
              </div>
            </div>

            {/* Ruolo 2: Provider Server Esterno */}
            <div style={{
              padding: '16px',
              borderRadius: '12px',
              background: isLight ? '#fbf8f0' : 'rgba(99, 102, 241, 0.04)',
              border: '1px solid rgba(99, 102, 241, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <Globe size={16} color="#6366f1" />
                  <span style={{ fontSize: '0.66rem', fontWeight: 800, color: '#6366f1', letterSpacing: '0.5px' }}>
                    RUOLO 2: LOCAL PROVIDER PER ALTRI PROGRAMMI
                  </span>
                </div>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  🔌 Server API Standard OpenAI & Ollama
                </h4>
                <p style={{ margin: 0, fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.45 }}>
                  Avviando il server (:8000), qualsiasi software esterno come <strong>Visual Studio Code</strong> (Continue, Cline, Roo Code), <strong>Cursor</strong>, <strong>Windsurf</strong>, <strong>Open WebUI</strong> o script Python può connettersi a SigmaEngine come se fosse OpenAI o Ollama.
                </p>
              </div>
              <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.7rem', color: '#6366f1', fontWeight: 700 }}>
                <CheckCheck size={14} color="#6366f1" />
                <span>Interoperabilità istantanea con zero configurazioni complesse.</span>
              </div>
            </div>
          </div>

          {/* Endpoints Table Strip (Like LM Studio Server Route List) */}
          <div style={{
            padding: '14px',
            borderRadius: '12px',
            background: innerCardBg,
            border: innerCardBorder,
            marginBottom: '16px'
          }}>
            <div style={{ fontSize: '0.74rem', fontWeight: 800, color: titleColor, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Radio size={14} color="#00f2fe" />
              <span>Route API Esportate da SigmaEngine (:8000)</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {/* Route 1: OpenAI Chat Completions */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                borderRadius: '8px',
                background: isLight ? '#ffffff' : '#07090e',
                border: innerCardBorder,
                flexWrap: 'wrap',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.64rem', fontWeight: 800, color: '#10a37f', background: 'rgba(16, 163, 127, 0.15)', padding: '2px 6px', borderRadius: '4px' }}>POST</span>
                  <code style={{ fontSize: '0.78rem', color: titleColor, fontWeight: 700 }}>http://localhost:8000/v1/chat/completions</code>
                  <span style={{ fontSize: '0.68rem', color: subtitleColor }}>Standard OpenAI Chat (Streaming SSE)</span>
                </div>
                <button
                  onClick={() => copyKeyToClipboard('route_openai_chat', 'http://localhost:8000/v1/chat/completions')}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '6px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {copiedKey === 'route_openai_chat' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />} Copia URL
                </button>
              </div>

              {/* Route 2: OpenAI Models List */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                borderRadius: '8px',
                background: isLight ? '#ffffff' : '#07090e',
                border: innerCardBorder,
                flexWrap: 'wrap',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.64rem', fontWeight: 800, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.15)', padding: '2px 6px', borderRadius: '4px' }}>GET</span>
                  <code style={{ fontSize: '0.78rem', color: titleColor, fontWeight: 700 }}>http://localhost:8000/v1/models</code>
                  <span style={{ fontSize: '0.68rem', color: subtitleColor }}>Rilevamento Modelli Disponibili</span>
                </div>
                <button
                  onClick={() => copyKeyToClipboard('route_openai_models', 'http://localhost:8000/v1/models')}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '6px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {copiedKey === 'route_openai_models' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />} Copia URL
                </button>
              </div>

              {/* Route 3: Ollama Chat API */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                borderRadius: '8px',
                background: isLight ? '#ffffff' : '#07090e',
                border: innerCardBorder,
                flexWrap: 'wrap',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.64rem', fontWeight: 800, color: '#00d2ff', background: 'rgba(0, 210, 255, 0.15)', padding: '2px 6px', borderRadius: '4px' }}>POST</span>
                  <code style={{ fontSize: '0.78rem', color: titleColor, fontWeight: 700 }}>http://localhost:8000/api/chat</code>
                  <span style={{ fontSize: '0.68rem', color: subtitleColor }}>Standard Ollama Protocol (NDJSON Stream)</span>
                </div>
                <button
                  onClick={() => copyKeyToClipboard('route_ollama_chat', 'http://localhost:8000/api/chat')}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '6px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {copiedKey === 'route_ollama_chat' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />} Copia URL
                </button>
              </div>
            </div>
          </div>

          {/* Developer Integration & Code Exporter (LM Studio Style) */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Code size={16} color="#00f2fe" />
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: titleColor }}>
                  Generatore di Configurazione & Snippet per Software Esterni
                </span>
              </div>

              {/* Model Target Selector */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.68rem', color: subtitleColor, fontWeight: 700 }}>Modello Esportato:</span>
                <select
                  value={selectedGuideModel}
                  onChange={e => setSelectedGuideModel(e.target.value)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '8px',
                    background: innerCardBg,
                    border: '1px solid rgba(0, 242, 254, 0.4)',
                    color: titleColor,
                    fontSize: '0.74rem',
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

            {/* Integration Tabs Switcher */}
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '10px' }}>
              {[
                { id: 'continue', label: '🧩 Continue (VS Code)' },
                { id: 'cline', label: '🤖 Cline / Roo Code' },
                { id: 'copilot', label: '🚀 Cursor / Copilot' },
                { id: 'python', label: '🐍 Python SDK' },
                { id: 'node', label: '📦 Node.js / TS' },
                { id: 'curl', label: '💻 cURL Test' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveVsCodeTab(tab.id)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '8px',
                    fontSize: '0.72rem',
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

            {/* TAB CONTENT: CONTINUE */}
            {activeVsCodeTab === 'continue' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <p style={{ margin: 0, fontSize: '0.73rem', color: subtitleColor }}>
                    Incolla questo blocco nel file di configurazione di Continue (<code style={{ color: '#00f2fe' }}>~/.continue/config.json</code>):
                  </p>
                  <button
                    onClick={downloadContinueConfig}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                      border: 'none',
                      color: '#000',
                      fontSize: '0.7rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    <Download size={11} /> Scarica config.json
                  </button>
                </div>
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
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
                <div style={{ padding: '8px 12px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder }}>
                  <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>API PROVIDER</div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>OpenAI Compatible</div>
                </div>
                <div style={{ padding: '8px 12px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>BASE URL</div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00f2fe', marginTop: '2px' }}>http://localhost:8000/v1</div>
                  </div>
                  <button onClick={() => copyKeyToClipboard('cline_base', 'http://localhost:8000/v1')} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                    {copiedKey === 'cline_base' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                  </button>
                </div>
                <div style={{ padding: '8px 12px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>API KEY</div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>sigma</div>
                  </div>
                  <button onClick={() => copyKeyToClipboard('cline_key', 'sigma')} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                    {copiedKey === 'cline_key' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                  </button>
                </div>
                <div style={{ padding: '8px 12px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>MODEL ID</div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#00d2ff', marginTop: '2px' }}>{selectedGuideModel}</div>
                  </div>
                  <button onClick={() => copyKeyToClipboard('cline_model', selectedGuideModel)} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                    {copiedKey === 'cline_model' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                  </button>
                </div>
              </div>
            )}

            {/* TAB CONTENT: CURSOR / COPILOT */}
            {activeVsCodeTab === 'copilot' && (
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
              }}>{`# Variabili di ambiente per Cursor, Windsurf, Aider o terminale:
export OPENAI_BASE_URL="http://localhost:8000/v1"
export OPENAI_API_KEY="sigma"
export OPENAI_MODEL="${selectedGuideModel}"`}</pre>
            )}

            {/* TAB CONTENT: PYTHON SDK */}
            {activeVsCodeTab === 'python' && (
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

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sigma")
response = client.chat.completions.create(
    model="${selectedGuideModel}",
    messages=[{"role": "user", "content": "Ciao da Visual Studio Code!"}],
    stream=True
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`}</pre>
            )}

            {/* TAB CONTENT: NODE.JS / TYPESCRIPT */}
            {activeVsCodeTab === 'node' && (
              <pre style={{
                padding: '12px 14px',
                borderRadius: '10px',
                background: '#07090e',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: '#38bdf8',
                fontSize: '0.74rem',
                fontFamily: 'Consolas, monospace',
                overflowX: 'auto',
                margin: 0
              }}>{`import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:8000/v1',
  apiKey: 'sigma'
});

const stream = await client.chat.completions.create({
  model: '${selectedGuideModel}',
  messages: [{ role: 'user', content: 'Ciao da Node.js!' }],
  stream: true
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || '');
}`}</pre>
            )}

            {/* TAB CONTENT: CURL */}
            {activeVsCodeTab === 'curl' && (
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
            )}
          </div>
        </div>

        {/* ===================================================================== */}
        {/* DEFAULT ENGINE INFERENCE & CONTEXT PARAMETERS (STUDIO & SERVER FALLBACK) */}
        {/* ===================================================================== */}
        <div style={{
          padding: '18px 20px',
          borderRadius: '16px',
          background: cardBg,
          border: '1px solid rgba(250, 160, 60, 0.35)',
          boxShadow: cardShadow,
          marginBottom: '16px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '30px',
                height: '30px',
                borderRadius: '8px',
                background: 'rgba(250, 160, 60, 0.15)',
                border: '1px solid rgba(250, 160, 60, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Sliders size={16} color="#faa03c" />
              </div>
              <div>
                <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                  ⚙️ Parametri di Inferenza Predefiniti del Motore (Sigma Studio & Fallback Server :8000)
                </h4>
                <p style={{ margin: 0, fontSize: '0.72rem', color: subtitleColor }}>
                  Controllano la temperatura, il campionamento (Top_P) e la finestra di contesto caricata in VRAM per le chat/agenti interni e come valori di default per le richieste al server :8000.
                </p>
              </div>
            </div>

            <button
              onClick={saveAllConfig}
              disabled={saving}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #faa03c, #f97316)',
                border: 'none',
                color: '#000',
                fontSize: '0.72rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Save size={12} /> Applica al Motore
            </button>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: '14px'
          }}>
            {/* Box 1: Temperatura & Campionamento */}
            <div style={{ padding: '14px', borderRadius: '12px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff', marginBottom: '10px' }}>
                🌡️ Temperatura & Campionamento Statistico
              </div>

              {/* Temperature Slider */}
              <div style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: titleColor }}>Temperatura</label>
                  <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff' }}>{parameters.temperature}</span>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.62rem', color: subtitleColor, marginTop: '2px' }}>
                  <span>0.0 (Deterministico / Codice)</span>
                  <span>0.7 (Bilanciato)</span>
                  <span>1.0 (Creativo)</span>
                </div>
              </div>

              {/* Top P Slider */}
              <div style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: titleColor }}>Top_P (Nucleus Sampling)</label>
                  <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#bc8cff' }}>{parameters.top_p}</span>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: titleColor }}>Penalità di Ripetizione</label>
                  <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#3fb950' }}>{parameters.repeat_penalty}</span>
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

            {/* Box 2: Finestra di Contesto & Token */}
            <div style={{ padding: '14px', borderRadius: '12px', background: innerCardBg, border: innerCardBorder }}>
              <div style={{ fontSize: '0.74rem', fontWeight: 800, color: '#faa03c', marginBottom: '10px' }}>
                💾 Finestra di Contesto VRAM & Limite Token
              </div>

              {/* Num Ctx */}
              <div style={{ marginBottom: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: titleColor }}>Contesto Massimo (num_ctx)</label>
                  <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#faa03c' }}>{parameters.num_ctx.toLocaleString()} token</span>
                </div>
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '4px' }}>
                  {[8192, 16384, 32768, 65536, 131072, 262144].map(ctx => (
                    <button
                      key={ctx}
                      onClick={() => setParameters(p => ({ ...p, num_ctx: ctx }))}
                      style={{
                        padding: '3px 7px',
                        borderRadius: '6px',
                        fontSize: '0.66rem',
                        fontWeight: 700,
                        border: 'none',
                        cursor: 'pointer',
                        background: parameters.num_ctx === ctx ? '#faa03c' : (isLight ? '#ffffff' : '#07090e'),
                        color: parameters.num_ctx === ctx ? '#000000' : subtitleColor
                      }}
                    >
                      {ctx >= 1000 ? `${ctx / 1024}K` : ctx}
                    </button>
                  ))}
                </div>
                <span style={{ fontSize: '0.62rem', color: subtitleColor }}>Allocazione memoria KV Cache in VRAM/RAM</span>
              </div>

              {/* Max Output Tokens */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <label style={{ fontSize: '0.72rem', fontWeight: 700, color: titleColor }}>Max Token di Risposta</label>
                  <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff' }}>{parameters.max_tokens.toLocaleString()} token</span>
                </div>
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                  {[4096, 8192, 16384, 32768, 65536].map(tok => (
                    <button
                      key={tok}
                      onClick={() => setParameters(p => ({ ...p, max_tokens: tok }))}
                      style={{
                        padding: '3px 7px',
                        borderRadius: '6px',
                        fontSize: '0.66rem',
                        fontWeight: 700,
                        border: 'none',
                        cursor: 'pointer',
                        background: parameters.max_tokens === tok ? '#00d2ff' : (isLight ? '#ffffff' : '#07090e'),
                        color: parameters.max_tokens === tok ? '#000000' : subtitleColor
                      }}
                    >
                      {tok >= 1024 ? `${tok / 1024}K` : tok}
                    </button>
                  ))}
                </div>
                <span style={{ fontSize: '0.62rem', color: subtitleColor, marginTop: '4px', display: 'block' }}>Limite massimo di generazione per singola risposta</span>
              </div>
            </div>
          </div>
        </div>

        {/* Interactive Live Server SSE Probe Tester (LM Studio Playground Style) */}
        <div style={{
          padding: '16px 20px',
          borderRadius: '14px',
          background: cardBg,
          border: '1px solid rgba(0, 242, 254, 0.25)',
          boxShadow: cardShadow
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Zap size={16} color="#00f2fe" />
              <h4 style={{ margin: 0, fontSize: '0.88rem', fontWeight: 800, color: titleColor }}>
                Test Live Risposta Server (:8000)
              </h4>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                onClick={() => setLiveTestState(p => ({ ...p, protocol: 'openai' }))}
                style={{
                  padding: '3px 8px',
                  borderRadius: '6px',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: liveTestState.protocol === 'openai' ? '#10a37f' : innerCardBg,
                  color: liveTestState.protocol === 'openai' ? '#fff' : subtitleColor
                }}
              >
                OpenAI (/v1)
              </button>
              <button
                onClick={() => setLiveTestState(p => ({ ...p, protocol: 'ollama' }))}
                style={{
                  padding: '3px 8px',
                  borderRadius: '6px',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: liveTestState.protocol === 'ollama' ? '#00d2ff' : innerCardBg,
                  color: liveTestState.protocol === 'ollama' ? '#fff' : subtitleColor
                }}
              >
                Ollama (/api)
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
            <input
              type="text"
              value={liveTestState.prompt}
              onChange={e => setLiveTestState(p => ({ ...p, prompt: e.target.value }))}
              placeholder="Inserisci un prompt di test..."
              style={{
                flex: 1,
                padding: '7px 10px',
                borderRadius: '8px',
                background: innerCardBg,
                border: innerCardBorder,
                color: titleColor,
                fontSize: '0.76rem',
                outline: 'none'
              }}
            />
            <button
              onClick={runLiveServerTest}
              disabled={liveTestState.isTesting}
              style={{
                padding: '7px 14px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                border: 'none',
                color: '#000',
                fontSize: '0.74rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              {liveTestState.isTesting ? <RefreshCw size={12} className="spin" /> : <Play size={12} />}
              Test Streaming
            </button>
          </div>

          {(liveTestState.outputText || liveTestState.isTesting || liveTestState.error) && (
            <div style={{
              padding: '12px',
              borderRadius: '10px',
              background: '#07090e',
              border: '1px solid rgba(0, 242, 254, 0.3)',
              fontSize: '0.76rem',
              color: '#e2e8f0',
              lineHeight: 1.45
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.66rem', color: subtitleColor }}>
                <span>Protocollo: <strong>{liveTestState.protocol.toUpperCase()}</strong> • Modello: <strong style={{ color: '#00f2fe' }}>{selectedGuideModel}</strong></span>
                {liveTestState.ttft && <span>TTFT: <strong style={{ color: '#00f2fe' }}>{liveTestState.ttft}ms</strong> • Totale: <strong style={{ color: '#3fb950' }}>{liveTestState.latency || '...'}ms</strong></span>}
              </div>
              {liveTestState.error ? (
                <div style={{ color: '#ef4444' }}>❌ {liveTestState.error}</div>
              ) : (
                <div style={{ whiteSpace: 'pre-wrap' }}>
                  {liveTestState.outputText}
                  {liveTestState.isTesting && <span style={{ display: 'inline-block', width: '6px', height: '12px', background: '#00f2fe', marginLeft: '3px', verticalAlign: 'middle', animation: 'blink 1s infinite' }} />}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 2: 🐙 MOTORI OPEN-SOURCE & PROVIDERS SCARICABILI DA GITHUB */}
      {/* ========================================================================= */}
      <div id="section-github" style={{ marginBottom: '36px', scrollMarginTop: '65px' }}>
        {/* Section Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'rgba(99, 102, 241, 0.15)',
              border: '1px solid rgba(99, 102, 241, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(99, 102, 241, 0.2)'
            }}>
              <GithubIcon size={20} color="#6366f1" />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: titleColor }}>
                2. 🐙 Motori & Providers Open-Source (GitHub & Software Locali)
              </h2>
              <p style={{ margin: 0, fontSize: '0.74rem', color: subtitleColor }}>
                I migliori motori di inferenza e framework locali della community. Puoi scaricarli da GitHub o dal sito ufficiale, avviarli sul tuo PC e collegarli a Sigma Studio in 1 clic.
              </p>
            </div>
          </div>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#6366f1', background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '3px 10px', borderRadius: '10px' }}>
            {GITHUB_ENGINES.length} Motori Curati
          </span>
        </div>

        {/* GitHub Engines Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(295px, 1fr))',
          gap: '14px'
        }}>
          {GITHUB_ENGINES.map(engine => {
            const IconComp = ProviderIcons[engine.iconKey] || ProviderIcons.sigma_engine;
            const isCurrentlyActive = (engine.providerId === 'ailoflow' && activeProvider === 'ailoflow') ||
                                      (engine.providerId === 'ollama' && activeProvider === 'ollama') ||
                                      (engine.providerId === 'lmstudio' && activeProvider === 'lmstudio') ||
                                      (engine.providerId === 'custom' && activeProvider === 'custom' && providerSettings.custom?.api_url?.includes(engine.defaultPort));

            return (
              <div
                key={engine.id}
                style={{
                  padding: '16px',
                  borderRadius: '14px',
                  background: cardBg,
                  border: isCurrentlyActive ? `2px solid ${engine.color}` : cardBorder,
                  boxShadow: isCurrentlyActive ? `0 4px 18px ${engine.color}25` : cardShadow,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '12px',
                  transition: 'all 0.2s ease',
                  position: 'relative'
                }}
              >
                <div>
                  {/* Card Top */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '10px',
                        background: `${engine.color}15`,
                        border: `1px solid ${engine.color}35`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0
                      }}>
                        <IconComp size={20} color={engine.color} />
                      </div>
                      <div>
                        <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: titleColor }}>
                          {engine.name}
                        </h3>
                        <span style={{ fontSize: '0.62rem', fontWeight: 800, color: engine.color, letterSpacing: '0.4px' }}>
                          {engine.badge}
                        </span>
                      </div>
                    </div>

                    {isCurrentlyActive && (
                      <span style={{
                        fontSize: '0.62rem',
                        fontWeight: 800,
                        color: '#3fb950',
                        background: 'rgba(63, 185, 80, 0.15)',
                        border: '1px solid rgba(63, 185, 80, 0.3)',
                        padding: '2px 6px',
                        borderRadius: '6px'
                      }}>
                        IN USO
                      </span>
                    )}
                  </div>

                  <p style={{ margin: '0 0 6px 0', fontSize: '0.74rem', fontWeight: 600, color: titleColor, lineHeight: 1.35 }}>
                    {engine.tagline}
                  </p>
                  <p style={{ margin: 0, fontSize: '0.7rem', color: subtitleColor, lineHeight: 1.4 }}>
                    {engine.description}
                  </p>

                  <div style={{
                    marginTop: '8px',
                    padding: '5px 8px',
                    borderRadius: '6px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    fontSize: '0.68rem',
                    color: subtitleColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <span>Porta Predefinita: <strong style={{ color: engine.color }}>:{engine.defaultPort}</strong></span>
                    <span style={{ fontSize: '0.64rem', color: subtitleColor }}>{engine.protocol}</span>
                  </div>
                </div>

                {/* Card Actions (GitHub Repo, Download, Connect in Sigma) */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderTop: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.05)', paddingTop: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <a
                      href={engine.repoUrl}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        flex: 1,
                        padding: '5px 8px',
                        borderRadius: '8px',
                        background: innerCardBg,
                        border: innerCardBorder,
                        color: titleColor,
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        textDecoration: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px'
                      }}
                    >
                      <GithubIcon size={12} /> GitHub Repo <ArrowUpRight size={10} />
                    </a>

                    <a
                      href={engine.releasesUrl}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        padding: '5px 10px',
                        borderRadius: '8px',
                        background: `${engine.color}15`,
                        border: `1px solid ${engine.color}35`,
                        color: engine.color,
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        textDecoration: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '3px'
                      }}
                    >
                      <Download size={11} /> Download
                    </a>
                  </div>

                  <button
                    onClick={() => handleConnectGitHubEngine(engine)}
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      borderRadius: '8px',
                      background: isCurrentlyActive ? 'rgba(63, 185, 80, 0.15)' : `linear-gradient(135deg, ${engine.color}25, ${engine.color}10)`,
                      border: isCurrentlyActive ? '1px solid rgba(63, 185, 80, 0.4)' : `1px solid ${engine.color}40`,
                      color: isCurrentlyActive ? '#3fb950' : engine.color,
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '5px'
                    }}
                  >
                    <Zap size={12} />
                    {isCurrentlyActive ? 'Connesso come Provider Attivo' : `⚡ Collega ${engine.name} in Sigma Studio`}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SECTION 3: ☁️ CLOUD PROVIDERS & API HUB */}
      {/* ========================================================================= */}
      <div id="section-cloud" style={{ marginBottom: '36px', scrollMarginTop: '65px' }}>
        {/* Section Header & Filters */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'rgba(16, 163, 127, 0.15)',
              border: '1px solid rgba(16, 163, 127, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(16, 163, 127, 0.2)'
            }}>
              <Key size={20} color="#10a37f" />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: titleColor }}>
                3. ☁️ Cloud Providers & API Vault (OpenAI, Claude, DeepSeek, Gemini, ecc.)
              </h2>
              <p style={{ margin: 0, fontSize: '0.74rem', color: subtitleColor }}>
                Configura chiavi API, modelli e parametri di connessione per i principali provider cloud globali e gateway personalizzati.
              </p>
            </div>
          </div>

          {/* Search Box */}
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
              placeholder="Cerca provider o modello..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: titleColor,
                fontSize: '0.74rem',
                outline: 'none',
                width: '160px'
              }}
            />
          </div>
        </div>

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
            { id: 'local', label: '🏠 Locali (4)' },
            { id: 'cloud', label: '⚡ Top Cloud (4)' },
            { id: 'fast', label: '🚀 Ultra-Fast (3)' },
            { id: 'hub', label: '🌐 Hub Multi-Modello (3)' },
            { id: 'chinese', label: '🎋 Asia (2)' },
            { id: 'custom', label: '🛠️ Custom API (1)' }
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
                  color: active ? '#000000' : subtitleColor
                }}
              >
                {cat.label}
              </button>
            );
          })}
        </div>

        {/* Providers Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))',
          gap: '14px'
        }}>
          {filteredProviders.map(prov => {
            const pState = providerSettings[prov.id] || {};
            const isSelected = activeProvider === prov.id;
            const hasKey = prov.id === 'ollama' || prov.id === 'sigma_engine' || prov.id === 'lmstudio' ? true : (pState.has_api_key || (pState.api_key && pState.api_key.trim().length > 0));
            const isVisible = visibleKeys[prov.id];
            const test = testResults[prov.id];
            const isTesting = testingProvider === prov.id;
            const IconComp = ProviderIcons[prov.id] || ProviderIcons.ollama;

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
                  border: isSelected 
                    ? `2px solid ${prov.color}` 
                    : (isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.07)'),
                  boxShadow: isSelected ? `0 4px 16px ${prov.color}20` : cardShadow,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '10px'
                }}
              >
                <div>
                  {/* Card Header */}
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
                        <span style={{ fontSize: '0.6rem', fontWeight: 800, color: prov.color, letterSpacing: '0.4px' }}>
                          {prov.badge}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setActiveProvider(prov.id);
                        if (pState.custom_model || pState.model) {
                          setActiveModel(pState.custom_model || pState.model);
                        } else if (prov.default_model) {
                          setActiveModel(prov.default_model);
                        }
                      }}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        fontSize: '0.66rem',
                        fontWeight: 800,
                        cursor: 'pointer',
                        background: isSelected ? prov.color : innerCardBg,
                        border: isSelected ? 'none' : innerCardBorder,
                        color: isSelected ? '#000000' : subtitleColor,
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {isSelected ? '✓ Principale' : 'Imposta'}
                    </button>
                  </div>

                  <p style={{ margin: '0 0 10px 0', fontSize: '0.72rem', color: subtitleColor, lineHeight: 1.35 }}>
                    {prov.hint}
                  </p>

                  {/* Model Selector */}
                  <div style={{ marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor }}>
                        Modello
                      </label>
                      {prov.id === 'ollama' && (
                        <button
                          onClick={() => fetchOllamaModels(true)}
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
                        if (isSelected) setActiveModel(mod);
                      }}
                      isLight={isLight}
                      titleColor={titleColor}
                      subtitleColor={subtitleColor}
                      innerCardBg={innerCardBg}
                      innerCardBorder={innerCardBorder}
                    />
                  </div>

                  {/* API Key Vault Input (if required) */}
                  {prov.api_key_required && (
                    <div style={{ marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'flex', alignItems: 'center', gap: '3px' }}>
                          <Lock size={10} color={hasKey ? '#3fb950' : subtitleColor} />
                          Chiave API / Token
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
                          placeholder={pState.has_api_key ? '•••••••••••••••• (Salvata nel Vault)' : prov.key_placeholder}
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

                  {/* Endpoint Override (for Ollama, LM Studio, Custom or Proxies) */}
                  {(prov.id === 'ollama' || prov.id === 'custom' || prov.id === 'ailoflow' || prov.id === 'lmstudio') && (
                    <div style={{ marginBottom: '8px' }}>
                      <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'block', marginBottom: '3px' }}>
                        Endpoint URL
                      </label>
                      <input
                        type="text"
                        placeholder={prov.endpoint || prov.api_url || 'http://localhost:1234/v1'}
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
      </div>
    </div>
  );
}
