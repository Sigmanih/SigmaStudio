import React, { useState, useEffect, useCallback } from 'react';
import { Folder, FolderOpen, ArrowUp, HardDrive, Check, X, FileText, Cpu, Package } from 'lucide-react';

/**
 * Browses the server's filesystem to choose a models directory or local model file.
 *
 * A server-side browser rather than a file input: a browser only ever reveals
 * the name of a chosen folder, never its absolute path, and this setting needs
 * an absolute path on the machine the engine runs on.
 */
export default function DirectoryPicker({
  initialPath,
  isLight,
  title = 'Scegli la cartella dei modelli',
  confirmLabel = 'Usa questa cartella',
  includeFiles = false,
  onSelect,
  onClose
}) {
  const [current, setCurrent] = useState('');
  const [selectedItem, setSelectedItem] = useState(null);
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
  const selectedBg = isLight ? 'rgba(0, 210, 255, 0.12)' : 'rgba(0, 210, 255, 0.18)';
  const selectedBorder = '1px solid rgba(0, 210, 255, 0.4)';

  const browse = useCallback(async (path) => {
    setLoading(true);
    setSelectedItem(null);
    try {
      const queryParams = new URLSearchParams();
      if (path) queryParams.set('path', path);
      if (includeFiles) queryParams.set('include_files', '1');
      const url = '/api/models/browse?' + queryParams.toString();

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
  }, [includeFiles]);

  useEffect(() => { browse(initialPath); }, [browse, initialPath]);

  const effectiveSelection = selectedItem ? selectedItem.path : current;

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
          width: 'min(640px, 94vw)', maxHeight: '82vh', background: bg,
          border, borderRadius: '14px', padding: '18px',
          display: 'flex', flexDirection: 'column', gap: '12px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong style={{ color: textPrimary, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FolderOpen size={18} color="#00d2ff" />
            {title}
          </strong>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: textMuted }}
          >
            <X size={17} />
          </button>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '8px 12px', borderRadius: '8px',
          background: isLight ? '#f9fafb' : 'rgba(0,0,0,0.3)',
          border: '1px solid rgba(255,255,255,0.06)'
        }}>
          <span style={{ fontSize: '0.70rem', fontWeight: 800, color: '#00d2ff', textTransform: 'uppercase' }}>
            {selectedItem ? (selectedItem.is_dir ? 'Cartella Selezionata' : 'File Selezionato') : 'Percorso Attuale'}:
          </span>
          <code
            style={{
              fontSize: '0.74rem', color: textPrimary, wordBreak: 'break-all', flex: 1, fontFamily: 'monospace'
            }}
          >
            {effectiveSelection || '—'}
          </code>
        </div>

        {roots.length > 0 && (
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.70rem', color: textMuted, fontWeight: 700 }}>Unità:</span>
            {roots.map(r => (
              <button
                key={r}
                onClick={() => browse(r)}
                style={{
                  padding: '4px 10px', borderRadius: '6px', border,
                  background: current.startsWith(r) ? 'rgba(0, 210, 255, 0.12)' : 'transparent',
                  color: current.startsWith(r) ? '#00d2ff' : textMuted,
                  fontSize: '0.72rem', cursor: 'pointer', fontWeight: 700
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

        <div style={{ overflowY: 'auto', flex: 1, minHeight: '220px', maxHeight: '380px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {loading ? (
            <div style={{ color: textMuted, fontSize: '0.8rem', padding: '16px', textAlign: 'center' }}>
              Lettura disco in corso...
            </div>
          ) : (
            <>
              {parent && (
                <div
                  style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    padding: '7px 10px', borderRadius: '8px', cursor: 'pointer',
                    fontSize: '0.8rem', color: textPrimary,
                  }}
                  onClick={() => browse(parent)}
                  onMouseEnter={e => { e.currentTarget.style.background = rowHover; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <ArrowUp size={14} color="#ffb86c" />
                  <span style={{ fontWeight: 700 }}>.. (Cartella superiore)</span>
                </div>
              )}
              {entries.map(entry => {
                const isSelected = selectedItem && selectedItem.path === entry.path;
                const isDir = entry.is_dir !== false;
                return (
                  <div
                    key={entry.path}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '7px 10px', borderRadius: '8px', cursor: 'pointer',
                      fontSize: '0.8rem', color: textPrimary,
                      background: isSelected ? selectedBg : 'transparent',
                      border: isSelected ? selectedBorder : '1px solid transparent',
                      transition: 'all 0.15s ease'
                    }}
                    onClick={() => {
                      if (isDir) {
                        browse(entry.path);
                      } else {
                        setSelectedItem(entry);
                      }
                    }}
                    onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = rowHover; }}
                    onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {isDir ? (
                        <Folder size={15} color={entry.has_models ? '#22c55e' : '#ffb86c'} />
                      ) : (
                        <Package size={15} color="#00d2ff" />
                      )}
                      <span style={{ fontWeight: isDir ? (entry.has_models ? 700 : 500) : 600 }}>
                        {entry.name}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {entry.has_models && (
                        <span style={{
                          fontSize: '0.66rem', color: '#22c55e', fontWeight: 800,
                          background: 'rgba(34,197,94,0.12)', padding: '2px 6px', borderRadius: '4px'
                        }}>
                          contiene modelli
                        </span>
                      )}
                      {!isDir && entry.size_mb && (
                        <span style={{
                          fontSize: '0.66rem', color: '#00d2ff', fontWeight: 800,
                          background: 'rgba(0,210,255,0.12)', padding: '2px 6px', borderRadius: '4px'
                        }}>
                          {entry.size_mb > 1024 ? `${(entry.size_mb / 1024).toFixed(1)} GB` : `${entry.size_mb} MB`}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
              {!entries.length && !parent && (
                <div style={{ color: textMuted, fontSize: '0.78rem', padding: '16px', textAlign: 'center' }}>
                  Nessun elemento trovato in questa cartella.
                </div>
              )}
            </>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '8px', borderTop: border }}>
          <span style={{ fontSize: '0.70rem', color: textMuted }}>
            {selectedItem ? 'Elemento selezionato' : 'Naviga nella cartella desiderata e conferma'}
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
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
              onClick={() => { onSelect(effectiveSelection); onClose(); }}
              disabled={!effectiveSelection}
              style={{
                padding: '8px 16px', borderRadius: '8px',
                border: '1px solid rgba(0,210,255,0.4)',
                background: 'linear-gradient(135deg, rgba(0,210,255,0.2), rgba(0,136,255,0.2))',
                color: '#00d2ff',
                fontSize: '0.8rem', fontWeight: 800, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px'
              }}
            >
              <Check size={14} />
              {selectedItem && !selectedItem.is_dir ? 'Seleziona questo file' : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

