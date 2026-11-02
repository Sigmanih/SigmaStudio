import { WORK_DOMAINS, modulesForDomain, workDomainFor } from '../utils/workDomains.js';

const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .toLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();

export function availableWorkspaces(catalog = []) {
  if (!Array.isArray(catalog)) return [];
  return WORK_DOMAINS.flatMap(domain => modulesForDomain(domain.id, catalog)
    .filter(entry => typeof entry.id === 'string' && typeof entry.tabType === 'string')
    .map(entry => ({ moduleId: entry.id, tabType: entry.tabType, name: entry.name, workDomain: domain.id })));
}

export function resolveWorkspaceRequest(text, role, catalog = []) {
  // Solo comandi di navigazione completi: domande tecniche e richieste composte restano all'AI.
  const command = normalize(text).replace(/[.!?]+$/, '').replace(/^per favore[, ]+/, '');
  const match = command.match(/^(?:apri|avvia|mostra|vai a|passa a|entra in|puoi aprire|potresti aprire|mi apri)\s+(.+)$/);
  if (!match) return null;
  const target = match[1].replace(/^(?:(?:il|lo|la|un|uno|una)\s+|l['’])/, '').replace(/[, ]+per favore$/, '');
  const workspaces = availableWorkspaces(catalog);
  const exact = workspaces.filter(entry => [entry.name, entry.tabType, entry.moduleId.replace(/^sigma_/, '')]
    .some(alias => [normalize(alias), `scheda ${normalize(alias)}`, `tab ${normalize(alias)}`].includes(target)));
  let options = exact;
  if (!options.length) {
    const domain = WORK_DOMAINS.find(entry => normalize(entry.name) === target || entry.id === target
      || [`ambiente di ${normalize(entry.name)}`, `laboratorio di ${normalize(entry.name)}`].includes(target));
    const contextual = /^(?:(?:tuo|suo) )?(?:ambiente(?: di lavoro)?|laboratorio|workspace|strumenti|tab|scheda)$/.test(target);
    if (!domain && !contextual) return null;
    if (contextual && (!role || role.path === 'auto' || role.id === 'auto')) {
      return { type: 'choose', options: workspaces, message: 'Scegli lo spazio di lavoro da aprire.' };
    }
    const domainId = domain?.id || workDomainFor(role).id;
    options = workspaces.filter(entry => entry.workDomain === domainId);
  }
  if (options.length === 1) return { type: 'open', options, message: `Ho aperto ${options[0].name}.` };
  if (options.length > 1) return { type: 'choose', options, message: 'Per questo campo sono disponibili più strumenti. Quale vuoi aprire?' };
  return { type: 'unavailable', options: [], message: 'Non ci sono spazi di lavoro disponibili per questo campo.' };
}

export function resolveWorkspaceTarget(target, catalog) {
  if (!target || typeof target.moduleId !== 'string' || typeof target.tabType !== 'string') return null;
  return availableWorkspaces(catalog).find(entry => entry.moduleId === target.moduleId && entry.tabType === target.tabType) || null;
}

export function openAvailableWorkspace(target, catalog, openTab) {
  const current = resolveWorkspaceTarget(target, catalog);
  if (!current || typeof openTab !== 'function') return false;
  openTab({ name: current.name }, current.tabType);
  return true;
}

export function isNavigationRequest(text) {
  return /^(?:per favore[, ]+)?(?:apri|avvia|mostra|vai a|passa a|entra in|puoi aprire|potresti aprire|mi apri)\s+/i.test(String(text || '').trim());
}

export function modelHistory(messages) {
  return (Array.isArray(messages) ? messages : []).filter(message => !message.localOnly);
}
