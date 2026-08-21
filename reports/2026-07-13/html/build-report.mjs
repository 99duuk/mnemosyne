import fs from "node:fs";
import path from "node:path";
import { marked } from "marked";

const root = path.resolve(import.meta.dirname, "../..");

const synthesisPath = path.join(root, ".omo/ulw-research/20260713-071314/SYNTHESIS.md");
const cssPath = path.join(import.meta.dirname, "report.css");
const outputPath = path.join(import.meta.dirname, "REPORT.html");

const source = fs.readFileSync(synthesisPath, "utf8");
const css = fs.readFileSync(cssPath, "utf8");
const bodySource = source
  .replace(/^# .+\n\n/, "")
  .replace(/^연구 기준일:.+\n결론 수준:.+\n\n/, "")
  .replace(/\[Source (\d+)\]/g, "[Source $1](#source-$1)");

const headingIds = new Map([
  ["TL;DR", "tldr"],
  ["문제 원인 분석", "problem-analysis"],
  ["정확한 해결책", "solution"],
  ["확장 가능한 대안 제시", "alternatives"],
  ["단계별 실행안", "roadmap"],
  ["주의 사항 또는 리스크", "risks"],
  ["검증된 결론과 아직 잠정인 결론", "confidence"],
  ["Sources", "sources"],
]);

let body = marked.parse(bodySource, { gfm: true });
body = body.replace(/<h2>(.*?)<\/h2>/g, (match, label) => {
  const id = headingIds.get(label);
  return id ? `<h2 id="${id}">${label}</h2>` : match;
});
const tableLabels = ["접근·권리 게이트", "위협 예방·탐지·복구", "평가 하네스 배포 게이트"];
let tableNumber = 0;
body = body.replace(/<table>/g, () => {
  const label = tableLabels[tableNumber];
  if (!label) throw new Error(`Unexpected table at index ${tableNumber}`);
  tableNumber += 1;
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${label}"><table><caption>${label}</caption>`;
});
body = body.replace(/<\/table>/g, "</table></div>");
body = body.replace(/<pre>/g, '<pre tabindex="0">');
body = body.replace(/(<code>.*?<\/code>)([은는이가을를과와으로에서의도만])/g, '$1&#8288;$2');
body = body.replace(/<code>prompt -&gt; response<\/code>/g, '<code class="nowrap">prompt -&gt; response</code>');
body = body.replace(
  /<code>COMPLETE_RELATIVE_TO_OWNER_DECLARED_SCOPE_AT_CUTOFF<\/code>/g,
  '<code class="breakable-id"><span>COMPLETE_</span><wbr><span>RELATIVE_</span><wbr><span>TO_</span><wbr><span>OWNER_</span><wbr><span>DECLARED_</span><wbr><span>SCOPE_</span><wbr><span>AT_</span><wbr><span>CUTOFF</span></code>',
);
body = body.replace(/canonical input으로 한다\./g, 'canonical <span class="nowrap">input으로 한다.</span>');
body = body.replace(/cryptographically inaccessible이어야 한다\./g, 'cryptographically <span class="nowrap">inaccessible이어야 한다.</span>');
body = body.replace('<ul>\n<li>RAG의 retrieval, citation, privacy, identity, deletion gate가 먼저 통과한다.</li>', '<ul class="tuning-conditions">\n<li>RAG의 retrieval, citation, privacy, identity, deletion gate가 먼저 통과한다.</li>');

const sourceIndex = body.indexOf('<h2 id="sources">');
let sourceNumber = 0;
if (sourceIndex >= 0) {
  const beforeSources = body.slice(0, sourceIndex);
  let sources = body.slice(sourceIndex);
  sources = sources.replace(/<li>/g, () => {
    sourceNumber += 1;
    return `<li id="source-${sourceNumber}">`;
  });
  body = beforeSources + sources;
}

const headingCount = [...headingIds.values()].filter((id) => body.includes(`id="${id}"`)).length;
const citationCount = (body.match(/href="#source-\d+"/g) ?? []).length;
const tuningConditionListCount = (body.match(/class="tuning-conditions"/g) ?? []).length;
const breakableIdentifierCount = (body.match(/class="breakable-id"/g) ?? []).length;
if (headingCount !== headingIds.size || tableNumber !== tableLabels.length || sourceNumber !== 38 || citationCount !== 49 || tuningConditionListCount !== 1 || breakableIdentifierCount !== 2) {
  throw new Error(`Report structure mismatch: headings=${headingCount}/${headingIds.size}, tables=${tableNumber}/${tableLabels.length}, sources=${sourceNumber}/38, citations=${citationCount}/49, tuningLists=${tuningConditionListCount}/1, breakableIds=${breakableIdentifierCount}/2`);
}

const toc = [
  ["tldr", "TL;DR"],
  ["problem-analysis", "문제 원인 분석"],
  ["solution", "정확한 해결책"],
  ["alternatives", "확장 가능한 대안"],
  ["roadmap", "단계별 실행안"],
  ["risks", "주의 사항과 리스크"],
  ["confidence", "결론의 확실성"],
  ["sources", "Sources"],
].map(([id, label]) => `<li><a href="#${id}">${label}</a></li>`).join("\n");

const html = `<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="네이버 블로그 글을 권한 기반으로 수집하고 출처 귀속형 사고·문체 프록시를 만드는 구현 청사진">
  <title>네이버 블로그 기반 사고·문체 프록시 구현 청사진</title>
  <style>${css}</style>
</head>
<body>
  <header class="site-header">
    <div class="eyebrow">Evidence-locked research blueprint</div>
    <h1>네이버 블로그 기반 <span class="nowrap">사고·문체</span> 프록시 구현 청사진</h1>
    <p class="lead">특정인의 “사고를 복제”한다는 모호한 목표를, 권한이 확인된 자료에서 과거 주장·판단 근거·표현 습관을 날짜와 출처로 답하는 검증 가능한 시스템으로 바꾼다.</p>
    <div class="meta-row"><span><span class="meta-label">기준일</span> 2026-07-13 KST</span><span><span class="meta-label">범위</span> 기술·법률·운영 설계</span><span><span class="meta-label">주의</span> 개별 배포 법률 의견 아님</span></div>
  </header>
  <section class="decision-grid" aria-label="핵심 의사결정">
    <article class="decision-card allowed"><span class="badge">권장</span><h2>비공개·3인칭·RAG 우선</h2><p>저자가 제공한 원문과 선언된 inventory를 기준으로, 문장별 날짜와 출처를 붙이는 분석 프록시부터 시작한다.</p></article>
    <article class="decision-card conditional"><span class="badge">조건부</span><h2>스타일 어댑터는 마지막</h2><p>권리·검색·인용·삭제 gate 이후에도 반복되는 순수 문체 격차가 측정될 때만 분리 가능한 LoRA를 검토한다.</p></article>
    <article class="decision-card blocked"><span class="badge">현재 중단</span><h2>공개 실명 1인칭 분신</h2><p>현재 신념과 동의를 암시하고 화자를 바꾸므로 단순 문체 변환이 아니다. 별도 승인 전에는 제품 범위에서 제외한다.</p></article>
  </section>
  <div class="report-shell">
    <nav class="toc" aria-label="보고서 목차"><h2>Contents</h2><ol>${toc}</ol></nav>
    <main id="main-content">${body}</main>
  </div>
  <footer class="site-footer">본 보고서는 공식 문서, 한국 법령·판례, 동료평가 연구와 합성 데이터 실행 검증을 종합한 구현 설계다. 실제 특정 블로그 corpus의 권리와 품질은 별도 검증이 필요하다.</footer>
</body>
</html>`;

const tempOutputPath = `${outputPath}.${process.pid}.tmp`;
try {
  fs.writeFileSync(tempOutputPath, html);
  fs.renameSync(tempOutputPath, outputPath);
} finally {
  fs.rmSync(tempOutputPath, { force: true });
}
console.log(outputPath);
