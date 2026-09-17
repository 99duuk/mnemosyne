export function identity(raw) {
  try {
    const u = new URL(raw);
    if (u.origin !== 'https://blog.naver.com' || u.username || u.password) return null;
    const direct = /^\/([A-Za-z0-9_-]{1,64})\/([1-9][0-9]{0,19})\/?$/.exec(u.pathname);
    let blog, post;
    if (direct) [, blog, post] = direct;
    else if (u.pathname === '/PostView.naver') {
      if (u.searchParams.getAll('blogId').length !== 1 || u.searchParams.getAll('logNo').length !== 1) return null;
      blog = u.searchParams.get('blogId'); post = u.searchParams.get('logNo');
    }
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(blog ?? '') || !/^[1-9][0-9]{0,19}$/.test(post ?? '')) return null;
    return {blog, post, key: `${blog}:${post}`, url: `https://blog.naver.com/${blog}/${post}`};
  } catch { return null; }
}

export async function revisionOf(payload) {
  const bytes = new TextEncoder().encode(JSON.stringify([payload.title, payload.published_at_raw, payload.body]));
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2, '0')).join('');
}

export function validateCapture(payload, sender, session) {
  if (!session?.enabled || sender.tab?.id !== session.tabId) throw new Error('NOT_ARMED');
  if (Date.now() > session.expiresAt) throw new Error('SESSION_EXPIRED');
  const page = identity(sender.tab.url);
  const frame = identity(sender.url);
  const source = identity(payload?.source_url);
  if (!page || !frame || !source || page.key !== frame.key || frame.key !== source.key || source.blog !== session.blog) {
    throw new Error('DOCUMENT_MISMATCH');
  }
  for (const [key, max] of [['title', 2000], ['published_at_raw', 256], ['body', 2_000_000]]) {
    if (typeof payload[key] !== 'string' || !payload[key].trim() || payload[key].length > max) throw new Error('INVALID_PAYLOAD');
  }
  if (!Array.isArray(payload.warnings) || payload.warnings.some(x => typeof x !== 'string' || x.length > 80)) throw new Error('INVALID_PAYLOAD');
  if (payload.body.length < 20) throw new Error('INCOMPLETE_BODY');
  return source;
}
