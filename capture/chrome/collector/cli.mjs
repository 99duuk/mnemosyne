import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {parseArgs} from 'node:util';
import {fileURLToPath} from 'node:url';
import {Store} from './store.mjs';
import {makePlan, selectDocuments, blogId} from './plan.mjs';
import {Browser} from './browser.mjs';

process.umask(0o077);
const {values: args, positionals} = parseArgs({allowPositionals: true, options: {
  blog: {type: 'string'}, dir: {type: 'string'}, plan: {type: 'string'}, include: {type: 'string'}, exclude: {type: 'string'},
  'max-pages': {type: 'string', default: '10'}, limit: {type: 'string', default: '50'}, interval: {type: 'string', default: '5000'},
  headless: {type: 'boolean'}, refresh: {type: 'boolean'}, 'retry-review': {type: 'boolean'}, 'load-media': {type: 'boolean'},
  file: {type: 'string'}, help: {type: 'boolean'},
}});
const command = positionals[0];
if (args.help || !command) {
  console.log(`Mnemosyne public-blog collector (Node 22.13+)
  node collector/cli.mjs categories --blog sofoswh
  node collector/cli.mjs plan --blog sofoswh [--include 1,71] [--exclude 14]
  node collector/cli.mjs discover --blog sofoswh [--include 1,71] [--exclude 14,22] [--max-pages 10|all]
  node collector/cli.mjs discover --plan /path/to/sofoswh-plan.json
  node collector/cli.mjs collect --blog sofoswh [--limit 50|all]
  node collector/cli.mjs status | export
  node collector/cli.mjs import --file /path/to/posts.jsonl
Options: --dir PATH, --headless, --interval MS (minimum 3000), --refresh, --retry-review, --load-media.
Default scope is every category, without date/post-count cutoff. Page/limit flags budget one run; rerun to resume.
discover --refresh starts fresh list snapshots. collect --refresh explicitly revisits stored posts.
Changing include/exclude requires completing exclusion lists before collect can start.
After an access stop, inspect the browser/site and run clear-stop manually; Retry-After must have elapsed.`);
  process.exit(0);
}
const budget = value => { if (value === 'all') return Infinity; if (!/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error('INVALID_BUDGET'); return Number(value); };
const dir = path.resolve(args.dir ?? path.join(os.homedir(), 'Library/Application Support/Mnemosyne/collection'));
await fs.mkdir(dir, {recursive: true, mode: 0o700});
const store = new Store(dir); let browser, lock;
const log = value => console.log(JSON.stringify(value));
async function acquire() {
  const filename = path.join(dir, 'collector.lock');
  try { lock = await fs.open(filename, 'wx', 0o600); }
  catch (e) {
    if (e.code !== 'EEXIST') throw e;
    const pid = Number(await fs.readFile(filename, 'utf8'));
    if (!Number.isInteger(pid) || pid < 1) throw new Error('INVALID_LOCK_REQUIRES_MANUAL_REVIEW');
    try { process.kill(pid, 0); throw new Error('COLLECTOR_ALREADY_RUNNING'); }
    catch (err) { if (err.code !== 'ESRCH') throw err; }
    await fs.unlink(filename); lock = await fs.open(filename, 'wx', 0o600);
  }
  await lock.writeFile(String(process.pid));
}
async function renderPlanner(blog, categories) {
  const snapshots = store.inventories(blog);
  const plan = store.get(`plan:${blog}`);
  const states = Object.fromEntries(store.db.prepare('SELECT document_id,status FROM documents WHERE blog=?').all(blog).map(d => [d.document_id, d.status]));
  let selection = null; try { selection = selectDocuments(plan, snapshots); } catch {}
  const selectionPath = path.join(dir, `${blog}-selection.jsonl`);
  if (selection) await fs.writeFile(selectionPath, selection.map(d => JSON.stringify({...d, status: states[d.document_id]})).join('\n') + (selection.length ? '\n' : ''), {mode: 0o600});
  else await fs.rm(selectionPath, {force: true});
  const quote = value => "'" + value.replaceAll("'", "'\\''") + "'";
  const data = {blog, categories, plan, snapshots, states, created_at: new Date().toISOString(), progress: Object.entries(snapshots).map(([id, s]) => ({name: categories.find(c => c.id === id)?.name ?? id, collected: s.documents.length, expected: s.expected_count, status: s.status})),
    command: `cd ${quote(fileURLToPath(new URL('..', import.meta.url)))}\nnode collector/cli.mjs discover --plan ~/Downloads/${blog}-plan.json --dir ${quote(dir)} --max-pages all\nnode collector/cli.mjs collect --plan ~/Downloads/${blog}-plan.json --dir ${quote(dir)} --limit 50`};
  const template = await fs.readFile(new URL('./planner.html', import.meta.url), 'utf8');
  const filename = path.join(dir, `${blog}-planner.html`);
  await fs.writeFile(filename, template.replace('__MNEMOSYNE_DATA__', JSON.stringify(data).replaceAll('<', '\\u003c')), {mode: 0o600});
  return filename;
}
try {
  if (!['categories', 'plan', 'discover', 'collect', 'status', 'export', 'import', 'clear-stop'].includes(command)) throw new Error('UNKNOWN_COMMAND');
  if (command === 'status') {
    log({dir, states: store.db.prepare('SELECT blog,status,count(*) AS count FROM documents GROUP BY blog,status').all(), stop: store.get('access_stop')});
  } else if (command === 'export') { await acquire(); log(store.export()); }
  else {
    await acquire();
    if (command === 'clear-stop') {
      const stop = store.get('access_stop');
      if (stop?.retry_not_before && Date.now() < Date.parse(stop.retry_not_before)) throw new Error('RETRY_AFTER_NOT_ELAPSED');
      store.set('access_stop', null); log({cleared: stop, note: 'No challenge was solved or bypassed. A new signal will stop the next run.'});
    } else if (command === 'import') {
      if (!args.file) throw new Error('FILE_REQUIRED');
      const lines = (await fs.readFile(args.file, 'utf8')).split(/\r?\n/).filter(line => line.trim());
      for (const line of lines) await store.save(JSON.parse(line));
      log({imported: lines.length, ...store.export()});
    } else {
      const config = args.plan ? JSON.parse(await fs.readFile(args.plan, 'utf8')) : null;
      const blog = blogId(args.blog ?? config?.blog);
      if (config && config.blog !== blog) throw new Error('PLAN_BLOG_MISMATCH');
      const interval = Number(args.interval);
      if (!Number.isInteger(interval) || interval < 3000 || interval > 60000) throw new Error('INTERVAL_MUST_BE_3000_TO_60000_MS');
      const maxPages = budget(args['max-pages']), limit = budget(args.limit);
      const options = {headless: args.headless, interval, loadMedia: args['load-media']};
      let categories = store.get(`categories:${blog}`);
      const ensureBrowser = async () => { if (!browser) { browser = new Browser(store, options); await browser.open(); } };
      if (command === 'categories' || !categories) {
        await ensureBrowser(); categories = await browser.categories(blog); store.set(`categories:${blog}`, categories);
        await fs.writeFile(path.join(dir, `${blog}-categories.json`), JSON.stringify(categories, null, 2), {mode: 0o600});
      }
      const split = s => s === undefined ? undefined : s.split(',').map(x => x.trim()).filter(Boolean);
      const savedPlan = store.get(`plan:${blog}`);
      const overrides = config || args.include !== undefined || args.exclude !== undefined;
      const plan = makePlan(blog, categories, overrides ? {include: split(args.include) ?? config?.include, exclude: split(args.exclude) ?? config?.exclude} : savedPlan ?? {});
      store.set(`plan:${blog}`, plan);
      await fs.writeFile(path.join(dir, `${blog}-plan.json`), JSON.stringify(plan, null, 2), {mode: 0o600});
      if (command === 'discover') {
        let remaining = maxPages;
        for (const id of [...new Set([...plan.exclude, ...plan.include])]) {
          if (remaining <= 0) break;
          if (!args.refresh && store.inventories(blog)[id]?.status === 'complete') continue;
          await ensureBrowser();
          const result = await browser.inventory(blog, categories.find(c => c.id === id), {maxPages: remaining, refresh: args.refresh, onPage: log});
          remaining -= result.pages;
        }
      } else if (command === 'collect') {
        const snapshots = store.inventories(blog);
        for (const id of plan.include) if (!snapshots[id]) throw new Error('RUN_DISCOVER_FIRST');
        const selection = selectDocuments(plan, snapshots);
        const targets = selection.filter(d => {
          const saved = store.document(d.document_id);
          return args.refresh || saved?.status === 'pending' || (args['retry-review'] && saved?.status === 'review');
        }).slice(0, limit);
        log({selected: selection.length, already_stored: selection.filter(d => store.document(d.document_id)?.status === 'stored').length, visits_scheduled: targets.length});
        let failures = 0;
        for (const target of targets) {
          await ensureBrowser();
          try {
            const record = await browser.capture(target); failures = 0;
            log({document_id: record.document_id, status: 'stored', characters: record.body.length, quality: record.quality_flags});
          } catch (e) {
            store.fail(target.document_id, e.message.split('\n')[0]); failures++;
            log({document_id: target.document_id, status: 'review', error: e.message.split('\n')[0]});
            if (browser.stopped || failures >= 3) throw e;
          }
        }
        log(store.export());
      }
      const snapshots = store.inventories(blog);
      let selected = null; try { selected = selectDocuments(plan, snapshots).length; } catch {}
      log({blog, plan: {include: plan.include, exclude: plan.exclude}, selected_documents: selected,
        planner: await renderPlanner(blog, categories), dir});
    }
  }
} catch (e) { log({result: 'ERROR', error: e.message.split('\n')[0], dir}); process.exitCode = 1; }
finally {
  try {
    if (browser) store.set('last_browser_run', {finished_at: new Date().toISOString(), http_status_counts: browser.responses, stop: browser.stopped});
    await browser?.close();
    // Export committed records even after a driver failure; the database remains canonical.
    if (['collect', 'import'].includes(command) && lock) store.export();
  } finally {
    store.close();
    if (lock) { await lock.close(); await fs.unlink(path.join(dir, 'collector.lock')); }
  }
}
