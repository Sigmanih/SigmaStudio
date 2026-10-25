import React, { useState } from 'react';
import { Sparkles, X, FileText, Code, CheckCircle, AlertTriangle, Layers } from 'lucide-react';

const AI_ROLES = [
  { id: 'writer', name: 'Documentazione & Teoria', icon: '📖', desc: 'Note scientifiche, KaTeX, manuali' },
  { id: 'math1', name: 'Matematica & Algoritmi', icon: '🧮', desc: 'Formulazioni analitiche rigorose' },
  { id: 'code_architect', name: 'Architettura & Codice', icon: '🏗️', desc: 'Moduli puliti con pattern robusti' },
  { id: 'tester', name: 'Suite di Test Pytest', icon: '🧪', desc: 'Test unitari e di regressione' },
];

export default function AiCreateFileModal({
  isOpen,
  onClose,
  targetFolderNode,
  workspaceRoot,
  onFileCreated,
  addToast,
  isLight
}) {
  const [filename, setFilename] = useState('');
  const [category, setCategory] = useState('docs');
  const [selectedRole, setSelectedRole] = useState('writer');
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const targetPath = targetFolderNode?.path || '';
  const displayFolder = targetPath || 'radice del workspace';

  const handleCreate = async () => {
    if (!filename.trim()) {
      addToast?.('Inserisci un nome file valido', 'error');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/developer/fs/ai-create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: targetPath,
          filename: filename.trim(),
          category,
          role: selectedRole,
          prompt: prompt.trim(),
          workspace_root: workspaceRoot
        })
      });

      const data = await res.json();
      if (data.success) {
        addToast?.(`✨ File ${filename} creato con successo!`, 'success');
        onFileCreated?.(data.path || `${targetPath}/${filename}`);
        onClose();
      } else {
        addToast?.(data.error || 'Errore durante la creazione del file', 'error');
      }
    } catch (err) {
      addToast?.('Errore di connessione al server', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-create-modal-overlay" onClick={onClose}>
      <div
        className={`ai-create-modal ${isLight ? 'light' : 'dark'}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={18} color="#00f2fe" />
            <span style={{ fontWeight: 700, fontSize: '0.88rem', letterSpacing: '-0.2px' }}>
              Crea Documento o Codice con AI
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: '#8b949e',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Target Folder indicator */}
          <div style={{
            fontSize: '0.72rem',
            padding: '6px 10px',
            borderRadius: '6px',
            background: isLight ? '#f6f8fa' : 'rgba(255,255,255,0.04)',
            color: '#8b949e',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <Layers size={13} color="#00f2fe" />
            <span>Destinazione: <strong style={{ color: isLight ? '#24292f' : '#e6edf3' }}>{displayFolder}</strong></span>
          </div>

          {/* Nome File & Categoria */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 140px', gap: '10px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, marginBottom: '5px' }}>
                Nome File (es. teoria.md, worker.py)
              </label>
              <input
                type="text"
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                placeholder="es. formulazione_rete.md"
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  borderRadius: '6px',
                  border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
                  background: isLight ? '#fff' : '#07090e',
                  color: isLight ? '#24292f' : '#e6edf3',
                  fontSize: '0.8rem',
                  outline: 'none'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, marginBottom: '5px' }}>
                Tipo Contenuto
              </label>
              <select
                value={category}
                onChange={(e) => {
                  const cat = e.target.value;
                  setCategory(cat);
                  if (cat === 'docs') setSelectedRole('writer');
                  else if (cat === 'code') setSelectedRole('code_architect');
                  else if (cat === 'test') setSelectedRole('tester');
                }}
                style={{
                  width: '100%',
                  padding: '7px 8px',
                  borderRadius: '6px',
                  border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
                  background: isLight ? '#fff' : '#07090e',
                  color: isLight ? '#24292f' : '#e6edf3',
                  fontSize: '0.76rem',
                  outline: 'none'
                }}
              >
                <option value="docs">📖 Teoria / Docs</option>
                <option value="code">⚙️ Codice</option>
                <option value="test">🧪 Test Suite</option>
                <option value="config">🔧 Config</option>
              </select>
            </div>
          </div>

          {/* Selezione Ruolo AI */}
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, marginBottom: '6px' }}>
              Ruolo AI Specializzato
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
              {AI_ROLES.map((role) => {
                const isSelected = selectedRole === role.id;
                return (
                  <div
                    key={role.id}
                    onClick={() => setSelectedRole(role.id)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      border: isSelected
                        ? '1px solid #00f2fe'
                        : (isLight ? '1px solid #e1e4e8' : '1px solid rgba(255,255,255,0.08)'),
                      background: isSelected
                        ? (isLight ? 'rgba(0, 242, 254, 0.08)' : 'rgba(0, 242, 254, 0.12)')
                        : 'transparent',
                      transition: 'all 0.12s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.76rem', fontWeight: 700 }}>
                      <span>{role.icon}</span>
                      <span>{role.name}</span>
                    </div>
                    <div style={{ fontSize: '0.64rem', color: '#8b949e', marginTop: '2px' }}>
                      {role.desc}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Istruzioni / Prompt Utente */}
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, marginBottom: '5px' }}>
              Istruzioni e Note Concettuali (opzionale)
            </label>
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Descrivi i concetti, formule matematiche, classi o requisiti specifici che l'AI deve integrare..."
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: '6px',
                border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.12)',
                background: isLight ? '#fff' : '#07090e',
                color: isLight ? '#24292f' : '#e6edf3',
                fontSize: '0.76rem',
                outline: 'none',
                resize: 'none'
              }}
            />
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '8px',
          borderTop: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.08)',
          background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)'
        }}>
          <button
            onClick={onClose}
            disabled={loading}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: isLight ? '1px solid #d0d7de' : '1px solid rgba(255,255,255,0.15)',
              background: 'transparent',
              color: isLight ? '#24292f' : '#c9d1d9',
              fontSize: '0.76rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Annulla
          </button>
          <button
            onClick={handleCreate}
            disabled={loading}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: 'linear-gradient(135deg, #00f2fe 0%, #4facfe 100%)',
              color: '#07090e',
              fontSize: '0.76rem',
              fontWeight: 700,
              cursor: loading ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              opacity: loading ? 0.7 : 1
            }}
          >
            <Sparkles size={14} />
            <span>{loading ? 'Generazione...' : 'Crea con AI'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
