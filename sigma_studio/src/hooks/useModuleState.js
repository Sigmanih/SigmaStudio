/**
 * useModuleState — Centralised hook for optional module install state.
 *
 * Single source of truth: fetches from /api/marketplace/modules on mount,
 * then keeps in sync via the 'sigma_modules_updated' custom event.
 *
 * Optional modules default to FALSE until the backend confirms otherwise.
 * Kernel modules (creative_studio, research_lab, etc.) always stay TRUE.
 */

import { useState, useEffect, useCallback } from 'react';

// Optional modules — these can be installed / uninstalled by the user.
// All modules default to FALSE until the backend confirms otherwise.
const OPTIONAL_MODULE_IDS = [
  // Media & Generazione
  'sigma_creative_lab',  // Creative Lab 3D/2D
  'audio_studio',        // Hi-Fi Sound & FM Radio Studio
  'sigma_voice_studio',  // Voice Studio & Neural Speech Lab
  // Sviluppo & Sandbox
  'sigma_developer_lab', // Developer Lab & Docker Sandbox
  // Infrastruttura Lab
  'sigma_training_lab',  // Training Lab & SLM Forge
  'sigma_hardware_lab',  // Hardware Lab & VRAM
  'sigma_research_lab',  // Pipelines Lab & Dynamic Swarm
  // Knowledge & Pianificazione
  'sigma_knowledge',     // Knowledge Explorer
  'sigma_roadmap',       // Pianificazione & Task Audit
  'sigma_mcp_hub',       // MCP Tools Hub
  // IoT
  'sigma_domotica',      // Domotica & Home Assistant IoT
  // Rete & Comunicazione
  'sigma_network_lab',   // Network Explorer & Web Research
  'sigma_email_client',  // Email Hub & Client
  'sigma_messaging_hub', // Messaging & Notification Hub
];

// Kernel modules — always present and active natively in Sigma Studio core.
const KERNEL_MODULE_IDS = ['sigma_model_hub'];


/**
 * Returns the current install state for all optional modules.
 *
 * @returns {{ modulesState: Record<string, boolean>, isLoaded: boolean, refetch: () => void }}
 *
 * Usage:
 *   const { modulesState, isLoaded } = useModuleState();
 *   const isAudioInstalled = modulesState.audio_studio === true;
 */
export function useModuleState() {
  const [modulesState, setModulesState] = useState(() => {
    // Initialise: optional modules default false, kernel always true.
    const state = {};
    KERNEL_MODULE_IDS.forEach(id => { state[id] = true; });
    OPTIONAL_MODULE_IDS.forEach(id => { state[id] = false; });

    // Override only optional modules from localStorage (not kernel).
    try {
      const saved = localStorage.getItem('sigma_modules_state');
      if (saved) {
        const parsed = JSON.parse(saved);
        OPTIONAL_MODULE_IDS.forEach(id => {
          if (parsed[id] !== undefined) state[id] = parsed[id] === true;
        });
      }
    } catch (e) {}

    return state;
  });

  const [isLoaded, setIsLoaded] = useState(false);

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch('/api/marketplace/modules');
      if (res.ok) {
        const data = await res.json();
        if (data.modules_state) {
          setModulesState(prev => {
            const next = { ...prev };
            // Only override optional module states from backend
            OPTIONAL_MODULE_IDS.forEach(id => {
              next[id] = data.modules_state[id] === true;
            });
            // Persist to localStorage
            try {
              const existing = JSON.parse(localStorage.getItem('sigma_modules_state') || '{}');
              OPTIONAL_MODULE_IDS.forEach(id => { existing[id] = next[id]; });
              localStorage.setItem('sigma_modules_state', JSON.stringify(existing));
            } catch (e) {}
            return next;
          });
        }
      }
    } catch (e) {
      console.warn('[useModuleState] Backend fetch failed, using localStorage fallback:', e);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    // Fetch backend state on mount
    fetchState();

    // Listen for install/uninstall events
    const handleUpdate = (e) => {
      const { moduleId, installed } = e.detail || {};
      if (!moduleId) return;
      setModulesState(prev => ({ ...prev, [moduleId]: installed === true }));
      // Sync localStorage
      try {
        const existing = JSON.parse(localStorage.getItem('sigma_modules_state') || '{}');
        existing[moduleId] = installed === true;
        localStorage.setItem('sigma_modules_state', JSON.stringify(existing));
      } catch (e) {}
    };

    window.addEventListener('sigma_modules_updated', handleUpdate);
    return () => window.removeEventListener('sigma_modules_updated', handleUpdate);
  }, [fetchState]);

  return { modulesState, isLoaded, refetch: fetchState };
}

export { OPTIONAL_MODULE_IDS, KERNEL_MODULE_IDS };
