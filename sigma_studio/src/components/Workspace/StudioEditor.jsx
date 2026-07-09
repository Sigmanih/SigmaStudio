import React from 'react';
import { Play, Save, Trash2 } from 'lucide-react';
import Editor from 'react-simple-code-editor';
import { highlight, languages } from 'prismjs/components/prism-core';
import 'prismjs/components/prism-python';
import 'prismjs/themes/prism-tomorrow.css';

const CodeEditor = typeof Editor === 'function' ? Editor : Editor.default;

// ==============================================================================
// StudioEditor — Code editor with syntax highlighting
// ==============================================================================

export default function StudioEditor({ tab, onSave, onDirtyChange, onDelete, onRun, terminalOutput }) {
  const [code, setCode] = React.useState('');
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    fetch(`/api/get_file?path=${tab.path}`)
      .then(res => res.json())
      .then(data => {
        if (data.success) setCode(data.content);
        setLoading(false);
      });
  }, [tab.path]);

  const handleSave = async () => {
    await fetch('/api/create_file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: tab.path, content: code })
    });
    onDirtyChange(tab.id, false);
  };

  if (loading) return <div className="placeholder-content">Caricamento editor...</div>;

  return (
    <div className="studio-editor">
      <div className="editor-main">
        <div className="editor-header">
          <span className="file-path">{tab.path}</span>
          <div className="editor-actions">
            <button className="btn btn-run" onClick={() => onRun(tab.path)}>
              <Play size={14} /> Avvia
            </button>
            <button className="btn btn-save-file" onClick={handleSave}>
              <Save size={14} /> Salva
            </button>
            <button className="btn btn-delete-file" onClick={(e) => onDelete(e, tab.path)}>
              <Trash2 size={14} /> Elimina
            </button>
          </div>
        </div>
        <div className="editor-container">
          <CodeEditor
            value={code}
            onValueChange={c => { setCode(c); onDirtyChange(tab.id, true); }}
            highlight={code => highlight(code, languages.python)}
            padding={20}
            className="mono-editor"
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 14,
              minHeight: '100%'
            }}
          />
        </div>
      </div>
      <div className="editor-terminal">
        <div className="terminal-header">VALIDATION OUTPUT</div>
        <div className="terminal-content mono">{terminalOutput}</div>
      </div>
    </div>
  );
}