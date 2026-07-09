import React, { useState, useEffect, useCallback, useRef } from 'react';

// ==============================================================================
// ToastNotification — Notifiche temporanee in basso a destra
// Mostra avanzamento loop, task completati, errori
// ==============================================================================

let toastIdCounter = 0;

export function useToast() {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef({});

  const addToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = ++toastIdCounter;
    setToasts(prev => [...prev, { id, message, type, timestamp: Date.now() }]);
    
    if (duration > 0) {
      timersRef.current[id] = setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
        delete timersRef.current[id];
      }, duration);
    }
    
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    if (timersRef.current[id]) {
      clearTimeout(timersRef.current[id]);
      delete timersRef.current[id];
    }
  }, []);

  const clearAll = useCallback(() => {
    Object.values(timersRef.current).forEach(clearTimeout);
    timersRef.current = {};
    setToasts([]);
  }, []);

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach(clearTimeout);
    };
  }, []);

  return { toasts, addToast, removeToast, clearAll };
}

const TOAST_COLORS = {
  info: { bg: 'rgba(0,210,255,0.12)', border: 'rgba(0,210,255,0.25)', icon: 'ℹ️', color: '#00d2ff' },
  success: { bg: 'rgba(63,185,80,0.12)', border: 'rgba(63,185,80,0.25)', icon: '✅', color: '#3fb950' },
  warning: { bg: 'rgba(210,153,34,0.12)', border: 'rgba(210,153,34,0.25)', icon: '⚠️', color: '#d29922' },
  error: { bg: 'rgba(248,81,73,0.12)', border: 'rgba(248,81,73,0.25)', icon: '❌', color: '#f85149' },
  loop: { bg: 'rgba(188,140,255,0.12)', border: 'rgba(188,140,255,0.25)', icon: '🔄', color: '#bc8cff' },
  task: { bg: 'rgba(88,166,255,0.12)', border: 'rgba(88,166,255,0.25)', icon: '📋', color: '#58a6ff' },
};

export default function ToastNotification({ toasts, removeToast }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map(t => {
        const style = TOAST_COLORS[t.type] || TOAST_COLORS.info;
        return (
          <div
            key={t.id}
            className="toast-item"
            style={{
              background: style.bg,
              borderColor: style.border,
              '--toast-color': style.color,
            }}
            onClick={() => removeToast(t.id)}
          >
            <span className="toast-icon">{style.icon}</span>
            <span className="toast-message">{t.message}</span>
            <button className="toast-close" onClick={(e) => { e.stopPropagation(); removeToast(t.id); }}>✕</button>
          </div>
        );
      })}
    </div>
  );
}