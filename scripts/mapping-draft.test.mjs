import test from 'node:test';
import assert from 'node:assert/strict';
import { recoverDraft } from '../assets/mapping-draft.mjs';
const catalog = [{ platform: 'p', emojis: ['a', 'b', 'c'].map(url => ({ url })) }];
const file = (first = 'a', second = null) => ({ semantics: [
  { key: 'first', mappings: { p: first } },
  { key: 'second', mappings: { p: second } },
] });
test('刷新恢复选择和清空，且不修改文件快照', () => {
  const baseline = file('a', 'b');
  const data = file('c', null);
  const result = recoverDraft(baseline, { baseline, data }, catalog);
  assert.deepEqual(result.data, data);
  assert.equal(result.restored, 2);
  assert.deepEqual(result.conflicts, []);
  assert.deepEqual(baseline, file('a', 'b'));
});
test('保留外部改动，仅恢复用户编辑的单元格', () => {
  const result = recoverDraft(file('a', 'c'), { baseline: file(), data: file('b') }, catalog);
  assert.deepEqual(result.data, file('b', 'c'));
  assert.deepEqual(result.conflicts, []);
});
test('同一单元格冲突不能因再次刷新而失去确认', () => {
  const current = file('c');
  const first = recoverDraft(current, { baseline: file(), data: file('b') }, catalog);
  assert.deepEqual(first.conflicts, ['first:p']);
  const second = recoverDraft(current, {
    baseline: current, data: first.data, conflicts: first.conflicts,
  }, catalog);
  assert.deepEqual(second.conflicts, ['first:p']);
});
test('已写入的草稿不恢复为未保存，移除的语义和素材不复活', () => {
  const draft = { baseline: file(), data: file('b', 'missing') };
  const result = recoverDraft(file('b'), draft, catalog);
  assert.equal(result.restored, 0);
  assert.equal(result.skipped, 1);
  assert.deepEqual(result.data, file('b'));
  const removed = recoverDraft({ semantics: [] }, draft, catalog);
  assert.equal(removed.skipped, 2);
  assert.deepEqual(removed.data.semantics, []);
});
