import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Auto-recovery for stale dynamic chunk preloads when frontend is updated
window.addEventListener('vite:preloadError', (event) => {
  console.warn('[SigmaStudio] Nuova versione dell\'applicazione rilevata, ricaricamento...', event);
  window.location.reload();
});

window.addEventListener('error', (e) => {
  if (e?.message && (e.message.includes('Unable to preload CSS') || e.message.includes('Failed to fetch dynamically imported module'))) {
    console.warn('[SigmaStudio] Asset cache obsoleto, ricaricamento pagina...', e);
    window.location.reload();
  }
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
