// =============================================================================
// PcbToolbar — barra superiore della tab PCB Lab (Fase 1)
// Assembla: ProjectSelector, ZoomControls, LayerToggles, GridControl
// =============================================================================
import { useState } from 'react';
import {
  FolderOpen,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Layers,
  Grid3x3,
  PackagePlus,
  List,
  Trash2,
  RotateCw,
  Spline,
  CircleDot,
  Undo2,
} from 'lucide-react';
import type { LayerKey } from '../types/pcb';
import { GRID_SIZE_OPTIONS } from '../lib/constants';

// ---------------------------------------------------------------------------
// Props della toolbar
// ---------------------------------------------------------------------------
export interface PcbToolbarProps {
  /** Elenco progetti disponibili (nomi). */
  projects: string[];
  /** Progetto attualmente selezionato, o null. */
  selectedProject: string | null;
  /** Callback quando l'utente apre un progetto. */
  onOpenProject: (name: string) => void;

  // Zoom
  zoomPercent: number; // es. 100 = fit-to-board
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitToBoard: () => void;

  // Layer toggles
  layerVisibility: Record<string, boolean>;
  onToggleLayer: (key: LayerKey) => void;

  // Griglia
  gridEnabled: boolean;
  gridSizeMm: number;
  onToggleGrid: () => void;
  onChangeGridSize: (mm: number) => void;

  // Editing: apertura pannello aggiunta footprint + rimozione selezione
  onOpenAddPart?: () => void;
  /** Apre/chiude il pannello lista footprint. */
  onToggleFpList?: () => void;
  /** true se il pannello lista footprint è aperto. */
  fpListOpen?: boolean;
  /** Rimuove la footprint selezionata (kicad_remove_footprint). */
  onRemoveSelected?: () => void;
  /** true se c'è una selezione attiva da rimuovere. */
  hasSelection?: boolean;
  /** Riferimento della footprint selezionata (es. "R1"), o null. */
  selectedReference?: string | null;
  /** Ruota la footprint selezionata di `degrees` (90/180/270) in senso orario. */
  onRotateSelected?: (degrees: 90 | 180 | 270) => void;
  /** true mentre la rotazione è in corso. */
  rotateBusy?: boolean;

  // Tracciatura tracce e vie
  drawMode?: 'none' | 'track' | 'via';
  onSetDrawMode?: (m: 'none' | 'track' | 'via') => void;
  trackWidthMm?: number;
  onChangeTrackWidth?: (mm: number) => void;
  viaSizeMm?: number;
  onChangeViaSize?: (mm: number) => void;
  netName?: string;
  onChangeNet?: (name: string) => void;
  onUndo?: () => void;
  undoBusy?: boolean;
}

// ---------------------------------------------------------------------------
// Mappa layer → etichetta visibile
// ---------------------------------------------------------------------------
const LAYER_LABELS: Record<LayerKey, string> = {
  'F.Cu': 'Top Cu',
  'B.Cu': 'Bot Cu',
  'F.SilkS': 'Silkscreen',
  'B.SilkS': 'Bot Silk',
  'Edge.Cuts': 'Courtyard',
};

const LAYER_ORDER: LayerKey[] = ['F.Cu', 'B.Cu', 'F.SilkS', 'Edge.Cuts'];

// ---------------------------------------------------------------------------
// Componente principale
// ---------------------------------------------------------------------------
export default function PcbToolbar(props: PcbToolbarProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <div className="pcb-toolbar">
      {/* ── ProjectSelector ─────────────────────────────────────────────── */}
      <div className="pcb-toolbar__group pcb-toolbar__project">
        <div className="pcb-dropdown" onClick={() => setDropdownOpen(!dropdownOpen)}>
          <span className="pcb-dropdown__label">
            {props.selectedProject ?? 'Nessun progetto'}
          </span>
          {dropdownOpen && (
            <ul className="pcb-dropdown__list">
              {props.projects.map((p) => (
                <li
                  key={p}
                  onClick={() => {
                    props.onOpenProject(p);
                    setDropdownOpen(false);
                  }}
                >
                  {p}
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          className="pcb-btn pcb-btn--primary"
          onClick={() => props.selectedProject && props.onOpenProject(props.selectedProject)}
          disabled={!props.selectedProject}
        >
          <FolderOpen size={14} />
          Apri
        </button>
      </div>

      {/* ── ZoomControls ────────────────────────────────────────────────── */}
      <div className="pcb-toolbar__group">
        <button className="pcb-btn" onClick={props.onZoomOut} title="Zoom out">
          <ZoomOut size={16} />
        </button>
        <span className="pcb-toolbar__zoom-label">{Math.round(props.zoomPercent)}%</span>
        <button className="pcb-btn" onClick={props.onZoomIn} title="Zoom in">
          <ZoomIn size={16} />
        </button>
        <button className="pcb-btn" onClick={props.onFitToBoard} title="Fit to board">
          <Maximize2 size={16} />
        </button>
      </div>

      {/* ── LayerToggles ────────────────────────────────────────────────── */}
      <div className="pcb-toolbar__group">
        <Layers size={14} className="pcb-toolbar__icon" />
        {LAYER_ORDER.map((key) => (
          <label key={key} className="pcb-layer-toggle">
            <input
              type="checkbox"
              checked={props.layerVisibility[key] ?? false}
              onChange={() => props.onToggleLayer(key)}
            />
            <span>{LAYER_LABELS[key]}</span>
          </label>
        ))}
      </div>

      {/* ── GridControl ─────────────────────────────────────────────────── */}
      <div className="pcb-toolbar__group">
        <Grid3x3 size={14} className="pcb-toolbar__icon" />
        <label className="pcb-grid-toggle">
          <input type="checkbox" checked={props.gridEnabled} onChange={props.onToggleGrid} />
          <span>Griglia</span>
        </label>
        {props.gridEnabled && (
          <select
            value={props.gridSizeMm}
            onChange={(e) => props.onChangeGridSize(Number(e.target.value))}
            className="pcb-select"
          >
            {GRID_SIZE_OPTIONS.map((mm) => (
              <option key={mm} value={mm}>{mm} mm</option>
            ))}
          </select>
        )}
      </div>

      {/* ── Editing: aggiunta / rimozione footprint ─────────────────────── */}
      {(props.onOpenAddPart || props.onRemoveSelected) && (
        <div className="pcb-toolbar__group pcb-toolbar__edit">
          {props.onOpenAddPart && (
            <button
              type="button"
              className="pcb-btn pcb-btn--accent"
              onClick={props.onOpenAddPart}
              title="Aggiungi una footprint alla board"
            >
              <PackagePlus size={14} />
              Aggiungi footprint
            </button>
          )}
          {props.onRemoveSelected && (
            <button
              type="button"
              className={`pcb-btn ${props.selectedReference ? 'pcb-btn--danger' : ''}`}
              onClick={props.onRemoveSelected}
              disabled={!props.selectedReference}
              title={
                props.selectedReference
                  ? `Rimuovi la footprint ${props.selectedReference} dalla board`
                  : "Seleziona una footprint sulla canvas per rimuoverla"
              }
            >
              <Trash2 size={14} />
              Rimuovi
            </button>
          )}
          {props.onRotateSelected && (
            <>
              <button
                type="button"
                className={`pcb-btn ${props.selectedReference ? 'pcb-btn--accent' : ''}`}
                onClick={() => props.onRotateSelected?.(90)}
                disabled={!props.selectedReference || props.rotateBusy}
                title={
                  props.selectedReference
                    ? `Ruota la footprint ${props.selectedReference} di 90° in senso orario (tasto R)`
                    : "Seleziona una footprint sulla canvas per ruotarla"
                }
              >
                <RotateCw size={14} />
                {props.rotateBusy ? '…' : '90°'}
              </button>
              <button
                type="button"
                className={`pcb-btn ${props.selectedReference ? 'pcb-btn--accent' : ''}`}
                onClick={() => props.onRotateSelected?.(180)}
                disabled={!props.selectedReference || props.rotateBusy}
                title={
                  props.selectedReference
                    ? `Ruota la footprint ${props.selectedReference} di 180° in senso orario`
                    : "Seleziona una footprint sulla canvas per ruotarla"
                }
              >
                <RotateCw size={14} />
                {props.rotateBusy ? '…' : '180°'}
              </button>
              <button
                type="button"
                className={`pcb-btn ${props.selectedReference ? 'pcb-btn--accent' : ''}`}
                onClick={() => props.onRotateSelected?.(270)}
                disabled={!props.selectedReference || props.rotateBusy}
                title={
                  props.selectedReference
                    ? `Ruota la footprint ${props.selectedReference} di 270° in senso orario`
                    : "Seleziona una footprint sulla canvas per ruotarla"
                }
              >
                <RotateCw size={14} />
                {props.rotateBusy ? '…' : '270°'}
              </button>
            </>
          )}
        </div>
      )}

      {/* ── Tracciatura tracce e vie ────────────────────────────────────── */}
      {props.onSetDrawMode && (
        <div className="pcb-toolbar__group pcb-toolbar__draw">
          <Spline size={14} className="pcb-toolbar__icon" />
          <button
            type="button"
            className={`pcb-btn ${props.drawMode === 'track' ? 'pcb-btn--active' : ''}`}
            onClick={() => props.onSetDrawMode?.(props.drawMode === 'track' ? 'none' : 'track')}
            title="Traccia un segmento (click-drag sulla canvas)"
          >
            Traccia
          </button>
          <input
            type="number"
            min={0.1}
            max={5}
            step={0.1}
            value={props.trackWidthMm ?? 0.25}
            onChange={(e) => props.onChangeTrackWidth?.(Number(e.target.value))}
            className="pcb-input pcb-input--num"
            title="Larghezza traccia (mm)"
          />

          <CircleDot size={14} className="pcb-toolbar__icon" />
          <button
            type="button"
            className={`pcb-btn ${props.drawMode === 'via' ? 'pcb-btn--active' : ''}`}
            onClick={() => props.onSetDrawMode?.(props.drawMode === 'via' ? 'none' : 'via')}
            title="Piazza una via (click sulla canvas)"
          >
            Via
          </button>
          <input
            type="number"
            min={0.4}
            max={3}
            step={0.1}
            value={props.viaSizeMm ?? 0.8}
            onChange={(e) => props.onChangeViaSize?.(Number(e.target.value))}
            className="pcb-input pcb-input--num"
            title="Diametro pad via (mm)"
          />

          <input
            type="text"
            value={props.netName ?? ''}
            onChange={(e) => props.onChangeNet?.(e.target.value)}
            placeholder="net (es. GND, VCC)"
            className="pcb-input pcb-input--net"
            title="Net da assegnare a tracce e vie"
          />

          {props.onUndo && (
            <button
              type="button"
              className="pcb-btn"
              onClick={props.onUndo}
              disabled={props.undoBusy}
              title="Annulla l'ultima modifica (kicad_undo)"
            >
              <Undo2 size={14} />
              {props.undoBusy ? '…' : 'Undo'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}