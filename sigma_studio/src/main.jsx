import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Auto-recovery for stale dynamic chunk preloads when frontend is updated
window.addEventListener('vite:preloadError', (event) => {
  console.warn('[SigmaStudio] Nuova versione dell\'applicazione rilevata:', event);
  const lastReload = sessionStorage.getItem('sigma_last_preload_reload');
  const now = Date.now();
  if (!lastReload || (now - Number(lastReload)) > 10000) {
    sessionStorage.setItem('sigma_last_preload_reload', String(now));
    window.location.reload();
  }
});

window.addEventListener('error', (e) => {
  if (e?.message && (e.message.includes('Unable to preload CSS') || e.message.includes('Failed to fetch dynamically imported module'))) {
    console.warn('[SigmaStudio] Asset cache warning:', e);
    const lastReload = sessionStorage.getItem('sigma_last_preload_reload');
    const now = Date.now();
    if (!lastReload || (now - Number(lastReload)) > 10000) {
      sessionStorage.setItem('sigma_last_preload_reload', String(now));
      window.location.reload();
    }
  }
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
