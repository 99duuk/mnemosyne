(function extractCurrentPage(topDocument) {
  "use strict";
  const unsupported = "MNEMOSYNE_UNSUPPORTED_PAGE";
  const pythonWhitespace = /[\u0009-\u000D\u001C-\u0020\u0085\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]+/gu;
  const pythonWhitespaceOnly = /^[\u0009-\u000D\u001C-\u0020\u0085\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]*$/u;
  const utf8Length = (value) => new TextEncoder().encode(value).length;
  const validString = (value, bytes, body = false) => {
    if (typeof value !== "string" || utf8Length(value) > bytes || /[\uD800-\uDFFF]/u.test(value)) return false;
    return body ? !/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/u.test(value) : !/[\u0000-\u001F\u007F-\u009F]/u.test(value);
  };
  const normalizeText = (value) => value.normalize("NFC").replace(pythonWhitespace, " ").replace(/^ | $/gu, "");
  const normalizeBody = (value) => {
    const lines = value.replace(/\r\n?/gu, "\n").normalize("NFC").split("\n").map((line) => line.replace(/[ \t]+$/gu, ""));
    while (lines.length && /^[ \t]*$/u.test(lines[0])) lines.shift();
    while (lines.length && /^[ \t]*$/u.test(lines.at(-1))) lines.pop();
    return `${lines.join("\n")}\n`;
  };
  const identity = (raw) => {
    if (!validString(raw, 4096) || !/^https:\/\/blog[.]naver[.]com(?:\/|$)/u.test(raw)) return null;
    let parsed;
    try { parsed = new URL(raw); } catch { return null; }
    if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.host !== "blog.naver.com") return null;
    const query = raw.split("#", 1)[0].split("?", 2)[1] ?? "";
    const values = { blogId: [], logNo: [] };
    for (const part of query ? query.split("&") : []) {
      const separator = part.indexOf("=");
      const name = separator < 0 ? part : part.slice(0, separator);
      if (name === "blogId" || name === "logNo") values[name].push(separator < 0 ? "" : part.slice(separator + 1));
    }
    if ([...values.blogId, ...values.logNo].some((value) => value.includes("%"))) return null;
    const direct = /^\/([A-Za-z0-9_-]{1,64})\/([0-9]{1,20})\/?$/u.exec(parsed.pathname);
    let blogId;
    let postId;
    if (direct) {
      [blogId, postId] = direct.slice(1);
      if ((values.blogId.length || values.logNo.length) && (values.blogId.length !== 1 || values.logNo.length !== 1 || values.blogId[0] !== blogId)) return null;
    } else if (parsed.pathname === "/PostView.naver" && values.blogId.length === 1 && values.logNo.length === 1) {
      [blogId] = values.blogId;
      [postId] = values.logNo;
    } else return null;
    if (!/^[A-Za-z0-9_-]{1,64}$/u.test(blogId) || !/^[0-9]{1,20}$/u.test(postId) || BigInt(postId) === 0n) return null;
    const canonicalPostId = BigInt(postId).toString();
    if (direct && values.logNo.length === 1 && (!/^[0-9]{1,20}$/u.test(values.logNo[0]) || BigInt(values.logNo[0]).toString() !== canonicalPostId)) return null;
    return { blogId, postId: canonicalPostId };
  };
  const sameIdentity = (left, right) => left && right && left.blogId === right.blogId && left.postId === right.postId;
  const render = (node) => {
    if (node.nodeType === 3) return node.data;
    if (node.nodeType !== 1 || ["SCRIPT", "STYLE", "NOSCRIPT"].includes(node.tagName)) return "";
    if (node.tagName === "BR") return "\n";
    return Array.from(node.childNodes ?? [], render).join("");
  };

  try {
    const topUrl = topDocument.location.href;
    const topIdentity = identity(topUrl);
    if (!topIdentity) return unsupported;
    const topRoots = topDocument.querySelectorAll(".se-main-container");
    let contentDocument = topDocument;
    let root;
    if (topRoots.length === 1) [root] = topRoots;
    else if (topRoots.length !== 0) return unsupported;
    else {
      const frames = topDocument.querySelectorAll("iframe#mainFrame");
      if (frames.length !== 1 || !frames[0].contentDocument) return unsupported;
      contentDocument = frames[0].contentDocument;
      const topOrigin = new URL(topUrl).origin;
      if (new URL(contentDocument.location.href).origin !== topOrigin) return unsupported;
      const roots = contentDocument.querySelectorAll(".se-main-container");
      if (roots.length !== 1) return unsupported;
      [root] = roots;
    }
    const contentUrl = contentDocument.location.href;
    if (!sameIdentity(identity(contentUrl), topIdentity)) return unsupported;

    const titleNodes = contentDocument.querySelectorAll(".se-title-text");
    let rawTitle;
    if (titleNodes.length === 1) rawTitle = titleNodes[0].textContent;
    else if (titleNodes.length === 0) {
      const metas = contentDocument.querySelectorAll('meta[property="og:title"]');
      if (metas.length !== 1) return unsupported;
      rawTitle = metas[0].getAttribute("content");
    } else return unsupported;
    const dates = contentDocument.querySelectorAll(".se_publishDate");
    if (dates.length !== 1) return unsupported;
    const rawDate = dates[0].textContent;
    if (!validString(rawTitle, 4096) || !validString(rawDate, 1024)) return unsupported;
    const title = normalizeText(rawTitle);
    const publishedAtRaw = normalizeText(rawDate);
    if (!title || [...title].length > 500 || !publishedAtRaw || [...publishedAtRaw].length > 128) return unsupported;

    const paragraphs = Array.from(root.querySelectorAll(".se-text-paragraph")).filter((paragraph) => {
      for (let parent = paragraph.parentElement; parent && parent !== root; parent = parent.parentElement) {
        if (["TABLE", "IFRAME", "OBJECT", "EMBED", "VIDEO", "AUDIO"].includes(parent.tagName)) return false;
      }
      return true;
    });
    if (!paragraphs.length) return unsupported;
    const rawBody = paragraphs.map(render).join("\n\n");
    if (!validString(rawBody, 10485760, true)) return unsupported;
    const body = normalizeBody(rawBody);
    if (utf8Length(body) > 10485760 || pythonWhitespaceOnly.test(body)) return unsupported;

    const canonicalLinks = contentDocument.querySelectorAll('link[rel="canonical"]');
    if (canonicalLinks.length > 1) return unsupported;
    let canonicalUrl = null;
    if (canonicalLinks.length === 1) {
      const rawHref = canonicalLinks[0].getAttribute("href");
      const domHref = canonicalLinks[0].href;
      if (!validString(rawHref, 4096) || !rawHref || !validString(domHref, 4096)) return unsupported;
      const resolved = new URL(rawHref, contentUrl).href;
      if (resolved !== domHref || !sameIdentity(identity(resolved), topIdentity)) return unsupported;
      canonicalUrl = resolved;
    }
    const componentCounts = {
      images: root.querySelectorAll("img").length,
      tables: root.querySelectorAll("table").length,
      embeds: root.querySelectorAll("iframe,object,embed").length,
      media: root.querySelectorAll("video,audio").length,
    };
    const warnings = [];
    if (componentCounts.images > 0) warnings.push("IMAGES_OMITTED");
    if (componentCounts.tables > 0) warnings.push("TABLES_OMITTED");
    if (componentCounts.embeds > 0) warnings.push("EMBEDS_OMITTED");
    if (componentCounts.media > 0) warnings.push("MEDIA_OMITTED");
    warnings.sort();
    return JSON.stringify({
      schema: "mnemosyne.safari-extract/v1",
      top_document_url: topUrl,
      content_document_url: contentUrl,
      canonical_url: canonicalUrl,
      title,
      published_at_raw: publishedAtRaw,
      body,
      editor_fingerprint: "smarteditor_one",
      component_counts: componentCounts,
      warnings,
    });
  } catch {
    return unsupported;
  }
})(document);
