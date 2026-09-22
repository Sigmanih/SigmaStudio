// =============================================================================
// Hash deterministico net → colore HSL (Fase 1)
// Stessa stringa net produce sempre lo stesso colore; net diverse producono
// colori distinguibili. Nessun stato, nessuna dipendenza.
// =============================================================================

/**
 * Calcola un hash numerico di una stringa (djb2).
 */
function djb2(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    // hash = hash * 33 + charCode
    hash = ((hash << 5) + hash + str.charCodeAt(i)) >>> 0;
  }
  return hash;
}

/**
 * Mappa una stringa net a un colore HSL deterministico.
 * @param netName - Nome della net (es. "VCC", "GND", "NET_12")
 * @returns Stringa CSS `hsl(h, s%, l%)`
 */
export function netColorHash(netName: string | null | undefined): string {
  if (!netName || netName.trim() === '') {
    // Net non assegnata → grigio neutro
    return 'hsl(0, 0%, 55%)';
  }

  const hash = djb2(netName);
  // Mappa l'hash su una gamma di tonalità (0-360) evitando zone troppo simili al bg
  const hue = hash % 360;
  const saturation = 70 + (hash >> 8) % 20;   // 70-90%
  const lightness = 55 + (hash >> 16) % 15;   // 55-70%

  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}
