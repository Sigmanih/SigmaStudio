// Importazione delle dipendenze necessarie
import React, { useState, useEffect } from 'react';
import { SunIcon, MoonIcon } from 'lucide-react';

// Componente PeerList
const PeerList = ({ isLight }) => {
  const [peers, setPeers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch peers from the API
    fetch('/api/sigma_network/peers')
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok ' + response.statusText);
        }
        return response.json();
      })
      .then(data => {
        setPeers(data);
        setLoading(false);
      })
      .catch(error => {
        setError(error.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (peers.length === 0) {
    return <div>No peers found.</div>;
  }

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <h1>Peer List</h1>
      <ul style={{ listStyleType: 'none', padding: 0, margin: 0, width: '100%' }}>
        {peers.map(peer => (
          <li key={peer.peer_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', borderBottom: '1px solid #ccc', padding: '10px' }}>
            <div>
              <span style={{ marginRight: '10px' }}>Name: {peer.name}</span>
              <span style={{ marginRight: '10px' }}>Host: {peer.host}:{peer.port}</span>
              <span>Status: {peer.status}</span>
            </div>
            <div>
              <button style={{ padding: '5px 10px', margin: '0 5px', backgroundColor: isLight ? '#ddd' : '#333', color: isLight ? '#000' : '#fff', border: 'none', borderRadius: '5px' }}>Trust</button>
              <button style={{ padding: '5px 10px', margin: '0 5px', backgroundColor: isLight ? '#ddd' : '#333', color: isLight ? '#000' : '#fff', border: 'none', borderRadius: '5px' }}>Block</button>
              <button style={{ padding: '5px 10px', margin: '0 5px', backgroundColor: isLight ? '#ddd' : '#333', color: isLight ? '#000' : '#fff', border: 'none', borderRadius: '5px' }}>Remove</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default PeerList;
