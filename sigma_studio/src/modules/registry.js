// ==============================================================================
// sigma_studio/src/modules/registry.js — Dynamic Module Registry (Vite Glob)
// Usa import.meta.glob per scoprire a build-time solo i moduli FISICAMENTE presenti
// nella cartella src/modules/. Se un modulo non è installato, non viene incluso nel bundle
// e getLazyModule() ritorna null, attivando la schermata ModuleNotInstalled.
// ==============================================================================
import React from 'react';

// Scansiona dinamicamente tutti i moduli installati nella directory (.jsx e .js)
const installedModules = import.meta.glob([
  './*/index.jsx',
  './*/index.js',
  './*/DomoticaTab.jsx'
]);

// Scansiona dinamicamente tutti i Floating Panel opzionali presenti nella directory
const installedFloatingPanels = import.meta.glob([
  './*/HardwareFloatingPanel.jsx',
  './*/HardwareFloatingPanel.js'
]);

// Mappatura tabType → nome cartella modulo
const TAB_TO_FOLDER = {
  sigma_network: 'sigma_network',
  // Multimodale & Grafica
  creative_studio: 'sigma_creative_lab',

  // Audio & Streaming
  music:           'sigma_audio_studio',
  music_lounge:    'sigma_audio_studio',
  audio_studio:    'sigma_audio_studio',
  voice_studio:    'sigma_voice_studio',

  // Lab & Infrastruttura
  training_lab:    'sigma_training_lab',
  hardware_lab:    'sigma_hardware_lab',
  hardware:        'sigma_hardware_lab',
  model_hub:       'sigma_model_hub',
  research_lab:    'sigma_research_lab',
  developer_lab:   'sigma_developer_lab',
  network_lab:     'sigma_network_lab',

  // Knowledge & MCP
  knowledge:       'sigma_knowledge',
  mcp_hub:         'sigma_mcp_hub',
  roadmap:         'sigma_roadmap',

  // Messaging & Email
  email_client:    'sigma_email_client',
  messaging_hub:   'sigma_messaging_hub',

  // IoT & Domotica
  domotica:        'sigma_domotica',
  home_assistant:  'sigma_domotica',
};

function findModuleImport(tabType) {
  const folder = TAB_TO_FOLDER[tabType] || tabType;
  const candidates = [
    `./${folder}/index.jsx`,
    `./${folder}/index.js`,
    `./${folder}/DomoticaTab.jsx`,
  ];
  for (const c of candidates) {
    if (installedModules[c]) return installedModules[c];
  }
  return null;
}

const _componentCache = {};

/**
 * Restituisce un componente React.lazy() per il tabType specificato SE il modulo è installato su disco.
 * Altrimenti ritorna null.
 *
 * @param {string} tabType
 * @returns {React.LazyExoticComponent | null}
 */
export function getLazyModule(tabType) {
  const importFn = findModuleImport(tabType);
  if (!importFn) {
    return null;
  }

  if (!_componentCache[tabType]) {
    _componentCache[tabType] = React.lazy(importFn);
  }
  return _componentCache[tabType];
}

/**
 * Restituisce il componente React.lazy() per l'Hardware Floating Panel se il modulo sigma_hardware_lab è installato.
 * Altrimenti ritorna null.
 *
 * @returns {React.LazyExoticComponent | null}
 */
export function getLazyHardwareFloating() {
  const candidates = [
    './sigma_hardware_lab/HardwareFloatingPanel.jsx',
    './sigma_hardware_lab/HardwareFloatingPanel.js'
  ];
  let importFn = null;
  for (const c of candidates) {
    if (installedFloatingPanels[c]) {
      importFn = installedFloatingPanels[c];
      break;
    }
  }
  if (!importFn) {
    return null;
  }
  if (!_componentCache['hardware_floating']) {
    _componentCache['hardware_floating'] = React.lazy(importFn);
  }
  return _componentCache['hardware_floating'];
}

/**
 * Verifica se il modulo è presente su disco e compilato.
 *
 * @param {string} tabType
 * @returns {boolean}
 */
export function isModuleRegistered(tabType) {
  return Boolean(findModuleImport(tabType));
}
