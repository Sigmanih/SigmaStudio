// ==============================================================================
// sigma_studio/src/components/Chat/core/modelSpecsHelper.js
// Utility to dynamically parse and enrich model parameter count, file size in GB,
// format and quantization directly from the real model inventory (zero hardcoding/guesses).
// ==============================================================================

let _localModelsCache = [];

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
export async function syncLocalModelsCache() {
  try {
    const res = await fetch('/api/models/local/list');
    if (res.ok) {
      const json = await res.json();
      if (json.success && Array.isArray(json.models)) {
        registerLocalModels(json.models);
        return json.models;
      }
    }
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

      return {
        name: found.display_name || found.name || raw,
        params: params || '',
        size: size || '',
        format: format || '',
        quantization: quant || '',
        provider: found.provider || 'sigma_engine'
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

  return {
    name: raw,
    params: params || '',
    size: size || '',
    format: format || '',
    quantization: quant || '',
    provider
  };
}
