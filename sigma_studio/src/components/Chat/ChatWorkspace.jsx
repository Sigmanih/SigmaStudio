// ==============================================================================
// ChatWorkspace.jsx — Wrapper backwards-compat per ChatWorkspaceTab
// Sigma Studio v7 — Tutta la logica in useChatCore + layout in layouts/
// NOTA: Questo file è un wrapper. Le modifiche vanno in:
//   - core/useChatCore.js (logica)
//   - layouts/ChatWorkspaceTab.jsx (layout workspace)
//   - ui/ (componenti UI)
// ==============================================================================
import ChatWorkspaceTab from './layouts/ChatWorkspaceTab';

export default function ChatWorkspace() {
  return <ChatWorkspaceTab />;
}