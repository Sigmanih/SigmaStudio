// =============================================================================
// Test unitari per parseKicadBoardResponse (≥8 casi)
// =============================================================================

import { describe, it, expect } from 'vitest';
import { parseKicadBoardResponse } from '../parseKicadBoardResponse';

describe('parseKicadBoardResponse', () => {
  it('happy path: converte una risposta completa in PcbBoardModel coerente', () => {
    const raw = {
      projectName: 'TestBoard',
      filePath: '/tmp/test.kicad_pcb',
      width: 100,
      height: 80,
      footprints: [
        {
          reference: 'U1',
          value: 'STM32F4',
          footprintName: 'LQFP-48',
          position: { x: 50, y: 40 },
          rotation: 90,
          layer: 'F.Cu',
          pads: [
            { id: '1', position: { x: 45, y: 35 }, width: 1.0, height: 1.0, shape: 'rect', type: 'smd', netName: 'VCC' },
            { id: '2', position: { x: 55, y: 45 }, width: 1.0, height: 1.0, shape: 'circle', type: 'thru_hole', netName: null },
          ],
        },
      ],
      tracks: [
        { start: { x: 10, y: 10 }, end: { x: 90, y: 10 }, netName: 'VCC', width: 0.5, layer: 'F.Cu' },
      ],
      vias: [
        { position: { x: 20, y: 20 }, drillDiameter: 0.3, padDiameter: 0.8, netName: 'GND' },
      ],
      outline: {
        points: [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 80 }, { x: 0, y: 80 }],
      },
    };

    const model = parseKicadBoardResponse(raw);

    expect(model.projectName).toBe('TestBoard');
    expect(model.filePath).toBe('/tmp/test.kicad_pcb');
    expect(model.width).toBe(100);
    expect(model.height).toBe(80);
    expect(model.footprints).toHaveLength(1);
    expect(model.tracks).toHaveLength(1);
    expect(model.vias).toHaveLength(1);
    expect(model.outline).not.toBeNull();

    const fp = model.footprints[0];
    expect(fp.reference).toBe('U1');
    expect(fp.value).toBe('STM32F4');
    expect(fp.layer).toBe('F.Cu');
    expect(fp.pads).toHaveLength(2);

    const pad = fp.pads[0];
    expect(pad.id).toBe('1');
    expect(pad.shape).toBe('rect');
    expect(pad.type).toBe('smd');
    expect(pad.netName).toBe('VCC');
  });

  it('campi mancanti: usa default sensati', () => {
    const raw = {};
    const model = parseKicadBoardResponse(raw);
    expect(model.projectName).toBe('Progetto sconosciuto');
    expect(model.width).toBe(100); // default
    expect(model.height).toBe(80); // default
    expect(model.footprints).toEqual([]);
    expect(model.tracks).toEqual([]);
    expect(model.vias).toEqual([]);
    expect(model.outline).toBeNull();
  });

  it('Y-flip: le coordinate y sono invertite rispetto all altezza board', () => {
    const raw = {
      width: 100,
      height: 80,
      footprints: [
        { reference: 'U1', position: { x: 10, y: 20 }, pads: [] },
      ],
    };
    const model = parseKicadBoardResponse(raw);
    // y originale 20 → flipY(20, 80) = 60
    expect(model.footprints[0].position.y).toBe(60);
  });

  it('schema backend sigma_kicad_lab: components con x_mm/y_mm/side/width_mm/height_mm', () => {
    const raw = {
      ok: true,
      board: { width_mm: 60, height_mm: 40 },
      components: [
        { designator: 'R1', x_mm: 12.5, y_mm: 8.25, rotation: 90, side: 'F', locked: false, footprint: 'Resistor_SMD:R_0805', width_mm: 1.6, height_mm: 0.8 },
        { designator: 'C3', x_mm: 30, y_mm: 20, rotation: 0, side: 'B', locked: true, footprint: 'Capacitor_SMD:C_0402', width_mm: 1.0, height_mm: 0.5 },
      ],
      nets: [{ name: 'VCC', class: 'power', pins: 4 }],
      total_components: 2,
      total_nets: 1,
    };

    const model = parseKicadBoardResponse(raw);

    expect(model.width).toBe(60);
    expect(model.height).toBe(40);
    expect(model.footprints).toHaveLength(2);

    const r1 = model.footprints.find((f) => f.reference === 'R1');
    expect(r1).toBeDefined();
    expect(r1!.layer).toBe('F.Cu');
    expect(r1!.rotation).toBe(90);
    // y_mm 8.25 → flipY(8.25, 40) = 31.75
    expect(r1!.position.y).toBeCloseTo(31.75, 4);
    // Pad sintetizzato dalle dimensioni del corpo (width_mm/height_mm)
    expect(r1!.pads).toHaveLength(1);
    expect(r1!.pads[0].width).toBeCloseTo(1.6, 4);
    expect(r1!.pads[0].height).toBeCloseTo(0.8, 4);

    const c3 = model.footprints.find((f) => f.reference === 'C3');
    expect(c3!.layer).toBe('B.Cu');
  });

  it('track con netName null: restituisce null', () => {
    const raw = {
      tracks: [{ start: { x: 1, y: 1 }, end: { x: 2, y: 2 } }],
    };
    const model = parseKicadBoardResponse(raw);
    expect(model.tracks[0].netName).toBeNull();
  });

  it('via con campi mancanti: usa default per diametri', () => {
    const raw = { vias: [{ position: { x: 1, y: 2 } }] };
    const model = parseKicadBoardResponse(raw);
    expect(model.vias[0].drillDiameter).toBe(0.3); // default
    expect(model.vias[0].padDiameter).toBe(0.8);   // default
  });

  it('outline con meno di 2 punti: restituisce null', () => {
    const raw = { outline: { points: [{ x: 0, y: 0 }] } };
    const model = parseKicadBoardResponse(raw);
    expect(model.outline).toBeNull();
  });

  it('layer B.Cu viene normalizzato a "B.Cu"', () => {
    const raw = {
      footprints: [{ reference: 'R2', position: { x: 1, y: 1 }, layer: 'b.cu' }],
    };
    const model = parseKicadBoardResponse(raw);
    expect(model.footprints[0].layer).toBe('B.Cu');
  });
});
