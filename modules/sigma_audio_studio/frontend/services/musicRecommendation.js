// ==============================================================================
// musicRecommendation.js — Multi-Engine Music Database & Smart Taste Profiler
// Multi-Broadcaster Support (Mediaset, Rai, 24 ORE, Kiss Kiss, Global UK, Indie, Sigma DSP)
// ==============================================================================

export const BROADCASTERS = [
  { id: 'all', name: 'Tutti gli Enti', icon: '🌐', tag: 'ALL NETWORKS', color: '#00f2fe' },
  { id: 'mediaset', name: 'Mediaset / United Radio', icon: '📻', tag: 'VIRGIN / 105 / RMC / R101', color: '#38bdf8' },
  { id: 'rai', name: 'Rai Radio (Servizio Pubblico)', icon: '🏛️', tag: 'RAI RADIO 1 / 2 / CLASSICA', color: '#818cf8' },
  { id: 'sole24ore', name: 'Gruppo 24 ORE', icon: '📰', tag: 'RADIO 24 IL SOLE 24 ORE', color: '#10b981' },
  { id: 'kisskiss', name: 'Kiss Kiss Network', icon: '⭐', tag: 'RADIO KISS KISS FM', color: '#ec4899' },
  { id: 'uk_global', name: 'Global UK Broadcasting', icon: '🇬🇧', tag: 'CLASSIC FM LONDRA', color: '#f59e0b' },
  { id: 'independent', name: 'Lofi Girl & Web Stream Labs', icon: '🎧', tag: 'YOUTUBE & WEBRADIO', color: '#14b8a6' },
  { id: 'sigma_dsp', name: 'Sigma Audio DSP', icon: '⚡', tag: 'SYNTH LOCALE 432HZ', color: '#c084fc' }
];

export const GENRES = [
  {
    id: 'radio_fm',
    name: 'Radio FM Live',
    tag: 'FM BROADCAST',
    color: '#00f2fe',
    icon: '📻',
    description: 'Dirette radiofoniche FM nazionali in tempo reale (Virgin, 105, RMC, Rai, Radio 24, R101, Kiss Kiss)'
  },
  {
    id: 'lofi',
    name: 'Lo-Fi Beats',
    tag: 'STUDY & RELAX',
    color: '#00d2ff',
    icon: '🎧',
    description: 'Beats morbidi, fruscio di vinile e atmosfere rilassanti per studio e lavoro'
  },
  {
    id: 'synthwave',
    name: 'Synthwave & Cyber',
    tag: 'CODING & FLOW',
    color: '#bc8cff',
    icon: '🌆',
    description: 'Sintetizzatori analogici, ritmi anni 80 e mood futuristico cyberpunk'
  },
  {
    id: 'rock',
    name: 'Rock & Alternative',
    tag: 'HIGH ENERGY',
    color: '#ef4444',
    icon: '🎸',
    description: 'Chitarre elettriche, riff energici, batteria solida e rock leggendario'
  },
  {
    id: 'metal',
    name: 'Metal & Hard Rock',
    tag: 'INTENSE POWER',
    color: '#dc2626',
    icon: '⚡',
    description: 'Chitarre distorte, riff pesanti e adrenalina pura per sprint ad alta intensità'
  },
  {
    id: 'jazz',
    name: 'Jazz & Lounge',
    tag: 'CAFE VIBES',
    color: '#f97316',
    icon: '🎷',
    description: 'Sassofono, pianoforte bebop, percussioni calde e atmosfere da club'
  },
  {
    id: 'classical',
    name: 'Piano & Classica',
    tag: 'CREATIVITY',
    color: '#facc15',
    icon: '🎹',
    description: 'Melodie pianistiche calme, quartetti d\'archi e armonie neoclassiche'
  },
  {
    id: 'electronic',
    name: 'Electronic & Dance',
    tag: 'FLOW STATE',
    color: '#ec4899',
    icon: '🎛️',
    description: 'Techno melodica, Dance 90, House beats e ritmi costanti per la programmazione'
  },
  {
    id: 'ambient',
    name: 'Ambient & Deep Focus',
    tag: 'DEEP WORK',
    color: '#4ade80',
    icon: '🌌',
    description: 'Droni spaziali, frequenze binaurali 432Hz e paesaggi sonori immersivi'
  },
  {
    id: 'chillhop',
    name: 'Chillhop & HipHop',
    tag: 'GROOVE',
    color: '#14b8a6',
    icon: '☕',
    description: 'Campioni di vinile, linee di basso calde, hiphop rilassato e beat da coffee shop'
  },
  {
    id: 'cinematic',
    name: 'Colonne Sonore & Epic',
    tag: 'SOUNDTRACK',
    color: '#f59e0b',
    icon: '🎬',
    description: 'Capolavori orchestrali di Hans Zimmer, Ennio Morricone, John Williams per pura ispirazione'
  },
  {
    id: 'gaming',
    name: 'Gaming & ChipTune',
    tag: 'GAME ON',
    color: '#8b5cf6',
    icon: '🎮',
    description: 'Temi leggendari da Doom, Skyrim, The Witcher, Undertale per sprint ad alta concentrazione'
  }
];

export const INSTRUMENTS = [
  { id: 'piano', name: 'Pianoforte', icon: '🎹', color: '#facc15' },
  { id: 'guitar', name: 'Chitarra', icon: '🎸', color: '#ef4444' },
  { id: 'sax', name: 'Sassofono', icon: '🎷', color: '#f97316' },
  { id: 'synth', name: 'Sintetizzatore', icon: '🎛️', color: '#bc8cff' },
  { id: 'drums', name: 'Batteria & Beat', icon: '🥁', color: '#00d2ff' },
  { id: 'strings', name: 'Archi & Violino', icon: '🎻', color: '#ec4899' },
  { id: 'trumpet', name: 'Tromba & Ottoni', icon: '🎺', color: '#eab308' },
  { id: 'bass', name: 'Basso Elettrico', icon: '🎸', color: '#10b981' },
  { id: 'flute', name: 'Flauto & Fiati', icon: '🪈', color: '#06b6d4' },
  { id: 'vinyl', name: 'Vinile & Scratches', icon: '📻', color: '#8b5cf6' }
];

export const MOODS = [
  { id: 'coding', name: 'Coding Sprint', icon: '💻', color: '#00d2ff' },
  { id: 'focus', name: 'Deep Focus', icon: '🧠', color: '#4ade80' },
  { id: 'relax', name: 'Relax & Chill', icon: '☕', color: '#f97316' },
  { id: 'energy', name: 'Alta Energia', icon: '⚡', color: '#ef4444' },
  { id: 'night', name: 'Sessione Notturna', icon: '🌙', color: '#bc8cff' },
  { id: 'meditation', name: 'Zen & Meditazione', icon: '🧘', color: '#14b8a6' }
];

// Rich, resilient default catalog with Verified Broadcasters, Live FM & Iconic Masterpieces
export const DEFAULT_TRACKS = [
  // ==============================================================================
  // 1. 📻 RADIO FM LIVE (DIRETTE BROADCAST NAZIONALI & INTERNAZIONALI)
  // ==============================================================================
  {
    id: 'fm-virgin-1',
    title: 'Virgin Radio Italia FM',
    artist: 'Virgin Radio Live (Style Rock)',
    broadcaster: 'mediaset',
    broadcasterName: 'Mediaset Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 104.5',
    duration: 0,
    isLive: true,
    url: 'http://icecast.unitedradio.it/Virgin.mp3',
    cover: 'linear-gradient(135deg, #18181b 0%, #3f3f46 50%, #dc2626 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['fm', 'radio', 'virgin', 'rock', 'guitar', 'live', 'mediaset']
  },
  {
    id: 'fm-virgin-classics',
    title: 'Virgin Radio Classic Rock',
    artist: 'Virgin Classic Rock Legends',
    broadcaster: 'mediaset',
    broadcasterName: 'Mediaset Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM Rock',
    duration: 0,
    isLive: true,
    url: 'http://icy.unitedradio.it/VirginRockClassics.mp3',
    cover: 'linear-gradient(135deg, #450a0a 0%, #7f1d1d 50%, #b91c1c 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['fm', 'radio', 'classics', '70s', '80s', 'rock', 'mediaset']
  },
  {
    id: 'fm-105-1',
    title: 'Radio 105 Network FM',
    artist: 'Radio 105 FM Live (Hits & Urban)',
    broadcaster: 'mediaset',
    broadcasterName: 'Mediaset Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 105.0',
    duration: 0,
    isLive: true,
    url: 'http://icecast.unitedradio.it/Radio105.mp3',
    cover: 'linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #3b82f6 100%)',
    instruments: ['drums', 'synth', 'vinyl'],
    moods: ['energy', 'relax'],
    tags: ['fm', 'radio', '105', 'hits', 'pop', 'live', 'mediaset']
  },
  {
    id: 'fm-rmc-1',
    title: 'Radio Monte Carlo (RMC) FM',
    artist: 'RMC Live (Musica di Gran Classe)',
    broadcaster: 'mediaset',
    broadcasterName: 'Mediaset Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 105.5',
    duration: 0,
    isLive: true,
    url: 'http://icecast.unitedradio.it/RMC.mp3',
    cover: 'linear-gradient(135deg, #451a03 0%, #78350f 50%, #d97706 100%)',
    instruments: ['sax', 'piano', 'bass'],
    moods: ['relax', 'focus', 'night'],
    tags: ['fm', 'radio', 'rmc', 'lounge', 'soul', 'jazz', 'mediaset']
  },
  {
    id: 'fm-rmc-buddha',
    title: 'RMC Buddha-Bar Lounge',
    artist: 'Radio Monte Carlo Deep Lounge',
    broadcaster: 'mediaset',
    broadcasterName: 'Mediaset Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'Web Lounge',
    duration: 0,
    isLive: true,
    url: 'http://edge.radiomontecarlo.net/rmcweb002',
    cover: 'linear-gradient(135deg, #1e1b4b 0%, #4338ca 50%, #818cf8 100%)',
    instruments: ['synth', 'drums', 'flute'],
    moods: ['focus', 'relax', 'night'],
    tags: ['fm', 'rmc', 'buddhabar', 'ambient', 'lounge', 'oriental', 'mediaset']
  },
  {
    id: 'fm-r101-1',
    title: 'R101 FM',
    artist: 'R101 Live (Enjoy the Music)',
    broadcaster: 'mediaset',
    broadcasterName: 'Mediaset Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 101.0',
    duration: 0,
    isLive: true,
    url: 'http://icecast.unitedradio.it/r101',
    cover: 'linear-gradient(135deg, #701a75 0%, #a21caf 50%, #e879f9 100%)',
    instruments: ['drums', 'synth', 'guitar'],
    moods: ['energy', 'relax'],
    tags: ['fm', 'radio', 'r101', 'hits', '80s', '90s', 'live', 'mediaset']
  },
  {
    id: 'fm-rai-1',
    title: 'Rai Radio 1 FM',
    artist: 'Rai Radio 1 Live (Giornale Radio & Informazione)',
    broadcaster: 'rai',
    broadcasterName: 'Rai Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 89.7',
    duration: 0,
    isLive: true,
    url: 'http://icestreaming.rai.it/1.mp3',
    cover: 'linear-gradient(135deg, #0c4a6e 0%, #0284c7 50%, #38bdf8 100%)',
    instruments: ['synth'],
    moods: ['focus', 'coding'],
    tags: ['fm', 'radio', 'rai', 'radio1', 'news', 'live']
  },
  {
    id: 'fm-rai-2',
    title: 'Rai Radio 2 FM',
    artist: 'Rai Radio 2 Live (Intrattenimento & Musica)',
    broadcaster: 'rai',
    broadcasterName: 'Rai Radio',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 91.7',
    duration: 0,
    isLive: true,
    url: 'http://icestreaming.rai.it/2.mp3',
    cover: 'linear-gradient(135deg, #1e1b4b 0%, #3730a3 50%, #6366f1 100%)',
    instruments: ['drums', 'guitar', 'piano'],
    moods: ['relax', 'energy'],
    tags: ['fm', 'radio', 'rai', 'radio2', 'pop', 'live']
  },
  {
    id: 'fm-radio24-1',
    title: 'Radio 24 Il Sole 24 Ore FM',
    artist: 'Radio 24 Live (News, Economia & Approfondimento)',
    broadcaster: 'sole24ore',
    broadcasterName: 'Gruppo 24 ORE',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 104.8',
    duration: 0,
    isLive: true,
    url: 'http://shoutcast2.radio24.it:8000/;',
    cover: 'linear-gradient(135deg, #022c22 0%, #065f46 50%, #10b981 100%)',
    instruments: ['synth'],
    moods: ['focus', 'coding'],
    tags: ['fm', 'radio', 'radio24', 'news', 'talk', 'live', 'sole24ore']
  },
  {
    id: 'fm-kisskiss-1',
    title: 'Radio Kiss Kiss FM',
    artist: 'Radio Kiss Kiss Live (Play Everywhere)',
    broadcaster: 'kisskiss',
    broadcasterName: 'Kiss Kiss Network',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 97.0',
    duration: 0,
    isLive: true,
    url: 'http://wma08.fluidstream.net:4610/',
    cover: 'linear-gradient(135deg, #831843 0%, #be185d 50%, #f472b6 100%)',
    instruments: ['drums', 'synth'],
    moods: ['energy', 'relax'],
    tags: ['fm', 'radio', 'kisskiss', 'hits', 'pop']
  },
  {
    id: 'fm-classic-uk',
    title: 'Classic FM UK (Londra)',
    artist: 'Classic FM London Live',
    broadcaster: 'uk_global',
    broadcasterName: 'Global UK',
    genre: 'radio_fm',
    engine: 'radio',
    frequency: 'FM 100.0',
    duration: 0,
    isLive: true,
    url: 'https://media-ssl.musicradio.com/ClassicFM',
    cover: 'linear-gradient(135deg, #1c1917 0%, #44403c 50%, #78716c 100%)',
    instruments: ['piano', 'strings', 'flute'],
    moods: ['focus', 'meditation'],
    tags: ['fm', 'radio', 'classicfm', 'london', 'orchestra', 'uk']
  },

  // ==============================================================================
  // 2. 🎸 ROCK & ALTERNATIVE (BRANI ICONICI & MASTERPIECES)
  // ==============================================================================
  {
    id: 'rock-queen-bohemian',
    title: 'Bohemian Rhapsody',
    artist: 'Queen',
    broadcaster: 'independent',
    broadcasterName: 'Rock Classics',
    genre: 'rock',
    engine: 'youtube',
    youtubeId: 'fJ9rUzIMcZQ',
    url: 'https://www.youtube.com/watch?v=fJ9rUzIMcZQ',
    duration: 359,
    cover: 'linear-gradient(135deg, #450a0a 0%, #991b1b 50%, #ef4444 100%)',
    instruments: ['piano', 'guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['rock', 'queen', 'bohemian-rhapsody', 'legend', '70s']
  },
  {
    id: 'rock-pinkfloyd-numb',
    title: 'Comfortably Numb',
    artist: 'Pink Floyd',
    broadcaster: 'independent',
    broadcasterName: 'Progressive Rock',
    genre: 'rock',
    engine: 'youtube',
    youtubeId: '_FrOQC-zSog',
    url: 'https://www.youtube.com/watch?v=_FrOQC-zSog',
    duration: 382,
    cover: 'linear-gradient(135deg, #18181b 0%, #27272a 50%, #dc2626 100%)',
    instruments: ['guitar', 'synth', 'bass', 'drums'],
    moods: ['focus', 'night', 'coding'],
    tags: ['rock', 'pinkfloyd', 'solo', 'guitar', 'legend']
  },
  {
    id: 'rock-acdc-backinblack',
    title: 'Back In Black',
    artist: 'AC/DC',
    broadcaster: 'independent',
    broadcasterName: 'Hard Rock HQ',
    genre: 'rock',
    engine: 'youtube',
    youtubeId: 'pAgnJDJN4VA',
    url: 'https://www.youtube.com/watch?v=pAgnJDJN4VA',
    duration: 255,
    cover: 'linear-gradient(135deg, #09090b 0%, #1c1917 50%, #b91c1c 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['rock', 'acdc', 'hardrock', 'riff', 'power']
  },
  {
    id: 'rock-ledzep-stairway',
    title: 'Stairway to Heaven',
    artist: 'Led Zeppelin',
    broadcaster: 'independent',
    broadcasterName: 'Classic Rock Icons',
    genre: 'rock',
    engine: 'youtube',
    youtubeId: 'QkF3oxziUI4',
    url: 'https://www.youtube.com/watch?v=QkF3oxziUI4',
    duration: 482,
    cover: 'linear-gradient(135deg, #2e1065 0%, #581c87 50%, #f59e0b 100%)',
    instruments: ['guitar', 'flute', 'drums'],
    moods: ['focus', 'relax', 'night'],
    tags: ['rock', 'ledzeppelin', 'acoustic', 'electric', 'masterpiece']
  },
  {
    id: 'rock-direstraits-sultans',
    title: 'Sultans of Swing',
    artist: 'Dire Straits (Mark Knopfler)',
    broadcaster: 'independent',
    broadcasterName: 'Classic Rock',
    genre: 'rock',
    engine: 'youtube',
    youtubeId: '0fAQH8DrBU4',
    url: 'https://www.youtube.com/watch?v=0fAQH8DrBU4',
    duration: 348,
    cover: 'linear-gradient(135deg, #042f2e 0%, #115e59 50%, #14b8a6 100%)',
    instruments: ['guitar', 'bass', 'drums'],
    moods: ['coding', 'focus', 'relax'],
    tags: ['rock', 'direstraits', 'knopfler', 'guitar', 'groove']
  },
  {
    id: 'rock-nirvana-teen',
    title: 'Smells Like Teen Spirit',
    artist: 'Nirvana',
    broadcaster: 'independent',
    broadcasterName: 'Grunge Vault',
    genre: 'rock',
    engine: 'youtube',
    youtubeId: 'hTWKbfoikeg',
    url: 'https://www.youtube.com/watch?v=hTWKbfoikeg',
    duration: 301,
    cover: 'linear-gradient(135deg, #172554 0%, #1e40af 50%, #60a5fa 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['rock', 'grunge', 'nirvana', '90s', 'alternative']
  },
  {
    id: 'rock-eagles-hotelcalifornia',
    title: 'Hotel California',
    artist: 'Eagles',
    broadcaster: 'independent',
    broadcasterName: 'Classic Rock',
    genre: 'rock',
    engine: 'youtube',
    youtubeId: '09839DpTctU',
    url: 'https://www.youtube.com/watch?v=09839DpTctU',
    duration: 391,
    cover: 'linear-gradient(135deg, #451a03 0%, #9a3412 50%, #ea580c 100%)',
    instruments: ['guitar', 'bass', 'drums'],
    moods: ['relax', 'focus', 'night'],
    tags: ['rock', 'eagles', 'solo', 'california', '70s']
  },

  // ==============================================================================
  // 3. ⚡ METAL & HARD ROCK (BRANI AD ALTA ENERGIA & POWER RIFFS)
  // ==============================================================================
  {
    id: 'metal-metallica-puppets',
    title: 'Master of Puppets',
    artist: 'Metallica',
    broadcaster: 'independent',
    broadcasterName: 'Thrash Metal Legends',
    genre: 'metal',
    engine: 'youtube',
    youtubeId: 'xnKhsTXoKmg',
    url: 'https://www.youtube.com/watch?v=xnKhsTXoKmg',
    duration: 515,
    cover: 'linear-gradient(135deg, #450a0a 0%, #18181b 50%, #dc2626 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['metal', 'metallica', 'thrash', 'speed', 'riff']
  },
  {
    id: 'metal-ironmaiden-trooper',
    title: 'The Trooper',
    artist: 'Iron Maiden',
    broadcaster: 'independent',
    broadcasterName: 'Heavy Metal Hall',
    genre: 'metal',
    engine: 'youtube',
    youtubeId: 'X4bgXH3sJ2Q',
    url: 'https://www.youtube.com/watch?v=X4bgXH3sJ2Q',
    duration: 252,
    cover: 'linear-gradient(135deg, #1c1917 0%, #78350f 50%, #b45309 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['metal', 'ironmaiden', 'heavy', 'trooper', 'gallop']
  },
  {
    id: 'metal-blacksabbath-paranoid',
    title: 'Paranoid',
    artist: 'Black Sabbath',
    broadcaster: 'independent',
    broadcasterName: 'Heavy Metal Origins',
    genre: 'metal',
    engine: 'youtube',
    youtubeId: '0qanF-91aJo',
    url: 'https://www.youtube.com/watch?v=0qanF-91aJo',
    duration: 168,
    cover: 'linear-gradient(135deg, #18181b 0%, #3f3f46 50%, #a855f7 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['metal', 'blacksabbath', 'heavy', 'ozzy', 'riff']
  },
  {
    id: 'metal-soad-toxicity',
    title: 'Toxicity',
    artist: 'System of a Down',
    broadcaster: 'independent',
    broadcasterName: 'Alt Metal Vault',
    genre: 'metal',
    engine: 'youtube',
    youtubeId: 'iywaBOMvYLI',
    url: 'https://www.youtube.com/watch?v=iywaBOMvYLI',
    duration: 219,
    cover: 'linear-gradient(135deg, #312e81 0%, #1e1b4b 50%, #ec4899 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['metal', 'soad', 'toxicity', 'alternative', '2000s']
  },
  {
    id: 'metal-rammstein-duhast',
    title: 'Du Hast',
    artist: 'Rammstein',
    broadcaster: 'independent',
    broadcasterName: 'Industrial Metal',
    genre: 'metal',
    engine: 'youtube',
    youtubeId: 'W3q8Od5qJio',
    url: 'https://www.youtube.com/watch?v=W3q8Od5qJio',
    duration: 235,
    cover: 'linear-gradient(135deg, #18181b 0%, #7f1d1d 50%, #f97316 100%)',
    instruments: ['synth', 'guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['metal', 'rammstein', 'industrial', 'german', 'power']
  },
  {
    id: 'metal-judaspriest-painkiller',
    title: 'Painkiller',
    artist: 'Judas Priest',
    broadcaster: 'independent',
    broadcasterName: 'Speed Metal',
    genre: 'metal',
    engine: 'youtube',
    youtubeId: 'WS6-vI70oc0',
    url: 'https://www.youtube.com/watch?v=WS6-vI70oc0',
    duration: 365,
    cover: 'linear-gradient(135deg, #09090b 0%, #1e1b4b 50%, #6366f1 100%)',
    instruments: ['guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['metal', 'judaspriest', 'speed', 'drums', 'solo']
  },

  // ==============================================================================
  // 4. 🌆 SYNTHWAVE & CYBERPUNK (ANALOG VIBES, CODING FLOW & RETRO)
  // ==============================================================================
  {
    id: 'synth-kavinsky-nightcall',
    title: 'Nightcall (Drive Soundtrack)',
    artist: 'Kavinsky',
    broadcaster: 'independent',
    broadcasterName: 'Synthwave & Outrun',
    genre: 'synthwave',
    engine: 'youtube',
    youtubeId: 'MV_3Dpw-BRY',
    url: 'https://www.youtube.com/watch?v=MV_3Dpw-BRY',
    duration: 259,
    cover: 'linear-gradient(135deg, #701a75 0%, #be185d 50%, #00f2fe 100%)',
    instruments: ['synth', 'drums', 'vocoder'],
    moods: ['coding', 'night', 'focus'],
    tags: ['synthwave', 'kavinsky', 'drive', 'retrowave', 'night']
  },
  {
    id: 'synth-midnight-sunset',
    title: 'Sunset',
    artist: 'The Midnight',
    broadcaster: 'independent',
    broadcasterName: 'Synthpop & Wave',
    genre: 'synthwave',
    engine: 'youtube',
    youtubeId: '61A5Pz2iV8k',
    url: 'https://www.youtube.com/watch?v=61A5Pz2iV8k',
    duration: 326,
    cover: 'linear-gradient(135deg, #831843 0%, #c026d3 50%, #38bdf8 100%)',
    instruments: ['synth', 'sax', 'drums'],
    moods: ['coding', 'relax', 'night'],
    tags: ['synthwave', 'themidnight', 'sunset', 'sax', 'summer']
  },
  {
    id: 'synth-home-resonance',
    title: 'Resonance',
    artist: 'HOME',
    broadcaster: 'independent',
    broadcasterName: 'Chillwave & Nostalgia',
    genre: 'synthwave',
    engine: 'youtube',
    youtubeId: '8GW6sLrK40k',
    url: 'https://www.youtube.com/watch?v=8GW6sLrK40k',
    duration: 212,
    cover: 'linear-gradient(135deg, #1e1b4b 0%, #4338ca 50%, #06b6d4 100%)',
    instruments: ['synth', 'drums', 'bass'],
    moods: ['focus', 'coding', 'meditation'],
    tags: ['synthwave', 'home', 'resonance', 'nostalgia', 'chill']
  },
  {
    id: 'synth-carpenter-turbokiller',
    title: 'Turbo Killer',
    artist: 'Carpenter Brut',
    broadcaster: 'independent',
    broadcasterName: 'Darksynth & Cyber',
    genre: 'synthwave',
    engine: 'youtube',
    youtubeId: 'er416XiUp4g',
    url: 'https://www.youtube.com/watch?v=er416XiUp4g',
    duration: 208,
    cover: 'linear-gradient(135deg, #18181b 0%, #450a0a 50%, #dc2626 100%)',
    instruments: ['synth', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['synthwave', 'carpenterbrut', 'darksynth', 'cyberpunk', 'fast']
  },
  {
    id: 'synth-gunship-technoir',
    title: 'Tech Noir',
    artist: 'GUNSHIP',
    broadcaster: 'independent',
    broadcasterName: 'Cinematic Synthwave',
    genre: 'synthwave',
    engine: 'youtube',
    youtubeId: '-EDmtbSyBv4',
    url: 'https://www.youtube.com/watch?v=-EDmtbSyBv4',
    duration: 297,
    cover: 'linear-gradient(135deg, #312e81 0%, #6d28d9 50%, #ec4899 100%)',
    instruments: ['synth', 'guitar', 'drums'],
    moods: ['coding', 'night', 'focus'],
    tags: ['synthwave', 'gunship', 'technoir', 'cyberpunk', '80s']
  },

  // ==============================================================================
  // 5. 🎧 LO-FI BEATS & CHILL (STUDIO, RELAX & CODING FLOW)
  // ==============================================================================
  {
    id: 'lofi-lofigirl-beats',
    title: 'Lofi Hip Hop Radio (Beats to Relax/Study to)',
    artist: 'Lofi Girl',
    broadcaster: 'independent',
    broadcasterName: 'Lofi Girl Live',
    genre: 'lofi',
    engine: 'youtube',
    youtubeId: 'jfKfPfyJRdk',
    url: 'https://www.youtube.com/watch?v=jfKfPfyJRdk',
    duration: 0,
    isLive: true,
    cover: 'linear-gradient(135deg, #1e1b4b 0%, #4338ca 100%)',
    instruments: ['piano', 'drums', 'vinyl'],
    moods: ['coding', 'focus', 'relax'],
    tags: ['lofi', 'lofigirl', 'study', 'relax', 'beats']
  },
  {
    id: 'lofi-chillhop-spring',
    title: 'Chillhop Radio - Jazzy & Lofi Beats',
    artist: 'Chillhop Music',
    broadcaster: 'independent',
    broadcasterName: 'Chillhop Live',
    genre: 'lofi',
    engine: 'youtube',
    youtubeId: '5yx6BWlEVcY',
    url: 'https://www.youtube.com/watch?v=5yx6BWlEVcY',
    duration: 0,
    isLive: true,
    cover: 'linear-gradient(135deg, #022c22 0%, #0d9488 50%, #5eead4 100%)',
    instruments: ['piano', 'sax', 'drums', 'vinyl'],
    moods: ['relax', 'focus', 'coding'],
    tags: ['lofi', 'chillhop', 'jazzy', 'raccoon', 'beats']
  },
  {
    id: 'lofi-kupla-blue',
    title: 'Kingdom in Blue',
    artist: 'Kupla',
    broadcaster: 'independent',
    broadcasterName: 'Lofi Records',
    genre: 'lofi',
    engine: 'youtube',
    youtubeId: 'Qc7_zRjH808',
    url: 'https://www.youtube.com/watch?v=Qc7_zRjH808',
    duration: 178,
    cover: 'linear-gradient(135deg, #0c4a6e 0%, #0284c7 50%, #38bdf8 100%)',
    instruments: ['piano', 'flute', 'drums'],
    moods: ['focus', 'relax', 'meditation'],
    tags: ['lofi', 'kupla', 'piano', 'calm', 'study']
  },

  // ==============================================================================
  // 6. 🎷 JAZZ & BEBOP LOUNGE (CAPOLAVORI TIMELESS)
  // ==============================================================================
  {
    id: 'jazz-miles-sowhat',
    title: 'So What (Kind of Blue)',
    artist: 'Miles Davis',
    broadcaster: 'independent',
    broadcasterName: 'Modal Jazz Classic',
    genre: 'jazz',
    engine: 'youtube',
    youtubeId: 'zqNTltOGh5c',
    url: 'https://www.youtube.com/watch?v=zqNTltOGh5c',
    duration: 562,
    cover: 'linear-gradient(135deg, #172554 0%, #1e3a8a 50%, #3b82f6 100%)',
    instruments: ['trumpet', 'sax', 'piano', 'bass', 'drums'],
    moods: ['focus', 'relax', 'night'],
    tags: ['jazz', 'milesdavis', 'kindofblue', 'trumpet', 'masterpiece']
  },
  {
    id: 'jazz-brubeck-takefive',
    title: 'Take Five (Time Out)',
    artist: 'The Dave Brubeck Quartet',
    broadcaster: 'independent',
    broadcasterName: 'Cool Jazz Hall',
    genre: 'jazz',
    engine: 'youtube',
    youtubeId: 'vmDDOFXSgAs',
    url: 'https://www.youtube.com/watch?v=vmDDOFXSgAs',
    duration: 324,
    cover: 'linear-gradient(135deg, #451a03 0%, #9a3412 50%, #f59e0b 100%)',
    instruments: ['sax', 'piano', 'drums', 'bass'],
    moods: ['coding', 'focus', 'relax'],
    tags: ['jazz', 'davebrubeck', 'takefive', 'sax', '5/4']
  },
  {
    id: 'jazz-coltrane-giantsteps',
    title: 'Giant Steps',
    artist: 'John Coltrane',
    broadcaster: 'independent',
    broadcasterName: 'Hard Bop Master',
    genre: 'jazz',
    engine: 'youtube',
    youtubeId: '30FTr6G53VU',
    url: 'https://www.youtube.com/watch?v=30FTr6G53VU',
    duration: 283,
    cover: 'linear-gradient(135deg, #2e1065 0%, #6b21a8 50%, #c084fc 100%)',
    instruments: ['sax', 'piano', 'bass', 'drums'],
    moods: ['energy', 'focus', 'coding'],
    tags: ['jazz', 'johncoltrane', 'sax', 'bebop', 'theory']
  },
  {
    id: 'jazz-chetbaker-fallinlove',
    title: 'I Fall in Love Too Easily',
    artist: 'Chet Baker',
    broadcaster: 'independent',
    broadcasterName: 'Cool Jazz & Vocals',
    genre: 'jazz',
    engine: 'youtube',
    youtubeId: '3zrSoHgPDe0',
    url: 'https://www.youtube.com/watch?v=3zrSoHgPDe0',
    duration: 201,
    cover: 'linear-gradient(135deg, #18181b 0%, #312e81 50%, #818cf8 100%)',
    instruments: ['trumpet', 'piano', 'bass'],
    moods: ['night', 'relax', 'meditation'],
    tags: ['jazz', 'chetbaker', 'trumpet', 'vocal', 'melancholy']
  },
  {
    id: 'jazz-billevans-autumn',
    title: 'Autumn Leaves (Portrait in Jazz)',
    artist: 'Bill Evans Trio',
    broadcaster: 'independent',
    broadcasterName: 'Piano Jazz Lounge',
    genre: 'jazz',
    engine: 'youtube',
    youtubeId: 'r-Z8KuwI7Gc',
    url: 'https://www.youtube.com/watch?v=r-Z8KuwI7Gc',
    duration: 325,
    cover: 'linear-gradient(135deg, #451a03 0%, #78350f 50%, #d97706 100%)',
    instruments: ['piano', 'bass', 'drums'],
    moods: ['relax', 'focus', 'night'],
    tags: ['jazz', 'billevans', 'piano', 'autumnleaves', 'trio']
  },

  // ==============================================================================
  // 7. 🎹 PIANO & CLASSICA (CAPOLAVORI SINFONICI E PIANISTICI IMMORTALI)
  // ==============================================================================
  {
    id: 'class-beethoven-ode',
    title: 'Symphony No. 9 in D Minor (Ode to Joy)',
    artist: 'Ludwig van Beethoven',
    broadcaster: 'independent',
    broadcasterName: 'Symphonic Masterworks',
    genre: 'classical',
    engine: 'youtube',
    youtubeId: 'IInG5nY_wrU',
    url: 'https://www.youtube.com/watch?v=IInG5nY_wrU',
    duration: 620,
    cover: 'linear-gradient(135deg, #451a03 0%, #b45309 50%, #fbbf24 100%)',
    instruments: ['strings', 'trumpet', 'flute', 'drums'],
    moods: ['energy', 'focus', 'coding'],
    tags: ['classical', 'beethoven', 'symphony', 'odetojoy', 'orchestra']
  },
  {
    id: 'class-mozart-lacrimosa',
    title: 'Requiem in D Minor: Lacrimosa',
    artist: 'Wolfgang Amadeus Mozart',
    broadcaster: 'independent',
    broadcasterName: 'Sacred Classics',
    genre: 'classical',
    engine: 'youtube',
    youtubeId: 'k1-TrAvp_xs',
    url: 'https://www.youtube.com/watch?v=k1-TrAvp_xs',
    duration: 202,
    cover: 'linear-gradient(135deg, #18181b 0%, #3f3f46 50%, #a1a1aa 100%)',
    instruments: ['strings', 'flute'],
    moods: ['focus', 'meditation', 'night'],
    tags: ['classical', 'mozart', 'requiem', 'lacrimosa', 'choir']
  },
  {
    id: 'class-vivaldi-winter',
    title: 'The Four Seasons: Winter (L\'Inverno)',
    artist: 'Antonio Vivaldi',
    broadcaster: 'independent',
    broadcasterName: 'Baroque Masterpieces',
    genre: 'classical',
    engine: 'youtube',
    youtubeId: 'TZCfydWF48c',
    url: 'https://www.youtube.com/watch?v=TZCfydWF48c',
    duration: 540,
    cover: 'linear-gradient(135deg, #0c4a6e 0%, #0369a1 50%, #38bdf8 100%)',
    instruments: ['strings'],
    moods: ['energy', 'focus', 'coding'],
    tags: ['classical', 'vivaldi', 'fourseasons', 'winter', 'violin']
  },
  {
    id: 'class-chopin-nocturne',
    title: 'Nocturne in E-Flat Major Op. 9 No. 2',
    artist: 'Frédéric Chopin',
    broadcaster: 'independent',
    broadcasterName: 'Romantic Piano Solo',
    genre: 'classical',
    engine: 'youtube',
    youtubeId: '9E6b3swbnWg',
    url: 'https://www.youtube.com/watch?v=9E6b3swbnWg',
    duration: 275,
    cover: 'linear-gradient(135deg, #1e1b4b 0%, #3730a3 50%, #c084fc 100%)',
    instruments: ['piano'],
    moods: ['relax', 'night', 'meditation'],
    tags: ['classical', 'chopin', 'nocturne', 'piano', 'romantic']
  },
  {
    id: 'class-bach-cellosuite',
    title: 'Cello Suite No. 1 in G Major: Prelude',
    artist: 'Johann Sebastian Bach (Yo-Yo Ma)',
    broadcaster: 'independent',
    broadcasterName: 'Baroque Strings',
    genre: 'classical',
    engine: 'youtube',
    youtubeId: '1prweT95U44',
    url: 'https://www.youtube.com/watch?v=1prweT95U44',
    duration: 151,
    cover: 'linear-gradient(135deg, #451a03 0%, #78350f 50%, #d97706 100%)',
    instruments: ['strings'],
    moods: ['focus', 'coding', 'meditation'],
    tags: ['classical', 'bach', 'cello', 'prelude', 'yoyoma']
  },
  {
    id: 'class-debussy-clairdelune',
    title: 'Suite Bergamasque: Clair de Lune',
    artist: 'Claude Debussy',
    broadcaster: 'independent',
    broadcasterName: 'Impressionist Piano',
    genre: 'classical',
    engine: 'youtube',
    youtubeId: 'WNcsUNKlAKw',
    url: 'https://www.youtube.com/watch?v=WNcsUNKlAKw',
    duration: 310,
    cover: 'linear-gradient(135deg, #030712 0%, #1e1b4b 50%, #6366f1 100%)',
    instruments: ['piano'],
    moods: ['relax', 'night', 'meditation'],
    tags: ['classical', 'debussy', 'clairdelune', 'piano', 'moonlight']
  },

  // ==============================================================================
  // 8. 🎛️ ELECTRONIC & DANCE (DAFT PUNK, AVICII, DEADMAU5 & FLOW STATE)
  // ==============================================================================
  {
    id: 'elec-daftpunk-harder',
    title: 'Harder, Better, Faster, Stronger',
    artist: 'Daft Punk',
    broadcaster: 'independent',
    broadcasterName: 'French Touch & House',
    genre: 'electronic',
    engine: 'youtube',
    youtubeId: 'LKYPYj2XX80',
    url: 'https://www.youtube.com/watch?v=LKYPYj2XX80',
    duration: 224,
    cover: 'linear-gradient(135deg, #18181b 0%, #312e81 50%, #ec4899 100%)',
    instruments: ['synth', 'drums', 'vocoder'],
    moods: ['energy', 'coding'],
    tags: ['electronic', 'daftpunk', 'house', 'frenchtouch', 'vocoder']
  },
  {
    id: 'elec-avicii-wakemeup',
    title: 'Wake Me Up',
    artist: 'Avicii',
    broadcaster: 'independent',
    broadcasterName: 'Melodic EDM',
    genre: 'electronic',
    engine: 'youtube',
    youtubeId: 'IcrbM1l_BoI',
    url: 'https://www.youtube.com/watch?v=IcrbM1l_BoI',
    duration: 252,
    cover: 'linear-gradient(135deg, #78350f 0%, #b45309 50%, #38bdf8 100%)',
    instruments: ['guitar', 'synth', 'drums'],
    moods: ['energy', 'relax'],
    tags: ['electronic', 'avicii', 'edm', 'melodic', 'anthem']
  },
  {
    id: 'elec-deadmau5-strobe',
    title: 'Strobe (Club Edit / Original Master)',
    artist: 'deadmau5',
    broadcaster: 'independent',
    broadcasterName: 'Progressive House',
    genre: 'electronic',
    engine: 'youtube',
    youtubeId: 'tKi9Z-f6qX4',
    url: 'https://www.youtube.com/watch?v=tKi9Z-f6qX4',
    duration: 637,
    cover: 'linear-gradient(135deg, #09090b 0%, #1e1b4b 50%, #00f2fe 100%)',
    instruments: ['synth', 'drums', 'bass'],
    moods: ['coding', 'focus', 'night'],
    tags: ['electronic', 'deadmau5', 'progressive', 'house', 'masterpiece']
  },
  {
    id: 'elec-prodigy-firestarter',
    title: 'Firestarter',
    artist: 'The Prodigy',
    broadcaster: 'independent',
    broadcasterName: 'Big Beat & Rave',
    genre: 'electronic',
    engine: 'youtube',
    youtubeId: 'wmin5WkSmX0',
    url: 'https://www.youtube.com/watch?v=wmin5WkSmX0',
    duration: 226,
    cover: 'linear-gradient(135deg, #18181b 0%, #450a0a 50%, #ef4444 100%)',
    instruments: ['synth', 'drums', 'guitar'],
    moods: ['energy', 'coding'],
    tags: ['electronic', 'prodigy', 'bigbeat', 'rave', '90s']
  },
  {
    id: 'elec-kraftwerk-model',
    title: 'The Model / Das Model',
    artist: 'Kraftwerk',
    broadcaster: 'independent',
    broadcasterName: 'Krautrock & Electro Pioneers',
    genre: 'electronic',
    engine: 'youtube',
    youtubeId: 'OQIYEPe6DWY',
    url: 'https://www.youtube.com/watch?v=OQIYEPe6DWY',
    duration: 220,
    cover: 'linear-gradient(135deg, #18181b 0%, #7f1d1d 50%, #f59e0b 100%)',
    instruments: ['synth', 'drums'],
    moods: ['coding', 'focus'],
    tags: ['electronic', 'kraftwerk', 'synthpop', 'pioneers', 'krautrock']
  },

  // ==============================================================================
  // 9. 🌌 AMBIENT & DEEP FOCUS (BRIAN ENO, TYCHO & 432HZ BINAURAL)
  // ==============================================================================
  {
    id: 'amb-brianeno-airports',
    title: 'Ambient 1: Music for Airports 1/1',
    artist: 'Brian Eno',
    broadcaster: 'independent',
    broadcasterName: 'Ambient Origins',
    genre: 'ambient',
    engine: 'youtube',
    youtubeId: 'vNwYtllyt3Q',
    url: 'https://www.youtube.com/watch?v=vNwYtllyt3Q',
    duration: 1042,
    cover: 'linear-gradient(135deg, #022c22 0%, #065f46 50%, #10b981 100%)',
    instruments: ['piano', 'synth'],
    moods: ['focus', 'meditation', 'coding'],
    tags: ['ambient', 'brianeno', 'airports', 'generative', 'zen']
  },
  {
    id: 'amb-tycho-awake',
    title: 'Awake',
    artist: 'Tycho',
    broadcaster: 'independent',
    broadcasterName: 'IDM & Organic Ambient',
    genre: 'ambient',
    engine: 'youtube',
    youtubeId: 'pitwtbE4r0M',
    url: 'https://www.youtube.com/watch?v=pitwtbE4r0M',
    duration: 284,
    cover: 'linear-gradient(135deg, #78350f 0%, #d97706 50%, #f43f5e 100%)',
    instruments: ['synth', 'guitar', 'drums', 'bass'],
    moods: ['coding', 'focus', 'relax'],
    tags: ['ambient', 'tycho', 'awake', 'sunset', 'chill']
  },
  {
    id: 'amb-marconi-weightless',
    title: 'Weightless (Most Relaxing Sound on Earth)',
    artist: 'Marconi Union',
    broadcaster: 'independent',
    broadcasterName: 'Sound Therapy Lab',
    genre: 'ambient',
    engine: 'youtube',
    youtubeId: 'UfcAVejslrU',
    url: 'https://www.youtube.com/watch?v=UfcAVejslrU',
    duration: 485,
    cover: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #00f2fe 100%)',
    instruments: ['synth', 'guitar', 'piano'],
    moods: ['meditation', 'relax', 'focus'],
    tags: ['ambient', 'weightless', 'therapy', 'sleep', 'relaxation']
  },
  {
    id: 'amb-cbl-sleepers',
    title: 'World of Sleepers',
    artist: 'Carbon Based Lifeforms',
    broadcaster: 'independent',
    broadcasterName: 'Psybient & Deep Space',
    genre: 'ambient',
    engine: 'youtube',
    youtubeId: '0RhsZvdTkSQ',
    url: 'https://www.youtube.com/watch?v=0RhsZvdTkSQ',
    duration: 420,
    cover: 'linear-gradient(135deg, #030712 0%, #0f172a 50%, #38bdf8 100%)',
    instruments: ['synth', 'bass'],
    moods: ['focus', 'coding', 'night'],
    tags: ['ambient', 'psybient', 'carbonbasedlifeforms', 'space']
  },
  {
    id: 'ambient-synth-432',
    title: 'Deep Alpha Waves 432Hz Focus Kernel',
    artist: 'Sigma Audio Synthesizer',
    broadcaster: 'sigma_dsp',
    broadcasterName: 'Sigma Audio DSP',
    genre: 'ambient',
    engine: 'synth',
    duration: 360,
    url: '',
    cover: 'linear-gradient(135deg, #030712 0%, #1e1b4b 50%, #0369a1 100%)',
    instruments: ['synth', 'flute'],
    moods: ['focus', 'meditation'],
    tags: ['alpha-waves', '432hz', 'zen', 'calm', 'binaural', 'sigma']
  },

  // ==============================================================================
  // 10. ☕ CHILLHOP & HIP-HOP (DR. DRE, EMINEM, 2PAC, BIGGIE)
  // ==============================================================================
  {
    id: 'hiphop-drdre-stilldre',
    title: 'Still D.R.E.',
    artist: 'Dr. Dre ft. Snoop Dogg',
    broadcaster: 'independent',
    broadcasterName: 'West Coast Classics',
    genre: 'chillhop',
    engine: 'youtube',
    youtubeId: '_CL6n0FJZpk',
    url: 'https://www.youtube.com/watch?v=_CL6n0FJZpk',
    duration: 290,
    cover: 'linear-gradient(135deg, #18181b 0%, #3f3f46 50%, #10b981 100%)',
    instruments: ['piano', 'drums', 'bass'],
    moods: ['coding', 'relax', 'energy'],
    tags: ['hiphop', 'drdre', 'snoopdogg', 'stilldre', 'piano', 'groove']
  },
  {
    id: 'hiphop-eminem-loseyourself',
    title: 'Lose Yourself (8 Mile)',
    artist: 'Eminem',
    broadcaster: 'independent',
    broadcasterName: 'Hip Hop Anthems',
    genre: 'chillhop',
    engine: 'youtube',
    youtubeId: '_Yhyp-_hX2s',
    url: 'https://www.youtube.com/watch?v=_Yhyp-_hX2s',
    duration: 326,
    cover: 'linear-gradient(135deg, #450a0a 0%, #7f1d1d 50%, #f59e0b 100%)',
    instruments: ['piano', 'guitar', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['hiphop', 'eminem', 'loseyourself', '8mile', 'motivation']
  },
  {
    id: 'hiphop-2pac-changes',
    title: 'Changes',
    artist: '2Pac ft. Talent',
    broadcaster: 'independent',
    broadcasterName: 'Hip Hop Legends',
    genre: 'chillhop',
    engine: 'youtube',
    youtubeId: 'eXvBjCO19QY',
    url: 'https://www.youtube.com/watch?v=eXvBjCO19QY',
    duration: 270,
    cover: 'linear-gradient(135deg, #1e1b4b 0%, #4338ca 50%, #38bdf8 100%)',
    instruments: ['piano', 'drums', 'bass'],
    moods: ['relax', 'focus', 'night'],
    tags: ['hiphop', '2pac', 'changes', 'piano', 'conscious']
  },
  {
    id: 'hiphop-biggie-juicy',
    title: 'Juicy',
    artist: 'The Notorious B.I.G.',
    broadcaster: 'independent',
    broadcasterName: 'East Coast Gold',
    genre: 'chillhop',
    engine: 'youtube',
    youtubeId: '_JZom_gVfuw',
    url: 'https://www.youtube.com/watch?v=_JZom_gVfuw',
    duration: 255,
    cover: 'linear-gradient(135deg, #78350f 0%, #b45309 50%, #ec4899 100%)',
    instruments: ['drums', 'bass', 'synth'],
    moods: ['relax', 'coding'],
    tags: ['hiphop', 'biggie', 'juicy', '90s', 'classic']
  },

  // ==============================================================================
  // 11. 🎬 COLONNE SONORE & EPIC (HANS ZIMMER, ENNIO MORRICONE, JOHN WILLIAMS)
  // ==============================================================================
  {
    id: 'cine-zimmer-interstellar',
    title: 'Interstellar Main Theme (First Step)',
    artist: 'Hans Zimmer',
    broadcaster: 'independent',
    broadcasterName: 'Epic Soundtracks',
    genre: 'cinematic',
    engine: 'youtube',
    youtubeId: 'UDVtMYqUAyw',
    url: 'https://www.youtube.com/watch?v=UDVtMYqUAyw',
    duration: 257,
    cover: 'linear-gradient(135deg, #030712 0%, #1e1b4b 50%, #38bdf8 100%)',
    instruments: ['piano', 'synth', 'strings'],
    moods: ['focus', 'coding', 'meditation'],
    tags: ['soundtrack', 'hanszimmer', 'interstellar', 'space', 'organ']
  },
  {
    id: 'cine-zimmer-time',
    title: 'Inception: Time',
    artist: 'Hans Zimmer',
    broadcaster: 'independent',
    broadcasterName: 'Cinematic Masterpieces',
    genre: 'cinematic',
    engine: 'youtube',
    youtubeId: 'RxabLA7UQ9k',
    url: 'https://www.youtube.com/watch?v=RxabLA7UQ9k',
    duration: 275,
    cover: 'linear-gradient(135deg, #0f172a 0%, #334155 50%, #f59e0b 100%)',
    instruments: ['strings', 'piano', 'guitar'],
    moods: ['focus', 'night', 'meditation'],
    tags: ['soundtrack', 'inception', 'time', 'zimmer', 'epic']
  },
  {
    id: 'cine-morricone-goodbad',
    title: 'The Good, the Bad and the Ugly Theme',
    artist: 'Ennio Morricone',
    broadcaster: 'independent',
    broadcasterName: 'Cinema Legends',
    genre: 'cinematic',
    engine: 'youtube',
    youtubeId: 'AFa1-kciNw4',
    url: 'https://www.youtube.com/watch?v=AFa1-kciNw4',
    duration: 162,
    cover: 'linear-gradient(135deg, #78350f 0%, #b45309 50%, #eab308 100%)',
    instruments: ['flute', 'guitar', 'trumpet', 'drums'],
    moods: ['energy', 'focus'],
    tags: ['soundtrack', 'morricone', 'western', 'legend', 'cinema']
  },
  {
    id: 'cine-williams-imperial',
    title: 'Star Wars: The Imperial March (Darth Vader\'s Theme)',
    artist: 'John Williams (London Symphony Orchestra)',
    broadcaster: 'independent',
    broadcasterName: 'Sci-Fi Orchestras',
    genre: 'cinematic',
    engine: 'youtube',
    youtubeId: '-bzWSJG93P8',
    url: 'https://www.youtube.com/watch?v=-bzWSJG93P8',
    duration: 184,
    cover: 'linear-gradient(135deg, #18181b 0%, #450a0a 50%, #dc2626 100%)',
    instruments: ['trumpet', 'strings', 'drums'],
    moods: ['energy', 'coding'],
    tags: ['soundtrack', 'starwars', 'johnwilliams', 'imperial', 'vader']
  },
  {
    id: 'cine-shore-hobbits',
    title: 'The Lord of the Rings: Concerning Hobbits',
    artist: 'Howard Shore',
    broadcaster: 'independent',
    broadcasterName: 'Fantasy Soundtracks',
    genre: 'cinematic',
    engine: 'youtube',
    youtubeId: '_pGaz_qN0cw',
    url: 'https://www.youtube.com/watch?v=_pGaz_qN0cw',
    duration: 164,
    cover: 'linear-gradient(135deg, #022c22 0%, #065f46 50%, #84cc16 100%)',
    instruments: ['flute', 'strings', 'guitar'],
    moods: ['relax', 'focus', 'meditation'],
    tags: ['soundtrack', 'lotr', 'hobbit', 'howardshore', 'shire']
  },

  // ==============================================================================
  // 12. 🎮 GAMING & CHIPTUNE (DOOM, SKYRIM, THE WITCHER, UNDERTALE)
  // ==============================================================================
  {
    id: 'game-doom-fear',
    title: 'The Only Thing They Fear Is You (DOOM Eternal)',
    artist: 'Mick Gordon',
    broadcaster: 'independent',
    broadcasterName: 'Industrial Gaming Metal',
    genre: 'gaming',
    engine: 'youtube',
    youtubeId: 'kpnW68QXu78',
    url: 'https://www.youtube.com/watch?v=kpnW68QXu78',
    duration: 413,
    cover: 'linear-gradient(135deg, #450a0a 0%, #991b1b 50%, #ea580c 100%)',
    instruments: ['guitar', 'synth', 'drums', 'bass'],
    moods: ['energy', 'coding'],
    tags: ['gaming', 'doom', 'mickgordon', 'heavy', 'adrenaline']
  },
  {
    id: 'game-skyrim-theme',
    title: 'The Elder Scrolls V: Skyrim - Dragonborn Theme',
    artist: 'Jeremy Soule',
    broadcaster: 'independent',
    broadcasterName: 'Epic RPG Soundtracks',
    genre: 'gaming',
    engine: 'youtube',
    youtubeId: '2-_g8NZr1tA',
    url: 'https://www.youtube.com/watch?v=2-_g8NZr1tA',
    duration: 238,
    cover: 'linear-gradient(135deg, #0f172a 0%, #334155 50%, #94a3b8 100%)',
    instruments: ['trumpet', 'strings', 'drums'],
    moods: ['energy', 'focus', 'coding'],
    tags: ['gaming', 'skyrim', 'dragonborn', 'elderscrolls', 'epic']
  },
  {
    id: 'game-witcher-silver',
    title: 'The Witcher 3: Wild Hunt - Silver for Monsters',
    artist: 'Marcin Przybyłowicz & Percival',
    broadcaster: 'independent',
    broadcasterName: 'Dark Fantasy OST',
    genre: 'gaming',
    engine: 'youtube',
    youtubeId: 'UENb3l_zS_Y',
    url: 'https://www.youtube.com/watch?v=UENb3l_zS_Y',
    duration: 260,
    cover: 'linear-gradient(135deg, #1c1917 0%, #44403c 50%, #ef4444 100%)',
    instruments: ['strings', 'drums', 'flute'],
    moods: ['energy', 'coding'],
    tags: ['gaming', 'witcher', 'geralt', 'folk', 'monsters']
  },
  {
    id: 'game-undertale-megalovania',
    title: 'MEGALOVANIA (Undertale)',
    artist: 'Toby Fox',
    broadcaster: 'independent',
    broadcasterName: 'Chiptune & Boss Themes',
    genre: 'gaming',
    engine: 'youtube',
    youtubeId: 'wDgQdr8ZkTw',
    url: 'https://www.youtube.com/watch?v=wDgQdr8ZkTw',
    duration: 156,
    cover: 'linear-gradient(135deg, #09090b 0%, #1e1b4b 50%, #38bdf8 100%)',
    instruments: ['synth', 'drums', 'guitar'],
    moods: ['energy', 'coding'],
    tags: ['gaming', 'undertale', 'sans', 'megalovania', 'chiptune']
  }
];

const STORAGE_KEYS = {
  TASTE_PROFILE: 'sigma_music_taste_profile_v5',
  FAVORITES: 'sigma_music_favorites_v5',
  HISTORY: 'sigma_music_history_v5',
  CUSTOM_TRACKS: 'sigma_music_custom_tracks_v5'
};

/** Load user's taste profile from localStorage */
export function loadTasteProfile() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.TASTE_PROFILE);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return {
    genreScores: {
      radio_fm: 18,
      rock: 12,
      lofi: 12,
      synthwave: 10,
      jazz: 8,
      classical: 8,
      electronic: 8,
      metal: 7,
      ambient: 8
    },
    broadcasterScores: {
      mediaset: 10,
      rai: 8,
      sole24ore: 8,
      uk_global: 6,
      independent: 8
    },
    instrumentScores: {
      piano: 8,
      guitar: 9,
      sax: 7,
      synth: 8,
      drums: 8
    },
    trackListens: {},
    totalListenSeconds: 0
  };
}

/** Save taste profile */
export function saveTasteProfile(profile) {
  try {
    localStorage.setItem(STORAGE_KEYS.TASTE_PROFILE, JSON.stringify(profile));
  } catch (e) {}
}

/** Load favorite track IDs */
export function loadFavorites() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.FAVORITES);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return ['fm-virgin-1', 'fm-105-1', 'fm-rai-classica', 'lofi-live-1'];
}

/** Save favorite track IDs */
export function saveFavorites(favs) {
  try {
    localStorage.setItem(STORAGE_KEYS.FAVORITES, JSON.stringify(favs));
  } catch (e) {}
}

/** Load custom added tracks / files */
export function loadCustomTracks() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.CUSTOM_TRACKS);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return [];
}

/** Save custom added tracks */
export function saveCustomTracks(tracks) {
  try {
    localStorage.setItem(STORAGE_KEYS.CUSTOM_TRACKS, JSON.stringify(tracks));
  } catch (e) {}
}

/** Load listening history */
export function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.HISTORY);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return [];
}

/** Save history */
export function saveHistory(hist) {
  try {
    localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(hist.slice(0, 50)));
  } catch (e) {}
}

/** Record a listening event and update user taste scores */
export function recordListen(track, durationSec = 15) {
  if (!track) return;
  const profile = loadTasteProfile();
  
  if (!profile.genreScores) profile.genreScores = {};
  if (!profile.broadcasterScores) profile.broadcasterScores = {};
  if (!profile.instrumentScores) profile.instrumentScores = {};
  if (!profile.trackListens) profile.trackListens = {};

  const g = track.genre || 'radio_fm';
  profile.genreScores[g] = (profile.genreScores[g] || 0) + Math.max(1, Math.round(durationSec / 10));

  if (track.broadcaster) {
    profile.broadcasterScores[track.broadcaster] = (profile.broadcasterScores[track.broadcaster] || 0) + 1;
  }

  if (track.instruments && Array.isArray(track.instruments)) {
    track.instruments.forEach(inst => {
      profile.instrumentScores[inst] = (profile.instrumentScores[inst] || 0) + 1;
    });
  }

  profile.trackListens[track.id] = (profile.trackListens[track.id] || 0) + 1;
  profile.totalListenSeconds = (profile.totalListenSeconds || 0) + durationSec;

  saveTasteProfile(profile);

  // Update history
  const history = loadHistory();
  const filtered = history.filter(h => h.id !== track.id);
  filtered.unshift({
    ...track,
    listenedAt: new Date().toISOString()
  });
  saveHistory(filtered);
}

/** Smart recommendation engine with broadcaster affinity and taste scores */
export function getSmartRecommendations(allTracks = DEFAULT_TRACKS, currentTrackId = null, limit = 6) {
  const profile = loadTasteProfile();
  const favorites = new Set(loadFavorites());
  const history = loadHistory();
  const recentTrackIds = new Set(history.slice(0, 3).map(h => h.id));

  const gScores = profile.genreScores || {};
  const bScores = profile.broadcasterScores || {};
  const iScores = profile.instrumentScores || {};

  // Find top genre & broadcaster
  let topGenre = 'radio_fm';
  let maxGScore = -1;
  Object.entries(gScores).forEach(([genre, score]) => {
    if (score > maxGScore) {
      maxGScore = score;
      topGenre = genre;
    }
  });

  let topBroadcaster = 'mediaset';
  let maxBScore = -1;
  Object.entries(bScores).forEach(([bc, score]) => {
    if (score > maxBScore) {
      maxBScore = score;
      topBroadcaster = bc;
    }
  });

  // Score candidate tracks
  const scoredTracks = allTracks.map(track => {
    let score = 0;
    const genreScore = gScores[track.genre] || 1;
    score += genreScore * 2.5;

    // Broadcaster boost
    if (track.broadcaster && bScores[track.broadcaster]) {
      score += bScores[track.broadcaster] * 2.0;
    }

    // Instrument affinity boost
    if (track.instruments && Array.isArray(track.instruments)) {
      track.instruments.forEach(inst => {
        score += (iScores[inst] || 0) * 1.5;
      });
    }

    // Favorites boost
    if (favorites.has(track.id)) {
      score += 18;
    }

    // Historical listen boost
    const listenCount = (profile.trackListens && profile.trackListens[track.id]) || 0;
    score += Math.min(25, listenCount * 3.5);

    // Variety penalty for current playing track
    if (track.id === currentTrackId) {
      score -= 50;
    }

    if (recentTrackIds.has(track.id)) {
      score -= 5;
    }

    score += Math.random() * 4;

    // Build intelligent rationale string
    let rationale = `Basato sui tuoi ascolti in ${track.genre.toUpperCase()}`;
    if (favorites.has(track.id)) {
      rationale = 'Tra le tue stazioni preferite ❤️';
    } else if (track.broadcasterName) {
      rationale = `Canale ufficiale ${track.broadcasterName}`;
    } else if (track.frequency) {
      rationale = `Diretta FM (${track.frequency}) consigliata`;
    }

    return {
      ...track,
      recommendationScore: score,
      recommendationReason: rationale
    };
  });

  scoredTracks.sort((a, b) => b.recommendationScore - a.recommendationScore);
  return scoredTracks.slice(0, limit);
}

export const DEFAULT_USER_CATEGORIES = [
  { id: 'cat-focus', name: 'Focus & Deep Work', icon: '🧠', color: '#00d2ff' },
  { id: 'cat-relax', name: 'Chill & Relax', icon: '☕', color: '#10b981' },
  { id: 'cat-energy', name: 'Energia & Rock', icon: '⚡', color: '#ef4444' },
  { id: 'cat-night', name: 'Notte & Ambient', icon: '🌌', color: '#a78bfa' }
];

export function loadUserCategories() {
  try {
    const raw = localStorage.getItem('sigma_music_categories');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (e) {}
  return DEFAULT_USER_CATEGORIES;
}

export function saveUserCategories(categories) {
  try {
    localStorage.setItem('sigma_music_categories', JSON.stringify(categories));
  } catch (e) {}
}

