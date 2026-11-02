export function prepareRoleChat(storage, { roleId = 'auto', text = '', files = [], send = false } = {}) {
  // L'invio si abilita per ultimo: un errore di quota non deve inviare un messaggio precedente.
  storage.removeItem('sigma_pending_chat_send');
  storage.removeItem('sigma_pending_chat_prompt');
  storage.removeItem('sigma_pending_chat_files');
  storage.setItem('sigma_active_role', roleId || 'auto');
  if (text.trim()) storage.setItem('sigma_pending_chat_prompt', text.trim());
  if (files.length) storage.setItem('sigma_pending_chat_files', JSON.stringify(files));
  if (send && (text.trim() || files.length)) storage.setItem('sigma_pending_chat_send', '1');
}

export function findRoleManifesto(manifestos, roleId) {
  const basename = value => String(value || '').replaceAll('\\', '/').split('/').pop().replace(/\.md$/i, '').toLowerCase();
  const wanted = basename(roleId);
  if (!wanted) return undefined;
  return manifestos.find(role => [role.id, role.filename, role.path].some(value => basename(value) === wanted));
}
