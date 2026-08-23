import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Upload, X, Globe, Lock, CheckCircle2, AlertTriangle, ExternalLink,
  Loader2, RefreshCw, Key, Shield, User, Sparkles
} from 'lucide-react';

export default function HfPublishModal({ model, onClose, isLight, addToast }) {
  const [whoami, setWhoami] = useState(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [targetNamespace, setTargetNamespace] = useState('');
  const [repoSlug, setRepoSlug] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);
  const [commitMsg, setCommitMsg] = useState('Upload model via Sigma Studio');
  const [customCardNotes, setCustomCardNotes] = useState('');

  // Active task monitoring
  const [activeTask, setActiveTask] = useState(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishError, setPublishError] = useState(null);

  // Manual token input if whoami fails
  const [manualToken, setManualToken] = useState('');
  const [testingToken, setTestingToken] = useState(false);

  const pollTimerRef = useRef(null);

  const cardBg = isLight ? '#ffffff' : '#0d1019';
  const cardBorder = isLight ? '1px solid rgba(190, 160, 110, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)';
  const textPrimary = isLight ? '#111827' : '#ffffff';
  const textMuted = isLight ? '#6b7280' : '#8b8fa3';
  const subBg = isLight ? '#f8f5ee' : 'rgba(255, 255, 255, 0.03)';
  const subBorder = isLight ? '1px solid rgba(190, 160, 110, 0.22)' : '1px solid rgba(255, 255, 255, 0.06)';
  const inputBg = isLight ? '#ffffff' : '#141824';

  // Initialize repo slug from model filename
  useEffect(() => {
    if (model) {
      const rawName = (model.filename || model.display_name || model.model_id || 'my-model')
        .replace(/\.[^/.]+$/, '') // remove extension like .gguf
        .replace(/[^a-zA-Z0-9._-]/g, '-');
      setRepoSlug(rawName);
    }
  }, [model]);

  // Fetch current Hugging Face user profile
  const fetchWhoami = useCallback(async (tokenToTest = null) => {
    setLoadingUser(true);
    setPublishError(null);
    try {
      const url = tokenToTest
        ? `/api/models/hf/whoami?token=${encodeURIComponent(tokenToTest)}`
        : '/api/models/hf/whoami';
      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        setWhoami(json);
        if (json.authenticated && json.username) {
          setTargetNamespace(json.username);
        }
      }
    } catch (e) {
      console.error('Error in whoami check:', e);
      setWhoami({ authenticated: false, error: e.message });
    } finally {
      setLoadingUser(false);
      setTestingToken(false);
    }
  }, []);

  useEffect(() => {
    fetchWhoami();
  }, [fetchWhoami]);

  const handleTestManualToken = async () => {
    if (!manualToken.trim()) return;
    setTestingToken(true);
    await fetchWhoami(manualToken.trim());
  };

  // Poll active task status
  const startPollingTask = useCallback((taskId) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);

    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/models/hf/upload/tasks');
        if (res.ok) {
          const json = await res.json();
          if (json.success) {
            const task = (json.tasks || []).find(t => t.task_id === taskId);
            if (task) {
              setActiveTask(task);
              if (task.status === 'completed') {
                setIsPublishing(false);
                clearInterval(pollTimerRef.current);
                if (addToast) addToast(`🎉 Modello pubblicato con successo su Hugging Face!`, 'success');
              } else if (task.status === 'failed' || task.status === 'cancelled') {
                setIsPublishing(false);
                clearInterval(pollTimerRef.current);
                setPublishError(task.error_message || 'Caricamento fallito.');
              }
            }
          }
        }
      } catch (e) {
        console.error('Error polling upload task:', e);
      }
    }, 1200);
  }, [addToast]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  const handleStartPublish = async () => {
    if (!whoami?.authenticated) {
      if (addToast) addToast('Token Hugging Face non valido o mancante', 'error');
      return;
    }
    if (!targetNamespace || !repoSlug) {
      if (addToast) addToast('Specificare il nome del repository (namespace/nome)', 'error');
      return;
    }

    const fullRepoId = `${targetNamespace}/${repoSlug}`.replace(/\/+/g, '/');
    const localPath = model.path || model.filename;

    setIsPublishing(true);
    setPublishError(null);

    try {
      const res = await fetch('/api/models/hf/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          local_path: localPath,
          repo_id: fullRepoId,
          private: isPrivate,
          commit_message: commitMsg || 'Upload model via Sigma Studio',
          model_card: customCardNotes ? `${customCardNotes}\n\n*Uploaded from Sigma Studio.*` : null,
          token: manualToken.trim() || undefined
        })
      });

      const json = await res.json();
      if (res.ok && json.success && json.task) {
        setActiveTask(json.task);
        startPollingTask(json.task.task_id);
        if (addToast) addToast(`🚀 Caricamento avviato verso ${fullRepoId}`, 'info');
      } else {
        setIsPublishing(false);
        setPublishError(json.error || 'Impossibile avviare il caricamento.');
        if (addToast) addToast(`Errore: ${json.error}`, 'error');
      }
    } catch (e) {
      setIsPublishing(false);
      setPublishError(e.message);
      if (addToast) addToast(`Errore di rete: ${e.message}`, 'error');
    }
  };

  const handleCancelTask = async () => {
    if (!activeTask) return;
    try {
      await fetch('/api/models/hf/upload/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: activeTask.task_id })
      });
      setIsPublishing(false);
      if (addToast) addToast('Caricamento annullato', 'warning');
    } catch (e) {
      console.error('Error cancelling upload:', e);
    }
  };

  const fullTargetRepo = `${targetNamespace || 'username'}/${repoSlug || 'repo-name'}`;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px'
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: '640px', maxHeight: '90vh',
          background: cardBg, border: cardBorder, borderRadius: '18px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.5), 0 0 30px rgba(255, 184, 108, 0.15)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden'
        }}
      >
        {/* Modal Header */}
        <div style={{
          padding: '16px 20px', borderBottom: subBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: isLight ? 'rgba(190, 160, 110, 0.08)' : 'rgba(255, 255, 255, 0.02)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '1.4rem' }}>🤗</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                Pubblica su Hugging Face Hub
              </h3>
              <div style={{ fontSize: '0.72rem', color: textMuted, marginTop: '2px' }}>
                Condividi il tuo modello o checkpoint con il tuo profilo Hugging Face
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: textMuted,
              cursor: 'pointer', padding: '6px', borderRadius: '8px',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* 1. Model Info Summary Card */}
          <div style={{
            padding: '12px 14px', borderRadius: '12px',
            background: subBg, border: subBorder,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ fontSize: '0.66rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase' }}>
                FILE DA CARICARE
              </div>
              <div style={{ fontSize: '0.86rem', fontWeight: 800, color: textPrimary, marginTop: '2px', wordBreak: 'break-all' }}>
                {model.filename || model.display_name}
              </div>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <span style={{
                fontSize: '0.70rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px',
                background: 'rgba(0, 210, 255, 0.15)', color: '#00d2ff', border: '1px solid rgba(0, 210, 255, 0.3)'
              }}>
                💾 {model.size_gb ? `${model.size_gb} GB` : (model.size_label || 'Storage Locale')}
              </span>
            </div>
          </div>

          {/* 2. Hugging Face Account Section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.70rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <User size={12} color="#00d2ff" /> Account Hugging Face
            </span>

            {loadingUser ? (
              <div style={{ padding: '12px', borderRadius: '10px', background: subBg, border: subBorder, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: textMuted }}>
                <Loader2 size={14} className="mh-spin" color="#00d2ff" />
                Verifica autorizzazioni Hugging Face...
              </div>
            ) : whoami?.authenticated ? (
              <div style={{
                padding: '10px 14px', borderRadius: '10px',
                background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {whoami.avatar_url ? (
                    <img src={whoami.avatar_url} alt="Avatar" style={{ width: '26px', height: '26px', borderRadius: '50%' }} />
                  ) : (
                    <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.75rem', fontWeight: 800 }}>
                      {whoami.username?.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div>
                    <div style={{ fontSize: '0.80rem', fontWeight: 800, color: textPrimary }}>
                      @{whoami.username} {whoami.fullname && <span style={{ color: textMuted, fontWeight: 500 }}>({whoami.fullname})</span>}
                    </div>
                    <div style={{ fontSize: '0.65rem', color: '#10b981' }}>
                      ✓ Token attivo • Permesso: {whoami.role || 'Scrittura'}
                    </div>
                  </div>
                </div>

                {/* Organization selector if any */}
                {whoami.orgs && whoami.orgs.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.68rem', color: textMuted }}>Pubblica come:</span>
                    <select
                      value={targetNamespace}
                      onChange={e => setTargetNamespace(e.target.value)}
                      style={{
                        background: inputBg, color: textPrimary, border: subBorder,
                        borderRadius: '6px', padding: '4px 8px', fontSize: '0.74rem', fontWeight: 700
                      }}
                    >
                      <option value={whoami.username}>@{whoami.username} (Personale)</option>
                      {whoami.orgs.map(org => (
                        <option key={org.name} value={org.name}>🏢 {org.fullname || org.name}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            ) : (
              <div style={{
                padding: '12px 14px', borderRadius: '10px',
                background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.3)',
                display: 'flex', flexDirection: 'column', gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.76rem', color: '#ef4444', fontWeight: 700 }}>
                  <AlertTriangle size={14} /> Token Hugging Face non rilevato o non valido
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <input
                    type="password"
                    placeholder="Incolla il tuo Hugging Face Access Token (hf_...)"
                    value={manualToken}
                    onChange={e => setManualToken(e.target.value)}
                    style={{
                      flex: 1, padding: '7px 10px', borderRadius: '8px',
                      background: inputBg, border: subBorder, color: textPrimary,
                      fontSize: '0.76rem'
                    }}
                  />
                  <button
                    onClick={handleTestManualToken}
                    disabled={testingToken || !manualToken.trim()}
                    style={{
                      padding: '7px 14px', borderRadius: '8px', border: 'none',
                      background: 'linear-gradient(135deg, #00d2ff, #0090ff)', color: '#ffffff',
                      fontSize: '0.74rem', fontWeight: 800, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '4px'
                    }}
                  >
                    {testingToken ? <Loader2 size={12} className="mh-spin" /> : <Key size={12} />}
                    Collega
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 3. Repository Configuration */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.70rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase' }}>
                Nome Repository Target
              </label>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '8px 12px', borderRadius: '10px', background: inputBg, border: subBorder
              }}>
                <span style={{ fontSize: '0.80rem', fontWeight: 800, color: '#00d2ff' }}>
                  {targetNamespace || 'username'} /
                </span>
                <input
                  type="text"
                  value={repoSlug}
                  onChange={e => setRepoSlug(e.target.value.replace(/[^a-zA-Z0-9._-]/g, '-'))}
                  placeholder="nome-del-modello"
                  disabled={isPublishing}
                  style={{
                    flex: 1, background: 'transparent', border: 'none', outline: 'none',
                    color: textPrimary, fontSize: '0.82rem', fontWeight: 800
                  }}
                />
              </div>
              <div style={{ fontSize: '0.65rem', color: textMuted }}>
                URL finale: <span style={{ color: '#00d2ff' }}>https://huggingface.co/{fullTargetRepo}</span>
              </div>
            </div>

            {/* Visibility Toggle */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.70rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase' }}>
                Visibilità Repository
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div
                  onClick={() => !isPublishing && setIsPrivate(false)}
                  style={{
                    padding: '10px 12px', borderRadius: '10px', cursor: 'pointer',
                    background: !isPrivate ? 'rgba(0, 210, 255, 0.12)' : subBg,
                    border: !isPrivate ? '1.5px solid #00d2ff' : subBorder,
                    display: 'flex', alignItems: 'center', gap: '8px'
                  }}
                >
                  <Globe size={16} color={!isPrivate ? '#00d2ff' : textMuted} />
                  <div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 800, color: !isPrivate ? '#00d2ff' : textPrimary }}>
                      Pubblico 🌐
                    </div>
                    <div style={{ fontSize: '0.62rem', color: textMuted }}>
                      Visibile a tutta la community HF
                    </div>
                  </div>
                </div>

                <div
                  onClick={() => !isPublishing && setIsPrivate(true)}
                  style={{
                    padding: '10px 12px', borderRadius: '10px', cursor: 'pointer',
                    background: isPrivate ? 'rgba(255, 184, 108, 0.12)' : subBg,
                    border: isPrivate ? '1.5px solid #ffb86c' : subBorder,
                    display: 'flex', alignItems: 'center', gap: '8px'
                  }}
                >
                  <Lock size={16} color={isPrivate ? '#ffb86c' : textMuted} />
                  <div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 800, color: isPrivate ? '#ffb86c' : textPrimary }}>
                      Privato 🔒
                    </div>
                    <div style={{ fontSize: '0.62rem', color: textMuted }}>
                      Accessibile solo al tuo account
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Commit Message */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.70rem', fontWeight: 800, color: textMuted, textTransform: 'uppercase' }}>
                Messaggio di Commit
              </label>
              <input
                type="text"
                value={commitMsg}
                onChange={e => setCommitMsg(e.target.value)}
                placeholder="Upload model via Sigma Studio"
                disabled={isPublishing}
                style={{
                  padding: '8px 12px', borderRadius: '8px', background: inputBg,
                  border: subBorder, color: textPrimary, fontSize: '0.76rem'
                }}
              />
            </div>
          </div>

          {/* 4. Active Upload Task Monitoring */}
          {activeTask && (
            <div style={{
              padding: '14px 16px', borderRadius: '12px',
              background: activeTask.status === 'completed'
                ? 'rgba(16, 185, 129, 0.10)'
                : activeTask.status === 'failed'
                ? 'rgba(239, 68, 68, 0.10)'
                : 'rgba(0, 210, 255, 0.08)',
              border: activeTask.status === 'completed'
                ? '1px solid rgba(16, 185, 129, 0.3)'
                : activeTask.status === 'failed'
                ? '1px solid rgba(239, 68, 68, 0.3)'
                : '1px solid rgba(0, 210, 255, 0.3)',
              display: 'flex', flexDirection: 'column', gap: '8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <span style={{ fontWeight: 800, color: textPrimary, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {activeTask.status === 'uploading' && <Loader2 size={13} className="mh-spin" color="#00d2ff" />}
                  {activeTask.status === 'completed' && <CheckCircle2 size={14} color="#10b981" />}
                  {activeTask.status === 'failed' && <AlertTriangle size={14} color="#ef4444" />}
                  {activeTask.status === 'uploading' ? 'Caricamento in corso su Hugging Face...' :
                   activeTask.status === 'completed' ? 'Pubblicazione completata!' :
                   activeTask.status === 'cancelled' ? 'Caricamento annullato.' : 'Caricamento fallito.'}
                </span>
                <span style={{ fontWeight: 800, color: '#00d2ff' }}>
                  {activeTask.progress_pct}%
                </span>
              </div>

              {/* Progress bar */}
              <div style={{ height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${activeTask.progress_pct}%`,
                  background: activeTask.status === 'completed' ? '#10b981' : 'linear-gradient(90deg, #00d2ff, #3a7bd5)',
                  transition: 'width 0.3s ease'
                }} />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.68rem', color: textMuted }}>
                <span>{activeTask.uploaded_label}</span>
                {activeTask.speed_label && <span>⚡ {activeTask.speed_label}</span>}
              </div>

              {activeTask.status === 'completed' && (
                <div style={{ marginTop: '4px', paddingTop: '8px', borderTop: subBorder }}>
                  <a
                    href={activeTask.hf_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      color: '#10b981', fontWeight: 800, fontSize: '0.78rem', textDecoration: 'none'
                    }}
                  >
                    🔗 Apri il repository su Hugging Face <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </div>
          )}

          {/* Error Message */}
          {publishError && (
            <div style={{
              padding: '10px 12px', borderRadius: '8px',
              background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444', fontSize: '0.74rem', display: 'flex', alignItems: 'center', gap: '6px'
            }}>
              <AlertTriangle size={13} /> {publishError}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '14px 20px', borderTop: subBorder,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: isLight ? 'rgba(190, 160, 110, 0.05)' : 'rgba(255, 255, 255, 0.01)'
        }}>
          <button
            onClick={onClose}
            disabled={isPublishing}
            style={{
              padding: '8px 16px', borderRadius: '8px', border: subBorder,
              background: subBg, color: textPrimary, fontSize: '0.76rem',
              fontWeight: 700, cursor: 'pointer'
            }}
          >
            Chiudi
          </button>

          {isPublishing ? (
            <button
              onClick={handleCancelTask}
              style={{
                padding: '8px 16px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.4)',
                background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444',
                fontSize: '0.76rem', fontWeight: 800, cursor: 'pointer'
              }}
            >
              Annulla Caricamento
            </button>
          ) : activeTask?.status === 'completed' ? (
            <a
              href={activeTask.hf_url}
              target="_blank"
              rel="noreferrer"
              style={{
                padding: '8px 18px', borderRadius: '8px', border: 'none',
                background: 'linear-gradient(135deg, #10b981, #00d2ff)', color: '#ffffff',
                fontSize: '0.76rem', fontWeight: 800, textDecoration: 'none',
                display: 'flex', alignItems: 'center', gap: '5px',
                boxShadow: '0 0 12px rgba(16, 185, 129, 0.3)'
              }}
            >
              <ExternalLink size={13} /> Visualizza su Hugging Face
            </a>
          ) : (
            <button
              onClick={handleStartPublish}
              disabled={!whoami?.authenticated || !repoSlug}
              style={{
                padding: '8px 20px', borderRadius: '8px', border: 'none',
                background: (!whoami?.authenticated || !repoSlug)
                  ? 'rgba(255,255,255,0.1)'
                  : 'linear-gradient(135deg, #ffb86c, #ea580c)',
                color: (!whoami?.authenticated || !repoSlug) ? textMuted : '#ffffff',
                fontSize: '0.76rem', fontWeight: 800,
                cursor: (!whoami?.authenticated || !repoSlug) ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: '6px',
                boxShadow: (!whoami?.authenticated || !repoSlug) ? 'none' : '0 0 14px rgba(255, 184, 108, 0.3)'
              }}
            >
              <Upload size={13} /> Pubblica su Hugging Face
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
