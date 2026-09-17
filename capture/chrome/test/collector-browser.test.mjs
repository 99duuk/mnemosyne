import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Browser} from '../collector/browser.mjs';
import {Store} from '../collector/store.mjs';

function listFixture() {
  return `<!doctype html><meta charset="utf-8"><h4 class="category_title">전체보기 65개의 글</h4>
  <ul><li><a id="category0" href="/PostList.naver?blogId=fixture&categoryNo=0">전체보기</a><span class="num">(65)</span></li></ul>
  <span id="listCountView">30줄 보기</span><div id="list"></div><div class="blog2_paginate"></div>
  <a class="btn_openlist _toggleTopList" href="#" onclick="render(1);document.querySelector('#toplistSpanBlind').textContent='목록닫기';return false"><span id="toplistSpanBlind">목록열기</span></a>
  <script>function render(n){let html='<table class="blog2_categorylist">';for(let i=(n-1)*30+1;i<=Math.min(n*30,65);i++)html+='<tr><td><a class="_setTopListUrl" href="https://blog.naver.com/fixture/'+i+'">합성 글 '+i+'</a></td><td class="date">2026. 9. 11.</td></tr>';document.querySelector('#list').innerHTML=html+'</table>';document.querySelector('.blog2_paginate').innerHTML=[1,2,3].map(i=>i===n?'<strong class="_goPageTop _param('+i+')">'+i+'</strong>':'<a href="#" class="_goPageTop _param('+i+')" onclick="render('+i+');return false">'+i+'</a>').join('')}</script>`;
}
function articleFixture() {
  return `<!doctype html><meta charset="utf-8"><h1 class="se-title-text">합성 글 1</h1><time class="se_publishDate">2026. 9. 11. 12:40</time>
  <span class="nick">합성 작성자</span><a href="/PostList.naver?blogId=fixture&categoryNo=1" onclick="sendClickNlog('pst.category','')">테스트</a>
  <table><tr><td><main class="se-main-container"><p class="se-text-paragraph">이 글은 수집기의 본문 저장과 원문 비교를 검증하기 위한 합성 자료입니다.</p>
  <div class="se-quotation-container"><p class="se-text-paragraph">다른 사람의 말은 작성자 본인의 주장으로 단정하지 않는다.</p></div>
  <table><tr><td><p class="se-text-paragraph">표 안에만 존재하는 중요한 근거</p></td></tr></table>
  <a href="https://example.com/research">출처 링크</a><img src="https://example.com/image.png" alt="합성 도표 설명"><script>window.fixture=true</script></main></td></tr></table>`;
}

test('browser inventory resumes with one-page budgets, archives quote/table/image, prunes only after commit, persists stop', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'mnemosyne-collector-browser-'));
  let store = new Store(dir), browser;
  const open = async () => {
    browser = new Browser(store, {headless: true, interval: 0}); await browser.open();
    await browser.context.route('**/*', route => {
      const u = new URL(route.request().url());
      if (u.hostname !== 'blog.naver.com') return route.abort();
      if (u.pathname === '/blocked') return route.fulfill({status: 429, headers: {'Retry-After': '120'}, body: 'Rate limit'});
      return route.fulfill({contentType: 'text/html; charset=utf-8', body: u.pathname === '/PostList.naver' ? listFixture() : articleFixture()});
    });
  };
  try {
    await open(); const categories = await browser.categories('fixture');
    const frames = browser.page.frames.bind(browser.page);
    browser.page.frames = () => [{url: () => ''}, ...frames()];
    await browser.check(); browser.page.frames = frames;
    let result = await browser.inventory('fixture', categories[0], {maxPages: 1});
    assert.equal(result.snapshot.documents.length, 30); assert.equal(result.snapshot.status, 'partial');
    await browser.close(); store.close(); store = new Store(dir); await open();
    result = await browser.inventory('fixture', categories[0], {maxPages: 1});
    assert.equal(result.snapshot.documents.length, 60);
    result = await browser.inventory('fixture', categories[0], {maxPages: 1});
    assert.equal(result.snapshot.documents.length, 65); assert.equal(result.snapshot.status, 'complete');
    const record = await browser.capture(result.snapshot.documents[0]);
    assert.equal(record.category.name, '테스트');
    assert(record.blocks.some(b => b.type === 'quote'));
    assert(record.blocks.some(b => b.type === 'table' && b.rows[0][0].includes('중요한 근거')));
    assert(record.blocks.some(b => b.type === 'image' && b.alt === '합성 도표 설명'));
    assert(!record.body.includes('표 안에만')); // old body remains byte-for-byte compatible
    assert.equal(record.links[0].url, 'https://example.com/research');
    assert.equal(store.document(record.document_id).status, 'stored');
    const staging = await browser.worker.evaluate(async () => Object.keys(await chrome.storage.local.get(null)).filter(k => k.startsWith('record:')));
    assert.equal(staging.length, 0);
    await assert.rejects(browser.goto('https://blog.naver.com/blocked'), /ACCESS_STOP_HTTP_429/);
    assert.equal(store.get('access_stop').reason, 'HTTP_429');
    assert(store.get('access_stop').retry_not_before);
    await browser.close();
    await assert.rejects(browser.open(), /ACCESS_STOP_PENDING_REVIEW/);
  } finally { await browser?.close(); store.close(); await fs.rm(dir, {recursive: true, force: true}); }
});
