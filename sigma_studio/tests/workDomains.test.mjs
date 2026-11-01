import test from 'node:test';
import assert from 'node:assert/strict';
import { groupWorkDomains, modulesForDomain, workDomainFor } from '../src/utils/workDomains.js';
import { prepareRoleChat, findRoleManifesto } from '../src/services/chatNavigation.js';

test('lo sviluppo rappresenta anche i test senza perdere gli specialisti', () => {
  const roles = [{ id: 'test_engineer', name: 'Test Engineer', category: 'Sviluppo' },
    { id: 'code_architect', name: 'Sviluppatore', category: 'Sviluppo' },
    { id: 'regista', name: 'Regista', category: 'Creatività' }];
  const groups = groupWorkDomains(roles);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].id, 'code_architect');
  assert.equal(groups[0].name, 'Sviluppo');
  assert.equal(groups[0].members.length, 2);
  assert.equal(roles[0].name, 'Test Engineer');
});

test('un ruolo sospeso non diventa rappresentante della Home', () => {
  assert.deepEqual(groupWorkDomains([{ id: 'coder', active: false }]), []);
});

test('i domini dichiarati prevalgono sulla classificazione di compatibilità', () => {
  assert.equal(workDomainFor({ name: 'Test', workDomain: 'research' }).id, 'research');
});

test('si aprono solo strumenti caricati e associati al campo di lavoro', () => {
  const catalog = [{ id: 'dev', category: 'Sviluppo', tabType: 'developer', available: true },
    { id: 'video', category: 'Video', tabType: 'video', available: true },
    { id: 'assente', category: 'Sviluppo', tabType: 'dev', available: false }];
  assert.deepEqual(modulesForDomain('development', catalog).map(entry => entry.id), ['dev']);
});

test('aprire una chat non invia una richiesta precedente', () => {
  const values = new Map([['sigma_pending_chat_send', '1'], ['sigma_pending_chat_prompt', 'vecchio'],
    ['sigma_pending_chat_files', '["vecchio"]']]);
  const storage = { setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  prepareRoleChat(storage, { roleId: 'code_architect' });
  assert.equal(values.get('sigma_active_role'), 'code_architect');
  assert.equal(values.has('sigma_pending_chat_send'), false);
  assert.equal(values.has('sigma_pending_chat_prompt'), false);
  assert.equal(values.has('sigma_pending_chat_files'), false);
  prepareRoleChat(storage, { roleId: 'test_engineer', text: ' verifica ', send: true });
  assert.equal(values.get('sigma_pending_chat_prompt'), 'verifica');
  assert.equal(values.get('sigma_pending_chat_send'), '1');
});

test('un laboratorio espone schede aggiuntive senza duplicarle', () => {
  const tools = modulesForDomain('creative', [{ id: 'creative', workDomain: 'creative', available: true,
    name: 'Creative Studio', tabType: 'creative_studio', workspaceTabs: [
      { id: 'creative_studio', name: 'Duplicata' }, { id: 'video_studio', name: 'Film e manga' }, null,
    ] }]);
  assert.deepEqual(tools.map(tool => tool.tabType), ['creative_studio', 'video_studio']);
  assert.equal(tools[1].name, 'Film e manga');
});

test('il ruolo scelto risolve identificativi e percorsi senza ripiegare su auto', () => {
  const roles = [{ id: 'auto', path: 'auto' }, { filename: 'Coder.md', path: 'roles/Coder.md' }];
  assert.equal(findRoleManifesto(roles, 'coder'), roles[1]);
  assert.equal(findRoleManifesto(roles, 'roles\\CODER.md'), roles[1]);
  assert.equal(findRoleManifesto(roles, 'assente'), undefined);
});
