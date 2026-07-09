// ==============================================================================
// Chat components index — Esporta tutti i componenti pubblici
// Sigma Studio v7 — Organizzato in core/ (logica), ui/ (componenti), layouts/ (pagine)
// ==============================================================================

// Layouts (pagine complete)
export { default as ChatPanel } from './ChatPanel';
export { default as ChatFloatingPanel } from './layouts/ChatFloatingPanel';
export { default as ChatWorkspaceTab } from './layouts/ChatWorkspaceTab';

// Core hook (logica)
export { default as useChatCore } from './core/useChatCore';

// UI Components
export { default as ChatHeader } from './ui/ChatHeader';
export { default as ChatInput } from './ui/ChatInput';
export { default as ChatMessages } from './ui/ChatMessages';

// Legacy components (still used)
export { default as ChatHistory } from './ChatHistory';
export { default as MessageBubble } from './MessageBubble';
export { default as ModelSelector } from './ModelSelector';
export { default as FilePicker } from './FilePicker';
export { default as ActionsBar } from './ActionsBar';