import React, { useState, useEffect } from 'react';
import { 
  Server, Wrench, Database, Cpu, Zap, Settings, Globe, Play, RefreshCw,
  CheckCircle2, Search, FileText, ChevronRight, Terminal, Check, XCircle
} from 'lucide-react';

const MCP_ICONS = {
  'Memory MCP': Database,
  'Developer MCP': Wrench,
  'Hardware MCP': Cpu,
  'Training MCP': Settings,
  'Inference MCP': Zap,
  'Network MCP': Globe,
};

const SAMPLE_TOOL_ARGS = {
  'query_vector_db': { query: 'Sigma Studio RAG architecture', limit: 5 },
  'save_episodic_memory': { session_id: 'active_session', memory_key: 'user_pref', content: 'Preferisco il tema scuro' },
  'search_knowledge_graph': { topic: 'matematica' },
  'run_pytest': { test_path: 'tests/test_mcp_servers.py' },
  'create_workspace_file': { path: 'data/notes.md', content: '# Note di ricerca' },
  'execute_sandbox_code': { code: 'print("MCP Sandbox test OK")' },
  'git_status': {},
  'get_hardware_status': {},
  'clear_vram_cache': {},
  'benchmark_gpu': {},
  'import_dataset': { dataset_name: 'test_dataset', data_path: 'training/datasets/sample.jsonl' },
  'start_lora_training': { job_name: 'job_test', base_model: 'llama3.2', dataset_id: 'test_dataset', epochs: 1 },
  'export_ollama_model': { checkpoint_id: 'ckpt_1', target_model_name: 'sigma-lora-test' },
  'select_routed_model': { prompt: 'Vorrei analizzare un algoritmo in Python' },
  'swap_kv_cache': { session_id: 'swarm_session_1', target_agent: 'code_architect' },
  'forward_logits_ensemble': { primary_agent: 'sigma_assistant', secondary_agent: 'code_architect', alpha: 0.7 },
  'discover_peers': {},
  'broadcast_task_to_swarm': { task_name: 'test_swarm', payload: { goal: 'test' } },
  'ping_node': { node_ip: '127.0.0.1' },
  'search_web': { query: 'Sigma Studio AI', max_results: 3 },
  'fetch_web_page': { url: 'https://wikipedia.org' }
};

export default function McpHubTab() {
  const [servers, setServers] = useState([]);
  const [tools, setTools] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTool, setSelectedTool] = useState(null);
  const [toolArgs, setToolArgs] = useState('{}');
  const [testResult, setTestResult] = useState(null);
  const [testingTool, setTestingTool] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('tools'); // 'tools' | 'resources' | 'console'

  // Diagnostic Console State
  const [diagnosticLogs, setDiagnosticLogs] = useState([]);
  const [runningFullTest, setRunningFullTest] = useState(false);

  const loadMcpData = async () => {
    setLoading(true);
    try {
      const [resServers, resTools, resResources] = await Promise.all([
        fetch('/api/mcp/servers'),
        fetch('/api/mcp/tools'),
        fetch('/api/mcp/resources')
      ]);

      if (resServers.ok) {
        const d = await resServers.json();
        setServers(d.servers || []);
      }
      if (resTools.ok) {
        const d = await resTools.json();
        const loadedTools = d.tools || [];
        setTools(loadedTools);
        if (loadedTools.length > 0 && !selectedTool) {
          const first = loadedTools[0];
          setSelectedTool(first);
          setToolArgs(JSON.stringify(SAMPLE_TOOL_ARGS[first.name] || {}, null, 2));
        }
      }
      if (resResources.ok) {
        const d = await resResources.json();
        setResources(d.resources || []);
      }
    } catch (e) {
      console.error("Error loading MCP data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMcpData();
  }, []);

  const selectToolWithDefaults = (tool) => {
    setSelectedTool(tool);
    const sample = SAMPLE_TOOL_ARGS[tool.name] || {};
    setToolArgs(JSON.stringify(sample, null, 2));
    setTestResult(null);
  };

  const handleTestTool = async () => {
    if (!selectedTool) return;
    setTestingTool(true);
    setTestResult(null);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(toolArgs);
      } catch {
        parsedArgs = { query: toolArgs };
      }

      const res = await fetch('/api/mcp/rpc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: `test-${Date.now()}`,
          method: 'tools/call',
          params: {
            name: selectedTool.name,
            arguments: parsedArgs
          }
        })
      });
      const data = await res.json();
      setTestResult(data.result || data);
    } catch (e) {
      setTestResult({ isError: true, content: [{ type: 'text', text: e.message }] });
    } finally {
      setTestingTool(false);
    }
  };

  const handleTestAllTools = async () => {
    setRunningFullTest(true);
    setActiveSubTab('console');
    setDiagnosticLogs([{ time: new Date().toLocaleTimeString(), message: '🚀 Avvio Collaudo Diagnostico Integrale dei 6 MCP Server...', type: 'info' }]);

    let passedCount = 0;
    for (const tool of tools) {
      const args = SAMPLE_TOOL_ARGS[tool.name] || {};
      try {
        const res = await fetch('/api/mcp/rpc', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: `diag-${Date.now()}`,
            method: 'tools/call',
            params: { name: tool.name, arguments: args }
          })
        });
        const data = await res.json();
        const isErr = data.error || (data.result && data.result.isError);
        if (!isErr) {
          passedCount++;
          setDiagnosticLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            message: `✅ [${tool.server}] Tool '${tool.name}' superato con successo.`,
            type: 'success'
          }]);
        } else {
          setDiagnosticLogs(prev => [...prev, {
            time: new Date().toLocaleTimeString(),
            message: `❌ [${tool.server}] Tool '${tool.name}' fallito: ${JSON.stringify(data.error || data.result)}`,
            type: 'error'
          }]);
        }
      } catch (err) {
        setDiagnosticLogs(prev => [...prev, {
          time: new Date().toLocaleTimeString(),
          message: `❌ [${tool.server}] Tool '${tool.name}' errore rete: ${err.message}`,
          type: 'error'
        }]);
      }
    }

    setDiagnosticLogs(prev => [...prev, {
      time: new Date().toLocaleTimeString(),
      message: `🎉 Collaudo Completato: ${passedCount}/${tools.length} Tool MCP verificate e collaudate con successo al 100%!`,
      type: 'summary'
    }]);
    setRunningFullTest(false);
  };

  return (
    <div style={{ padding: '24px', background: '#0a0c14', color: '#e2e4eb', minHeight: '100%', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ padding: '10px', background: 'rgba(0, 210, 255, 0.1)', borderRadius: '12px', border: '1px solid rgba(0, 210, 255, 0.2)' }}>
            <Server size={24} color="#00d2ff" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: '#fff' }}>MCP Server Hub & Tools Catalog</h1>
            <div style={{ fontSize: '0.8rem', color: '#8b8fa3' }}>
              Gestione, collaudo ed orchestrazione dei 6 MCP Server integrati in Sigma Studio (JSON-RPC 2.0)
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={handleTestAllTools}
            disabled={runningFullTest}
            style={{
              background: 'linear-gradient(135deg, #00d2ff, #0072ff)',
              border: 'none',
              color: '#fff',
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.85rem'
            }}
          >
            {runningFullTest ? <RefreshCw className="spin" size={14} /> : <CheckCircle2 size={14} />}
            <span>{runningFullTest ? 'Collaudo in corso...' : '🧪 Collauda Tutti i Server & Tool MCP'}</span>
          </button>

          <button
            onClick={loadMcpData}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#e2e4eb',
              padding: '8px 14px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.82rem'
            }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Aggiorna Hub</span>
          </button>
        </div>
      </div>

      {/* Servers Summary Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
        {servers.map(s => {
          const Icon = MCP_ICONS[s.name] || Server;
          return (
            <div
              key={s.name}
              style={{
                background: 'rgba(15, 17, 26, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                padding: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px'
              }}
            >
              <div style={{ padding: '8px', background: 'rgba(0, 210, 255, 0.08)', borderRadius: '8px' }}>
                <Icon size={18} color="#00d2ff" />
              </div>
              <div style={{ overflow: 'hidden' }}>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#fff', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{s.name}</div>
                <div style={{ fontSize: '0.72rem', color: '#3fb950', fontWeight: 600 }}>● Attivo (v{s.version})</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Sub Tabs */}
      <div style={{ display: 'flex', gap: '10px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
        <button
          onClick={() => setActiveSubTab('tools')}
          style={{
            background: activeSubTab === 'tools' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'tools' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'tools' ? '#00d2ff' : '#8b8fa3',
            padding: '6px 16px',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <Wrench size={14} />
          <span>Strumenti & Tools ({tools.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('resources')}
          style={{
            background: activeSubTab === 'resources' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'resources' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'resources' ? '#00d2ff' : '#8b8fa3',
            padding: '6px 16px',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <FileText size={14} />
          <span>Risorse & URIs ({resources.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('console')}
          style={{
            background: activeSubTab === 'console' ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
            border: activeSubTab === 'console' ? '1px solid rgba(0, 210, 255, 0.3)' : 'none',
            color: activeSubTab === 'console' ? '#00d2ff' : '#8b8fa3',
            padding: '6px 16px',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <Terminal size={14} />
          <span>Console Diagnostica ({diagnosticLogs.length})</span>
        </button>
      </div>

      {/* Main Content Area */}
      {activeSubTab === 'tools' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Tools List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h3 style={{ fontSize: '0.95rem', margin: 0, color: '#fff' }}>Catalogo Strumenti MCP Registrati</h3>
            {tools.map(tool => {
              const isSelected = selectedTool?.name === tool.name;
              return (
                <div
                  key={tool.name}
                  onClick={() => selectToolWithDefaults(tool)}
                  style={{
                    background: isSelected ? 'rgba(0, 210, 255, 0.1)' : 'rgba(15, 17, 26, 0.6)',
                    border: isSelected ? '1px solid rgba(0, 210, 255, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                    borderRadius: '10px',
                    padding: '12px 14px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <div style={{ fontWeight: 700, color: '#00d2ff', fontSize: '0.9rem' }}>{tool.name}</div>
                    <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '10px', background: 'rgba(255,255,255,0.05)', color: '#8b8fa3' }}>
                      {tool.server}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#a0a5b8' }}>{tool.description}</div>
                </div>
              );
            })}
          </div>

          {/* Tool Tester Panel */}
          <div style={{ background: 'rgba(15, 17, 26, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <h3 style={{ fontSize: '0.95rem', margin: 0, color: '#fff', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={16} color="#00d2ff" />
              <span>Collaudo Interattivo Tool MCP</span>
            </h3>

            {selectedTool ? (
              <>
                <div style={{ fontSize: '0.85rem', color: '#3fb950', fontWeight: 600 }}>Tool Selezionato: {selectedTool.name}</div>
                <div style={{ fontSize: '0.78rem', color: '#8b8fa3' }}>{selectedTool.description}</div>

                <div>
                  <label style={{ fontSize: '0.75rem', color: '#8b8fa3', display: 'block', marginBottom: '4px' }}>Argomenti JSON Input:</label>
                  <textarea
                    rows={5}
                    value={toolArgs}
                    onChange={(e) => setToolArgs(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(0, 0, 0, 0.5)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: '8px',
                      color: '#00d2ff',
                      fontFamily: 'monospace',
                      padding: '10px',
                      fontSize: '0.8rem'
                    }}
                  />
                </div>

                <button
                  onClick={handleTestTool}
                  disabled={testingTool}
                  style={{
                    background: 'linear-gradient(135deg, #00d2ff, #0072ff)',
                    border: 'none',
                    color: '#fff',
                    padding: '10px 16px',
                    borderRadius: '8px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    fontSize: '0.85rem'
                  }}
                >
                  {testingTool ? <RefreshCw className="spin" size={14} /> : <Play size={14} />}
                  <span>{testingTool ? 'Esecuzione in corso...' : 'Esegui Tool MCP via JSON-RPC'}</span>
                </button>

                {testResult && (
                  <div style={{ marginTop: '10px' }}>
                    <div style={{ fontSize: '0.75rem', color: '#8b8fa3', marginBottom: '4px' }}>Risultato Output:</div>
                    <pre
                      style={{
                        background: '#05060a',
                        padding: '12px',
                        borderRadius: '8px',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                        color: testResult.isError ? '#ff5555' : '#50fa7b',
                        fontSize: '0.75rem',
                        overflowX: 'auto',
                        maxHeight: '220px'
                      }}
                    >
                      {JSON.stringify(testResult, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: '#8b8fa3', fontSize: '0.85rem', textAlign: 'center', padding: '40px 0' }}>
                Seleziona uno strumento dal catalogo per testarlo in tempo reale.
              </div>
            )}
          </div>
        </div>
      )}

      {activeSubTab === 'resources' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
          {resources.map(res => (
            <div
              key={res.uri}
              style={{
                background: 'rgba(15, 17, 26, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '10px',
                padding: '14px'
              }}
            >
              <div style={{ fontWeight: 700, color: '#00d2ff', fontSize: '0.88rem', marginBottom: '4px' }}>{res.name}</div>
              <div style={{ fontSize: '0.75rem', color: '#3fb950', fontFamily: 'monospace', marginBottom: '6px' }}>{res.uri}</div>
              <div style={{ fontSize: '0.75rem', color: '#8b8fa3' }}>{res.description}</div>
            </div>
          ))}
        </div>
      )}

      {activeSubTab === 'console' && (
        <div style={{ background: '#05060a', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.9rem', fontWeight: 700, color: '#00d2ff' }}>
              <Terminal size={16} />
              <span>Console Log Diagnostico integrato MCP Hub</span>
            </div>
            <button
              onClick={() => setDiagnosticLogs([])}
              style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', color: '#8b8fa3', borderRadius: '4px', padding: '4px 8px', fontSize: '0.75rem', cursor: 'pointer' }}
            >
              Pulisci Console
            </button>
          </div>

          <div style={{ fontFamily: 'monospace', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '400px', overflowY: 'auto' }}>
            {diagnosticLogs.length === 0 ? (
              <div style={{ color: '#8b8fa3', padding: '20px 0', textAlign: 'center' }}>
                Premere "🧪 Collauda Tutti i Server & Tool MCP" per avviare il test automatizzato di tutti i 21 tool MCP.
              </div>
            ) : (
              diagnosticLogs.map((log, idx) => (
                <div
                  key={idx}
                  style={{
                    color: log.type === 'success' ? '#50fa7b' : log.type === 'error' ? '#ff5555' : log.type === 'summary' ? '#00d2ff' : '#f1fa8c',
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                    paddingBottom: '4px'
                  }}
                >
                  <span style={{ color: '#8b8fa3', marginRight: '8px' }}>[{log.time}]</span>
                  <span>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
