// La Home propone campi di lavoro; i singoli specialisti restano selezionabili in chat.
export const WORK_DOMAINS = [
  { id: 'development', name: 'Sviluppo', title: 'Architettura, codice e verifiche', match: /svilupp|programm|code|coder|developer|software|test.engineer|revis.*codice/i },
  { id: 'hardware', name: 'Hardware', title: 'Circuiti, schede e dispositivi', match: /hardware|elettronic|circuit|kicad|pcb|\beda\b|domotic|iot/i },
  { id: 'creative', name: 'Creatività', title: 'Film, immagini, audio e storie', match: /creativ|regis|scenegg|fotograf|montagg|video|audio|music|sound|voce|voice|design|artist|multimodal|grafica/i },
  { id: 'health', name: 'Salute', title: 'Studio e analisi in ambito medico', match: /medic|clin|salute|biolog/i },
  { id: 'legal', name: 'Diritto ed economia', title: 'Analisi giuridica e finanziaria', match: /avvocat|giur|legale|diritto|finanz|econom|quant.law/i },
  { id: 'research', name: 'Ricerca e studio', title: 'Scienza, conoscenza e formazione', match: /ricerc|research|matemat|math|fisic|scienz|statist|professor|teacher|tutor|knowledge|training|benchmark|valutazione/i },
  { id: 'communication', name: 'Comunicazione', title: 'Messaggi, pubblicazione e ricerca web', match: /comunic|messagg|email|social|youtube|marketing|network.lab|web/i },
  { id: 'systems', name: 'Sistemi e modelli', title: 'Risorse, modelli e orchestrazione', match: /sistem|system|architect|architett|kernel|admin|modelli|model.hub|pesi|cluster|rete|network|infrastrutt/i },
  { id: 'general', name: 'Assistente', title: 'Obiettivi, pianificazione e supporto', match: /.*/ },
];

export function workDomainFor(item = {}) {
  const declared = item.workDomain || item.work_domain;
  const explicit = WORK_DOMAINS.find(domain => domain.id === declared);
  if (explicit) return explicit;
  const text = [item.id, item.name, item.title, item.role, item.category].filter(Boolean).join(' ');
  return WORK_DOMAINS.find(domain => domain.match.test(text));
}

function representativeRank(role) {
  const text = [role.id, role.name, role.title].filter(Boolean).join(' ');
  const specialist = /test|review|revis|audit|proof/i.test(text) ? -20 : 0;
  return specialist + (/architect|architett|director|direttor|regista|lead/i.test(text) ? 10 : 0);
}

export function groupWorkDomains(roles = []) {
  const available = roles.filter(role => role && role.active !== false && role.installed !== false);
  return WORK_DOMAINS.flatMap(domain => {
    const members = available.filter(role => workDomainFor(role).id === domain.id);
    if (!members.length) return [];
    members.sort((a, b) => representativeRank(b) - representativeRank(a)
      || String(a.name || a.id).localeCompare(String(b.name || b.id), 'it'));
    return [{ ...members[0], roleName: members[0].name, name: domain.name, title: domain.title,
      workDomain: domain.id, members }];
  });
}

export function modulesForDomain(domainId, catalog = []) {
  return catalog.filter(entry => entry.available === true && workDomainFor(entry).id === domainId)
    .flatMap(entry => {
      const tabs = Array.isArray(entry.workspaceTabs) ? entry.workspaceTabs : [];
      const seen = new Set();
      return [{ id: entry.tabType, name: entry.name }, ...tabs].flatMap(tab => {
        if (!tab || typeof tab.id !== 'string' || !tab.id || seen.has(tab.id)) return [];
        seen.add(tab.id);
        return [{ ...entry, tabType: tab.id, name: tab.name || entry.name }];
      });
    });
}
