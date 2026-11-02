export function modelName(value) {
  if (typeof value === 'string') return value.trim();
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '';
  for (const key of ['name', 'display_name', 'filename', 'model_id']) {
    if (typeof value[key] === 'string' && value[key].trim()) return value[key].trim();
  }
  return '';
}

export function modelNames(values) {
  return Array.isArray(values) ? [...new Set(values.map(modelName).filter(Boolean))] : [];
}
