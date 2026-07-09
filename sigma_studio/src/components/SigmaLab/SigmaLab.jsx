import React, { useState, useEffect } from 'react';
import { 
  FileText, Terminal, Globe, Layers, ChevronRight, BookOpen, 
  Settings, ArrowRight, Play, Upload, FilePlus
} from 'lucide-react';
import MarkdownPreview from './MarkdownPreview';
import CodeRunner from './CodeRunner';
import HtmlPreview from './HtmlPreview';

// ==============================================================================
// SigmaLab — Centro di Ricerca e Sviluppo Unificato
// Visualizza, edita, esegui e visualizza files MD, Python, HTML
// ==============================================================================

export default function SigmaLab({ initialPath, initialType }) {
  const [modules, setModules] = useState([]);
  const [activePath, setActivePath] = useState(initialPath || '');
  const [activeType, setActiveType] = useState(initialType || '');
  const [expandedModules, setExpandedModules] = useState({});

  useEffect(() => {
    fetch('/api/modules')
      .then(res => res.json())
      .then(data => setModules(data.modules || []))
      .catch(() => {});
  }, []);

  const handleFileClick = (path, type) => {
    setActivePath(path);
    setActiveType(type);
  };

  const toggleModule = (modNum) => {
    setExpandedModules(prev => ({
      ...prev,
      [modNum]: !prev[modNum]
    }));
  };

  const renderFileItem = (file, type) => (
    <div 
      key={file.path} 
      className="sigma-lab-file-item"
      onClick={() => handleFileClick(file.path, type)}
    >
      <FileIcon type={type} />
      <span>{file.filename}</span>
    </div>
  );

  const renderModule = (mod) => (
    <div key={mod.number} className="sigma-lab-module">
      <div 
        className="sigma-lab-module-header" 
        onClick={() => toggleModule(mod.number)}
      >
        <ChevronRight size={14} style={{ 
          transform: expandedModules[mod.number] ? 'rotate(90deg)' : 'none',
          transition: 'transform 0.2s'
        }} />
        <span>MOD {mod.number} — {mod.name}</span>
      </div>
      {expandedModules[mod.number] && (
        <div className="sigma-lab-module-files">
          {mod.teoria?.map(f => renderFileItem(f, 'teoria'))}
          {mod.test?.map(f => renderFileItem(f, 'test'))}
          {mod.viz?.map(f => renderFileItem(f, 'viz'))}
          {mod.docs?.map(f => renderFileItem(f, 'whitepaper'))}
        </div>
      )}
    </div>
  );

  const renderContent = () => {
    if (!activePath) {
      return (
        <div className="sigma-lab-empty">
          <Layers size={48} />
          <p>Seleziona un file dalla sidebar per visualizzarlo</p>
        </div>
      );
    }

    switch (activeType) {
      case 'test':
        return <CodeRunner scriptPath={activePath} />;
      case 'viz':
      case 'whitepaper':
      case 'docs':
        return <HtmlPreview htmlPath={activePath} />;
      default:
        return <MarkdownPreview path={activePath} />;
    }
  };

  return (
    <div className="sigma-lab">
      {/* Sidebar — Module Browser */}
      <div className="sigma-lab-sidebar">
        <div className="sigma-lab-sidebar-header">
          <Layers size={18} />
          <h3>Moduli</h3>
        </div>
        <div className="sigma-lab-sidebar-content">
          {modules.map(renderModule)}
          {modules.length === 0 && (
            <div className="sigma-lab-empty-hint">
              Nessun modulo disponibile
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="sigma-lab-content">
        {renderContent()}
      </div>
    </div>
  );
}

// Helper component for file icons
function FileIcon({ type }) {
  switch (type) {
    case 'test': return <Terminal size={14} className="icon-accent" />;
    case 'viz': return <Globe size={14} className="icon-success" />;
    case 'whitepaper': return <BookOpen size={14} className="icon-gold" />;
    case 'teoria': return <FileText size={14} className="icon-primary" />;
    default: return <FileText size={14} />;
  }
}