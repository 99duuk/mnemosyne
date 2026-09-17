import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {identity, revisionOf} from '../extension/core.js';
import {accessMonitor} from './access-monitor.mjs';

const blog = 'sofoswh';
const extension = fileURLToPath(new URL('../extension', import.meta.url));
const base = path.join(os.homedir(), 'Library/Application Support/Mnemosyne/browser-test');
await fs.mkdir(base, {recursive: true, mode: 0o700});
const dir = await fs.mkdtemp(path.join(base, 'live50-'));
const profile = path.join(dir, 'profile');
let context;
const receipts = [];
let monitor;

function xmlItems(xml) {
  return [...xml.matchAll(/<item>[\s\S]*?<\/item>/g)].map(m => m[0]).map(item => {
    const text = name => item.match(new RegExp(`<${name}>([\\s\\S]*?)</${name}>`))?.[1] ?? '';
    const decode = value => value.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
    return {title: decode(text('title')).trim(), url: decode(text('guid') || text('link')).trim(), pubDate: decode(text('pubDate')).trim()};
  }).map(x => ({...x, identity: identity(x.url)})).filter(x => x.identity?.blog === blog);
}

async function records(worker) {
  return worker.evaluate(async () => Object.entries(await chrome.storage.local.get(null))
    .filter(([key]) => key.startsWith('record:')).map(([, value]) => value));
}

async function capture(page, worker, target, index) {
  await monitor.check(page);
  const before = await worker.evaluate(async () => (await chrome.storage.local.get('lastReceipt')).lastReceipt?.request_id);
  const started = Date.now();
  const response = await page.goto(target.url, {waitUntil: 'domcontentloaded', timeout: 30000});
  if (!response?.ok()) throw new Error(`NAVIGATION_HTTP_${response?.status()}_${index}`);
  const deadline = Date.now() + 25000;
  let receipt;
  while (Date.now() < deadline) {
    await monitor.check(page);
    receipt = await worker.evaluate(async () => (await chrome.storage.local.get('lastReceipt')).lastReceipt);
    if (receipt?.request_id !== before && receipt?.document_id === target.identity.key) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  assert(receipt?.request_id !== before && receipt?.document_id === target.identity.key, `NO_RECEIPT_${index}`);
  assert(['SAVED', 'DUPLICATE'].includes(receipt.status));
  const saved = (await records(worker)).find(r => r.document_id === receipt.document_id && r.revision_id === receipt.revision_id);
  assert(saved, `NO_RECORD_${index}`);
  assert.equal(await revisionOf(saved), receipt.revision_id);
  let frame;
  for (const candidate of page.frames()) {
    if (identity(candidate.url())?.key !== target.identity.key) continue;
    if (await candidate.locator('.se-main-container').count()) { frame = candidate; break; }
  }
  assert(frame, `NO_ARTICLE_FRAME_${index}`);
  const sourceText = await frame.locator('.se-main-container .se-text-paragraph').evaluateAll(nodes => nodes.filter(p => {
    for (let parent = p.parentElement; parent && !parent.matches('.se-main-container'); parent = parent.parentElement) {
      if (['TABLE', 'IFRAME', 'OBJECT', 'EMBED'].includes(parent.tagName)) return false;
    }
    return true;
  }).map(p => p.innerText ?? p.textContent).join('\n\n').trim());
  assert.equal(saved.body, sourceText, `TEXT_MISMATCH_${index}`);
  const entry = {index, title: target.title, document_id: receipt.document_id, revision_id: receipt.revision_id,
    status: receipt.status, body_length: receipt.body_length, elapsed_ms: Date.now() - started, source_text_exact_match: true};
  receipts.push(entry);
  console.log(JSON.stringify(entry));
}

try {
  context = await chromium.launchPersistentContext(profile, {headless: false,
    args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]});
  monitor = accessMonitor(context);
  const rssResponse = await context.request.get(`https://rss.blog.naver.com/${blog}.xml`);
  if (!rssResponse.ok()) throw new Error(`RSS_HTTP_${rssResponse.status()}`);
  const items = xmlItems(await rssResponse.text());
  assert.equal(items.length, 50, `RSS_ITEMS_${items.length}`);
  const seen = new Set(); const targets = items.filter(item => !seen.has(item.identity.key) && seen.add(item.identity.key));
  assert.equal(targets.length, 50, `RSS_UNIQUE_${targets.length}`);
  const page = await context.newPage();
  await page.goto(targets[0].url, {waitUntil: 'domcontentloaded', timeout: 30000});
  const tab = page.url();
  assert.equal(identity(tab).key, targets[0].identity.key);
  // The controller page is not an extension popup; arm through a trusted extension page.
  const worker = context.serviceWorkers()[0] ?? await context.waitForEvent('serviceworker', {timeout: 15000});
  const extensionId = worker.url().split('/')[2];
  const control = await context.newPage(); await control.goto(`chrome-extension://${extensionId}/popup.html`);
  const tabId = await worker.evaluate(async url => (await chrome.tabs.query({})).find(t => t.url === url)?.id, tab);
  assert(Number.isInteger(tabId));
  const armed = await control.evaluate(args => chrome.runtime.sendMessage({type: 'ARM', ...args}), {tabId, blog, limit: 50});
  assert.equal(armed.status, 'ARMED');
  await page.bringToFront();
  for (let i = 0; i < targets.length; i += 1) await capture(page, worker, targets[i], i + 1);
  const savedRecords = await records(worker);
  assert.equal(savedRecords.length, 50);
  assert.equal(new Set(savedRecords.map(r => r.document_id)).size, 50);
  const access = monitor.report();
  const report = {mode: 'live50-public-browser', blog, rss_items: items.length, documents: savedRecords.length,
    receipts, access_observation: access, stopped: false, timestamp: new Date().toISOString()};
  await worker.evaluate(async () => chrome.storage.session.remove('session'));
  report.stopped = true;
  await fs.writeFile(path.join(dir, 'report.json'), JSON.stringify(report, null, 2), {mode: 0o600});
  await fs.writeFile(path.join(dir, 'posts.jsonl'), savedRecords.map(r => JSON.stringify(r)).join('\n') + '\n', {mode: 0o600});
  for (const r of savedRecords) {
    const target = path.join(dir, 'posts', r.document_id.replace(':', '-'), r.revision_id);
    await fs.mkdir(target, {recursive: true, mode: 0o700});
    await fs.writeFile(path.join(target, 'record.json'), JSON.stringify(r, null, 2), {mode: 0o600});
    await fs.writeFile(path.join(target, 'post.md'), `# ${r.title}\n\nSource: ${r.source_url}\nPublished (raw): ${r.published_at_raw}\n\n${r.body}\n`, {mode: 0o600});
  }
  console.log(JSON.stringify({result: 'PASS', documents: savedRecords.length, rssItems: items.length,
    blockingSignal: access.blocking_signal, artifacts: dir}));
  await context.close(); context = null;
} catch (error) {
  await fs.writeFile(path.join(dir, 'failure.json'), JSON.stringify({error: error.message, receipts,
    access_observation: monitor?.report()}, null, 2), {mode: 0o600});
  console.error(JSON.stringify({result: 'FAIL', error: error.message, completed: receipts.length, artifacts: dir}));
  process.exitCode = 1;
} finally { if (context) await context.close(); }
