import {test} from 'node:test';
import assert from 'node:assert/strict';
import {identity, revisionOf, validateCapture} from '../extension/core.js';

const source = 'https://blog.naver.com/fixture_author/12';
const payload = {source_url: source, title: '합성 예시', published_at_raw: '2026. 9. 16.',
  body: '이것은 원문 위치와 저장 결과를 검증하기 위한 합성 자료입니다.', warnings: []};
const session = {enabled: true, tabId: 10, blog: 'fixture_author', expiresAt: Date.now() + 60_000};
const sender = {tab: {id: 10, url: source}, url: 'https://blog.naver.com/PostView.naver?blogId=fixture_author&logNo=12'};

test('only canonical post identities are accepted', () => {
  assert.equal(identity(source).key, identity(sender.url).key);
  for (const url of ['https://blog.naver.com/fixture_author', 'https://blog.naver.com.evil.test/fixture_author/12',
    'http://blog.naver.com/fixture_author/12', 'https://blog.naver.com/PostView.naver?blogId=fixture_author&logNo=12&logNo=13']) {
    assert.equal(identity(url), null);
  }
});
test('wrong tab, author, frame and expired session cannot write', () => {
  assert.equal(validateCapture(payload, sender, session).post, '12');
  assert.throws(() => validateCapture(payload, sender, {...session, tabId: 11}), /NOT_ARMED/);
  assert.throws(() => validateCapture(payload, sender, {...session, blog: 'other'}), /DOCUMENT_MISMATCH/);
  assert.throws(() => validateCapture(payload, {...sender, url: source.replace('/12', '/13')}, session), /DOCUMENT_MISMATCH/);
  assert.throws(() => validateCapture(payload, sender, {...session, expiresAt: 0}), /SESSION_EXPIRED/);
});
test('invalid or incomplete records cannot receive a saved acknowledgment', () => {
  assert.throws(() => validateCapture({...payload, body: 'short'}, sender, session), /INCOMPLETE_BODY/);
  assert.throws(() => validateCapture({...payload, published_at_raw: ''}, sender, session), /INVALID_PAYLOAD/);
});
test('revision hashes ignore capture time and change with source text', async () => {
  const original = await revisionOf(payload);
  assert.equal(await revisionOf({...payload, captured_at: 'different'}), original);
  assert.notEqual(await revisionOf({...payload, body: payload.body + ' 변경.'}), original);
});
