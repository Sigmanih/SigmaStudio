// =============================================================================
// Test unitari per netColorHash (≥4 casi)
// =============================================================================

import { describe, it, expect } from 'vitest';
import { netColorHash } from '../netColorHash';

describe('netColorHash', () => {
  it('ritorna un colore HSL valido per una net assegnata', () => {
    const color = netColorHash('VCC');
    expect(color).toMatch(/^hsl\(\d{1,3}, \d{1,3}%, \d{1,3}%\)$/);
  });

  it('è deterministico: stessa net → stesso colore', () => {
    const a = netColorHash('GND');
    const b = netColorHash('GND');
    expect(a).toBe(b);
  });

  it('net diverse producono colori diversi (con alta probabilità)', () => {
    // Con hash djb2 su stringhe distinte, i colori differiscono quasi sempre.
    const colors = new Set(
      ['NET_1', 'NET_2', 'VCC', 'GND', 'SCL', 'SDA'].map((n) => netColorHash(n))
    );
    expect(colors.size).toBeGreaterThanOrEqual(4);
  });

  it('ritorna grigio neutro per net null/undefined/vuota', () => {
    expect(netColorHash(null)).toBe('hsl(0, 0%, 55%)');
    expect(netColorHash(undefined)).toBe('hsl(0, 0%, 55%)');
    expect(netColorHash('')).toBe('hsl(0, 0%, 55%)');
    expect(netColorHash('   ')).toBe('hsl(0, 0%, 55%)');
  });
});
