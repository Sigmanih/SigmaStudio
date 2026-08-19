// ==============================================================================
// sigma_studio/src/modules/registry.js — Dynamic Module Registry (Vite Glob)
// Usa import.meta.glob per scoprire a build-time solo i moduli FISICAMENTE presenti
// nella cartella src/modules/. Se un modulo non è installato, non viene incluso nel bundle
// e getLazyModule() ritorna null, attivando la schermata ModuleNotInstalled.
// ==============================================================================
import React from 'react';

// Scansiona dinamicamente tutti i moduli installati nella directory
const installedModules = import.meta.glob('./*/index.jsx');

// Scansiona dinamicamente tutti i Floating Panel opzionali presenti nella directory
const installedFloatingPanels = import.meta.glob('./*/HardwareFloatingPanel.jsx');

// Mappatura tabType → path del modulo
const TAB_TO_MODULE_PATH = {
  // Multimodale & Grafica
  creative_studio: './sigma_creative_lab/index.jsx',

  // Audio & Streaming
  music:           './sigma_audio_studio/index.jsx',
  music_lounge:    './sigma_audio_studio/index.jsx',
  audio_studio:    './sigma_audio_studio/index.jsx',
  voice_studio:    './sigma_voice_studio/index.jsx',

  // Lab & Infrastruttura
  training_lab:    './sigma_training_lab/index.jsx',
  hardware_lab:    './sigma_hardware_lab/index.jsx',
  hardware:        './sigma_hardware_lab/index.jsx',
  model_hub:       './sigma_model_hub/index.jsx',
  research_lab:    './sigma_research_lab/index.jsx',
  developer_lab:   './sigma_developer_lab/index.jsx',
  network_lab:     './sigma_network_lab/index.jsx',


  // Knowledge & MCP
  knowledge:       './sigma_knowledge/index.jsx',
  mcp_hub:         './sigma_mcp_hub/index.jsx',
  roadmap:         './sigma_roadmap/index.jsx',

  // Messaging & Email
  email_client:    './sigma_email_client/index.jsx',
  messaging_hub:   './sigma_messaging_hub/index.jsx',

  // IoT & Domotica
  domotica:        './sigma_domotica/index.jsx',
  home_assistant:  './sigma_domotica/index.jsx',
};


const _componentCache = {};

/**
 * Restituisce un componente React.lazy() per il tabType specificato SE il modulo è installato su disco.
 * Altrimenti ritorna null.
 *
 * @param {string} tabType
 * @returns {React.LazyExoticComponent | null}
 */
export function getLazyModule(tabType) {
  const path = TAB_TO_MODULE_PATH[tabType];
  if (!path || !installedModules[path]) {
    return null;
  }

  if (!_componentCache[tabType]) {
    _componentCache[tabType] = React.lazy(installedModules[path]);
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
  const path = './sigma_hardware_lab/HardwareFloatingPanel.jsx';
  if (!installedFloatingPanels[path]) {
    return null;
  }
  if (!_componentCache['hardware_floating']) {
    _componentCache['hardware_floating'] = React.lazy(installedFloatingPanels[path]);
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
  const path = TAB_TO_MODULE_PATH[tabType];
  return Boolean(path && installedModules[path]);
}
