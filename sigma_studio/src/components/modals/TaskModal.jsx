import React, { useState, useEffect, useMemo } from 'react';
import { X, Trash2 } from 'lucide-react';

export default function TaskModal({ isOpen, onClose, onSave, initialData = null, onOpenFile }) {
  const [task, setTask] = useState({
    titolo: "",
    descrizione: "",
    status: "in_corso",
    priorita: "media",
    moduli: ["01"],
    files: []
  });
  const [modules, setModules] = useState([]);
  const [expandedMods, setExpandedMods] = useState({});
  const [expandedTypes, setExpandedTypes] = useState({});
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState('all');
  const [noteInput, setNoteInput] = useState("");

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/modules')
      .then(r => r.json())
      .then(data => setModules(data.modules || []))
      .catch(() => {});
  }, [isOpen]);

  useEffect(() => {
    if (initialData) {
      setTask({
        titolo: initialData.titolo || "",
        descrizione: initialData.descrizione || "",
        status: initialData.status || "in_corso",
        priorita: initialData.priorita || "media",
        moduli: initialData.moduli || ["01"],
        files: initialData.files || [],
        note: initialData.note || []
      });
    } else {
      setTask({ titolo: "", descrizione: "", status: "in_corso", priorita: "media", moduli: ["01"], files: [], note: [] });
    }
    setSearchQuery("");
    setFilterType('all');
    setExpandedMods({});
    setExpandedTypes({});
    setNoteInput("");
  }, [initialData, isOpen]);

  const addNote = () => {
    if (!noteInput.trim()) return;
    const newNote = {
      timestamp: new Date().toISOString(),
      text: noteInput.trim()
    };
    setTask({ ...task, note: [...(task.note || []), newNote] });
    setNoteInput("");
  };

  const addFileFromBrowser = (path, filename, type) => {
    if (task.files.some(f => f.path === path)) return;
    setTask({ ...task, files: [...task.files, { path, filename, type }] });
  };

  const removeFile = (index) => {
    setTask({ ...task, files: task.files.filter((_, i) => i !== index) });
  };

  const toggleMod = (num) => {
    setExpandedMods(prev => ({ ...prev, [num]: !prev[num] }));
  };

  const toggleType = (key) => {
    setExpandedTypes(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const fileGroups = useMemo(() => {
    const groups = [];
    for (const mod of modules) {
      const modEntry = { num: mod.number, name: mod.name, folder: mod.folder, types: [] };
      const subdirs = [
        { key: 'whitepapers', label: 'Whitepaper', icon: '📜', filesList: mod.whitepapers || [] },
        { key: 'teoria', label: 'Teoria', icon: '📖', filesList: mod.teoria || [] },
        { key: 'test', label: 'Test', icon: '🧪', filesList: mod.test || [] },
        { key: 'viz', label: 'Viz', icon: '📊', filesList: mod.viz || [] },
        { key: 'docs', label: 'Docs', icon: '📄', filesList: mod.docs || [] },
      ];
      for (const sd of subdirs) {
        if (sd.filesList.length > 0) {
          const files = sd.filesList.map(f => ({
            path: f.path,
            filename: f.filename,
            type: sd.key === 'whitepapers' ? 'whitepaper' : sd.key === 'teoria' ? 'teoria' : sd.key === 'test' ? 'test' : sd.key === 'viz' ? 'viz' : 'docs'
          }));
          modEntry.types.push({ key: sd.key, label: sd.label, icon: sd.icon, files });
        }
      }
      if (modEntry.types.length > 0) groups.push(modEntry);
    }
    return groups;
  }, [modules]);

  const filteredGroups = useMemo(() => {
    if (!searchQuery && filterType === 'all') return fileGroups;
    return fileGroups.map(mod => {
      const filteredTypes = mod.types
        .filter(t => filterType === 'all' || t.key === filterType)
        .map(t => ({
          ...t,
          files: searchQuery 
            ? t.files.filter(f => f.filename.toLowerCase().includes(searchQuery.toLowerCase()))
            : t.files
        }))
        .filter(t => t.files.length > 0);
      return { ...mod, types: filteredTypes };
    }).filter(mod => mod.types.length > 0);
  }, [fileGroups, searchQuery, filterType]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content task-modal">
        <div className="modal-header">
          <h3>{initialData ? '✏️ Modifica Task' : '➕ Nuovo Task'}</h3>
          <button onClick={onClose} aria-label="Close modal"><X size={20} /></button>
        </div>
        <div className="modal-body">
          <div className="input-group">
            <label>Titolo Obiettivo</label>
            <input value={task.titolo} onChange={e => setTask({...task, titolo: e.target.value})} placeholder="Es. Validazione Hub D..." autoFocus />
          </div>
          <div className="input-row">
            <div className="input-group">
              <label>Modulo</label>
              <input value={task.moduli?.[0]} onChange={e => setTask({...task, moduli: [e.target.value]})} placeholder="01" />
            </div>
            <div className="input-group">
              <label>Priorità</label>
              <select value={task.priorita} onChange={e => setTask({...task, priorita: e.target.value})}>
                <option value="bassa">Bassa</option>
                <option value="media">Media</option>
                <option value="alta">Alta</option>
                <option value="critica">Critica</option>
              </select>
            </div>
            <div className="input-group">
              <label>Stato</label>
              <select value={task.status} onChange={e => setTask({...task, status: e.target.value})}>
                <option value="in_corso">In Corso</option>
                <option value="done">Completato</option>
                <option value="blocked">Bloccato</option>
              </select>
            </div>
          </div>
          <div className="input-group">
            <label>Descrizione Dettagliata</label>
            <textarea value={task.descrizione} onChange={e => setTask({...task, descrizione: e.target.value})} rows={6} placeholder="Descrivi obiettivo, contesto, criteri di successo..." />
          </div>
          
          {/* File Browser */}
          <div className="input-group">
            <label>📎 File di Riferimento</label>
            
            <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Cerca file per nome..."
                style={{ flex: 1, fontSize: '0.7rem' }}
              />
              <select value={filterType} onChange={e => setFilterType(e.target.value)} style={{ width: '120px', fontSize: '0.65rem' }}>
                <option value="all">Tutti i tipi</option>
                <option value="whitepapers">📜 Whitepaper</option>
                <option value="teoria">📖 Teoria</option>
                <option value="test">🧪 Test</option>
                <option value="viz">📊 Viz</option>
                <option value="docs">📄 Docs</option>
              </select>
            </div>

            <div className="file-browser-tree">
              <style>{`
                .file-browser-tree { max-height: 200px; overflow-y: auto; border: 1px solid #2a2d3e; border-radius: 6px; padding: 4px; background: #0e1016; margin-bottom: 8px; }
                .file-browser-tree::-webkit-scrollbar { width: 3px; }
                .file-browser-tree::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 2px; }
                .fb-mod { margin-bottom: 2px; }
                .fb-mod-header { display: flex; align-items: center; gap: 4px; padding: 4px 8px; cursor: pointer; border-radius: 4px; font-size: 0.65rem; color: #8b8fa3; transition: all 0.1s; }
                .fb-mod-header:hover { background: rgba(255,255,255,0.03); color: #e2e4eb; }
                .fb-mod-header .arrow { transition: transform 0.15s; font-size: 0.55rem; width: 12px; }
                .fb-mod-header .arrow.open { transform: rotate(90deg); }
                .fb-type { margin-left: 12px; margin-bottom: 1px; }
                .fb-type-header { display: flex; align-items: center; gap: 4px; padding: 3px 6px; cursor: pointer; border-radius: 4px; font-size: 0.6rem; color: #5a5e72; transition: all 0.1s; }
                .fb-type-header:hover { background: rgba(255,255,255,0.03); color: #8b8fa3; }
                .fb-type-header .arrow { transition: transform 0.15s; font-size: 0.5rem; width: 10px; }
                .fb-type-header .arrow.open { transform: rotate(90deg); }
                .fb-file { display: flex; align-items: center; gap: 4px; padding: 3px 6px 3px 16px; cursor: pointer; border-radius: 4px; font-size: 0.6rem; color: #5a5e72; transition: all 0.1s; margin-left: 12px; }
                .fb-file:hover { background: rgba(0,210,255,0.06); color: #00d2ff; }
                .fb-file .fb-plus { opacity: 0; margin-left: auto; font-size: 0.55rem; color: #3fb950; }
                .fb-file:hover .fb-plus { opacity: 1; }
                .fb-file.added { color: #3fb950; background: rgba(63,185,80,0.06); }
                .fb-empty { font-size: 0.65rem; color: #5a5e72; text-align: center; padding: 16px; }
                .ref-files-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
                .ref-file-item { display: flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 6px; background: rgba(255,255,255,0.03); border: 1px solid #1e2030; font-size: 0.6rem; }
                .ref-file-item .ref-file-icon { font-size: 0.6rem; }
                .ref-file-item .ref-file-name { cursor: pointer; color: #8b8fa3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
                .ref-file-item .ref-file-name:hover { color: #00d2ff; }
                .ref-file-item .ref-file-type { font-size: 0.45rem; background: #1e2030; padding: 1px 5px; border-radius: 3px; color: #5a5e72; }
                .ref-file-item .ref-file-del { background: none; border: none; color: #ff5555; cursor: pointer; padding: 0 2px; opacity: 0.6; }
                .ref-file-item .ref-file-del:hover { opacity: 1; }
              `}</style>

              {filteredGroups.length === 0 && (
                <div className="fb-empty">Nessun file trovato</div>
              )}
              {filteredGroups.map(mod => (
                <div key={mod.num} className="fb-mod">
                  <div className="fb-mod-header" onClick={() => toggleMod(mod.num)}>
                    <span className={`arrow ${expandedMods[mod.num] ? 'open' : ''}`}>▶</span>
                    <span>M{mod.num} — {mod.name}</span>
                    <span style={{ marginLeft: 'auto', fontSize: '0.5rem', opacity: 0.5 }}>
                      {mod.types.reduce((sum, t) => sum + t.files.length, 0)} files
                    </span>
                  </div>
                  {expandedMods[mod.num] && mod.types.map(type => (
                    <div key={type.key} className="fb-type">
                      <div className="fb-type-header" onClick={() => toggleType(type.key + '-' + mod.num)}>
                        <span className={`arrow ${expandedTypes[type.key + '-' + mod.num] ? 'open' : ''}`}>▶</span>
                        <span>{type.icon} {type.label}</span>
                        <span style={{ marginLeft: 'auto', fontSize: '0.5rem', opacity: 0.5 }}>{type.files.length}</span>
                      </div>
                      {expandedTypes[type.key + '-' + mod.num] && type.files.map(f => {
                        const alreadyAdded = task.files.some(tf => tf.path === f.path);
                        return (
                          <div key={f.path} className={`fb-file ${alreadyAdded ? 'added' : ''}`} onClick={() => !alreadyAdded && addFileFromBrowser(f.path, f.filename, f.type)} title={f.path}>
                            <span>{type.icon}</span>
                            <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.filename}</span>
                            {alreadyAdded ? <span style={{ fontSize: '0.5rem', color: '#3fb950' }}>✓</span> : <span className="fb-plus">+</span>}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {task.files.length > 0 && (
              <div className="ref-files-list">
                {task.files.map((f, i) => (
                  <div key={i} className="ref-file-item">
                    <span className="ref-file-icon">
                      {f.type === 'test' ? '🧪' : f.type === 'viz' ? '📊' : f.type === 'whitepaper' ? '📜' : '📖'}
                    </span>
                    <span className="ref-file-name" onClick={() => onOpenFile && onOpenFile(f.path)} title={f.path}>
                      {f.filename}
                    </span>
                    <span className="ref-file-type">{f.type.toUpperCase()}</span>
                    <button className="ref-file-del" onClick={() => removeFile(i)}><Trash2 size={10} /></button>
                  </div>
                ))}
              </div>
            )}
            {task.files.length === 0 && (
              <div style={{ fontSize: '0.65rem', color: '#5a5e72', fontStyle: 'italic', textAlign: 'center', padding: '6px' }}>
                Seleziona file dal browser qui sopra
              </div>
            )}
          </div>
          {/* Notes Section */}
          <div className="input-group" style={{ borderTop: '1px solid #1e2030', paddingTop: '12px', marginTop: '4px' }}>
            <label>📝 Note di Progresso</label>
            <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
              <input
                value={noteInput}
                onChange={e => setNoteInput(e.target.value)}
                placeholder="Scrivi una nota sul progresso..."
                style={{ flex: 1, fontSize: '0.7rem' }}
                onKeyDown={e => { if (e.key === 'Enter') addNote(); }}
              />
              <button onClick={addNote} style={{
                padding: '6px 14px', borderRadius: '6px', border: '1px solid rgba(0,210,255,0.3)',
                background: 'rgba(0,210,255,0.1)', color: '#00d2ff', cursor: 'pointer',
                fontSize: '0.65rem', fontWeight: 600, whiteSpace: 'nowrap'
              }}>
                + Aggiungi
              </button>
            </div>
            {task.note && task.note.length > 0 ? (
              <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {task.note.map((n, i) => (
                  <div key={i} style={{
                    padding: '8px 10px', borderRadius: '6px',
                    background: 'rgba(255,255,255,0.02)', border: '1px solid #1e2030',
                    fontSize: '0.65rem'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ color: '#00d2ff', fontSize: '0.55rem', fontWeight: 600 }}>
                        Nota #{i + 1}
                      </span>
                      <span style={{ color: '#5a5e72', fontSize: '0.5rem' }}>
                        {new Date(n.timestamp).toLocaleString('it-IT', {
                          day: '2-digit', month: '2-digit', year: 'numeric',
                          hour: '2-digit', minute: '2-digit'
                        })}
                      </span>
                    </div>
                    <div style={{ color: '#c8cad4', lineHeight: 1.5 }}>{n.text}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '0.65rem', color: '#5a5e72', fontStyle: 'italic', textAlign: 'center', padding: '8px' }}>
                Nessuna nota ancora. Aggiungi note per tracciare i progressi.
              </div>
            )}
          </div>

        </div>
        <div className="modal-footer" style={{ padding: '16px 24px', gap: '10px' }}>
          <button className="btn-cancel" onClick={onClose}>Annulla</button>
          <button className="btn-save" onClick={() => onSave(task)}>
            {initialData ? '💾 Salva Modifiche' : '➕ Crea Task'}
          </button>
        </div>
      </div>
    </div>
  );
}