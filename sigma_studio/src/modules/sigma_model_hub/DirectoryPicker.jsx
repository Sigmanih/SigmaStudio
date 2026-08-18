import React, { useState, useEffect, useCallback } from 'react';
import { Folder, FolderOpen, ArrowUp, HardDrive, Check, X } from 'lucide-react';

/**
 * Browses the server's filesystem to choose a models directory.
 *
 * A server-side browser rather than a file input: a browser only ever reveals
 * the name of a chosen folder, never its absolute path, and this setting needs
 * an absolute path on the machine the engine runs on.
 */
export default function DirectoryPicker({ initialPath, isLight, onSelect, onClose }) {
  const [current, setCurrent] = useState('');
  const [parent, setParent] = useState(null);
  const [entries, setEntries] = useState([]);
  const [roots, setRoots] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const bg = isLight ? '#ffffff' : '#131722';
  const border = isLight ? '1px solid #e5e7eb' : '1px solid rgba(255,255,255,0.1)';
  const textPrimary = isLight ? '#111827' : '#e5e7eb';
  const textMuted = isLight ? '#6b7280' : '#9ca3af';
  const rowHover = isLight ? '#f3f4f6' : 'rgba(255,255,255,0.05)';

  const browse = useCallback(async (path) => {
    setLoading(true);
    try {
      const url = path
        ? '/api/models/browse?path=' + encodeURIComponent(path)
        : '/api/models/browse';
      const res = await fetch(url);
      const json = await res.json();
      if (json.success) {
        setCurrent(json.current);
        setParent(json.parent);
        setEntries(json.entries || []);
        setRoots(json.roots || []);
        setError(null);
      } else {
        setError(json.error || 'Cartella non leggibile.');
      }
    } catch (e) {
      setError('Impossibile contattare il server: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { browse(initialPath); }, [browse, initialPath]);

  const row = {
    display: 'flex', alignItems: 'center', gap: '8px',
    padding: '7px 10px', borderRadius: '8px', cursor: 'pointer',
    fontSize: '0.8rem', color: textPrimary,
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: 'min(620px, 92vw)', maxHeight: '78vh', background: bg,
          border, borderRadius: '14px', padding: '18px',
          display: 'flex', flexDirection: 'column', gap: '12px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong style={{ color: textPrimary, fontSize: '0.95rem' }}>
            <FolderOpen size={15} style={{ verticalAlign: '-2px', marginRight: '6px' }} />
            Scegli la cartella dei modelli
          </strong>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: textMuted }}
          >
            <X size={17} />
          </button>
        </div>

        <code
          style={{
            fontSize: '0.74rem', color: textMuted, wordBreak: 'break-all',
            padding: '7px 10px', borderRadius: '7px',
            background: isLight ? '#f9fafb' : 'rgba(0,0,0,0.3)',
          }}
        >
          {current || '—'}
        </code>

        {roots.length > 0 && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {roots.map(r => (
              <button
                key={r}
                onClick={() => browse(r)}
                style={{
                  padding: '4px 10px', borderRadius: '6px', border,
                  background: 'transparent', color: textMuted,
                  fontSize: '0.72rem', cursor: 'pointer',
                }}
              >
                <HardDrive size={11} style={{ verticalAlign: '-1px', marginRight: '4px' }} />
                {r}
              </button>
            ))}
          </div>
        )}

        {error && (
          <div
            style={{
              padding: '10px 12px', borderRadius: '8px', fontSize: '0.78rem',
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.35)', color: '#ef4444',
            }}
          >
            {error}
          </div>
        )}

        <div style={{ overflowY: 'auto', flex: 1, minHeight: '180px' }}>
          {loading ? (
            <div style={{ color: textMuted, fontSize: '0.8rem', padding: '10px' }}>
              Lettura in corso...
            </div>
          ) : (
            <>
              {parent && (
                <div
                  style={row}
                  onClick={() => browse(parent)}
                  onMouseEnter={e => { e.currentTarget.style.background = rowHover; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <ArrowUp size={14} color="#ffb86c" /> ..
                </div>
              )}
              {entries.map(entry => (
                <div
                  key={entry.path}
                  style={row}
                  onClick={() => browse(entry.path)}
                  onMouseEnter={e => { e.currentTarget.style.background = rowHover; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <Folder size={14} color={entry.has_models ? '#22c55e' : '#ffb86c'} />
                  {entry.name}
                  {entry.has_models && (
                    <span style={{ fontSize: '0.68rem', color: '#22c55e', fontWeight: 700 }}>
                      contiene modelli
                    </span>
                  )}
                </div>
              ))}
              {!entries.length && !parent && (
                <div style={{ color: textMuted, fontSize: '0.78rem', padding: '10px' }}>
                  Nessuna sottocartella.
                </div>
              )}
            </>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 14px', borderRadius: '8px', border,
              background: 'transparent', color: textMuted,
              fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer',
            }}
          >
            Annulla
          </button>
          <button
            onClick={() => { onSelect(current); onClose(); }}
            disabled={!current}
            style={{
              padding: '8px 16px', borderRadius: '8px',
              border: '1px solid rgba(34,197,94,0.4)',
              background: 'rgba(34,197,94,0.15)', color: '#22c55e',
              fontSize: '0.8rem', fontWeight: 800, cursor: 'pointer',
            }}
          >
            <Check size={13} style={{ verticalAlign: '-2px', marginRight: '5px' }} />
            Usa questa cartella
          </button>
        </div>
      </div>
    </div>
  );
}
