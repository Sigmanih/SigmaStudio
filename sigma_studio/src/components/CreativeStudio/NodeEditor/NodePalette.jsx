import React, { useMemo, useState } from 'react';
import { Search, Plus } from 'lucide-react';

const CATEGORY_ORDER = ['Input', 'Generate', 'Edit', '3D', 'Mesh', 'Materials', 'Output'];

export default function NodePalette({ catalog = [], templates = {}, onLoadTemplate, onAddNode }) {
  const [query, setQuery] = useState('');
  const [template, setTemplate] = useState('blank');

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const groups = new Map();
    catalog
      .filter(n => !q || n.label.toLowerCase().includes(q) || n.type.includes(q))
      .forEach(n => {
        const key = n.category || 'Altro';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(n);
      });
    return [...groups.entries()].sort(
      (a, b) => (CATEGORY_ORDER.indexOf(a[0]) + 99) % 99 - (CATEGORY_ORDER.indexOf(b[0]) + 99) % 99
    );
  }, [catalog, query]);

  return (
    <div className="cs-node-palette" onPointerDown={e => e.stopPropagation()}>
      <h4 className="cs-palette-title">Node Library</h4>

      <div className="cs-palette-search">
        <Search size={13} />
        <input
          type="text"
          placeholder="Cerca nodi..."
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
      </div>

      <div className="cs-palette-content">
        {catalog.length === 0 && <p className="cs-palette-empty">Catalogo nodi non disponibile</p>}
        {grouped.map(([category, items]) => (
          <div key={category} className="cs-palette-category">
            <h5 style={{ color: items[0]?.color }}>{category}</h5>
            {items.map(node => (
              <div
                key={node.type}
                className="cs-node-item"
                draggable
                onDragStart={e => {
                  e.dataTransfer.setData('nodeType', node.type);
                  e.dataTransfer.effectAllowed = 'copy';
                }}
                onDoubleClick={() => onAddNode?.(node.type)}
                title={`${node.type} — trascina sul canvas o doppio click`}
              >
                <span className="cs-node-item-dot" style={{ background: node.color }} />
                <span>{node.label}</span>
                <Plus size={12} className="cs-node-item-add" onClick={() => onAddNode?.(node.type)} />
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="cs-palette-templates">
        <h5>Template</h5>
        <select
          value={template}
          onChange={e => { setTemplate(e.target.value); onLoadTemplate?.(e.target.value); }}
        >
          {Object.entries(templates).map(([key, tpl]) => (
            <option key={key} value={key}>{tpl.label}</option>
          ))}
        </select>
        {templates[template]?.description && (
          <p className="cs-palette-hint">{templates[template].description}</p>
        )}
      </div>
    </div>
  );
}
