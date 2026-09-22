// =============================================================================
// useFootprintDrag — test unitari
// Verifica: start/move/end drag, invio MCP, refresh board, cancel, no-op.
// =============================================================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFootprintDrag } from '../../hooks/useFootprintDrag';
import type { Footprint } from '../../types/pcb';

function makeFp(ref: string, x = 10, y = 20): Footprint {
  return {
    reference: ref,
    value: 'R 10k',
    layer: 'F.Cu',
    position: { x, y },
    rotation: 0,
    pads: [],
    footprintName: `${ref.toLowerCase()}-resistor`,
  };
}

function mockFetch(ok = true) {
  const fn = vi.fn().mockImplementation(async () => ({
    ok,
    status: ok ? 200 : 500,
    json: async () => (ok ? { success: true } : { success: false, error: 'boom' }),
  }));
  vi.stubGlobal('fetch', fn);
  return fn;
}

describe('useFootprintDrag', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('non avvia il drag se la footprint non è selezionata', () => {
    const fp = makeFp('R1');
    const { result } = renderHook(() =>
      useFootprintDrag({
        projectPath: 'proj',
        selectedFootprint: null,
        onBoardChanged: vi.fn(),
      })
    );
    act(() => {
      result.current.startDrag(fp, { x: 11, y: 21 });
    });
    expect(result.current.dragging).toBe(false);
    expect(result.current.previewPosition).toBeNull();
  });

  it('avvia il drag se la footprint è selezionata e calcola grabOffset', () => {
    const fp = makeFp('R1', 10, 20);
    const { result } = renderHook(() =>
      useFootprintDrag({
        projectPath: 'proj',
        selectedFootprint: fp,
        onBoardChanged: vi.fn(),
      })
    );
    act(() => {
      result.current.startDrag(fp, { x: 12.5, y: 23 });
    });
    expect(result.current.dragging).toBe(true);
    expect(result.current.grabOffset).toEqual({ x: 2.5, y: 3 });
    expect(result.current.previewPosition).toEqual({ x: 10, y: 20 });
  });

  it('moveDrag aggiorna previewPosition tenendo fisso l\'offset di presa', () => {
    const fp = makeFp('R1', 10, 20);
    const { result } = renderHook(() =>
      useFootprintDrag({
        projectPath: 'proj',
        selectedFootprint: fp,
        onBoardChanged: vi.fn(),
      })
    );
    act(() => {
      result.current.startDrag(fp, { x: 12.5, y: 23 });
    });
    act(() => {
      result.current.moveDrag({ x: 30, y: 40 });
    });
    // offset (2.5, 3) → posizione = (30-2.5, 40-3)
    expect(result.current.previewPosition).toEqual({ x: 27.5, y: 37 });
  });

  it('endDrag invia kicad_update_footprint_position e richiama onBoardChanged', async () => {
    const fp = makeFp('R1', 10, 20);
    const fetchMock = mockFetch(true);
    const onBoardChanged = vi.fn();
    const { result } = renderHook(() =>
      useFootprintDrag({
        projectPath: 'proj',
        selectedFootprint: fp,
        onBoardChanged,
      })
    );
    act(() => {
      result.current.startDrag(fp, { x: 12.5, y: 23 });
    });
    act(() => {
      result.current.moveDrag({ x: 30, y: 40 });
    });
    await act(async () => {
      await result.current.endDrag();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/mcp/kicad_update_footprint_position');
    const body = JSON.parse((init as { body: string }).body);
    expect(body.reference).toBe('R1');
    expect(body.x_mm).toBeCloseTo(27.5);
    expect(body.y_mm).toBeCloseTo(37);
    expect(onBoardChanged).toHaveBeenCalledTimes(1);
    expect(result.current.dragging).toBe(false);
    expect(result.current.lastOk).toContain('R1');
  });

  it('endDrag non invia nulla se la posizione non cambia (delta < 0.01mm)', async () => {
    const fp = makeFp('R1', 10, 20);
    const fetchMock = mockFetch(true);
    const { result } = renderHook(() =>
      useFootprintDrag({
        projectPath: 'proj',
        selectedFootprint: fp,
        onBoardChanged: vi.fn(),
      })
    );
    act(() => {
      result.current.startDrag(fp, { x: 10.005, y: 20.005 });
    });
    await act(async () => {
      await result.current.endDrag();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('endDrag cattura l\'errore MCP in state.error', async () => {
    const fp = makeFp('R1', 10, 20);
    mockFetch(false);
    const { result } = renderHook(() =>
      useFootprintDrag({
        projectPath: 'proj',
        selectedFootprint: fp,
        onBoardChanged: vi.fn(),
      })
    );
    act(() => {
      result.current.startDrag(fp, { x: 12.5, y: 23 });
    });
    act(() => {
      result.current.moveDrag({ x: 30, y: 40 });
    });
    await act(async () => {
      await result.current.endDrag();
    });
    expect(result.current.error).toBe('boom');
    expect(result.current.lastOk).toBeNull();
  });

  it('cancel annulla il drag senza inviare modifiche', async () => {
    const fp = makeFp('R1', 10, 20);
    const fetchMock = mockFetch(true);
    const { result } = renderHook(() =>
      useFootprintDrag({
        projectPath: 'proj',
        selectedFootprint: fp,
        onBoardChanged: vi.fn(),
      })
    );
    act(() => {
      result.current.startDrag(fp, { x: 12.5, y: 23 });
    });
    act(() => {
      result.current.moveDrag({ x: 30, y: 40 });
    });
    act(() => {
      result.current.cancel();
    });
    expect(result.current.dragging).toBe(false);
    expect(result.current.previewPosition).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
