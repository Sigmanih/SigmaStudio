import { Clapperboard } from 'lucide-react';
import TabHeader from './common/TabHeader';
import CapabilityCard from './common/CapabilityCard';
import { useModuleState } from '../hooks/useModuleState';
import { useCapabilities } from '../hooks/useCapabilities';
import { multimediaEntries } from '../services/studioNavigation';
import '../styles/03-modules/skills-workspace.css';

export default function MultimediaWorkspace({ openTab }) {
  const { moduleCatalog, isLoaded, error } = useModuleState();
  const { skills } = useCapabilities();
  const entries = multimediaEntries(moduleCatalog, skills);
  return <section className="capabilities-hub multimedia-workspace" data-agent-component="MultimediaWorkspace">
    <TabHeader icon={Clapperboard} title="Multimedia" description="Tutti gli strumenti per immagini, video e audio." />
    <div className="capabilities-body">
      <header className="capabilities-intro"><div><span className="studio-eyebrow">IL TUO SPAZIO MULTIMEDIALE</span>
        <h2>Dai forma alle tue idee</h2><p>Scegli cosa creare. Ritrovi qui gli stessi strumenti disponibili nella Home e nella sidebar.</p></div></header>
      {error && <p role="alert">{error}</p>}
      {!isLoaded && <p role="status">Caricamento degli strumenti multimediali…</p>}
      <div className="capabilities-grid">{entries.map(entry => <CapabilityCard key={entry.id} entry={entry} openTab={openTab} compact />)}</div>
      {isLoaded && !entries.length && <p>Nessuno strumento multimediale attivo. Puoi gestire i moduli dalla tab Skills.</p>}
    </div>
  </section>;
}
