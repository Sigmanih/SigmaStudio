// ==============================================================================
// ChatPanel.jsx — Wrapper backwards-compat per ChatFloatingPanel
// Sigma Studio v7 — Tutta la logica in useChatCore + layout in layouts/
// NOTA: Questo file è un wrapper. Le modifiche vanno in:
//   - core/useChatCore.js (logica)
//   - layouts/ChatFloatingPanel.jsx (layout pannello)
//   - ui/ (componenti UI)
// ==============================================================================
import ChatFloatingPanel from './layouts/ChatFloatingPanel';

export default function ChatPanel(props) {
  return <ChatFloatingPanel {...props} />;
}