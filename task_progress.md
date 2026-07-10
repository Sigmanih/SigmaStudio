# Task Progress — Chat UI Revolution

## Phase 1: Model Selector Default Label
- [x] Analyze current ModelSelector and ChatHeader code
- [ ] Modify ModelSelector to show "Scegli modello" when no model selected
- [ ] Modify ChatHeader to show placeholder when no manifesto selected

## Phase 2: Professional Markdown + KaTeX in Chat Messages
- [x] Analyze AgentMessage.jsx (current plain text rendering)
- [x] Analyze MessageBubble.jsx (proper markdown+KaTeX rendering)
- [ ] Port renderMarkdown + renderMathInElement functions into AgentMessage.jsx
- [ ] Replace plain text `<div className="chat-content">` with dangerouslySetInnerHTML markdown rendering
- [ ] Add KaTeX re-rendering via useEffect after DOM updates

## Phase 3: Premium Chat CSS — Better Than ChatGPT/Claude
- [x] Analyze existing chat.css styles
- [ ] Add typography improvements (better font sizes, line heights, colors)
- [ ] Add gradient backgrounds, subtle shadows, and animations
- [ ] Improve code blocks with syntax theme
- [ ] Improve KaTeX display (larger, centered with glow)
- [ ] Add smooth transitions for thinking sections
- [ ] Improve message bubbles with better spacing and visual hierarchy
- [ ] Add scrollbar styling and smoother animations

## Phase 4: Manifesto Adaptations for Model Selection
- [ ] Update manifesto panels to reflect rich markdown rendering
- [ ] Ensure backend model selections respect the visual improvements

## Phase 5: Testing
- [ ] Verify "Scegli modello" appears correctly
- [ ] Verify markdown renders in chat messages
- [ ] Verify KaTeX renders mathematical expressions
- [ ] Verify all CSS improvements look correct