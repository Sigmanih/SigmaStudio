import React, { useCallback, useEffect, useState } from 'react';
import {
  HardDrive, AlertTriangle, CheckCircle2, Circle, Zap, Play, RefreshCw, Cpu
} from 'lucide-react';

// Gli stessi cinque stati del backend, con l'ordine che conta.
const STATES = [
  { id: 'installed', label: 'Installato', icon: Circle,
    hint: 'Il file è su disco ma nessun runtime lo espone.' },
  { id: 'available', label: 'Disponibile', icon: CheckCircle2,
    hint: 'Il backend lo espone e può caricarlo.' },
  { id: 'loaded', label: 'Caricato', icon: Zap,
    hint: 'Usato di recente: verosimilmente ancora in VRAM.' },
  { id: 'active', label: 'In uso', icon: Play,
    hint: 'Sta eseguendo un job adesso.' },
];

const STATE_BY_ID = Object.fromEntries(STATES.map(s => [s.id, s]));

/**
 * Inventario dei modelli nei loro stati reali.
 *
 * "Il file esiste" e "il backend può usarlo" sono fatti diversi con fonti
 * diverse: tenerli separati è ciò che evita di mostrare un checkpoint sul disco
 * accanto a un conteggio a zero.
 */
export default function ModelInventory({ onRefresh }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setBusy(true);
    return fetch('/api/creative/models/inventory')
      .then(r => r.json())
      .then(d => (d.success ? setData(d) : setError(d.error)))
      .catch(e => setError(e.message))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error) return <div className="cs-banner warn"><AlertTriangle size={15} /><span>{error}</span></div>;
  if (!data) return <p className="cs-hint">Lettura inventario...</p>;

  const categories = Object.entries(data.categories).filter(([, c]) => c.models.length);
  const stats = data.backend_stats || {};

  return (
    <div className="cs-inventory">
      <div className="cs-downloads-head">
        <div>
          <h3 className="cs-mesh-title"><HardDrive size={18} /> Inventario modelli</h3>
          <p className="cs-hint">
            {data.runtime_reachable
              ? <>Runtime <strong>{data.backend}</strong> attivo{stats.version ? ` · v${stats.version}` : ''}</>
              : <><AlertTriangle size={12} /> Runtime <strong>{data.backend}</strong> non in esecuzione: i file
                restano installati ma nessuno può caricarli.</>}
          </p>
        </div>
        <button className="cs-copy-btn" onClick={() => { load(); onRefresh?.(); }} disabled={busy}>
          <RefreshCw size={11} /> Aggiorna
        </button>
      </div>

      <div className="cs-state-legend">
        {STATES.map(s => (
          <span key={s.id} className={`cs-state-chip ${s.id}`} title={s.hint}>
            <s.icon size={11} /> {s.label}
            <em>{data.totals[s.id] || 0}</em>
          </span>
        ))}
      </div>

      {stats.devices?.length > 0 && (
        <div className="cs-device-row">
          {stats.devices.map(d => (
            <span key={d.name} className="cs-hint">
              <Cpu size={12} /> {d.name.split(':').pop().trim()} — {d.vram_free_gb}/{d.vram_total_gb} GB liberi
              {d.torch_vram_used_gb > 0 && ` · ${d.torch_vram_used_gb} GB in uso`}
            </span>
          ))}
        </div>
      )}

      {categories.length === 0 && (
        <p className="cs-hint">Nessun modello nelle cartelle di {data.backend}. Scaricane uno qui sopra.</p>
      )}

      {categories.map(([id, category]) => (
        <div key={id} className="cs-inv-category">
          <h5>
            {category.label}
            <span>{category.counts.available}/{category.counts.installed} utilizzabili</span>
          </h5>
          {category.models.map(model => {
            const state = STATE_BY_ID[model.state] || STATE_BY_ID.installed;
            return (
              <div key={model.name + model.type} className={`cs-inv-row state-${model.state}`}>
                <span className={`cs-state-dot ${model.state}`} title={state.label} />
                <div className="cs-inv-main">
                  <span className="cs-inv-name" title={model.path}>{model.name}</span>
                  <span className="cs-inv-reason">{model.state_reason}</span>
                </div>
                <div className="cs-inv-meta">
                  {model.size_gb > 0 && <em>{model.size_gb} GB</em>}
                  {model.estimated_vram_gb > 0 && <em title="VRAM stimata per tenerlo in memoria">~{model.estimated_vram_gb} GB VRAM</em>}
                </div>
                <div className="cs-inv-caps">
                  {model.capabilities.slice(0, 3).map(c => <span key={c}>{c}</span>)}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
