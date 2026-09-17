(() => {
  if (globalThis.__mnemosyneCaptureTest) return;
  globalThis.__mnemosyneCaptureTest = true;
  const documentUrl = location.href;
  let previous = '', stableSince = 0, startedAt = 0, inFlight = false, finished = false;
  let sessionId = null;
  const badge = document.createElement('div');
  badge.id = 'mnemosyne-capture-status';
  badge.setAttribute('role', 'status');
  Object.assign(badge.style, {position: 'fixed', right: '14px', bottom: '14px', zIndex: '2147483647',
    background: '#102b21', color: '#fff', padding: '10px 14px', borderRadius: '8px', font: '13px sans-serif'});
  function show(status, detail = '') {
    badge.textContent = `Mnemosyne · ${status}${detail ? ` · ${detail}` : ''}`;
    badge.dataset.status = status;
    if (!badge.isConnected) document.documentElement.append(badge);
  }
  function extract() {
    const roots = document.querySelectorAll('.se-main-container');
    if (roots.length !== 1) return null;
    const titles = document.querySelectorAll('.se-title-text');
    const dates = document.querySelectorAll('.se_publishDate');
    if (titles.length !== 1 || dates.length !== 1) return null;
    const root = roots[0];
    const paragraphs = [...root.querySelectorAll('.se-text-paragraph')].filter(p => {
      const container = p.closest('table,iframe,object,embed');
      return !container || !root.contains(container);
    });
    const body = paragraphs.map(p => p.innerText ?? p.textContent).join('\n\n').trim();
    const warnings = [];
    if (root.querySelector('img')) warnings.push('IMAGES_OMITTED');
    if (root.querySelector('table')) warnings.push('TABLES_OMITTED');
    if (root.querySelector('iframe,object,embed,video,audio')) warnings.push('MEDIA_OMITTED');
    if (root.querySelector('.se-quotation-container')) warnings.push('QUOTATIONS_REQUIRE_REVIEW');
    const title = titles[0].textContent.trim();
    const date = dates[0].textContent.trim();
    if (!title || !date || body.length < 20) return null;
    return {source_url: documentUrl, title, published_at_raw: date, body, warnings};
  }
  async function tick() {
    if (inFlight || finished) return;
    inFlight = true;
    try {
      if (location.href !== documentUrl) { finished = true; return; }
      const hello = await chrome.runtime.sendMessage({type: 'HELLO'});
      if (!hello?.armed) return;
      if (sessionId !== hello.sessionId) {
        sessionId = hello.sessionId; startedAt = Date.now(); previous = ''; stableSince = 0;
      }
      const payload = extract();
      if (!payload) {
        // Naver's outer page is a layout wrapper; its mainFrame owns the article.
        if (document.querySelector('iframe#mainFrame')) return;
        show('WAITING', '본문 확인 중');
        if (Date.now() - startedAt > 20_000) { show('ERROR', '본문·제목·날짜 확인 실패'); finished = true; }
        return;
      }
      const signature = JSON.stringify(payload);
      if (signature !== previous) { previous = signature; stableSince = Date.now(); return; }
      if (Date.now() - stableSince < 1200) return;
      show('SAVING');
      const receipt = await chrome.runtime.sendMessage({type: 'CAPTURE', sessionId,
        requestId: crypto.randomUUID(), payload});
      finished = true;
      show(receipt.status, receipt.error ?? `${receipt.body_length}자`);
      badge.dataset.documentId = receipt.document_id ?? '';
      badge.dataset.revisionId = receipt.revision_id ?? '';
    } catch {
      show('ERROR', '확장 프로그램 연결 실패'); finished = true;
    } finally { inFlight = false; if (finished) clearInterval(timer); }
  }
  const timer = setInterval(tick, 500);
  tick();
})();
