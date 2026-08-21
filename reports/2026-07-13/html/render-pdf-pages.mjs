import fs from "node:fs";
import path from "node:path";
import { createCanvas, loadImage, DOMMatrix, ImageData, Path2D } from "@napi-rs/canvas";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";

globalThis.DOMMatrix = DOMMatrix;
globalThis.ImageData = ImageData;
globalThis.Path2D = Path2D;

const root = path.resolve(import.meta.dirname, "../..");
const pdfPath = path.join(root, "output/pdf/naver-blog-persona-research.pdf");
const outputDir = path.join(root, ".omo/evidence/naver-persona-report/pdf-pages");
const evidenceRoot = path.dirname(outputDir);
const tempOutputDir = path.join(evidenceRoot, `.pdf-pages.${process.pid}.${Date.now()}.tmp`);
const backupDir = path.join(evidenceRoot, `.pdf-pages.${process.pid}.backup`);
const lockPath = path.join(evidenceRoot, ".pdf-pages.lock");

if (!fs.existsSync(pdfPath) || fs.statSync(pdfPath).size === 0) throw new Error(`Missing or empty PDF: ${pdfPath}`);
fs.mkdirSync(evidenceRoot, { recursive: true });
let lockHandle;
try {
  lockHandle = fs.openSync(lockPath, "wx");
} catch (error) {
  throw new Error(`Another PDF evidence render is active (${lockPath})`, { cause: error });
}
let document;
try {
  fs.mkdirSync(tempOutputDir, { recursive: true });
  const data = new Uint8Array(fs.readFileSync(pdfPath));
  const loadingTask = pdfjs.getDocument({ data, useSystemFonts: true });
  document = await loadingTask.promise;
  if (document.numPages !== 17) throw new Error(`Expected 17 PDF pages, received ${document.numPages}`);
  const pagePaths = [];
  const pageTexts = [];

  for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
    const page = await document.getPage(pageNumber);
    const viewport = page.getViewport({ scale: 1.45 });
    const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    await page.render({ canvasContext: context, viewport }).promise;
    const pageFilename = `page-${String(pageNumber).padStart(2, "0")}.png`;
    const pagePath = path.join(tempOutputDir, pageFilename);
    fs.writeFileSync(pagePath, canvas.toBuffer("image/png"));
    pagePaths.push(path.join(outputDir, pageFilename));

    const textContent = await page.getTextContent();
    const text = textContent.items.map((item) => item.str).join(" ");
    pageTexts.push(`\n--- PAGE ${pageNumber} ---\n${text}`);
  }

  const extractedText = `${pageTexts.join("\n")}\n`;
  const requiredMarkers = ["대상이 본인이거나", "target corpus에서 비교", "생성 정책", "prompt -> response", "위협 모델", "평가 하네스", "삭제 saga", "운영·사고 대응", "Naver Blog robots"];
  const missingMarkers = requiredMarkers.filter((marker) => !extractedText.includes(marker));
  if (extractedText.includes("\0") || extractedText.includes("□") || missingMarkers.length > 0) {
    throw new Error(`PDF text verification failed: missing=${missingMarkers.join(",") || "none"}, nul=${extractedText.includes("\0")}, tofu=${extractedText.includes("□")}`);
  }
  fs.writeFileSync(path.join(tempOutputDir, "extracted-text.txt"), extractedText);

  const columns = 4;
  const thumbWidth = 210;
  const thumbHeight = 297;
  const gap = 16;
  const labelHeight = 24;
  const rows = Math.ceil(pagePaths.length / columns);
  const sheet = createCanvas(columns * thumbWidth + (columns + 1) * gap, rows * (thumbHeight + labelHeight) + (rows + 1) * gap);
  const sheetContext = sheet.getContext("2d");
  sheetContext.fillStyle = "#d8d4cc";
  sheetContext.fillRect(0, 0, sheet.width, sheet.height);
  sheetContext.font = "14px sans-serif";
  sheetContext.textAlign = "center";

  for (let index = 0; index < pagePaths.length; index += 1) {
    const image = await loadImage(path.join(tempOutputDir, path.basename(pagePaths[index])));
    const column = index % columns;
    const row = Math.floor(index / columns);
    const x = gap + column * (thumbWidth + gap);
    const y = gap + row * (thumbHeight + labelHeight + gap);
    sheetContext.fillStyle = "#ffffff";
    sheetContext.fillRect(x, y, thumbWidth, thumbHeight);
    sheetContext.drawImage(image, x, y, thumbWidth, thumbHeight);
    sheetContext.fillStyle = "#242321";
    sheetContext.fillText(`Page ${index + 1}`, x + thumbWidth / 2, y + thumbHeight + 18);
  }

  const contactSheetPath = path.join(outputDir, "contact-sheet.png");
  fs.writeFileSync(path.join(tempOutputDir, "contact-sheet.png"), sheet.toBuffer("image/png"));
  const manifest = { pdfPath, pageCount: document.numPages, pagePaths, contactSheetPath };
  fs.writeFileSync(path.join(tempOutputDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);

  if (fs.existsSync(outputDir)) fs.renameSync(outputDir, backupDir);
  fs.renameSync(tempOutputDir, outputDir);
  fs.rmSync(backupDir, { recursive: true, force: true });
  console.log(JSON.stringify(manifest, null, 2));
} catch (error) {
  if (!fs.existsSync(outputDir) && fs.existsSync(backupDir)) fs.renameSync(backupDir, outputDir);
  throw error;
} finally {
  if (document) await document.destroy();
  fs.rmSync(tempOutputDir, { recursive: true, force: true });
  fs.rmSync(backupDir, { recursive: true, force: true });
  if (lockHandle !== undefined) fs.closeSync(lockHandle);
  fs.rmSync(lockPath, { force: true });
}
