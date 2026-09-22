// =============================================================================
// Costanti di tema e configurazione per PcbLab (Fase 1)
// =============================================================================

/** Palette colori per i layer SVG (usata dai componenti di rendering). */
export const PCB_COLORS = {
  bg: '#0a1628',
  surface: '#0f172a',
  accent: '#00d4ff',
  textPrimary: '#e2e8f0',
  textSecondary: '#94a3b8',
  padTop: '#00d4ff',
  padBottom: '#f59e0b',
  gridLine: 'rgba(148, 163, 184, 0.15)',
  silkscreen: '#e2e8f0',
  courtyard: 'rgba(148, 163, 184, 0.3)',
  trackRouted: '#00d4ff',
  trackUnrouted: '#ef4444',
  viaHole: '#e2e8f0',
  viaAnnular: '#00d4ff',
  viaUnrouted: '#ef4444',
} as const;

/** Token CSS del tema PCB. */
export const PCB_THEME = {
  bg: '#0a1628',
  surface: '#0f172a',
  accent: '#00d4ff',
  textPrimary: '#e2e8f0',
  textSecondary: '#94a3b8',
  padTop: '#00d4ff',
  padBottom: '#f59e0b',
  gridLine: 'rgba(148, 163, 184, 0.15)',
  silkscreen: '#e2e8f0',
  courtyard: 'rgba(148, 163, 184, 0.3)',
} as const;

/** Limiti di zoom (frazione rispetto al fit-to-board). */
export const ZOOM_LIMITS = {
  min: 0.25,
  max: 8.0,
} as const;

/** Visibilità layer di default (tutti ON tranne griglia OFF). */
export const DEFAULT_LAYER_VISIBILITY: Record<string, boolean> = {
  'Edge.Cuts': true,
  'F.Cu': true,
  'B.Cu': true,
  'F.SilkS': true,
  'B.SilkS': false,
};

/** Alias tipizzato per PcbLabTab: visibilità layer di default. */
import type { LayerKey } from '../types/pcb';
export const LAYER_DEFAULTS = DEFAULT_LAYER_VISIBILITY as Record<LayerKey, boolean>;

/** Opzioni disponibili per la dimensione griglia (mm). */
export const GRID_SIZE_OPTIONS = [0.1, 0.25, 0.5, 1.0] as const;

/** Step griglia disponibili (mm) — alias di GRID_SIZE_OPTIONS per compatibilità. */
export const GRID_STEPS: readonly number[] = [...GRID_SIZE_OPTIONS];

/** Griglia di default: OFF, step 0.5mm. */
export const DEFAULT_GRID = {
  enabled: false,
  sizeMm: 0.5,
} as const;
