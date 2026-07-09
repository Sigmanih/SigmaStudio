import React, { useState, useEffect } from 'react';
import { Globe, ExternalLink, Loader } from 'lucide-react';

// ==============================================================================
// HtmlPreview — Visualizzatore pagine HTML con iframe sandbox
// ==============================================================================

export default function HtmlPreview({ htmlPath }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    
    // Check if file exists
    if (!htmlPath) {
      setError('Nessun path HTML specificato');
      setLoading(false);
      return;
    }

    // For HTML files, we just need to serve them directly
    // The iframe will load from the relative path
    setLoading(false);
  }, [htmlPath]);

  if (error) {
    return <div className="placeholder-content">{error}</div>;
  }

  return (
    <div className="html-preview">
      <div className="html-preview-header">
        <div className="html-preview-path">
          <Globe size={14} /> {htmlPath}
        </div>
        <a 
          href={htmlPath} 
          target="_blank" 
          rel="noopener noreferrer"
          className="btn btn-outline"
          title="Apri in nuova finestra"
        >
          <ExternalLink size={14} /> Apri
        </a>
      </div>
      {loading ? (
        <div className="placeholder-content">
          <Loader size={20} className="spin" /> Caricamento...
        </div>
      ) : (
        <iframe 
          src={htmlPath} 
          className="html-preview-frame"
          title="HTML Preview"
          onError={() => setError('Errore nel caricamento del file HTML')}
        />
      )}
    </div>
  );
}