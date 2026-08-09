import React from 'react';
import { Box, Layers, Hexagon, Trash2, Image as ImageIcon } from 'lucide-react';

const TYPE_META = {
  image: { cls: 'type-image', Icon: ImageIcon },
  render: { cls: 'type-image', Icon: ImageIcon },
  texture: { cls: 'type-texture', Icon: Layers },
  material: { cls: 'type-texture', Icon: Layers },
  mesh: { cls: 'type-mesh', Icon: Hexagon },
  model_3d: { cls: 'type-mesh', Icon: Box },
};

export default function AssetCard({ asset, active, onClick, onDoubleClick, onDelete }) {
  const meta = TYPE_META[asset.type] || TYPE_META.image;
  const Icon = meta.Icon;

  return (
    <div
      className={`cs-asset-card ${active ? 'active' : ''}`}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      title={asset.name}
    >
      <div className="cs-asset-thumb">
        <span className={`cs-badge ${meta.cls}`} />
        {asset.url
          ? <img src={asset.url} alt={asset.name} loading="lazy" />
          : <Icon size={24} style={{ opacity: 0.35 }} />}
        {onDelete && (
          <button className="cs-card-delete" title="Elimina asset"
                  onClick={(e) => { e.stopPropagation(); onDelete(); }}>
            <Trash2 size={12} />
          </button>
        )}
      </div>
      <div className="cs-asset-info">
        <div className="cs-asset-name">{asset.name || 'Untitled'}</div>
        <span className="cs-asset-type">{asset.type}{asset.current_version > 1 ? ` · v${asset.current_version}` : ''}</span>
      </div>
    </div>
  );
}
