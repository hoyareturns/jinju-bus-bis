import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const context = { URL };
vm.runInNewContext(fs.readFileSync(new URL('../static/worker-policy.js', import.meta.url), 'utf8'), context);
const policy = context.BusWorkerPolicy;
const scope = 'https://example.test/apps/bus/';
test('worker handles only its explicit own app assets', () => {
  assert.equal(policy.cacheable(scope + 'app.js', scope), true);
  for (const path of ['https://example.test/', scope+'api/v2/locations', scope+'other', 'https://tiles.test/a.png']) {
    assert.equal(policy.cacheable(path, scope), false);
  }
});
test('cache cleanup preserves hub and other installation caches', () => {
  assert.equal(policy.obsolete('zeriona-v1', scope, 'v2'), false);
  assert.equal(policy.obsolete('jinju-bus:/other/:v1', scope, 'v2'), false);
  assert.equal(policy.obsolete('jinju-bus:/apps/bus/:v1', scope, 'v2'), true);
  assert.equal(policy.obsolete('jinju-bus:/apps/bus/:v2', scope, 'v2'), false);
});
