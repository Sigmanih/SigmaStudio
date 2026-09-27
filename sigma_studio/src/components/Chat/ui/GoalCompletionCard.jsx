// ==============================================================================
// GoalCompletionCard.jsx — Scheda di chiusura obiettivo (Chat + Developer Studio)
// Il risultato di `complete_goal` non e' un JSON da leggere in un <pre>: e' il
// riepilogo del lavoro con la prova di ogni criterio. Qui diventa una scheda
// leggibile — markdown reso, prove in evidenza, esito del cancello — con il
// JSON grezzo ancora raggiungibile ma dietro un pulsante.
// ==============================================================================
import React, { useCallback, useMemo, useState } from 'react';
import {
  Award,
  Braces,
  Check,
  Copy,
  ListChecks,
  ShieldAlert,
  ShieldCheck,
  TerminalSquare
} from 'lucide-react';
import { renderMarkdownLatex } from '../../../utils/markdownLatex';
import '../../../styles/01-primitives/goal-card.css';

/** I tool che chiudono un lavoro dichiarano un obiettivo. */
const TOOL_OBIETTIVO = ['complete_goal', 'finish_task', 'task_complete'];

export function isToolObiettivo(nome) {
  return TOOL_OBIETTIVO.includes(String(nome || '').toLowerCase());
}

/**
 * Il riepilogo puo' arrivare come `summary` del tool o come `message` di
 * cortesia: la scheda non deve mostrare il secondo quando c'e' il primo.
 */
export function estraiRiepilogo(result) {
  if (!result || typeof result !== 'object') return '';
  const candidati = [result.summary, result.riepilogo, result.report, result.message];
  for (const c of candidati) {
    if (typeof c === 'string' && c.trim()) return c.trim();
  }
  return '';
}

/**
 * I criteri arrivano in tre forme: stringhe sciolte, `{id, evidence}` come li
 * chiede la specifica del tool, oppure i `requirements` del ledger. Una sola
 * forma normalizzata per il rendering.
 */
export function normalizzaCriteri(sorgente) {
  if (!Array.isArray(sorgente)) return [];
  return sorgente
    .map((voce, indice) => {
      if (typeof voce === 'string') {
        return { chiave: `c${indice}`, id: String(indice + 1), descrizione: '', prova: voce.trim(), ok: true };
      }
      if (!voce || typeof voce !== 'object') return null;
      const prova = voce.evidence || voce.evidenza || voce.prova || voce.dettaglio || voce.detail || '';
      const descrizione =
        voce.description || voce.descrizione || voce.requirement || voce.requisito || voce.testo || voce.title || '';
      const esito = voce.met ?? voce.superata ?? voce.ok ?? voce.passed;
      return {
        chiave: `${voce.id ?? indice}-${indice}`,
        id: String(voce.id ?? indice + 1),
        descrizione: typeof descrizione === 'string' ? descrizione.trim() : '',
        prova: typeof prova === 'string' ? prova.trim() : '',
        ok: esito !== false
      };
    })
    .filter((c) => c && (c.prova || c.descrizione));
}

/** Ricompone il markdown che finisce negli appunti, cosi' resta leggibile. */
function componiTesto({ titolo, riepilogo, criteri }) {
  const righe = [`# ${titolo}`, ''];
  if (riepilogo) righe.push(riepilogo, '');
  if (criteri.length > 0) {
    righe.push('## Criteri e prove', '');
    criteri.forEach((c) => {
      righe.push(`${c.ok ? '- [x]' : '- [ ]'} ${c.descrizione || `Criterio ${c.id}`}`);
      if (c.prova) righe.push(`      prova: ${c.prova}`);
    });
  }
  return righe.join('\n').trim();
}

export default function GoalCompletionCard({
  result,
  summary,
  title,
  criteria,
  isLight = false,
  mostraRiepilogo = true,
  onOpenFile
}) {
  const [jsonAperto, setJsonAperto] = useState(false);
  const [copiato, setCopiato] = useState(false);

  const dati = useMemo(() => (result && typeof result === 'object' ? result : {}), [result]);

  const riepilogo = useMemo(() => {
    const diretto = typeof summary === 'string' ? summary.trim() : '';
    return diretto || estraiRiepilogo(dati);
  }, [summary, dati]);

  const elencoCriteri = useMemo(
    () => normalizzaCriteri(criteria ?? dati.criteria ?? dati.criteri ?? dati.requirements),
    [criteria, dati]
  );

  // `success` dice com'e' finita la chiamata, `is_completed` se il cancello ha
  // accettato la chiusura: la distinzione e' l'unica informazione utile qui.
  const stato = dati.success === false || dati.error ? 'errore' : dati.is_completed === false ? 'aperto' : 'ok';
  const completato = stato === 'ok';
  const prove = elencoCriteri.filter((c) => c.ok).length;

  const titolo = (typeof title === 'string' && title.trim())
    || (completato ? 'Obiettivo completato' : 'Obiettivo non completato');

  const handleCopy = useCallback(() => {
    const testo = componiTesto({ titolo, riepilogo, criteri: elencoCriteri });
    if (!testo) return;
    try {
      navigator.clipboard.writeText(testo);
      setCopiato(true);
      setTimeout(() => setCopiato(false), 2000);
    } catch (e) { /* copia non disponibile: nessun danno */ }
  }, [titolo, riepilogo, elencoCriteri]);

  const handleBodyClick = useCallback((e) => {
    const link = e.target.closest ? e.target.closest('.chat-file-link') : null;
    if (!link || !onOpenFile) return;
    e.preventDefault();
    const percorso = link.getAttribute('data-path') || link.dataset?.path;
    if (percorso) onOpenFile(percorso);
  }, [onOpenFile]);

  const markdown = useMemo(
    () => (mostraRiepilogo && riepilogo ? renderMarkdownLatex(riepilogo) : ''),
    [mostraRiepilogo, riepilogo]
  );

  if (!riepilogo && elencoCriteri.length === 0) return null;

  const classi = [
    'goal-card',
    stato === 'aperto' ? 'goal-card--aperto' : '',
    stato === 'errore' ? 'goal-card--errore' : '',
    isLight ? 'goal-card--light' : ''
  ].filter(Boolean).join(' ');

  return (
    <section className={classi} aria-label={titolo}>
      <header className="goal-card__head">
        <span className="goal-card__icon" aria-hidden="true">
          <Award size={17} />
        </span>

        <div className="goal-card__titles">
          <h4 className="goal-card__title">{titolo}</h4>
          <p className="goal-card__meta">
            {elencoCriteri.length > 0 ? (
              <>
                <b>{prove}</b>
                <span>di {elencoCriteri.length} criteri con prova · cancello di completamento</span>
              </>
            ) : (
              <span>{completato ? 'Lavoro verificato dal cancello di completamento' : 'Verifica non superata'}</span>
            )}
          </p>
        </div>

        <div className="goal-card__actions">
          <span className="goal-card__pill">
            {completato ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
            {completato ? 'Verificato' : stato === 'aperto' ? 'Da chiudere' : 'Non chiuso'}
          </span>
          {riepilogo && (
            <button
              type="button"
              className="goal-card__btn"
              onClick={handleCopy}
              title="Copia riepilogo e prove in markdown"
            >
              {copiato ? <Check size={12} /> : <Copy size={12} />}
              <span>{copiato ? 'Copiato' : 'Copia'}</span>
            </button>
          )}
          {result && (
            <button
              type="button"
              className={`goal-card__btn${jsonAperto ? ' goal-card__btn--on' : ''}`}
              onClick={() => setJsonAperto((v) => !v)}
              aria-expanded={jsonAperto}
              title="Mostra il risultato grezzo del tool"
            >
              <Braces size={12} />
              <span>JSON</span>
            </button>
          )}
        </div>
      </header>

      {markdown && (
        <div
          className="goal-card__body chat-md"
          onClick={handleBodyClick}
          dangerouslySetInnerHTML={{ __html: markdown }}
        />
      )}

      {elencoCriteri.length > 0 && (
        <div className="goal-card__criteria">
          <div className="goal-card__section">
            <ListChecks size={13} />
            <span>Criteri e prove ({prove}/{elencoCriteri.length})</span>
          </div>
          <ol className="goal-card__list">
            {elencoCriteri.map((c) => (
              <li key={c.chiave} className={`goal-card__item${c.ok ? ' goal-card__item--ok' : ''}`}>
                <span className="goal-card__bullet" aria-hidden="true">
                  {c.ok ? <Check size={11} /> : c.id}
                </span>
                <div className="goal-card__item-body">
                  {c.descrizione && <div className="goal-card__item-desc">{c.descrizione}</div>}
                  {c.prova && (
                    <code className="goal-card__proof">
                      <TerminalSquare size={11} aria-hidden="true" /> {c.prova}
                    </code>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {jsonAperto && result && (
        <pre className="goal-card__raw">{JSON.stringify(result, null, 2)}</pre>
      )}
    </section>
  );
}
