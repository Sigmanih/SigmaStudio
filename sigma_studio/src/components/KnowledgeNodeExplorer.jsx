import React, { useState, useEffect } from 'react';
import { 
  Folder, FolderPlus, FileText, Code, Globe, Play, Image as ImageIcon,
  ChevronRight, ChevronDown, Plus, Trash2, RefreshCw, Eye, ExternalLink, Terminal, Layers
} from 'lucide-react';

const FILE_TYPE_ICONS = {
  markdown: FileText,
  python: Code,
  javascript: Code,
  html: Globe,
  image: ImageIcon,
  json: Terminal,
  text: FileText
};

export default function KnowledgeNodeExplorer() {
  const [nodes, setNodes] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [loadingFile, setLoadingFile] = useState(false);
  const [viewMode, setViewMode] = useState('code'); // 'code' | 'app_runner' | 'preview'

  // New Node Modal State
  const [showNewNodeModal, setShowNewNodeModal] = useState(false);
  const [newNodeName, setNewNodeName] = useState('');
  const [creatingNode, setCreatingNode] = useState(false);

  const fetchNodes = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/nodes');
      if (res.ok) {
        const data = await res.json();
        setNodes(data.nodes || {});
        const keys = Object.keys(data.nodes || {});
        if (keys.length > 0 && !selectedNodeId) {
          setSelectedNodeId(keys[0]);
        }
      }
    } catch (e) {
      console.error("Error fetching knowledge nodes:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNodes();
  }, []);

  const handleSelectFile = async (file) => {
    setSelectedFile(file);
    setLoadingFile(true);
    setFileContent('');

    // Check if file is HTML/App
    if (file.type === 'html' || file.name.endsWith('.html')) {
      setViewMode('app_runner');
    } else {
      setViewMode('code');
    }

    try {
      const res = await fetch(`/api/view_file?file_path=${encodeURIComponent(file.path)}`);
      if (res.ok) {
        const text = await res.text();
        setFileContent(text);
      }
    } catch (e) {
      setFileContent(`// Error loading file: ${e.message}`);
    } finally {
      setLoadingFile(false);
    }
  };

  const handleCreateNode = async () => {
    if (!newNodeName.trim()) return;
    setCreatingNode(true);
    try {
      const targetPath = selectedNodeId ? `${selectedNodeId}/${newNodeName.trim().toLowerCase().replace(/\s+/g, '_')}` : newNodeName.trim().toLowerCase().replace(/\s+/g, '_');
      const res = await fetch('/api/nodes/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_path: targetPath })
      });
      if (res.ok) {
        setNewNodeName('');
        setShowNewNodeModal(false);
        await fetchNodes();
        setSelectedNodeId(targetPath);
      }
    } catch (e) {
      console.error("Failed to create node:", e);
    } finally {
      setCreatingNode(false);
    }
  };

  const currentNode = nodes[selectedNodeId] || null;

  return (
    <div style={{ background: '#0a0c14', color: '#e2e4eb', minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Hero Visual Banner matching Domotica & Bacheca Header Style */}
      <div style={{
        position: 'relative',
        zIndex: 1,
        borderRadius: 0,
        overflow: 'hidden',
        padding: '20px 32px 18px 32px',
        minHeight: '100px',
        borderBottom: '1px solid rgba(0, 210, 255, 0.25)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        backgroundImage: 'linear-gradient(to right, rgba(28, 12, 4, 0.96) 35%, rgba(120, 45, 10, 0.6) 75%, rgba(234, 88, 12, 0.22) 100%), url("/images/hero_banner.jpg")',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center center',
        marginBottom: '20px',
        flexShrink: 0
      }}>
        <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ maxWidth: '680px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '3px 12px', borderRadius: '14px',
              background: 'rgba(0, 210, 255, 0.15)', border: '1px solid rgba(0, 210, 255, 0.35)',
              color: '#00d2ff', fontSize: '0.68rem', fontWeight: 800, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: '6px'
            }}>
              <Layers size={14} /> UNIVERSAL KNOWLEDGE GRAPH & APP EXPLORER
            </div>
            <h1 style={{ margin: '0 0 4px 0', fontSize: '1.35rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px' }}>
              🌐 Universal Knowledge Nodes & App Explorer
            </h1>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#ffffff', lineHeight: 1.4 }}>
              Gestione nodi gerarchici universali, codice, documenti ed applicativi integrati in Sigma Studio.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              onClick={fetchNodes}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#e2e4eb',
                padding: '10px 16px',
                borderRadius: '12px',
                fontWeight: 800,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <RefreshCw size={15} className={loading ? 'spin' : ''} />
              <span>Aggiorna Nodi</span>
            </button>
            <button
              onClick={() => setShowNewNodeModal(true)}
              style={{
                background: 'linear-gradient(135deg, #00d2ff, #0072ff)',
                border: 'none',
                color: '#fff',
                padding: '10px 18px',
                borderRadius: '12px',
                fontWeight: 800,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 4px 16px rgba(0,210,255,0.3)'
              }}
            >
              <FolderPlus size={15} />
              <span>Nuovo Nodo / App Folder</span>
            </button>
          </div>
        </div>
      </div>

      <div style={{ padding: '0 24px 24px 24px', display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
        {/* Main Grid: Tree Explorer + Node Details & Content Runner */}
      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '20px' }}>
        
        {/* Node Tree Navigation */}
        <div style={{ background: 'rgba(15, 17, 26, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h3 style={{ fontSize: '0.9rem', margin: 0, color: '#fff', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Folder size={16} color="#00d2ff" />
            <span>Albero Nodi di Conoscenza</span>
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '550px', overflowY: 'auto' }}>
            {Object.values(nodes).map(node => {
              const isSelected = selectedNodeId === node.id;
              const isChild = !!node.parent_id;
              return (
                <div
                  key={node.id}
                  onClick={() => {
                    setSelectedNodeId(node.id);
                    setSelectedFile(null);
                  }}
                  style={{
                    padding: '8px 12px',
                    marginLeft: isChild ? '16px' : '0px',
                    background: isSelected ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                    border: isSelected ? '1px solid rgba(0, 210, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.05)',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                    <Folder size={15} color={node.has_app ? '#50fa7b' : '#00d2ff'} />
                    <span style={{ fontSize: '0.82rem', color: isSelected ? '#fff' : '#c0c5d6', fontWeight: isSelected ? 700 : 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {node.name}
                    </span>
                  </div>
                  {node.has_app && (
                    <span style={{ fontSize: '0.65rem', padding: '2px 6px', background: 'rgba(80, 250, 123, 0.15)', color: '#50fa7b', borderRadius: '6px', fontWeight: 600 }}>
                      APP
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Node Workspace / Viewer */}
        <div style={{ background: 'rgba(15, 17, 26, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {currentNode ? (
            <>
              {/* Node Header Info */}
              <div style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>{currentNode.name}</span>
                    <span style={{ fontSize: '0.7rem', color: '#8b8fa3', fontFamily: 'monospace' }}>({currentNode.folder})</span>
                  </h2>
                  <div style={{ fontSize: '0.8rem', color: '#8b8fa3', marginTop: '4px' }}>{currentNode.description}</div>
                </div>

                {currentNode.has_app && (
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => {
                        const mainHtml = currentNode.files.find(f => f.type === 'html' || f.is_entrypoint);
                        if (mainHtml) handleSelectFile(mainHtml);
                      }}
                      style={{
                        background: 'rgba(80, 250, 123, 0.15)',
                        border: '1px solid rgba(80, 250, 123, 0.3)',
                        color: '#50fa7b',
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontWeight: 600,
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <Play size={14} />
                      <span>Esegui App del Nodo</span>
                    </button>
                  </div>
                )}
              </div>

              {/* File List in Current Node */}
              <div>
                <div style={{ fontSize: '0.8rem', color: '#8b8fa3', marginBottom: '8px', fontWeight: 600 }}>File & Applicativi Contenuti ({currentNode.files.length}):</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                  {currentNode.files.map(file => {
                    const isSelected = selectedFile?.path === file.path;
                    const Icon = FILE_TYPE_ICONS[file.type] || FileText;
                    return (
                      <div
                        key={file.path}
                        onClick={() => handleSelectFile(file)}
                        style={{
                          background: isSelected ? 'rgba(0, 210, 255, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          border: isSelected ? '1px solid rgba(0, 210, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                          borderRadius: '8px',
                          padding: '8px 12px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px'
                        }}
                      >
                        <Icon size={16} color={file.type === 'html' ? '#50fa7b' : file.type === 'python' ? '#ff79c6' : '#00d2ff'} />
                        <span style={{ fontSize: '0.82rem', color: isSelected ? '#fff' : '#c0c5d6' }}>{file.name}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Dynamic Content Viewer / Web App Embedded Runner */}
              {selectedFile ? (
                <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontSize: '0.85rem', color: '#00d2ff', fontWeight: 600 }}>Visualizzatore: {selectedFile.name}</div>
                    
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => setViewMode('code')}
                        style={{
                          background: viewMode === 'code' ? 'rgba(0, 210, 255, 0.2)' : 'transparent',
                          border: '1px solid rgba(0, 210, 255, 0.3)',
                          color: '#00d2ff',
                          padding: '4px 10px',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          cursor: 'pointer'
                        }}
                      >
                        Codice / Testo
                      </button>

                      {(selectedFile.type === 'html' || selectedFile.name.endsWith('.html')) && (
                        <button
                          onClick={() => setViewMode('app_runner')}
                          style={{
                            background: viewMode === 'app_runner' ? 'rgba(80, 250, 123, 0.2)' : 'transparent',
                            border: '1px solid rgba(80, 250, 123, 0.3)',
                            color: '#50fa7b',
                            padding: '4px 10px',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <Play size={12} />
                          <span>Esegui App Web Live</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {viewMode === 'app_runner' ? (
                    <div style={{ border: '1px solid rgba(80, 250, 123, 0.3)', borderRadius: '8px', overflow: 'hidden', height: '400px', background: '#fff' }}>
                      <iframe
                        srcDoc={fileContent}
                        title={selectedFile.name}
                        style={{ width: '100%', height: '100%', border: 'none' }}
                      />
                    </div>
                  ) : (
                    <pre
                      style={{
                        background: '#05060a',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: '8px',
                        padding: '14px',
                        color: '#f8f8f2',
                        fontSize: '0.8rem',
                        fontFamily: 'monospace',
                        maxHeight: '400px',
                        overflowY: 'auto',
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {loadingFile ? 'Caricamento contenuto...' : fileContent}
                    </pre>
                  )}
                </div>
              ) : (
                <div style={{ color: '#8b8fa3', fontSize: '0.85rem', textAlign: 'center', padding: '40px 0' }}>
                  Seleziona un file dal nodo per aprirne il codice o avviarne l'applicazione.
                </div>
              )}
            </>
          ) : (
            <div style={{ color: '#8b8fa3', fontSize: '0.85rem', textAlign: 'center', padding: '60px 0' }}>
              Nessun nodo selezionato.
            </div>
          )}
        </div>
      </div>
      </div>

      {/* New Node Modal */}
      {showNewNodeModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#0f111a', border: '1px solid rgba(0, 210, 255, 0.3)', borderRadius: '12px', padding: '24px', width: '400px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <h3 style={{ margin: 0, color: '#fff' }}>Crea Nuovo Nodo o Cartella App</h3>
            <input
              type="text"
              placeholder="Nome del nodo (es. simulazioni_fisica)"
              value={newNodeName}
              onChange={(e) => setNewNodeName(e.target.value)}
              style={{
                background: 'rgba(0,0,0,0.5)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px',
                color: '#fff',
                padding: '10px',
                fontSize: '0.85rem'
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setShowNewNodeModal(false)}
                style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', color: '#8b8fa3', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
              >
                Annulla
              </button>
              <button
                onClick={handleCreateNode}
                disabled={creatingNode}
                style={{ background: 'linear-gradient(135deg, #00d2ff, #0072ff)', border: 'none', color: '#fff', padding: '6px 14px', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}
              >
                Crea Nodo
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
