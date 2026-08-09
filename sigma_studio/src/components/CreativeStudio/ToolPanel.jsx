import React from 'react';
import { Image as ImageIcon, Paintbrush, Box, Grid, Scissors, Workflow } from 'lucide-react';

const TOOLS = [
  { id: 'generate', icon: ImageIcon, label: 'Text to Image' },
  { id: 'edit', icon: Paintbrush, label: 'Inpaint / Edit' },
  { id: '3d', icon: Box, label: 'Image to 3D' },
  { id: 'mesh', icon: Scissors, label: 'Mesh Lab' },
  { id: 'materials', icon: Grid, label: 'Materiali' },
  { id: 'pipeline', icon: Workflow, label: 'Pipeline' },
];

export default function ToolPanel({ activeView, onViewChange }) {
  return (
    <div className="cs-tool-panel">
      <div className="cs-tool-section">
        <div className="cs-tool-section-title">Moduli</div>
        <div className="cs-tool-grid">
          {TOOLS.map(t => (
            <button
              key={t.id}
              className={`cs-tool-btn ${activeView === t.id ? 'active' : ''}`}
              onClick={() => onViewChange(t.id)}
              title={t.label}
            >
              <t.icon size={18} />
              <span>{t.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
