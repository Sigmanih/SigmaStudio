// Home, agenti e sidebar devono aprire le stesse destinazioni e sottosezioni.
export const WORKSPACE_TITLES = {
  multimedia: 'Multimedia', whitepapers_lib: 'Agenti',
  creative_studio: 'Immagini', video_studio: 'Video', voice_studio: 'Audio', music: 'Radio',
  developer_studio: 'Developer Sigma', model_hub: 'Modelli', research_lab: 'Pipelines',
  training_lab: 'Training', benchmark_lab: 'Benchmark', hardware_lab: 'Monitor Hardware',
  kicad_lab: 'PCB Lab', knowledge: 'Argomenti', roadmap: 'Pianificazione & Task',
  network_lab: 'AI Web Browser', sigma_network: 'Sigma Network', domotica: 'Domotica',
  email_client: 'Email Hub', messaging_hub: 'Messaging Hub', youtube_studio: 'YouTube',
};

export const AUDIO_SECTIONS = [
  { id: 'music', name: 'Genera musica', description: 'Componi e ascolta le tue basi musicali', icon: 'Music' },
  { id: 'voice', name: 'Voci e narrazione', description: 'Sintesi vocale, personaggi e racconti', icon: 'Mic' },
  { id: 'editor', name: 'Editor', description: 'Monta, modifica e mixa le tracce', icon: 'SlidersHorizontal' },
  { id: 'radio', name: 'Radio', description: 'Stazioni, ascolto e libreria musicale', icon: 'Radio' },
];

const sub = (id, name) => ({ id, name });
export const CORE_NAVIGATION = [
  { tabType: 'chat', name: 'Chat', description: 'Conversazioni e lavori in corso', icon: 'MessageSquare' },
  { tabType: 'model_hub', name: 'Modelli', icon: 'Cpu', children: [sub('inventory', 'Modelli'), sub('benchmark', 'Benchmark'), sub('training', 'Training')] },
  { tabType: 'multimedia', name: 'Multimedia', description: 'Immagini, video e audio nello stesso spazio', icon: 'Clapperboard' },
  { tabType: 'ai_config', name: 'Providers', icon: 'SlidersHorizontal', children: [sub('engine_server', 'Server locale e proxy'), sub('external_providers', 'Provider esterni')] },
  { tabType: 'marketplace', name: 'Skills', description: 'Capacità, agenti e moduli', icon: 'Sparkles', section: 'capabilities', children: [sub('capabilities', 'Capacità e agenti'), sub('installed', 'Moduli installati'), sub('remote', 'Catalogo moduli')] },
  { tabType: 'whitepapers_lib', name: 'Agenti', icon: 'Users', children: [sub('installed', 'Agenti disponibili'), sub('hub', 'Hub community')] },
  { tabType: 'mcp_hub', name: 'MCP Tools', icon: 'Wrench' },
  { tabType: 'developer_studio', name: 'Developer Sigma', icon: 'Terminal' },
  { tabType: 'account', name: 'Impostazioni', icon: 'Settings' },
  { tabType: 'theme', name: 'Tema', icon: 'Palette' },
];

const icons = { creative_studio: 'Image', video_studio: 'Clapperboard', voice_studio: 'AudioLines',
  music: 'Radio', hardware_lab: 'Activity', kicad_lab: 'CircuitBoard', model_hub: 'Cpu',
  developer_studio: 'Terminal', email_client: 'Mail', messaging_hub: 'Send', youtube_studio: 'MonitorPlay',
  research_lab: 'Workflow', training_lab: 'Brain', benchmark_lab: 'Gauge', knowledge: 'BookOpen',
  roadmap: 'Calendar', domotica: 'House', network_lab: 'Globe', sigma_network: 'Network' };

const descriptions = {
  creative_studio: 'Genera immagini, ritocca le tue creazioni e prepara soggetti e riferimenti visivi.',
  video_studio: 'Crea video e organizza scene, soggetti e sequenze nel tuo progetto.',
  voice_studio: 'Un unico spazio per musica, voci e narrazione, montaggio audio e radio.',
};

export function workspaceEntries(catalog = [], skills = []) {
  const seen = new Set();
  const hasAudio = catalog.some(m => m.available === true && m.tabType === 'voice_studio');
  const entries = catalog.filter(m => m.available === true && m.tabType).flatMap(module => {
    if (module.tabType === 'music' && hasAudio) return [];
    const skill = skills.find(s => s.tab_type === module.tabType);
    if (skill?.enabled === false) return [];
    return [{ id: module.tabType, name: module.name }, ...(module.workspaceTabs || [])].flatMap(tab => {
      if (!tab?.id || seen.has(tab.id)) return [];
      seen.add(tab.id);
      return [{ ...module, id: `${module.id}:${tab.id}`, moduleId: module.id, tabType: tab.id,
        name: WORKSPACE_TITLES[tab.id] || tab.name || module.name,
        description: descriptions[tab.id] || module.description || '', icon: icons[tab.id] || 'Blocks', skill,
        children: tab.id === 'voice_studio' ? AUDIO_SECTIONS : [] }];
    });
  });
  const modelEntry = entries.find(e => e.tabType === 'model_hub');
  const modelChildren = CORE_NAVIGATION.find(e => e.tabType === 'model_hub').children
    .filter(c => c.id === 'inventory' || entries.some(e => e.tabType === `${c.id}_lab`));
  const standalone = entries.filter(e => !['benchmark_lab', 'training_lab'].includes(e.tabType));
  if (modelEntry) modelEntry.children = modelChildren;
  else if (modelChildren.length > 1) standalone.push({ ...CORE_NAVIGATION.find(e => e.tabType === 'model_hub'),
    id: 'model_hub', children: modelChildren.filter(c => c.id !== 'inventory'), workDomain: 'systems' });
  return standalone;
}

export function multimediaEntries(catalog = [], skills = []) {
  const entries = workspaceEntries(catalog, skills).filter(e => ['creative_studio', 'video_studio', 'voice_studio', 'music'].includes(e.tabType));
  return entries.flatMap(entry => [{ ...entry, children: [] }, ...(entry.tabType === 'voice_studio'
    ? AUDIO_SECTIONS.map(section => ({ ...section, tabType: entry.tabType, section: section.id, id: `audio:${section.id}` })) : [])]);
}

export function coreNavigation(catalog = [], skills = []) {
  const entries = workspaceEntries(catalog, skills);
  return CORE_NAVIGATION.filter(entry => !skills.some(s => s.tab_type === entry.tabType && s.enabled === false))
    .map(entry => entry.tabType === 'multimedia' ? { ...entry, children: multimediaEntries(catalog, skills) }
      : entry.tabType === 'model_hub' ? { ...entry, children: entries.find(e => e.tabType === 'model_hub')?.children || [] }
      : entry.tabType === 'account' ? { ...entry, children: settingsEntries(skills) } : entry)
    .filter(entry => !['mcp_hub', 'theme'].includes(entry.tabType));
}

export function settingsEntries(skills = []) {
  return ['account', 'mcp_hub', 'theme'].map(type => CORE_NAVIGATION.find(entry => entry.tabType === type))
    .filter(entry => !skills.some(skill => skill.tab_type === entry.tabType && skill.enabled === false))
    .map(entry => ({ ...entry, id: entry.tabType, name: entry.tabType === 'account' ? 'Profilo e preferenze' : entry.name }));
}

export function selectModelSection(section) {
  const area = ['benchmark', 'training'].includes(section) ? section : 'models';
  try { window.sessionStorage.setItem('sigma_model_workspace_section', area); } catch { /* Sezione disponibile anche senza storage. */ }
  window.dispatchEvent(new CustomEvent('sigma-model-workspace-section', { detail: area }));
}

const sections = {
  voice_studio: ['sigmaAudioStudioSection', 'sigma_audio_studio_section'],
  model_hub: ['sigma_model_hub_active_subtab', 'sigma-model-hub-set-tab'],
  ai_config: ['sigma_providers_active_subtab', 'sigma-providers-set-tab'],
  marketplace: ['sigma_marketplace_active_subtab', 'sigma-marketplace-set-tab'],
  whitepapers_lib: ['sigma_manifesti_active_subtab', 'sigma-manifesti-set-tab'],
};

export function navigateStudio(entry, openTab, section = entry?.section) {
  if (!entry || typeof openTab !== 'function') return;
  const child = entry.children?.find(c => c.id === section);
  if (child?.tabType) return navigateStudio(child, openTab);
  if (entry.tabType === 'model_hub' && section) selectModelSection(section);
  const channel = sections[entry.tabType];
  const innerSection = entry.tabType === 'model_hub' && ['benchmark', 'training'].includes(section) ? null : section;
  if (channel && innerSection) {
    const storage = entry.tabType === 'voice_studio' ? window.sessionStorage : window.localStorage;
    try { storage.setItem(channel[0], innerSection); } catch { /* La navigazione resta disponibile senza storage. */ }
  }
  if (entry.tabType === 'marketplace' && section === 'capabilities') {
    const domain = entry.domain || 'all';
    try { window.sessionStorage.setItem('sigma_skills_domain', domain); } catch { /* Filtro solo in memoria. */ }
    window.dispatchEvent(new CustomEvent('sigma-skills-domain', { detail: domain }));
  }
  openTab({ name: WORKSPACE_TITLES[entry.tabType] || entry.name }, entry.tabType);
  if (channel && innerSection) window.dispatchEvent(new CustomEvent(channel[1], { detail: innerSection }));
}
