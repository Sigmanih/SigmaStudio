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

  // Markdown images: strip completely (do not speak alt text as prose)
  out = out.replace(/!\[[^\]]*\]\([^)]*\)/g, ' ');

  // Markdown links: replace [Readable Title](https://...) -> Readable Title
  out = out.replace(/\[([^\]]+)\]\([^)]*\)/g, ' $1 ');

  // Incomplete markdown link fragments: [Readable Title](https://... -> Readable Title
  out = out.replace(/\[([^\]]+)\]\s*\(\s*https?:\/\/[^\s)]*/g, ' $1 ');

  // Standalone bracketed labels: [Label] -> Label
  out = out.replace(/\[([^\]]+)\]/g, ' $1 ');

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

  // Leftover structural punctuation, raw URLs, and domain names (never speak URLs aloud).
  out = out.replace(/https?:\/\/[^\s)]+/gi, ' ');
  out = out.replace(/\bwww\.[a-zA-Z0-9\-_.]{2,}\.[a-zA-Z]{2,}\b/gi, ' ');
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
  try {
    const installedRaw = localStorage.getItem('sigma_marketplace_installed');
    if (installedRaw) {
      const parsed = JSON.parse(installedRaw);
      if (parsed && parsed.sigma_voice_studio === false) {
        serverEngines = [];
        return Promise.resolve([]);
      }
    }
  } catch (e) {}

  enginesProbe = fetch('/api/tts/engines')
    .then(r => {
      if (!r.ok) return { engines: [], default: { engine: 'browser', voice: '' } };
      return r.json();
    })
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
 * Best voice that synthesises on this machine.
 *
 * The premium voices preferred above are the ones that stream their audio from
 * a server, so they are also the ones that go missing when the network does.
 * This is where a reading retreats to when that keeps happening.
 */
function pickBestLocalVoice(voices) {
  const local = voices.filter(v => v.localService !== false);
  const italian = local.filter(v => (v.lang || '').toLowerCase().startsWith('it'));
  return italian[0] || local[0] || null;
}

/**
 * Give up on an online voice that keeps losing sentences.
 *
 * Retrying a remote voice that cannot reach its server just loses the sentence
 * again, so past a couple of faults the whole reading switches to a local one.
 */
function noteVoiceFault(record) {
  const voice = record.utterance && record.utterance.voice;
  if (forcedLocalVoiceURI || !voice || voice.localService !== false) return;

  remoteVoiceFaults += 1;
  if (remoteVoiceFaults < MAX_REMOTE_FAULTS) return;

  const local = pickBestLocalVoice(getAvailableVoices());
  if (!local) return;
  forcedLocalVoiceURI = local.voiceURI;
  speedSamples = [];                        // a different voice, a different speed
  reportSpeechIssue(
    'remote-voice-unstable',
    `Voce online instabile: la lettura passa alla voce locale "${local.name}"`,
    voice.name || '',
  );
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
  // A voice that proved unreliable this session overrides the preference: the
  // setting is untouched, only this run stops using it.
  if (forcedLocalVoiceURI) {
    utterance.voice = voices.find(v => v.voiceURI === forcedLocalVoiceURI) || null;
  }
  if (!utterance.voice && cfg.voiceURI) {
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

  const currentIdx = speechProgressState.charIndex || 0;
  const currentText = speechProgressState.fullText || '';
  const currentId = speechProgressState.speechId || activeSpeechId;

  stopUtteranceSync();
  stopWatchdog();

  if (speechStream) {
    speechStream.isPaused = true;
    speechStream.busy = false;
    speechStream.chromeActive = 0;
    speechStream.inFlight = [];
    if (speechStream.leadTimer) { clearTimeout(speechStream.leadTimer); speechStream.leadTimer = null; }
    if (speechStream.browserQueue) speechStream.browserQueue = [];
    // Immediately halt neural audio playback
    if (speechStream.audio) {
      speechStream.audio.pause();
    }
  }

  // Freeze position snapshot
  speechProgressState = {
    speechId: currentId,
    fullText: currentText,
    charIndex: currentIdx,
    charLength: 5,
    progress: currentText.length > 0 ? Math.min(1, currentIdx / currentText.length) : 0,
    paused: true,
    isSpeaking: true,
    savedPauseIndex: currentIdx,
    savedPauseId: currentId,
    savedPauseText: currentText,
  };

  // Detach handlers from active utterances to prevent Chrome's onend/onerror callbacks from wiping state
  activeUtterances.forEach(u => {
    u.onend = null;
    u.onerror = null;
    u.onboundary = null;
    u.onstart = null;
  });
  activeUtterances.clear();
  // Their records would otherwise look stranded to the watchdog on resume.
  utteranceRecords.forEach(record => { record.finished = true; });
  utteranceRecords.clear();

  try { window.speechSynthesis.cancel(); } catch (e) {}

  // Broadcast paused state to all subscribers
  progressSubscribers.forEach(fn => { try { fn(speechProgressState); } catch (e) {} });
}

export function resumeSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;

  const targetId = speechProgressState.savedPauseId || speechProgressState.speechId || activeSpeechId;
  const targetText = speechProgressState.savedPauseText || speechProgressState.fullText;
  const targetIndex = speechProgressState.savedPauseIndex !== undefined ? speechProgressState.savedPauseIndex : (speechProgressState.charIndex || 0);

  if (targetId && targetText) {
    seekSpeech(targetId, targetIndex, targetText);
  }
}

export function togglePauseSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  if (speechProgressState.paused) {
    resumeSpeech();
  } else {
    pauseSpeech();
  }
}

export function seekSpeech(speechId, targetCharIndex, fullText = null) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  const text = fullText || speechProgressState.fullText;
  if (!text) return;

  const clampedIndex = Math.max(0, Math.min(text.length - 1, Math.round(targetCharIndex)));
  stopSpeech();
  setTimeout(() => {
    speakAgentMessage(text, null, null, speechId, clampedIndex);
  }, 60);
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

let audioSyncInterval = null;
let activeUtteranceStart = 0;
let activeChunkOffset = 0;

function startUtteranceSync(state, chunkOffset, textLength) {
  stopUtteranceSync();
  if (!state) return;

  activeChunkOffset = chunkOffset;
  activeUtteranceStart = Date.now();

  const speed = charsPerSec();

  audioSyncInterval = setInterval(() => {
    if (!speechStream || speechStream !== state || !window.speechSynthesis) {
      stopUtteranceSync();
      return;
    }
    if (speechProgressState.paused) {
      return;
    }

    const elapsed = (Date.now() - activeUtteranceStart) / 1000;
    const spokenChars = Math.round(elapsed * speed);
    const clampedChunkPos = Math.min(textLength, spokenChars);
    const currentCharIdx = activeChunkOffset + clampedChunkPos;
    const totalLen = (state.fullCleanText || '').length || 1;

    const prog = Math.min(1, Math.max(0, currentCharIdx / totalLen));

    updateSpeechProgress({
      speechId: state.id,
      fullText: state.fullCleanText || '',
      charIndex: currentCharIdx,
      charLength: 5,
      progress: prog,
      paused: false,
      isSpeaking: true,
    });
  }, 100);
}

// --- Neural engine progress sync -----------------------------------------------
let neuralSyncRAF = null;
let neuralClipStartTime = 0;
let neuralClipDuration = 0;
let neuralClipCharOffset = 0;
let neuralClipCharLength = 0;

function startNeuralSync(state, audio, charOffsetInCleanedText, charLengthOfClip) {
  stopNeuralSync();
  if (!state || !audio) return;

  neuralClipCharOffset = charOffsetInCleanedText;
  neuralClipCharLength = charLengthOfClip || 1;
  neuralClipStartTime = performance.now();
  neuralClipDuration = (audio.duration && isFinite(audio.duration)) ? audio.duration * 1000 : 0;

  const tick = () => {
    if (speechProgressState.paused) {
      neuralSyncRAF = requestAnimationFrame(tick);
      return;
    }

    // Use audio.currentTime when available, otherwise estimate from elapsed wall clock
    let progressFraction = 0;
    if (audio.currentTime !== undefined && audio.duration && isFinite(audio.duration) && audio.duration > 0) {
      progressFraction = Math.min(1, audio.currentTime / audio.duration);
    } else if (neuralClipDuration > 0) {
      const elapsed = performance.now() - neuralClipStartTime;
      progressFraction = Math.min(1, elapsed / neuralClipDuration);
    }

    const currentCharIdx = neuralClipCharOffset + Math.round(progressFraction * neuralClipCharLength);
    const totalLen = (state.fullCleanText || '').length || 1;
    const prog = Math.min(1, Math.max(0, currentCharIdx / totalLen));

    updateSpeechProgress({
      speechId: state.id,
      fullText: state.fullCleanText || '',
      charIndex: currentCharIdx,
      charLength: 5,
      progress: prog,
      paused: false,
      isSpeaking: true,
    });

    if (audio.paused || audio.ended || progressFraction >= 1) {
      stopNeuralSync();
      return;
    }
    neuralSyncRAF = requestAnimationFrame(tick);
  };

  neuralSyncRAF = requestAnimationFrame(tick);
}

function stopNeuralSync() {
  if (neuralSyncRAF) {
    cancelAnimationFrame(neuralSyncRAF);
    neuralSyncRAF = null;
  }
}

function stopUtteranceSync() {
  if (audioSyncInterval) {
    clearInterval(audioSyncInterval);
    audioSyncInterval = null;
  }
  stopNeuralSync();
}

// --- Sentence-level streaming playback ---------------------------------------

let speechStream = null;

const SENTENCE_ENDINGS = '.!?…\n';
const MIN_FIRST_CHUNK = 60;
const MAX_UNPUNCTUATED = 200;
const HAS_LETTERS = /[a-zA-ZÀ-ÿ]/;

// Hold active SpeechSynthesisUtterance references to prevent V8 garbage collection mid-speech
const activeUtterances = new Set();

// --- Playback faults ---------------------------------------------------------
// Speech synthesis fails in ways that are inaudible by design: an utterance the
// engine drops, a sentence cut off halfway, a clip the server never rendered.
// Every one of them sounds like a hole in the voice, so each is detected,
// repaired where possible, and reported — never swallowed.

const speechIssueListeners = new Set();
let lastSpeechIssue = null;

/** Subscribe to playback faults. Returns an unsubscribe function. */
export function subscribeSpeechIssues(listener) {
  speechIssueListeners.add(listener);
  return () => speechIssueListeners.delete(listener);
}

/** Most recent playback fault, or null. */
export function getLastSpeechIssue() {
  return lastSpeechIssue;
}

function reportSpeechIssue(code, message, detail = '') {
  lastSpeechIssue = { code, message, detail, at: Date.now() };
  console.warn(`[TTS] ${code} — ${message}`, detail || '');
  speechIssueListeners.forEach(fn => { try { fn(lastSpeechIssue); } catch (e) {} });
}

// --- Speaking speed calibration ---------------------------------------------
// Deciding whether an utterance was cut short means knowing how long it should
// have taken, and 14.5 characters per second is only a starting guess: a
// Microsoft Natural voice and an old SAPI voice differ by more than a third.
// A wrong guess either misses real drop-outs or repeats good audio, so the real
// speed is measured from the utterances that do complete.
//
// A cut-off utterance always *inflates* the measurement — same text, less time
// — so the honest samples are the slow ones: the estimate is a low percentile,
// never the mean.

const CHARS_PER_SEC_BASE = 14.5;
const SPEED_SAMPLE_LIMIT = 24;
const MIN_CALIBRATION_SAMPLES = 4;
const SPEED_PERCENTILE = 0.3;

let speedSamples = [];
let speedSampleKey = '';

/** Samples belong to one voice at one rate; anything else invalidates them. */
function calibrationKey() {
  const cfg = getVoiceConfig();
  return `${forcedLocalVoiceURI || cfg.voiceURI || 'auto'}|${cfg.rate}`;
}

function recordSpeedSample(textLength, elapsedMs) {
  if (textLength < 25 || elapsedMs < 300) return;      // too short to measure
  const key = calibrationKey();
  if (key !== speedSampleKey) { speedSampleKey = key; speedSamples = []; }
  speedSamples.push((textLength / elapsedMs) * 1000);
  if (speedSamples.length > SPEED_SAMPLE_LIMIT) speedSamples.shift();
}

function isCalibrated() {
  return speedSamples.length >= MIN_CALIBRATION_SAMPLES && calibrationKey() === speedSampleKey;
}

function charsPerSec() {
  if (isCalibrated()) {
    const sorted = [...speedSamples].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length * SPEED_PERCENTILE)];
  }
  const rate = parseFloat(getVoiceConfig().rate) || 1.0;
  return CHARS_PER_SEC_BASE * rate;
}

// Chrome stops speaking after roughly 15 s and never reports it: the utterance
// simply ends. Keeping every utterance well under that ceiling avoids the bug
// instead of trying to detect it — 170 characters is ~11 s at rate 1.0.
const MAX_UTTERANCE_CHARS = 170;

// Utterances buffered inside Chrome. Two is the sweet spot: the next one is
// always queued so the audio device is never released, and the queue never
// grows past the ~5 items where Chrome starts silently dropping utterances.
const MAX_CHROME_QUEUE = 2;

// Before the first utterance, wait for a second one to be ready. Starting with
// nothing behind it means Chrome drains the queue, closes the WASAPI device and
// re-opens it for the next sentence — a 1-3 s hardware gap on Realtek / USB /
// Bluetooth outputs. Capped so the reading never starts noticeably later.
const MIN_LEAD_CHUNKS = 2;
const LEAD_DEADLINE_MS = 700;

// Watchdog: how often to look for a stalled engine, and how many consecutive
// silent ticks mean the utterances Chrome holds are never going to play.
const WATCHDOG_MS = 700;
const STALL_TICKS = 3;

// How much of an utterance must have been spoken for it to count as delivered.
// Until the voice is calibrated only a gross shortfall is acted on, so a voice
// faster than the guess is never mistaken for a drop-out.
const COVERAGE_OK = 0.85;
const COVERAGE_OK_UNCALIBRATED = 0.5;

// Below this share of the utterance the engine produced no audio at all: an
// online voice whose audio never downloaded, or one Chrome accepted and threw
// away. Measured as a fraction, not in milliseconds, so it holds for a
// two-word fragment and a full sentence alike.
const NO_AUDIO_COVERAGE = 0.12;

// Short utterances are never judged on timing: on a "Terza." the numbers are
// noise. Repeating what was already heard is worse than the half-second of
// silence it would be repairing, so a repair has to be worth making.
const MIN_JUDGEABLE_UTTERANCE = 40;
const MIN_REPAIRABLE_TAIL = 20;
const MAX_UTTERANCE_RETRIES = 2;

// Online voices (localService === false) stream their audio from Microsoft's
// servers, so a network stumble silently costs a sentence. After a couple of
// faults the reading moves to a local voice and stops depending on the network.
const MAX_REMOTE_FAULTS = 2;
let forcedLocalVoiceURI = '';
let remoteVoiceFaults = 0;

// Errors the engine raises when we ourselves stopped it: not faults.
const BENIGN_UTTERANCE_ERRORS = ['interrupted', 'canceled', 'cancelled'];

/** Bookkeeping for every utterance in flight, keyed by the utterance itself. */
const utteranceRecords = new Map();

let watchdogTimer = null;
let stallTicks = 0;

function startWatchdog() {
  if (watchdogTimer || typeof window === 'undefined' || !window.speechSynthesis) return;
  stallTicks = 0;
  watchdogTimer = setInterval(watchdogTick, WATCHDOG_MS);
}

function stopWatchdog() {
  if (watchdogTimer) {
    clearInterval(watchdogTimer);
    watchdogTimer = null;
  }
  stallTicks = 0;
}

function watchdogTick() {
  const state = speechStream;
  const synth = typeof window !== 'undefined' ? window.speechSynthesis : null;
  if (!state || !synth) { stopWatchdog(); return; }

  if (state.chromeActive === 0) {
    stallTicks = 0;
    if (!state.browserQueue || state.browserQueue.length === 0) stopWatchdog();
    return;
  }
  if (speechProgressState.paused) { stallTicks = 0; return; }

  // Chrome can latch into a paused state after a cancel(): speak() still queues
  // the utterance, onstart never fires, and the reading dies without a sound.
  if (synth.paused) {
    try { synth.resume(); } catch (e) {}
    reportSpeechIssue('synth-stuck-paused', 'Motore vocale bloccato in pausa, ripreso');
    stallTicks = 0;
    return;
  }

  // An utterance that started and never ends holds the whole reading behind it.
  // A remote voice whose audio stream stalls does exactly this, silently.
  const overdue = state.inFlight.find(record => !record.finished && record.sawStart &&
    Date.now() - record.startedAt > (record.item.text.length / charsPerSec()) * 1000 * 3 + 5000);
  if (overdue) {
    stallTicks = 0;
    finishUtterance(overdue, 'error', 'hung');
    // Let go of a dead utterance only once nothing else depends on the engine:
    // a repair has already taken back whatever was queued behind it.
    if (synth.speaking && state.inFlight.length === 0) {
      try { synth.cancel(); } catch (e) {}
    }
    return;
  }

  if (synth.speaking || synth.pending) { stallTicks = 0; return; }

  // Utterances are outstanding, nothing is playing and no event ever arrived:
  // Chrome dropped them. Push them through the fault path so the reading
  // recovers instead of going quiet for the rest of the answer.
  stallTicks += 1;
  if (stallTicks < STALL_TICKS) return;
  stallTicks = 0;
  Array.from(utteranceRecords.values())
    .filter(record => record.state === state && !record.finished)
    .forEach(record => finishUtterance(record, 'error', 'stalled'));
}

// The watchdog replaced the old keep-alive ticker, which only read
// `speechSynthesis.speaking` and therefore did nothing. Names kept for callers.
export function startKeepAlive() { startWatchdog(); }
export function stopKeepAlive() { stopWatchdog(); }

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

/** True while a markdown link `[title](url)` is still unclosed in the chunk buffer. */
function isMidMarkdownLink(chunk) {
  const lastOpenBracket = chunk.lastIndexOf('[');
  if (lastOpenBracket === -1) return false;
  const afterBracket = chunk.slice(lastOpenBracket);
  const closeBracket = afterBracket.indexOf(']');
  if (closeBracket === -1) return true; // '[' not closed yet
  // If [title] is immediately followed by '(', check if ')' has arrived
  const afterCloseBracket = afterBracket.slice(closeBracket + 1);
  if (afterCloseBracket.startsWith('(')) {
    return !afterCloseBracket.includes(')');
  }
  return false;
}

function settleChunk(state) {
  if (speechStream !== state) return;
  if (speechProgressState && speechProgressState.paused) return;
  state.pending = Math.max(0, state.pending - 1);
  const queueEmpty = !state.browserQueue || state.browserQueue.length === 0;
  if (state.started && state.ended && state.pending === 0 && queueEmpty) {
    stopWatchdog();
    if (state.leadTimer) { clearTimeout(state.leadTimer); state.leadTimer = null; }
    activeUtterances.clear();
    utteranceRecords.clear();
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

  const entry = state.queue.get(state.playSeq);
  state.queue.delete(state.playSeq);
  state.playSeq += 1;

  const advance = () => {
    state.busy = false;
    settleChunk(state);
    playNextClip(state);
  };

  if (!entry) { advance(); return; }

  // Synthesis failed for this sentence. Skipping it would leave a hole in the
  // middle of the answer, so it is read by the system voice in its own slot:
  // sequential playback means the two voices never overlap.
  if (!entry.url) {
    if (!entry.text) { advance(); return; }
    state.busy = true;
    markStarted(state);
    speakFallbackClip(state, entry, advance);
    return;
  }

  const audio = entry.audio || new Audio(entry.url);
  const cfg = getVoiceConfig();
  audio.volume = cfg.volume !== undefined ? Math.max(0, Math.min(1, parseFloat(cfg.volume))) : 1.0;
  state.busy = true;
  state.audio = audio;
  markStarted(state);

  if (entry.charOffset !== undefined && entry.charLength) {
    startNeuralSync(state, audio, entry.charOffset, entry.charLength);
  }

  let settled = false;
  const done = (fallbackReason) => {
    if (settled) return;             // guard against a doubled end/error event
    settled = true;
    stopNeuralSync();
    URL.revokeObjectURL(entry.url);
    state.audio = null;

    // The clip exists but cannot be played (decode failure, autoplay block):
    // the sentence is still owed to the listener.
    if (fallbackReason && entry.text) {
      reportSpeechIssue('clip-unplayable', 'Clip audio non riproducibile, letta con la voce di sistema', fallbackReason);
      speakFallbackClip(state, entry, advance);
      return;
    }
    advance();
  };

  audio.onended = () => done(null);
  audio.onerror = () => done('decode-error');
  audio.play().catch(err => done((err && err.name) || 'play-rejected'));
}

/** Read one sentence with the system voice, inside the neural playback order. */
function speakFallbackClip(state, entry, onDone) {
  if (typeof window === 'undefined' || !window.speechSynthesis) { onDone(); return; }

  const parts = splitUtterance(entry.text);
  let index = 0;
  let guard = null;

  const next = () => {
    if (guard) { clearTimeout(guard); guard = null; }
    if (speechStream !== state) return;
    if (index >= parts.length) { onDone(); return; }

    const text = parts[index++];
    const utterance = buildUtterance(text);
    activeUtterances.add(utterance);

    let advanced = false;
    const step = () => {
      if (advanced) return;
      advanced = true;
      activeUtterances.delete(utterance);
      next();
    };
    utterance.onend = step;
    utterance.onerror = step;

    try {
      if (window.speechSynthesis.paused) window.speechSynthesis.resume();
      window.speechSynthesis.speak(utterance);
      // Neither event is guaranteed to fire. Without this the whole reading
      // would stop here instead of losing a single sentence.
      guard = setTimeout(step, (text.length / charsPerSec()) * 1000 * 2 + 4000);
    } catch (err) {
      step();
    }
  };

  next();
}

function enqueueNeural(state, clean, engine, voice) {
  const seq = state.nextSeq++;
  state.pending += 1;

  // Offset of this chunk inside the cleaned text, for the progress bar. It is
  // fixed at enqueue time; playback must not advance it again.
  const charOffset = state.processedChars || 0;
  const charLen = clean.length;
  state.processedChars = charOffset + charLen + 1;   // +1: the chunk separator

  requestClip(state, seq, clean, engine, voice, charOffset, charLen, 0);
}

// One retry absorbs the transient failures — a dropped connection, an engine
// still loading its model, a request that lost the server-side lock.
const MAX_CLIP_RETRIES = 1;
const CLIP_RETRY_DELAY_MS = 250;

function requestClip(state, seq, clean, engine, voice, charOffset, charLen, attempt) {
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
      const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));

      // Decode now, not when the previous clip ends: buffering at play time
      // shows up as a gap between one sentence and the next.
      const audio = new Audio();
      audio.preload = 'auto';
      audio.src = url;
      try { audio.load(); } catch (e) {}

      state.queue.set(seq, { url, audio, text: clean, charOffset, charLength: charLen });
      playNextClip(state);
    })
    .catch(err => {
      if (speechStream !== state) return;
      if (err && err.name === 'AbortError') return;

      if (attempt < MAX_CLIP_RETRIES) {
        setTimeout(() => {
          if (speechStream === state) {
            requestClip(state, seq, clean, engine, voice, charOffset, charLen, attempt + 1);
          }
        }, CLIP_RETRY_DELAY_MS);
        return;
      }

      if (!neuralDegraded) {
        neuralDegraded = true;
        reportSpeechIssue(
          'neural-degraded',
          'TTS neurale non disponibile: le prossime letture useranno la voce di sistema',
          err.message,
        );
      }
      // Kept with its text so the slot is read by the system voice rather than
      // passing in silence.
      state.queue.set(seq, { url: null, text: clean, charOffset, charLength: charLen });
      playNextClip(state);
    });
}

/**
 * Cut a sentence into pieces short enough for the engine to finish.
 *
 * Chrome gives up on a long utterance after ~15 s without an error, so a single
 * long sentence would be read halfway and then abandoned. The pieces queue
 * back-to-back, so the split is not audible.
 */
function splitUtterance(text) {
  if (text.length <= MAX_UTTERANCE_CHARS) return [text];

  const parts = [];
  let rest = text;
  while (rest.length > MAX_UTTERANCE_CHARS) {
    const window = rest.slice(0, MAX_UTTERANCE_CHARS);
    // A clause break is the natural place to breathe; a space is the fallback.
    // Cutting inside a word would mispronounce both halves.
    let cut = Math.max(window.lastIndexOf(', '), window.lastIndexOf('; '), window.lastIndexOf(': '));
    if (cut < MAX_UTTERANCE_CHARS * 0.5) cut = window.lastIndexOf(' ');
    if (cut <= 0) cut = MAX_UTTERANCE_CHARS - 1;
    const piece = rest.slice(0, cut + 1).trim();
    if (piece) parts.push(piece);
    rest = rest.slice(cut + 1);
  }
  if (rest.trim()) parts.push(rest.trim());
  return parts;
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
 */
function feedChromeQueue(state) {
  if (speechStream !== state) return;
  if (speechProgressState.paused) return;
  const queue = state.browserQueue;
  if (!queue || queue.length === 0) return;

  // Build a small lead before the first utterance so the audio device stays
  // open from the very first sentence, without waiting on a slow generation.
  if (!state.started && state.chromeActive === 0 && !state.ended && queue.length < MIN_LEAD_CHUNKS) {
    if (state.leadDeadline === undefined) state.leadDeadline = Date.now() + LEAD_DEADLINE_MS;
    if (Date.now() < state.leadDeadline) {
      if (!state.leadTimer) {
        state.leadTimer = setTimeout(() => {
          state.leadTimer = null;
          if (speechStream === state) feedChromeQueue(state);
        }, LEAD_DEADLINE_MS);
      }
      return;
    }
  }

  while (state.chromeActive < MAX_CHROME_QUEUE && queue.length > 0) {
    speakQueueItem(state, queue.shift());
  }
  startWatchdog();
}

/** Hand one queue item to the engine, with full fault bookkeeping. */
function speakQueueItem(state, item) {
  const utterance = buildUtterance(item.text);
  const record = {
    state, item, utterance,
    sawStart: false, startedAt: 0, charIndex: 0, sawBoundary: false,
    finished: false, requeue: false,
  };
  activeUtterances.add(utterance);
  utteranceRecords.set(utterance, record);
  state.inFlight.push(record);                   // ordered: repairs depend on it
  state.chromeActive += 1;

  utterance.onstart = () => {
    record.sawStart = true;
    record.startedAt = Date.now();
    markStarted(state);
    startWatchdog();
    startUtteranceSync(state, item.offset, item.text.length);
    reclaimSkipped(state, record);
  };

  utterance.onboundary = (event) => {
    if (event.charIndex !== undefined && event.charIndex >= 0) {
      record.charIndex = event.charIndex;
      record.sawBoundary = true;
      activeUtteranceStart = Date.now() - (event.charIndex / charsPerSec()) * 1000;
    }
  };

  utterance.onend = () => finishUtterance(record, 'end');
  utterance.onerror = (event) => finishUtterance(record, 'error', event && event.error);

  try {
    // A cancel() can leave the engine paused; speak() would then queue silently.
    if (window.speechSynthesis.paused) window.speechSynthesis.resume();
    window.speechSynthesis.speak(utterance);
    startWatchdog();
  } catch (err) {
    finishUtterance(record, 'error', 'speak-threw');
  }
}

/**
 * Catch an utterance the engine skipped, the moment it skips it.
 *
 * The engine starts utterances in the order it was given them, so one starting
 * while an earlier one has never begun is proof the earlier one was thrown
 * away. Waiting for the watchdog to notice would cost two seconds, by which
 * point the following sentence has been read and the repair arrives out of
 * order; here the loss is caught before the listener is a word into it.
 */
function reclaimSkipped(state, started) {
  const at = state.inFlight.indexOf(started);
  if (at <= 0) return;
  const skipped = state.inFlight.slice(0, at).find(r => !r.finished && !r.sawStart);
  if (skipped) finishUtterance(skipped, 'error', 'skipped');
}

function snapToWordStart(text, index) {
  if (index <= 0) return 0;
  const space = text.lastIndexOf(' ', index);
  return space === -1 ? 0 : space + 1;
}

/**
 * How much of an utterance the engine actually got through, in characters.
 *
 * Boundary events are the direct measurement, but the premium Windows voices
 * often do not emit any, so elapsed time against the calibrated speed stands in
 * for them. Both agree on the case that matters: an utterance that produced no
 * audio at all reads as zero either way.
 */
function spokenCharacters(record) {
  const elapsed = Date.now() - record.startedAt;
  if (record.sawBoundary) return record.charIndex;
  return (elapsed / 1000) * charsPerSec();
}

/**
 * Decide whether a finished utterance really was delivered, and return the part
 * still owed to the listener.
 *
 * Repeating a sentence the listener already heard is as jarring as the hole it
 * repairs, so a repair needs evidence — but silence is the worse of the two
 * failures, so anything short of a delivered utterance is repaired.
 */
function repairableTail(record, reason, errorCode) {
  const { item } = record;
  if (item.retries >= MAX_UTTERANCE_RETRIES) return null;

  // Accepted and then dropped: the engine never spoke a word of it.
  if (!record.sawStart) {
    return {
      text: item.text,
      from: 0,
      code: 'utterance-dropped',
      message: 'Frase mai avviata dal motore vocale, ripetuta',
    };
  }

  if (item.text.length < MIN_JUDGEABLE_UTTERANCE) return null;

  const covered = spokenCharacters(record) / item.text.length;

  // Started and over in no time: the audio never arrived. This is how an online
  // voice fails when it cannot reach its server — no error, just nothing.
  if (covered < NO_AUDIO_COVERAGE) {
    return {
      text: item.text,
      from: 0,
      code: 'utterance-no-audio',
      message: 'Nessun audio prodotto per la frase, ripetuta',
    };
  }

  if (covered >= (isCalibrated() ? COVERAGE_OK : COVERAGE_OK_UNCALIBRATED)) return null;

  // Not every engine reports boundaries at word starts, and the time-based
  // estimate never does. Resuming mid-word would mispronounce it, so a repair
  // always restarts from a whole word.
  const from = snapToWordStart(item.text, Math.floor(spokenCharacters(record)));
  const tail = item.text.slice(from).trim();
  if (tail.length < MIN_REPAIRABLE_TAIL) return null;

  return {
    text: tail,
    from,
    code: reason === 'error' ? `utterance-${errorCode || 'error'}` : 'utterance-truncated',
    message: 'Frase interrotta dal motore vocale, ripresa dal punto di interruzione',
  };
}

/**
 * Put a reading back on track at the point it went wrong.
 *
 * The engine is holding the following utterance already, so a repair cannot
 * simply be pushed onto the front of our queue: it would be heard after the
 * sentence that comes next. Everything still in flight is taken back and
 * re-queued behind the repair, so the answer is never heard out of order.
 */
function requeueFromFault(state, record, tail) {
  const stranded = state.inFlight.filter(other => other !== record && !other.finished);
  stranded.forEach(other => { other.requeue = true; });

  state.browserQueue.unshift(
    { text: tail.text, offset: record.item.offset + tail.from, retries: record.item.retries + 1 },
    ...stranded.map(other => other.item),
  );

  // Their utterances come back as 'interrupted', handled by the requeue flag.
  if (stranded.length > 0) {
    try { window.speechSynthesis.cancel(); } catch (e) {}
  }
  feedChromeQueue(state);
}

function finishUtterance(record, reason, errorCode) {
  if (record.finished) return;
  record.finished = true;

  const { state, utterance } = record;
  stopUtteranceSync();
  activeUtterances.delete(utterance);
  utteranceRecords.delete(utterance);
  const at = state.inFlight.indexOf(record);
  if (at !== -1) state.inFlight.splice(at, 1);
  state.chromeActive = Math.max(0, state.chromeActive - 1);

  if (speechStream !== state) return;              // a newer reading took over

  // Taken back so a repair could go first: it keeps its place in `pending`.
  if (record.requeue) {
    feedChromeQueue(state);
    return;
  }

  // Our own stopSpeech() / pauseSpeech(): the silence is intended.
  if (BENIGN_UTTERANCE_ERRORS.includes(errorCode)) {
    settleChunk(state);
    return;
  }

  const tail = repairableTail(record, reason, errorCode);
  if (tail) {
    reportSpeechIssue(tail.code, tail.message, tail.text.slice(0, 60));
    noteVoiceFault(record);
    requeueFromFault(state, record, tail);
    return;
  }

  // Delivered in full: a trustworthy sample of how fast this voice really is.
  if (reason === 'end' && record.sawStart) {
    recordSpeedSample(record.item.text.length, Date.now() - record.startedAt);
  }

  settleChunk(state);
  feedChromeQueue(state);
}

function enqueueBrowser(state, clean) {
  if (!state.browserQueue) state.browserQueue = [];

  const parts = splitUtterance(clean);
  let offset = state.processedChars || 0;
  parts.forEach(text => {
    state.browserQueue.push({ text, offset, retries: 0 });
    offset += text.length + 1;
  });
  state.processedChars = offset;
  state.pending += parts.length;

  feedChromeQueue(state);
}

function enqueueSpeech(state, rawText) {
  const clean = cleanTextForSpeech(stripFencedCode(state, rawText));
  // Punctuation-only leftovers would be spoken as an audible hiccup.
  if (!clean || !HAS_LETTERS.test(clean)) return;

  // In streaming mode (answer still arriving), accumulate cleaned text so the
  // progress bar can display a meaningful percentage. The trailing space is the
  // separator both engines count in their offsets: without it every chunk
  // shifts the seek position by one more character than the last.
  if (state.isStreaming) {
    state.fullCleanText = (state.fullCleanText || '') + clean + ' ';
  }

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
    // Only cut on real sentence endings: . ! ? … \n
    if (!SENTENCE_ENDINGS.includes(char)) continue;
    // Don't cut the first chunk until we have at least MIN_FIRST_CHUNK chars
    if (first && i < MIN_FIRST_CHUNK) continue;
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
    if (isMidMarkdownLink(candidate)) continue;
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
    browserQueue: [], chromeActive: 0, inFlight: [],
    leadDeadline: undefined, leadTimer: null,
    processedChars: initialOffset,
    fullCleanText: fullCleanText,
    isStreaming: fullCleanText === '' && initialOffset === 0,
    abort: new AbortController(),
    onStart, onEnd,
  };
  setActiveSpeechId(speechId);

  const initialProgress = fullCleanText.length > 0 ? Math.min(1, initialOffset / fullCleanText.length) : 0;
  updateSpeechProgress({
    speechId: speechId,
    fullText: fullCleanText,
    charIndex: initialOffset,
    charLength: 5,
    progress: initialProgress,
    paused: false,
    isSpeaking: true,
  });

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

  // The lead buffer was waiting for text that is no longer coming.
  if (state.leadTimer) { clearTimeout(state.leadTimer); state.leadTimer = null; }
  feedChromeQueue(state);

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

  stopWatchdog();
  stopUtteranceSync();
  activeUtterances.clear();
  utteranceRecords.forEach(record => { record.finished = true; });
  utteranceRecords.clear();

  const state = speechStream;
  speechStream = null;

  if (window.speechSynthesis) window.speechSynthesis.cancel();

  if (state) {
    state.busy = false;
    state.chromeActive = 0;
    state.inFlight = [];
    if (state.leadTimer) { clearTimeout(state.leadTimer); state.leadTimer = null; }
    if (state.browserQueue) state.browserQueue = [];
    try { state.abort.abort(); } catch (e) {}
    if (state.audio) {
      state.audio.onended = state.audio.onerror = null;
      state.audio.pause();
      state.audio = null;
    }
    state.queue.forEach(entry => {
      if (entry && entry.url) URL.revokeObjectURL(entry.url);
    });
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
