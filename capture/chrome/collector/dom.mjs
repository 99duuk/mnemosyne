// These functions run in the page's read-only DOM context. No page scripts/API calls.
export function readCategories() {
  return [...document.querySelectorAll('a[id^="category"]')].filter(a => /^category\d+$/.test(a.id)).map(a => {
    const li = a.closest('li');
    const count = (a.parentElement.querySelector('.num')?.textContent ?? '').replace(/[^0-9]/g, '');
    return {id: a.id.slice(8), name: a.textContent.replace(/\s+/g, ' ').trim(),
      parent_id: li?.className.match(/parentcategoryno_(\d+)/)?.[1] ?? (a.id === 'category0' ? null : '0'),
      count: count ? Number(count) : null, url: a.href.trim()};
  });
}

export function readList() {
  const rows = [...document.querySelectorAll('table.blog2_categorylist a._setTopListUrl')].map(a => ({
    url: a.href, title: a.textContent.trim(), published_at_raw: a.closest('tr')?.querySelector('td.date')?.textContent.trim() ?? '',
  }));
  const current = document.querySelector('.blog2_paginate strong._goPageTop')?.className.match(/_param\((\d+)\)/)?.[1];
  const pages = [...document.querySelectorAll('.blog2_paginate a._goPageTop')].map(a => Number(a.className.match(/_param\((\d+)\)/)?.[1])).filter(Number.isFinite);
  const count = document.querySelector('h4.category_title')?.textContent.match(/([\d,]+)개의 글/)?.[1];
  return {rows, current_page: current ? Number(current) : 1, pages, expected_count: count === undefined ? null : Number(count.replaceAll(',', '')),
    page_size: Number(document.querySelector('#listCountView')?.textContent.match(/\d+/)?.[0] ?? 5)};
}

export function readArticleExtras() {
  const root = document.querySelector('.se-main-container');
  if (!root || document.querySelectorAll('.se-main-container').length !== 1) throw new Error('UNSUPPORTED_ARTICLE_LAYOUT');
  const text = el => (el.innerText ?? el.textContent ?? '').trim();
  const safeURL = raw => { try { const u = new URL(raw, location.href); return /^https?:$/.test(u.protocol) ? u.href : null; } catch { return null; } };
  const blocks = [...root.querySelectorAll('.se-text-paragraph,table,img,iframe,video,audio')].filter(el => {
    const table = el.parentElement?.closest('table'); return !table || !root.contains(table);
  }).map((el, index) => {
    if (el.tagName === 'TABLE') return {index, type: 'table', rows: [...el.rows].map(r => [...r.cells].map(text))};
    if (el.tagName === 'IMG') return {index, type: 'image', url: safeURL(el.getAttribute('data-lazy-src') || el.getAttribute('data-src') || el.getAttribute('src')),
      alt: el.getAttribute('alt') ?? '', caption: el.closest('.se-component')?.querySelector('.se-caption')?.textContent.trim() ?? ''};
    if (['IFRAME', 'VIDEO', 'AUDIO'].includes(el.tagName)) return {index, type: 'media', url: safeURL(el.getAttribute('src')), media_type: el.tagName.toLowerCase()};
    return {index, type: el.closest('.se-quotation-container,.se-quotation') ? 'quote' : el.closest('.se-caption') ? 'caption' : 'paragraph', text: text(el)};
  });
  const links = [...root.querySelectorAll('a[href]')].map(a => ({text: text(a), url: safeURL(a.getAttribute('href'))})).filter(a => a.url);
  const category = [...document.querySelectorAll('a[href*="PostList.naver"]')].find(a => /pst\.category/.test(a.getAttribute('onclick') ?? ''));
  const categoryURL = category ? new URL(category.href) : null;
  const copy = root.cloneNode(true);
  copy.querySelectorAll('script,style,iframe,object,embed').forEach(el => el.remove());
  for (const el of [copy, ...copy.querySelectorAll('*')]) for (const attr of [...el.attributes]) {
    if (/^on/i.test(attr.name) || ['srcdoc', 'nonce'].includes(attr.name)) el.removeAttribute(attr.name);
  }
  return {extractor_version: 'naver-smarteditor-dom/1', blocks, links,
    category: category ? {id: categoryURL.searchParams.get('categoryNo'), name: text(category)} : null,
    author_display_name: document.querySelector('.nick a,.nick')?.textContent.trim() ?? null,
    tags: [...document.querySelectorAll('.blog_tag .item')].map(text),
    article_html: copy.outerHTML,
    html_scope: 'article DOM fragment; scripts, event handlers and embedded documents removed; never render as trusted HTML'};
}
