// ==============================================================================
// MusicFloatingWidget.jsx — Quick Floating Mini-Player & Speed-Dial Hi-Fi Tool
// Adaptive Light/Dark Theme Support
// ==============================================================================

import React, { useState } from 'react';
import { 
  Play, Pause, SkipForward, SkipBack, Volume2, VolumeX, 
  Heart, Music, Sparkles, Radio, ExternalLink, ChevronUp, ChevronDown, 
import { useMusic } from './AudioContext';

export default function AudioFloatingWidget({ onOpenTab, theme: propTheme }) {
  const isLight = propTheme === 'light';

  const {
    currentTrack,
    isPlaying,
    activeGenre,
    genres,
    volume,
    isMuted,
    favorites,
    togglePlay,
    nextTrack,
    prevTrack,
    setVolume,
    toggleMute,
    toggleFavorite,
    selectGenre
  } = useMusic();

  const [expanded, setExpanded] = useState(false);

  if (!currentTrack) return null;

  const currentGenreObj = genres.find(g => g.id === currentTrack.genre) || genres[0];
  const isFav = favorites.includes(currentTrack.id);

  return (
    <div 
      className="music-floating-widget"
      style={{
        background: isLight 
          ? 'linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(241, 245, 249, 0.95))' 
          : 'linear-gradient(135deg, rgba(8, 12, 22, 0.96), rgba(15, 23, 42, 0.94))',
        border: isLight ? '1px solid rgba(2, 132, 199, 0.25)' : '1px solid rgba(0, 242, 254, 0.35)',
        borderRadius: '14px',
        padding: '10px 14px',
        boxShadow: isLight 
          ? '0 12px 36px rgba(0, 0, 0, 0.12), 0 0 20px rgba(2, 132, 199, 0.1)' 
          : '0 12px 36px rgba(0, 0, 0, 0.65), 0 0 24px rgba(0, 242, 254, 0.15)',
        backdropFilter: 'blur(16px)',
        color: isLight ? '#0f172a' : '#e2e8f0',
        userSelect: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        minWidth: '280px',
        maxWidth: '360px',
        transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)'
      }}
    >
      {/* Header with Genre and Expand */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.95rem' }}>{currentGenreObj.icon}</span>
          <span 
            style={{ 
              fontSize: '0.68rem', 
              fontWeight: 800, 
              letterSpacing: '0.6px', 
              textTransform: 'uppercase',
              color: currentGenreObj.color,
              padding: '1px 6px',
              borderRadius: '6px',
              background: `${currentGenreObj.color}22`,
              border: `1px solid ${currentGenreObj.color}44`
            }}
          >
            {currentGenreObj.name}
          </span>
          {currentTrack.frequency && (
            <span style={{
              fontSize: '0.64rem',
              fontWeight: 900,
              color: isLight ? '#0284c7' : '#00f2fe',
              background: isLight ? 'rgba(2, 132, 199, 0.12)' : 'rgba(0, 242, 254, 0.15)',
              border: isLight ? '1px solid rgba(2, 132, 199, 0.35)' : '1px solid rgba(0, 242, 254, 0.35)',
              padding: '1px 5px',
              borderRadius: '4px'
            }}>
              {currentTrack.frequency}
            </span>
          )}
          {isPlaying && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '2px', marginLeft: '4px' }}>
              <span className="eq-bar eq-1" style={{ background: isLight ? '#0284c7' : '#00f2fe' }} />
              <span className="eq-bar eq-2" style={{ background: isLight ? '#0284c7' : '#00f2fe' }} />
              <span className="eq-bar eq-3" style={{ background: isLight ? '#0284c7' : '#00f2fe' }} />
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {onOpenTab && (
            <button
              onClick={() => onOpenTab({ name: '📻 Hi-Fi & Radio FM' }, 'music')}
              title="Apri Tab Radio & Musica Completa"
              style={{
                background: 'transparent',
                border: 'none',
                color: isLight ? '#64748b' : '#8b8fa3',
                cursor: 'pointer',
                padding: '4px',
                display: 'flex',
                alignItems: 'center',
                borderRadius: '4px',
                transition: 'color 0.15s ease'
              }}
              onMouseEnter={(e) => e.currentTarget.style.color = isLight ? '#0284c7' : '#00f2fe'}
              onMouseLeave={(e) => e.currentTarget.style.color = isLight ? '#64748b' : '#8b8fa3'}
            >
              <ExternalLink size={13} />
            </button>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'transparent',
              border: 'none',
              color: isLight ? '#64748b' : '#8b8fa3',
              cursor: 'pointer',
              padding: '2px',
              display: 'flex'
            }}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Track Info & Controls Row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
        {/* Cover / Vinyl Art */}
        <div 
          style={{
            width: '38px',
            height: '38px',
            borderRadius: '8px',
            background: currentTrack.cover || (isLight ? 'linear-gradient(135deg, #0284c7, #6366f1)' : 'linear-gradient(135deg, #00f2fe, #bc8cff)'),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: isPlaying 
              ? (isLight ? '0 0 12px rgba(2, 132, 199, 0.35)' : '0 0 14px rgba(0, 242, 254, 0.45)') 
              : 'none',
            transition: 'box-shadow 0.3s ease'
          }}
        >
          <Music size={16} color="#fff" />
        </div>

        {/* Title & Artist */}
        <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
          <div 
            style={{ 
              fontSize: '0.82rem', 
              fontWeight: 800, 
              color: isLight ? '#0f172a' : '#f8fafc',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}
            title={currentTrack.title}
          >
            {currentTrack.title}
          </div>
          <div 
            style={{ 
              fontSize: '0.68rem', 
              color: isLight ? '#475569' : '#94a3b8',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}
          >
            {currentTrack.artist}
          </div>
        </div>

        {/* Compact Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
          <button
            onClick={() => toggleFavorite(currentTrack.id)}
            style={{
              background: 'transparent',
              border: 'none',
              color: isFav ? '#ef4444' : (isLight ? '#94a3b8' : '#64748b'),
              cursor: 'pointer',
              padding: '4px',
              display: 'flex'
            }}
            title={isFav ? 'Rimuovi dai Preferiti' : 'Aggiungi ai Preferiti'}
          >
            <Heart size={14} fill={isFav ? '#ef4444' : 'none'} />
          </button>

          <button
            onClick={prevTrack}
            style={{ background: 'transparent', border: 'none', color: isLight ? '#334155' : '#cbd5e1', cursor: 'pointer', padding: '4px', display: 'flex' }}
            title="Traccia precedente"
          >
            <SkipBack size={14} />
          </button>

          <button
            onClick={togglePlay}
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: isPlaying 
                ? (isLight ? 'linear-gradient(135deg, #0284c7, #0369a1)' : 'linear-gradient(135deg, #00f2fe, #4facfe)') 
                : (isLight ? 'linear-gradient(135deg, #38bdf8, #0ea5e9)' : 'linear-gradient(135deg, #38bdf8, #0ea5e9)'),
              border: 'none',
              color: '#ffffff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: isLight ? '0 2px 10px rgba(2, 132, 199, 0.35)' : '0 2px 12px rgba(0, 242, 254, 0.45)',
              transition: 'transform 0.15s ease'
            }}
            onMouseDown={(e) => e.currentTarget.style.transform = 'scale(0.92)'}
            onMouseUp={(e) => e.currentTarget.style.transform = 'scale(1)'}
            title={isPlaying ? 'Pausa' : 'Riproduci'}
          >
            {isPlaying ? <Pause size={15} fill="#ffffff" /> : <Play size={15} fill="#ffffff" style={{ marginLeft: '2px' }} />}
          </button>

          <button
            onClick={nextTrack}
            style={{ background: 'transparent', border: 'none', color: isLight ? '#334155' : '#cbd5e1', cursor: 'pointer', padding: '4px', display: 'flex' }}
            title="Prossima traccia"
          >
            <SkipForward size={14} />
          </button>
        </div>
      </div>

      {/* Expanded Quick Genre & Volume Panel */}
      {expanded && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          paddingTop: '6px',
          borderTop: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.08)',
          animation: 'fadeIn 0.2s ease'
        }}>
          {/* Quick Genre Selector */}
          <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '2px' }}>
            {genres.slice(0, 6).map(g => (
              <button
                key={g.id}
                onClick={() => selectGenre(g.id)}
                style={{
                  background: activeGenre === g.id ? `${g.color}33` : (isLight ? 'rgba(0, 0, 0, 0.03)' : 'rgba(255, 255, 255, 0.04)'),
                  border: activeGenre === g.id ? `1px solid ${g.color}` : (isLight ? '1px solid rgba(0, 0, 0, 0.06)' : '1px solid rgba(255, 255, 255, 0.06)'),
                  color: activeGenre === g.id ? g.color : (isLight ? '#334155' : '#cbd5e1'),
                  borderRadius: '6px',
                  padding: '3px 7px',
                  fontSize: '0.64rem',
                  fontWeight: 700,
                  whiteSpace: 'nowrap',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '3px'
                }}
              >
                <span>{g.icon}</span>
                <span>{g.name}</span>
              </button>
            ))}
          </div>

          {/* Volume Slider Row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={toggleMute}
              style={{ background: 'transparent', border: 'none', color: isLight ? '#64748b' : '#8b8fa3', cursor: 'pointer', padding: '2px' }}
            >
              {isMuted || volume === 0 ? <VolumeX size={13} /> : <Volume2 size={13} />}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={isMuted ? 0 : volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              style={{
                flex: 1,
                height: '4px',
                accentColor: isLight ? '#0284c7' : '#00f2fe',
                cursor: 'pointer'
              }}
            />
            <span style={{ fontSize: '0.64rem', color: isLight ? '#64748b' : '#8b8fa3', minWidth: '26px', textAlign: 'right', fontFamily: 'monospace' }}>
              {isMuted ? '0%' : `${Math.round(volume * 100)}%`}
            </span>
          </div>
        </div>
      )}

      {/* Mini Equalizer animation styles */}
      <style>{`
        .eq-bar {
          width: 2px;
          height: 10px;
          border-radius: 1px;
          display: inline-block;
          animation: eqAnim 0.8s ease-in-out infinite alternate;
        }
        .eq-1 { animation-delay: 0.1s; height: 6px; }
        .eq-2 { animation-delay: 0.3s; height: 11px; }
        .eq-3 { animation-delay: 0.5s; height: 8px; }
        @keyframes eqAnim {
          0% { transform: scaleY(0.3); }
          100% { transform: scaleY(1.2); }
        }
      `}</style>
    </div>
  );
}
