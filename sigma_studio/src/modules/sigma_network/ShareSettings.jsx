// ShareSettings.jsx
import React, { useState } from 'react';
import { LucideSwitchHorizontal, LucideDatabase, LucideDollarSign, LucideHash } from 'lucide-react';

const ShareSettings = () => {
  const [settings, setSettings] = useState({
    sharingEnabled: false,
    sharedModels: [],
    tokenPerUnit: 0,
    maxTokensPerRequest: 0,
    concurrentRequests: 0,
    hourlyRequests: 0,
    displayName: ''
  });

  const handleSave = () => {
    // Implement save logic here
    alert('Settings saved!');
  };

  return (
    <div className='share-settings'>
      <h2>Share Settings</h2>
      <div className='setting'>
        <LucideSwitchHorizontal />
        <label>
          <input
            type='checkbox'
            checked={settings.sharingEnabled}
            onChange={(e) => setSettings({ ...settings, sharingEnabled: e.target.checked })}
          />
          Enable Sharing
        </label>
      </div>
      <div className='setting'>
        <LucideDatabase />
        <label>
          Shared Models:
          <select multiple value={settings.sharedModels} onChange={(e) => setSettings({ ...settings, sharedModels: Array.from(e.target.selectedOptions).map(option => option.value) })}>
            {/* Add options for models here */}
          </select>
        </label>
      </div>
      <div className='setting'>
        <LucideDollarSign />
        <label>
          Token per Unit:
          <input
            type='number'
            value={settings.tokenPerUnit}
            onChange={(e) => setSettings({ ...settings, tokenPerUnit: parseInt(e.target.value) })}
          />
        </label>
      </div>
      <div className='setting'>
        <LucideHash />
        <label>
          Max Tokens per Request:
          <input
            type='number'
            value={settings.maxTokensPerRequest}
            onChange={(e) => setSettings({ ...settings, maxTokensPerRequest: parseInt(e.target.value) })}
          />
        </label>
      </div>
      <div className='setting'>
        <LucideHash />
        <label>
          Concurrent Requests:
          <input
            type='number'
            value={settings.concurrentRequests}
            onChange={(e) => setSettings({ ...settings, concurrentRequests: parseInt(e.target.value) })}
          />
        </label>
      </div>
      <div className='setting'>
        <LucideHash />
        <label>
          Hourly Requests:
          <input
            type='number'
            value={settings.hourlyRequests}
            onChange={(e) => setSettings({ ...settings, hourlyRequests: parseInt(e.target.value) })}
          />
        </label>
      </div>
      <div className='setting'>
        <LucideHash />
        <label>
          Display Name:
          <input
            type='text'
            value={settings.displayName}
            onChange={(e) => setSettings({ ...settings, displayName: e.target.value })}
          />
        </label>
      </div>
      <button onClick={handleSave}>Save Settings</button>
    </div>
  );
};

export default ShareSettings;
