import React, { useState } from 'react';
import { X } from 'lucide-react';

export default function NewFileModal({ isOpen, onClose, onSave, folder, type }) {
  const [name, setName] = useState("");
  const extensions = { teoria: '.md', test: '.py', viz: '.html', docs: '.md', whitepaper: '.md', manifesti: '.md' };

  if (!isOpen) return null;

  const typeLabel = type === 'manifesti' ? 'Manifesto' : type.charAt(0).toUpperCase() + type.slice(1);
  const targetPath = type === 'manifesti' ? 'manifesti/' : `/${folder}/${type}/`;

  return (
    <div className="modal-overlay">
      <div className="modal-content small">
        <div className="modal-header">
          <h3>New {typeLabel}</h3>
          <button onClick={onClose} aria-label="Close modal"><X size={20} /></button>
        </div>
        <div className="modal-body">
          <p style={{fontSize: '0.75rem', color: '#9494a5', marginBottom: '16px', borderLeft: '2px solid var(--primary)', paddingLeft: '12px'}}>
            Target: <code>{targetPath}</code>
          </p>
          <div className="input-group">
            <label>Filename</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Lv2_ipotesi_estensione" />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>Annulla</button>
          <button className="btn-save" onClick={() => onSave(name + extensions[type])}>Create File</button>
        </div>
      </div>
    </div>
  );
}