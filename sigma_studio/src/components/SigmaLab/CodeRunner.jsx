import React, { useState, useRef, useEffect } from 'react';
import { Play, Square, Terminal, Loader } from 'lucide-react';

// ==============================================================================
// CodeRunner — Esecuzione script Python con output in tempo reale
// ==============================================================================

export default function CodeRunner({ scriptPath, initialOutput = '' }) {
  const [output, setOutput] = useState(initialOutput);
  const [running, setRunning] = useState(false);
  const [exitCode, setExitCode] = useState(null);
  const outputRef = useRef(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const handleRun = async () => {
    if (!scriptPath || running) return;
    
    setRunning(true);
    setOutput('');
    setExitCode(null);

    try {
      const res = await fetch('/api/run_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_path: scriptPath })
      });
      const data = await res.json();
      
      const lines = [];
      if (data.stdout) lines.push(data.stdout);
      if (data.stderr) {
        lines.push('\n--- STDERR ---\n');
        lines.push(data.stderr);
      }
      lines.push(`\n[EXIT] Code ${data.exit_code}`);
      
      setOutput(lines.join(''));
      setExitCode(data.exit_code);
    } catch (e) {
      setOutput(`[ERROR] ${e.message}`);
      setExitCode(-1);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="code-runner">
      <div className="code-runner-header">
        <div className="code-runner-path">
          <Terminal size={14} /> {scriptPath}
        </div>
        <button 
          className={`btn ${running ? 'running' : 'run'}`} 
          onClick={handleRun}
          disabled={running}
        >
          {running ? (
            <>
              <Loader size={14} className="spin" /> In esecuzione...
            </>
          ) : (
            <>
              <Play size={14} /> Esegui Test
            </>
          )}
        </button>
      </div>
      <div className="code-runner-output" ref={outputRef}>
        {output || 'Nessun output. Premi "Esegui Test" per avviare.'}
      </div>
      {exitCode !== null && (
        <div className={`code-runner-status ${exitCode === 0 ? 'ok' : 'error'}`}>
          {exitCode === 0 ? '✅ Test passato' : '❌ Test fallito'} — Exit code: {exitCode}
        </div>
      )}
    </div>
  );
}