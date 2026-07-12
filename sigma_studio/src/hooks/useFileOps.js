import { useState } from 'react';

export function useFileOps({ fetchManifesti, fetchModules, openTab, openTabs, handleFileDelete }) {
  const [isFileModalOpen, setIsFileModalOpen] = useState(false);
  const [fileModalContext, setFileModalContext] = useState({ folder: "", type: "" });
  const [terminalOutput, setTerminalOutput] = useState("Sigma Studio Initialized. Ready for research.\n");

  const handleCreateFile = async (filename) => {
    let { folder, type } = fileModalContext;
    let finalPath = `${folder}/${type}/${filename}`;
    
    if (type === 'whitepaper') {
      finalPath = `${folder}/docs/WHITEPAPER_${filename}`;
    }
    if (type === 'manifesti') {
      finalPath = `manifesti/${filename}`;
    }

    const initialContent = type === 'test' 
      ? "# Sigma Validation Script\nimport os\n\ndef run():\n    print('Validating...')\n\nif __name__ == '__main__':\n    run()" 
      : "# Nuovo Manifesto Sigma\n= = = = = = = = = = = =\n\n**Sezione**: \n\nContenuto del manifesto...";
    
    try {
      const res = await fetch('/api/create_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: finalPath, content: initialContent })
      });
      const data = await res.json();
      if (data.success) {
        setIsFileModalOpen(false);
        if (type === 'manifesti') {
          if (fetchManifesti) fetchManifesti();
        } else {
          if (fetchModules) fetchModules();
        }
        if (openTab) {
          openTab({ path: finalPath, filename: filename.replace('.md', '') }, type);
        }
      }
    } catch (e) {
      alert(e.message);
    }
  };

  const deleteFileDirectly = async (e, path) => {
    if (e && e.stopPropagation) e.stopPropagation();
    if (!confirm(`Sei sicuro di voler eliminare dal progetto il file: ${path}?`)) return;
    try {
      const res = await fetch('/api/delete_file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const data = await res.json();
      if (data.success) {
        const tabMatch = openTabs.find(t => t.path === path);
        if (tabMatch && handleFileDelete) {
          handleFileDelete(tabMatch.id);
        }
        if (fetchModules) fetchModules();
      }
    } catch(e) {
      alert(e.message);
    }
  };

  const runTest = async (path) => {
    setTerminalOutput(`[RUNNING] ${path}...\n`);
    try {
      const res = await fetch('/api/run_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_path: path })
      });
      const data = await res.json();
      setTerminalOutput(prev => prev + (data.stdout || "") + (data.stderr || "") + `\n[EXIT] Code ${data.exit_code}`);
    } catch (e) {
      setTerminalOutput(prev => prev + `[ERROR] ${e.message}`);
    }
  };

  return {
    isFileModalOpen,
    setIsFileModalOpen,
    fileModalContext,
    setFileModalContext,
    terminalOutput,
    setTerminalOutput,
    handleCreateFile,
    deleteFileDirectly,
    runTest
  };
}
