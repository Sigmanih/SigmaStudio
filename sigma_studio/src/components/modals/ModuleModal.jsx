import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';

export default function ModuleModal({ isOpen, onClose, onSave, initialData = {} }) {
  const [num, setNum] = useState(initialData.number || "");
  const [name, setName] = useState(initialData.name || "");
  const [desc, setDesc] = useState(initialData.description || "");

  useEffect(() => {
    setNum(initialData.number || "");
    setName(initialData.name || "");
    setDesc(initialData.description || "");
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
          <h3>{initialData.folder ? 'Modifica Modulo' : 'Nuovo Modulo'}</h3>
          <button onClick={onClose}><X size={18} /></button>
        </div>
        <div className="modal-body">
          <div className="input-group">
            <label>Numero (es. 01)</label>
            <input value={num} onChange={e => setNum(e.target.value)} placeholder="01" />
          </div>
          <div className="input-group">
            <label>Nome</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Topologia" />
          </div>
          <div className="input-group">
            <label>Descrizione</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={4} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>Annulla</button>
          <button className="btn-save" onClick={() => onSave({ number: num, name, description: desc })}>Salva</button>
        </div>
      </div>
    </div>
  );
}