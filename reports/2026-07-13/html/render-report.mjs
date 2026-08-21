import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(import.meta.dirname, "../..");
const reportPath = path.join(import.meta.dirname, "REPORT.html");
const evidenceDir = path.join(root, ".omo/evidence/naver-persona-report/html");
const pdfDir = path.join(root, "output/pdf");
const pdfPath = path.join(pdfDir, "naver-blog-persona-research.pdf");
const pdfTempPath = path.join(pdfDir, `.naver-blog-persona-research.${process.pid}.${Date.now()}.tmp.pdf`);
const evidencePath = path.join(evidenceDir, "render-evidence.json");
const evidenceTempPath = `${evidencePath}.${process.pid}.tmp`;
const lockPath = path.join(import.meta.dirname, ".render-report.lock");
const executablePath = process.env.REPORT_CHROME_PATH || chromium.executablePath();

if (!fs.existsSync(reportPath)) throw new Error(`Missing report input: ${reportPath}`);
if (!fs.existsSync(executablePath)) throw new Error(`Missing browser executable: ${executablePath}. Run 'npx playwright install chromium' or set REPORT_CHROME_PATH.`);

fs.mkdirSync(evidenceDir, { recursive: true });
fs.mkdirSync(pdfDir, { recursive: true });

let lockHandle;
try {
  lockHandle = fs.openSync(lockPath, "wx");
} catch (error) {
  throw new Error(`Another report render is active (${lockPath})`, { cause: error });
}

let browser;
const results = [];
const consoleErrors = [];
try {
  browser = await chromium.launch({ executablePath, headless: true });
  const browserVersion = browser.version();
  for (const width of [375, 768, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push({ width, type: "console", text: message.text() });
    });
    page.on("pageerror", (error) => consoleErrors.push({ width, type: "pageerror", text: error.message }));
    await page.goto(pathToFileURL(reportPath).href, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    const metrics = await page.evaluate(() => ({
      title: document.title,
      lang: document.documentElement.lang,
      headings: document.querySelectorAll("h2, h3").length,
      sourceAnchors: document.querySelectorAll('[id^="source-"]').length,
      citationLinks: document.querySelectorAll('a[href^="#source-"]').length,
      tables: document.querySelectorAll("table").length,
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
      reportFontLoaded: document.fonts.check('16px "Report Noto Sans KR"'),
      preFontFamily: getComputedStyle(document.querySelector("pre")).fontFamily,
    }));
    await page.screenshot({ path: path.join(evidenceDir, `report-${width}.png`), fullPage: true });
    await page.locator('a[href="#source-1"]').first().click();
    const anchorVisible = await page.locator("#source-1").isVisible();
    const hash = await page.evaluate(() => location.hash);
    results.push({ width, ...metrics, horizontalOverflow: metrics.scrollWidth > metrics.clientWidth, anchorVisible, hash });
    await context.close();
  }

  const zoomContext = await browser.newContext({ viewport: { width: 768, height: 900 }, deviceScaleFactor: 1 });
  const zoomPage = await zoomContext.newPage();
  await zoomPage.goto(pathToFileURL(reportPath).href, { waitUntil: "load" });
  await zoomPage.evaluate(() => document.fonts.ready);
  await zoomPage.addStyleTag({ content: "html { font-size: 200% !important; }" });
  const zoomMetrics = await zoomPage.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  await zoomPage.screenshot({ path: path.join(evidenceDir, "report-text-zoom-200.png"), fullPage: true });
  await zoomContext.close();

  const failures = [];
  for (const result of results) {
    if (result.horizontalOverflow) failures.push(`${result.width}px horizontal overflow`);
    if (!result.reportFontLoaded) failures.push(`${result.width}px report font missing`);
    if (!result.anchorVisible || result.hash !== "#source-1") failures.push(`${result.width}px source anchor failed`);
    if (result.headings !== 40 || result.sourceAnchors !== 38 || result.citationLinks !== 49 || result.tables !== 3) failures.push(`${result.width}px structure counts changed`);
  }
  if (zoomMetrics.horizontalOverflow) failures.push("200% text zoom horizontal overflow");
  if (consoleErrors.length > 0) failures.push(`${consoleErrors.length} browser console/page errors`);
  if (failures.length > 0) throw new Error(`Browser verification failed: ${failures.join("; ")}`);

  const pdfContext = await browser.newContext();
  const pdfPage = await pdfContext.newPage();
  await pdfPage.goto(pathToFileURL(reportPath).href, { waitUntil: "load" });
  await pdfPage.evaluate(() => document.fonts.ready);
  await pdfPage.pdf({ path: pdfTempPath, format: "A4", printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false });
  await pdfContext.close();
  fs.renameSync(pdfTempPath, pdfPath);

  const evidence = { generatedAt: new Date().toISOString(), executablePath, browserVersion, results, zoom200: zoomMetrics, consoleErrors, pdfPath };
  fs.writeFileSync(evidenceTempPath, `${JSON.stringify(evidence, null, 2)}\n`);
  fs.renameSync(evidenceTempPath, evidencePath);
  console.log(JSON.stringify(evidence, null, 2));
} finally {
  if (browser) await browser.close();
  if (fs.existsSync(pdfTempPath)) fs.rmSync(pdfTempPath, { force: true });
  if (fs.existsSync(evidenceTempPath)) fs.rmSync(evidenceTempPath, { force: true });
  if (lockHandle !== undefined) fs.closeSync(lockHandle);
  fs.rmSync(lockPath, { force: true });
}
