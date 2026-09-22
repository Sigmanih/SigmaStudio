// =============================================================================
// useFootprintRotation — test unitari.
// Verifica che rotate(deg) chiami l'endpoint MCP con la nuova rotazione
// normalizzata e richiami onBoardChanged; gestisca errori e footprint assente.
// =============================================================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFootprintRotation } from '../../hooks/useFootprintRotation';
import type { Footprint } from '../../types/pcb';

function makeFp(ref: string, rotation = 0): Footprint {
  return {
    reference: ref,
    value: 'R 10k',
    layer: 'F.Cu',
    position: { x: 5, y: 7 },
    rotation,
    pads: [],
    footprintName: `${ref.toLowerCase()}-resistor`,
  };
}

function mockFetchOk(body: Record<string, unknown> = { success: true }) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  });
}

describe('useFootprintRotation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('ruota di 90° e chiama l\'endpoint MCP con la nuova rotazione', async () => {
    const fetchMock = mockFetchOk();
    vi.stubGlobal('fetch', fetchMock);
    const onBoardChanged = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useFootprintRotation({
        projectPath: '/proj/proj.kicad_pcb',
        selectedFootprint: makeFp('R1', 0),
        onBoardChanged,
      }),
    );

    await act(async () => {
      await result.current.rotate(90);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/mcp/kicad_update_footprint_position');
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.reference).toBe('R1');
    expect(body.rotation).toBe(90);
    expect(onBoardChanged).toHaveBeenCalledTimes(1);
    expect(result.current.lastOk).toContain('R1');
    expect(result.current.error).toBeNull();
  });

  it('normalizza la rotazione oltre 360°', async () => {
    const fetchMock = mockFetchOk();
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() =>
      useFootprintRotation({
        projectPath: '/proj/proj.kicad_pcb',
        selectedFootprint: makeFp('C1', 300),
        onBoardChanged: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.rotate(90);
    });

    const body = JSON.parse(
      (fetchMock.mock.calls[0][1] as RequestInit).body as string,
    );
    expect(body.rotation).toBe(30); // (300 + 90) % 360
  });

  it('non fa nulla se non c\'è footprint selezionata', async () => {
    const fetchMock = mockFetchOk();
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() =>
      useFootprintRotation({
        projectPath: '/proj/proj.kicad_pcb',
        selectedFootprint: null,
        onBoardChanged: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.rotate(180);
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.busy).toBe(false);
  });

  it('gestisce l\'errore HTTP e lo espone in error', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ success: false, error: 'backend down' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() =>
      useFootprintRotation({
        projectPath: '/proj/proj.kicad_pcb',
        selectedFootprint: makeFp('R2'),
        onBoardChanged: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.rotate(90);
    });

    expect(result.current.error).toBe('backend down');
    expect(result.current.busy).toBe(false);
  });
});