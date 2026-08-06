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

// --- Global speech state -----------------------------------------------------
// Any component can ask "is this message being read right now?". Without it the
// auto-play started by the chat stream is invisible to the per-message button,
// which then needs two clicks to stop: one to restart, one to cancel.
let activeSpeechId = null;
const speechListeners = new Set();

function setActiveSpeechId(id) {
  if (activeSpeechId === id) return;
  activeSpeechId = id;
  speechListeners.forEach(fn => { try { fn(activeSpeechId); } catch (e) {} });
}

/** Subscribe to speech state changes. Returns an unsubscribe function. */
export function subscribeSpeech(listener) {
  speechListeners.add(listener);
  return () => speechListeners.delete(listener);
}

/** Id of the message currently being read, or null. */
export function getActiveSpeechId() {
  return activeSpeechId;
}

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
 * Build a configured utterance (voice, rate and pitch from user settings).
 */
function buildUtterance(cleanText) {
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

  return utterance;
}

/**
 * Speak text using browser SpeechSynthesis (TTS).
 * `speechId` identifies the message being read so the UI can reflect its state.
 */
export function speakAgentMessage(text, onStart = null, onEnd = null, speechId = null) {
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

  const utterance = buildUtterance(cleanText);
  const id = speechId || `speech-${Date.now()}`;

  utterance.onstart = () => {
    activeUtterance = utterance;
    setActiveSpeechId(id);
    if (onStart) onStart();
  };

  const finish = () => {
    activeUtterance = null;
    setActiveSpeechId(null);
    if (onEnd) onEnd();
  };

  utterance.onend = finish;

  utterance.onerror = (err) => {
    // Interruption/cancellation when user stops speech is expected browser event
    if (!err || (err.error !== 'interrupted' && err.error !== 'canceled')) {
      console.error('SpeechSynthesis error:', err);
    }
    finish();
  };

  window.speechSynthesis.speak(utterance);
  return true;
}

// --- Incremental reading -----------------------------------------------------
// Reading only once generation is over means waiting minutes for a long answer.
// These helpers speak each sentence as soon as it is complete, keeping the
// synthesiser one step behind the text instead of one answer behind it.

let speechStream = null;

const SENTENCE_ENDINGS = '.!?…\n';
const MAX_UNPUNCTUATED = 260;
const HAS_LETTERS = /[a-zA-ZÀ-ÿ]/;

/** Strip fenced code blocks across chunk boundaries — nobody wants code read out. */
function stripFencedCode(state, text) {
  let out = '';
  let rest = text;
  while (rest.length) {
    const idx = rest.indexOf('```');
    if (idx === -1) {
      if (!state.inCode) out += rest;
      break;
    }
    if (!state.inCode) out += rest.slice(0, idx);
    rest = rest.slice(idx + 3);
    state.inCode = !state.inCode;
  }
  return out;
}

function enqueueSpeech(state, rawText) {
  const clean = cleanTextForSpeech(stripFencedCode(state, rawText));
  if (!clean) return;

  const utterance = buildUtterance(clean);
  state.pending += 1;

  const settle = () => {
    if (speechStream !== state) return;
    state.pending = Math.max(0, state.pending - 1);
    if (state.ended && state.pending === 0) {
      speechStream = null;
      setActiveSpeechId(null);
    }
  };
  utterance.onend = settle;
  utterance.onerror = settle;

  window.speechSynthesis.speak(utterance);
}

function drainSpeechStream(force) {
  const state = speechStream;
  if (!state) return;

  while (state.buffer) {
    let cut = -1;
    for (let i = state.buffer.length - 1; i >= 0; i--) {
      if (SENTENCE_ENDINGS.includes(state.buffer[i])) { cut = i; break; }
    }
    if (cut === -1) {
      // No sentence boundary yet: wait for more text, unless the answer is over
      // or the model is writing an unusually long unpunctuated run.
      if (force) cut = state.buffer.length - 1;
      else if (state.buffer.length > MAX_UNPUNCTUATED) {
        const space = state.buffer.lastIndexOf(' ');
        if (space <= 0) return;
        cut = space;
      } else return;
    }
    const chunk = state.buffer.slice(0, cut + 1);
    // A list marker ("1.") ends in a boundary but is not a sentence: speaking it
    // on its own turns an enumeration into a stutter. Wait for the actual text.
    if (!force && !HAS_LETTERS.test(chunk)) return;

    state.buffer = state.buffer.slice(cut + 1);
    enqueueSpeech(state, chunk);
    if (!force && !state.buffer) return;
  }
}

/** Begin reading a message that is still being generated. */
export function startSpeechStream(speechId) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return false;
  stopSpeech();
  speechStream = { id: speechId, buffer: '', pending: 0, ended: false, inCode: false };
  setActiveSpeechId(speechId);
  return true;
}

/** Feed the next slice of answer text (answer only — never the reasoning). */
export function pushSpeechStream(delta) {
  if (!speechStream || !delta) return;
  speechStream.buffer += delta;
  drainSpeechStream(false);
}

/** No more text is coming: speak the tail and release the state when done. */
export function endSpeechStream() {
  const state = speechStream;
  if (!state) return;
  drainSpeechStream(true);
  state.ended = true;
  if (state.pending === 0) {
    speechStream = null;
    setActiveSpeechId(null);
  }
}

/**
 * Stop active speech synthesis.
 */
export function stopSpeech() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    activeUtterance = null;
    speechStream = null;
    setActiveSpeechId(null);
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
