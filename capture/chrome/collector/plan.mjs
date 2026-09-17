export function blogId(value) {
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(value ?? '')) throw new Error('INVALID_BLOG_ID');
  return value;
}

export function makePlan(blog, categories, options = {}) {
  blogId(blog);
  const ids = new Set(categories.map(c => c.id));
  const include = options.include === undefined ? ['0'] : options.include.map(String);
  const exclude = (options.exclude ?? []).map(String);
  for (const id of [...include, ...exclude]) if (!ids.has(id)) throw new Error(`UNKNOWN_CATEGORY_${id}`);
  const ancestors = id => {
    const seen = new Set(); let current = id;
    while (current !== null && current !== undefined) {
      if (seen.has(current)) throw new Error('CATEGORY_CYCLE');
      seen.add(current); current = categories.find(c => c.id === current)?.parent_id;
    }
    seen.add('0'); return seen;
  };
  // Parent-category lists include descendants; avoid fetching the same subtree twice.
  const roots = selected => [...new Set(selected)].filter(id => !selected.some(other => other !== id && ancestors(id).has(other)));
  const includes = roots(include), excludes = roots(exclude);
  return {schema: 'mnemosyne.collection-plan/v1', blog,
    include: includes.filter(id => !excludes.some(ex => ancestors(id).has(ex))), exclude: excludes,
    created_at: new Date().toISOString(), category_snapshot: categories};
}

export function selectDocuments(plan, inventories) {
  for (const id of plan.exclude) {
    if (inventories[id]?.status !== 'complete') throw new Error(`EXCLUSION_INVENTORY_INCOMPLETE_${id}`);
  }
  const excluded = new Set(plan.exclude.flatMap(id => inventories[id].documents.map(d => d.document_id)));
  const result = new Map();
  for (const id of plan.include) for (const doc of inventories[id]?.documents ?? []) {
    if (!excluded.has(doc.document_id)) result.set(doc.document_id, doc);
  }
  return [...result.values()];
}

export function absoluteDate(raw) {
  const m = /^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?(?:\s+(\d{1,2}):(\d{2}))?\s*$/.exec(raw ?? '');
  if (!m) return {value: null, precision: 'unknown'};
  const day = `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  const check = new Date(`${day}T00:00:00Z`);
  if (Number.isNaN(+check) || check.toISOString().slice(0, 10) !== day || Number(m[4] ?? 0) > 23 || Number(m[5] ?? 0) > 59) return {value: null, precision: 'unknown'};
  return {value: m[4] ? `${day}T${m[4].padStart(2, '0')}:${m[5]}:00+09:00` : day, precision: m[4] ? 'minute' : 'day'};
}
