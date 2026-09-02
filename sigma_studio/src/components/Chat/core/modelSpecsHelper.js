// ==============================================================================
// sigma_studio/src/components/Chat/core/modelSpecsHelper.js
// Utility to dynamically parse and enrich model parameter count, file size in GB,
// format, quantization, family recognition, benchmark metadata, and live tokens/sec.
// ==============================================================================

let _localModelsCache = [];
const SPEED_STORAGE_KEY = 'sigma_model_chat_speeds';

export const FAMILY_CONFIG = {
  sigmanih: {
    id: 'sigmanih',
    title: 'Sigmanih',
    brand: 'Sigmanih Ecosystem',
    color: '#ffb86c',
    bg: 'rgba(255, 184, 108, 0.15)',
    border: 'rgba(255, 184, 108, 0.35)'
  },
  gemma: {
    id: 'gemma',
    title: 'Gemma',
    brand: 'Google DeepMind',
    color: '#00d2ff',
    bg: 'rgba(0, 210, 255, 0.15)',
    border: 'rgba(0, 210, 255, 0.35)'
  },
  qwen: {
    id: 'qwen',
    title: 'Qwen',
    brand: 'Alibaba Cloud',
    color: '#a855f7',
    bg: 'rgba(168, 85, 247, 0.15)',
    border: 'rgba(168, 85, 247, 0.35)'
  },
  llama: {
    id: 'llama',
    title: 'Llama',
    brand: 'Meta AI',
    color: '#38bdf8',
    bg: 'rgba(56, 189, 248, 0.15)',
    border: 'rgba(56, 189, 248, 0.35)'
  },
  deepseek: {
    id: 'deepseek',
    title: 'DeepSeek',
    brand: 'DeepSeek AI',
    color: '#f43f5e',
    bg: 'rgba(244, 63, 94, 0.15)',
    border: 'rgba(244, 63, 94, 0.35)'
  },
  mistral: {
    id: 'mistral',
    title: 'Mistral',
    brand: 'Mistral AI',
    color: '#10b981',
    bg: 'rgba(168, 85, 247, 0.15)',
    border: 'rgba(16, 185, 129, 0.35)'
  },
  phi: {
    id: 'phi',
    title: 'Phi',
    brand: 'Microsoft Research',
    color: '#fb923c',
    bg: 'rgba(251, 146, 60, 0.15)',
    border: 'rgba(251, 146, 60, 0.35)'
  },
  glm: {
    id: 'glm',
    title: 'GLM',
    brand: 'Zhipu AI',
    color: '#06b6d4',
    bg: 'rgba(6, 182, 212, 0.15)',
    border: 'rgba(6, 182, 212, 0.35)'
  },
  altro: {
    id: 'altro',
    title: 'Altro',
    brand: 'Community',
    color: '#94a3b8',
    bg: 'rgba(148, 163, 184, 0.12)',
    border: 'rgba(148, 163, 184, 0.25)'
  }
};

/**
 * Check if a model belongs to the Sigmanih ecosystem.
 */
export function isSigmanihModel(modelOrName) {
  if (!modelOrName) return false;
  const model = typeof modelOrName === 'object' ? modelOrName : { name: modelOrName };
  const rawName = String(model.name || model.display_name || model.filename || model.model_id || '').toLowerCase();
  const repoId = String(model.publication?.repo_id || '').toLowerCase();
  const author = String(model.author || model.publisher || '').toLowerCase();
  return Boolean(
    model.is_sigmanih ||
    repoId.startsWith('sigmanih/') ||
    author === 'sigmanih' ||
    rawName.startsWith('sigmanih') ||
    rawName.startsWith('sigma-')
  );
}

/**
 * Detect architectural family for a model object or string name.
 */
export function detectModelFamily(modelOrName) {
  if (!modelOrName) return 'altro';
  const model = typeof modelOrName === 'object' ? modelOrName : { name: modelOrName };
  const rawName = String(model.name || model.display_name || model.filename || model.model_id || '').toLowerCase();
  const repoId = String(model.publication?.repo_id || '').toLowerCase();
  const author = String(model.author || model.publisher || '').toLowerCase();
  const arch = String(model.architecture || '').toLowerCase();
  const combined = `${rawName} ${repoId} ${author} ${arch}`;

  // Base architecture check
  if (combined.includes('gemma')) return 'gemma';
  if (combined.includes('qwen') || combined.includes('qwq')) return 'qwen';
  if (combined.includes('llama') || combined.includes('meta')) return 'llama';
  if (combined.includes('deepseek') || combined.includes('r1')) return 'deepseek';
  if (combined.includes('mistral') || combined.includes('mixtral') || combined.includes('codestral') || combined.includes('pixtral') || combined.includes('ministral')) return 'mistral';
  if (combined.includes('phi')) return 'phi';
  if (combined.includes('glm') || combined.includes('chatglm') || combined.includes('zai')) return 'glm';

  if (isSigmanihModel(model)) {
    return 'sigmanih';
  }

  if (model.family) {
    const fLower = String(model.family).toLowerCase();
    if (FAMILY_CONFIG[fLower]) return fLower;
  }
  return 'altro';
}


/**
 * Retrieves all saved chat generation speeds (t/s) from localStorage.
 */
export function getAllModelChatSpeeds() {
  try {
    const raw = localStorage.getItem(SPEED_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

/**
 * Checks if a message text is an error output rather than valid generated inference content.
 */
export function isErrorMessage(text) {
  if (!text || typeof text !== 'string') return false;
  const trimmed = text.trim();
  return (
    trimmed.startsWith('❌') ||
    trimmed.startsWith('⚠️') ||
    trimmed.startsWith('Error:') ||
    trimmed.startsWith('Errore:') ||
    /^(?:❌|⚠️|\*\*Errore|\*\*Error|Error:|Errore:)/i.test(trimmed) ||
    /SigmaEngine non ha potuto caricare/i.test(trimmed) ||
    /llama-server non ha risposto/i.test(trimmed) ||
    /non ha potuto caricare/i.test(trimmed) ||
    /Errore caricamento modello/i.test(trimmed)
  );
}

/**
 * Removes recorded chat speed for a model (e.g. if an error occurred or speed was corrupted).
 */
export function removeModelChatSpeed(modelName) {
  if (!modelName) return;
  const rawKey = String(modelName).trim();
  const cleanKey = rawKey.toLowerCase().replace(/\.gguf$/i, '').replace(/^[a-z0-9_-]+--/i, '').replace(/^[a-z0-9_-]+\//i, '');
  try {
    const speeds = getAllModelChatSpeeds();
    delete speeds[rawKey];
    delete speeds[rawKey.toLowerCase()];
    if (cleanKey) delete speeds[cleanKey];
    localStorage.setItem(SPEED_STORAGE_KEY, JSON.stringify(speeds));
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('sigma-model-speed-updated', { detail: { model: modelName, tps: null } }));
    }
  } catch (e) {
    console.debug('[modelSpecsHelper] speed remove error:', e);
  }
}

/**
 * Records live measured tokens per second (t/s) for a model after chatting.
 */
export function recordModelChatSpeed(modelName, tps) {
  if (!modelName || tps === undefined || tps === null || isNaN(tps) || tps <= 0) return;
  const num = parseFloat(Number(tps).toFixed(1));
  const rawKey = String(modelName).trim();
  const cleanKey = rawKey.toLowerCase().replace(/\.gguf$/i, '').replace(/^[a-z0-9_-]+--/i, '').replace(/^[a-z0-9_-]+\//i, '');

  try {
    const speeds = getAllModelChatSpeeds();
    speeds[rawKey] = { tps: num, timestamp: Date.now() };
    speeds[rawKey.toLowerCase()] = { tps: num, timestamp: Date.now() };
    if (cleanKey && cleanKey !== rawKey.toLowerCase()) {
      speeds[cleanKey] = { tps: num, timestamp: Date.now() };
    }
    localStorage.setItem(SPEED_STORAGE_KEY, JSON.stringify(speeds));
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('sigma-model-speed-updated', { detail: { model: modelName, tps: num } }));
    }
  } catch (e) {
    console.debug('[modelSpecsHelper] speed record error:', e);
  }
}

/**
 * Gets recorded chat speed (t/s) for a model, or null if never chatted.
 */
export function getModelChatSpeed(modelName, modelObj = null) {
  if (!modelName && !modelObj) return null;
  const speeds = getAllModelChatSpeeds();
  const candidates = [
    modelName,
    typeof modelName === 'string' ? modelName.toLowerCase() : null,
    modelObj?.name,
    modelObj?.name?.toLowerCase?.(),
    modelObj?.filename,
    modelObj?.filename?.toLowerCase?.(),
    modelObj?.model_id,
    modelObj?.model_id?.toLowerCase?.(),
    modelObj?.display_name,
    modelObj?.display_name?.toLowerCase?.()
  ].filter(Boolean);

  for (const k of candidates) {
    if (speeds[k]?.tps !== undefined) {
      return speeds[k].tps;
    }
    const clean = k.replace(/\.gguf$/i, '').replace(/^[a-z0-9_-]+--/i, '').replace(/^[a-z0-9_-]+\//i, '');
    if (speeds[clean]?.tps !== undefined) {
      return speeds[clean].tps;
    }
  }

  return null;
}

/**
 * Register scanned local models from backend into cache for instant resolution anywhere.
 */
export function registerLocalModels(models = []) {
  if (Array.isArray(models) && models.length > 0) {
    _localModelsCache = models;
  }
}

/**
 * Lazily fetch local models inventory if cache is empty.
 */
export function syncLocalModelsCache() {
  try {
    fetch('/api/models/local/list')
      .then(res => res.json())
      .then(json => {
        if (json.success && Array.isArray(json.models)) {
          registerLocalModels(json.models);
        }
      })
      .catch(e => console.debug('[modelSpecsHelper] sync error:', e));
  } catch (e) {
    console.debug('[modelSpecsHelper] sync error:', e);
  }
  return _localModelsCache;
}

// Initial async warm-up
if (typeof window !== 'undefined') {
  setTimeout(() => { syncLocalModelsCache(); }, 300);
}

/**
 * Extract clean, precise specs for a given model name using live metadata or dynamic parsing.
 */
export function getModelSpecs(modelName, availableModels = []) {
  if (!modelName) return null;
  const raw = String(modelName).trim();
  const lower = raw.toLowerCase();

  // Combine passed availableModels with global cache
  const candidatePool = (Array.isArray(availableModels) && availableModels.length > 0)
    ? [...availableModels, ..._localModelsCache]
    : _localModelsCache;

  // 1. Search in candidate pool
  if (candidatePool.length > 0) {
    const cleanRaw = lower.replace(/\.gguf$/i, '').replace(/^.*\//, '').replace(/^.*\\/, '');

    const found = candidatePool.find(m => {
      if (!m) return false;
      const mName = (m.name || '').toLowerCase();
      const mFile = (m.filename || '').toLowerCase();
      const mId = (m.model_id || '').toLowerCase();
      const mDisp = (m.display_name || '').toLowerCase();

      return (
        mName === lower || mFile === lower || mId === lower || mDisp === lower ||
        mFile.replace(/\.gguf$/i, '') === cleanRaw ||
        mDisp.replace(/\.gguf$/i, '') === cleanRaw ||
        cleanRaw.includes(mFile.replace(/\.gguf$/i, '')) ||
        (mFile && cleanRaw.includes(mFile))
      );
    });

    if (found) {
      // Dynamic Parameter Count extraction
      let params = found.params_label || '';
      if (!params) {
        if (/2\.4t/i.test(raw) || /a95b/i.test(raw)) params = '95B (2.4T)';
        else if (/671b/i.test(raw)) params = '37B (671B)';
        else {
          const pMatch = raw.match(/(?:^|[_\-./ ])([0-9.]+[bBmMtT])(?:[_\-./ ]|$)/) || raw.match(/([0-9.]+[bBmMtT])/);
          if (pMatch) params = pMatch[1].toUpperCase();
        }
      }

      // Dynamic Quantization
      const quant = found.quantization && found.quantization !== 'Standard'
        ? found.quantization
        : (raw.match(/(Q[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|FP8|INT8|INT4|AWQ|EXL2)/i)?.[1]?.toUpperCase() || '');

      // Dynamic Format
      let format = found.format || (lower.includes('gguf') ? 'GGUF' : (lower.includes('safetensors') ? 'Safetensors' : ''));
      if (!format && (lower.includes('.gguf') || quant.startsWith('Q'))) format = 'GGUF';
      if (format === 'GGUF' && quant && !format.includes(quant)) {
        format = `GGUF (${quant})`;
      }

      // Real disk size measured from host storage
      let size = found.size_label;
      if (!size && found.size_gb) {
        size = found.size_gb >= 1000 ? `~${(found.size_gb / 1024).toFixed(1)} TB` : `~${found.size_gb.toFixed(1)} GB`;
      } else if (!size && found.size) {
        size = found.size;
      }

      const family = detectModelFamily(found);
      const chatSpeed = getModelChatSpeed(found.name || raw, found);

      return {
        name: found.display_name || found.name || raw,
        params: params || '',
        size: size || '',
        format: format || '',
        quantization: quant || '',
        provider: found.provider || 'sigma_engine',
        family,
        benchmark: found.benchmark_summary || null,
        chatSpeed: chatSpeed !== null ? chatSpeed : null,
        rawModel: found
      };
    }
  }

  // 2. Dynamic regex parsing (Zero hardcoded fake numbers)
  let params = '';
  let format = '';
  let size = '';

  // Extract Parameter Count (e.g. 27B, 14B, 7B, 32B, 70B, 3B, 1.5B, 340M, 671B)
  const pMatch = raw.match(/(?:^|[_\-./ ])([0-9.]+[bBmMtT])(?:[_\-./ ]|$)/) || raw.match(/([0-9.]+[bBmMtT])/);
  if (pMatch) {
    params = pMatch[1].toUpperCase();
  }

  // Extract Quantization
  const quantMatch = raw.match(/(Q[0-9]_[A-Z0-9_]+|FP16|FP32|BF16|FP8|INT8|INT4|AWQ|EXL2)/i);
  const quant = quantMatch ? quantMatch[1].toUpperCase() : '';

  // Extract Format
  if (lower.includes('.gguf') || lower.includes('gguf') || (quant && quant.startsWith('Q'))) {
    format = quant ? `GGUF (${quant})` : 'GGUF';
  } else if (lower.includes('safetensors')) {
    format = quant ? `Safetensors (${quant})` : 'Safetensors';
  } else if (/gpt-4o|o1-|o3-/i.test(raw)) {
    params = params || 'Omni';
    format = 'Cloud';
    size = 'Cloud API';
  } else if (/claude-3-5|claude-3-7|sonnet|opus/i.test(raw)) {
    params = params || 'Claude 3.5';
    format = 'Cloud';
    size = 'Cloud API';
  } else if (/gemini-2|gemini-1\.5/i.test(raw)) {
    params = params || 'Gemini';
    format = 'Cloud';
    size = 'Cloud API';
  } else if (/deepseek-chat|deepseek-reasoner/i.test(raw)) {
    params = params || '671B MoE';
    format = 'Cloud';
    size = 'Cloud API';
  }

  // Determine Provider
  let provider = 'sigma_engine';
  if (lower.startsWith('gpt-') || lower.startsWith('o1') || lower.startsWith('o3')) provider = 'openai';
  else if (lower.startsWith('claude')) provider = 'anthropic';
  else if (lower.startsWith('gemini')) provider = 'google';
  else if (lower.startsWith('deepseek-chat') || lower.startsWith('deepseek-reasoner')) provider = 'deepseek';

  const family = detectModelFamily({ name: raw });
  const chatSpeed = getModelChatSpeed(raw);

  return {
    name: raw,
    params: params || '',
    size: size || '',
    format: format || '',
    quantization: quant || '',
    provider,
    family,
    benchmark: null,
    chatSpeed: chatSpeed !== null ? chatSpeed : null
  };
}

/**
 * Convert parameter string (e.g. "70B", "32B", "340M", "1.5B", "2.4T", "16x17B") to numeric value in billions.
 */
export function parseParamsNumeric(paramsStr, modelObj = null) {
  if (modelObj?.params_count && !isNaN(modelObj.params_count)) {
    return Number(modelObj.params_count);
  }
  let str = paramsStr || modelObj?.params_label || modelObj?.parameters || '';
  if (!str) {
    const raw = String(modelObj?.name || modelObj?.filename || modelObj?.model_id || '');
    const m = raw.match(/(?:^|[_\-./ ])([0-9.]+)\s*([bBmMtT])(?:[_\-./ ]|$)/) || raw.match(/([0-9.]+)\s*([bBmMtT])/);
    if (m) str = `${m[1]}${m[2]}`;
  }
  if (!str || typeof str !== 'string') return 0;

  // Handle MoE e.g. "16x17B"
  const moeMatch = str.match(/(\d+)\s*[xX]\s*(\d+(?:\.\d+)?)\s*([bBmMtT])?/i);
  if (moeMatch) {
    const numExperts = parseFloat(moeMatch[1]);
    const expertSize = parseFloat(moeMatch[2]);
    const unit = (moeMatch[3] || 'B').toUpperCase();
    let mult = 1;
    if (unit === 'T') mult = 1000;
    else if (unit === 'M') mult = 0.001;
    return numExperts * expertSize * mult;
  }

  // Handle formats like "95B (2.4T)" or "37B (671B)"
  const firstMatch = str.match(/([0-9.]+)\s*([bBmMtT])/i);
  if (firstMatch) {
    const val = parseFloat(firstMatch[1]);
    const unit = firstMatch[2].toUpperCase();
    if (unit === 'T') return val * 1000;
    if (unit === 'B') return val;
    if (unit === 'M') return val * 0.001;
    if (unit === 'K') return val * 0.000001;
  }
  return 0;
}

/**
 * Convert size string or raw bytes/gb into numeric GB.
 */
export function parseSizeNumericGB(sizeStr, modelObj = null) {
  if (modelObj?.size_gb !== undefined && modelObj.size_gb !== null && !isNaN(modelObj.size_gb)) {
    return Number(modelObj.size_gb);
  }
  if (modelObj?.size_bytes !== undefined && modelObj.size_bytes !== null && !isNaN(modelObj.size_bytes)) {
    return Number(modelObj.size_bytes) / (1024 * 1024 * 1024);
  }
  const s = sizeStr || modelObj?.size || modelObj?.size_label || '';
  if (!s || typeof s !== 'string') return 0;

  const match = s.match(/([0-9.]+)\s*([tTgGmMkK]b?)/i);
  if (match) {
    const val = parseFloat(match[1]);
    const unit = match[2].toUpperCase();
    if (unit.startsWith('T')) return val * 1024;
    if (unit.startsWith('G')) return val;
    if (unit.startsWith('M')) return val / 1024;
    if (unit.startsWith('K')) return val / (1024 * 1024);
  }
  return 0;
}

/**
 * Extract benchmark score percentage (0 - 100).
 */
export function getBenchmarkScoreNumeric(modelObj, itemSpecs = null) {
  const bm = modelObj?.benchmark_summary || itemSpecs?.benchmark || null;
  if (!bm) return 0;
  const score = bm.score ?? bm.overall_pass_rate ?? bm.best_score;
  if (score !== undefined && score !== null && !isNaN(score)) {
    return Number(score);
  }
  return 0;
}

/**
 * Extract live tokens per second.
 */
export function getSpeedTpsNumeric(modelObj) {
  const chatTps = getModelChatSpeed(modelObj?.name, modelObj) ?? modelObj?.benchmark_summary?.tokens_per_sec;
  if (chatTps !== undefined && chatTps !== null && !isNaN(chatTps)) {
    return Number(chatTps);
  }
  return 0;
}

/**
 * Sorts a list of models according to criterion ('default', 'size', 'params', 'speed', 'benchmark', 'name') and order ('desc', 'asc').
 */
export function sortModelsList(modelsList = [], sortBy = 'default', sortOrder = 'desc', allModelsPool = []) {
  if (!Array.isArray(modelsList) || modelsList.length <= 1) return modelsList;
  if (sortBy === 'default') {
    if (sortOrder === 'asc') {
      return [...modelsList].sort((a, b) => {
        const nameA = String(a.display_name || a.clean_name || a.name || '').toLowerCase();
        const nameB = String(b.display_name || b.clean_name || b.name || '').toLowerCase();
        return nameA.localeCompare(nameB);
      });
    }
    return modelsList;
  }

  const sorted = [...modelsList].sort((a, b) => {
    const specsA = getModelSpecs(a.name, allModelsPool);
    const specsB = getModelSpecs(b.name, allModelsPool);

    let valA = 0;
    let valB = 0;

    switch (sortBy) {
      case 'size':
        valA = parseSizeNumericGB(specsA?.size, a);
        valB = parseSizeNumericGB(specsB?.size, b);
        break;
      case 'params':
        valA = parseParamsNumeric(specsA?.params, a);
        valB = parseParamsNumeric(specsB?.params, b);
        break;
      case 'speed':
        valA = getSpeedTpsNumeric(a) || (specsA?.chatSpeed ?? 0);
        valB = getSpeedTpsNumeric(b) || (specsB?.chatSpeed ?? 0);
        break;
      case 'benchmark':
        valA = getBenchmarkScoreNumeric(a, specsA);
        valB = getBenchmarkScoreNumeric(b, specsB);
        break;
      case 'name': {
        const nameA = String(a.display_name || a.clean_name || a.name || '').toLowerCase();
        const nameB = String(b.display_name || b.clean_name || b.name || '').toLowerCase();
        return sortOrder === 'asc' ? nameA.localeCompare(nameB) : nameB.localeCompare(nameA);
      }
      default:
        return 0;
    }

    if (valA !== valB) {
      return sortOrder === 'asc' ? valA - valB : valB - valA;
    }

    // Tie breaker: name A-Z
    const nameA = String(a.display_name || a.clean_name || a.name || '').toLowerCase();
    const nameB = String(b.display_name || b.clean_name || b.name || '').toLowerCase();
    return nameA.localeCompare(nameB);
  });

  return sorted;
}

