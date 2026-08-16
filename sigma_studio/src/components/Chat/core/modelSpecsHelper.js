// ==============================================================================
// sigma_studio/src/components/Chat/core/modelSpecsHelper.js
// Utility to parse and enrich model parameter count, file size in GB, format and hardware tier
// ==============================================================================

export function getModelSpecs(modelName, availableModels = []) {
  if (!modelName) return null;
  const raw = String(modelName).trim();
  const lower = raw.toLowerCase();

  // 1. Search in availableModels array first
  if (Array.isArray(availableModels) && availableModels.length > 0) {
    const found = availableModels.find(m => 
      (m.name && m.name.toLowerCase() === lower) || 
      (m.filename && m.filename.toLowerCase() === lower) ||
      (m.model_id && m.model_id.toLowerCase() === lower) ||
      (m.display_name && m.display_name.toLowerCase() === lower)
    );

    if (found) {
      let params = found.params_label || '';
      if (!params) {
        if (/2\.4t/i.test(raw) || /a95b/i.test(raw)) params = '95B Attivi (2.4T)';
        else if (/671b/i.test(raw)) params = '37B Attivi (671B)';
        else {
          const pMatch = raw.match(/([0-9.]+[bBmMtT])/);
          if (pMatch) params = pMatch[1].toUpperCase();
        }
      }
      return {
        name: found.display_name || found.name || raw,
        params: params || '7B',
        size: found.size_label || (found.size_gb ? `~${found.size_gb} GB` : (found.size || 'Local')),
        format: found.format || (lower.includes('gguf') ? 'GGUF' : (lower.includes('safetensors') ? 'Safetensors' : '')),
        quantization: found.quantization || '',
        provider: found.provider || 'sigma_engine'
      };
    }
  }

  // 2. Intelligent regex and heuristic parsing for recognized architectures
  let params = '';
  let size = '';
  let format = '';

  if (/2\.4t/i.test(raw) || /a95b/i.test(raw)) {
    params = '95B Attivi (2.4T)';
    size = '~2.5 TB';
    format = 'Safetensors (FP8)';
  } else if (/671b/i.test(raw)) {
    params = '37B Attivi (671B)';
    size = '~671 GB';
    format = 'Safetensors (FP8)';
  } else if (/27b/i.test(raw)) {
    params = '27B';
    size = '~51.8 GB';
    format = 'Safetensors (FP16)';
  } else if (/70b/i.test(raw)) {
    params = '70B';
    size = '~42 GB';
    format = 'GGUF / Safetensors';
  } else if (/32b|34b|35b/i.test(raw)) {
    params = '32B';
    size = '~20 GB';
    format = 'GGUF';
  } else if (/14b|16b/i.test(raw)) {
    params = '14B';
    size = '~9.2 GB';
    format = 'GGUF';
  } else if (/7b|8b/i.test(raw)) {
    params = '8B';
    size = '~4.9 GB';
    format = 'GGUF';
  } else if (/3b/i.test(raw)) {
    params = '3B';
    size = '~2.0 GB';
    format = 'GGUF';
  } else if (/1\.5b|1b/i.test(raw)) {
    params = '1.5B';
    size = '~1.0 GB';
    format = 'GGUF';
  } else if (/340m/i.test(raw)) {
    params = '340M';
    size = '683 MB';
    format = 'Sigma Compact';
  } else if (/gpt-4o|o1-|o3-/i.test(raw)) {
    params = 'Omni Frontier';
    size = 'Cloud API';
    format = 'Cloud';
  } else if (/claude-3-5|sonnet|opus/i.test(raw)) {
    params = 'Sonnet 3.5';
    size = 'Cloud API';
    format = 'Cloud';
  } else if (/gemini-2|gemini-1\.5/i.test(raw)) {
    params = 'Flash / Pro';
    size = 'Cloud API';
    format = 'Cloud';
  } else if (/deepseek-chat|deepseek-reasoner/i.test(raw)) {
    params = '671B MoE';
    size = 'Cloud API';
    format = 'Cloud';
  }

  const pMatch = !params && raw.match(/([0-9.]+[bBmMtT])/);
  if (pMatch) {
    params = pMatch[1].toUpperCase();
  }

  return {
    name: raw,
    params: params || '',
    size: size || '',
    format: format || '',
    provider: lower.startsWith('gpt-') ? 'openai' : (lower.startsWith('claude') ? 'anthropic' : 'sigma_engine')
  };
}
