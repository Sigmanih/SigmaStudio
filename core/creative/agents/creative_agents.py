import json
from pathlib import Path
from core.logger import get_logger

log = get_logger("creative_agents")

# Register creative agent definitions for agents_meta.json
CREATIVE_AGENTS = {
    'creative_planner': {
        'name': 'Creative Planner',
        'role': 'Decompone richieste creative in sub-task pipeline',
        'model': 'auto',
        'temperature': 0.3,
        'capabilities': ['planning', 'decomposition', 'pipeline_design'],
        'system_prompt': '''Sei il Creative Planner di Sigma Studio. 
Il tuo ruolo è analizzare richieste creative dell'utente e decomporle in una pipeline 
di operazioni (generazione, editing, 3D, mesh, texture, render) che gli agenti 
specializzati eseguiranno in sequenza.'''
    },
    'image_analyst': {
        'name': 'Image Analyst',
        'role': 'Analizza immagini per qualità, contenuto, stile',
        'model': 'auto',
        'temperature': 0.1,
        'capabilities': ['image_analysis', 'quality_assessment'],
        'system_prompt': '''Sei l'Image Analyst di Sigma Studio.
Analizzi immagini per determinare qualità, contenuto, stile, 
e suggerisci miglioramenti.'''
    },
    'mesh_specialist': {
        'name': 'Mesh Specialist',
        'role': 'Decide operazioni mesh ottimali',
        'model': 'auto',
        'temperature': 0.2,
        'capabilities': ['mesh_analysis', 'topology_optimization'],
        'system_prompt': '''Sei il Mesh Specialist di Sigma Studio.
Analizzi mesh 3D e decidi le operazioni ottimali: cleanup, remesh, 
decimazione, UV unwrap.'''
    },
    'texture_artist': {
        'name': 'Texture Artist',
        'role': 'Genera e valida texture PBR',
        'model': 'auto',
        'temperature': 0.5,
        'capabilities': ['texture_generation', 'pbr_validation'],
        'system_prompt': '''Sei il Texture Artist di Sigma Studio.
Generi texture PBR professionali e validi la qualità dei materiali.'''
    },
    'quality_inspector': {
        'name': 'Quality Inspector',
        'role': 'Valuta output e decide se serve ri-generazione',
        'model': 'auto',
        'temperature': 0.1,
        'capabilities': ['quality_control', 'feedback_loop'],
        'system_prompt': '''Sei il Quality Inspector di Sigma Studio.
Valuti la qualità degli output (immagini, mesh, texture, render) 
e decidi se il risultato è accettabile o serve una ri-generazione.'''
    },
    'render_director': {
        'name': 'Render Director',
        'role': 'Configura lighting, camera, render settings',
        'model': 'auto',
        'temperature': 0.3,
        'capabilities': ['lighting_setup', 'camera_placement', 'render_optimization'],
        'system_prompt': '''Sei il Render Director di Sigma Studio.
Configuri illuminazione, posizionamento camera, e impostazioni di rendering 
per ottenere risultati professionali.'''
    },
}

def register_creative_agents(agents_meta_path: str = 'agents_meta.json'):
    """Registra gli agenti creativi nel file agents_meta.json se non già presenti."""
    meta_path = Path(agents_meta_path)
    if not meta_path.exists():
        log.warning(f"{agents_meta_path} non trovato. Impossibile registrare agenti creativi.")
        return
        
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
            
        changed = False
        for agent_id, agent_def in CREATIVE_AGENTS.items():
            if agent_id not in meta:
                meta[agent_id] = agent_def
                changed = True
                log.info(f"Registrato agente creativo: {agent_id}")
                
        if changed:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2)
            log.info("agents_meta.json aggiornato con agenti creativi.")
    except Exception as e:
        log.error(f"Errore registrazione agenti creativi: {e}")
