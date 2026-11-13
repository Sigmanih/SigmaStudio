import { useState, useEffect } from 'react';
import { Cpu, Gauge, Brain } from 'lucide-react';
import { getLazyModule } from '../../modules/registry';
import ModuleNotInstalled from '../../modules/ModuleNotInstalled';
import { useApp } from '../../contexts/AppContext';
import { useModuleState } from '../../hooks/useModuleState';
import { useCapabilities } from '../../hooks/useCapabilities';
import { selectModelSection } from '../../services/studioNavigation';
import '../../styles/03-modules/studio-areas.css';

const sections = [
  { id: 'models', name: 'Modelli', type: 'model_hub', module: 'sigma_model_hub', icon: Cpu },
  { id: 'benchmark', name: 'Benchmark', type: 'benchmark_lab', module: 'sigma_benchmark_lab', icon: Gauge },
  { id: 'training', name: 'Training', type: 'training_lab', module: 'sigma_training_lab', icon: Brain },
];
function initialSection() {
  try { return sessionStorage.getItem('sigma_model_workspace_section') || 'models'; } catch { return 'models'; }
}

export default function ModelsWorkspace({ openTab, activeTabId }) {
  const { addToast, fetchTasks } = useApp();
  const { modulesState, isLoaded } = useModuleState();
  const { skills } = useCapabilities();
  const [selected, setSelected] = useState(initialSection);
  const [visited, setVisited] = useState(() => [initialSection()]);
  useEffect(() => {
    const select = event => {
      const id = sections.some(s => s.id === event.detail) ? event.detail : 'models';
      setSelected(id);
      setVisited(previous => previous.includes(id) ? previous : [...previous, id]);
    };
    const selectModels = () => select({ detail: 'models' });
    window.addEventListener('sigma-model-workspace-section', select);
    window.addEventListener('sigma-model-hub-set-tab', selectModels);
    return () => {
      window.removeEventListener('sigma-model-workspace-section', select);
      window.removeEventListener('sigma-model-hub-set-tab', selectModels);
    };
  }, []);
  const available = sections.filter(s => modulesState[s.module] === true
    && !skills.some(skill => skill.tab_type === s.type && skill.enabled === false) && getLazyModule(s.type));
  const active = available.some(s => s.id === selected) ? selected : available[0]?.id;
  return <section className="studio-area" data-agent-component="ModelsWorkspace">
    <nav className="studio-area-tabs" role="tablist" aria-label="Sezioni Modelli">
      {available.map((section, index) => <button type="button" role="tab" key={section.id}
        id={`models-tab-${section.id}`} aria-controls={`models-panel-${section.id}`} aria-selected={active === section.id}
        tabIndex={active === section.id ? 0 : -1} onClick={() => selectModelSection(section.id)}
        onKeyDown={event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? available.length - 1
            : (index + (event.key === 'ArrowRight' ? 1 : -1) + available.length) % available.length;
          selectModelSection(available[next].id);
          event.currentTarget.parentElement.children[next].focus();
        }}><section.icon size={17} />{section.name}</button>)}
    </nav>
    {!isLoaded && <p role="status">Caricamento delle sezioni Modelli…</p>}
    {isLoaded && !available.length && <ModuleNotInstalled tabType="model_hub" openTab={openTab} />}
    {available.filter(s => visited.includes(s.id) || s.id === active).map(section => {
      const Component = getLazyModule(section.type);
      return <div key={section.id} className="studio-area-panel" role="tabpanel" id={`models-panel-${section.id}`}
        aria-labelledby={`models-tab-${section.id}`} hidden={active !== section.id}>
        <Component openTab={openTab} addToast={addToast} activeTabId={activeTabId} onTasksUpdated={fetchTasks} />
      </div>;
    })}
  </section>;
}
