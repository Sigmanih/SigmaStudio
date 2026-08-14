// ==============================================================================
// MusicContext.jsx — Multi-Engine Global Background Audio & Music Lounge Provider
// Persistent playback across all tabs: Web Radio, YouTube, Spotify, Local & Synth
// ==============================================================================

import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import {
  DEFAULT_TRACKS,
  BROADCASTERS,
  GENRES,
  INSTRUMENTS,
  MOODS,
  loadTasteProfile,
  loadFavorites,
  saveFavorites,
  loadCustomTracks,
  saveCustomTracks,
  loadHistory,
  recordListen,
  getSmartRecommendations,
  loadUserCategories,
  saveUserCategories,
  DEFAULT_USER_CATEGORIES
} from './services/musicRecommendation';

const MusicContext = createContext(null);
export const AudioContext = MusicContext;
export const useAudio = () => useContext(MusicContext);

export function MusicProvider({ children }) {
  const [customTracks, setCustomTracks] = useState(loadCustomTracks);
  const [allTracks, setAllTracks] = useState(() => [...DEFAULT_TRACKS, ...loadCustomTracks()]);
  const [userCategories, setUserCategories] = useState(loadUserCategories);
  const [activeCategory, setActiveCategory] = useState('all');
  const [currentTrack, setCurrentTrack] = useState(DEFAULT_TRACKS[0]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeGenre, setActiveGenre] = useState('all');
  const [activeBroadcaster, setActiveBroadcaster] = useState('all');
  const [activeInstrument, setActiveInstrument] = useState('all');
  const [activeMood, setActiveMood] = useState('all');
  const [activeEngine, setActiveEngine] = useState('all'); // 'all' | 'radio' | 'youtube' | 'spotify' | 'local' | 'synth'

  const [volume, setVolumeState] = useState(() => {
    try {
      const v = localStorage.getItem('sigma_music_volume');
      return v !== null ? parseFloat(v) : 0.75;
    } catch (e) {
      return 0.75;
    }
  });
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(DEFAULT_TRACKS[0].duration || 180);
  const [favorites, setFavorites] = useState(loadFavorites);
  const [history, setHistory] = useState(loadHistory);
  const [recommendations, setRecommendations] = useState([]);
  const [shuffle, setShuffle] = useState(false);
  const [repeatMode, setRepeatMode] = useState('all'); // 'off' | 'all' | 'one'
  const [audioError, setAudioError] = useState(null);

  const audioRef = useRef(null);
  const ytIframeRef = useRef(null);
  const playTimerRef = useRef(null);
  const synthNodesRef = useRef(null);

  // Initialize Singleton HTML5 Audio element
  // NOTE: Do NOT set audio.crossOrigin = 'anonymous' because it breaks standard live audio streams & 302 redirects (like Rai Radio)
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const audio = new Audio();
    audio.preload = 'auto';
    audio.volume = isMuted ? 0 : volume;
    audioRef.current = audio;

    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime || 0);
      if (audio.duration && !isNaN(audio.duration)) {
        setDuration(audio.duration);
      }
    };

    const onLoadedMetadata = () => {
      if (audio.duration && !isNaN(audio.duration)) {
        setDuration(audio.duration);
      }
      setAudioError(null);
    };

    const onEnded = () => {
      handleTrackEnded();
    };

    const onError = () => {
      console.warn('Audio stream fallback activated:', audio.error?.message || 'Connection error');
      setAudioError('Stream Offline → Synth Fallback Attivo');
      startProceduralSynth(currentTrack?.genre || 'ambient');
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('loadedmetadata', onLoadedMetadata);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('error', onError);

    // Initial recommendations
    setRecommendations(getSmartRecommendations(allTracks, DEFAULT_TRACKS[0].id));

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('loadedmetadata', onLoadedMetadata);
      audio.removeEventListener('ended', onEnded);
      audio.removeEventListener('error', onError);
      audio.pause();
      stopProceduralSynth();
    };
  }, []);

  // Sync volume to audio element and YouTube iframe
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume;
    }
    if (ytIframeRef.current && ytIframeRef.current.contentWindow) {
      try {
        const volVal = isMuted ? 0 : Math.round(volume * 100);
        ytIframeRef.current.contentWindow.postMessage(JSON.stringify({
          event: 'command',
          func: 'setVolume',
          args: [volVal]
        }), '*');
      } catch (e) {}
    }
    try {
      localStorage.setItem('sigma_music_volume', String(volume));
    } catch (e) {}
  }, [volume, isMuted]);

  // Track listen duration for taste profiling
  useEffect(() => {
    if (isPlaying && currentTrack) {
      playTimerRef.current = setInterval(() => {
        recordListen(currentTrack, 5);
      }, 5000);
    } else {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    }
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [isPlaying, currentTrack]);

  // Refresh recommendations
  const refreshRecommendations = (trackId = currentTrack?.id) => {
    const recs = getSmartRecommendations(allTracks, trackId);
    setRecommendations(recs);
  };

  // Procedural Web Audio Ambient Synth Fallback
  const startProceduralSynth = (genre = 'lofi') => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      if (synthNodesRef.current) return;

      const ctx = new AudioCtx();
      const masterGain = ctx.createGain();
      masterGain.gain.setValueAtTime((isMuted ? 0 : volume) * 0.16, ctx.currentTime);
      masterGain.connect(ctx.destination);

      const freqs = genre === 'synthwave' ? [220, 277.18, 329.63, 440] : [174.61, 220.0, 261.63, 329.63];
      const oscs = freqs.map(freq => {
        const osc = ctx.createOscillator();
        const g = ctx.createGain();
        osc.type = genre === 'synthwave' ? 'sawtooth' : 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        g.gain.setValueAtTime(0.06, ctx.currentTime);
        osc.connect(g);
        g.connect(masterGain);
        osc.start();
        return osc;
      });

      synthNodesRef.current = { ctx, masterGain, oscs };
    } catch (e) {
      console.debug('Synth generator error:', e);
    }
  };

  const stopProceduralSynth = () => {
    if (synthNodesRef.current) {
      try {
        synthNodesRef.current.oscs.forEach(o => {
          try { o.stop(); } catch (e) {}
        });
        synthNodesRef.current.ctx.close();
      } catch (e) {}
      synthNodesRef.current = null;
    }
  };

  const playTrack = async (track) => {
    if (!track) return;
    stopProceduralSynth();
    setCurrentTrack(track);
    setCurrentTime(0);
    setDuration(track.duration || 180);
    setAudioError(null);

    const eng = track.engine || 'radio';

    if (eng === 'youtube') {
      if (audioRef.current) audioRef.current.pause();
      setIsPlaying(true);
    } else if (eng === 'synth') {
      if (audioRef.current) audioRef.current.pause();
      startProceduralSynth(track.genre);
      setIsPlaying(true);
    } else {
      // Audio or Radio stream or Local file
      if (audioRef.current) {
        try {
          audioRef.current.src = track.url;
          audioRef.current.load();
          await audioRef.current.play();
          setIsPlaying(true);
        } catch (err) {
          console.warn('Audio stream error, activating local synth generator:', err);
          startProceduralSynth(track.genre);
          setIsPlaying(true);
        }
      }
    }

    refreshRecommendations(track.id);
    setHistory(loadHistory());
  };

  const togglePlay = async () => {
    if (isPlaying) {
      if (audioRef.current) audioRef.current.pause();
      if (ytIframeRef.current && ytIframeRef.current.contentWindow) {
        try {
          ytIframeRef.current.contentWindow.postMessage(JSON.stringify({
            event: 'command',
            func: 'pauseVideo',
            args: []
          }), '*');
        } catch (e) {}
      }
      stopProceduralSynth();
      setIsPlaying(false);
    } else {
      if (currentTrack) {
        if (currentTrack.engine === 'youtube') {
          if (ytIframeRef.current && ytIframeRef.current.contentWindow) {
            try {
              ytIframeRef.current.contentWindow.postMessage(JSON.stringify({
                event: 'command',
                func: 'playVideo',
                args: []
              }), '*');
            } catch (e) {}
          }
          setIsPlaying(true);
        } else if (currentTrack.engine === 'synth') {
          startProceduralSynth(currentTrack.genre);
          setIsPlaying(true);
        } else if (audioRef.current) {
          if (!audioRef.current.src || audioRef.current.src !== currentTrack.url) {
            audioRef.current.src = currentTrack.url;
            audioRef.current.load();
          }
          try {
            await audioRef.current.play();
            setIsPlaying(true);
          } catch (e) {
            startProceduralSynth(currentTrack.genre);
            setIsPlaying(true);
          }
        }
      }
    }
  };

  const getFilteredTracks = () => {
    return allTracks.filter(t => {
      const matchGenre = activeGenre === 'all' || t.genre === activeGenre;
      const matchBroadcaster = activeBroadcaster === 'all' || t.broadcaster === activeBroadcaster;
      const matchInst = activeInstrument === 'all' || (t.instruments && t.instruments.includes(activeInstrument));
      const matchMood = activeMood === 'all' || (t.moods && t.moods.includes(activeMood));
      const matchEngine = activeEngine === 'all' || (t.engine || 'radio') === activeEngine;
      return matchGenre && matchBroadcaster && matchInst && matchMood && matchEngine;
    });
  };

  const nextTrack = () => {
    const list = getFilteredTracks();
    if (!list || list.length === 0) return;
    const currentIndex = list.findIndex(t => t.id === currentTrack?.id);

    let nextIndex;
    if (shuffle) {
      nextIndex = Math.floor(Math.random() * list.length);
      if (nextIndex === currentIndex && list.length > 1) {
        nextIndex = (nextIndex + 1) % list.length;
      }
    } else {
      nextIndex = (currentIndex + 1) % list.length;
    }

    playTrack(list[nextIndex]);
  };

  const prevTrack = () => {
    const list = getFilteredTracks();
    if (!list || list.length === 0) return;
    const currentIndex = list.findIndex(t => t.id === currentTrack?.id);
    const prevIndex = (currentIndex - 1 + list.length) % list.length;
    playTrack(list[prevIndex]);
  };

  const handleTrackEnded = () => {
    if (repeatMode === 'one') {
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
        audioRef.current.play().catch(() => {});
      }
    } else {
      nextTrack();
    }
  };

  const seek = (timeInSeconds) => {
    const clamped = Math.max(0, Math.min(duration, timeInSeconds));
    setCurrentTime(clamped);
    if (audioRef.current && currentTrack?.engine !== 'youtube') {
      try {
        audioRef.current.currentTime = clamped;
      } catch (e) {}
    }
  };

  const setVolume = (v) => {
    const val = Math.max(0, Math.min(1, v));
    setVolumeState(val);
    if (isMuted && val > 0) setIsMuted(false);
  };

  const toggleMute = () => {
    setIsMuted(prev => !prev);
  };

  const toggleFavorite = (trackId) => {
    setFavorites(prev => {
      const next = prev.includes(trackId)
        ? prev.filter(id => id !== trackId)
        : [...prev, trackId];
      saveFavorites(next);
      return next;
    });
    refreshRecommendations();
  };

  const createUserCategory = ({ name, icon, color }) => {
    if (!name || !name.trim()) return null;
    const cleanName = name.trim();
    const existing = userCategories.find(c => c.name.toLowerCase() === cleanName.toLowerCase());
    if (existing) return existing;

    const newCat = {
      id: `cat-${Date.now()}`,
      name: cleanName,
      icon: icon || '🎵',
      color: color || '#00f2fe'
    };
    const next = [...userCategories, newCat];
    setUserCategories(next);
    saveUserCategories(next);
    return newCat;
  };

  const deleteUserCategory = (catId) => {
    const next = userCategories.filter(c => c.id !== catId);
    setUserCategories(next);
    saveUserCategories(next);
    if (activeCategory === catId) setActiveCategory('all');
  };

  const assignTrackCategory = (trackId, categoryId) => {
    const updatedCustom = customTracks.map(t => {
      if (t.id === trackId) {
        return { ...t, category: categoryId, categoryId: categoryId };
      }
      return t;
    });
    setCustomTracks(updatedCustom);
    saveCustomTracks(updatedCustom);

    const updatedAll = allTracks.map(t => {
      if (t.id === trackId) {
        return { ...t, category: categoryId, categoryId: categoryId };
      }
      return t;
    });
    setAllTracks(updatedAll);
    if (currentTrack?.id === trackId) {
      setCurrentTrack(prev => ({ ...prev, category: categoryId, categoryId: categoryId }));
    }
  };

  const playCategory = (categoryId) => {
    setActiveCategory(categoryId);
    const catTracks = allTracks.filter(t => t.category === categoryId || t.categoryId === categoryId);
    if (catTracks.length > 0) {
      playTrack(catTracks[0]);
    }
  };

  // Quick save YouTube music video from chat to favorites with optional Category
  const saveYouTubeFavorite = ({ id, title, categoryId, categoryName, autoPlay }) => {
    let finalCatId = categoryId || (userCategories[0] ? userCategories[0].id : 'cat-focus');
    if (categoryName && categoryName.trim()) {
      const cat = createUserCategory({ name: categoryName.trim() });
      if (cat) finalCatId = cat.id;
    }

    const existingTrack = allTracks.find(t => t.youtubeId === id || t.id === `yt-${id}`);
    if (existingTrack) {
      const isAlreadyFav = favorites.includes(existingTrack.id);
      if (!isAlreadyFav) {
        setFavorites(prev => {
          const next = [...prev, existingTrack.id];
          saveFavorites(next);
          return next;
        });
      }
      if (finalCatId) {
        assignTrackCategory(existingTrack.id, finalCatId);
      }
      if (autoPlay) playTrack(existingTrack);
      return !isAlreadyFav;
    } else {
      const newTrack = {
        id: `yt-${id}`,
        title: title || 'Video Musicale Consigliato',
        artist: 'YouTube Music',
        broadcaster: 'independent',
        broadcasterName: 'YouTube Suggestion',
        genre: 'radio_fm',
        category: finalCatId,
        categoryId: finalCatId,
        engine: 'youtube',
        url: `https://www.youtube.com/watch?v=${id}`,
        youtubeId: id,
        duration: 0,
        isLive: true,
        instruments: ['synth', 'guitar'],
        moods: ['focus', 'relax'],
        cover: `https://img.youtube.com/vi/${id}/mqdefault.jpg`,
        tags: ['youtube', 'chat-saved', finalCatId]
      };
      const updatedCustom = [newTrack, ...customTracks];
      setCustomTracks(updatedCustom);
      saveCustomTracks(updatedCustom);
      const updatedAll = [newTrack, ...allTracks];
      setAllTracks(updatedAll);
      
      setFavorites(prev => {
        const next = [...prev, newTrack.id];
        saveFavorites(next);
        return next;
      });
      refreshRecommendations();
      if (autoPlay) playTrack(newTrack);
      return true;
    }
  };

  const selectGenre = (genreId) => {
    setActiveGenre(genreId);
    if (genreId !== 'all') {
      const genreTracks = allTracks.filter(t => t.genre === genreId);
      if (genreTracks.length > 0 && currentTrack?.genre !== genreId) {
        playTrack(genreTracks[0]);
      }
    }
  };

  const selectBroadcaster = (bcId) => {
    setActiveBroadcaster(bcId);
    if (bcId !== 'all') {
      const bcTracks = allTracks.filter(t => t.broadcaster === bcId);
      if (bcTracks.length > 0 && currentTrack?.broadcaster !== bcId) {
        playTrack(bcTracks[0]);
      }
    }
  };

  // Add custom URL / stream / YouTube / Spotify track
  const addCustomTrack = (trackData) => {
    let ytId = trackData.youtubeId;
    let eng = trackData.engine || 'radio';

    if (trackData.url && trackData.url.includes('youtube.com') || (trackData.url && trackData.url.includes('youtu.be'))) {
      const m = trackData.url.match(/(?:watch\?v=|embed\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
      if (m && m[1]) {
        ytId = m[1];
        eng = 'youtube';
      }
    }

    const newTrack = {
      id: `custom-${Date.now()}`,
      title: trackData.title || 'Traccia Personalizzata',
      artist: trackData.artist || 'Utente',
      broadcaster: 'independent',
      broadcasterName: 'Stream Utente',
      genre: trackData.genre || 'radio_fm',
      engine: eng,
      url: trackData.url || '',
      youtubeId: ytId || null,
      duration: trackData.duration || 0,
      isLive: true,
      instruments: trackData.instruments || ['synth'],
      moods: trackData.moods || ['focus'],
      cover: trackData.cover || 'linear-gradient(135deg, #00f2fe, #7928ca)',
      tags: ['custom', trackData.genre || 'radio_fm']
    };

    const updated = [newTrack, ...customTracks];
    setCustomTracks(updated);
    saveCustomTracks(updated);
    const updatedAll = [newTrack, ...allTracks];
    setAllTracks(updatedAll);
    playTrack(newTrack);
  };

  // Import local audio files from user PC
  const importLocalFiles = (fileList) => {
    if (!fileList || fileList.length === 0) return;
    const newLocalTracks = Array.from(fileList).map((file, idx) => {
      const blobUrl = URL.createObjectURL(file);
      const cleanName = file.name.replace(/\.[^/.]+$/, "");
      return {
        id: `local-${Date.now()}-${idx}`,
        title: cleanName,
        artist: 'File Locale',
        broadcaster: 'independent',
        broadcasterName: 'File dal PC',
        genre: 'lofi',
        engine: 'local',
        url: blobUrl,
        duration: 180,
        instruments: ['piano', 'guitar'],
        moods: ['focus'],
        cover: 'linear-gradient(135deg, #059669, #0284c7)',
        tags: ['local', 'mp3']
      };
    });

    const updatedAll = [...newLocalTracks, ...allTracks];
    setAllTracks(updatedAll);
    if (newLocalTracks.length > 0) {
      playTrack(newLocalTracks[0]);
    }
  };

  // Shuffle & play a random track from a specific genre
  const shuffleGenre = (genreId) => {
    const targetGenre = genreId || activeGenre;
    const genreTracks = targetGenre === 'all' 
      ? allTracks 
      : allTracks.filter(t => t.genre === targetGenre);
    if (genreTracks.length === 0) return;
    const randomIndex = Math.floor(Math.random() * genreTracks.length);
    playTrack(genreTracks[randomIndex]);
  };

  // Toggle or add all tracks in a genre to favorites
  const toggleGenreFavorites = (genreId) => {
    const targetGenre = genreId || activeGenre;
    const genreTracks = targetGenre === 'all' 
      ? allTracks 
      : allTracks.filter(t => t.genre === targetGenre);
    if (genreTracks.length === 0) return;
    
    const allInFav = genreTracks.every(t => favorites.includes(t.id));
    let updated;
    if (allInFav) {
      const idsToRemove = new Set(genreTracks.map(t => t.id));
      updated = favorites.filter(id => !idsToRemove.has(id));
    } else {
      const idsToAdd = genreTracks.map(t => t.id).filter(id => !favorites.includes(id));
      updated = [...favorites, ...idsToAdd];
    }
    setFavorites(updated);
    saveFavorites(updated);
  };

  const value = {
    tracks: allTracks,
    currentTrack,
    isPlaying,
    activeGenre,
    activeBroadcaster,
    activeInstrument,
    activeMood,
    activeEngine,
    volume,
    isMuted,
    currentTime,
    duration,
    favorites,
    history,
    recommendations,
    shuffle,
    repeatMode,
    audioError,
    broadcasters: BROADCASTERS,
    genres: GENRES,
    instruments: INSTRUMENTS,
    moods: MOODS,
    ytIframeRef,
    playTrack,
    togglePlay,
    nextTrack,
    prevTrack,
    seek,
    setVolume,
    toggleMute,
    toggleFavorite,
    selectGenre,
    selectBroadcaster,
    setActiveInstrument,
    setActiveMood,
    setActiveEngine,
    setShuffle,
    setRepeatMode,
    refreshRecommendations,
    addCustomTrack,
    saveYouTubeFavorite,
    userCategories,
    activeCategory,
    setActiveCategory,
    createUserCategory,
    deleteUserCategory,
    assignTrackCategory,
    playCategory,
    importLocalFiles,
    shuffleGenre,
    toggleGenreFavorites
  };

  return (
    <MusicContext.Provider value={value}>
      {children}
      {/* Background YouTube Audio/Video Player Iframe (Hidden / Persistent across all tabs) */}
      {currentTrack?.engine === 'youtube' && currentTrack?.youtubeId && (
        <div style={{ position: 'fixed', bottom: '-200px', right: '-200px', width: '100px', height: '100px', opacity: 0.01, pointerEvents: 'none', zIndex: -1 }}>
          <iframe
            ref={ytIframeRef}
            src={`https://www.youtube-nocookie.com/embed/${currentTrack.youtubeId}?enablejsapi=1&autoplay=1&origin=${typeof window !== 'undefined' ? window.location.origin : ''}`}
            title="YouTube Background Player"
            allow="autoplay; encrypted-media; compute-pressure"
            style={{ width: '100%', height: '100%', border: 0 }}
          />
        </div>
      )}
    </MusicContext.Provider>
  );
}

export function useMusic() {
  const context = useContext(MusicContext);
  if (!context) {
    throw new Error('useMusic must be used within a MusicProvider');
  }
  return context;
}
