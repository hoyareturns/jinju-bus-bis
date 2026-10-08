import test from 'node:test';
import assert from 'node:assert/strict';
import { readSelection, normalizeBuses, mergeLocations, restoreSnapshot } from '../static/state.mjs';

test('empty selection persists, corrupt storage recovers, input deduplicates', () => {
  assert.deepEqual(readSelection('[]'), []);
  assert.deepEqual(readSelection('{oops'), ['10']);
  assert.deepEqual(normalizeBuses(['10', ' 160 ', '10', '<img>']), ['10', '160']);
});

const route = {busNo:'10', routeId:'A', status:'ok', stale:false,
  updatedAt:'2026-10-08T00:00:00Z', vehicles:[{id:'A|1', lat:35.18, lon:128.1, bearing:90}]};
test('whole-bus failure retains data with original timestamp and unknown bearing', () => {
  const merged = mergeLocations([route], {routes:[], errors:[{busNo:'10', message:'오류'}]}, ['10']);
  assert.equal(merged[0].stale, true);
  assert.equal(merged[0].updatedAt, route.updatedAt);
  assert.equal(merged[0].vehicles[0].bearing, null);
  assert.equal(route.vehicles[0].bearing, 90);
});
test('removed routes and successfully empty variants do not reappear', () => {
  assert.deepEqual(mergeLocations([route], {routes:[route], errors:[]}, []), []);
  assert.deepEqual(mergeLocations([route], {routes:[{...route, vehicles:[]}], errors:[]}, ['10'])[0].vehicles, []);
  assert.deepEqual(mergeLocations([route], {routes:[], errors:[{busNo:'10', code:'NOT_FOUND'}]}, ['10']), []);
});
test('cache restores only selected valid recent data, always marked previous', () => {
  const now = Date.parse('2026-10-08T00:01:00Z');
  const restored = restoreSnapshot(JSON.stringify([route]), ['10'], now);
  assert.equal(restored[0].stale, true);
  assert.equal(restored[0].vehicles[0].bearing, null);
  assert.deepEqual(restoreSnapshot(JSON.stringify([route]), [], now), []);
  assert.deepEqual(restoreSnapshot(JSON.stringify([route]), ['10'], now+86400001), []);
  assert.deepEqual(restoreSnapshot('[{"busNo":"10"}]', ['10'], now), []);
});
