// ==============================================================================
// index.js — Entrypoint for isolated Sigma Audio Studio & FM Radio Module
// ==============================================================================

export { default as AudioStudioTab } from './AudioStudioTab';
export { default as AudioFloatingWidget } from './AudioFloatingWidget';
export { AudioProvider, useAudio } from './AudioContext';
export * from './services/musicRecommendation';

export const MODULE_META = {
  id: 'audio_studio',
  name: 'Hi-Fi Sound & FM Radio Studio',
  version: '1.0.0',
  category: 'Audio & Streaming',
  icon: 'Radio',
  color: '#00f2fe',
  tabType: 'music'
};
