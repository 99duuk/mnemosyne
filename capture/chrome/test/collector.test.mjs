import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {gunzipSync} from 'node:zlib';
import {makePlan, selectDocuments, absoluteDate} from '../collector/plan.mjs';
import {Store, digest, relativeDateRange} from '../collector/store.mjs';
import {retryAfter} from '../collector/browser.mjs';
import {revisionOf} from '../extension/core.js';

const categories = [
  {id: '0', parent_id: null}, {id: '1', parent_id: '0'}, {id: '14', parent_id: '0'},
  {id: '13', parent_id: '14'}, {id: '15', parent_id: '14'},
];
test('default all; descendants collapse; exclusion wins; invalid IDs rejected', () => {
  assert.deepEqual(makePlan('fixture', categories).include, ['0']);
  assert.deepEqual(makePlan('fixture', categories, {include: ['14', '13', '1']}).include, ['14', '1']);
  assert.deepEqual(makePlan('fixture', categories, {include: ['13'], exclude: ['14']}).include, []);
  assert.deepEqual(makePlan('fixture', categories, {include: []}).include, []);
  assert.throws(() => makePlan('fixture', categories, {exclude: ['missing']}), /UNKNOWN_CATEGORY/);
});
test('incomplete exclusion blocks selection, overlapping/pinned documents deduplicate', () => {
  const plan = makePlan('fixture', categories, {exclude: ['14']});
  const inventories = {'0': {documents: [{document_id: 'fixture:1'}, {document_id: 'fixture:2'}, {document_id: 'fixture:1'}]}, '14': {status: 'partial', documents: [{document_id: 'fixture:2'}]}};
  assert.throws(() => selectDocuments(plan, inventories), /EXCLUSION_INVENTORY_INCOMPLETE/);
  inventories['14'].status = 'complete';
  assert.deepEqual(selectDocuments(plan, inventories), [{document_id: 'fixture:1'}]);
});
test('dates preserve day precision and do not fabricate relative timestamps; Retry-After parsed', () => {
  assert.deepEqual(absoluteDate('2026. 9. 11. 12:40'), {value: '2026-09-11T12:40:00+09:00', precision: 'minute'});
  assert.deepEqual(absoluteDate('2026. 9. 11.'), {value: '2026-09-11', precision: 'day'});
  assert.equal(absoluteDate('2시간 전').value, null);
  assert.equal(absoluteDate('2026. 2. 31.').value, null);
  assert.equal(retryAfter('120', 0), '1970-01-01T00:02:00.000Z');
  assert.equal(retryAfter('Thu, 01 Jan 1970 00:02:00 GMT', 0), '1970-01-01T00:02:00.000Z');
  assert.deepEqual(relativeDateRange('5시간 전', '2026-09-16T12:00:00.000Z'), {lower: '2026-09-16T06:00:00.000Z', upper: '2026-09-16T07:00:00.000Z', precision: 'relative-시간'});
});
test('atomic archive survives reopen, rejects corrupt import, semantic revision ignores relative clock changes', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'mnemosyne-store-'));
  let store;
  try {
    store = new Store(dir);
    const record = {schema: 'mnemosyne.chrome-test/v1', document_id: 'fixture:1', source_url: 'https://blog.naver.com/fixture/1',
      title: '합성 글', body: '이것은 저장과 복원을 검증하기 위해 만들어진 합성 본문입니다.', published_at_raw: '2시간 전', captured_at: new Date().toISOString(), warnings: [], rag_eligible: false};
    record.revision_id = await revisionOf(record);
    const extras = {article_html: '<p>합성 원본</p>', blocks: [{type: 'paragraph', text: record.body}], links: [], category: {id: '1', name: '테스트'}};
    await store.save(record, extras);
    record.published_at_raw = '3시간 전'; record.revision_id = await revisionOf(record);
    await store.save(record, extras);
    assert.equal(store.db.prepare('SELECT count(*) AS n FROM records').get().n, 1);
    assert.equal(store.db.prepare('SELECT count(*) AS n FROM observations').get().n, 2);
    await assert.rejects(store.save({...record, body: 'tampered'}), /INVALID_RECORD/);
    store.close(); store = new Store(dir);
    assert.equal(store.document('fixture:1').status, 'stored');
    const row = store.db.prepare('SELECT * FROM records').get();
    assert.equal(digest(gunzipSync(row.html_gzip)), row.html_sha256);
    assert.equal(store.export().documents, 1);
    const exported = JSON.parse((await fs.readFile(path.join(dir, 'posts.jsonl'), 'utf8')).trim());
    assert.equal(await revisionOf(exported), exported.revision_id);
  } finally { store?.close(); await fs.rm(dir, {recursive: true, force: true}); }
});
