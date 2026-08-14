// ==============================================================================
// MODEL-PROVIDER MAP | Associa ogni modello al provider di routing corretto
// ==============================================================================

/**
 * Mappa modello → provider.
 * Ogni modello è associato al suo provider API per il routing.
 * I modelli Ollama sono quelli locali, gli altri vanno su API esterne.
 */
export const MODEL_PROVIDER_MAP = {
  // Ollama (locale)
  'llama3.2': { provider: 'ollama' },
  'llama3.1': { provider: 'ollama' },
  'llama3': { provider: 'ollama' },
  'llama2': { provider: 'ollama' },
  'mistral': { provider: 'ollama' },
  'mixtral': { provider: 'ollama' },
  'codellama': { provider: 'ollama' },
  'gemma': { provider: 'ollama' },
  'gemma2': { provider: 'ollama' },
  'phi': { provider: 'ollama' },
  'phi3': { provider: 'ollama' },
  'qwen': { provider: 'ollama' },
  'qwen2': { provider: 'ollama' },
  'deepseek-r1': { provider: 'ollama' },
  'deepseek-coder-v2': { provider: 'ollama' },
  'nomic-embed-text': { provider: 'ollama' },
  'nous-hermes2': { provider: 'ollama' },
  'starling-lm': { provider: 'ollama' },
  'openchat': { provider: 'ollama' },
  'neural-chat': { provider: 'ollama' },
  'solar': { provider: 'ollama' },
  'orca-mini': { provider: 'ollama' },
  'tinydolphin': { provider: 'ollama' },
  'sigma_architect_gwen3_6_35b': { provider: 'ollama' },
  'sigma_architect_gwen3_6_35b:latest': { provider: 'ollama' },
  'math1': { provider: 'ollama' },
  // DeepSeek API
  'deepseek-chat': { provider: 'deepseek' },
  'deepseek-reasoner': { provider: 'deepseek' },
  'deepseek-coder': { provider: 'deepseek' },
  'deepseek-v4-flash': { provider: 'deepseek' },
  'deepseek-v4-pro': { provider: 'deepseek' },
  // OpenAI
  'gpt-4o': { provider: 'openai' },
  'gpt-4o-mini': { provider: 'openai' },
  'gpt-4-turbo': { provider: 'openai' },
  'gpt-4': { provider: 'openai' },
  'gpt-3.5-turbo': { provider: 'openai' },
  'o1': { provider: 'openai' },
  'o3-mini': { provider: 'openai' },
  // Anthropic
  'claude-sonnet-4-20250514': { provider: 'anthropic' },
  'claude-sonnet-4': { provider: 'anthropic' },
  'claude-3-5-sonnet-20241022': { provider: 'anthropic' },
  'claude-3-opus-20240229': { provider: 'anthropic' },
  'claude-3-haiku-20240307': { provider: 'anthropic' },
  // Groq
  'llama-3.3-70b-versatile': { provider: 'groq' },
  'llama-3.1-8b-instant': { provider: 'groq' },
  'mixtral-8x7b-32768': { provider: 'groq' },
  'gemma2-9b-it': { provider: 'groq' },
  'deepseek-r1-distill-llama-70b': { provider: 'groq' },
  // OpenRouter
  'openai/gpt-4o-mini': { provider: 'openrouter' },
  'openai/gpt-4o': { provider: 'openrouter' },
  'anthropic/claude-sonnet-4': { provider: 'openrouter' },
  'google/gemini-pro-1.5': { provider: 'openrouter' },
  'mistral/mixtral-8x22b': { provider: 'openrouter' },
  'deepseek/deepseek-r1': { provider: 'openrouter' },
  // Google Gemini
  'gemini-2.0-flash': { provider: 'google' },
  'gemini-2.0-pro': { provider: 'google' },
  'gemini-2.0-flash-lite': { provider: 'google' },
  'gemini-1.5-pro': { provider: 'google' },
  'gemini-1.5-flash': { provider: 'google' },
  'gemini-1.5-flash-8b': { provider: 'google' },
  // Mistral AI
  'mistral-large-latest': { provider: 'mistral' },
  'mistral-small-latest': { provider: 'mistral' },
  'codestral-latest': { provider: 'mistral' },
  'mistral-medium-latest': { provider: 'mistral' },
  'open-mistral-nemo': { provider: 'mistral' },
  // xAI (Grok)
  'grok-2': { provider: 'xai' },
  'grok-2-mini': { provider: 'xai' },
  'grok-beta': { provider: 'xai' },
  'grok-2-vision': { provider: 'xai' },
  // Perplexity
  'sonar-pro': { provider: 'perplexity' },
  'sonar': { provider: 'perplexity' },
  'llama-3.1-sonar-small': { provider: 'perplexity' },
  'llama-3.1-sonar-large': { provider: 'perplexity' },
  'llama-3.1-sonar-huge': { provider: 'perplexity' },
  // Together AI
  'mistralai/Mixtral-8x22B-Instruct-v0.1': { provider: 'together' },
  'meta-llama/Llama-3.3-70B-Instruct-Turbo': { provider: 'together' },
  'deepseek-ai/deepseek-coder-v2-instruct': { provider: 'together' },
  'Qwen/Qwen2.5-72B-Instruct-Turbo': { provider: 'together' },
  'meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo': { provider: 'together' },
  // Qwen (Alibaba Cloud)
  'qwen-max': { provider: 'qwen' },
  'qwen-plus': { provider: 'qwen' },
  'qwen-turbo': { provider: 'qwen' },
  'qwen2.5-72b-instruct': { provider: 'qwen' },
  'qwen2.5-32b-instruct': { provider: 'qwen' },
  'qwen2.5-14b-instruct': { provider: 'qwen' },
  'qwen2.5-7b-instruct': { provider: 'qwen' },
  'qwen2.5-coder-32b-instruct': { provider: 'qwen' },
  'qwen2.5-math-72b-instruct': { provider: 'qwen' },
  // GLM (Zhipu AI)
  'glm-4-plus': { provider: 'glm' },
  'glm-4-0520': { provider: 'glm' },
  'glm-4-air': { provider: 'glm' },
  'glm-4-flash': { provider: 'glm' },
  'glm-4-long': { provider: 'glm' },
  'glm-4v-plus': { provider: 'glm' },
  'glm-4v': { provider: 'glm' },
  // Moonshot (Kimi)
  'moonshot-v1-8k': { provider: 'moonshot' },
  'moonshot-v1-32k': { provider: 'moonshot' },
  'moonshot-v1-128k': { provider: 'moonshot' },
  'moonshot-v1-auto': { provider: 'moonshot' },
  // Yi (01.AI)
  'yi-large': { provider: 'yi' },
  'yi-medium': { provider: 'yi' },
  'yi-vision': { provider: 'yi' },
  'yi-large-rag': { provider: 'yi' },
  'yi-large-turbo': { provider: 'yi' },
  'yi-lightning': { provider: 'yi' },
  'yi-large-preview': { provider: 'yi' },
};

/**
 * Colori per i badge dei provider.
 */
export const PROVIDER_COLORS = {
  ollama: { bg: '#1a1a2e', color: '#e94560' },
  deepseek: { bg: '#1a2e1a', color: '#4ecdc4' },
  openai: { bg: '#1a2e2e', color: '#74b9ff' },
  anthropic: { bg: '#2e1a2e', color: '#a29bfe' },
  groq: { bg: '#2e2e1a', color: '#fdcb6e' },
  openrouter: { bg: '#1a2e1a', color: '#00b894' },
  google: { bg: '#1a1a3e', color: '#4285f4' },
  mistral: { bg: '#2e1a1a', color: '#ff6b6b' },
  xai: { bg: '#1a2e2a', color: '#00ff88' },
  perplexity: { bg: '#2e1a2e', color: '#ff9ff3' },
  together: { bg: '#2e2e2e', color: '#ffd93d' },
  qwen: { bg: '#1a2a1a', color: '#6bff6b' },
  glm: { bg: '#2a1a2a', color: '#c084fc' },
  moonshot: { bg: '#1a1a2a', color: '#60a5fa' },
  yi: { bg: '#2a2a1a', color: '#facc15' },
};

/**
 * Trova il provider per un modello basandosi sul nome.
 * @param {string} modelName - Nome del modello
 * @param {Object} providerConfigs - Configurazioni provider dal server
 * @returns {string} Chiave del provider
 */
export function getProviderForModel(modelName, providerConfigs) {
  if (!modelName) return 'ollama';

  // Rule 0: Tag syntax with colon (e.g. 'deepseek-r1:70b', 'qwen3.6:35b', 'llama3:latest') is ALWAYS Ollama local
  if (modelName.includes(':')) {
    return 'ollama';
  }

  // 1) Direct map check
  if (MODEL_PROVIDER_MAP[modelName]?.provider) {
    return MODEL_PROVIDER_MAP[modelName].provider;
  }

  // 2) Check providerConfigs for exact configured models
  if (providerConfigs) {
    for (const [pk, pv] of Object.entries(providerConfigs)) {
      if (pk === 'ollama') continue;
      if ((pv.models || []).includes(modelName) || pv.model === modelName) {
        if (pv.has_api_key || (pv.api_key && pv.api_key.trim().length > 0) || pv.endpoint || pv.api_url) {
          return pk;
        }
      }
    }
  }

  // 3) Strict Cloud-only prefixes
  const providerMap = [
    { prefixes: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder'], provider: 'deepseek' },
    { prefixes: ['gpt-', 'o1-', 'o1', 'o3-', 'chatgpt-'], provider: 'openai' },
    { prefixes: ['claude-'], provider: 'anthropic' },
    { prefixes: ['gemini-'], provider: 'google' },
    { prefixes: ['mistral-large', 'mistral-small', 'codestral-', 'open-mistral'], provider: 'mistral' },
    { prefixes: ['grok-', 'grok-2'], provider: 'xai' },
    { prefixes: ['sonar'], provider: 'perplexity' },
    { prefixes: ['llama-3.3-70b', 'llama-3.1-8b', 'mixtral-8x7b', 'gemma2-9b', 'deepseek-r1-distill'], provider: 'groq' },
    { prefixes: ['openai/', 'anthropic/', 'google/', 'mistral/', 'deepseek/'], provider: 'openrouter' },
    { prefixes: ['qwen-plus', 'qwen-max', 'qwen-turbo'], provider: 'qwen' },
    { prefixes: ['glm-4'], provider: 'glm' },
    { prefixes: ['moonshot-v1'], provider: 'moonshot' },
    { prefixes: ['yi-large', 'yi-medium'], provider: 'yi' },
  ];

  for (const entry of providerMap) {
    for (const prefix of entry.prefixes) {
      if (modelName.toLowerCase().startsWith(prefix)) {
        return entry.provider;
      }
    }
  }

  // Default: ollama
  return 'ollama';
}

/**
 * Ottiene le info di routing per un dato modello.
 * @param {string} modelName
 * @param {Object} providerConfigs
 * @returns {{ provider: string, endpoint: string, api_url: string }}
 */
export function getModelRoutingInfo(modelName, providerConfigs) {
  const provider = getProviderForModel(modelName, providerConfigs) || 'ollama';
  const prov = providerConfigs?.[provider] || {};

  return {
    provider,
    endpoint: prov.endpoint || (provider === 'ollama' ? 'http://localhost:11434/api/chat' : ''),
    api_url: prov.api_url || ''
  };
}

/**
 * Provider prefix mapping for ModelSelector.
 */
export const PROVIDER_PREFIX_MAP = [
  { prefixes: ['deepseek-chat', 'deepseek-reasoner', 'deepseek-coder', 'deepseek-v4', 'deepseek/'], provider: 'deepseek' },
  { prefixes: ['gpt-', 'o1', 'o3-'], provider: 'openai' },
  { prefixes: ['claude-'], provider: 'anthropic' },
  { prefixes: ['llama-3.3-70b', 'llama-3.1-8b', 'mixtral-8x7b', 'gemma2-9b', 'deepseek-r1-distill'], provider: 'groq' },
  { prefixes: ['openai/', 'anthropic/', 'google/', 'mistral/', 'deepseek/deepseek'], provider: 'openrouter' },
  { prefixes: ['gemini-', 'gemma-3'], provider: 'google' },
  { prefixes: ['mistral-', 'codestral', 'open-mistral'], provider: 'mistral' },
  { prefixes: ['grok-', 'grok-beta'], provider: 'xai' },
  { prefixes: ['sonar', 'llama-3.1-sonar'], provider: 'perplexity' },
  { prefixes: ['mistralai/', 'meta-llama/', 'deepseek-ai/', 'Qwen/'], provider: 'together' },
  { prefixes: ['qwen-', 'qwen2'], provider: 'qwen' },
  { prefixes: ['glm-'], provider: 'glm' },
  { prefixes: ['moonshot'], provider: 'moonshot' },
  { prefixes: ['yi-'], provider: 'yi' },
];
