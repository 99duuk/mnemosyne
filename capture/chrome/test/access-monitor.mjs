// Observation and stop conditions only. No retries or challenge solving.
export function accessMonitor(context) {
  const documents = [];
  let blocked = null;
  context.on('response', response => {
    if (!response.request().isNavigationRequest()) return;
    const u = new URL(response.url());
    if (u.origin !== 'https://blog.naver.com') return;
    const status = response.status();
    documents.push({path: u.pathname, status});
    if ([401, 403, 429].includes(status)) blocked = `ACCESS_HTTP_${status}`;
  });
  return {
    async check(page) {
      if (blocked) throw new Error(blocked);
      for (const frame of page.frames()) {
        if (!frame.url().startsWith('https://blog.naver.com/')) continue;
        const signal = await frame.evaluate(() => {
          const visible = el => Boolean(el.getClientRects().length) && getComputedStyle(el).visibility !== 'hidden';
          const captcha = [...document.querySelectorAll('input[name*="captcha" i],input[id*="captcha" i],iframe[src*="captcha" i]')].some(visible);
          if (captcha) return 'VISIBLE_CAPTCHA';
          // Do not mistake a quoted article discussing access blocks for a block page.
          if (!document.querySelector('.se-main-container')) {
            const text = document.body?.innerText ?? '';
            if (/비정상적인 접근|접근이 제한|잠시 후 다시 이용|자동입력 방지문자/.test(text)) return 'ACCESS_NOTICE';
          }
          return null;
        }).catch(() => 'INSPECTION_FAILED');
        if (signal) { blocked = signal; throw new Error(signal); }
      }
    },
    report() { return {document_responses: [...documents], blocking_signal: blocked,
      detection_scope: 'document HTTP 401/403/429, visible CAPTCHA input/frame, selected access notices; not exhaustive'}; },
  };
}
