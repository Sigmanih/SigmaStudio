import { useState, useEffect, useCallback } from 'react';

/**
 * useChatDevMode — Gestisce la disponibilità e lo stato di "Dev Mode" per la Chat principale.
 *
 * Se il modulo sigma_developer_lab è presente e attivo sul server (/api/developer/status),
 * l'utente può attivare la modalità "🛠️ Dev Mode" con una checkbox per indirizzare
 * le richieste verso l'harness di sviluppo con pieno accesso al filesystem,
 * esecuzione di test e tool MCP avanzati.
 */
export function useChatDevMode() {
  const [devModeAvailable, setDevModeAvailable] = useState(false);
  const [workspaceRoot, setWorkspaceRoot] = useState('');
  const [devModeEnabled, setDevModeEnabledState] = useState(() => {
    try {
      return localStorage.getItem('sigma_chat_dev_mode_enabled') === 'true';
    } catch (e) {
      return false;
    }
  });

  const checkAvailability = useCallback(async () => {
    try {
      const res = await fetch('/api/developer/status');
      if (res.ok) {
        const data = await res.json();
        if (data.available) {
          setDevModeAvailable(true);
          setWorkspaceRoot(data.workspace_root || '');
          return;
        }
      }
      setDevModeAvailable(false);
    } catch (err) {
      // Modulo developer non presente o non installato
      setDevModeAvailable(false);
    }
  }, []);

  useEffect(() => {
    checkAvailability();
  }, [checkAvailability]);

  // Riallinea se cambia finestra o focus
  useEffect(() => {
    const onFocus = () => checkAvailability();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [checkAvailability]);

  const setDevModeEnabled = useCallback((enabled) => {
    setDevModeEnabledState(enabled);
    try {
      localStorage.setItem('sigma_chat_dev_mode_enabled', String(enabled));
    } catch (e) {}
  }, []);

  return {
    devModeAvailable,
    devModeEnabled: devModeAvailable && devModeEnabled,
    setDevModeEnabled,
    workspaceRoot,
    refreshAvailability: checkAvailability
  };
}
