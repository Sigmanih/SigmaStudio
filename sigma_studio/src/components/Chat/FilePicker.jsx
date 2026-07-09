import React, { useState, useEffect, useRef } from 'react';
import { FileText, Search, Loader, Check, FolderOpen, X, Upload } from 'lucide-react';

const MAX_ATTACHMENTS = 10;

export default function FilePicker({ onSelect, onClose, attachedFiles, pcFiles: initialPcFiles, onPcFilesChange }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedProject, setSelectedProject] = useState(attachedFiles || []);
  const [pcFiles, setPcFiles] = useState(initialPcFiles || []);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => { fetchFiles(); }, []);

  const fetchFiles = async () => {
    setLoading(true);
    try {
      const [modulesRes, manifestiRes] = await Promise.all([fetch('/api/modules'), fetch('/api/list_manifesti')]);
      const modulesData = await modulesRes.json();
      const manifestiData = await manifestiRes.json();
      const allFiles = [];
      if (manifestiData.success) (manifestiData.files || []).forEach(f => allFiles.push({ path: f.path, name: f.filename, group: 'manifesti' }));
      (modulesData.modules || []).forEach(mod => {
        ['teoria','test','viz','docs','whitepapers'].forEach(section => {
          (mod[section] || []).forEach(f => allFiles.push({ path: f.path, name: f.filename, group: `${mod.name}/${section}` }));
        });
      });
      setFiles(allFiles);
    } catch (e) { console.error('File fetch error:', e); }
    setLoading(false);
  };

  const toggleFile = (p) => setSelectedProject(prev => prev.includes(p) ? prev.filter(x => x !== p) : prev.length >= MAX_ATTACHMENTS - pcFiles.length ? prev : [...prev, p]);
  
  const handlePcFileSelect = (e) => {
    const farr = Array.from(e.target.files || []);
    if (!farr.length) return;
    const readers = farr.map(f => new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (ev) => resolve({ filename: f.name, content: ev.target.result });
      reader.onerror = () => resolve(null);
      reader.readAsText(f);
    }));
    Promise.all(readers).then(results => {
      const valid = results.filter(Boolean);
      setPcFiles(prev => [...prev, ...valid].slice(0, MAX_ATTACHMENTS));
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const farr = Array.from(e.dataTransfer.files || []);
    if (!farr.length) return;
    const readers = farr.map(f => new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (ev) => resolve({ filename: f.name, content: ev.target.result });
      reader.onerror = () => resolve(null);
      reader.readAsText(f);
    }));
    Promise.all(readers).then(results => {
      const valid = results.filter(Boolean);
      setPcFiles(prev => [...prev, ...valid].slice(0, MAX_ATTACHMENTS));
    });
  };

  const removePcFile = (filename) => {
    setPcFiles(prev => prev.filter(f => f.filename !== filename));
  };

  const handleConfirm = () => {
    const total = [...selectedProject, ...pcFiles.map(f => `__pc__${f.filename}`)];
    onSelect(total, pcFiles);
    if (onPcFilesChange) onPcFilesChange(pcFiles);
  };

  const filtered = search ? files.filter(f => f.name.toLowerCase().includes(search.toLowerCase()) || f.path.toLowerCase().includes(search.toLowerCase())) : files;
  const grouped = filtered.reduce((acc, f) => { if (!acc[f.group]) acc[f.group] = []; acc[f.group].push(f); return acc; }, {});

  return (
    <div className="chat-filepicker-overlay">
      <div className="chat-filepicker">
        <div className="chat-filepicker-header">
          <span><FolderOpen size={14} /> Seleziona file (max {MAX_ATTACHMENTS})</span>
          <div className="chat-filepicker-actions">
            <span className="chat-filepicker-count">{selectedProject.length + pcFiles.length}/{MAX_ATTACHMENTS}</span>
            <button className="chat-filepicker-close" onClick={onClose}><X size={14} /></button>
          </div>
        </div>

        {/* PC Upload Area */}
        <div
          className={`chat-filepicker-dropzone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload size={20} />
          <span className="chat-filepicker-dropzone-text">
            {dragOver ? 'Rilascia i file qui' : 'Trascina file dal PC o clicca per caricare'}
          </span>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handlePcFileSelect}
            multiple
            style={{ display: 'none' }}
            accept=".txt,.md,.py,.js,.jsx,.ts,.tsx,.json,.csv,.html,.css,.yaml,.yml,.xml,.log,.sh,.bat,.ps1,.cfg,.ini,.toml"
          />
        </div>

        {/* PC Files chips */}
        {pcFiles.length > 0 && (
          <div className="chat-filepicker-pc-chips">
            {pcFiles.map(f => (
              <span key={f.filename} className="chat-filepicker-pc-chip">
                <FileText size={10} /> {f.filename}
                <button className="chat-filepicker-pc-remove" onClick={(e) => { e.stopPropagation(); removePcFile(f.filename); }}><X size={10} /></button>
              </span>
            ))}
          </div>
        )}

        {/* Search */}
        <div className="chat-filepicker-search">
          <Search size={12} />
          <input type="text" placeholder="Cerca file nel progetto..." value={search} onChange={e => setSearch(e.target.value)} autoFocus />
        </div>

        {/* Project files list */}
        <div className="chat-filepicker-list">
          {loading && <div className="chat-filepicker-loading"><Loader size={14} className="spin" /> Caricamento file...</div>}
          {!loading && Object.entries(grouped).map(([g, gfs]) => (
            <div key={g} className="chat-filepicker-group">
              <div className="chat-filepicker-group-label">{g}</div>
              {gfs.map(f => (
                <div key={f.path} className={`chat-filepicker-item ${selectedProject.includes(f.path) ? 'selected' : ''}`} onClick={() => toggleFile(f.path)}>
                  <FileText size={12} />
                  <span className="chat-filepicker-item-name">{f.name}</span>
                  {selectedProject.includes(f.path) && <Check size={12} className="chat-filepicker-check" />}
                </div>
              ))}
            </div>
          ))}
          {!loading && Object.keys(grouped).length === 0 && <div className="chat-filepicker-empty">Nessun file trovato</div>}
        </div>

        {/* Footer */}
        <div className="chat-filepicker-footer">
          <button className="btn-cancel" onClick={onClose}>Annulla</button>
          <button className="btn-primary" onClick={handleConfirm}>
            Allega {(selectedProject.length + pcFiles.length) > 0 ? `(${selectedProject.length + pcFiles.length})` : ''}
          </button>
        </div>
      </div>
    </div>
  );
}