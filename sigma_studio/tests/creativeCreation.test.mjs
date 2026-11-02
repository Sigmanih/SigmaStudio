import nodeTest from 'node:test';
import { existsSync } from 'node:fs';
import assert from 'node:assert/strict';
const creationUrl = new URL('../src/modules/sigma_creative_lab/Generate/imageCreation.js', import.meta.url);
const responseUrl = new URL('../src/modules/sigma_creative_lab/creativeResponse.js', import.meta.url);
const installed = existsSync(creationUrl) && existsSync(responseUrl);
// Il checkout del solo kernel non installa i laboratori opzionali.
const test = (name, fn) => nodeTest(name, { skip: !installed && 'Creative Lab non installato' }, fn);
const { IMAGE_DRAFT, imageModels, selectionIssue, imageRequest, selectImageModel, draftFromAsset } = installed ? await import(creationUrl) : {};
const { readCreativeResponse } = installed ? await import(responseUrl) : {};

const model = { id: 'custom', tasks: ['text_to_image'], available: true, available_via: ['comfyui'], workflow_available: true };
test('il modello e il file scelti arrivano entrambi alla richiesta', () => {
  const draft = { ...IMAGE_DRAFT, prompt: '  Un paesaggio  ', model: { model_id: 'custom', ckpt: 'my_model.safetensors' }, backend: 'comfyui' };
  const request = imageRequest(draft);
  assert.equal(request.params.model_id, 'custom');
  assert.equal(request.params.ckpt, 'my_model.safetensors');
  assert.equal(request.backend, 'comfyui');
  assert.equal(request.params.prompt, 'Un paesaggio');
});
test('dimensioni e parametri vuoti non diventano valori silenziosamente diversi', () => {
  assert.throws(() => imageRequest({ ...IMAGE_DRAFT, prompt: 'x', width: '' }));
  assert.throws(() => imageRequest({ ...IMAGE_DRAFT, prompt: 'x', width: 1001 }), /multipli/);
  assert.throws(() => imageRequest({ ...IMAGE_DRAFT, prompt: 'x', seed: NaN }));
});
test('un file installato non rende utilizzabile un motore incompatibile', () => {
  const draft = { ...IMAGE_DRAFT, model: { model_id: 'custom', ckpt: 'paint.safetensors' } };
  const inventory = { reachable: true, enabled: true, checkpoints: ['paint.safetensors'] };
  assert.equal(selectionIssue(draft, [model], inventory), '');
  assert.match(selectionIssue({ ...draft, backend: 'fal_ai' }, [model], inventory), /ComfyUI/);
  assert.match(selectionIssue(draft, [model], { ...inventory, checkpoints: [] }), /non è più disponibile/);
});
test('cambio modello e riuso della descrizione conservano scelte coerenti', () => {
  const changed = selectImageModel({ ...IMAGE_DRAFT, prompt: 'x' }, { model_id: 'workflow:mine' }, { defaults: { steps: 6, cfg_scale: 2 } });
  assert.equal(changed.steps, 6);
  assert.equal(changed.prompt, 'x');
  const reused = draftFromAsset({ metadata: { params: { prompt: 'riusata', width: 512, model_id: 'custom' } } }, changed);
  assert.equal(reused.prompt, 'riusata');
  assert.equal(reused.width, 512);
  assert.equal(reused.model.model_id, 'custom');
  assert.equal(imageModels([{}, model]).length, 1);
});
function stream(chunks) {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({ start(controller) { chunks.forEach(c => controller.enqueue(encoder.encode(c))); controller.close(); } }), { headers: { 'Content-Type': 'text/event-stream' } });
}
test('SSE spezzati, CRLF e ultimo frame senza newline conservano il risultato', async () => {
  const events = [];
  const result = await readCreativeResponse(stream(['data:{"progress":5}\r\n\r', '\ndata: {"asset":', '{"id":"a1"}}']), event => events.push(event));
  assert.equal(result.asset.id, 'a1');
  assert.equal(events.length, 2);
});
test('fallimenti di pipeline e stream vuoti non sono successi', async () => {
  await assert.rejects(readCreativeResponse(stream(['data:{"asset":{"id":"partial"}}\n\ndata:{"error":"nodo fallito"}\n\n'])), /nodo fallito/);
  await assert.rejects(readCreativeResponse(stream(['data:{"status":"complete"}\n\n'])), /senza un risultato/);
  await assert.rejects(readCreativeResponse(new Response('<html>', { headers: { 'Content-Type': 'text/html' } })), /non risponde correttamente/);
});
