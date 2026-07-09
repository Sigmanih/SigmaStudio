import React from 'react';
import { BookOpen, FileText, Terminal, PieChart, Trash2, ChevronRight, FilePlus, Upload } from 'lucide-react';
import ColumnActions from './ColumnActions';

// ==============================================================================
// ModuleView — Visualizzazione modulo con colonne risorse
// ==============================================================================

/**
 * ModuleView: visualizzazione del modulo con colonne.
 * Ogni colonna ha i propri pulsanti "Nuovo" e "Da PC" sotto la lista dei file.
 */
class ModuleView extends React.Component {
  constructor(props) {
    super(props);
    this.state = { version: 0 };
  }

  refresh = () => {
    // Trigger re-render by bumping version counter; parent fetchData will update modules prop
    this.setState(s => ({ version: s.version + 1 }));
    if (this.props.onRefresh) this.props.onRefresh();
  };

  render() {
    const { mod, openTab, deleteFileDirectly, openAddFile } = this.props;

    return (
      <div className="module-view">
        <div className="view-header">
          <div>
            <h2 className="glow-text">{mod.name}</h2>
            <p className="mod-description">{mod.description || "Descrizione del modulo..."}</p>
          </div>
        </div>
        
        <div className="resource-grid">
          {/* --- Whitepapers --- */}
          <div className="res-column">
            <h4>📄 Whitepapers</h4>
            {mod.whitepapers?.map(f => (
              <div key={f.path} className="res-item" onClick={() => openTab(f, 'whitepaper')}>
                <BookOpen size={14} className="icon secondary" />
                <span>{f.filename}</span>
                <div className="item-actions">
                  <Trash2 size={12} className="mod-btn" onClick={(e) => deleteFileDirectly(e, f.path)} />
                </div>
              </div>
            ))}
            {!mod.whitepapers?.length && <p className="empty-hint">Nessun whitepaper.</p>}
            <ColumnActions label="Whitepaper" columnType="whitepaper" moduleFolder={mod.folder} onAddFile={openAddFile} onRefresh={this.refresh} />
          </div>

          {/* --- Teoria --- */}
          <div className="res-column">
            <h4>📖 Teoria & Documentazione</h4>
            {mod.teoria?.map(f => (
              <div key={f.path} className="res-item" onClick={() => openTab(f, 'teoria')}>
                <div className="item-info">
                  <FileText size={14} className="icon" />
                  <span>{f.filename}</span>
                </div>
                <div className="item-actions">
                  <Trash2 size={12} className="mod-btn" onClick={(e) => deleteFileDirectly(e, f.path)} />
                </div>
              </div>
            ))}
            {!mod.teoria?.length && <p className="empty-hint">Nessuna documentazione teorica.</p>}
            <ColumnActions label="Teoria" columnType="teoria" moduleFolder={mod.folder} onAddFile={openAddFile} onRefresh={this.refresh} />
          </div>

          {/* --- Test --- */}
          <div className="res-column">
            <h4>🧪 Validazione Computazionale</h4>
            {mod.test?.map(f => (
              <div key={f.path} className="res-item test-item" onClick={() => openTab(f, 'test')}>
                <div className="item-info">
                  <Terminal size={14} className="icon accent" />
                  <span>{f.filename}</span>
                </div>
                <div className="item-actions">
                  <Trash2 size={12} className="mod-btn" onClick={(e) => deleteFileDirectly(e, f.path)} />
                </div>
              </div>
            ))}
            {!mod.test?.length && <p className="empty-hint">Nessun test script.</p>}
            <ColumnActions label="Test" columnType="test" moduleFolder={mod.folder} onAddFile={openAddFile} onRefresh={this.refresh} />
          </div>

          {/* --- Viz e Docs --- */}
          <div className="res-column">
            <h4>🔬 Studio & Visualizzazione</h4>
            {mod.viz?.map(f => (
              <div key={f.path} className="res-item" onClick={() => openTab(f, 'viz')}>
                <PieChart size={14} className="icon success" />
                <span>{f.filename}</span>
                <div className="item-actions">
                  <Trash2 size={12} className="mod-btn" onClick={(e) => deleteFileDirectly(e, f.path)} />
                </div>
              </div>
            ))}
            {mod.docs?.map(f => (
              <div key={f.path} className="res-item" onClick={() => openTab(f, 'docs')}>
                <ChevronRight size={14} />
                <span>{f.filename}</span>
                <div className="item-actions">
                  <Trash2 size={12} className="mod-btn" onClick={(e) => deleteFileDirectly(e, f.path)} />
                </div>
              </div>
            ))}
            {(!mod.viz?.length && !mod.docs?.length) && <p className="empty-hint">Nessun file.</p>}
            <div className="col-actions">
              <button className="btn-col-add" onClick={() => openAddFile('viz')} title="Crea nuova visualizzazione">
                <FilePlus size={14} /> Nuovo Viz
              </button>
              <button className="btn-col-add" onClick={() => openAddFile('docs')} title="Crea nuovo documento">
                <FilePlus size={14} /> Nuovo Doc
              </button>
              <input
                type="file"
                style={{ display: 'none' }}
                id="upload-viz-docs"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const formData = new FormData();
                  formData.append('file', file);
                  formData.append('folder', mod.folder);
                  formData.append('type', 'viz');
                  try {
                    const res = await fetch('/api/upload_file', { method: 'POST', body: formData });
                    const data = await res.json();
                    if (data.success) { if (this.props.onRefresh) this.props.onRefresh(); }
                    else { alert('Upload error: ' + (data.error || 'unknown')); }
                  } catch (err) { alert('Upload error: ' + err.message); }
                  e.target.value = '';
                }}
              />
              <button className="btn-col-upload" onClick={() => document.getElementById('upload-viz-docs')?.click()}>
                <Upload size={14} /> Da PC
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}

export default ModuleView;