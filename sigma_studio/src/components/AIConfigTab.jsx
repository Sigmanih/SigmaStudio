import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { 
  Cpu, Key, ShieldCheck, Zap, RefreshCw, Save, CheckCircle2, 
  AlertCircle, Sliders, ExternalLink, Copy, Check, Eye, EyeOff, 
  Search, Server, Database, Download, Trash2, ChevronDown, Lock, Sparkles,
  Code, Terminal, Layers, Globe, Play, CheckCircle, FileText, Settings, Share2,
  Monitor, X, ChevronRight, Wifi, ArrowUpRight, HardDrive, Box,
  Activity, ArrowRight, CornerDownRight, CheckSquare, Power, Radio,
  Maximize2, SlidersHorizontal, CheckCheck, HelpCircle, Edit3, List, Trophy, Gauge, Award, CheckCircle as CheckIcon
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import CustomSelect from './common/CustomSelect';
import { getModelSpecs, getModelChatSpeed, detectModelFamily, FAMILY_CONFIG, isSigmanihModel } from './Chat/core/modelSpecsHelper';

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
  custom: ({ size = 20, color = '#eab308' }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke={color} strokeWidth="1.8" fill={`${color}15`} />
      <path d="M12 7V17M7 12H17" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
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
    label: 'OpenRouter (Multi-Model Router)',
    category: 'cloud',
    color: '#6366f1',
    badge: '300+ MODELLI',
    endpoint: '',
    api_url: 'https://openrouter.ai/api/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'sk-or-v1-...',
    docs_url: 'https://openrouter.ai/keys',
    hint: 'Hub unificato con oltre 300 modelli (Claude, DeepSeek, Llama, Qwen).',
    default_model: 'anthropic/claude-3.5-sonnet',
    popular_models: ['anthropic/claude-3.5-sonnet', 'deepseek/deepseek-r1', 'meta-llama/llama-3.3-70b-instruct', 'google/gemini-2.0-flash-thinking-exp:free', 'qwen/qwen-2.5-coder-32b-instruct']
  },
  mistral: {
    id: 'mistral',
    label: 'Mistral AI (La Plateforme)',
    category: 'cloud',
    color: '#ff7000',
    badge: 'LE CHAT & LARGE',
    endpoint: '',
    api_url: 'https://api.mistral.ai/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'Bearer token Mistral...',
    docs_url: 'https://console.mistral.ai/api-keys',
    hint: 'Mistral Large 2, Mistral Small 3, Codestral e Pixtral 12B.',
    default_model: 'mistral-large-latest',
    popular_models: ['mistral-large-latest', 'mistral-small-latest', 'codestral-latest', 'pixtral-12b-2409', 'open-mistral-nemo']
  },
  xai: {
    id: 'xai',
    label: 'xAI (Grok)',
    category: 'cloud',
    color: '#ffffff',
    badge: 'GROK 2',
    endpoint: '',
    api_url: 'https://api.x.ai/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'xai-...',
    docs_url: 'https://console.x.ai',
    hint: 'Grok-2 e Grok-2 Vision.',
    default_model: 'grok-2-latest',
    popular_models: ['grok-2-latest', 'grok-2-vision-latest', 'grok-beta']
  },
  perplexity: {
    id: 'perplexity',
    label: 'Perplexity AI (Sonar Search)',
    category: 'cloud',
    color: '#06b6d4',
    badge: 'LIVE WEB SEARCH',
    endpoint: '',
    api_url: 'https://api.perplexity.ai/chat/completions',
    api_key_required: true,
    key_placeholder: 'pplx-...',
    docs_url: 'https://www.perplexity.ai/settings/api',
    hint: 'Sonar con ricerca web integrata in tempo reale e citazione fonti.',
    default_model: 'sonar-reasoning-pro',
    popular_models: ['sonar-reasoning-pro', 'sonar-reasoning', 'sonar-pro', 'sonar']
  },
  together: {
    id: 'together',
    label: 'Together AI',
    category: 'cloud',
    color: '#3b82f6',
    badge: 'OPEN SOURCE CLOUD',
    endpoint: '',
    api_url: 'https://api.together.xyz/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'together-...',
    docs_url: 'https://api.together.ai/settings/api-keys',
    hint: 'DeepSeek R1, Llama 3.3 70B, Qwen 2.5 Coder e Flux Image.',
    default_model: 'deepseek-ai/DeepSeek-R1',
    popular_models: ['deepseek-ai/DeepSeek-R1', 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'Qwen/Qwen2.5-Coder-32B-Instruct', 'mistralai/Mixtral-8x22B-Instruct-v0.1']
  },
  qwen: {
    id: 'qwen',
    label: 'Alibaba Cloud (DashScope / Qwen)',
    category: 'cloud',
    color: '#8b5cf6',
    badge: 'QWEN MAX & CODER',
    endpoint: '',
    api_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    api_key_required: true,
    key_placeholder: 'sk-...',
    docs_url: 'https://dashscope.console.aliyun.com/apiKey',
    hint: 'Qwen-Max, Qwen-Plus, Qwen2.5-Coder e Qwen-VL.',
    default_model: 'qwen-max-latest',
    popular_models: ['qwen-max-latest', 'qwen-plus', 'qwen-turbo', 'qwen2.5-coder-32b-instruct', 'qwen-vl-max']
  },
  glm: {
    id: 'glm',
    label: 'Zhipu AI (GLM-4)',
    category: 'cloud',
    color: '#0284c7',
    badge: 'GLM-4 & LONG CONTEXT',
    endpoint: '',
    api_url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    api_key_required: true,
    key_placeholder: 'API Key Zhipu...',
    docs_url: 'https://open.bigmodel.cn/usercenter/apikeys',
    hint: 'GLM-4-Plus, GLM-4-0520 e GLM-4-Flash.',
    default_model: 'glm-4-plus',
    popular_models: ['glm-4-plus', 'glm-4-air', 'glm-4-flash', 'glm-4-long']
  },
  custom: {
    id: 'custom',
    label: 'Custom OpenAI / Local Server',
    category: 'custom',
    color: '#eab308',
    badge: 'OPEN COMPATIBLE',
    endpoint: 'http://localhost:8080',
    api_url: 'http://localhost:8080/v1/chat/completions',
    api_key_required: false,
    key_placeholder: 'Opzionale: Bearer token...',
    docs_url: '',
    hint: 'Qualsiasi server compatibile OpenAI (vLLM, LocalAI, llama.cpp, KoboldCpp, Tabby).',
    default_model: 'default',
    popular_models: ['default', 'qwen', 'llama3', 'mistral', 'deepseek']
  }
};

export default function AIConfigTab() {
  const { theme } = useApp();
  const isLight = theme === 'light';

  // Theme Styles
  const cardBg = isLight ? '#f4eedb' : 'rgba(13, 20, 36, 0.75)';
  const innerCardBg = isLight ? 'rgba(235, 225, 200, 0.6)' : 'rgba(9, 13, 22, 0.65)';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.4)' : '1px solid rgba(0, 242, 254, 0.15)';
  const innerCardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.25)' : '1px solid rgba(255, 255, 255, 0.06)';
  const titleColor = isLight ? '#111827' : '#ffffff';
  const subtitleColor = isLight ? '#4b5563' : '#a0a6bc';
  const cardShadow = isLight ? '0 2px 12px rgba(190, 160, 110, 0.1)' : '0 6px 24px rgba(0, 0, 0, 0.45)';

  // TWO MAIN TABS: 'engine_server' (Output / Proxy) | 'external_providers' (Input / Aggregation)
  const [mainHubTab, setMainHubTab] = useState('engine_server');

  // External providers sub-filter
  const [activeCategory, setActiveCategory] = useState('all'); // 'all' | 'cloud' | 'local'
  const [searchQuery, setSearchQuery] = useState('');

  // Callable Models List Search & Filter in Tab 1
  const [callableSearch, setCallableSearch] = useState('');
  const [callableFilter, setCallableFilter] = useState('all'); // 'all' | 'local' | 'vram' | 'cloud'

  // Central Config State
  const [activeProvider, setActiveProvider] = useState('sigma_engine');
  const [activeModel, setActiveModel] = useState('sigma:latest');
  const [providerSettings, setProviderSettings] = useState({});
  const [localDiskModels, setLocalDiskModels] = useState([]);
  const [ollamaLocalModels, setOllamaLocalModels] = useState([]);

  // Server Output Custom Configuration (Port, Host, Proxy Alias, Proxy Target Model, SSL/HTTPS)
  const [serverPort, setServerPort] = useState(8000);
  const [serverHost, setServerHost] = useState('localhost');
  const [proxyAlias, setProxyAlias] = useState('sigma');
  const [selectedGuideModel, setSelectedGuideModel] = useState('sigma');
  const [sslEnabled, setSslEnabled] = useState(false);

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

  // VS Code & SigmaEngine Server Interoperability State
  const [serverInfo, setServerInfo] = useState(null);
  const [providerServerEnabled, setProviderServerEnabled] = useState(true);
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

  // Dynamic Base URL calculated from state
  const effectiveBaseUrl = useMemo(() => {
    const host = serverHost || 'localhost';
    const port = serverPort || 8000;
    const proto = sslEnabled ? 'https' : 'http';
    return `${proto}://${host}:${port}`;
  }, [serverHost, serverPort, sslEnabled]);


  // Copy helper
  const copyKeyToClipboard = (keyId, textToCopy) => {
    navigator.clipboard.writeText(textToCopy);
    setCopiedKey(keyId);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Fetch local disk models from /api/models/local/list
  const fetchLocalDiskModels = useCallback(async () => {
    try {
      const res = await fetch('/api/models/local/list');
      const data = await res.json();
      if (data.success && Array.isArray(data.models)) {
        setLocalDiskModels(data.models);
      }
    } catch (e) {
      console.debug("Local disk models fetch:", e);
    }
  }, []);

  // Fetch server info
  const fetchServerInfo = useCallback(async () => {
    try {
      const res = await fetch('/api/engine/server_info');
      const data = await res.json();
      if (data.success) {
        setServerInfo(data);
        if (data.provider_server_enabled !== undefined) {
          setProviderServerEnabled(data.provider_server_enabled);
        }
        if (data.port) setServerPort(data.port);
        if (data.host) setServerHost(data.host);
        if (data.proxy_alias) setProxyAlias(data.proxy_alias);
        if (data.proxy_model) setSelectedGuideModel(data.proxy_model);
      }
    } catch (e) {
      console.debug("Server info fetch:", e);
    }
  }, []);

  // Toggle provider server
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
          msg: `SigmaEngine Server ${data.provider_server_enabled ? `ABILITATO 🟢 (Port :${serverPort})` : 'DISABILITATO 🔴'}`
        });
        setTimeout(() => setSaveToast(null), 3500);
        fetchServerInfo();
      }
    } catch (err) {
      setSaveToast({ type: 'error', msg: `Errore toggle server: ${err.message}` });
      setTimeout(() => setSaveToast(null), 3500);
    }
  };

  // Build model options for CustomSelect & Registry Table (Local models only, no cloud, deduplicated)
  const allAvailableGuideModels = useMemo(() => {
    const list = [
      { 
        value: proxyAlias || 'sigma', 
        label: `⚡ ${proxyAlias || 'sigma'} (Proxy Principale - Modello Selezionato)`, 
        badge: 'PROXY ALIAS',
        desc: `Inoltra istantaneamente le richieste al modello selezionato (${selectedGuideModel || 'Auto'})`,
        color: '#00f2fe',
        category: 'proxy',
        isProxyOption: true
      },
      { 
        value: 'sigmaengine', 
        label: '⚡ sigmaengine (Auto-Risoluzione Dinamica)', 
        badge: 'AUTO ROUTER',
        desc: 'Risolve automaticamente il modello residente in memoria GPU/RAM o attivo nel motore',
        color: '#00d2ff',
        category: 'proxy',
        isProxyOption: true
      }
    ];

    const seenValues = new Set(['sigma', 'sigmaengine', (proxyAlias || '').toLowerCase()]);
    const residentName = (serverInfo?.resident_model && serverInfo.resident_model !== 'Nessun modello caricato') 
      ? serverInfo.resident_model 
      : null;

    // Helper to check if a model matches the resident model
    const matchesResident = (mName, mPath) => {
      if (!residentName) return false;
      const rLower = residentName.toLowerCase().replace(/\.gguf$/, '');
      const nLower = (mName || '').toLowerCase().replace(/\.gguf$/, '');
      if (rLower === nLower) return true;
      if (mPath && rLower.includes(mPath.toLowerCase())) return true;
      if (nLower && (nLower.includes(rLower) || rLower.includes(nLower))) return true;
      return false;
    };

    let residentIncluded = false;

    // 1. Add all local disk models (deduplicated)
    (localDiskModels || []).forEach(m => {
      const canonicalVal = m.clean_name || m.model_id || m.filename;
      if (!canonicalVal) return;
      
      const valKey = canonicalVal.toLowerCase().replace(/\.gguf$/, '');
      if (seenValues.has(valKey)) return;
      seenValues.add(valKey);

      const isRes = matchesResident(canonicalVal, m.path) || matchesResident(m.filename, m.path) || matchesResident(m.model_id, m.path);
      if (isRes) residentIncluded = true;

      const specs = getModelSpecs(canonicalVal, localDiskModels);
      const chatSpeed = getModelChatSpeed(canonicalVal, m) ?? (m.benchmark_summary?.tokens_per_sec || specs?.chatSpeed || null);
      const bm = m.benchmark_summary || specs?.benchmark || null;
      const hasBm = Boolean(bm && (bm.has_benchmarks || bm.score !== undefined || bm.overall_pass_rate !== undefined || bm.best_score !== undefined));
      const bmScore = hasBm ? (bm.score ?? bm.overall_pass_rate ?? bm.best_score ?? null) : null;
      const familyKey = detectModelFamily(m);
      const familyConf = FAMILY_CONFIG[familyKey] || FAMILY_CONFIG.altro;

      list.push({
        value: canonicalVal,
        label: `${isRes ? '🔥' : '🏠'} ${m.display_name || m.clean_name || m.filename}`,
        badge: isRes ? '🔥 IN VRAM' : (m.is_multimodal ? 'GGUF + VISION' : (m.format_tag || 'GGUF')),
        desc: `${m.size_label || specs?.size || 'Su Disco'}${m.quantization || specs?.quantization ? ` • ${m.quantization || specs?.quantization}` : ''}${m.parameter_size || specs?.params ? ` • Parametri: ${m.parameter_size || specs?.params}` : ''}`,
        color: isRes ? '#faa03c' : (familyConf.color || '#3fb950'),
        category: isRes ? 'vram' : 'local',
        isResident: isRes,
        sizeLabel: m.size_label || specs?.size,
        quant: m.quantization || specs?.quantization,
        params: m.parameter_size || specs?.params,
        isMultimodal: m.is_multimodal,
        filePath: m.path,
        family: familyConf,
        chatSpeed,
        benchmark: bm,
        hasBenchmark: hasBm,
        benchmarkScore: bmScore
      });
    });

    // 2. If resident model in VRAM was not in localDiskModels, add it explicitly
    if (residentName && !residentIncluded) {
      const rKey = residentName.toLowerCase().replace(/\.gguf$/, '');
      if (!seenValues.has(rKey)) {
        seenValues.add(rKey);
        const specs = getModelSpecs(residentName, localDiskModels);
        const chatSpeed = getModelChatSpeed(residentName) ?? specs?.chatSpeed;
        const bm = specs?.benchmark || null;
        const hasBm = Boolean(bm && (bm.has_benchmarks || bm.score !== undefined || bm.overall_pass_rate !== undefined));
        const bmScore = hasBm ? (bm.score ?? bm.overall_pass_rate ?? null) : null;
        const familyKey = detectModelFamily(residentName);
        const familyConf = FAMILY_CONFIG[familyKey] || FAMILY_CONFIG.altro;

        list.push({
          value: residentName,
          label: `🔥 ${residentName}`,
          badge: 'IN VRAM',
          desc: 'Modello attualmente residente e pronto in memoria GPU/RAM',
          color: '#faa03c',
          category: 'vram',
          isResident: true,
          sizeLabel: specs?.size,
          quant: specs?.quantization,
          params: specs?.params,
          family: familyConf,
          chatSpeed,
          benchmark: bm,
          hasBenchmark: hasBm,
          benchmarkScore: bmScore
        });
      }
    }

    return list;
  }, [serverInfo, localDiskModels, proxyAlias, selectedGuideModel]);

  // Filtered callable models for the table
  const filteredCallableModels = useMemo(() => {
    return allAvailableGuideModels.filter(item => {
      const matchCategory = callableFilter === 'all' || 
                            (callableFilter === 'local' && (item.category === 'local' || item.category === 'vram')) ||
                            (callableFilter === 'vram' && (item.category === 'vram' || item.isResident)) ||
                            (callableFilter === 'proxy' && item.category === 'proxy');
      const matchSearch = !callableSearch || 
                          item.value.toLowerCase().includes(callableSearch.toLowerCase()) ||
                          item.label.toLowerCase().includes(callableSearch.toLowerCase()) ||
                          (item.desc && item.desc.toLowerCase().includes(callableSearch.toLowerCase()));
      return matchCategory && matchSearch;
    });
  }, [allAvailableGuideModels, callableFilter, callableSearch]);

  // Set proxy model handler
  const handleSetProxyModel = (modelId) => {
    setSelectedGuideModel(modelId);
    setSaveToast({
      type: 'success',
      msg: `Modello "${modelId}" impostato come Proxy "${proxyAlias || 'sigma'}"! Ricordati di salvare. 🎯`
    });
    setTimeout(() => setSaveToast(null), 3500);
  };

  // Fetch initial config
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      if (data.success && data.config) {
        const cfg = data.config;
        setActiveProvider(cfg.active_provider || cfg.provider || 'sigma_engine');
        setActiveModel(cfg.active_model || cfg.model || 'sigma:latest');
        if (cfg.sigma_proxy_model) {
          setSelectedGuideModel(cfg.sigma_proxy_model);
        }
        if (cfg.provider_server_port) setServerPort(Number(cfg.provider_server_port));
        if (cfg.provider_server_host) setServerHost(cfg.provider_server_host);
        if (cfg.sigma_proxy_alias) setProxyAlias(cfg.sigma_proxy_alias);
        if (cfg.ssl_enabled !== undefined) setSslEnabled(Boolean(cfg.ssl_enabled));
        
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

  // Fetch hardware profile
  const fetchEngineProfile = useCallback(async () => {
    try {
      const res = await fetch('/api/engine/profile');
      const data = await res.json();
      if (data.success) {
        setHardwareProfile(data);
      }
    } catch (e) {}
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchServerInfo();
    fetchLocalDiskModels();
    fetchEngineProfile();
  }, [fetchConfig, fetchServerInfo, fetchLocalDiskModels, fetchEngineProfile]);

  // Save All Configuration to Server
  const saveAllConfig = async () => {
    setSaving(true);
    try {
      const payload = {
        active_provider: activeProvider,
        active_model: activeModel,
        provider: activeProvider,
        model: activeModel,
        sigma_proxy_model: selectedGuideModel,
        sigma_proxy_alias: proxyAlias,
        provider_server_port: Number(serverPort),
        server_port: Number(serverPort),
        provider_server_host: serverHost,
        server_host: serverHost,
        ssl_enabled: Boolean(sslEnabled),
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
          endpoint: pCfg.endpoint,
          api_url: pCfg.api_url,
          model: pCfg.custom_model || pCfg.model
        };
        if (pCfg.api_key && pCfg.api_key.trim()) {
          payload.providers[pId].api_key = pCfg.api_key.trim();
        }
      });

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success) {
        setSaveToast({ type: 'success', msg: 'Configurazione, Porte e Modello Proxy salvati con successo! 🚀' });
        fetchConfig();
        fetchServerInfo();
      } else {
        setSaveToast({ type: 'error', msg: data.error || 'Errore durante il salvataggio.' });
      }
    } catch (e) {
      setSaveToast({ type: 'error', msg: `Errore rete: ${e.message}` });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveToast(null), 4000);
    }
  };

  // Test single provider connectivity
  const testProviderConnection = async (pId) => {
    setTestingProvider(pId);
    setTestResults(prev => ({ ...prev, [pId]: { testing: true } }));
    const p = providerSettings[pId] || {};
    const t0 = performance.now();

    try {
      const res = await fetch('/api/test_provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: pId,
          api_key: p.api_key || '',
          endpoint: p.endpoint || '',
          api_url: p.api_url || '',
          model: p.custom_model || p.model || ''
        })
      });
      const data = await res.json();
      const latency = Math.round(performance.now() - t0);

      setTestResults(prev => ({
        ...prev,
        [pId]: {
          success: data.success,
          message: data.message || (data.success ? 'Connessione stabilita con successo!' : 'Connessione fallita.'),
          latency,
          models: data.models || []
        }
      }));
    } catch (e) {
      setTestResults(prev => ({
        ...prev,
        [pId]: {
          success: false,
          message: `Errore: ${e.message}`,
          latency: null
        }
      }));
    } finally {
      setTestingProvider(null);
    }
  };

  // Live Server SSE Tester
  const runLiveServerTest = async () => {
    setLiveTestState(prev => ({
      ...prev,
      isTesting: true,
      outputText: '',
      latency: null,
      ttft: null,
      error: null
    }));

    const t0 = performance.now();
    let ttftRecorded = false;

    try {
      const isOllama = liveTestState.protocol === 'ollama';
      const endpoint = isOllama ? `${effectiveBaseUrl}/api/chat` : `${effectiveBaseUrl}/v1/chat/completions`;
      const targetModel = selectedGuideModel || proxyAlias || 'sigma';

      const payload = isOllama
        ? { model: targetModel, messages: [{ role: 'user', content: liveTestState.prompt }], stream: true }
        : { model: targetModel, messages: [{ role: 'user', content: liveTestState.prompt }], stream: true };

      let response;
      let usedFallback = false;
      try {
        response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer sigma' },
          body: JSON.stringify(payload)
        });
      } catch (networkErr) {
        // If connection was refused to custom host/port (e.g. server running on :8000 but port 8001 was typed in field),
        // fallback to relative path on active running origin so in-browser streaming test works immediately.
        const fallbackEndpoint = isOllama ? '/api/chat' : '/v1/chat/completions';
        if (endpoint !== fallbackEndpoint) {
          try {
            response = await fetch(fallbackEndpoint, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer sigma' },
              body: JSON.stringify(payload)
            });
            usedFallback = true;
          } catch (fallbackErr) {
            throw new Error(`Connessione rifiutata verso ${endpoint}. Verifica che il server sia attivo sulla porta ${serverPort}.`);
          }
        } else {
          throw networkErr;
        }
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        if (!ttftRecorded) {
          ttftRecorded = true;
          setLiveTestState(p => ({ ...p, ttft: Math.round(performance.now() - t0) }));
        }

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n').filter(l => l.trim().length > 0);

        for (const line of lines) {
          if (isOllama) {
            try {
              const parsed = JSON.parse(line);
              if (parsed.message?.content) {
                fullText += parsed.message.content;
                setLiveTestState(p => ({ ...p, outputText: fullText }));
              }
            } catch (e) {}
          } else {
            if (line.startsWith('data: ')) {
              const dataStr = line.replace(/^data:\s*/, '').trim();
              if (dataStr === '[DONE]') continue;
              try {
                const parsed = JSON.parse(dataStr);
                const delta = parsed.choices?.[0]?.delta?.content;
                if (delta) {
                  fullText += delta;
                  setLiveTestState(p => ({ ...p, outputText: fullText }));
                }
              } catch (e) {}
            }
          }
        }
      }

      setLiveTestState(p => ({
        ...p,
        isTesting: false,
        latency: Math.round(performance.now() - t0)
      }));
    } catch (err) {
      setLiveTestState(p => ({
        ...p,
        isTesting: false,
        error: err.message
      }));
    }
  };

  // Download Continue config.json
  const downloadContinueConfig = () => {
    const targetModel = selectedGuideModel || proxyAlias || 'sigma';
    const cfg = {
      models: [
        {
          title: `SigmaEngine (${targetModel})`,
          provider: "openai",
          model: targetModel,
          apiBase: `${effectiveBaseUrl}/v1`,
          apiKey: "sigma"
        }
      ],
      tabAutocompleteModel: {
        title: "SigmaEngine Autocomplete",
        provider: "openai",
        model: "qwen2.5-coder:7b",
        apiBase: `${effectiveBaseUrl}/v1`,
        apiKey: "sigma"
      }
    };
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(cfg, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", "continue_config.json");
    dlAnchor.click();
  };

  // Filtered external providers
  const filteredProviders = useMemo(() => {
    return Object.keys(PROVIDER_CATALOG).filter(k => {
      if (k === 'sigma_engine') return false; // Handled separately in Tab 1
      const p = PROVIDER_CATALOG[k];
      const matchCat = activeCategory === 'all' || 
                       (activeCategory === 'cloud' && p.category === 'cloud') ||
                       (activeCategory === 'local' && (p.category === 'local' || p.category === 'custom'));
      const matchQuery = !searchQuery || 
                         p.label.toLowerCase().includes(searchQuery.toLowerCase()) || 
                         k.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCat && matchQuery;
    });
  }, [activeCategory, searchQuery]);

  return (
    <div 
      className="providers-hub-page-container" 
      style={{
        width: '100%',
        maxWidth: '100%',
        height: '100%',
        minHeight: '100%',
        overflowY: 'auto',
        overflowX: 'hidden',
        boxSizing: 'border-box',
        padding: '24px 32px 60px 32px',
        color: titleColor,
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
      }}
    >

      {/* Toast Notification */}
      {saveToast && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 9999,
          padding: '12px 18px',
          borderRadius: '10px',
          background: saveToast.type === 'success' ? '#0f3a22' : '#451212',
          border: `1px solid ${saveToast.type === 'success' ? '#3fb950' : '#ef4444'}`,
          color: '#ffffff',
          boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
          fontSize: '0.82rem',
          fontWeight: 700,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          animation: 'fadeIn 0.2s ease-out'
        }}>
          {saveToast.type === 'success' ? <CheckCircle2 size={16} color="#3fb950" /> : <AlertCircle size={16} color="#ef4444" />}
          <span>{saveToast.msg}</span>
        </div>
      )}

      {/* Page Header (Full Width) */}
      <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px', width: '100%' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: titleColor, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <SlidersHorizontal size={26} color="#00f2fe" />
            <span>Providers Hub & SigmaEngine Gateway</span>
          </h1>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.82rem', color: subtitleColor }}>
            Gestisci il Server Locale SigmaEngine per client esterni (VS Code, Cursor, Python) e connetti i tuoi provider AI esterni.
          </p>
        </div>

        <button
          onClick={saveAllConfig}
          disabled={saving}
          style={{
            padding: '9px 20px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
            border: 'none',
            color: '#000',
            fontSize: '0.82rem',
            fontWeight: 800,
            cursor: saving ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            boxShadow: '0 4px 16px rgba(0, 242, 254, 0.3)',
            transition: 'all 0.15s ease'
          }}
        >
          {saving ? <RefreshCw size={14} className="spin" /> : <Save size={14} />}
          <span>{saving ? 'Salvataggio...' : 'Salva Modifiche'}</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* 2 MAIN TOP-LEVEL TABS (OUTPUT / PROXY vs INPUT / AGGREGATION) */}
      {/* ========================================================================= */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '6px',
        borderRadius: '14px',
        background: cardBg,
        border: cardBorder,
        boxShadow: cardShadow,
        marginBottom: '24px',
        width: '100%'
      }}>
        {/* TAB 1: SIGMAENGINE SERVER (OUTPUT / PROXY) */}
        <button
          onClick={() => setMainHubTab('engine_server')}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            padding: '11px 20px',
            borderRadius: '10px',
            fontSize: '0.84rem',
            fontWeight: 800,
            cursor: 'pointer',
            background: mainHubTab === 'engine_server' 
              ? 'linear-gradient(135deg, rgba(0, 242, 254, 0.22), rgba(0, 180, 255, 0.12))' 
              : 'transparent',
            border: mainHubTab === 'engine_server' 
              ? '1px solid #00f2fe' 
              : '1px solid transparent',
            color: mainHubTab === 'engine_server' ? '#00f2fe' : subtitleColor,
            boxShadow: mainHubTab === 'engine_server' ? '0 0 16px rgba(0, 242, 254, 0.25)' : 'none',
            transition: 'all 0.18s ease'
          }}
        >
          <Zap size={17} color={mainHubTab === 'engine_server' ? '#00f2fe' : 'currentColor'} />
          <span>⚡ 1. SigmaEngine Server (Output / Proxy)</span>
          <span style={{
            fontSize: '0.66rem',
            padding: '2px 8px',
            borderRadius: '6px',
            background: providerServerEnabled ? 'rgba(63, 185, 80, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            color: providerServerEnabled ? '#3fb950' : '#ef4444',
            border: `1px solid ${providerServerEnabled ? 'rgba(63, 185, 80, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
            fontWeight: 700
          }}>
            {providerServerEnabled ? `:${serverPort} ATTIVO 🟢` : 'DISATTIVATO 🔴'}
          </span>
        </button>

        {/* TAB 2: EXTERNAL PROVIDERS (INPUT / AGGREGATION) */}
        <button
          onClick={() => setMainHubTab('external_providers')}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            padding: '11px 20px',
            borderRadius: '10px',
            fontSize: '0.84rem',
            fontWeight: 800,
            cursor: 'pointer',
            background: mainHubTab === 'external_providers' 
              ? 'linear-gradient(135deg, rgba(168, 85, 247, 0.22), rgba(99, 102, 241, 0.12))' 
              : 'transparent',
            border: mainHubTab === 'external_providers' 
              ? '1px solid #a855f7' 
              : '1px solid transparent',
            color: mainHubTab === 'external_providers' ? '#c084fc' : subtitleColor,
            boxShadow: mainHubTab === 'external_providers' ? '0 0 16px rgba(168, 85, 247, 0.25)' : 'none',
            transition: 'all 0.18s ease'
          }}
        >
          <Globe size={17} color={mainHubTab === 'external_providers' ? '#c084fc' : 'currentColor'} />
          <span>🌐 2. Provider Esterni (Input / Aggregazione)</span>
          <span style={{
            fontSize: '0.66rem',
            padding: '2px 8px',
            borderRadius: '6px',
            background: 'rgba(168, 85, 247, 0.15)',
            color: '#c084fc',
            border: '1px solid rgba(168, 85, 247, 0.35)',
            fontWeight: 700
          }}>
            Cloud & GitHub
          </span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1 CONTENT: ⚡ SIGMAENGINE SERVER & PROXY GATEWAY */}
      {/* ========================================================================= */}
      {mainHubTab === 'engine_server' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px', width: '100%' }}>
          
          {/* Top Server Status Strip */}
          <div style={{
            padding: '18px 22px',
            borderRadius: '16px',
            background: cardBg,
            border: '1px solid rgba(0, 242, 254, 0.3)',
            boxShadow: cardShadow,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '14px',
            width: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                background: 'rgba(0, 242, 254, 0.15)',
                border: '1px solid rgba(0, 242, 254, 0.4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 16px rgba(0, 242, 254, 0.2)'
              }}>
                <Zap size={24} color="#00f2fe" />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: titleColor }}>
                  Server API Locale SigmaEngine (:{serverPort})
                </h3>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.76rem', color: subtitleColor }}>
                  Espone i modelli locali con protocolli standard OpenAI (<code style={{ color: '#00f2fe' }}>/v1</code>) e Ollama (<code style={{ color: '#00d2ff' }}>/api</code>) a qualsiasi client esterno.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                fontSize: '0.74rem',
                fontWeight: 800,
                color: providerServerEnabled ? '#3fb950' : '#ef4444',
                background: providerServerEnabled ? 'rgba(63, 185, 80, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                border: providerServerEnabled ? '1px solid rgba(63, 185, 80, 0.35)' : '1px solid rgba(239, 68, 68, 0.35)',
                padding: '6px 14px',
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
                {providerServerEnabled ? `ATTIVO (Port ${serverPort})` : 'DISABILITATO'}
              </span>

              <button
                onClick={() => toggleProviderServer()}
                style={{
                  padding: '8px 18px',
                  borderRadius: '8px',
                  background: providerServerEnabled ? 'rgba(239, 68, 68, 0.15)' : 'linear-gradient(135deg, #3fb950, #2ea043)',
                  border: providerServerEnabled ? '1px solid rgba(239, 68, 68, 0.35)' : 'none',
                  color: providerServerEnabled ? '#ef4444' : '#fff',
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <Power size={14} />
                {providerServerEnabled ? 'Arresta Server' : `Avvia Server :${serverPort}`}
              </button>
            </div>
          </div>

          {/* CARD 1: IMPOSTAZIONI DI RETE, PARAMETRI DI INFERENZA & TEST DI USCITA */}
          <div style={{
            padding: '22px',
            borderRadius: '16px',
            background: cardBg,
            border: '1px solid rgba(0, 242, 254, 0.3)',
            boxShadow: cardShadow,
            width: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sliders size={20} color="#00f2fe" />
                <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: titleColor }}>
                  🎯 Configurazione Proxy & Porta di Uscita
                </h4>
              </div>

              <button
                onClick={saveAllConfig}
                disabled={saving}
                style={{
                  padding: '7px 16px',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                  border: 'none',
                  color: '#000',
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 2px 10px rgba(0, 242, 254, 0.25)'
                }}
              >
                {saving ? <RefreshCw size={13} className="spin" /> : <Save size={13} />}
                <span>{saving ? 'Salvataggio...' : 'Salva Parametri Rete & Inferenza'}</span>
              </button>
            </div>

            {/* Editable Network & Proxy Inputs Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '14px',
              marginBottom: '16px'
            }}>
              {/* Field 1: Porta Server */}
              <div style={{ padding: '12px 14px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'block' }}>
                    PORTA SERVER (ROUTE DI USCITA)
                  </label>
                  {typeof window !== 'undefined' && window.location.port && Number(window.location.port) !== Number(serverPort) && (
                    <span style={{ fontSize: '0.60rem', color: '#faa03c', fontWeight: 700 }}>
                      ⚡ Attivo su :{window.location.port || '8000'}
                    </span>
                  )}
                </div>
                <input
                  type="number"
                  value={serverPort}
                  onChange={e => setServerPort(Number(e.target.value))}
                  placeholder="8000"
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    borderRadius: '7px',
                    background: isLight ? '#ffffff' : '#07090e',
                    border: '1px solid rgba(0, 242, 254, 0.4)',
                    color: '#00f2fe',
                    fontSize: '0.86rem',
                    fontWeight: 800,
                    fontFamily: 'monospace',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Field 2: Host / IP di Ascolto */}
              <div style={{ padding: '12px 14px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'block' }}>
                    HOST / INDIRIZZO IP DI ASCOLTO
                  </label>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                      type="button"
                      onClick={() => setServerHost('0.0.0.0')}
                      style={{
                        padding: '1px 5px',
                        borderRadius: '4px',
                        fontSize: '0.58rem',
                        fontWeight: 800,
                        border: 'none',
                        cursor: 'pointer',
                        background: serverHost === '0.0.0.0' ? '#00f2fe' : (isLight ? '#e2e8f0' : 'rgba(255,255,255,0.08)'),
                        color: serverHost === '0.0.0.0' ? '#000' : subtitleColor
                      }}
                      title="Ascolta su tutte le interfacce per consentire l'accesso da Wi-Fi, smartphone e rete locale"
                    >
                      0.0.0.0 (Wi-Fi/LAN)
                    </button>
                    <button
                      type="button"
                      onClick={() => setServerHost('localhost')}
                      style={{
                        padding: '1px 5px',
                        borderRadius: '4px',
                        fontSize: '0.58rem',
                        fontWeight: 800,
                        border: 'none',
                        cursor: 'pointer',
                        background: serverHost === 'localhost' || serverHost === '127.0.0.1' ? '#38bdf8' : (isLight ? '#e2e8f0' : 'rgba(255,255,255,0.08)'),
                        color: serverHost === 'localhost' || serverHost === '127.0.0.1' ? '#000' : subtitleColor
                      }}
                      title="Consenti l'accesso solo da questo computer"
                    >
                      localhost
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  value={serverHost}
                  onChange={e => setServerHost(e.target.value)}
                  placeholder="0.0.0.0"
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    borderRadius: '7px',
                    background: isLight ? '#ffffff' : '#07090e',
                    border: '1px solid rgba(0, 242, 254, 0.4)',
                    color: titleColor,
                    fontSize: '0.86rem',
                    fontWeight: 800,
                    fontFamily: 'monospace',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Field 3: Nome Alias Proxy */}
              <div style={{ padding: '12px 14px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'block', marginBottom: '4px' }}>
                  NOME ALIAS PROXY ESPORTATO
                </label>
                <input
                  type="text"
                  value={proxyAlias}
                  onChange={e => setProxyAlias(e.target.value)}
                  placeholder="sigma"
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    borderRadius: '7px',
                    background: isLight ? '#ffffff' : '#07090e',
                    border: '1px solid rgba(0, 242, 254, 0.4)',
                    color: '#3fb950',
                    fontSize: '0.86rem',
                    fontWeight: 800,
                    fontFamily: 'monospace',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Field 4: Modello Destinazione Proxy */}
              <div style={{ padding: '12px 14px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder, gridColumn: 'span 1' }}>
                <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'block', marginBottom: '4px' }}>
                  MODELLO PROXY ATTIVO
                </label>
                <CustomSelect
                  value={selectedGuideModel}
                  onChange={val => {
                    setSelectedGuideModel(val);
                  }}
                  options={allAvailableGuideModels}
                  placeholder="Seleziona modello proxy..."
                  searchable={true}
                  variant="cyan"
                />
              </div>

              {/* Field 5: Connessione Sicura HTTPS / TLS */}
              <div style={{
                padding: '12px 14px',
                borderRadius: '10px',
                background: innerCardBg,
                border: sslEnabled ? '1px solid rgba(0, 242, 254, 0.4)' : innerCardBorder,
                gridColumn: 'span 1',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ fontSize: '0.68rem', fontWeight: 700, color: subtitleColor, display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <ShieldCheck size={14} color={sslEnabled ? '#00f2fe' : '#8b8fa3'} />
                    <span>HTTPS / TLS (LAN & MICROFONO)</span>
                  </label>
                  <span style={{
                    fontSize: '0.58rem',
                    padding: '1px 6px',
                    borderRadius: '4px',
                    fontWeight: 800,
                    background: sslEnabled ? 'rgba(0, 242, 254, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                    color: sslEnabled ? '#00f2fe' : '#8b8fa3'
                  }}>
                    {sslEnabled ? '🔒 HTTPS ATTIVO' : '🔓 HTTP'}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                  <span style={{ fontSize: '0.70rem', color: subtitleColor }}>
                    {sslEnabled ? 'TLS locale abilitato' : 'Crittografia disattivata'}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      const nextSsl = !sslEnabled;
                      setSslEnabled(nextSsl);
                      setSaveToast({
                        type: 'success',
                        msg: nextSsl ? 'HTTPS abilitato 🔒! Clicca "Salva Parametri" per applicare.' : 'HTTPS disabilitato (HTTP standard).'
                      });
                      setTimeout(() => setSaveToast(null), 3000);
                    }}
                    style={{
                      padding: '4px 12px',
                      borderRadius: '6px',
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      border: 'none',
                      cursor: 'pointer',
                      background: sslEnabled ? 'linear-gradient(135deg, #00f2fe, #0072ff)' : (isLight ? '#e2e8f0' : 'rgba(255,255,255,0.1)'),
                      color: sslEnabled ? '#000' : subtitleColor,
                      transition: 'all 0.2s ease'
                    }}
                  >
                    {sslEnabled ? 'Disattiva' : 'Abilita HTTPS ⚡'}
                  </button>
                </div>
              </div>
            </div>

            {/* Sub-Section: Accesso Wi-Fi / Rete Locale (LAN) */}
            <div style={{
              padding: '16px',
              borderRadius: '12px',
              background: isLight ? 'rgba(56, 189, 248, 0.06)' : 'rgba(56, 189, 248, 0.04)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              marginBottom: '16px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Wifi size={16} color="#38bdf8" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#38bdf8' }}>
                    🌐 Accesso da Rete Locale & Dispositivi Wi-Fi (Smartphone, Tablet, Altri PC)
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {sslEnabled && (
                    <span style={{
                      fontSize: '0.62rem',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: 'rgba(0, 242, 254, 0.15)',
                      color: '#00f2fe',
                      border: '1px solid rgba(0, 242, 254, 0.35)',
                      fontWeight: 800,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      🔒 TLS / HTTPS ATTIVO
                    </span>
                  )}
                  <span style={{
                    fontSize: '0.62rem',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: 'rgba(63, 185, 80, 0.15)',
                    color: '#3fb950',
                    border: '1px solid rgba(63, 185, 80, 0.35)',
                    fontWeight: 800,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <CheckCircle2 size={11} /> PRONTO SU RETE LOCALE (0.0.0.0)
                  </span>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px', marginBottom: '10px' }}>
                {/* 1. Web UI URL for Smartphone/Tablet/Browser */}
                <div style={{ padding: '10px 14px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                  <div>
                    <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>LINK WEB UI (PER SMARTPHONE & BROWSER)</div>
                    <code style={{ fontSize: '0.82rem', color: '#00f2fe', fontWeight: 800 }}>
                      {sslEnabled ? 'https' : 'http'}://{serverInfo?.lan_ip || '192.168.1.2'}:{serverPort}
                    </code>
                  </div>
                  <button
                    onClick={() => copyKeyToClipboard('lan_web_ui', `${sslEnabled ? 'https' : 'http'}://${serverInfo?.lan_ip || '192.168.1.2'}:${serverPort}`)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: 'rgba(0, 242, 254, 0.12)',
                      border: '1px solid rgba(0, 242, 254, 0.3)',
                      color: '#00f2fe',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    {copiedKey === 'lan_web_ui' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                    <span>{copiedKey === 'lan_web_ui' ? 'Copiato!' : 'Copia Link'}</span>
                  </button>
                </div>

                {/* 2. Provider API Base URL for other PCs/Cursor */}
                <div style={{ padding: '10px 14px', borderRadius: '8px', background: innerCardBg, border: innerCardBorder, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                  <div>
                    <div style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>API BASE URL (CURSOR / CLINE / CONTINUE SU ALTRI PC)</div>
                    <code style={{ fontSize: '0.82rem', color: '#38bdf8', fontWeight: 800 }}>
                      {sslEnabled ? 'https' : 'http'}://{serverInfo?.lan_ip || '192.168.1.2'}:{serverPort}/v1
                    </code>
                  </div>
                  <button
                    onClick={() => copyKeyToClipboard('lan_api_url', `${sslEnabled ? 'https' : 'http'}://${serverInfo?.lan_ip || '192.168.1.2'}:${serverPort}/v1`)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      background: 'rgba(56, 189, 248, 0.12)',
                      border: '1px solid rgba(56, 189, 248, 0.3)',
                      color: '#38bdf8',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    {copiedKey === 'lan_api_url' ? <Check size={12} color="#3fb950" /> : <Copy size={12} />}
                    <span>{copiedKey === 'lan_api_url' ? 'Copiato!' : 'Copia API'}</span>
                  </button>
                </div>
              </div>

              <p style={{ margin: 0, fontSize: '0.72rem', color: subtitleColor, lineHeight: 1.4 }}>
                💡 <strong>Come connetterti:</strong> Assicurati che lo smartphone o l'altro PC sia connesso alla stessa rete Wi-Fi di questo computer. {sslEnabled ? 'Con HTTPS attivo, i browser mobile su smartphone e tablet (iOS Safari, Android Chrome) sbloccano l\'accesso al microfono per la Voice Chat locale.' : 'Puoi abilitare HTTPS per consentire l\'uso del microfono da smartphone/tablet.'}
              </p>
            </div>


            {/* Sub-Section 1: Parametri di Inferenza & Limiti di Contesto Predefiniti */}
            <div style={{
              padding: '16px',
              borderRadius: '12px',
              background: isLight ? 'rgba(250, 160, 60, 0.05)' : 'rgba(250, 160, 60, 0.03)',
              border: '1px solid rgba(250, 160, 60, 0.25)',
              marginBottom: '16px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <SlidersHorizontal size={16} color="#faa03c" />
                <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#faa03c' }}>
                  Parametri di Inferenza & Limiti di Contesto Predefiniti (Uscita Proxy)
                </span>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                gap: '14px'
              }}>
                {/* Box A: Temperatura & Sampling */}
                <div style={{ padding: '14px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 800, color: '#00d2ff', marginBottom: '10px' }}>
                    🌡️ Temperatura & Campionamento Statistico
                  </div>

                  {/* Temperature */}
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
                      <span>0.0 (Codice)</span>
                      <span>0.7 (Bilanciato)</span>
                      <span>1.0 (Creativo)</span>
                    </div>
                  </div>

                  {/* Top P */}
                  <div>
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
                </div>

                {/* Box B: Context Window & Tokens */}
                <div style={{ padding: '14px', borderRadius: '10px', background: innerCardBg, border: innerCardBorder }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 800, color: '#faa03c', marginBottom: '10px' }}>
                    💾 Finestra di Contesto VRAM & Limite Token
                  </div>

                  {/* Num Ctx */}
                  <div style={{ marginBottom: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <label style={{ fontSize: '0.72rem', fontWeight: 700, color: titleColor }}>Finestra di Contesto (num_ctx)</label>
                      <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#faa03c' }}>{parameters.num_ctx.toLocaleString()} token</span>
                    </div>
                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                      {[8192, 16384, 32768, 65536, 131072].map(ctx => (
                        <button
                          key={ctx}
                          onClick={() => setParameters(p => ({ ...p, num_ctx: ctx }))}
                          style={{
                            padding: '3px 8px',
                            borderRadius: '5px',
                            fontSize: '0.68rem',
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
                  </div>

                  {/* Max Tokens */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <label style={{ fontSize: '0.72rem', fontWeight: 700, color: titleColor }}>Max Token Risposta</label>
                      <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#00d2ff' }}>{parameters.max_tokens.toLocaleString()}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                      {[4096, 8192, 16384, 32768].map(tok => (
                        <button
                          key={tok}
                          onClick={() => setParameters(p => ({ ...p, max_tokens: tok }))}
                          style={{
                            padding: '3px 8px',
                            borderRadius: '5px',
                            fontSize: '0.68rem',
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
                  </div>
                </div>
              </div>
            </div>

            {/* Sub-Section 2: Test Live Risposta Streaming Server */}
            <div style={{
              padding: '16px',
              borderRadius: '12px',
              background: isLight ? 'rgba(0, 242, 254, 0.05)' : 'rgba(0, 242, 254, 0.03)',
              border: '1px solid rgba(0, 242, 254, 0.25)',
              marginBottom: '16px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Zap size={16} color="#00f2fe" />
                  <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#00f2fe' }}>
                    Test Live Risposta Streaming Server (:{serverPort})
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <button
                    onClick={() => setLiveTestState(p => ({ ...p, protocol: 'openai' }))}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '0.7rem',
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
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '0.7rem',
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

              <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                <input
                  type="text"
                  value={liveTestState.prompt}
                  onChange={e => setLiveTestState(p => ({ ...p, prompt: e.target.value }))}
                  placeholder="Inserisci un prompt di test..."
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '8px',
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
                    padding: '8px 16px',
                    borderRadius: '8px',
                    background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                    border: 'none',
                    color: '#000',
                    fontSize: '0.76rem',
                    fontWeight: 800,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  {liveTestState.isTesting ? <RefreshCw size={13} className="spin" /> : <Play size={13} />}
                  <span>Test Streaming</span>
                </button>
              </div>

              {(liveTestState.outputText || liveTestState.isTesting || liveTestState.error) && (
                <div style={{
                  padding: '12px 14px',
                  borderRadius: '8px',
                  background: '#07090e',
                  border: '1px solid rgba(0, 242, 254, 0.3)',
                  fontSize: '0.78rem',
                  color: '#e2e8f0',
                  lineHeight: 1.5
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.68rem', color: subtitleColor }}>
                    <span>Protocollo: <strong>{liveTestState.protocol.toUpperCase()}</strong> • Modello: <strong style={{ color: '#00f2fe' }}>{selectedGuideModel || proxyAlias || 'sigma'}</strong></span>
                    {liveTestState.ttft && <span>TTFT: <strong style={{ color: '#00f2fe' }}>{liveTestState.ttft}ms</strong> • Totale: <strong style={{ color: '#3fb950' }}>{liveTestState.latency || '...'}ms</strong></span>}
                  </div>
                  {liveTestState.error ? (
                    <div style={{ color: '#ef4444' }}>❌ {liveTestState.error}</div>
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                      {liveTestState.outputText}
                      {liveTestState.isTesting && <span style={{ display: 'inline-block', width: '6px', height: '14px', background: '#00f2fe', marginLeft: '3px', verticalAlign: 'middle', animation: 'blink 1s infinite' }} />}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Sub-Section 3: Explanation of Proxy Alias vs Direct Exact Name Routing */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
              gap: '14px'
            }}>
              {/* Option 1: Proxy Alias */}
              <div style={{
                padding: '14px 16px',
                borderRadius: '10px',
                background: innerCardBg,
                border: '1px solid rgba(0, 242, 254, 0.25)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#00f2fe' }}>OPZIONE 1: ALIAS PROXY "{proxyAlias || 'sigma'}"</span>
                </div>
                <p style={{ margin: 0, fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.5 }}>
                  Imposta nel tuo client esterno <code style={{ color: '#00f2fe' }}>model: "{proxyAlias || 'sigma'}"</code> (o <code style={{ color: '#00f2fe' }}>"sigmaengine"</code>). Le richieste verranno inoltrate istantaneamente al modello scelto (<strong style={{ color: '#ffffff' }}>{selectedGuideModel}</strong>) senza dover riconfigurare l'IDE ogni volta che cambi modello!
                </p>
              </div>

              {/* Option 2: Direct Model Name */}
              <div style={{
                padding: '14px 16px',
                borderRadius: '10px',
                background: innerCardBg,
                border: '1px solid rgba(168, 85, 247, 0.25)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#c084fc' }}>OPZIONE 2: CHIAMATA DIRETTA PER NOME</span>
                </div>
                <p style={{ margin: 0, fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.5 }}>
                  Puoi richiedere direttamente qualsiasi modello presente su disco passando il suo nome esatto (es. <code style={{ color: '#c084fc' }}>"Qwen3.5-9B-GGUF"</code> o <code style={{ color: '#c084fc' }}>"sigma-alpaca-3b-gguf"</code>). Il router di SigmaEngine caricherà il modello richiesto on-demand.
                </p>
              </div>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* CARD 2: LISTA MODELLI RICHIAMABILI CON TASTO COPIA & SCELTA PROXY */}
          {/* ========================================================================= */}
          <div style={{
            padding: '22px',
            borderRadius: '16px',
            background: cardBg,
            border: '1px solid rgba(0, 242, 254, 0.3)',
            boxShadow: cardShadow,
            width: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'rgba(0, 242, 254, 0.15)',
                  border: '1px solid rgba(0, 242, 254, 0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <List size={18} color="#00f2fe" />
                </div>
                <div>
                  <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: titleColor }}>
                    📋 Registro Modelli Richiamabili & Selezione Rapida Proxy
                  </h4>
                  <p style={{ margin: '2px 0 0 0', fontSize: '0.74rem', color: subtitleColor }}>
                    Tutti i modelli locali ospitati ed esportati da Sigma Studio come Provider API OpenAI/Ollama. Copia il <strong>Model ID</strong> esatto per i tuoi client esterni (Cursor, VS Code, Cline, Continue) o imposta il modello come destinazione del proxy <code>{proxyAlias || 'sigma'}</code>.
                  </p>
                </div>
              </div>

              {/* Search & Filter pills */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                {/* Search */}
                <div style={{ position: 'relative', width: '220px' }}>
                  <Search size={14} color="#a0a6bc" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="text"
                    value={callableSearch}
                    onChange={e => setCallableSearch(e.target.value)}
                    placeholder="Filtra modelli locali..."
                    style={{
                      width: '100%',
                      padding: '6px 10px 6px 30px',
                      borderRadius: '7px',
                      background: innerCardBg,
                      border: innerCardBorder,
                      color: titleColor,
                      fontSize: '0.74rem',
                      outline: 'none'
                    }}
                  />
                </div>

                {/* Category Filter Pills */}
                <div style={{ display: 'flex', gap: '4px' }}>
                  {[
                    { id: 'all', label: 'Tutti' },
                    { id: 'vram', label: '🔥 In VRAM' },
                    { id: 'local', label: '🏠 Locali GGUF' },
                    { id: 'proxy', label: '⚡ Proxy & Router' }
                  ].map(f => (
                    <button
                      key={f.id}
                      onClick={() => setCallableFilter(f.id)}
                      style={{
                        padding: '5px 10px',
                        borderRadius: '6px',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        border: 'none',
                        cursor: 'pointer',
                        background: callableFilter === f.id ? '#00f2fe' : innerCardBg,
                        color: callableFilter === f.id ? '#000' : subtitleColor,
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Models Table / List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filteredCallableModels.length === 0 ? (
                <div style={{ padding: '24px', textAlign: 'center', color: subtitleColor, fontSize: '0.8rem', background: innerCardBg, borderRadius: '10px' }}>
                  Nessun modello trovato corrispondente ai criteri di ricerca.
                </div>
              ) : (
                filteredCallableModels.map((item, idx) => {
                  const isCurrentProxy = selectedGuideModel === item.value;
                  const itemKey = `callable_model_${item.value}_${idx}`;

                  return (
                    <div
                      key={itemKey}
                      style={{
                        padding: '12px 16px',
                        borderRadius: '10px',
                        background: isCurrentProxy 
                          ? (isLight ? 'rgba(0, 242, 254, 0.1)' : 'rgba(0, 242, 254, 0.08)') 
                          : (isLight ? '#ffffff' : '#07090e'),
                        border: isCurrentProxy 
                          ? '1px solid rgba(0, 242, 254, 0.45)' 
                          : innerCardBorder,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '12px',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {/* Left: Model Name, Badges (Family, Speed, Benchmark, Params, Size, Quant) */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '260px', flex: 1 }}>
                        <div style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          background: item.color || '#00f2fe',
                          boxShadow: `0 0 8px ${item.color || '#00f2fe'}`
                        }} />

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '0.86rem', fontWeight: 800, color: titleColor }}>
                              {item.label}
                            </span>

                            {item.badge && (
                              <span style={{
                                fontSize: '0.62rem',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                background: `${item.color || '#00f2fe'}18`,
                                color: item.color || '#00f2fe',
                                border: `1px solid ${item.color || '#00f2fe'}35`,
                                fontWeight: 700
                              }}>
                                {item.badge}
                              </span>
                            )}

                            {/* Family Badge */}
                            {item.family && item.family.id !== 'altro' && (
                              <span style={{
                                fontSize: '0.60rem',
                                padding: '1px 6px',
                                borderRadius: '4px',
                                background: item.family.bg,
                                color: item.family.color,
                                border: `1px solid ${item.family.border}`,
                                fontWeight: 800
                              }}>
                                {item.family.title}
                              </span>
                            )}

                            {/* Live Speed (t/s) */}
                            {item.chatSpeed !== null && item.chatSpeed !== undefined && (
                              <span
                                title={`Velocità live: ${item.chatSpeed} token/sec`}
                                style={{
                                  fontSize: '0.62rem',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  background: 'rgba(0, 210, 255, 0.14)',
                                  color: '#00d2ff',
                                  border: '1px solid rgba(0, 210, 255, 0.35)',
                                  fontWeight: 800,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '2px'
                                }}
                              >
                                <Zap size={10} color="#00d2ff" />
                                <span>{item.chatSpeed} t/s</span>
                              </span>
                            )}

                            {/* Benchmark Score */}
                            {item.hasBenchmark && item.benchmarkScore !== null && (
                              <span
                                title={`Benchmark Suite: ${item.benchmark?.tests_passed || 0}/${item.benchmark?.tests_total || 0} quesiti superati`}
                                style={{
                                  fontSize: '0.62rem',
                                  padding: '2px 7px',
                                  borderRadius: '4px',
                                  background: item.benchmarkScore >= 75 ? 'rgba(16, 185, 129, 0.16)' : 'rgba(250, 204, 21, 0.16)',
                                  color: item.benchmarkScore >= 75 ? '#10b981' : '#facc15',
                                  border: `1px solid ${item.benchmarkScore >= 75 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(250, 204, 21, 0.4)'}`,
                                  fontWeight: 800,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '3px'
                                }}
                              >
                                <Trophy size={10} />
                                <span>🏆 {item.benchmarkScore}% Pass</span>
                              </span>
                            )}

                            {/* Active Proxy Badge */}
                            {isCurrentProxy && (
                              <span style={{
                                fontSize: '0.62rem',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                background: 'linear-gradient(135deg, rgba(0, 242, 254, 0.25), rgba(79, 172, 254, 0.25))',
                                color: '#00f2fe',
                                border: '1px solid #00f2fe',
                                fontWeight: 800,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '3px'
                              }}>
                                <Zap size={10} /> PROXY ATTIVO ("{proxyAlias || 'sigma'}")
                              </span>
                            )}
                          </div>

                          {/* Secondary Specs Row */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', fontSize: '0.7rem', color: subtitleColor }}>
                            {item.params && (
                              <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8', fontWeight: 800 }}>
                                ⚡ {item.params}
                              </span>
                            )}
                            {item.quant && (
                              <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(192, 132, 252, 0.12)', color: '#c084fc', fontWeight: 700 }}>
                                🏷️ {item.quant}
                              </span>
                            )}
                            {item.sizeLabel && (
                              <span style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(255, 184, 108, 0.12)', color: '#ffb86c', fontWeight: 700 }}>
                                💾 {item.sizeLabel}
                              </span>
                            )}
                            {item.desc && !item.params && !item.sizeLabel && (
                              <span>{item.desc}</span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Center: Exact Model ID Code Tag */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '4px 10px',
                        borderRadius: '6px',
                        background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.08)'
                      }}>
                        <span style={{ fontSize: '0.64rem', color: subtitleColor, fontWeight: 700 }}>MODEL ID:</span>
                        <code style={{ fontSize: '0.78rem', color: item.color || '#00f2fe', fontWeight: 800 }}>
                          {item.value}
                        </code>
                      </div>

                      {/* Right: Actions (Copy Model ID + Set as Proxy) */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {/* Copy Model ID Button */}
                        <button
                          onClick={() => copyKeyToClipboard(`copy_model_${item.value}`, item.value)}
                          style={{
                            padding: '5px 12px',
                            borderRadius: '6px',
                            background: innerCardBg,
                            border: innerCardBorder,
                            color: titleColor,
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            transition: 'all 0.15s ease'
                          }}
                        >
                          {copiedKey === `copy_model_${item.value}` ? (
                            <>
                              <Check size={12} color="#3fb950" />
                              <span style={{ color: '#3fb950' }}>Copiato!</span>
                            </>
                          ) : (
                            <>
                              <Copy size={12} />
                              <span>Copia ID</span>
                            </>
                          )}
                        </button>

                        {/* Set as Proxy Button */}
                        {isCurrentProxy ? (
                          <div style={{
                            padding: '5px 12px',
                            borderRadius: '6px',
                            background: 'rgba(63, 185, 80, 0.15)',
                            border: '1px solid rgba(63, 185, 80, 0.4)',
                            color: '#3fb950',
                            fontSize: '0.72rem',
                            fontWeight: 800,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}>
                            <CheckCircle2 size={13} color="#3fb950" />
                            <span>Proxy Agganciato</span>
                          </div>
                        ) : (
                          <button
                            onClick={() => handleSetProxyModel(item.value)}
                            style={{
                              padding: '5px 12px',
                              borderRadius: '6px',
                              background: 'linear-gradient(135deg, rgba(0, 242, 254, 0.18), rgba(0, 180, 255, 0.12))',
                              border: '1px solid rgba(0, 242, 254, 0.4)',
                              color: '#00f2fe',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              transition: 'all 0.15s ease'
                            }}
                          >
                            <Zap size={12} />
                            <span>Imposta come Proxy</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* CARD 3: ROUTE API ESPORTATE */}
          <div style={{
            padding: '20px 22px',
            borderRadius: '16px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            width: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ fontSize: '0.88rem', fontWeight: 800, color: titleColor, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Radio size={18} color="#00f2fe" />
              <span>Route API Esportate da SigmaEngine (:{serverPort})</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {/* Route 1: OpenAI Chat Completions */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: '10px',
                background: isLight ? '#ffffff' : '#07090e',
                border: innerCardBorder,
                flexWrap: 'wrap',
                gap: '10px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#10a37f', background: 'rgba(16, 163, 127, 0.15)', padding: '2px 8px', borderRadius: '4px' }}>POST</span>
                  <code style={{ fontSize: '0.84rem', color: titleColor, fontWeight: 700 }}>{effectiveBaseUrl}/v1/chat/completions</code>
                  <span style={{ fontSize: '0.72rem', color: subtitleColor }}>Standard OpenAI Chat (Streaming SSE)</span>
                </div>
                <button
                  onClick={() => copyKeyToClipboard('route_openai_chat', `${effectiveBaseUrl}/v1/chat/completions`)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '6px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}
                >
                  {copiedKey === 'route_openai_chat' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                  <span>{copiedKey === 'route_openai_chat' ? 'Copiato!' : 'Copia URL'}</span>
                </button>
              </div>

              {/* Route 2: OpenAI Models List */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: '10px',
                background: isLight ? '#ffffff' : '#07090e',
                border: innerCardBorder,
                flexWrap: 'wrap',
                gap: '10px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.15)', padding: '2px 8px', borderRadius: '4px' }}>GET</span>
                  <code style={{ fontSize: '0.84rem', color: titleColor, fontWeight: 700 }}>{effectiveBaseUrl}/v1/models</code>
                  <span style={{ fontSize: '0.72rem', color: subtitleColor }}>Rilevamento Modelli Disponibili</span>
                </div>
                <button
                  onClick={() => copyKeyToClipboard('route_openai_models', `${effectiveBaseUrl}/v1/models`)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '6px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}
                >
                  {copiedKey === 'route_openai_models' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                  <span>{copiedKey === 'route_openai_models' ? 'Copiato!' : 'Copia URL'}</span>
                </button>
              </div>

              {/* Route 3: Ollama Chat API */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderRadius: '10px',
                background: isLight ? '#ffffff' : '#07090e',
                border: innerCardBorder,
                flexWrap: 'wrap',
                gap: '10px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#00d2ff', background: 'rgba(0, 210, 255, 0.15)', padding: '2px 8px', borderRadius: '4px' }}>POST</span>
                  <code style={{ fontSize: '0.84rem', color: titleColor, fontWeight: 700 }}>{effectiveBaseUrl}/api/chat</code>
                  <span style={{ fontSize: '0.72rem', color: subtitleColor }}>Standard Ollama Protocol (NDJSON Stream)</span>
                </div>
                <button
                  onClick={() => copyKeyToClipboard('route_ollama_chat', `${effectiveBaseUrl}/api/chat`)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '6px',
                    background: innerCardBg,
                    border: innerCardBorder,
                    color: titleColor,
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}
                >
                  {copiedKey === 'route_ollama_chat' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                  <span>{copiedKey === 'route_ollama_chat' ? 'Copiato!' : 'Copia URL'}</span>
                </button>
              </div>
            </div>
          </div>

          {/* CARD 4: SNIPPET DI INTEGRAZIONE RAPIDA (CON TASTI COPIA) */}
          <div style={{
            padding: '22px',
            borderRadius: '16px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            width: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Code size={20} color="#00f2fe" />
                <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: titleColor }}>
                  Integrazione Istantanea nei tuoi Tool di Sviluppo
                </h4>
              </div>
            </div>

            {/* Integration Tabs Switcher */}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
              {[
                { id: 'continue', label: '🧩 Continue (VS Code)' },
                { id: 'cline', label: '🤖 Cline / Roo Code' },
                { id: 'copilot', label: '🚀 Cursor / Windsurf' },
                { id: 'python', label: '🐍 Python SDK' },
                { id: 'node', label: '📦 Node.js / TS' },
                { id: 'curl', label: '💻 cURL Test' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveVsCodeTab(tab.id)}
                  style={{
                    padding: '7px 16px',
                    borderRadius: '8px',
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    border: 'none',
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <p style={{ margin: 0, fontSize: '0.76rem', color: subtitleColor }}>
                    Incolla questo blocco nel file <code style={{ color: '#00f2fe' }}>~/.continue/config.json</code>:
                  </p>
                  <button
                    onClick={downloadContinueConfig}
                    style={{
                      padding: '5px 12px',
                      borderRadius: '6px',
                      background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                      border: 'none',
                      color: '#000',
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    <Download size={12} /> Scarica config.json
                  </button>
                </div>
                <div style={{ position: 'relative' }}>
                  <pre style={{
                    padding: '16px 18px',
                    borderRadius: '10px',
                    background: '#07090e',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    color: '#00f2fe',
                    fontSize: '0.78rem',
                    fontFamily: 'Consolas, monospace',
                    overflowX: 'auto',
                    margin: 0
                  }}>{`{
  "models": [
    {
      "title": "SigmaEngine (${selectedGuideModel || proxyAlias || 'sigma'})",
      "provider": "openai",
      "model": "${selectedGuideModel || proxyAlias || 'sigma'}",
      "apiBase": "${effectiveBaseUrl}/v1",
      "apiKey": "sigma"
    }
  ]
}`}</pre>
                  <button
                    onClick={() => copyKeyToClipboard('continue_code', `{\n  "models": [\n    {\n      "title": "SigmaEngine (${selectedGuideModel || proxyAlias || 'sigma'})",\n      "provider": "openai",\n      "model": "${selectedGuideModel || proxyAlias || 'sigma'}",\n      "apiBase": "${effectiveBaseUrl}/v1",\n      "apiKey": "sigma"\n    }\n  ]\n}`)}
                    style={{
                      position: 'absolute',
                      top: '10px',
                      right: '10px',
                      padding: '5px 12px',
                      borderRadius: '6px',
                      background: 'rgba(255,255,255,0.12)',
                      border: '1px solid rgba(255,255,255,0.2)',
                      color: '#fff',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    {copiedKey === 'continue_code' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                    <span>{copiedKey === 'continue_code' ? 'Copiato!' : 'Copia JSON'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* TAB CONTENT: CLINE / ROO CODE */}
            {activeVsCodeTab === 'cline' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                <div style={{ padding: '12px 16px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder }}>
                  <div style={{ fontSize: '0.66rem', color: subtitleColor, fontWeight: 700 }}>API PROVIDER</div>
                  <div style={{ fontSize: '0.84rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>OpenAI Compatible</div>
                </div>
                <div style={{ padding: '12px 16px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.66rem', color: subtitleColor, fontWeight: 700 }}>BASE URL</div>
                    <div style={{ fontSize: '0.84rem', fontWeight: 800, color: '#00f2fe', marginTop: '2px' }}>{effectiveBaseUrl}/v1</div>
                  </div>
                  <button onClick={() => copyKeyToClipboard('cline_base', `${effectiveBaseUrl}/v1`)} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                    {copiedKey === 'cline_base' ? <Check size={15} color="#3fb950" /> : <Copy size={15} />}
                  </button>
                </div>
                <div style={{ padding: '12px 16px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.66rem', color: subtitleColor, fontWeight: 700 }}>API KEY</div>
                    <div style={{ fontSize: '0.84rem', fontWeight: 800, color: titleColor, marginTop: '2px' }}>sigma</div>
                  </div>
                  <button onClick={() => copyKeyToClipboard('cline_key', 'sigma')} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                    {copiedKey === 'cline_key' ? <Check size={15} color="#3fb950" /> : <Copy size={15} />}
                  </button>
                </div>
                <div style={{ padding: '12px 16px', borderRadius: '8px', background: isLight ? '#ffffff' : '#07090e', border: innerCardBorder, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: '0.66rem', color: subtitleColor, fontWeight: 700 }}>MODEL ID</div>
                    <div style={{ fontSize: '0.84rem', fontWeight: 800, color: '#00d2ff', marginTop: '2px' }}>{selectedGuideModel || proxyAlias || 'sigma'}</div>
                  </div>
                  <button onClick={() => copyKeyToClipboard('cline_model', selectedGuideModel || proxyAlias || 'sigma')} style={{ background: 'none', border: 'none', color: subtitleColor, cursor: 'pointer' }}>
                    {copiedKey === 'cline_model' ? <Check size={15} color="#3fb950" /> : <Copy size={15} />}
                  </button>
                </div>
              </div>
            )}

            {/* TAB CONTENT: CURSOR / COPILOT */}
            {activeVsCodeTab === 'copilot' && (
              <div style={{ position: 'relative' }}>
                <pre style={{
                  padding: '16px 18px',
                  borderRadius: '10px',
                  background: '#07090e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#3fb950',
                  fontSize: '0.78rem',
                  fontFamily: 'Consolas, monospace',
                  overflowX: 'auto',
                  margin: 0
                }}>{`# Variabili di ambiente per Cursor, Windsurf, Aider o shell:
export OPENAI_BASE_URL="${effectiveBaseUrl}/v1"
export OPENAI_API_KEY="sigma"
export OPENAI_MODEL="${selectedGuideModel || proxyAlias || 'sigma'}"`}</pre>
                <button
                  onClick={() => copyKeyToClipboard('copilot_code', `export OPENAI_BASE_URL="${effectiveBaseUrl}/v1"\nexport OPENAI_API_KEY="sigma"\nexport OPENAI_MODEL="${selectedGuideModel || proxyAlias || 'sigma'}"`)}
                  style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    padding: '5px 12px',
                    borderRadius: '6px',
                    background: 'rgba(255,255,255,0.12)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    color: '#fff',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {copiedKey === 'copilot_code' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                  <span>{copiedKey === 'copilot_code' ? 'Copiato!' : 'Copia'}</span>
                </button>
              </div>
            )}

            {/* TAB CONTENT: PYTHON SDK */}
            {activeVsCodeTab === 'python' && (
              <div style={{ position: 'relative' }}>
                <pre style={{
                  padding: '16px 18px',
                  borderRadius: '10px',
                  background: '#07090e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#faa03c',
                  fontSize: '0.78rem',
                  fontFamily: 'Consolas, monospace',
                  overflowX: 'auto',
                  margin: 0
                }}>{`from openai import OpenAI

client = OpenAI(base_url="${effectiveBaseUrl}/v1", api_key="sigma")
response = client.chat.completions.create(
    model="${selectedGuideModel || proxyAlias || 'sigma'}",
    messages=[{"role": "user", "content": "Ciao da Python!"}],
    stream=True
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`}</pre>
                <button
                  onClick={() => copyKeyToClipboard('python_code', `from openai import OpenAI\n\nclient = OpenAI(base_url="${effectiveBaseUrl}/v1", api_key="sigma")\nresponse = client.chat.completions.create(\n    model="${selectedGuideModel || proxyAlias || 'sigma'}",\n    messages=[{"role": "user", "content": "Ciao da Python!"}],\n    stream=True\n)\nfor chunk in response:\n    print(chunk.choices[0].delta.content or "", end="", flush=True)`)}
                  style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    padding: '5px 12px',
                    borderRadius: '6px',
                    background: 'rgba(255,255,255,0.12)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    color: '#fff',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {copiedKey === 'python_code' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                  <span>{copiedKey === 'python_code' ? 'Copiato!' : 'Copia'}</span>
                </button>
              </div>
            )}

            {/* TAB CONTENT: NODE.JS / TYPESCRIPT */}
            {activeVsCodeTab === 'node' && (
              <div style={{ position: 'relative' }}>
                <pre style={{
                  padding: '16px 18px',
                  borderRadius: '10px',
                  background: '#07090e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#38bdf8',
                  fontSize: '0.78rem',
                  fontFamily: 'Consolas, monospace',
                  overflowX: 'auto',
                  margin: 0
                }}>{`import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: '${effectiveBaseUrl}/v1',
  apiKey: 'sigma'
});

const stream = await client.chat.completions.create({
  model: '${selectedGuideModel || proxyAlias || 'sigma'}',
  messages: [{ role: 'user', content: 'Ciao da Node.js!' }],
  stream: true
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || '');
}`}</pre>
                <button
                  onClick={() => copyKeyToClipboard('node_code', `import OpenAI from 'openai';\n\nconst client = new OpenAI({\n  baseURL: '${effectiveBaseUrl}/v1',\n  apiKey: 'sigma'\n});\n\nconst stream = await client.chat.completions.create({\n  model: '${selectedGuideModel || proxyAlias || 'sigma'}',\n  messages: [{ role: 'user', content: 'Ciao da Node.js!' }],\n  stream: true\n});\n\nfor await (const chunk of stream) {\n  process.stdout.write(chunk.choices[0]?.delta?.content || '');\n}`)}
                  style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    padding: '5px 12px',
                    borderRadius: '6px',
                    background: 'rgba(255,255,255,0.12)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    color: '#fff',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {copiedKey === 'node_code' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                  <span>{copiedKey === 'node_code' ? 'Copiato!' : 'Copia'}</span>
                </button>
              </div>
            )}

            {/* TAB CONTENT: CURL */}
            {activeVsCodeTab === 'curl' && (
              <div style={{ position: 'relative' }}>
                <pre style={{
                  padding: '16px 18px',
                  borderRadius: '10px',
                  background: '#07090e',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#00f2fe',
                  fontSize: '0.78rem',
                  fontFamily: 'Consolas, monospace',
                  overflowX: 'auto',
                  margin: 0
                }}>{`curl ${effectiveBaseUrl}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sigma" \\
  -d '{
    "model": "${selectedGuideModel || proxyAlias || 'sigma'}",
    "messages": [{"role": "user", "content": "Ciao SigmaEngine!"}],
    "stream": true
  }'`}</pre>
                <button
                  onClick={() => copyKeyToClipboard('curl_code', `curl ${effectiveBaseUrl}/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer sigma" -d "{\\"model\\":\\"${selectedGuideModel || proxyAlias || 'sigma'}\\",\\"messages\\":[{\\"role\\":\\"user\\",\\"content\\":\\"Ciao SigmaEngine!\\"}],\\"stream\\":true}"`)}
                  style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    padding: '5px 12px',
                    borderRadius: '6px',
                    background: 'rgba(255,255,255,0.12)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    color: '#fff',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  {copiedKey === 'curl_code' ? <Check size={13} color="#3fb950" /> : <Copy size={13} />} 
                  <span>{copiedKey === 'curl_code' ? 'Copiato!' : 'Copia'}</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2 CONTENT: 🌐 PROVIDER ESTERNI (INPUT / AGGREGAZIONE) */}
      {/* ========================================================================= */}
      {mainHubTab === 'external_providers' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '22px', width: '100%' }}>
          
          {/* Top Filter & Search Bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '14px',
            padding: '14px 18px',
            borderRadius: '14px',
            background: cardBg,
            border: cardBorder,
            boxShadow: cardShadow,
            width: '100%',
            boxSizing: 'border-box'
          }}>
            {/* Category Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              {[
                { id: 'all', label: 'Tutti i Provider' },
                { id: 'cloud', label: '☁️ Cloud API Vault (OpenAI, DeepSeek, Claude...)' },
                { id: 'local', label: '🐙 Motori Locali (Ollama, LM Studio...)' }
              ].map(cat => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  style={{
                    padding: '7px 14px',
                    borderRadius: '8px',
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    background: activeCategory === cat.id ? '#a855f7' : innerCardBg,
                    color: activeCategory === cat.id ? '#ffffff' : subtitleColor,
                    transition: 'all 0.15s ease'
                  }}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div style={{ position: 'relative', width: '260px' }}>
              <Search size={15} color="#a0a6bc" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Cerca provider..."
                style={{
                  width: '100%',
                  padding: '7px 10px 7px 32px',
                  borderRadius: '8px',
                  background: innerCardBg,
                  border: innerCardBorder,
                  color: titleColor,
                  fontSize: '0.76rem',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          {/* Providers Grid (Full Width) */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: '18px',
            width: '100%'
          }}>
            {filteredProviders.map(pKey => {
              const p = PROVIDER_CATALOG[pKey];
              const pConfig = providerSettings[pKey] || {};
              const testRes = testResults[pKey];
              const isTestingThis = testingProvider === pKey;
              const showKey = visibleKeys[pKey];
              const IconComp = ProviderIcons[pKey] || ProviderIcons.sigma_engine;
              const hasConfiguredKey = pConfig.has_api_key || Boolean(pConfig.api_key);

              // Model Options for CustomSelect
              const modelOptions = (p.popular_models || []).map(m => ({
                value: m,
                label: m,
                badge: p.badge
              }));

              return (
                <div
                  key={pKey}
                  style={{
                    padding: '18px',
                    borderRadius: '14px',
                    background: cardBg,
                    border: hasConfiguredKey ? `1px solid ${p.color}40` : cardBorder,
                    boxShadow: cardShadow,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '14px',
                    boxSizing: 'border-box'
                  }}
                >
                  {/* Card Top: Icon, Label, Badge */}
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{
                          width: '34px',
                          height: '34px',
                          borderRadius: '8px',
                          background: `${p.color}15`,
                          border: `1px solid ${p.color}35`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <IconComp size={20} color={p.color} />
                        </div>
                        <div>
                          <div style={{ fontSize: '0.9rem', fontWeight: 800, color: titleColor }}>{p.label}</div>
                          <div style={{ fontSize: '0.66rem', color: subtitleColor }}>{p.badge}</div>
                        </div>
                      </div>

                      {hasConfiguredKey ? (
                        <span style={{
                          fontSize: '0.64rem',
                          fontWeight: 700,
                          color: '#3fb950',
                          background: 'rgba(63, 185, 80, 0.12)',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          border: '1px solid rgba(63, 185, 80, 0.3)'
                        }}>
                          CONFIGURATO 🟢
                        </span>
                      ) : (
                        <span style={{
                          fontSize: '0.64rem',
                          fontWeight: 700,
                          color: '#a0a6bc',
                          background: 'rgba(255, 255, 255, 0.05)',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          border: '1px solid rgba(255, 255, 255, 0.1)'
                        }}>
                          INATTIVO
                        </span>
                      )}
                    </div>

                    <p style={{ margin: '0 0 12px 0', fontSize: '0.74rem', color: subtitleColor, lineHeight: 1.45 }}>
                      {p.hint}
                    </p>

                    {/* API Key Input (if required) */}
                    {p.api_key_required && (
                      <div style={{ marginBottom: '12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <label style={{ fontSize: '0.7rem', fontWeight: 700, color: subtitleColor }}>API Key</label>
                          {p.docs_url && (
                            <a href={p.docs_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.66rem', color: '#00f2fe', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '2px' }}>
                              Ottieni Chiave <ExternalLink size={10} />
                            </a>
                          )}
                        </div>
                        <div style={{ position: 'relative' }}>
                          <input
                            type={showKey ? 'text' : 'password'}
                            value={pConfig.api_key || ''}
                            onChange={e => {
                              const val = e.target.value;
                              setProviderSettings(prev => ({
                                ...prev,
                                [pKey]: { ...prev[pKey], api_key: val }
                              }));
                            }}
                            placeholder={pConfig.has_api_key ? '•••••••••••••••• (Chiave Salvata)' : p.key_placeholder}
                            style={{
                              width: '100%',
                              padding: '7px 30px 7px 10px',
                              borderRadius: '7px',
                              background: innerCardBg,
                              border: innerCardBorder,
                              color: titleColor,
                              fontSize: '0.76rem',
                              outline: 'none',
                              fontFamily: showKey ? 'monospace' : 'inherit'
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => setVisibleKeys(prev => ({ ...prev, [pKey]: !prev[pKey] }))}
                            style={{
                              position: 'absolute',
                              right: '8px',
                              top: '50%',
                              transform: 'translateY(-50%)',
                              background: 'none',
                              border: 'none',
                              color: subtitleColor,
                              cursor: 'pointer'
                            }}
                          >
                            {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Model Selection via CustomSelect */}
                    <div>
                      <label style={{ fontSize: '0.7rem', fontWeight: 700, color: subtitleColor, marginBottom: '4px', display: 'block' }}>
                        Modello Predefinito
                      </label>
                      <CustomSelect
                        value={pConfig.model || p.default_model}
                        onChange={val => {
                          setProviderSettings(prev => ({
                            ...prev,
                            [pKey]: { ...prev[pKey], model: val }
                          }));
                        }}
                        options={modelOptions}
                        placeholder="Seleziona modello..."
                        variant="purple"
                      />
                    </div>
                  </div>

                  {/* Card Bottom: Test Connection & Status */}
                  <div style={{ borderTop: innerCardBorder, paddingTop: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                      <button
                        onClick={() => testProviderConnection(pKey)}
                        disabled={isTestingThis}
                        style={{
                          flex: 1,
                          padding: '7px 12px',
                          borderRadius: '7px',
                          background: innerCardBg,
                          border: innerCardBorder,
                          color: titleColor,
                          fontSize: '0.74rem',
                          fontWeight: 700,
                          cursor: isTestingThis ? 'not-allowed' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px'
                        }}
                      >
                        {isTestingThis ? <RefreshCw size={13} className="spin" /> : <Wifi size={13} color={p.color} />}
                        <span>{isTestingThis ? 'Verifica in corso...' : 'Verifica Connessione'}</span>
                      </button>
                    </div>

                    {/* Test result message */}
                    {testRes && (
                      <div style={{
                        marginTop: '8px',
                        padding: '6px 10px',
                        borderRadius: '6px',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        background: testRes.success ? 'rgba(63, 185, 80, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                        color: testRes.success ? '#3fb950' : '#ef4444',
                        border: `1px solid ${testRes.success ? 'rgba(63, 185, 80, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
                      }}>
                        {testRes.success ? `✅ ${testRes.message} (${testRes.latency}ms)` : `❌ ${testRes.message}`}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
