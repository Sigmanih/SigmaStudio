// ==============================================================================
// MusicTab.jsx — Sigma Studio Modern Audio & FM Radio Stream Deck v11.0
// Clean Flat Architecture, Seamless Responsive Player Bar & Direct Stream Hub
// ==============================================================================

import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, Pause, SkipForward, SkipBack, Shuffle, Repeat, Volume2, VolumeX, 
  Heart, Sparkles, Search, Disc, Music, Radio, Flame, Clock, Compass, 
  ListMusic, Activity, Sliders, Headphones, Upload, Plus, Link, Video, 
  Layers, Filter, FolderPlus, Zap, CheckCircle2, SlidersHorizontal, 
  RadioTower, Waves, Building2, Globe, X, RotateCcw, PlayCircle
} from 'lucide-react';
import { useMusic } from './AudioContext';

const YoutubeIcon = ({ size = 18, color = '#ff0000' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17" fill="currentColor" fillOpacity="0.2"/>
    <polygon points="10 15 15 12 10 9 10 15" fill={color}/>
  </svg>
);

const EQ_PRESETS = [
  { id: 'flat', name: 'Flat', icon: '🎧' },
  { id: 'bass', name: 'Bass Boost', icon: '⚡' },
  { id: 'rock', name: 'Rock Punch', icon: '🎸' },
  { id: 'vocal', name: 'Vocal Clarity', icon: '🎷' },
  { id: 'acoustic', name: 'Acoustic Hall', icon: '🎹' }
];

export default function AudioStudioTab() {
  const isLight = false;

  const {
    tracks,
    currentTrack,
    isPlaying,
    activeGenre,
    activeBroadcaster,
    activeInstrument,
    activeMood,
    activeEngine,
    userCategories,
    activeCategory,
    setActiveCategory,
    createUserCategory,
    deleteUserCategory,
    assignTrackCategory,
    playCategory,
    volume,
    isMuted,
    currentTime,
    duration,
    favorites,
    history,
    recommendations,
    shuffle,
    repeatMode,
    broadcasters,
    genres,
    instruments,
    moods,
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
    addCustomTrack,
    importLocalFiles,
    shuffleGenre,
    toggleGenreFavorites
  } = useMusic();

  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('radio_fm'); // default to FM Radios
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isCatModalOpen, setIsCatModalOpen] = useState(false);
  const [catNameInput, setCatNameInput] = useState('');
  const [catIconInput, setCatIconInput] = useState('🎵');
  const [catColorInput, setCatColorInput] = useState('#00f2fe');
  const [customInputUrl, setCustomInputUrl] = useState('');
  const [customInputTitle, setCustomInputTitle] = useState('');
  const [customInputGenre, setCustomInputGenre] = useState('radio_fm');
  const [activeEq, setActiveEq] = useState('flat');

  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  // Compact Real-time Canvas Soundwave
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const width = canvas.width;
      const height = canvas.height;

      const numBars = 28;
      const barWidth = Math.max(2, (width / numBars) - 2);

      for (let i = 0; i < numBars; i++) {
        const factor = Math.sin(phase + i * 0.25) * 0.5 + 0.5;
        const barHeight = isPlaying 
          ? factor * (height * 0.85) * (volume + 0.2) + 2
          : 2;
        const x = i * (barWidth + 2);
        const y = height - barHeight;

        const gradient = ctx.createLinearGradient(0, height, 0, 0);
        if (isLight) {
          gradient.addColorStop(0, '#0284c7');
          gradient.addColorStop(1, '#6366f1');
        } else {
          gradient.addColorStop(0, '#00f2fe');
          gradient.addColorStop(1, '#4facfe');
        }

        ctx.fillStyle = gradient;
        ctx.fillRect(x, y, barWidth, barHeight);
      }

      if (isPlaying) phase += 0.08;
      animationFrameId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animationFrameId);
  }, [isPlaying, volume, isLight]);

  const formatTime = (secs) => {
    if (!secs || isNaN(secs)) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  // Filtered tracks calculation
  const filteredTracks = tracks.filter(t => {
    const matchesGenre = activeGenre === 'all' || t.genre === activeGenre;
    const matchesBroadcaster = activeBroadcaster === 'all' || t.broadcaster === activeBroadcaster;
    const matchesInst = activeInstrument === 'all' || (t.instruments && t.instruments.includes(activeInstrument));
    const matchesMood = activeMood === 'all' || (t.moods && t.moods.includes(activeMood));
    const matchesEngine = activeEngine === 'all' || (t.engine || 'radio') === activeEngine;
    const matchesCategory = activeCategory === 'all' || t.category === activeCategory || t.categoryId === activeCategory;
    const matchesTab = activeTab === 'all' || 
      (activeTab === 'radio_fm' && t.genre === 'radio_fm') ||
      (activeTab === 'youtube' && t.engine === 'youtube') ||
      (activeTab === 'local' && t.engine === 'local') ||
      (activeTab === 'favorites' && favorites.includes(t.id)) ||
      (activeTab === 'categories' && !!(t.category || t.categoryId)) ||
      (activeTab === 'history' && history.some(h => h.id === t.id));

    const q = searchQuery.toLowerCase().trim();
    const matchesSearch = !q || 
      t.title.toLowerCase().includes(q) ||
      t.artist.toLowerCase().includes(q) ||
      (t.broadcasterName && t.broadcasterName.toLowerCase().includes(q)) ||
      (t.frequency && t.frequency.toLowerCase().includes(q)) ||
      (t.tags && t.tags.some(tag => tag.toLowerCase().includes(q))) ||
      (t.instruments && t.instruments.some(inst => inst.toLowerCase().includes(q))) ||
      (t.moods && t.moods.some(mood => mood.toLowerCase().includes(q)));

    return matchesGenre && matchesBroadcaster && matchesInst && matchesMood && matchesEngine && matchesCategory && matchesTab && matchesSearch;
  });

  const currentGenreObj = genres.find(g => g.id === currentTrack?.genre) || genres[0];
  const isFav = currentTrack ? favorites.includes(currentTrack.id) : false;

  const hasActiveFilters = activeGenre !== 'all' || activeBroadcaster !== 'all' || activeInstrument !== 'all' || activeMood !== 'all' || activeEngine !== 'all' || activeCategory !== 'all' || !!searchQuery;

  const handleResetAllFilters = () => {
    selectGenre('all');
    selectBroadcaster('all');
    setActiveInstrument('all');
    setActiveMood('all');
    setActiveEngine('all');
    setActiveCategory('all');
    setSearchQuery('');
  };

  const handleAddTrackSubmit = (e) => {
    e.preventDefault();
    if (!customInputUrl.trim()) return;
    addCustomTrack({
      title: customInputTitle.trim() || 'Traccia Personalizzata',
      url: customInputUrl.trim(),
      genre: customInputGenre
    });
    setCustomInputUrl('');
    setCustomInputTitle('');
    setIsAddModalOpen(false);
  };

  const handleFileUpload = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      importLocalFiles(files);
      setIsAddModalOpen(false);
    }
  };

  return (
    <div className="music-tab-container" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
      padding: '20px 24px',
      maxWidth: '1600px',
      margin: '0 auto',
      color: isLight ? '#0f172a' : '#e2e8f0',
      minHeight: '100%',
      boxSizing: 'border-box'
    }}>
      
      {/* ============================================================================== */}
      {/* 1. TOP HEADER & STUDIO ACTIONS                                                 */}
      {/* ============================================================================== */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px',
        borderBottom: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.08)',
        paddingBottom: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '10px',
            background: isLight 
              ? 'linear-gradient(135deg, #0284c7 0%, #6366f1 100%)' 
              : 'linear-gradient(135deg, #00f2fe 0%, #4facfe 50%, #7928ca 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: isLight ? '0 4px 14px rgba(2, 132, 199, 0.25)' : '0 4px 16px rgba(0, 242, 254, 0.35)',
            flexShrink: 0
          }}>
            <RadioTower size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f8fafc', letterSpacing: '-0.3px' }}>
                Sigma Radio & Music Lounge
              </h1>
              <span style={{
                fontSize: '0.7rem',
                fontWeight: 800,
                color: isLight ? '#0284c7' : '#00f2fe',
                background: isLight ? 'rgba(2, 132, 199, 0.1)' : 'rgba(0, 242, 254, 0.12)',
                border: isLight ? '1px solid rgba(2, 132, 199, 0.3)' : '1px solid rgba(0, 242, 254, 0.3)',
                padding: '2px 8px',
                borderRadius: '6px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isLight ? '#0284c7' : '#00f2fe', animation: 'pulseDot 1.4s infinite' }} />
                LIVE STREAM
              </span>
            </div>
            <p style={{ margin: '2px 0 0', fontSize: '0.82rem', color: isLight ? '#475569' : '#94a3b8' }}>
              Dirette Radio FM Nazionali, YouTube Live, Brani Locali e Sintetizzatore 432Hz
            </p>
          </div>
        </div>

        {/* Top Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
            style={{
              background: isLight ? 'rgba(16, 185, 129, 0.1)' : 'rgba(74, 222, 128, 0.1)',
              border: isLight ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(74, 222, 128, 0.3)',
              color: isLight ? '#059669' : '#4ade80',
              borderRadius: '8px',
              padding: '7px 14px',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <FolderPlus size={15} />
            <span>Importa MP3</span>
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            multiple
            accept="audio/*"
            style={{ display: 'none' }}
          />

          <button
            onClick={() => setIsAddModalOpen(true)}
            style={{
              background: isLight ? 'linear-gradient(135deg, #0284c7, #0369a1)' : 'linear-gradient(135deg, #00f2fe, #4facfe)',
              border: 'none',
              color: '#ffffff',
              borderRadius: '8px',
              padding: '7px 16px',
              fontSize: '0.78rem',
              fontWeight: 800,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Plus size={15} />
            <span>Aggiungi Stream</span>
          </button>
        </div>
      </div>

      {/* ============================================================================== */}
      {/* 2. SLEEK UNCLIPPED MASTER PLAYER BAR (CLEAN & DIRECT)                          */}
      {/* ============================================================================== */}
      <div style={{
        background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.9)',
        border: isLight ? '1px solid rgba(0, 0, 0, 0.1)' : '1px solid rgba(0, 242, 254, 0.3)',
        borderRadius: '12px',
        padding: '14px 20px',
        display: 'grid',
        gridTemplateColumns: 'minmax(260px, 1.2fr) minmax(280px, 1fr) minmax(240px, 1fr)',
        gap: '20px',
        alignItems: 'center',
        boxShadow: isLight ? '0 4px 16px rgba(0,0,0,0.05)' : '0 6px 24px rgba(0,0,0,0.5)',
        position: 'sticky',
        top: '0',
        zIndex: 50,
        backdropFilter: 'blur(12px)'
      }}>
        
        {/* Left: Station Identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: 0 }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '8px',
            background: currentTrack?.cover || (isLight ? 'linear-gradient(135deg, #0284c7, #6366f1)' : 'linear-gradient(135deg, #00f2fe, #7928ca)'),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: isPlaying ? `0 0 12px ${currentGenreObj.color}88` : 'none'
          }}>
            {currentTrack?.engine === 'youtube' ? (
              <YoutubeIcon size={22} color="#ff0000" />
            ) : (
              <Disc size={22} color="#fff" />
            )}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px', flexWrap: 'wrap' }}>
              {currentTrack?.frequency && (
                <span style={{
                  fontSize: '0.66rem',
                  fontWeight: 900,
                  color: isLight ? '#0284c7' : '#00f2fe',
                  background: isLight ? 'rgba(2, 132, 199, 0.12)' : 'rgba(0, 242, 254, 0.15)',
                  padding: '1px 5px',
                  borderRadius: '4px',
                  fontFamily: 'monospace'
                }}>
                  {currentTrack.frequency}
                </span>
              )}
              {currentTrack?.broadcasterName && (
                <span style={{
                  fontSize: '0.64rem',
                  color: isLight ? '#475569' : '#cbd5e1',
                  background: isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.08)',
                  padding: '1px 5px',
                  borderRadius: '4px',
                  fontWeight: 700
                }}>
                  {currentTrack.broadcasterName}
                </span>
              )}
              {currentTrack?.isLive && (
                <span style={{
                  fontSize: '0.62rem',
                  color: '#ff0055',
                  background: 'rgba(255, 0, 85, 0.15)',
                  padding: '1px 5px',
                  borderRadius: '4px',
                  fontWeight: 900
                }}>
                  🔴 LIVE
                </span>
              )}
            </div>

            <div style={{
              fontSize: '1rem',
              fontWeight: 800,
              color: isLight ? '#0f172a' : '#f8fafc',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}>
              {currentTrack?.title || 'Seleziona una stazione'}
            </div>
            <div style={{ fontSize: '0.75rem', color: isLight ? '#64748b' : '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {currentTrack?.artist || 'Sigma Studio'}
            </div>
          </div>

          <button
            onClick={() => currentTrack && toggleFavorite(currentTrack.id)}
            style={{ background: 'transparent', border: 'none', color: isFav ? '#ef4444' : (isLight ? '#94a3b8' : '#64748b'), cursor: 'pointer', padding: '4px' }}
            title={isFav ? 'Rimuovi dai Preferiti' : 'Aggiungi ai Preferiti'}
          >
            <Heart size={18} fill={isFav ? '#ef4444' : 'none'} />
          </button>
        </div>

        {/* Center: Playback Controls & Timeline */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <button
              onClick={() => setShuffle(!shuffle)}
              style={{ background: 'transparent', border: 'none', color: shuffle ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#94a3b8' : '#64748b'), cursor: 'pointer', padding: '4px' }}
              title="Casuale"
            >
              <Shuffle size={16} />
            </button>

            <button
              onClick={prevTrack}
              style={{ background: 'transparent', border: 'none', color: isLight ? '#0f172a' : '#f8fafc', cursor: 'pointer', padding: '4px' }}
              title="Precedente"
            >
              <SkipBack size={18} />
            </button>

            <button
              onClick={togglePlay}
              style={{
                width: '42px',
                height: '42px',
                borderRadius: '50%',
                background: isLight ? 'linear-gradient(135deg, #0284c7, #0369a1)' : 'linear-gradient(135deg, #00f2fe, #4facfe)',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: isLight ? '0 2px 10px rgba(2, 132, 199, 0.3)' : '0 2px 12px rgba(0, 242, 254, 0.4)',
                transition: 'transform 0.15s ease'
              }}
              onMouseDown={(e) => e.currentTarget.style.transform = 'scale(0.92)'}
              onMouseUp={(e) => e.currentTarget.style.transform = 'scale(1)'}
              title={isPlaying ? 'Pausa' : 'Riproduci'}
            >
              {isPlaying ? <Pause size={18} fill="#ffffff" /> : <Play size={18} fill="#ffffff" style={{ marginLeft: '2px' }} />}
            </button>

            <button
              onClick={nextTrack}
              style={{ background: 'transparent', border: 'none', color: isLight ? '#0f172a' : '#f8fafc', cursor: 'pointer', padding: '4px' }}
              title="Successiva"
            >
              <SkipForward size={18} />
            </button>

            <button
              onClick={() => setRepeatMode(repeatMode === 'all' ? 'one' : repeatMode === 'one' ? 'off' : 'all')}
              style={{ background: 'transparent', border: 'none', color: repeatMode !== 'off' ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#94a3b8' : '#64748b'), cursor: 'pointer', padding: '4px', position: 'relative' }}
              title={`Ripeti: ${repeatMode}`}
            >
              <Repeat size={16} />
              {repeatMode === 'one' && (
                <span style={{ position: 'absolute', top: '1px', right: '1px', fontSize: '0.55rem', fontWeight: 900, color: isLight ? '#0284c7' : '#00f2fe' }}>1</span>
              )}
            </button>
          </div>

          {/* Timeline / Live Status */}
          {currentTrack?.duration > 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', maxWidth: '280px' }}>
              <span style={{ fontSize: '0.68rem', color: isLight ? '#64748b' : '#94a3b8', fontFamily: 'monospace' }}>{formatTime(currentTime)}</span>
              <input
                type="range"
                min="0"
                max={duration || 100}
                step="1"
                value={currentTime}
                onChange={(e) => seek(parseFloat(e.target.value))}
                style={{ flex: 1, height: '4px', accentColor: isLight ? '#0284c7' : '#00f2fe', cursor: 'pointer' }}
              />
              <span style={{ fontSize: '0.68rem', color: isLight ? '#64748b' : '#94a3b8', fontFamily: 'monospace' }}>{formatTime(duration)}</span>
            </div>
          ) : (
            <div style={{ fontSize: '0.7rem', color: isLight ? '#0284c7' : '#00f2fe', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Waves size={13} />
              <span>DIRETTA BROADCAST LIVE</span>
            </div>
          )}
        </div>

        {/* Right: Volume & Real-time Mini Spectrum */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '16px' }}>
          {/* Canvas Spectrum */}
          <div style={{ width: '100px', height: '24px' }}>
            <canvas ref={canvasRef} width={100} height={24} style={{ width: '100%', height: '100%' }} />
          </div>

          {/* Volume Control */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '120px' }}>
            <button
              onClick={toggleMute}
              style={{ background: 'transparent', border: 'none', color: isLight ? '#475569' : '#94a3b8', cursor: 'pointer', padding: '2px' }}
            >
              {isMuted || volume === 0 ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={isMuted ? 0 : volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              style={{ width: '70px', height: '4px', accentColor: isLight ? '#0284c7' : '#00f2fe', cursor: 'pointer' }}
            />
            <span style={{ fontSize: '0.72rem', color: isLight ? '#0f172a' : '#f8fafc', minWidth: '30px', textAlign: 'right', fontFamily: 'monospace', fontWeight: 700 }}>
              {isMuted ? '0%' : `${Math.round(volume * 100)}%`}
            </span>
          </div>
        </div>
      </div>

      {/* ============================================================================== */}
      {/* 3. BROADCASTER & NETWORK SELECTOR ROW                                         */}
      {/* ============================================================================== */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        flexWrap: 'wrap',
        background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.65)',
        border: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)',
        borderRadius: '10px',
        padding: '10px 14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '4px' }}>
          <Building2 size={15} color={isLight ? '#0284c7' : '#00f2fe'} />
          <span style={{ fontSize: '0.74rem', fontWeight: 800, textTransform: 'uppercase', color: isLight ? '#475569' : '#94a3b8' }}>
            ENTI:
          </span>
        </div>

        {broadcasters && broadcasters.map(bc => {
          const isSel = activeBroadcaster === bc.id;
          const count = bc.id === 'all' ? tracks.length : tracks.filter(t => t.broadcaster === bc.id).length;
          return (
            <button
              key={bc.id}
              onClick={() => selectBroadcaster(bc.id)}
              style={{
                background: isSel 
                  ? (isLight ? `${bc.color}25` : `${bc.color}35`) 
                  : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
                border: isSel 
                  ? `1px solid ${bc.color}` 
                  : (isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)'),
                color: isSel ? (isLight ? '#0f172a' : '#ffffff') : (isLight ? '#475569' : '#cbd5e1'),
                borderRadius: '8px',
                padding: '5px 10px',
                fontSize: '0.74rem',
                fontWeight: isSel ? 800 : 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <span>{bc.icon}</span>
              <span>{bc.name}</span>
              <span style={{ fontSize: '0.62rem', opacity: 0.8, fontWeight: 700 }}>({count})</span>
            </button>
          );
        })}
      </div>

      {/* ============================================================================== */}
      {/* 4. GENRES, INSTRUMENTS & MOOD FILTER BAR                                       */}
      {/* ============================================================================== */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.65)',
        border: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)',
        borderRadius: '10px',
        padding: '12px 14px'
      }}>
        {/* Row: Genres */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', color: isLight ? '#475569' : '#94a3b8', width: '80px' }}>
              GENERI:
            </span>
            <button
              onClick={() => selectGenre('all')}
              style={{
                background: activeGenre === 'all' 
                  ? (isLight ? 'rgba(2, 132, 199, 0.15)' : 'rgba(0, 242, 254, 0.2)') 
                  : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
                border: activeGenre === 'all' 
                  ? (isLight ? '1px solid #0284c7' : '1px solid #00f2fe') 
                  : (isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)'),
                color: activeGenre === 'all' ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '4px 9px',
                fontSize: '0.72rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Tutti
            </button>
            {genres.map(g => {
              const isSel = activeGenre === g.id;
              const count = tracks.filter(t => t.genre === g.id).length;
              return (
                <button
                  key={g.id}
                  onClick={() => selectGenre(isSel ? 'all' : g.id)}
                  style={{
                    background: isSel ? `${g.color}33` : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
                    border: isSel ? `1px solid ${g.color}` : (isLight ? '1px solid rgba(0, 0, 0, 0.06)' : '1px solid rgba(255, 255, 255, 0.06)'),
                    color: isSel ? g.color : (isLight ? '#334155' : '#cbd5e1'),
                    borderRadius: '6px',
                    padding: '4px 9px',
                    fontSize: '0.72rem',
                    fontWeight: isSel ? 800 : 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <span>{g.icon}</span>
                  <span>{g.name}</span>
                  <span style={{ fontSize: '0.62rem', opacity: 0.8 }}>({count})</span>
                </button>
              );
            })}
          </div>

          {/* Quick Actions for active genre: Shuffle & Favorite All */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
            <button
              onClick={() => shuffleGenre(activeGenre)}
              title="Riproduci casualmente un brano da questo genere"
              style={{
                background: isLight ? 'rgba(2, 132, 199, 0.12)' : 'rgba(0, 242, 254, 0.15)',
                border: isLight ? '1px solid rgba(2, 132, 199, 0.3)' : '1px solid rgba(0, 242, 254, 0.4)',
                color: isLight ? '#0284c7' : '#00f2fe',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.72rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Shuffle size={13} />
              <span>Mix Casuale {activeGenre !== 'all' ? `(${genres.find(g => g.id === activeGenre)?.name || activeGenre})` : ''}</span>
            </button>

            {activeGenre !== 'all' && (
              <button
                onClick={() => toggleGenreFavorites(activeGenre)}
                title="Aggiungi o rimuovi tutti i brani di questo genere dai preferiti"
                style={{
                  background: isLight ? 'rgba(236, 72, 153, 0.1)' : 'rgba(236, 72, 153, 0.18)',
                  border: '1px solid rgba(236, 72, 153, 0.4)',
                  color: '#ec4899',
                  borderRadius: '6px',
                  padding: '4px 10px',
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px'
                }}
              >
                <Heart size={13} fill={tracks.filter(t => t.genre === activeGenre).every(t => favorites.includes(t.id)) ? '#ec4899' : 'none'} />
                <span>Salva Genere</span>
              </button>
            )}
          </div>
        </div>

        {/* Row: Instruments */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', color: isLight ? '#475569' : '#94a3b8', width: '80px' }}>
            STRUMENTI:
          </span>
          <button
            onClick={() => setActiveInstrument('all')}
            style={{
              background: activeInstrument === 'all' 
                ? (isLight ? 'rgba(202, 138, 4, 0.15)' : 'rgba(250, 204, 21, 0.2)') 
                : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
              border: activeInstrument === 'all' 
                ? (isLight ? '1px solid #ca8a04' : '1px solid #facc15') 
                : (isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)'),
              color: activeInstrument === 'all' ? (isLight ? '#ca8a04' : '#facc15') : (isLight ? '#475569' : '#94a3b8'),
              borderRadius: '6px',
              padding: '3px 8px',
              fontSize: '0.7rem',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            Tutti
          </button>
          {instruments.map(inst => {
            const isSel = activeInstrument === inst.id;
            return (
              <button
                key={inst.id}
                onClick={() => setActiveInstrument(isSel ? 'all' : inst.id)}
                style={{
                  background: isSel ? `${inst.color}33` : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
                  border: isSel ? `1px solid ${inst.color}` : (isLight ? '1px solid rgba(0, 0, 0, 0.06)' : '1px solid rgba(255, 255, 255, 0.06)'),
                  color: isSel ? inst.color : (isLight ? '#334155' : '#cbd5e1'),
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  fontWeight: isSel ? 800 : 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <span>{inst.icon}</span>
                <span>{inst.name}</span>
              </button>
            );
          })}
        </div>

        {/* Row: Moods & Active Reset */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', color: isLight ? '#475569' : '#94a3b8', width: '80px' }}>
              MOOD:
            </span>
            <button
              onClick={() => setActiveMood('all')}
              style={{
                background: activeMood === 'all' 
                  ? (isLight ? 'rgba(16, 185, 129, 0.15)' : 'rgba(74, 222, 128, 0.2)') 
                  : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
                border: activeMood === 'all' 
                  ? (isLight ? '1px solid #10b981' : '1px solid #4ade80') 
                  : (isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)'),
                color: activeMood === 'all' ? (isLight ? '#10b981' : '#4ade80') : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '3px 8px',
                fontSize: '0.7rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              Tutti
            </button>
            {moods.map(m => {
              const isSel = activeMood === m.id;
              return (
                <button
                  key={m.id}
                  onClick={() => setActiveMood(isSel ? 'all' : m.id)}
                  style={{
                    background: isSel ? `${m.color}33` : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
                    border: isSel ? `1px solid ${m.color}` : (isLight ? '1px solid rgba(0, 0, 0, 0.06)' : '1px solid rgba(255, 255, 255, 0.06)'),
                    color: isSel ? m.color : (isLight ? '#334155' : '#cbd5e1'),
                    borderRadius: '6px',
                    padding: '3px 8px',
                    fontSize: '0.7rem',
                    fontWeight: isSel ? 800 : 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <span>{m.icon}</span>
                  <span>{m.name}</span>
                </button>
              );
            })}
          </div>

          {hasActiveFilters && (
            <button
              onClick={handleResetAllFilters}
              style={{
                background: isLight ? 'rgba(239, 68, 68, 0.1)' : 'rgba(239, 68, 68, 0.15)',
                border: '1px solid #ef4444',
                color: '#ef4444',
                borderRadius: '6px',
                padding: '3px 10px',
                fontSize: '0.72rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <RotateCcw size={12} />
              <span>Azzera Filtri ({filteredTracks.length} trovati)</span>
            </button>
          )}
        </div>

        {/* Row: Categorie Utente & Dynamic Genres */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          flexWrap: 'wrap',
          paddingTop: '8px',
          borderTop: isLight ? '1px dashed rgba(0,0,0,0.08)' : '1px dashed rgba(255,255,255,0.08)'
        }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', color: isLight ? '#0284c7' : '#00f2fe', width: '80px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <FolderPlus size={13} />
            CATEGORIE:
          </span>
          <button
            onClick={() => setActiveCategory('all')}
            style={{
              background: activeCategory === 'all' 
                ? (isLight ? 'rgba(2, 132, 199, 0.15)' : 'rgba(0, 242, 254, 0.2)') 
                : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
              border: activeCategory === 'all' 
                ? (isLight ? '1px solid #0284c7' : '1px solid #00f2fe') 
                : (isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)'),
              color: activeCategory === 'all' ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#475569' : '#94a3b8'),
              borderRadius: '6px',
              padding: '4px 9px',
              fontSize: '0.72rem',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            Tutte
          </button>
          {userCategories && userCategories.map(cat => {
            const isSel = activeCategory === cat.id;
            const count = tracks.filter(t => t.category === cat.id || t.categoryId === cat.id).length;
            return (
              <div key={cat.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                <button
                  onClick={() => setActiveCategory(isSel ? 'all' : cat.id)}
                  style={{
                    background: isSel ? `${cat.color || '#00f2fe'}33` : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.03)'),
                    border: isSel ? `1px solid ${cat.color || '#00f2fe'}` : (isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)'),
                    color: isSel ? (cat.color || '#00f2fe') : (isLight ? '#334155' : '#cbd5e1'),
                    borderRadius: '6px',
                    padding: '4px 9px',
                    fontSize: '0.72rem',
                    fontWeight: isSel ? 800 : 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <span>{cat.icon || '📁'}</span>
                  <span>{cat.name}</span>
                  <span style={{ fontSize: '0.62rem', opacity: 0.75 }}>({count})</span>
                </button>
                {isSel && count > 0 && (
                  <button
                    onClick={() => playCategory(cat.id)}
                    style={{
                      background: cat.color || '#00f2fe',
                      color: '#000000',
                      border: 'none',
                      borderRadius: '6px',
                      padding: '4px 7px',
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '3px'
                    }}
                    title={`Riproduci tutta la categoria ${cat.name}`}
                  >
                    <Play size={11} fill="#000" /> Play
                  </button>
                )}
                <button
                  onClick={() => {
                    if (window.confirm(`Vuoi eliminare la categoria "${cat.name}"?`)) {
                      deleteUserCategory(cat.id);
                    }
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: isLight ? '#94a3b8' : '#64748b',
                    cursor: 'pointer',
                    padding: '2px',
                    fontSize: '0.65rem'
                  }}
                  title="Elimina categoria"
                >
                  ✕
                </button>
              </div>
            );
          })}
          
          <button
            onClick={() => setIsCatModalOpen(true)}
            style={{
              background: isLight ? 'rgba(2, 132, 199, 0.08)' : 'rgba(0, 242, 254, 0.08)',
              border: isLight ? '1px dashed #0284c7' : '1px dashed #00f2fe',
              color: isLight ? '#0284c7' : '#00f2fe',
              borderRadius: '6px',
              padding: '4px 9px',
              fontSize: '0.72rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Plus size={13} /> + Nuova Categoria
          </button>
        </div>
      </div>

      {/* ============================================================================== */}
      {/* 5. RECOMMENDATIONS (AI TASTE PROFILER)                                         */}
      {/* ============================================================================== */}
      {recommendations.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={16} color={isLight ? '#0284c7' : '#00f2fe'} />
            <span style={{ fontSize: '0.86rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f8fafc' }}>
              Consigliati per Te
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: '12px'
          }}>
            {recommendations.slice(0, 5).map(rec => {
              const gObj = genres.find(g => g.id === rec.genre) || genres[0];
              const isCurrent = currentTrack?.id === rec.id;

              return (
                <div
                  key={rec.id}
                  onClick={() => playTrack(rec)}
                  style={{
                    background: isCurrent 
                      ? (isLight ? 'rgba(2, 132, 199, 0.12)' : 'rgba(0, 242, 254, 0.12)') 
                      : (isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.65)'),
                    border: isCurrent 
                      ? (isLight ? '1.5px solid #0284c7' : '1.5px solid #00f2fe') 
                      : (isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)'),
                    borderRadius: '10px',
                    padding: '10px 12px',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.62rem', fontWeight: 800, color: gObj.color, background: `${gObj.color}22`, padding: '2px 5px', borderRadius: '4px' }}>
                      {gObj.icon} {gObj.name}
                    </span>
                    {rec.frequency && (
                      <span style={{ fontSize: '0.62rem', color: isLight ? '#0284c7' : '#00f2fe', fontWeight: 800 }}>
                        {rec.frequency}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {rec.title}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: isLight ? '#64748b' : '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {rec.artist}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ============================================================================== */}
      {/* 6. MAIN STATIONS CATALOGUE & PLAYLISTS TABLE                                   */}
      {/* ============================================================================== */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        
        {/* Navigation Tabs & Search */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{
            display: 'flex',
            gap: '4px',
            background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)',
            padding: '3px',
            borderRadius: '8px',
            border: isLight ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.06)'
          }}>
            <button
              onClick={() => setActiveTab('radio_fm')}
              style={{
                background: activeTab === 'radio_fm' ? (isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.2)') : 'transparent',
                border: activeTab === 'radio_fm' ? (isLight ? '1px solid #0284c7' : '1px solid #00f2fe') : '1px solid transparent',
                color: activeTab === 'radio_fm' ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Radio size={14} />
              <span>Radio FM ({tracks.filter(t => t.genre === 'radio_fm').length})</span>
            </button>

            <button
              onClick={() => setActiveTab('all')}
              style={{
                background: activeTab === 'all' ? (isLight ? '#ffffff' : 'rgba(0, 242, 254, 0.2)') : 'transparent',
                border: activeTab === 'all' ? (isLight ? '1px solid #0284c7' : '1px solid #00f2fe') : '1px solid transparent',
                color: activeTab === 'all' ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              Tutti ({tracks.length})
            </button>

            <button
              onClick={() => setActiveTab('youtube')}
              style={{
                background: activeTab === 'youtube' ? 'rgba(239, 68, 68, 0.15)' : 'transparent',
                border: activeTab === 'youtube' ? '1px solid #ef4444' : '1px solid transparent',
                color: activeTab === 'youtube' ? '#ef4444' : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <YoutubeIcon size={14} />
              <span>YouTube</span>
            </button>

            <button
              onClick={() => setActiveTab('local')}
              style={{
                background: activeTab === 'local' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                border: activeTab === 'local' ? '1px solid #10b981' : '1px solid transparent',
                color: activeTab === 'local' ? '#10b981' : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <FolderPlus size={14} />
              <span>File Locali</span>
            </button>

            <button
              onClick={() => setActiveTab('categories')}
              style={{
                background: activeTab === 'categories' ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                border: activeTab === 'categories' ? '1px solid #00f2fe' : '1px solid transparent',
                color: activeTab === 'categories' ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <FolderPlus size={14} />
              <span>Categorie ({userCategories.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('favorites')}
              style={{
                background: activeTab === 'favorites' ? 'rgba(236, 72, 153, 0.15)' : 'transparent',
                border: activeTab === 'favorites' ? '1px solid #ec4899' : '1px solid transparent',
                color: activeTab === 'favorites' ? '#ec4899' : (isLight ? '#475569' : '#94a3b8'),
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              ❤️ Preferiti ({favorites.length})
            </button>
          </div>

          {/* Quick Search */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.8)',
            border: isLight ? '1px solid rgba(0, 0, 0, 0.12)' : '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '8px',
            padding: '6px 12px',
            minWidth: '240px'
          }}>
            <Search size={14} color={isLight ? '#64748b' : '#94a3b8'} />
            <input
              type="text"
              placeholder="Cerca stazione o artista..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: isLight ? '#0f172a' : '#fff',
                fontSize: '0.8rem',
                outline: 'none',
                width: '100%'
              }}
            />
          </div>
        </div>

        {/* Stations Table */}
        <div style={{
          background: isLight ? '#ffffff' : 'rgba(15, 23, 42, 0.65)',
          border: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: '10px',
          overflow: 'hidden'
        }}>
          {filteredTracks.length === 0 ? (
            <div style={{ padding: '36px 20px', textAlign: 'center', color: isLight ? '#94a3b8' : '#64748b' }}>
              <Music size={32} style={{ margin: '0 auto 8px', opacity: 0.5 }} />
              <div style={{ fontSize: '0.88rem' }}>Nessuna stazione trovata con i filtri attuali.</div>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: isLight ? '1px solid rgba(0, 0, 0, 0.06)' : '1px solid rgba(255, 255, 255, 0.06)', color: isLight ? '#475569' : '#94a3b8', textAlign: 'left' }}>
                  <th style={{ padding: '10px 14px', width: '40px' }}>#</th>
                  <th style={{ padding: '10px 14px' }}>STAZIONE / CANALE</th>
                  <th style={{ padding: '10px 14px' }}>ENTE BROADCASTER</th>
                  <th style={{ padding: '10px 14px' }}>CATEGORIA</th>
                  <th style={{ padding: '10px 14px' }}>GENERE & STRUMENTI</th>
                  <th style={{ padding: '10px 14px', textAlign: 'right' }}>STATO</th>
                  <th style={{ padding: '10px 14px', width: '50px', textAlign: 'center' }}>SALVA</th>
                </tr>
              </thead>
              <tbody>
                {filteredTracks.map((t, idx) => {
                  const isCur = currentTrack?.id === t.id;
                  const isF = favorites.includes(t.id);
                  const gObj = genres.find(g => g.id === t.genre) || genres[0];

                  return (
                    <tr
                      key={t.id + idx}
                      onClick={() => playTrack(t)}
                      style={{
                        borderBottom: isLight ? '1px solid rgba(0, 0, 0, 0.04)' : '1px solid rgba(255, 255, 255, 0.03)',
                        background: isCur 
                          ? (isLight ? 'rgba(2, 132, 199, 0.1)' : 'rgba(0, 242, 254, 0.1)') 
                          : 'transparent',
                        cursor: 'pointer',
                        transition: 'background 0.12s ease'
                      }}
                      onMouseEnter={(e) => { if (!isCur) e.currentTarget.style.background = isLight ? 'rgba(0, 0, 0, 0.02)' : 'rgba(255, 255, 255, 0.03)'; }}
                      onMouseLeave={(e) => { if (!isCur) e.currentTarget.style.background = 'transparent'; }}
                    >
                      <td style={{ padding: '10px 14px', color: isCur ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#64748b' : '#64748b'), fontWeight: 800 }}>
                        {isCur && isPlaying ? (
                          <span style={{ color: isLight ? '#0284c7' : '#00f2fe' }}>▶</span>
                        ) : (
                          idx + 1
                        )}
                      </td>
                      <td style={{ padding: '10px 14px', fontWeight: isCur ? 800 : 600, color: isCur ? (isLight ? '#0284c7' : '#00f2fe') : (isLight ? '#0f172a' : '#f1f5f9') }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {t.frequency && (
                            <span style={{
                              fontSize: '0.64rem',
                              fontWeight: 900,
                              color: isLight ? '#0284c7' : '#00f2fe',
                              background: isLight ? 'rgba(2, 132, 199, 0.12)' : 'rgba(0, 242, 254, 0.15)',
                              border: isLight ? '1px solid rgba(2, 132, 199, 0.3)' : '1px solid rgba(0, 242, 254, 0.3)',
                              padding: '1px 5px',
                              borderRadius: '4px'
                            }}>
                              {t.frequency}
                            </span>
                          )}
                          {t.engine === 'youtube' && <YoutubeIcon size={14} color="#ff4444" />}
                          {t.engine === 'local' && <FolderPlus size={14} color={isLight ? '#059669' : '#4ade80'} />}
                          <span>{t.title}</span>
                        </div>
                      </td>
                      <td style={{ padding: '10px 14px', color: isLight ? '#475569' : '#94a3b8' }}>
                        {t.broadcasterName || t.artist}
                      </td>
                      <td style={{ padding: '10px 14px' }} onClick={(e) => e.stopPropagation()}>
                        <select
                          value={t.category || t.categoryId || ''}
                          onChange={(e) => assignTrackCategory(t.id, e.target.value)}
                          style={{
                            background: isLight ? '#f1f5f9' : 'rgba(255, 255, 255, 0.06)',
                            border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.1)',
                            color: isLight ? '#0f172a' : '#f8fafc',
                            borderRadius: '6px',
                            padding: '3px 8px',
                            fontSize: '0.7rem',
                            cursor: 'pointer',
                            maxWidth: '130px'
                          }}
                        >
                          <option value="">(Nessuna)</option>
                          {userCategories.map(c => (
                            <option key={c.id} value={c.id}>
                              {c.icon} {c.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          <span style={{
                            fontSize: '0.64rem',
                            fontWeight: 700,
                            color: gObj.color,
                            padding: '1px 6px',
                            borderRadius: '4px',
                            background: `${gObj.color}18`
                          }}>
                            {gObj.name}
                          </span>
                          {t.instruments && t.instruments.map(inst => {
                            const instObj = instruments.find(i => i.id === inst);
                            return (
                              <span key={inst} style={{
                                fontSize: '0.62rem',
                                color: isLight ? '#475569' : '#94a3b8',
                                background: isLight ? 'rgba(0, 0, 0, 0.04)' : 'rgba(255, 255, 255, 0.04)',
                                padding: '1px 4px',
                                borderRadius: '3px'
                              }}>
                                {instObj?.icon}
                              </span>
                            );
                          })}
                        </div>
                      </td>
                      <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                        {t.duration > 0 ? (
                          <span style={{ color: isLight ? '#64748b' : '#64748b', fontFamily: 'monospace' }}>{formatTime(t.duration)}</span>
                        ) : (
                          <span style={{ color: '#ff0055', fontWeight: 800, fontSize: '0.68rem' }}>🔴 DIRETTA</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleFavorite(t.id);
                          }}
                          style={{ background: 'transparent', border: 'none', color: isF ? '#ef4444' : (isLight ? '#94a3b8' : '#64748b'), cursor: 'pointer', padding: '4px' }}
                        >
                          <Heart size={15} fill={isF ? '#ef4444' : 'none'} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ============================================================================== */}
      {/* MODAL: ADD CUSTOM STREAM / YOUTUBE URL                                         */}
      {/* ============================================================================== */}
      {isAddModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.65)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          animation: 'fadeIn 0.2s ease'
        }}>
          <div style={{
            background: isLight ? '#ffffff' : '#0f172a',
            border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(0, 242, 254, 0.3)',
            borderRadius: '12px',
            padding: '24px',
            width: '460px',
            maxWidth: '92%',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.4)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            color: isLight ? '#0f172a' : '#ffffff'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Link size={18} color={isLight ? '#0284c7' : '#00f2fe'} />
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800 }}>Aggiungi Flusso Audio o YouTube</h3>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: isLight ? '#64748b' : '#8b8fa3', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddTrackSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '0.75rem', color: isLight ? '#475569' : '#94a3b8', display: 'block', marginBottom: '4px' }}>
                  URL Streaming (YouTube o Web Radio MP3/AAC)
                </label>
                <input
                  type="text"
                  placeholder="https://www.youtube.com/watch?v=... o http://stream.url:8000"
                  value={customInputUrl}
                  onChange={(e) => setCustomInputUrl(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.05)',
                    border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.1)',
                    color: isLight ? '#0f172a' : '#fff',
                    fontSize: '0.82rem',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: isLight ? '#475569' : '#94a3b8', display: 'block', marginBottom: '4px' }}>
                  Nome Canale / Titolo
                </label>
                <input
                  type="text"
                  placeholder="Nome della stazione o brano"
                  value={customInputTitle}
                  onChange={(e) => setCustomInputTitle(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: isLight ? '#ffffff' : 'rgba(255, 255, 255, 0.05)',
                    border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.1)',
                    color: isLight ? '#0f172a' : '#fff',
                    fontSize: '0.82rem',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: isLight ? '#475569' : '#94a3b8', display: 'block', marginBottom: '4px' }}>
                  Genere Associato
                </label>
                <select
                  value={customInputGenre}
                  onChange={(e) => setCustomInputGenre(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: isLight ? '#ffffff' : '#1e293b',
                    border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.1)',
                    color: isLight ? '#0f172a' : '#fff',
                    fontSize: '0.82rem',
                    boxSizing: 'border-box'
                  }}
                >
                  {genres.map(g => (
                    <option key={g.id} value={g.id}>
                      {g.icon} {g.name}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  style={{
                    background: 'transparent',
                    border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.1)',
                    color: isLight ? '#475569' : '#cbd5e1',
                    borderRadius: '8px',
                    padding: '8px 14px',
                    cursor: 'pointer',
                    fontSize: '0.78rem'
                  }}
                >
                  Annulla
                </button>
                <button
                  type="submit"
                  style={{
                    background: isLight ? 'linear-gradient(135deg, #0284c7, #0369a1)' : 'linear-gradient(135deg, #00f2fe, #4facfe)',
                    border: 'none',
                    color: '#ffffff',
                    borderRadius: '8px',
                    padding: '8px 18px',
                    fontWeight: 800,
                    cursor: 'pointer',
                    fontSize: '0.78rem'
                  }}
                >
                  Aggiungi
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================================== */}
      {/* MODAL: CREATE CUSTOM CATEGORY / GENRE                                         */}
      {/* ============================================================================== */}
      {isCatModalOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            background: isLight ? '#ffffff' : '#0f172a',
            border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(0, 242, 254, 0.4)',
            borderRadius: '16px',
            padding: '24px 28px',
            width: '90%',
            maxWidth: '440px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>✨</span> Crea Nuova Categoria / Genere
              </h3>
              <button
                onClick={() => setIsCatModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: isLight ? '#64748b' : '#94a3b8', cursor: 'pointer', fontSize: '1rem' }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700, color: isLight ? '#475569' : '#94a3b8' }}>
                Nome Categoria / Playlist
              </label>
              <input
                type="text"
                value={catNameInput}
                onChange={(e) => setCatNameInput(e.target.value)}
                placeholder="es. Cyberpunk Coding, Rock Anni 90, Gaming Beats..."
                style={{
                  background: isLight ? '#f8fafc' : '#1e293b',
                  border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '10px 12px',
                  color: isLight ? '#0f172a' : '#ffffff',
                  fontSize: '0.85rem'
                }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, color: isLight ? '#475569' : '#94a3b8' }}>
                  Icona Emoji
                </label>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {['🎵', '🎧', '⚡', '🧠', '☕', '🎸', '🎹', '🌆', '🌌', '🚀', '🔥', '💎'].map(emoji => (
                    <button
                      key={emoji}
                      onClick={() => setCatIconInput(emoji)}
                      style={{
                        background: catIconInput === emoji ? (isLight ? 'rgba(2, 132, 199, 0.2)' : 'rgba(0, 242, 254, 0.25)') : 'transparent',
                        border: catIconInput === emoji ? '1px solid #00f2fe' : '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '6px',
                        padding: '4px 8px',
                        fontSize: '0.9rem',
                        cursor: 'pointer'
                      }}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 700, color: isLight ? '#475569' : '#94a3b8' }}>
                  Colore Accent
                </label>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {['#00f2fe', '#38bdf8', '#818cf8', '#ec4899', '#ef4444', '#10b981', '#f59e0b', '#c084fc'].map(color => (
                    <button
                      key={color}
                      onClick={() => setCatColorInput(color)}
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: color,
                        border: catColorInput === color ? '2.5px solid #ffffff' : 'none',
                        cursor: 'pointer'
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
              <button
                onClick={() => setIsCatModalOpen(false)}
                style={{
                  background: 'transparent',
                  border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.15)',
                  color: isLight ? '#475569' : '#cbd5e1',
                  borderRadius: '8px',
                  padding: '8px 16px',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                Annulla
              </button>
              <button
                onClick={() => {
                  if (catNameInput.trim()) {
                    createUserCategory({
                      name: catNameInput.trim(),
                      icon: catIconInput,
                      color: catColorInput
                    });
                    setCatNameInput('');
                    setIsCatModalOpen(false);
                  }
                }}
                disabled={!catNameInput.trim()}
                style={{
                  background: 'linear-gradient(135deg, #00f2fe, #4facfe)',
                  border: 'none',
                  color: '#000000',
                  borderRadius: '8px',
                  padding: '8px 20px',
                  fontSize: '0.8rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  opacity: catNameInput.trim() ? 1 : 0.5
                }}
              >
                Crea Categoria
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulseDot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.3; transform: scale(1.3); }
        }
      `}</style>
    </div>
  );
}
