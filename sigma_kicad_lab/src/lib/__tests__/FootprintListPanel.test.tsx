// =============================================================================
// Test unitari per FootprintListPanel (task #1)
// Verifica: lista popolata, filtro ricerca, click-to-select, evidenziazione.
// =============================================================================
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FootprintListPanel from '../../components/FootprintListPanel';
import type { Footprint } from '../../types/pcb';

const FPs: Footprint[] = [
  {
    reference: 'R1',
    value: '10k',
    footprintName: 'Resistor_SMD:R_0603_1608Metric',
    layer: 'F.Cu',
    position: { x: 10.5, y: 20.3 },
    rotation: 0,
    pads: [],
  },
  {
    reference: 'C7',
    value: '100nF',
    footprintName: 'Capacitor_SMD:C_0402_1005Metric',
    layer: 'B.Cu',
    position: { x: 3.2, y: 8.7 },
    rotation: 90,
    pads: [],
  },
  {
    reference: 'U2',
    value: 'STM32F103C8T6',
    footprintName: 'Package_QFP:LQFP-48_7x7mm_P0.5mm',
    layer: 'F.Cu',
    position: { x: 50.0, y: 50.0 },
    rotation: 180,
    pads: [],
  },
];

describe('FootprintListPanel', () => {
  it('mostra tutte le footprint con riferimento e valore', () => {
    render(
      <FootprintListPanel
        footprints={FPs}
        selectedRef={null}
        onSelect={() => {}}
        onClose={() => {}}
      />
    );
    expect(screen.getByText('R1')).toBeTruthy();
    expect(screen.getByText('C7')).toBeTruthy();
    expect(screen.getByText('U2')).toBeTruthy();
    expect(screen.getByText('10k')).toBeTruthy();
    expect(screen.getByText('100nF')).toBeTruthy();
  });

  it('mostra il layer TOP/BOT per ogni footprint', () => {
    render(
      <FootprintListPanel
        footprints={FPs}
        selectedRef={null}
        onSelect={() => {}}
        onClose={() => {}}
      />
    );
    // R1 e U2 su F.Cu → TOP; C7 su B.Cu → BOT
    expect(screen.getAllByText('TOP').length).toBe(2);
    expect(screen.getAllByText('BOT').length).toBe(1);
  });

  it('filtra la lista in base alla query di ricerca', () => {
    render(
      <FootprintListPanel
        footprints={FPs}
        selectedRef={null}
        onSelect={() => {}}
        onClose={() => {}}
      />
    );
    const input = screen.getByPlaceholderText('Cerca ref, valore…');
    fireEvent.change(input, { target: { value: 'R1' } });
    // Solo R1 resta visibile
    expect(screen.getByText('R1')).toBeTruthy();
    expect(screen.queryByText('C7')).toBeNull();
    expect(screen.queryByText('U2')).toBeNull();
  });

  it('chiama onSelect con la footprint corretta al click', () => {
    const onSelect = vi.fn();
    render(
      <FootprintListPanel
        footprints={FPs}
        selectedRef={null}
        onSelect={onSelect}
        onClose={() => {}}
      />
    );
    fireEvent.click(screen.getByText('U2'));
    expect(onSelect).toHaveBeenCalledTimes(1);
    const arg = onSelect.mock.calls[0][0] as Footprint;
    expect(arg.reference).toBe('U2');
    expect(arg.value).toBe('STM32F103C8T6');
  });

  it('evidenzia la footprint selezionata con classe fp-item--selected', () => {
    render(
      <FootprintListPanel
        footprints={FPs}
        selectedRef="C7"
        onSelect={() => {}}
        onClose={() => {}}
      />
    );
    const items = document.querySelectorAll('.fp-item');
    expect(items.length).toBe(3);
    const selected = document.querySelector('.fp-item--selected');
    expect(selected).toBeTruthy();
    expect(selected!.textContent).toContain('C7');
  });

  it('chiama onClose al click sul pulsante di chiusura', () => {
    const onClose = vi.fn();
    render(
      <FootprintListPanel
        footprints={FPs}
        selectedRef={null}
        onSelect={() => {}}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByTitle('Chiudi pannello'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('mostra il messaggio di vuoto quando nessun filtro corrisponde', () => {
    render(
      <FootprintListPanel
        footprints={FPs}
        selectedRef={null}
        onSelect={() => {}}
        onClose={() => {}}
      />
    );
    const input = screen.getByPlaceholderText('Cerca ref, valore…');
    fireEvent.change(input, { target: { value: 'ZZZ-non-esistente' } });
    expect(screen.getByText('Nessuna footprint trovata')).toBeTruthy();
  });
});
