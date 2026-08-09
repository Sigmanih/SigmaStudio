import React, { useRef, useState } from 'react';
import { Search, LayoutGrid, List, Image as ImageIcon, Box, Hexagon, Layers, Upload, Trash2 } from 'lucide-react';
import AssetCard from './shared/AssetCard';

const FILTERS = [
  { id: 'all', label: 'Tutti', icon: null },
  { id: 'image', label: 'Immagini', icon: ImageIcon },
  { id: 'model_3d', label: '3D', icon: Box },
  { id: 'mesh', label: 'Mesh', icon: Hexagon },
  { id: 'material', label: 'Materiali', icon: Layers },
];

export default function AssetPanel({ assets, selectedAsset, onSelectAsset, onOpenAsset, onUpload, onDelete }) {
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [filterType, setFilterType] = useState('all');
  const fileRef = useRef(null);

  const filtered = assets.filter(a => {
    if (filterType !== 'all' && a.type !== filterType) return false;
    if (search && !a.name?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="cs-panel-header">
        <span>Asset Vault</span>
        <div style={{ display: 'flex', gap: '4px' }}>
          <button className="collapse-btn" onClick={() => fileRef.current?.click()} title="Carica immagine">
            <Upload size={14} color="var(--text-dim)" />
          </button>
          <button className="collapse-btn" onClick={() => setViewMode('grid')} title="Griglia">
            <LayoutGrid size={14} color={viewMode === 'grid' ? 'var(--primary)' : 'var(--text-dim)'} />
          </button>
          <button className="collapse-btn" onClick={() => setViewMode('list')} title="Lista">
            <List size={14} color={viewMode === 'list' ? 'var(--primary)' : 'var(--text-dim)'} />
          </button>
        </div>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        hidden
        onChange={e => { const f = e.target.files?.[0]; if (f) onUpload?.(f); e.target.value = ''; }} />

      <div style={{ padding: '12px' }}>
        <div style={{ position: 'relative', marginBottom: '12px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-dim)' }} />
          <input
            type="text"
            placeholder="Cerca asset..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', padding: '8px 8px 8px 32px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: 'var(--text)' }} />
        </div>
        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
          {FILTERS.map(f => (
            <button
              key={f.id}
              className={`cs-pill ${filterType === f.id ? 'active' : ''}`}
              onClick={() => setFilterType(f.id)}
            >
              {f.icon && <f.icon size={12} style={{ marginRight: '4px' }} />}{f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="cs-panel-content" style={{ padding: '0 12px 12px 12px' }}>
        {filtered.length === 0 && (
          <p className="cs-hint" style={{ padding: '12px 0' }}>
            {assets.length ? 'Nessun asset per questo filtro.' : 'Il vault è vuoto: genera o carica un\'immagine.'}
          </p>
        )}

        {viewMode === 'grid' ? (
          <div className="cs-asset-grid">
            {filtered.map(a => (
              <AssetCard
                key={a.id}
                asset={a}
                active={selectedAsset?.id === a.id}
                onClick={() => onSelectAsset(a)}
                onDoubleClick={() => onOpenAsset?.(a)}
                onDelete={onDelete ? () => onDelete(a.id) : undefined} />
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {filtered.map(a => (
              <div
                key={a.id}
                className={`cs-asset-row ${selectedAsset?.id === a.id ? 'active' : ''}`}
                onClick={() => onSelectAsset(a)}
                onDoubleClick={() => onOpenAsset?.(a)}
              >
                {a.url
                  ? <img src={a.url} alt={a.name} loading="lazy" />
                  : <div className="cs-asset-row-placeholder">{a.type === 'material' ? <Layers size={16} /> : <Box size={16} />}</div>}
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="cs-asset-row-name">{a.name || 'Untitled'}</div>
                  <div className="cs-asset-row-meta">
                    {a.type}{a.created_at ? ` • ${new Date(a.created_at).toLocaleDateString()}` : ''}
                  </div>
                </div>
                {onDelete && (
                  <button className="cs-row-delete" title="Elimina"
                          onClick={(e) => { e.stopPropagation(); onDelete(a.id); }}>
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
