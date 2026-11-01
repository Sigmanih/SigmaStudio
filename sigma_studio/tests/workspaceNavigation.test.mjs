import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveWorkspaceRequest, openAvailableWorkspace, modelHistory } from '../src/services/workspaceNavigation.js';

const catalog = [
  { id: 'dev', name: 'Developer Studio', tabType: 'developer_studio', workDomain: 'development', available: true },
  { id: 'creative', name: 'Creative Studio', tabType: 'creative_studio', workDomain: 'creative', available: true,
    workspaceTabs: [{ id: 'video_studio', name: 'Film e manga' }] },
  { id: 'assente', name: 'Assente', tabType: 'assente', workDomain: 'hardware', available: false },
];
const developer = { id: 'code_architect', path: 'roles/code_architect.md', name: 'Sviluppatore' };

test('la richiesta di un’architettura rimane in chat', () => {
  for (const text of ['Progetta un’architettura modulare', 'Come posso aprire Developer Studio?',
    'Non aprire Developer Studio', 'Apri Developer Studio e scrivi una app', 'Apri il file main.py']) {
    assert.equal(resolveWorkspaceRequest(text, developer, catalog), null, text);
  }
});

test('un comando esplicito apre lo strumento disponibile', () => {
  const result = resolveWorkspaceRequest('Puoi aprire Developer Studio?', developer, catalog);
  assert.equal(result.type, 'open');
  assert.equal(result.options[0].tabType, 'developer_studio');
  assert.equal(resolveWorkspaceRequest('Apri il tuo ambiente', developer, catalog).type, 'open');
  assert.equal(resolveWorkspaceRequest('Apri sviluppo', developer, catalog).type, 'open');
  assert.equal(resolveWorkspaceRequest('Apri la scheda Developer Studio', developer, catalog).type, 'open');
});

test('un campo con più strumenti propone una scelta', () => {
  const result = resolveWorkspaceRequest('Apri il laboratorio', { id: 'regista' }, catalog);
  assert.equal(result.type, 'choose');
  assert.deepEqual(result.options.map(entry => entry.tabType), ['creative_studio', 'video_studio']);
  assert.equal(resolveWorkspaceRequest('Apri Film e manga', developer, catalog).type, 'open');
});

test('Auto non inventa un ruolo per scegliere un laboratorio', () => {
  const result = resolveWorkspaceRequest('Apri il laboratorio', { path: 'auto' }, catalog);
  assert.equal(result.type, 'choose');
  assert.equal(result.options.length, 3);
  assert.equal(resolveWorkspaceRequest('Apri hardware', developer, catalog).type, 'unavailable');
});

test('i comandi locali non entrano nel contesto inviato al modello', () => {
  const messages = [{ role: 'user', content: 'apri sviluppo', localOnly: true },
    { role: 'assistant', content: 'Ho aperto lo studio', localOnly: true },
    { role: 'user', content: 'progetta un’architettura' }];
  assert.deepEqual(modelHistory(messages), [messages[2]]);
});

test('una scelta salvata viene rivalidata prima dell’apertura', () => {
  const target = { moduleId: 'dev', tabType: 'developer_studio', name: 'Nome precedente' };
  const calls = [];
  assert.equal(openAvailableWorkspace(target, catalog, (...args) => calls.push(args)), true);
  assert.deepEqual(calls, [[{ name: 'Developer Studio' }, 'developer_studio']]);
  assert.equal(openAvailableWorkspace(target, [], () => assert.fail()), false);
  assert.equal(openAvailableWorkspace({ moduleId: 'dev', tabType: 'non_dichiarata' }, catalog, () => assert.fail()), false);
});
