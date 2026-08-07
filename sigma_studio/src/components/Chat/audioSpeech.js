// ==============================================================================
// audioSpeech.js — High Efficiency TTS (Text-to-Speech) & STT (Speech-to-Text)
// Italian Language Support, Markdown Cleanup & Web Speech API Integration
// ==============================================================================

// --- Text normalisation for speech ------------------------------------------
// Three rules drive this section:
//   · emphasis is markup, but the word it wraps is still a word — read it;
//   · emoji and decorative runs (----, ====) are layout, never speech;
//   · mathematics is content: it gets spoken out in Italian, not stripped.

/** LaTeX commands → spoken Italian. Order matters: specific before generic. */
const LATEX_RULES = [
  [/\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, ' $1 fratto $2 '],
  [/\\sqrt\s*\[\s*3\s*\]\s*\{([^{}]*)\}/g, ' radice cubica di $1 '],
  [/\\sqrt\s*\{([^{}]*)\}/g, ' radice quadrata di $1 '],
  [/\\(?:times|cdot|ast)\b/g, ' per '],
  [/\\div\b/g, ' diviso '],
  [/\\pm\b/g, ' più o meno '],
  [/\\(?:leq|le)\b/g, ' minore o uguale a '],
  [/\\(?:geq|ge)\b/g, ' maggiore o uguale a '],
  [/\\(?:neq|ne)\b/g, ' diverso da '],
  [/\\(?:approx|sim)\b/g, ' circa uguale a '],
  [/\\equiv\b/g, ' equivalente a '],
  [/\\infty\b/g, ' infinito '],
  [/\\sum\b/g, ' sommatoria '],
  [/\\prod\b/g, ' produttoria '],
  [/\\int\b/g, ' integrale '],
  [/\\lim\b/g, ' limite '],
  [/\\log\b/g, ' logaritmo '],
  [/\\ln\b/g, ' logaritmo naturale '],
  [/\\(?:rightarrow|to|implies|Rightarrow)\b/g, ' implica '],
  [/\\in\b/g, ' appartiene a '],
  [/\\forall\b/g, ' per ogni '],
  [/\\exists\b/g, ' esiste '],
  [/\\(?:cdots|ldots|dots)\b/g, ' e così via '],
  [/\\pi\b/g, ' pi greco '],
  [/\\alpha\b/g, ' alfa '], [/\\beta\b/g, ' beta '], [/\\gamma\b/g, ' gamma '],
  [/\\delta\b/g, ' delta '], [/\\theta\b/g, ' theta '], [/\\lambda\b/g, ' lambda '],
  [/\\mu\b/g, ' mu '], [/\\sigma\b/g, ' sigma '], [/\\omega\b/g, ' omega '],
  [/\\phi\b/g, ' fi '], [/\\epsilon\b/g, ' epsilon '],
  [/\\(?:left|right|quad|qquad|,|;|!)/g, ' '],
  [/\\text\s*\{([^{}]*)\}/g, ' $1 '],
  [/\\[a-zA-Z]+/g, ' '],            // any command we do not translate
  [/\^\s*\{?\s*2\s*\}?(?![\w])/g, ' al quadrato '],
  [/\^\s*\{?\s*3\s*\}?(?![\w])/g, ' al cubo '],
  [/\^\s*\{([^{}]*)\}/g, ' alla $1 '],
  [/\^\s*(-?\w)/g, ' alla $1 '],
  [/_\s*\{([^{}]*)\}/g, ' con indice $1 '],
  [/_\s*(\w)/g, ' con indice $1 '],
  [/[{}\\]/g, ' '],
];

/** Math symbols that show up in plain prose, outside any LaTeX delimiter. */
const MATH_SYMBOL_RULES = [
  [/×/g, ' per '], [/÷/g, ' diviso '], [/±/g, ' più o meno '],
  [/≤/g, ' minore o uguale a '], [/≥/g, ' maggiore o uguale a '],
  [/≠/g, ' diverso da '], [/≈/g, ' circa uguale a '], [/≡/g, ' equivalente a '],
  [/√/g, ' radice di '], [/π/g, ' pi greco '], [/∞/g, ' infinito '],
  [/∑/g, ' sommatoria '], [/∏/g, ' produttoria '], [/∫/g, ' integrale '],
  [/∈/g, ' appartiene a '], [/∀/g, ' per ogni '], [/∃/g, ' esiste '],
  [/[→⇒]/g, ' implica '],
  [/²/g, ' al quadrato '], [/³/g, ' al cubo '],
  [/−/g, ' meno '],
  [/=/g, ' uguale a '],
  [/%/g, ' percento '],
  // Ambiguous in prose: only spoken when they sit between numbers.
  [/(\d)\s*\+\s*(\d)/g, '$1 più $2'],
  [/(\d)\s*-\s*(\d)/g, '$1 meno $2'],
  [/(\d)\s*\*\s*(\d)/g, '$1 per $2'],
  [/(\d)\s*\/\s*(\d)/g, '$1 diviso $2'],
  [/(\w)\s*\^\s*(\d)/g, '$1 alla $2'],
];

function applyRules(text, rules) {
  return rules.reduce((acc, [pattern, replacement]) => acc.replace(pattern, replacement), text);
}

/** Turn a LaTeX expression into something a synthesiser can pronounce. */
export function mathToSpeech(expression) {
  return applyRules(expression, LATEX_RULES).replace(/\s+/g, ' ').trim();
}

/**
 * Clean markdown, emoji and layout noise for natural speech synthesis,
 * keeping every actual word — emphasis included — and speaking the maths.
 */
export function cleanTextForSpeech(text) {
  if (!text) return '';
  let out = text;

  // Code blocks are never read aloud.
  out = out.replace(/```[\s\S]*?```/g, ' ');
  out = out.replace(/<[^>]*>/g, ' ');

  // Maths first: the markdown pass below would otherwise shred it.
  out = out.replace(/\$\$([\s\S]+?)\$\$/g, (_, e) => ` ${mathToSpeech(e)} `);
  out = out.replace(/\\\[([\s\S]+?)\\\]/g, (_, e) => ` ${mathToSpeech(e)} `);
  out = out.replace(/\\\(([\s\S]+?)\\\)/g, (_, e) => ` ${mathToSpeech(e)} `);
  out = out.replace(/\$([^$\n]+?)\$/g, (_, e) => ` ${mathToSpeech(e)} `);

  // Emphasis and highlights: drop the markers, keep the words.
  out = out.replace(/`([^`\n]+)`/g, '$1');
  out = out.replace(/!\[[^\]]*\]\([^)]*\)/g, ' ');
  out = out.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1');
  out = out.replace(/^\s{0,3}#{1,6}\s+/gm, '');
  out = out.replace(/(\*\*\*|\*\*|\*|___|__|~~)(?=\S)([\s\S]*?\S)\1/g, '$2');
  out = out.replace(/^\s{0,3}[-*+]\s+/gm, '');       // list bullets
  out = out.replace(/^\s{0,3}>\s?/gm, '');           // quote markers

  // Emoji, pictographs and their modifiers say nothing out loud.
  out = out.replace(/[\p{Extended_Pictographic}\p{Emoji_Presentation}]/gu, ' ');
  out = out.replace(/[︎️‍⃣\u{1F3FB}-\u{1F3FF}]/gu, '');

  // Decorative runs: ----, ====, ***, ### — before the maths pass, or "===="
  // would come out as "uguale a uguale a uguale a uguale a".
  out = out.replace(/([^\p{L}\p{N}\s])\1{2,}/gu, ' ');

  out = applyRules(out, MATH_SYMBOL_RULES);

  // Arrows and box drawing left over once the meaningful ones are spoken.
  out = out.replace(/[←-⇿─-╿■-◿]/g, ' ');

  // Leftover structural punctuation, then whitespace normalisation.
  out = out.replace(/https?:\/\/\S+/g, ' ');
  out = out.replace(/[*_~`#\[\]|>]/g, ' ');
  out = out.replace(/\n+/g, '. ');
  out = out.replace(/\s+/g, ' ');
  out = out.replace(/\s+([.,;:!?])/g, '$1');
  out = out.replace(/(?:\.\s*){2,}/g, '. ');
  // A chunk that starts right after a cut inherits the separator: drop it.
  out = out.replace(/^[\s.]+/, '');

  return out.trim();
}

let cachedVoices = [];

// --- Global speech state -----------------------------------------------------
// Any component can ask "is this message being read right now?". Without it the
// auto-play started by the chat stream is invisible to the per-message button,
// which then needs two clicks to stop: one to restart, one to cancel.
let activeSpeechId = null;
const speechListeners = new Set();

let speechProgressState = {
  speechId: null,
  fullText: '',
  charIndex: 0,
  charLength: 0,
  progress: 0,
  paused: false,
  isSpeaking: false,
};
const progressSubscribers = new Set();

export function subscribeSpeechProgress(listener) {
  progressSubscribers.add(listener);
  try { listener(speechProgressState); } catch (e) {}
  return () => progressSubscribers.delete(listener);
}

export function getSpeechProgress() {
  return speechProgressState;
}

function updateSpeechProgress(patch) {
  speechProgressState = { ...speechProgressState, ...patch };
  progressSubscribers.forEach(fn => { try { fn(speechProgressState); } catch (e) {} });
}

function setActiveSpeechId(id) {
  if (activeSpeechId === id) return;
  activeSpeechId = id;
  if (!id) {
    updateSpeechProgress({ isSpeaking: false, paused: false, speechId: null, charIndex: 0, progress: 0 });
  }
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

// --- Voice configuration -----------------------------------------------------

const VOICE_CONFIG_KEY = 'sigma_assistant_voice_config';
const DEFAULT_VOICE_CONFIG = {
  engine: '',        // '' = follow the server recommendation
  neuralVoice: '',
  voiceURI: '',      // system voice, used by the browser engine
  rate: 1.05,
  pitch: 1.0,
  volume: 1.0,
};

// Populated once from /api/tts/engines. Until it resolves the browser engine is
// used, which is also the correct answer when no neural engine is installed.
let serverEngines = null;
let serverDefault = { engine: 'browser', voice: '' };
let enginesProbe = null;

/** Read the saved voice settings, tolerating the legacy plain-string format. */
export function getVoiceConfig() {
  try {
    const raw = localStorage.getItem(VOICE_CONFIG_KEY) || localStorage.getItem('sigma_tts_voice');
    if (!raw) return { ...DEFAULT_VOICE_CONFIG };
    const parsed = raw.startsWith('{') ? JSON.parse(raw) : { voiceURI: raw };
    return { ...DEFAULT_VOICE_CONFIG, ...parsed };
  } catch (e) {
    return { ...DEFAULT_VOICE_CONFIG };
  }
}

export function setVoiceConfig(patch) {
  const updated = { ...getVoiceConfig(), ...patch };
  try { localStorage.setItem(VOICE_CONFIG_KEY, JSON.stringify(updated)); } catch (e) {}

  // Realtime volume update for active playing neural audio stream
  if (updated.volume !== undefined) {
    const vol = Math.max(0, Math.min(1, parseFloat(updated.volume)));
    if (speechStream && speechStream.audio) {
      speechStream.audio.volume = vol;
    }
  }
  return updated;
}

// Set when the server fails to synthesize: later readings go straight to the
// system voice instead of discovering the failure sentence by sentence.
let neuralDegraded = false;

/** Engine actually in use: the explicit choice, else the server recommendation. */
function resolveEngine() {
  const cfg = getVoiceConfig();
  const wanted = cfg.engine || serverDefault.engine;
  if (wanted === 'browser' || neuralDegraded) return { engine: 'browser', voice: '' };

  // Never commit to an engine the server cannot actually run: discovering it
  // mid-answer would mean changing voice halfway through.
  const known = (serverEngines || []).find(e => e.id === wanted);
  if (serverEngines && (!known || !known.installed)) return { engine: 'browser', voice: '' };

  return { engine: wanted, voice: cfg.neuralVoice || serverDefault.voice };
}

/** Ask the backend which neural engines are installed. Cached after first call. */
export function loadTTSEngines(force = false) {
  if (enginesProbe && !force) return enginesProbe;
  enginesProbe = fetch('/api/tts/engines')
    .then(r => r.json())
    .then(data => {
      serverEngines = data.engines || [];
      if (data.default) serverDefault = data.default;
      return serverEngines;
    })
    .catch(() => {
      serverEngines = [];
      return serverEngines;
    });
  return enginesProbe;
}

if (typeof window !== 'undefined') {
  loadTTSEngines();
}

/** Cached engine list (null until the first probe resolves). */
export function getTTSEngines() {
  return serverEngines;
}

/** Best system voice: Windows/macOS neural voices sound far better than the legacy ones. */
function pickBestSystemVoice(voices) {
  const italian = voices.filter(v => (v.lang || '').toLowerCase().startsWith('it'));
  const pool = italian.length > 0 ? italian : voices;
  const premium = pool.find(v => /natural|neural|online|premium|enhanced/i.test(v.name || ''));
  return premium || pool[0] || null;
}

/**
 * Build a configured utterance (voice, rate, pitch and volume from user settings).
 */
function buildUtterance(cleanText) {
  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.lang = 'it-IT';

  const cfg = getVoiceConfig();
  utterance.rate = parseFloat(cfg.rate) || DEFAULT_VOICE_CONFIG.rate;
  utterance.pitch = parseFloat(cfg.pitch) || DEFAULT_VOICE_CONFIG.pitch;
  utterance.volume = cfg.volume !== undefined ? Math.max(0, Math.min(1, parseFloat(cfg.volume))) : 1.0;

  const voices = getAvailableVoices();
  if (cfg.voiceURI) {
    utterance.voice = voices.find(v => v.voiceURI === cfg.voiceURI || v.name === cfg.voiceURI) || null;
  }
  if (!utterance.voice) utterance.voice = pickBestSystemVoice(voices);

  return utterance;
}

/**
 * Speak text using browser SpeechSynthesis (TTS).
 * `speechId` identifies the message being read so the UI can reflect its state.
 */
export function speakAgentMessage(text, onStart = null, onEnd = null, speechId = null, initialOffset = 0) {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    console.warn('SpeechSynthesis is not supported in this browser.');
    if (onEnd) onEnd();
    return false;
  }

  const clean = cleanTextForSpeech(text);
  if (!clean) {
    if (onEnd) onEnd();
    return false;
  }

  const id = speechId || `speech-${Date.now()}`;
  const clampedOffset = Math.max(0, Math.min(clean.length - 1, initialOffset));

  if (!startSpeechStream(id, { onStart, onEnd, initialOffset: clampedOffset, fullCleanText: clean })) {
    if (onEnd) onEnd();
    return false;
  }

  const textToSpeak = clampedOffset > 0 ? clean.slice(clampedOffset) : clean;
  pushSpeechStream(textToSpeak);
  endSpeechStream();
  return true;
}

export function pauseSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
    window.speechSynthesis.pause();
    updateSpeechProgress({ paused: true });
  }
}

export function resumeSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  if (window.speechSynthesis.paused) {
    window.speechSynthesis.resume();
    updateSpeechProgress({ paused: false });
  }
}

export function togglePauseSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  if (window.speechSynthesis.paused) {
    resumeSpeech();
  } else if (window.speechSynthesis.speaking) {
    pauseSpeech();
  }
}

export function seekSpeech(speechId, targetCharIndex, fullText = null) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  const text = fullText || speechProgressState.fullText;
  if (!text) return;

  const clampedIndex = Math.max(0, Math.min(text.length - 1, Math.round(targetCharIndex)));
  stopSpeech();
  speakAgentMessage(text, null, null, speechId, clampedIndex);
}

export function seekSpeechRelative(speechId, charDelta, fullText = null) {
  const currentIdx = speechProgressState.charIndex || 0;
  seekSpeech(speechId, currentIdx + charDelta, fullText);
}

export function seekSpeechPercent(speechId, percent, fullText = null) {
  const text = fullText || speechProgressState.fullText;
  if (!text) return;
  const targetIdx = Math.round(Math.max(0, Math.min(1, percent)) * text.length);
  seekSpeech(speechId, targetIdx, text);
}

// --- Sentence-level streaming playback ---------------------------------------

let speechStream = null;

const SENTENCE_ENDINGS = '.!?…\n';
const CLAUSE_ENDINGS = ',;:';
const MIN_FIRST_CHUNK = 20;
const MIN_CLAUSE_CHUNK = 35;
const MAX_UNPUNCTUATED = 100;
const HAS_LETTERS = /[a-zA-ZÀ-ÿ]/;

// Hold active SpeechSynthesisUtterance references to prevent V8 garbage collection mid-speech
const activeUtterances = new Set();
let keepAliveTimer = null;

export function startKeepAlive() {
  if (keepAliveTimer || typeof window === 'undefined' || !window.speechSynthesis) return;
  keepAliveTimer = setInterval(() => {
    if (window.speechSynthesis) {
      // Touch speaking property to keep IPC active without triggering audio device WASAPI pauses
      const _active = window.speechSynthesis.speaking;
    }
    if (!isSpeaking()) {
      stopKeepAlive();
    }
  }, 5000);
}

export function stopKeepAlive() {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }
}

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

/** True while a math delimiter is still open, so the chunk must not be cut yet. */
function isMidFormula(chunk) {
  const dollars = (chunk.match(/\$/g) || []).length;
  if (dollars % 2 === 1) return true;
  const opens = (chunk.match(/\\[[(]/g) || []).length;
  const closes = (chunk.match(/\\[\])]/g) || []).length;
  return opens > closes;
}

function settleChunk(state) {
  if (speechStream !== state) return;
  state.pending = Math.max(0, state.pending - 1);
  const queueEmpty = !state.browserQueue || state.browserQueue.length === 0;
  if (state.started && state.ended && state.pending === 0 && queueEmpty) {
    stopKeepAlive();
    activeUtterances.clear();
    speechStream = null;
    setActiveSpeechId(null);
    if (state.onEnd) state.onEnd();
  }
}

function markStarted(state) {
  if (state.started) return;
  state.started = true;
  if (state.onStart) state.onStart();
}

/**
 * Play neural clips one at a time, strictly in sequence order.
 *
 * Synthesis is a network round-trip per sentence and responses can land out of
 * order, so each clip carries its slot number and waits its turn.
 */
function playNextClip(state) {
  if (speechStream !== state || state.busy) return;
  if (!state.queue.has(state.playSeq)) return;

  const url = state.queue.get(state.playSeq);
  state.queue.delete(state.playSeq);
  state.playSeq += 1;

  if (!url) {                        // sentence with no audio: skip its slot
    settleChunk(state);
    playNextClip(state);
    return;
  }

  state.busy = true;
  markStarted(state);

  const audio = new Audio(url);
  const cfg = getVoiceConfig();
  audio.volume = cfg.volume !== undefined ? Math.max(0, Math.min(1, parseFloat(cfg.volume))) : 1.0;
  state.audio = audio;

  const done = () => {
    if (!state.busy) return;         // guard against a doubled end/error event
    state.busy = false;
    URL.revokeObjectURL(url);
    state.audio = null;
    settleChunk(state);
    playNextClip(state);
  };
  audio.onended = done;
  audio.onerror = done;
  audio.play().catch(done);
}

function enqueueNeural(state, clean, engine, voice) {
  const seq = state.nextSeq++;
  state.pending += 1;

  fetch('/api/tts/speak', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: clean, engine, voice, speed: getVoiceConfig().rate }),
    signal: state.abort.signal,
  })
    .then(r => r.json())
    .then(data => {
      if (speechStream !== state) return;
      if (!data.audio) throw new Error(data.error || 'Sintesi fallita');
      const bytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
      state.queue.set(seq, URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' })));
      playNextClip(state);
    })
    .catch(err => {
      if (speechStream !== state) return;
      if (err && err.name === 'AbortError') return;
      if (!neuralDegraded) {
        neuralDegraded = true;
        console.warn('TTS neurale non disponibile, le prossime letture useranno la voce di sistema:', err.message);
      }
      // Deliberately silent for this sentence rather than starting a system
      // voice on top of the clips still playing: one reading, one voice.
      state.queue.set(seq, null);
      playNextClip(state);
    });
}

/**
 * Buffered browser TTS: feed Chrome at most MAX_CHROME_QUEUE utterances at a
 * time from a JS-side queue.
 *
 * Why not feed them all?  Chrome/SAPI silently drops utterances when its
 * internal C++ queue grows past ~5 items — events still fire but no audio
 * reaches the speakers.
 *
 * Why not feed one at a time?  Chrome closes and re-opens the WASAPI audio
 * device between utterances when the queue is empty, causing a 1-3 s hardware
 * gap on Realtek / USB / Bluetooth speakers.
 *
 * Keeping 2 buffered is the sweet spot: the next utterance is already queued
 * when the current one ends, so Chrome never releases the audio device, but
 * the queue never grows large enough to trigger the silent-drop bug.
 */
const MAX_CHROME_QUEUE = 2;

function feedChromeQueue(state) {
  if (speechStream !== state) return;
  if (!state.browserQueue || state.browserQueue.length === 0) return;

  while (state.chromeActive < MAX_CHROME_QUEUE && state.browserQueue.length > 0) {
    const clean = state.browserQueue.shift();
    const chunkOffset = state.processedChars || 0;
    state.processedChars = chunkOffset + clean.length + 1;

    const utterance = buildUtterance(clean);
    activeUtterances.add(utterance);
    state.chromeActive += 1;

    utterance.onboundary = (event) => {
      if (event.name === 'word' || !event.name) {
        const charIdx = chunkOffset + (event.charIndex || 0);
        const charLen = event.charLength || 5;
        const totalLen = (state.fullCleanText || '').length || 1;
        updateSpeechProgress({
          speechId: state.id,
          fullText: state.fullCleanText || '',
          charIndex: charIdx,
          charLength: charLen,
          progress: Math.min(1, Math.max(0, charIdx / totalLen)),
          paused: false,
          isSpeaking: true,
        });
      }
    };

    const handleFinish = () => {
      activeUtterances.delete(utterance);
      state.chromeActive = Math.max(0, state.chromeActive - 1);
      settleChunk(state);
      feedChromeQueue(state);
    };

    utterance.onstart = () => {
      markStarted(state);
      startKeepAlive();
    };
    utterance.onend = handleFinish;
    utterance.onerror = handleFinish;

    try {
      window.speechSynthesis.speak(utterance);
      startKeepAlive();
    } catch (err) {
      handleFinish();
    }
  }
}

function enqueueBrowser(state, clean) {
  state.pending += 1;
  if (!state.browserQueue) state.browserQueue = [];
  state.browserQueue.push(clean);
  feedChromeQueue(state);
}

function enqueueSpeech(state, rawText) {
  const clean = cleanTextForSpeech(stripFencedCode(state, rawText));
  // Punctuation-only leftovers would be spoken as an audible hiccup.
  if (!clean || !HAS_LETTERS.test(clean)) return;

  state.chunkCount += 1;
  if (state.engine && state.engine !== 'browser') {
    enqueueNeural(state, clean, state.engine, state.voice);
  } else {
    enqueueBrowser(state, clean);
  }
}

/**
 * Index of the first boundary that closes a real sentence, or -1.
 *
 * Boundaries that do not end a sentence are skipped rather than cut on: the dot
 * of a list marker ("1.") would otherwise be spoken alone, turning an
 * enumeration into a stutter, and a dot inside "$1.5$" would swallow the maths.
 */
function findSentenceCut(buffer, force, first) {
  for (let i = 0; i < buffer.length; i++) {
    const char = buffer[i];
    const strong = SENTENCE_ENDINGS.includes(char);
    const minLen = first ? MIN_FIRST_CHUNK : MIN_CLAUSE_CHUNK;
    const weak = i >= minLen && CLAUSE_ENDINGS.includes(char);
    if (!strong && !weak) continue;
    if (char === '.') {
      // A real full stop is followed by a space. Without this check the dot in
      // "example.com" or "1.5" splits the text and the markdown link (or the
      // number) no longer survives the cleaning pass.
      const next = buffer[i + 1];
      if (next === undefined ? !force : !/\s/.test(next)) continue;
    }
    const candidate = buffer.slice(0, i + 1);
    if (!HAS_LETTERS.test(candidate)) continue;
    if (isMidFormula(candidate)) continue;
    return i;
  }
  return -1;
}

function drainSpeechStream(force) {
  const state = speechStream;
  if (!state) return;

  while (state.buffer) {
    let cut = findSentenceCut(state.buffer, force, state.chunkCount === 0);
    if (cut === -1) {
      // No complete sentence yet: wait for more text, unless the answer is over
      // or the model is writing an unusually long unpunctuated run.
      if (force) cut = state.buffer.length - 1;
      else if (state.buffer.length > MAX_UNPUNCTUATED) {
        const space = state.buffer.lastIndexOf(' ');
        if (space <= 0) return;
        cut = space;
      } else return;
    }
    const chunk = state.buffer.slice(0, cut + 1);
    state.buffer = state.buffer.slice(cut + 1);
    enqueueSpeech(state, chunk);
  }
}

/** Begin reading a message that is still being generated. */
export function startSpeechStream(speechId, { onStart = null, onEnd = null, initialOffset = 0, fullCleanText = '' } = {}) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return false;
  stopSpeech();

  const { engine, voice } = resolveEngine();
  speechStream = {
    id: speechId,
    buffer: '', inCode: false, chunkCount: 0,
    pending: 0, ended: false, started: false,
    engine, voice,
    queue: new Map(), nextSeq: 0, playSeq: 0, busy: false, audio: null,
    browserQueue: [], chromeActive: 0,
    processedChars: initialOffset,
    fullCleanText: fullCleanText,
    abort: new AbortController(),
    onStart, onEnd,
  };
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
  const queueEmpty = !state.browserQueue || state.browserQueue.length === 0;
  if (state.pending === 0 && queueEmpty) {
    speechStream = null;
    setActiveSpeechId(null);
    if (state.onEnd) state.onEnd();
  }
}

/**
 * Stop active speech synthesis: system voice, queued clips and pending requests.
 */
export function stopSpeech() {
  if (typeof window === 'undefined') return;

  stopKeepAlive();
  activeUtterances.clear();

  const state = speechStream;
  speechStream = null;

  if (window.speechSynthesis) window.speechSynthesis.cancel();

  if (state) {
    state.busy = false;
    state.chromeActive = 0;
    if (state.browserQueue) state.browserQueue = [];
    try { state.abort.abort(); } catch (e) {}
    if (state.audio) {
      state.audio.onended = state.audio.onerror = null;
      state.audio.pause();
      state.audio = null;
    }
    state.queue.forEach(url => { if (url) URL.revokeObjectURL(url); });
    state.queue.clear();
  }

  setActiveSpeechId(null);
}

/**
 * Check if TTS speech is currently playing.
 */
export function isSpeaking() {
  if (typeof window === 'undefined') return false;
  if (speechStream && speechStream.audio) return true;
  return window.speechSynthesis ? window.speechSynthesis.speaking : false;
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

// --- Wake-word microphone ----------------------------------------------------

const WAKE_WORD = 'sigma';
const SILENCE_MS = 2000;
// Fired by the browser during normal operation; restarting is the answer, not
// an error message.
const BENIGN_RECOGNITION_ERRORS = ['no-speech', 'aborted', 'audio-capture'];

/** Lowercase and strip combining accents so "Sìgma" still matches the wake word. */
function normalizeForMatch(text) {
  return text.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/**
 * Microphone that listens for a wake word and submits on silence.
 *
 * It stays in `waiting` until it hears the wake word, then captures everything
 * said after it and, once the speaker has been quiet for `silenceMs`, hands the
 * phrase over and returns to waiting. The browser ends recognition on its own
 * every so often, so it is restarted for as long as the caller keeps it active.
 *
 * Returns a handle with `start()` / `stop()`, or null when unsupported.
 */
export function createWakeWordMic({
  wakeWord = WAKE_WORD,
  silenceMs = SILENCE_MS,
  lang = 'it-IT',
  onState = null,
  onTranscript = null,
  onSubmit = null,
  onError = null,
} = {}) {
  if (typeof window === 'undefined') return null;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn('SpeechRecognition is not supported in this browser.');
    return null;
  }

  const wake = normalizeForMatch(wakeWord);
  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = lang;

  let active = false;      // the user wants the mic on
  let armed = false;       // wake word heard, capturing the command
  let wakeIndex = -1;      // index of the initial wake word in the transcript
  let captured = '';
  let silenceTimer = null;
  let restartTimer = null;
  let ignoreUntilRestart = false;

  const setState = (state) => { if (onState) onState(state); };

  const clearSilence = () => {
    if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
  };

  const resetRecognitionSession = () => {
    clearSilence();
    armed = false;
    wakeIndex = -1;
    captured = '';
    ignoreUntilRestart = true;
    if (active) {
      setState('waiting');
      try { recognition.stop(); } catch (e) {}
    }
  };

  const submitCaptured = () => {
    clearSilence();
    const phrase = captured.trim();
    armed = false;
    wakeIndex = -1;
    captured = '';
    ignoreUntilRestart = true;
    if (active) setState('waiting');
    if (phrase && onSubmit) onSubmit(phrase);
    if (active) {
      try { recognition.stop(); } catch (e) {}
    }
  };

  recognition.onstart = () => {
    ignoreUntilRestart = false;
  };

  recognition.onresult = (event) => {
    if (ignoreUntilRestart) return;

    let transcript = '';
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }

    const normalized = normalizeForMatch(transcript);

    if (!armed) {
      const at = normalized.indexOf(wake);
      if (at === -1) return;                 // still nothing addressed to us
      armed = true;
      wakeIndex = at;
      setState('listening');
      // Barge-in: the user talking to the agent outranks the agent talking.
      stopSpeech();
    }

    if (wakeIndex === -1) {
      wakeIndex = normalized.indexOf(wake);
    }

    // Keep only what was said after the initial wake word, punctuation trimmed.
    if (wakeIndex !== -1) {
      captured = transcript.slice(wakeIndex + wakeWord.length).replace(/^[\s,.;:!?]+/, '');
    } else {
      captured = transcript.replace(/^[\s,.;:!?]+/, '');
    }

    if (onTranscript) onTranscript(captured);
    clearSilence();
    silenceTimer = setTimeout(submitCaptured, silenceMs);
  };

  recognition.onerror = (event) => {
    const code = event && event.error;
    if (BENIGN_RECOGNITION_ERRORS.includes(code)) return;
    if (onError) onError(code || 'unknown');
  };

  recognition.onend = () => {
    // A pending phrase must not be lost when the browser closes the session,
    // unless we intentionally stopped recognition to reset after a submission.
    if (armed && !ignoreUntilRestart) submitCaptured();
    if (!active) { setState('off'); return; }
    // Rapid restart (50ms) to prevent audio capture dropouts in Chrome.
    restartTimer = setTimeout(() => {
      if (!active) return;
      try {
        recognition.start();
      } catch (e) {
        // If Chrome is still releasing the previous session, retry seamlessly in 100ms
        restartTimer = setTimeout(() => {
          if (!active) return;
          try { recognition.start(); } catch (err) {}
        }, 100);
      }
    }, 50);
  };

  return {
    start() {
      if (active) return true;
      active = true;
      armed = false;
      wakeIndex = -1;
      captured = '';
      ignoreUntilRestart = false;
      try {
        recognition.start();
      } catch (e) {
        active = false;
        if (onError) onError(e.message || 'start-failed');
        return false;
      }
      setState('waiting');
      return true;
    },
    stop() {
      active = false;
      armed = false;
      wakeIndex = -1;
      captured = '';
      ignoreUntilRestart = false;
      clearSilence();
      if (restartTimer) { clearTimeout(restartTimer); restartTimer = null; }
      try { recognition.stop(); } catch (e) {}
      setState('off');
    },
    reset() {
      resetRecognitionSession();
    },
    isActive() { return active; },
  };
}
