// Keep only user-edited cells when recovering onto a newer mapping file.
export function recoverDraft(current, draft, catalog) {
  const data = structuredClone(current);
  const conflicts = [];
  let restored = 0;
  let skipped = 0;
  if (!draft?.data?.semantics || !draft?.baseline?.semantics)
    throw new Error("草稿格式无效");
  const urls = new Map(catalog.map(p => [p.platform, new Set(p.emojis.map(e => e.url))]));
  for (const row of draft.data.semantics) {
    const base = draft.baseline.semantics.find(r => r.key === row.key);
    const target = data.semantics.find(r => r.key === row.key);
    if (!base) continue;
    for (const [platform, value] of Object.entries(row.mappings)) {
      if (value === base.mappings[platform]) continue;
      if (!target || !Object.hasOwn(target.mappings, platform) ||
          (value !== null && !urls.get(platform)?.has(value))) {
        skipped++;
        continue;
      }
      if (target.mappings[platform] === value) continue;
      if (target.mappings[platform] !== base.mappings[platform] ||
          draft.conflicts?.includes(`${row.key}:${platform}`))
        conflicts.push(`${row.key}:${platform}`);
      target.mappings[platform] = value;
      restored++;
    }
  }
  return { data, conflicts, restored, skipped };
}
