// =============================================================================
// PcbLabTab — componente root della tab PCB Lab (Fase 1, read-only)
// Assembla Toolbar, Canvas SVG, StatusBar e ErrorOverlay.
// Gestisce state globale: board, zoom, pan, layers, grid, tooltip.
// Persiste l'ultimo progetto in localStorage.
// All'avvio chiama kicad_status; al click "Apri" chiama kicad_board_read.
// =============================================================================
import { useCallback, useEffect, useState } from 'react';
import type { PcbBoardModel, LayerKey } from '../types/pcb';
import { parseKicadBoardResponse } from '../lib/parseKicadBoardResponse';
import { LAYER_DEFAULTS, GRID_STEPS } from '../lib/constants';
import { useSvgViewport } from '../hooks/useSvgViewport';
import { useMcpTool } from '../hooks/useMcpTool';
import { useTrackDrawing, type DrawMode } from '../hooks/useTrackDrawing';
import { useFootprintDrag } from '../hooks/useFootprintDrag';
import { useFootprintRotation } from '../hooks/useFootprintRotation';
import PcbToolbar from './PcbToolbar';
import PcbCanvas from './PcbCanvas';
import PcbStatusBar from './PcbStatusBar';
import ErrorOverlay from './ErrorOverlay';
import PartAddPanel from './PartAddPanel';
import FootprintListPanel from './FootprintListPanel';
import { PropertiesPanel } from './PropertiesPanel';

const LS_KEY = 'sigma_kicad_lab:last_project';
const LS_LAYERS = 'sigma_kicad_lab:layers';

function loadLastProject(): string | null {
  try {
    return window.localStorage.getItem(LS_KEY);
  } catch {
    return null;
  }
}

function saveLastProject(name: string): void {
  try {
    window.localStorage.setItem(LS_KEY, name);
  } catch {
    // localStorage non disponibile — ignora
  }
}

function loadLayers(): Record<LayerKey, boolean> {
  try {
    const raw = window.localStorage.getItem(LS_LAYERS);
    if (raw) {
      const parsed = JSON.parse(raw) as Record<string, boolean>;
      // Merge con i default per gestire layer nuovi
      return { ...LAYER_DEFAULTS, ...parsed } as Record<LayerKey, boolean>;
    }
  } catch {
    // parse error — usa default
  }
  return { ...LAYER_DEFAULTS };
}

function saveLayers(layers: Record<LayerKey, boolean>): void {
  try {
    window.localStorage.setItem(LS_LAYERS, JSON.stringify(layers));
  } catch {
    // localStorage non disponibile — ignora
  }
}

export default function PcbLabTab() {
  const [projects, setProjects] = useState<string[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(loadLastProject());
  const [board, setBoard] = useState<PcbBoardModel | null>(null);
  const [layersOn, setLayersOn] = useState<Record<LayerKey, boolean>>(loadLayers);
  const [gridOn, setGridOn] = useState(false);
  const [gridStep, setGridStep] = useState<number>(GRID_STEPS[2]); // 0.5mm default
  const [cursorMm, setCursorMm] = useState<{ x: number; y: number } | null>(null);
  const [addPartOpen, setAddPartOpen] = useState(false);

  // Selezione footprint (task #1): riferimento selezionato + pannello lista aperto.
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [fpListOpen, setFpListOpen] = useState(false);

  // Stato tracciatura tracce/vie (task #4)
  const [trackWidthMm, setTrackWidthMm] = useState(0.25);
  const [viaSizeMm, setViaSizeMm] = useState(0.8);
  const [netName, setNetName] = useState('');
  const [activeLayer, setActiveLayer] = useState<'F.Cu' | 'B.Cu'>('F.Cu');
  const [undoBusy, setUndoBusy] = useState(false);

  const viewport = useSvgViewport(board);

  // Refresh della board dopo una modifica (es. aggiunta footprint).
  const handleBoardChanged = useCallback(async () => {
    if (!selectedProject) return;
    try {
      const res = await fetch('/api/mcp/kicad_board_read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: selectedProject }),
      });
      if (!res.ok) throw new Error(`kicad_board_read HTTP ${res.status}`);
      const raw = (await res.json()) as unknown;
      const model = parseKicadBoardResponse(raw);
      setBoard(model);
    } catch {
      // errore di refresh: la board resta invariata
    }
  }, [selectedProject]);

  // Hook tracciatura tracce/vie (task #4) — dichiarato DOPO handleBoardChanged.
  const drawing = useTrackDrawing({
    projectPath: selectedProject ?? '',
    layer: activeLayer,
    netName,
    trackWidthMm,
    viaSizeMm,
    onBoardChanged: handleBoardChanged,
  });

  // Hook drag-to-move footprint (task #2) — dichiarato DOPO handleBoardChanged.
  const selectedFootprint = board?.footprints.find((fp) => fp.reference === selectedRef) ?? null;
  const dragFp = useFootprintDrag({
    projectPath: selectedProject ?? '',
    selectedFootprint,
    onBoardChanged: handleBoardChanged,
    onSelect: setSelectedRef,
  });

  // Hook rotazione footprint (task #3) — ruota la selezionata di 90° in senso orario.
  const rotateFp = useFootprintRotation({
    projectPath: selectedProject ?? '',
    selectedFootprint,
    onBoardChanged: handleBoardChanged,
  });

  // Undo dell'ultima modifica (kicad_undo) con refresh della board.
  const handleUndo = useCallback(async () => {
    if (!selectedProject || undoBusy) return;
    setUndoBusy(true);
    try {
      const res = await fetch('/api/mcp/kicad_undo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: selectedProject }),
      });
      if (!res.ok) throw new Error(`kicad_undo HTTP ${res.status}`);
      await handleBoardChanged();
    } catch {
      // errore undo: la board resta invariata
    } finally {
      setUndoBusy(false);
    }
  }, [selectedProject, undoBusy, handleBoardChanged]);

  // Carica la lista progetti all'avvio via kicad_status.
  const statusTool = useMcpTool<Record<string, unknown>>(async () => {
    const res = await fetch('/api/mcp/kicad_status');
    if (!res.ok) throw new Error(`kicad_status HTTP ${res.status}`);
    return (await res.json()) as Record<string, unknown>;
  }, { autoRun: true });

  useEffect(() => {
    const data = statusTool.data;
    if (!data) return;
    const list = Array.isArray(data.projects) ? (data.projects as string[]) : [];
    setProjects(list);
  }, [statusTool.data]);

  // Apri una board: chiama kicad_board_read e parsea la risposta.
  const openTool = useMcpTool<unknown>(async () => {
    if (!selectedProject) throw new Error('Nessun progetto selezionato');
    const res = await fetch('/api/mcp/kicad_board_read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project: selectedProject }),
    });
    if (!res.ok) throw new Error(`kicad_board_read HTTP ${res.status}`);
    return (await res.json()) as unknown;
  });

  const handleOpen = useCallback(async () => {
    try {
      const raw = await openTool.execute();
      const model = parseKicadBoardResponse(raw);
      setBoard(model);
      saveLastProject(selectedProject!);
      viewport.fitToBoard();
    } catch (err) {
      // errore già tracciato in openTool.error
    }
  }, [openTool.execute, selectedProject, viewport]);

  const toggleLayer = useCallback((key: LayerKey) => {
    setLayersOn(prev => {
      const next = { ...prev, [key]: !prev[key] };
      saveLayers(next);
      return next;
    });
  }, []);

  // Selezione footprint dalla lista (task #1): seleziona e centra la canvas.
  const handleSelectFootprint = useCallback(
    (fp: { reference: string; position: { x: number; y: number } }) => {
      setSelectedRef(fp.reference);
      viewport.centerOn(fp.position.x, fp.position.y);
    },
    [viewport]
  );

  // Salva riferimento e valore della footprint selezionata via MCP, poi ricarica la board.
  const handleSaveProps = useCallback(
    async (ref: string, value: string) => {
      setBusy(true);
      setError(null);
      try {
        await postMcp('kicad_update_footprint', { reference: ref, value });
        await loadBoard();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Errore nel salvataggio proprietà');
      } finally {
        setBusy(false);
      }
    },
    [loadBoard, postMcp]
  );

  // Stato di errore da mostrare nell'overlay.
  const error = openTool.error ?? statusTool.error;
  const loading = openTool.status === 'loading';

  return (
    <div className="pcb-lab">
      <PcbToolbar
        projects={projects}
        selectedProject={selectedProject ?? ''}
        onOpenProject={(name: string) => setSelectedProject(name)}
        zoomPercent={Math.round(viewport.zoom * 100)}
        onZoomIn={() => viewport.zoomIn()}
        onZoomOut={() => viewport.zoomOut()}
        onFitToBoard={() => viewport.fitToBoard()}
        layerVisibility={layersOn as Record<string, boolean>}
        onToggleLayer={(key: LayerKey) => toggleLayer(key)}
        gridEnabled={gridOn}
        gridSizeMm={gridStep}
        onToggleGrid={() => setGridOn(prev => !prev)}
        onChangeGridSize={(mm: number) => setGridStep(mm)}
        onOpenAddPart={() => setAddPartOpen(true)}
        onToggleFpList={() => setFpListOpen(prev => !prev)}
        fpListOpen={fpListOpen}
        selectedReference={selectedRef}
        onRotateSelected={(deg) => void rotateFp.rotate(deg)}
        rotateBusy={rotateFp.busy}

        // Tracciatura tracce e vie (task #4/#5)
        drawMode={drawing.mode}
        onSetDrawMode={(m) => drawing.setMode(m as DrawMode)}
        trackWidthMm={trackWidthMm}
        onChangeTrackWidth={(mm: number) => setTrackWidthMm(mm)}
        viaSizeMm={viaSizeMm}
        onChangeViaSize={(mm: number) => setViaSizeMm(mm)}
        netName={netName}
        onChangeNet={(name: string) => setNetName(name)}
        onUndo={() => void handleUndo()}
        undoBusy={undoBusy}
      />

      <div className="pcb-lab__canvas-wrap">
        {board ? (
          <PcbCanvas
            board={board}
            viewBox={{ x: viewport.viewBox.x, y: viewport.viewBox.y, w: viewport.viewBox.width, h: viewport.viewBox.height }}
            layerVisibility={layersOn as Record<string, boolean>}
            gridVisible={gridOn}
            gridStep={gridStep}
            tooltipData={null}
            mouseX={0}
            mouseY={0}
            drawMode={drawing.mode}
            draftSegment={drawing.draft}
            draftWidthMm={trackWidthMm}
            onDrawStart={(p) => drawing.startDrag(p)}
            onDrawMove={(p) => drawing.moveDrag(p)}
            onDrawEnd={() => void drawing.endDrag()}
            onViaPlace={(p) => void drawing.placeVia(p)}
            draggingRef={dragFp.dragging ? selectedRef : null}
            dragPreviewPosition={dragFp.previewPosition}
            onFootprintDragStart={(fp, p) => dragFp.startDrag(fp, p)}
            onFootprintDragMove={(p) => dragFp.moveDrag(p)}
            onFootprintDragEnd={() => void dragFp.endDrag()}
          />
        ) : error ? (
          <ErrorOverlay
            variant="error"
            title="Errore di caricamento"
            description={error}
            onAction={() => void handleOpen()}
            actionLabel="Riprova"
          />
        ) : loading ? (
          <div className="pcb-lab__loading">Caricamento board…</div>
        ) : (
          <ErrorOverlay
            variant="empty"
            title="Nessuna board caricata"
            description="Seleziona un progetto per iniziare"
          />
        )}
      </div>

      <PcbStatusBar
        project={selectedProject ?? '—'}
        file={board?.filePath ?? '—'}
        statusText={loading ? 'Caricamento…' : error ? 'Errore' : board ? 'Pronto' : 'In attesa'}
        zoomPercent={Math.round(viewport.zoom * 100)}
        cursorMm={cursorMm}
      />

      {addPartOpen && (
        <PartAddPanel
          projectPath={selectedProject ?? ''}
          onAdded={() => void handleBoardChanged()}
          onClose={() => setAddPartOpen(false)}
        />
      )}

      {/* Pannello lista footprint con ricerca e click-to-select (task #1) */}
      {fpListOpen && board && (
        <FootprintListPanel
          footprints={board.footprints}
          selectedRef={selectedRef}
          onSelect={(fp) => handleSelectFootprint(fp)}
          onClose={() => setFpListOpen(false)}
        />
      )}

      {/* Pannello proprietà: modifica riferimento e valore della footprint selezionata (task #4) */}
      {board && selectedRef && (
        <PropertiesPanel
          footprint={board.footprints.find((f) => f.reference === selectedRef) ?? null}
          onSave={handleSaveProps}
          onClose={() => setSelectedRef(null)}
        />
      )}
    </div>
  );
}