import {test} from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {accessMonitor} from './access-monitor.mjs';

test('access monitor stops on HTTP denials and visible challenges, including iframe denials', async () => {
  const browser = await chromium.launch();
  try {
    for (const variant of ['403', '429', 'captcha', 'iframe-403', 'ordinary-article']) {
      const context = await browser.newContext();
      const monitor = accessMonitor(context);
      await context.route('https://blog.naver.com/**', async route => {
        const child = route.request().url().includes('PostView');
        const status = variant === '403' || variant === '429' ? Number(variant) : variant === 'iframe-403' && child ? 403 : 200;
        const body = variant === 'captcha' ? '<input name="captcha" aria-label="자동입력 방지문자">' :
          variant === 'iframe-403' && !child ? '<iframe src="/PostView.naver?blogId=fixture_author&logNo=1"></iframe>' :
          '<main class="se-main-container">합성 글: 비정상적인 접근이라는 문구를 설명하는 본문</main><input name="captcha" hidden>';
        await route.fulfill({status, contentType: 'text/html; charset=utf-8', body});
      });
      const page = await context.newPage();
      await page.goto('https://blog.naver.com/fixture_author/1');
      if (variant === 'ordinary-article') {
        await monitor.check(page);
        assert.equal(monitor.report().blocking_signal, null);
      } else {
        await assert.rejects(monitor.check(page), /ACCESS_HTTP_|VISIBLE_CAPTCHA/);
        assert(monitor.report().blocking_signal);
      }
      await context.close();
    }
  } finally { await browser.close(); }
});
