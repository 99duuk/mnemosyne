import {identity, revisionOf, validateCapture} from './core.js';

// Keep raw records readable by extension pages/service worker only.
const ready = Promise.all([
  chrome.storage.local.setAccessLevel({accessLevel: 'TRUSTED_CONTEXTS'}),
  chrome.storage.session.setAccessLevel({accessLevel: 'TRUSTED_CONTEXTS'}),
]);
let queue = Promise.resolve();
const ownPage = sender => sender.id === chrome.runtime.id && sender.url?.startsWith(chrome.runtime.getURL(''));

async function handle(message, sender) {
  await ready;
  if (message.type === 'ARM') {
    if (!ownPage(sender)) throw new Error('UNTRUSTED_CONTROL');
    const tab = await chrome.tabs.get(message.tabId);
    const source = identity(tab.url);
    if (!source || source.blog !== message.blog) throw new Error('OPEN_A_POST_FIRST');
    const requestedLimit = Number.isInteger(message.limit) ? message.limit : 2;
    if (requestedLimit < 1 || requestedLimit > 50) throw new Error('INVALID_LIMIT');
    const session = {enabled: true, id: crypto.randomUUID(), tabId: tab.id, blog: source.blog,
      expiresAt: Date.now() + 30 * 60_000, documents: [], limit: requestedLimit};
    await chrome.storage.session.set({session});
    await chrome.storage.local.remove('lastReceipt');
    return {status: 'ARMED', session};
  }
  if (message.type === 'STOP') {
    if (!ownPage(sender)) throw new Error('UNTRUSTED_CONTROL');
    await chrome.storage.session.remove('session');
    return {status: 'STOPPED'};
  }
  const {session} = await chrome.storage.session.get('session');
  if (message.type === 'STATUS') {
    if (!ownPage(sender)) throw new Error('UNTRUSTED_CONTROL');
    const {lastReceipt} = await chrome.storage.local.get('lastReceipt');
    return {session: session ?? null, lastReceipt: lastReceipt ?? null};
  }
  if (message.type === 'HELLO') {
    const top = identity(sender.tab?.url);
    const frame = identity(sender.url);
    const armed = Boolean(session?.enabled && session.tabId === sender.tab?.id && Date.now() < session.expiresAt
      && top && frame && top.key === frame.key && top.blog === session.blog);
    return {armed, sessionId: armed ? session.id : null};
  }
  if (message.type !== 'CAPTURE') throw new Error('UNKNOWN_MESSAGE');
  if (message.sessionId !== session?.id) throw new Error('STALE_SESSION');
  // A frame from the old navigation must not acknowledge a newly opened post.
  const currentTab = await chrome.tabs.get(sender.tab.id);
  if (identity(currentTab.url)?.key !== identity(sender.tab.url)?.key) throw new Error('STALE_DOCUMENT');
  const source = validateCapture(message.payload, sender, session);
  const revision = await revisionOf(message.payload);
  const key = `record:${source.key}:${revision}`;
  const existing = (await chrome.storage.local.get(key))[key];
  const newDocument = !session.documents.includes(source.key);
  if (newDocument && session.documents.length >= session.limit) throw new Error('LIMIT_REACHED');
  const capturedAt = new Date().toISOString();
  if (!existing) {
    const previous = (await chrome.storage.local.get(`head:${source.key}`))[`head:${source.key}`] ?? null;
    const record = {schema: 'mnemosyne.chrome-test/v1', document_id: source.key, revision_id: revision,
      supersedes_revision_id: previous, source_url: source.url, observed_url: sender.tab.url,
      content_url: sender.url, title: message.payload.title, published_at_raw: message.payload.published_at_raw,
      published_at: null, captured_at: capturedAt, body: message.payload.body,
      warnings: message.payload.warnings, rights_review_status: 'UNREVIEWED', rag_eligible: false,
      capture_method: 'chrome_extension_public_test'};
    await chrome.storage.local.set({[key]: record, [`head:${source.key}`]: revision});
  }
  // Read back and check the content hash before acknowledging durable storage.
  const saved = (await chrome.storage.local.get(key))[key];
  if (!saved || await revisionOf(saved) !== revision) throw new Error('WRITE_VERIFICATION_FAILED');
  if (newDocument) session.documents.push(source.key);
  await chrome.storage.session.set({session});
  const receipt = {status: existing ? 'DUPLICATE' : 'SAVED', session_id: session.id,
    request_id: message.requestId, document_id: source.key, revision_id: revision,
    body_length: saved.body.length, completed_at: new Date().toISOString()};
  await chrome.storage.local.set({lastReceipt: receipt});
  await chrome.action.setBadgeText({tabId: sender.tab.id, text: existing ? 'DUP' : 'OK'});
  return receipt;
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  const job = queue.then(() => handle(message, sender));
  queue = job.catch(() => {});
  job.then(respond, error => respond({status: 'ERROR', error: error.message}));
  return true;
});
