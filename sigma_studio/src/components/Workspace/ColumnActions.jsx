import React from 'react';
import { Upload, FilePlus } from 'lucide-react';

// ==============================================================================
// ColumnActions — Pulsanti Aggiungi e Upload per una colonna di modulo
// ==============================================================================

export default function ColumnActions({ label, columnType, moduleFolder, onAddFile, onRefresh }) {
  const fileInputRef = React.useRef(null);
  const [uploading, setUploading] = React.useState(false);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('folder', moduleFolder);
    formData.append('type', columnType === 'whitepaper' ? 'docs' : columnType);
    try {
      const res = await fetch('/api/upload_file', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.success) {
        if (onRefresh) onRefresh();
      } else {
        alert('Upload error: ' + (data.error || 'unknown'));
      }
    } catch (err) {
      alert('Upload error: ' + err.message);
    }
    setUploading(false);
    e.target.value = '';
  };

  return (
    <div className="col-actions">
      <button className="btn-col-add" onClick={() => onAddFile(columnType)} title={`Crea nuovo file ${label}`}>
        <FilePlus size={14} /> Nuovo
      </button>
      <input
        ref={fileInputRef}
        type="file"
        style={{ display: 'none' }}
        onChange={handleUpload}
      />
      <button className="btn-col-upload" onClick={() => fileInputRef.current?.click()} disabled={uploading} title={`Carica file ${label} da PC`}>
        <Upload size={14} /> {uploading ? 'Caricamento...' : 'Da PC'}
      </button>
    </div>
  );
}