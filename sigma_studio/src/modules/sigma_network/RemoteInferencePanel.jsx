// RemoteInferencePanel.jsx
import React, { useState } from 'react';
import { LucideUsers, LucideMessageSquare } from 'lucide-react';

const RemoteInferencePanel = () => {
  const [peer, setPeer] = useState('');
  const [model, setModel] = useState('');
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [cost, setCost] = useState(0);

  const handleInference = () => {
    // Implement inference logic here
    fetch('/api/sigma_network/inference/remote', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ peer, model, prompt })
    })
    .then(response => response.json())
    .then(data => {
      setResponse(data.response);
      setCost(data.cost);
    });
  };

  return (
    <div className='remote-inference-panel'>
      <h2>Remote Inference</h2>
      <div className='setting'>
        <LucideUsers />
        <label>
          Peer:
          <input
            type='text'
            value={peer}
            onChange={(e) => setPeer(e.target.value)}
          />
        </label>
      </div>
      <div className='setting'>
        <LucideMessageSquare />
        <label>
          Model:
          <input
            type='text'
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
        </label>
      </div>
      <div className='setting'>
        <LucideMessageSquare />
        <label>
          Prompt:
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </label>
      </div>
      <button onClick={handleInference}>Run Inference</button>
      <div className='response'>
        <h3>Response:</h3>
        <p>{response}</p>
      </div>
      <div className='cost'>
        <h3>Cost:</h3>
        <p>{cost} AiloCoin</p>
      </div>
    </div>
  );
};

export default RemoteInferencePanel;
