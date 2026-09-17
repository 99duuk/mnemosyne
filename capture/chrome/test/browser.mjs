import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {identity, revisionOf} from '../extension/core.js';
import {accessMonitor} from './access-monitor.mjs';

const live = process.argv.includes('--live');
const blog = live ? process.env.MNEMOSYNE_TEST_BLOG : 'fixture_author';
if (!/^[A-Za-z0-9_-]{1,64}$/.test(blog ?? '')) throw new Error('Set MNEMOSYNE_TEST_BLOG explicitly for --live');
const extension = fileURLToPath(new URL('../extension', import.meta.url));
const base = live ? path.join(os.homedir(), 'Library/Application Support/Mnemosyne/browser-test') : os.tmpdir();
await fs.mkdir(base, {recursive: true, mode: 0o700});
const dir = await fs.mkdtemp(path.join(base, live ? 'live-' : 'mnemosyne-extension-'));
const profile = path.join(dir, 'profile');
const receipts = [];
let context;
let changed = false;
let monitor;

function fixture(post) {
  const body = `합성 글 ${post}: 선택의 기대 이익과 실패했을 때의 비용을 함께 비교한다. 적용 조건이 달라지면 결론도 달라질 수 있다.${changed && post === '1' ? ' 수정된 조건.' : ''}`;
  return `<!doctype html><html><meta charset="utf-8"><title>Synthetic ${post}</title>
    <h1 class="se-title-text">합성 글 ${post}</h1><time class="se_publishDate">2026. 9. 16. 12:00</time>
    <table class="page-layout"><tr><td><main class="se-main-container"><p class="se-text-paragraph">${body}</p>
    <table><tr><td><p class="se-text-paragraph">합성 표: 본문에서 제외</p></td></tr></table>
    </main></td></tr></table></html>`;
}

async function launch() {
  const c = await chromium.launchPersistentContext(profile, {channel: 'chromium', headless: !live,
    args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]});
  if (!live) await c.route('https://blog.naver.com/**', async route => {
    const u = new URL(route.request().url()); const id = identity(u.href);
    const body = u.pathname === `/${blog}/2`
      ? `<!doctype html><iframe id="mainFrame" src="/PostView.naver?blogId=${blog}&logNo=2"></iframe>`
      : fixture(id?.post ?? '0');
    await route.fulfill({status: 200, contentType: 'text/html; charset=utf-8', body});
  });
  let worker = c.serviceWorkers()[0];
  if (!worker) worker = await c.waitForEvent('serviceworker', {timeout: 15000});
  return {c, worker};
}

async function records(worker) {
  return worker.evaluate(async () => Object.entries(await chrome.storage.local.get(null))
    .filter(([k]) => k.startsWith('record:')).map(([, v]) => v));
}

async function capture(page, worker, url, expected) {
  const started = Date.now();
  const previous = await worker.evaluate(async () => (await chrome.storage.local.get('lastReceipt')).lastReceipt?.request_id);
  const response = await page.goto(url, {waitUntil: 'domcontentloaded', timeout: 30000});
  if (!response?.ok()) throw new Error(`NAVIGATION_HTTP_${response?.status()}`);
  const deadline = Date.now() + 25000;
  let receipt;
  while (Date.now() < deadline) {
    await monitor.check(page);
    receipt = await worker.evaluate(async () => (await chrome.storage.local.get('lastReceipt')).lastReceipt);
    if (receipt && receipt.request_id !== previous && receipt.document_id === identity(url).key) break;
    for (const frame of page.frames()) {
      const failure = await frame.locator('#mnemosyne-capture-status[data-status="ERROR"]').textContent({timeout: 100}).catch(() => null);
      if (failure) throw new Error(failure);
    }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  assert(receipt && receipt.request_id !== previous && receipt.document_id === identity(url).key, 'No matching durable receipt');
  assert.equal(receipt.status, expected);
  const saved = (await records(worker)).find(r => r.document_id === receipt.document_id && r.revision_id === receipt.revision_id);
  assert(saved, 'Receipt without stored record');
  assert.equal(await revisionOf(saved), receipt.revision_id);
  // Independent comparison with rendered paragraphs, not with the extension message.
  const sourceFrame = page.frames().find(f => identity(f.url())?.key === identity(url).key && f !== page.mainFrame()) ?? page.mainFrame();
  const sourceText = await sourceFrame.locator('.se-main-container .se-text-paragraph').evaluateAll(nodes =>
    nodes.filter(p => {
      for (let parent = p.parentElement; parent && !parent.matches('.se-main-container'); parent = parent.parentElement) {
        if (['TABLE', 'IFRAME', 'OBJECT', 'EMBED'].includes(parent.tagName)) return false;
      }
      return true;
    }).map(p => p.innerText ?? p.textContent).join('\n\n').trim());
  assert.equal(saved.body, sourceText);
  await monitor.check(page);
  const screenshot = `capture-${receipts.length + 1}.png`;
  if (live) await sourceFrame.locator('.se-main-container').screenshot({path: path.join(dir, screenshot)});
  receipts.push({...receipt, source_text_exact_match: true, elapsed_ms: Date.now() - started,
    screenshot: live ? screenshot : null});
  console.log(JSON.stringify({status: receipt.status, characters: receipt.body_length, sourceTextExactMatch: true}));
  return saved;
}

try {
  let {c, worker} = await launch(); context = c;
  monitor = accessMonitor(c);
  const page = c.pages()[0] ?? await c.newPage();
  let urls;
  if (live) {
    const response = await page.goto(`https://blog.naver.com/${blog}`, {waitUntil: 'domcontentloaded', timeout: 30000});
    if (!response?.ok()) throw new Error('HOME_UNAVAILABLE');
    await page.waitForTimeout(2000);
    await monitor.check(page);
    const links = [];
    for (const frame of page.frames()) links.push(...await frame.locator('a[href]').evaluateAll(nodes => nodes.map(n => n.href)));
    urls = [...new Set(links.map(identity).filter(x => x?.blog === blog).map(x => x.url))].slice(0, 2);
    assert.equal(urls.length, 2, 'Could not discover two posts in homepage links');
  } else urls = [`https://blog.naver.com/${blog}/1`, `https://blog.naver.com/${blog}/2`];

  // Open a post unarmed, then exercise the real extension control message.
  await page.goto(urls[0], {waitUntil: 'domcontentloaded'});
  await monitor.check(page);
  const tabId = await worker.evaluate(async url => (await chrome.tabs.query({})).find(t => t.url === url)?.id, urls[0]);
  assert(Number.isInteger(tabId));
  const control = await c.newPage();
  await control.goto(`chrome-extension://${worker.url().split('/')[2]}/popup.html`);
  const armed = await control.evaluate(args => chrome.runtime.sendMessage({type: 'ARM', ...args}), {tabId, blog});
  assert.equal(armed.status, 'ARMED');
  await page.bringToFront();

  await capture(page, worker, urls[0], 'SAVED');
  await capture(page, worker, urls[0], 'DUPLICATE');
  await capture(page, worker, urls[1], 'SAVED');

  if (!live) {
    for (const record of await records(worker)) {
      assert(!record.body.includes('합성 표: 본문에서 제외'));
      assert(record.warnings.includes('TABLES_OMITTED'));
    }
    changed = true;
    const revised = await capture(page, worker, urls[0], 'SAVED');
    assert(revised.supersedes_revision_id);
    await assert.rejects(capture(page, worker, `https://blog.naver.com/${blog}/3`, 'SAVED'), /LIMIT_REACHED/);
    await page.goto('https://blog.naver.com/other_author/9');
    const before = (await records(worker)).length;
    await page.waitForTimeout(1800);
    assert.equal((await records(worker)).length, before);
    assert.equal(await page.locator('#mnemosyne-capture-status').count(), 0);
  }

  const originalRecords = await records(worker);
  const accessReport = monitor.report();
  assert.equal(new Set(originalRecords.map(r => r.document_id)).size, 2);
  await control.evaluate(() => chrome.runtime.sendMessage({type: 'STOP'}));
  await c.close(); context = null;
  // Browser restart proves records outlive the worker/context and capture remains disarmed.
  ({c, worker} = await launch()); context = c;
  const persisted = await records(worker);
  assert.deepEqual(persisted.sort((a,b) => a.revision_id.localeCompare(b.revision_id)),
    originalRecords.sort((a,b) => a.revision_id.localeCompare(b.revision_id)));
  assert.equal(await worker.evaluate(async () => Boolean((await chrome.storage.session.get('session')).session?.enabled)), false);
  const report = {mode: live ? 'live-public-browser' : 'synthetic-browser', browser: 'Playwright Chromium with real MV3 extension',
    chrome_for_codex_verified: false, documents: 2, revisions: persisted.length, receipts,
    restart_persistence: true, stopped: true, synthetic_extra_checks: live ? null : ['revision-lineage', 'third-document-limit', 'wrong-author-block'],
    access_observation: accessReport,
    timestamp: new Date().toISOString()};
  await fs.writeFile(path.join(dir, 'report.json'), JSON.stringify(report, null, 2), {mode: 0o600});
  await fs.writeFile(path.join(dir, 'posts.jsonl'), persisted.map(r => JSON.stringify(r)).join('\n') + '\n', {mode: 0o600});
  for (const r of persisted) {
    const target = path.join(dir, 'posts', r.document_id.replace(':', '-'), r.revision_id);
    await fs.mkdir(target, {recursive: true, mode: 0o700});
    await fs.writeFile(path.join(target, 'record.json'), JSON.stringify(r, null, 2), {mode: 0o600});
    await fs.writeFile(path.join(target, 'post.md'), `# ${r.title}\n\nSource: ${r.source_url}\nPublished (raw): ${r.published_at_raw}\n\n${r.body}\n`, {mode: 0o600});
  }
  console.log(JSON.stringify({result: 'PASS', mode: report.mode, documents: 2, revisions: persisted.length,
    restartPersistence: true, chromeForCodexVerified: false, artifacts: dir}));
} catch (error) {
  await fs.writeFile(path.join(dir, 'failure.json'), JSON.stringify({error: error.message, receipts, access_observation: monitor?.report()}, null, 2), {mode: 0o600});
  console.error(JSON.stringify({result: 'FAIL', error: error.message, artifacts: dir}));
  process.exitCode = 1;
} finally {
  if (context) {
    for (const worker of context.serviceWorkers()) await worker.evaluate(() => chrome.storage.session.remove('session')).catch(() => {});
    await context.close();
  }
}
