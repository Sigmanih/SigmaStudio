import test from 'node:test';
import assert from 'node:assert/strict';
import { modelName, modelNames } from '../src/services/modelIdentity.js';
import { getProviderForModel } from '../src/components/Chat/modelProviderMap.js';

test('i modelli locali e le preferenze producono sempre un nome valido', () => {
  assert.equal(modelName({ name: ' fixture-model ' }), 'fixture-model');
  assert.equal(modelName({ name: {}, filename: 'qwen.gguf' }), 'qwen.gguf');
  assert.equal(modelName({ model_id: 'repo/model' }), 'repo/model');
  for (const invalid of [null, undefined, 42, {}, [], { name: {} }]) {
    assert.equal(modelName(invalid), '');
  }
  assert.deepEqual(modelNames([' a ', { name: 'a' }, {}, { filename: 'b' }]), ['a', 'b']);
  assert.deepEqual(modelNames({ name: 'a' }), []);
});

test('il routing gestisce descrittori e dati incompleti senza interrompere la chat', () => {
  assert.equal(getProviderForModel({ filename: 'qwen.gguf' }), 'sigma_engine');
  assert.equal(getProviderForModel({ name: 'gpt-4o' }), 'openai');
  assert.equal(getProviderForModel({ name: {} }), 'sigma_engine');
});
