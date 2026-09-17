import {DatabaseSync} from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {identity, revisionOf} from '../extension/core.js';
import {absoluteDate} from './plan.mjs';

export const digest = value => createHash('sha256').update(value).digest('hex');
export function relativeDateRange(raw, observedAt) {
  const text = String(raw ?? '').trim();
  const observed = Date.parse(observedAt ?? '');
  if (!Number.isFinite(observed)) return null;
  const m = text.match(/^(\d+)\s*(분|시간|일)\s*전$/);
  if (!m) return null;
  const unit = {분: 60_000, 시간: 3_600_000, 일: 86_400_000}[m[2]];
  const age = Number(m[1]) * unit;
  return {lower: new Date(observed - (age + unit)).toISOString(), upper: new Date(observed - age).toISOString(), precision: `relative-${m[2]}`};
}
export class Store {
  constructor(dir) {
    fs.mkdirSync(dir, {recursive: true, mode: 0o700}); this.dir = dir;
    this.db = new DatabaseSync(path.join(dir, 'collection.sqlite'));
    fs.chmodSync(path.join(dir, 'collection.sqlite'), 0o600);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS inventories(blog TEXT, category TEXT, json TEXT NOT NULL, PRIMARY KEY(blog,category));
      CREATE TABLE IF NOT EXISTS inventory_history(blog TEXT, category TEXT, started_at TEXT, json TEXT NOT NULL, PRIMARY KEY(blog,category,started_at));
      CREATE TABLE IF NOT EXISTS documents(document_id TEXT PRIMARY KEY, blog TEXT NOT NULL, title TEXT NOT NULL,
        source_url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT, head TEXT, updated_at TEXT);
      CREATE TABLE IF NOT EXISTS records(document_id TEXT, content_hash TEXT, revision_id TEXT NOT NULL,
        json TEXT NOT NULL, html_gzip BLOB, html_sha256 TEXT, PRIMARY KEY(document_id,content_hash));
      CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY, document_id TEXT NOT NULL,
        observed_at TEXT NOT NULL, json TEXT NOT NULL);
      CREATE VIEW IF NOT EXISTS current_posts AS SELECT d.document_id,d.blog,d.title,d.status,d.source_url,
        json_extract(r.json,'$.published_at') AS published_at, json_extract(r.json,'$.published_at_lower_bound') AS published_at_lower_bound,
        json_extract(r.json,'$.published_at_upper_bound') AS published_at_upper_bound, json_extract(r.json,'$.category.name') AS category,
        json_extract(r.json,'$.body') AS body, json_extract(r.json,'$.quality_flags') AS quality_flags,
        r.revision_id,r.content_hash FROM documents d JOIN records r ON d.document_id=r.document_id AND d.head=r.content_hash;`);
  }
  close() { this.db.close(); }
  transaction(fn) { this.db.exec('BEGIN IMMEDIATE'); try { const result = fn(); this.db.exec('COMMIT'); return result; } catch (e) { this.db.exec('ROLLBACK'); throw e; } }
  get(key) { const row = this.db.prepare('SELECT json FROM settings WHERE key=?').get(key); return row ? JSON.parse(row.json) : null; }
  set(key, value) { this.db.prepare('INSERT OR REPLACE INTO settings VALUES (?,?)').run(key, JSON.stringify(value)); }
  inventories(blog) { return Object.fromEntries(this.db.prepare('SELECT category,json FROM inventories WHERE blog=?').all(blog).map(r => [r.category, JSON.parse(r.json)])); }
  inventory(blog, category, snapshot) {
    this.transaction(() => {
      const previous = this.db.prepare('SELECT json FROM inventories WHERE blog=? AND category=?').get(blog, category);
      if (previous && JSON.parse(previous.json).started_at !== snapshot.started_at) {
        this.db.prepare('INSERT OR IGNORE INTO inventory_history VALUES (?,?,?,?)').run(blog, category, JSON.parse(previous.json).started_at, previous.json);
      }
      this.db.prepare('INSERT OR REPLACE INTO inventories VALUES (?,?,?)').run(blog, category, JSON.stringify(snapshot));
      for (const doc of snapshot.documents) this.discover(doc);
    });
  }
  discover(doc) {
    const id = identity(doc.source_url);
    if (!id || id.key !== doc.document_id) throw new Error('INVALID_DOCUMENT_IDENTITY');
    this.db.prepare(`INSERT INTO documents(document_id,blog,title,source_url) VALUES (?,?,?,?)
      ON CONFLICT(document_id) DO NOTHING`).run(id.key, id.blog, doc.title, id.url);
  }
  document(id) { return this.db.prepare('SELECT * FROM documents WHERE document_id=?').get(id); }
  fail(id, code) { this.db.prepare("UPDATE documents SET status=CASE WHEN head IS NULL THEN 'review' ELSE status END,last_error=?,attempts=attempts+1 WHERE document_id=?").run(code, id); }
  async save(record, extra = null) {
    const id = identity(record.source_url);
    if (!id || id.key !== record.document_id || await revisionOf(record) !== record.revision_id) throw new Error('INVALID_RECORD_HASH_OR_ID');
    const {article_html = null, ...metadata} = extra ?? {};
    const normalized = record.body.replace(/\u200b/g, '').replace(/\r\n/g, '\n').trim();
    const flags = [...record.warnings];
    if (normalized.length < 100) flags.push('SHORT_TEXT_REVIEW');
    if (!extra) flags.push('LEGACY_TEXT_ONLY');
    if (!metadata.category) flags.push('CATEGORY_UNKNOWN');
    const published = absoluteDate(record.published_at_raw);
    const relative = published.value ? null : relativeDateRange(record.published_at_raw, record.captured_at);
    if (!published.value) flags.push(relative ? 'DATE_RELATIVE_RANGE' : 'DATE_UNRESOLVED');
    const contentHash = digest(JSON.stringify([record.title, normalized, metadata.blocks ?? null, metadata.links ?? null]));
    const previousHash = this.document(id.key)?.head ?? null;
    const htmlHash = article_html === null ? null : digest(article_html);
    const saved = {...record, ...metadata, normalized_body: normalized, published_at: published.value,
      published_at_precision: published.value ? published.precision : relative?.precision ?? 'unknown',
      published_at_lower_bound: published.value ? published.value : relative?.lower ?? null,
      published_at_upper_bound: published.value ? published.value : relative?.upper ?? null,
      content_hash: contentHash, article_html_sha256: htmlHash,
      quality_flags: [...new Set(flags)], quality_status: flags.length ? 'review' : 'ok',
      supersedes_content_hash: previousHash !== contentHash ? previousHash : null,
      rights_review_status: 'UNREVIEWED', rag_eligible: false,
      archive_schema: 'mnemosyne.collection/v1'};
    this.transaction(() => {
      this.discover(record);
      this.db.prepare(`INSERT INTO records(document_id,content_hash,revision_id,json,html_gzip,html_sha256) VALUES (?,?,?,?,?,?)
        ON CONFLICT(document_id,content_hash) DO UPDATE SET revision_id=excluded.revision_id,
        json=excluded.json, html_gzip=COALESCE(excluded.html_gzip,records.html_gzip), html_sha256=COALESCE(excluded.html_sha256,records.html_sha256)`).run(id.key, contentHash, record.revision_id,
        JSON.stringify(saved), article_html === null ? null : gzipSync(article_html), htmlHash);
      this.db.prepare("UPDATE documents SET head=?,status='stored',title=?,last_error=NULL,updated_at=? WHERE document_id=?")
        .run(contentHash, record.title, new Date().toISOString(), id.key);
      this.db.prepare('INSERT INTO observations(document_id,observed_at,json) VALUES (?,?,?)')
        .run(id.key, record.captured_at, JSON.stringify({published_at_raw: record.published_at_raw, revision_id: record.revision_id, content_hash: contentHash,
          category: metadata.category ?? null, quality_flags: saved.quality_flags, html_sha256: htmlHash}));
    });
    const checked = this.db.prepare('SELECT json FROM records WHERE document_id=? AND content_hash=?').get(id.key, contentHash);
    if (!checked || await revisionOf(JSON.parse(checked.json)) !== JSON.parse(checked.json).revision_id) throw new Error('DATABASE_READBACK_FAILED');
    return saved;
  }
  export() {
    const rows = this.db.prepare('SELECT r.json FROM documents d JOIN records r ON d.document_id=r.document_id AND d.head=r.content_hash ORDER BY d.document_id DESC').all();
    const filename = path.join(this.dir, 'posts.jsonl');
    fs.writeFileSync(`${filename}.tmp`, rows.map(r => r.json).join('\n') + (rows.length ? '\n' : ''), {mode: 0o600});
    fs.renameSync(`${filename}.tmp`, filename); return {documents: rows.length, file: filename};
  }
}
