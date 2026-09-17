import {chromium} from 'playwright';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {identity, revisionOf} from '../extension/core.js';
import {readCategories, readList, readArticleExtras} from './dom.mjs';

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
export function retryAfter(raw, now = Date.now()) {
  if (!raw) return null;
  const at = /^\d+$/.test(raw) ? now + Number(raw) * 1000 : Date.parse(raw);
  return Number.isFinite(at) ? new Date(Math.max(now, at)).toISOString() : null;
}

export class Browser {
  constructor(store, {headless = false, interval = 5000, loadMedia = false} = {}) {
    this.store = store; this.options = {headless, interval, loadMedia}; this.lastAction = 0;
    this.stopped = null; this.responses = {}; this.context = null;
  }
  async open() {
    if (this.store.get('access_stop')) throw new Error('ACCESS_STOP_PENDING_REVIEW');
    const extension = fileURLToPath(new URL('../extension', import.meta.url));
    this.context = await chromium.launchPersistentContext(path.join(this.store.dir, 'profile'), {
      channel: 'chromium', headless: this.options.headless,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`],
    });
    if (!this.options.loadMedia) await this.context.route('**/*', route =>
      ['image', 'media', 'font'].includes(route.request().resourceType()) ? route.abort() : route.continue());
    this.context.on('response', response => {
      const u = new URL(response.url());
      if (u.hostname !== 'blog.naver.com') return;
      const status = response.status(); this.responses[status] = (this.responses[status] ?? 0) + 1;
      if ([401, 403, 429].includes(status)) this.stop(`HTTP_${status}`, retryAfter(response.headers()['retry-after']));
    });
    this.worker = this.context.serviceWorkers()[0] ?? await this.context.waitForEvent('serviceworker');
    this.page = await this.context.newPage();
    this.control = await this.context.newPage();
    await this.control.goto(`chrome-extension://${this.worker.url().split('/')[2]}/popup.html`);
  }
  stop(reason, retryAt = null) {
    if (!this.stopped) {
      this.stopped = {reason, at: new Date().toISOString(), retry_not_before: retryAt};
      this.store.set('access_stop', this.stopped);
    }
  }
  async check() {
    if (this.stopped) throw new Error(`ACCESS_STOP_${this.stopped.reason}`);
    for (const frame of this.page.frames()) {
      // Newly attached ad/layout frames can have an empty URL before navigation.
      if (!frame.url()) continue;
      const u = new URL(frame.url());
      if (/^(nid|accounts)\.naver\.com$/.test(u.hostname)) { this.stop('LOGIN_REDIRECT'); break; }
      if (u.hostname !== 'blog.naver.com') continue;
      const signal = await frame.evaluate(() => {
        const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
        if ([...document.querySelectorAll('input[name*="captcha" i],input[id*="captcha" i],iframe[src*="captcha" i]')].some(visible)) return 'CAPTCHA';
        if (!document.querySelector('.se-main-container') && /비정상적인 접근|접근이 제한|잠시 후 다시 이용|자동입력 방지문자/.test(document.body?.innerText ?? '')) return 'ACCESS_NOTICE';
        return null;
      }).catch(() => 'INSPECTION_FAILED');
      if (signal) { this.stop(signal); break; }
    }
    if (this.stopped) throw new Error(`ACCESS_STOP_${this.stopped.reason}`);
  }
  async pace() {
    await this.check();
    const previous = Math.max(this.lastAction, this.store.get('last_navigation_at') ?? 0);
    await wait(Math.max(0, this.options.interval - (Date.now() - previous)));
    await this.check(); this.lastAction = Date.now(); this.store.set('last_navigation_at', this.lastAction);
  }
  async goto(url) {
    await this.pace();
    const response = await this.page.goto(url, {waitUntil: 'domcontentloaded', timeout: 30000});
    await this.check();
    if (!response?.ok()) throw new Error(`NAVIGATION_HTTP_${response?.status()}`);
  }
  async categories(blog) {
    await this.goto(`https://blog.naver.com/PostList.naver?blogId=${blog}&categoryNo=0`);
    await this.page.locator('#category0').waitFor({timeout: 20000});
    const categories = await this.page.evaluate(readCategories);
    if (categories.length < 1 || new Set(categories.map(c => c.id)).size !== categories.length) throw new Error('CATEGORY_LAYOUT_UNSUPPORTED');
    for (const c of categories) {
      const u = new URL(c.url);
      if (u.origin !== 'https://blog.naver.com' || u.searchParams.get('blogId') !== blog) throw new Error('CATEGORY_BLOG_MISMATCH');
    }
    await this.check(); return categories;
  }
  async ensureListOpen() {
    const closed = async () => (await this.page.locator('#toplistSpanBlind').textContent({timeout: 100}).catch(() => '')).trim() === '목록열기';
    if (await closed()) {
      await this.pace();
      // Site preferences can settle while pacing. Never toggle an already open list shut.
      if (await closed()) await this.page.locator('a.btn_openlist._toggleTopList').click();
      await this.page.waitForFunction(() => document.querySelector('#toplistSpanBlind')?.textContent.trim() === '목록닫기', null, {timeout: 20000});
    }
  }
  async listState() {
    await this.page.locator('h4.category_title').waitFor({timeout: 20000});
    await this.ensureListOpen();
    await this.page.waitForFunction(() => {
      const count = document.querySelector('h4.category_title')?.textContent.match(/([\d,]+)개의 글/)?.[1];
      return document.querySelector('table.blog2_categorylist') || (count !== undefined && Number(count.replaceAll(',', '')) === 0);
    }, null, {timeout: 20000});
    return this.page.evaluate(readList);
  }
  async pageNumber(number) {
    await this.pace();
    await this.ensureListOpen();
    await this.page.locator(`.blog2_paginate a._goPageTop[class*="_param(${number})"]`).click();
    await this.page.waitForFunction(n => document.querySelector('.blog2_paginate strong._goPageTop')?.className.includes(`_param(${n})`), number, {timeout: 20000});
    await this.check(); return this.listState();
  }
  async inventory(blog, category, {maxPages = 10, refresh = false, onPage = () => {}} = {}) {
    let snapshot = !refresh ? this.store.inventories(blog)[category.id] : null;
    if (snapshot?.status === 'complete') return {pages: 0, snapshot};
    snapshot ??= {started_at: new Date().toISOString(), documents: [], pages: {}, last_page: 0, status: 'partial'};
    await this.goto(category.url);
    let state = await this.listState();
    if (state.expected_count > state.page_size && state.page_size !== 30) {
      await this.pace(); await this.ensureListOpen(); await this.page.locator('#listCountToggle').click();
      await this.page.locator('a.option[data-value="30"]').click();
      await this.page.waitForFunction(() => document.querySelector('#listCountView')?.textContent.includes('30'));
      // The label and AJAX table update separately.
      await this.page.waitForFunction(() => {
        const count = Number((document.querySelector('h4.category_title')?.textContent.match(/([\d,]+)개의 글/)?.[1] ?? '').replaceAll(',', ''));
        return document.querySelectorAll('table.blog2_categorylist a._setTopListUrl').length === Math.min(30, count);
      }, null, {timeout: 20000});
      state = await this.listState();
    }
    // Resume through visible pagination controls, overlapping one saved page.
    const previousLastPage = snapshot.last_page;
    const resume = Math.max(1, previousLastPage - 1);
    while (state.current_page < resume) {
      const candidates = state.pages.filter(n => n <= resume && n > state.current_page);
      if (!candidates.length) throw new Error('RESUME_PAGE_UNAVAILABLE_REFRESH_REQUIRED');
      state = await this.pageNumber(Math.max(...candidates));
    }
    let pages = 0;
    while (pages < maxPages) {
      await this.check();
      if (state.expected_count === null || (state.expected_count > 0 && !state.rows.length)) throw new Error('LIST_LAYOUT_OR_EMPTY_RESPONSE');
      const docs = state.rows.map(row => {
        const id = identity(row.url);
        if (!id || id.blog !== blog) throw new Error('LIST_DOCUMENT_MISMATCH');
        return {document_id: id.key, source_url: id.url, title: row.title, published_at_raw: row.published_at_raw,
          list_category_id: category.id, list_page: state.current_page, discovered_at: new Date().toISOString()};
      });
      const signature = docs.map(d => d.document_id).join(',');
      if (Object.entries(snapshot.pages).some(([n, sig]) => Number(n) !== state.current_page && sig === signature && signature)) throw new Error('REPEATED_LIST_PAGE');
      snapshot.documents = [...new Map([...snapshot.documents, ...docs].map(d => [d.document_id, d])).values()];
      snapshot.pages[state.current_page] = signature; snapshot.last_page = state.current_page;
      snapshot.expected_count = state.expected_count; snapshot.observed_at = new Date().toISOString();
      const hasNext = state.pages.includes(state.current_page + 1);
      const covered = snapshot.documents.length === state.expected_count;
      snapshot.status = !hasNext ? (covered ? 'complete' : 'count_mismatch') : 'partial';
      this.store.inventory(blog, category.id, snapshot);
      // Rechecking overlap pages must not consume the new-page budget; even a
      // one-page run must make forward progress after a restart.
      if (state.current_page > previousLastPage) pages++;
      onPage({category: category.id, page: state.current_page, discovered: snapshot.documents.length, expected: state.expected_count, status: snapshot.status});
      if (!hasNext || pages >= maxPages) break;
      state = await this.pageNumber(state.current_page + 1);
    }
    return {pages, snapshot};
  }
  async capture(target) {
    await this.control.evaluate(() => chrome.runtime.sendMessage({type: 'STOP'}));
    await this.goto(target.source_url);
    const tabId = await this.worker.evaluate(async url => (await chrome.tabs.query({})).find(t => t.url === url)?.id, this.page.url());
    const armed = await this.control.evaluate(args => chrome.runtime.sendMessage({type: 'ARM', ...args}), {tabId, blog: identity(target.source_url).blog, limit: 1});
    if (armed.status !== 'ARMED') throw new Error(armed.error ?? 'ARM_FAILED');
    const deadline = Date.now() + 25000; let receipt;
    while (Date.now() < deadline) {
      await this.check();
      receipt = await this.worker.evaluate(async () => (await chrome.storage.local.get('lastReceipt')).lastReceipt);
      if (receipt?.session_id === armed.session.id && receipt.document_id === target.document_id) break;
      await wait(300);
    }
    if (receipt?.session_id !== armed.session.id || receipt?.document_id !== target.document_id) throw new Error('CAPTURE_TIMEOUT_OR_UNSUPPORTED_LAYOUT');
    const key = `record:${receipt.document_id}:${receipt.revision_id}`;
    const record = await this.worker.evaluate(async k => (await chrome.storage.local.get(k))[k], key);
    if (!record || await revisionOf(record) !== receipt.revision_id) throw new Error('EXTENSION_READBACK_FAILED');
    let frame;
    for (const candidate of this.page.frames()) if (identity(candidate.url())?.key === target.document_id && await candidate.locator('.se-main-container').count() === 1) { frame = candidate; break; }
    if (!frame) throw new Error('ARTICLE_FRAME_MISSING');
    const source = await frame.locator('.se-main-container .se-text-paragraph').evaluateAll(nodes => nodes.filter(p => {
      const table = p.closest('table,iframe,object,embed'); return !table || !p.closest('.se-main-container').contains(table);
    }).map(p => p.innerText ?? p.textContent).join('\n\n').trim());
    if (source !== record.body) throw new Error('RENDERED_TEXT_MISMATCH');
    const extras = await frame.evaluate(readArticleExtras);
    await this.check();
    const saved = await this.store.save(record, extras);
    // SQLite commit/readback precedes deletion of the extension's staging copy.
    await this.worker.evaluate(async id => {
      const keys = Object.keys(await chrome.storage.local.get(null)).filter(k => k.startsWith(`record:${id}:`) || k === `head:${id}`);
      await chrome.storage.local.remove(keys);
    }, target.document_id);
    await this.control.evaluate(() => chrome.runtime.sendMessage({type: 'STOP'}));
    return saved;
  }
  async close() {
    if (this.context) {
      await this.control?.evaluate(() => chrome.runtime.sendMessage({type: 'STOP'})).catch(() => {});
      await this.context.close(); this.context = null;
    }
  }
}
