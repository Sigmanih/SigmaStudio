// ==============================================================================
// audioSpeech.js — High Efficiency TTS (Text-to-Speech) & STT (Speech-to-Text)
// Italian Language Support, Markdown Cleanup & Web Speech API Integration
// ==============================================================================

/**
 * Clean markdown symbols, code blocks, HTML, and URLs for natural speech synthesis.
 */
export function cleanTextForSpeech(text) {
  if (!text) return '';
  return text
    .replace(/```[\s\S]*?```/g, '')        // remove multiline code blocks
    .replace(/`[^`]*`/g, '')               // remove inline code
    .replace(/<[^>]*>/g, '')               // remove HTML tags
    .replace(/#+\s+/g, '')                 // remove headers
    .replace(/\!\[.*?\]\(.*?\)/g, '')      // remove images
    .replace(/\[.*?\]\(.*?\)/g, '')        // remove markdown links
    .replace(/[*_~`#\[\]\(\)>|]/g, '')     // remove formatting symbols
    .replace(/https?:\/\/\S+/g, '')        // remove raw URLs
    .replace(/\n+/g, '. ')                 // replace newlines with period pauses
    .replace(/\s+/g, ' ')                  // collapse multiple spaces
    .trim();
}

let activeUtterance = null;
let cachedVoices = [];

function updateVoicesCache() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    const v = window.speechSynthesis.getVoices();
    if (v && v.length > 0) {
      cachedVoices = v;
    }
  }
}

if (typeof window !== 'undefined' && window.speechSynthesis) {
  updateVoicesCache();
  try {
    window.speechSynthesis.addEventListener('voiceschanged', updateVoicesCache);
  } catch (e) {
    window.speechSynthesis.onvoiceschanged = updateVoicesCache;
  }
}

/**
 * Get available system voices with pre-cached fallback.
 */
export function getAvailableVoices() {
  updateVoicesCache();
  return cachedVoices.length > 0 ? cachedVoices : (typeof window !== 'undefined' && window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
}

/**
 * Speak text using browser SpeechSynthesis (TTS).
 */
export function speakAgentMessage(text, onStart = null, onEnd = null) {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    console.warn('SpeechSynthesis is not supported in this browser.');
    if (onEnd) onEnd();
    return false;
  }

  stopSpeech();

  const cleanText = cleanTextForSpeech(text);
  if (!cleanText) {
    if (onEnd) onEnd();
    return false;
  }

  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.lang = 'it-IT';
  utterance.rate = 1.05;
  utterance.pitch = 1.0;

  const voices = getAvailableVoices();

  // Load custom voice config from localStorage if available
  try {
    const savedConfig = localStorage.getItem('sigma_assistant_voice_config') || localStorage.getItem('sigma_tts_voice');
    if (savedConfig) {
      const cfg = typeof savedConfig === 'string' && savedConfig.startsWith('{') ? JSON.parse(savedConfig) : { voiceURI: savedConfig };
      if (cfg.rate) utterance.rate = parseFloat(cfg.rate);
      if (cfg.pitch) utterance.pitch = parseFloat(cfg.pitch);
      if (cfg.voiceURI) {
        const selected = voices.find(v => v.voiceURI === cfg.voiceURI || v.name === cfg.voiceURI);
        if (selected) utterance.voice = selected;
      }
    }
    if (!utterance.voice && voices.length > 0) {
      const itVoice = voices.find(v => v.lang.startsWith('it') || v.lang.includes('IT'));
      if (itVoice) utterance.voice = itVoice;
    }
  } catch (e) {
    if (voices.length > 0) {
      const itVoice = voices.find(v => v.lang.startsWith('it') || v.lang.includes('IT'));
      if (itVoice) utterance.voice = itVoice;
    }
  }

  utterance.onstart = () => {
    activeUtterance = utterance;
    if (onStart) onStart();
  };

  utterance.onend = () => {
    activeUtterance = null;
    if (onEnd) onEnd();
  };

  utterance.onerror = (err) => {
    // Interruption/cancellation when user stops speech is expected browser event
    if (err && (err.error === 'interrupted' || err.error === 'canceled')) {
      activeUtterance = null;
      if (onEnd) onEnd();
      return;
    }
    console.error('SpeechSynthesis error:', err);
    activeUtterance = null;
    if (onEnd) onEnd();
  };

  window.speechSynthesis.speak(utterance);
  return true;
}

/**
 * Stop active speech synthesis.
 */
export function stopSpeech() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    activeUtterance = null;
  }
}

/**
 * Check if TTS speech is currently playing.
 */
export function isSpeaking() {
  return typeof window !== 'undefined' && window.speechSynthesis ? window.speechSynthesis.speaking : false;
}

/**
 * Initialize Web Speech API Speech Recognition for Voice Commands (STT).
 */
export function initSpeechRecognition({ onResult, onError, onEnd, lang = 'it-IT' }) {
  if (typeof window === 'undefined') return null;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn('SpeechRecognition is not supported in this browser.');
    return null;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = lang;

  recognition.onresult = (event) => {
    let accumulatedText = '';
    for (let i = 0; i < event.results.length; ++i) {
      accumulatedText += event.results[i][0].transcript;
    }

    if (onResult) {
      onResult(accumulatedText);
    }
  };

  if (onError) recognition.onerror = onError;
  if (onEnd) recognition.onend = onEnd;

  return recognition;
}
