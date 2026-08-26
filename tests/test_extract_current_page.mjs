import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const extractorPath = new URL("../capture/extract-current-page.js", import.meta.url);
const source = fs.readFileSync(extractorPath, "utf8");

class NodeStub {
  constructor(tagName, { text = "", attrs = {}, children = [] } = {}) {
    this.nodeType = 1;
    this.tagName = tagName.toUpperCase();
    this.textContent = text;
    this.attrs = attrs;
    this.childNodes = children;
    this.parentElement = null;
    this.selectors = new Map();
    for (const child of children) {
      if (child.nodeType === 1) child.parentElement = this;
    }
  }

  getAttribute(name) {
    return Object.hasOwn(this.attrs, name) ? this.attrs[name] : null;
  }

  querySelectorAll(selector) {
    return this.selectors.get(selector) ?? [];
  }
}

const text = (data) => ({ nodeType: 3, data });
const element = (tagName, children = []) => new NodeStub(tagName, { children });

function makeDocument(changes = {}) {
  const url = changes.url ?? "https://blog.naver.com/fixture_author/42";
  const paragraph = element("p", [text("First"), element("br"), text("Second")]);
  const root = new NodeStub("div");
  root.selectors.set(".se-text-paragraph", changes.paragraphs ?? [paragraph]);
  root.selectors.set("img", Array(changes.images ?? 1).fill(new NodeStub("img")));
  root.selectors.set("table", Array(changes.tables ?? 0).fill(new NodeStub("table")));
  root.selectors.set("iframe,object,embed", Array(changes.embeds ?? 0).fill(new NodeStub("iframe")));
  root.selectors.set("video,audio", Array(changes.media ?? 0).fill(new NodeStub("video")));

  const document = new NodeStub("document");
  document.location = { href: url };
  document.selectors.set(".se-main-container", changes.roots ?? [root]);
  document.selectors.set("iframe#mainFrame", changes.frames ?? []);
  document.selectors.set(".se-title-text", changes.titles ?? [new NodeStub("h1", { text: " Synthetic title " })]);
  document.selectors.set("meta[property=\"og:title\"]", changes.metas ?? []);
  document.selectors.set(".se_publishDate", changes.dates ?? [new NodeStub("time", { text: "2026. 8. 26." })]);
  const canonical = new NodeStub("link", { attrs: { href: changes.canonicalRaw ?? "/fixture_author/42" } });
  canonical.href = changes.canonicalResolved ?? "https://blog.naver.com/fixture_author/42";
  document.selectors.set("link[rel=\"canonical\"]", changes.canonicals ?? [canonical]);
  return { document, root };
}

function extract(document) {
  return vm.runInNewContext(source, { document, TextEncoder, URL, JSON });
}

function payload(document) {
  const result = extract(document);
  assert.notEqual(result, "MNEMOSYNE_UNSUPPORTED_PAGE");
  return JSON.parse(result);
}

test("renders the selected document and exact omission warnings", () => {
  const { document } = makeDocument({ images: 1, tables: 2, embeds: 3, media: 4 });
  const result = payload(document);

  assert.deepEqual({ ...result.component_counts }, { images: 1, tables: 2, embeds: 3, media: 4 });
  assert.deepEqual(
    [...result.warnings],
    ["EMBEDS_OMITTED", "IMAGES_OMITTED", "MEDIA_OMITTED", "TABLES_OMITTED"],
  );
  assert.equal(result.body, "First\nSecond\n");
  assert.equal(result.title, "Synthetic title");
});

test("uses only the same-origin main frame when the top document has no root", () => {
  const framed = makeDocument({ images: 0 });
  const frame = new NodeStub("iframe");
  frame.contentDocument = framed.document;
  const top = makeDocument({ roots: [], frames: [frame], url: "https://blog.naver.com/fixture_author/42?x=1" });
  top.document.selectors.set("link[rel=\"canonical\"]", [new NodeStub("link", { attrs: { href: "bad" } })]);

  const result = payload(top.document);

  assert.equal(result.top_document_url, top.document.location.href);
  assert.equal(result.content_document_url, framed.document.location.href);
  assert.equal(result.canonical_url, "https://blog.naver.com/fixture_author/42");
});

test("uses the raw og title fallback only when the title selector is absent", () => {
  const meta = new NodeStub("meta", { attrs: { content: "  Fallback title  " } });
  const { document } = makeDocument({ titles: [], metas: [meta] });

  assert.equal(payload(document).title, "Fallback title");
});

test("matches Python whitespace semantics without stripping format characters", () => {
  const { document } = makeDocument({ titles: [new NodeStub("h1", { text: "A\uFEFFB\u2003 C" })] });

  assert.equal(payload(document).title, "A\uFEFFB C");
});

test("renders text and br while skipping executable descendants and excluded paragraphs", () => {
  const script = element("script", [text("hidden")]);
  const style = element("style", [text("hidden")]);
  const noscript = element("noscript", [text("hidden")]);
  const retained = element("p", [text("A"), element("br"), script, style, noscript, text("B")]);
  const excluded = element("p", [text("table text")]);
  const table = element("table", [excluded]);
  excluded.parentElement = table;
  const { document } = makeDocument({ paragraphs: [retained, excluded] });

  assert.equal(payload(document).body, "A\nB\n");
});

test("rejects every ambiguous selector cardinality and inaccessible frame", () => {
  const valid = makeDocument();
  const inaccessible = new NodeStub("iframe");
  Object.defineProperty(inaccessible, "contentDocument", { get() { throw new Error("blocked"); } });
  const cases = [
    makeDocument({ roots: [] }).document,
    makeDocument({ roots: [valid.root, valid.root] }).document,
    makeDocument({ roots: [], frames: [new NodeStub("iframe"), new NodeStub("iframe")] }).document,
    makeDocument({ roots: [], frames: [inaccessible] }).document,
    makeDocument({ titles: [new NodeStub("h1"), new NodeStub("h1")] }).document,
    makeDocument({ titles: [], metas: [] }).document,
    makeDocument({ titles: [], metas: [new NodeStub("meta"), new NodeStub("meta")] }).document,
    makeDocument({ dates: [] }).document,
    makeDocument({ dates: [new NodeStub("time"), new NodeStub("time")] }).document,
    makeDocument({ paragraphs: [] }).document,
    makeDocument({ canonicals: [new NodeStub("link"), new NodeStub("link")] }).document,
  ];

  for (const document of cases) assert.equal(extract(document), "MNEMOSYNE_UNSUPPORTED_PAGE");

  const crossOrigin = new NodeStub("iframe");
  crossOrigin.contentDocument = makeDocument({ url: "https://example.invalid/fixture_author/42" }).document;
  assert.equal(
    extract(makeDocument({ roots: [], frames: [crossOrigin] }).document),
    "MNEMOSYNE_UNSUPPORTED_PAGE",
  );
});

test("rejects canonical raw/resolved mismatch and every URL identity disagreement", () => {
  const cases = [
    makeDocument({ canonicalRaw: "", canonicalResolved: "https://blog.naver.com/fixture_author/42" }).document,
    makeDocument({ canonicalRaw: "/fixture_author/42", canonicalResolved: "https://blog.naver.com/fixture_author/43" }).document,
    makeDocument({ canonicalRaw: "/fixture_author/43", canonicalResolved: "https://blog.naver.com/fixture_author/43" }).document,
    makeDocument({ url: "https://blog.naver.com/PostView.naver?blogId=fixture_author&logNo=43" }).document,
    makeDocument({ url: "https://m.blog.naver.com/fixture_author/42" }).document,
    makeDocument({ url: "https://blog.naver.com/fixture_author/42?blogId=other&logNo=42" }).document,
  ];

  for (const document of cases) assert.equal(extract(document), "MNEMOSYNE_UNSUPPORTED_PAGE");
});

test("accepts 4096-byte URLs and rejects 4097-byte top/content/canonical URLs", () => {
  const padded = (size) => {
    const base = "https://blog.naver.com/fixture_author/42#";
    return base + "x".repeat(size - Buffer.byteLength(base));
  };
  assert.equal(Buffer.byteLength(padded(4096)), 4096);
  assert.notEqual(extract(makeDocument({ url: padded(4096) }).document), "MNEMOSYNE_UNSUPPORTED_PAGE");

  const topTooLong = makeDocument({ url: padded(4097) }).document;
  const contentTooLong = makeDocument();
  const frame = new NodeStub("iframe");
  frame.contentDocument = makeDocument({ url: padded(4097) }).document;
  contentTooLong.document.selectors.set(".se-main-container", []);
  contentTooLong.document.selectors.set("iframe#mainFrame", [frame]);
  const rawTooLong = makeDocument({ canonicalRaw: padded(4097), canonicalResolved: padded(4097) }).document;
  const resolvedTooLong = makeDocument({ canonicalRaw: "/fixture_author/42", canonicalResolved: padded(4097) }).document;

  for (const document of [topTooLong, contentTooLong.document, rawTooLong, resolvedTooLong]) {
    assert.equal(extract(document), "MNEMOSYNE_UNSUPPORTED_PAGE");
  }
});

test("permits no canonical link and rejects invalid content boundaries", () => {
  assert.equal(payload(makeDocument({ canonicals: [] }).document).canonical_url, null);
  assert.equal(
    payload(makeDocument({ canonicalRaw: "https://blog.naver.com/fixture_author/42" }).document).canonical_url,
    "https://blog.naver.com/fixture_author/42",
  );
  const missingRaw = new NodeStub("link");
  missingRaw.href = "https://blog.naver.com/fixture_author/42";
  const cases = [
    makeDocument({ canonicals: [missingRaw] }).document,
    makeDocument({ titles: [new NodeStub("h1", { text: " " })] }).document,
    makeDocument({ titles: [], metas: [new NodeStub("meta", { attrs: { content: "" } })] }).document,
    makeDocument({ dates: [new NodeStub("time", { text: " " })] }).document,
    makeDocument({ paragraphs: [element("p", [text(" ")])] }).document,
    makeDocument({ titles: [new NodeStub("h1", { text: "a".repeat(4097) })] }).document,
  ];
  for (const document of cases) assert.equal(extract(document), "MNEMOSYNE_UNSUPPORTED_PAGE");
});
