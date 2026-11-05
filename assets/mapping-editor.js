import { loadJSON, renderTable, element, imageFor } from "./mapping-table.js";
import { recommendCandidates } from "./mapping-candidates.mjs";
import { recoverDraft } from "./mapping-draft.mjs";
const $ = (selector) => document.querySelector(selector);
let data, catalog, baseline, revision, token, active, selected;
let saving = false;
let recoveredConflicts = [];
const draftKey = "uniemoji-mapping-draft-v1";
function showError(message) {
  $("#editor-error").textContent = message;
  $("#editor-error").hidden = false;
}
function persistDraft() {
  try {
    if (changed.size)
      sessionStorage.setItem(draftKey, JSON.stringify({ data, baseline, conflicts: recoveredConflicts }));
    else sessionStorage.removeItem(draftKey);
  } catch {
    showError("浏览器无法备份草稿，请勿刷新或关闭页面，先保存到本地文件。");
  }
}
const changed = new Set();
const candidates = new Map();
const dialog = $("#picker");
function update() {
  changed.clear();
  data.semantics.forEach((row, i) =>
    data.platforms.forEach((p) => {
      if (row.mappings[p.id] !== baseline.semantics[i].mappings[p.id])
        changed.add(`${row.key}:${p.id}`);
    }),
  );
  renderTable($("#mapping-table"), data, catalog, {
    onSelect: openPicker,
    onChoose: chooseInline,
    candidates,
    disabled: saving,
    onlyMissing: $("#only-missing").checked,
    changed,
  });
  $("#save").disabled = saving || !changed.size;
  $("#save-status").textContent = saving
    ? "正在保存…"
    : changed.size
      ? `${changed.size} 项修改未保存`
      : "已与本地文件同步";
  persistDraft();
}
function chooseInline(semantic, platform, url) {
  if (saving) return;
  semantic.mappings[platform.id] = url;
  const scroll = $(".mapping-scroll");
  const position = { top: scroll.scrollTop, left: scroll.scrollLeft };
  update();
  const button = [...document.querySelectorAll(".mapping-cell")].find(
    (b) =>
      b.dataset.key === semantic.key &&
      b.dataset.platform === platform.id,
  );
  (button || $("#only-missing")).focus({ preventScroll: true });
  scroll.scrollTo(position);
}
function preview(item) {
  $("#preview-image").replaceChildren(
    ...(item ? [imageFor(item.url, item.name, 128)] : []),
  );
  $("#preview-name").textContent = item?.name || "选择一个表情";
  $("#preview-path").textContent = item?.url || "";
}
function showCandidates() {
  const query = $("#picker-search").value.trim().toLowerCase();
  const items = catalog
    .find((p) => p.platform === active.platform.id)
    .emojis.filter((e) =>
      [e.name, e.url, ...(e.tags || []), ...(e.keywords || [])]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  $("#candidate-count").textContent = `${items.length} 个表情`;
  $("#candidates").replaceChildren();
  for (const item of items) {
    const button = element("button", undefined, "candidate");
    button.type = "button";
    button.dataset.url = item.url;
    button.setAttribute("aria-pressed", String(selected?.url === item.url));
    button.title = `${item.name} · ${item.url}`;
    button.append(imageFor(item.url, "", 40), element("span", item.name));
    button.addEventListener("mouseenter", () => preview(item));
    button.addEventListener("focus", () => preview(item));
    button.addEventListener("click", () => apply(item.url));
    $("#candidates").append(button);
  }
  if (!items.length)
    $("#candidates").append(element("p", "没有找到匹配的表情"));
}
function openPicker(semantic, platform) {
  if (saving) return;
  active = { semantic, platform };
  $("#picker-title").textContent = `${semantic.emoji} ${semantic.label}`;
  $("#picker-platform").textContent = platform.name;
  $("#picker-search").value = "";
  selected =
    catalog
      .find((p) => p.platform === platform.id)
      .emojis.find((e) => e.url === semantic.mappings[platform.id]) || null;
  preview(selected);
  showCandidates();
  dialog.showModal();
  $("#picker-search").focus();
}
function apply(url) {
  active.semantic.mappings[active.platform.id] = url;
  dialog.close();
  update();
  const button = [...document.querySelectorAll(".mapping-cell")].find(
    (b) =>
      b.dataset.key === active.semantic.key &&
      b.dataset.platform === active.platform.id,
  );
  (button || $("#only-missing")).focus();
}
$("#picker-search").addEventListener("input", showCandidates);
$("#close-picker").addEventListener("click", () => dialog.close());
$("#clear-image").addEventListener("click", () => apply(null));
$("#only-missing").addEventListener("change", () => {
  if (data) update();
});
window.addEventListener("beforeunload", (event) => {
  if (changed.size) {
    event.preventDefault();
    event.returnValue = "";
  }
});
$("#save").addEventListener("click", async () => {
  if (saving || !changed.size) return;
  const conflicts = recoveredConflicts.filter(key => changed.has(key));
  if (conflicts.length && !window.confirm(
    `恢复的草稿与本地文件有 ${conflicts.length} 处冲突（${conflicts.join("、")}）。确认使用当前页面的选择覆盖这些位置吗？`,
  )) return;
  saving = true;
  update();
  $("#editor-error").hidden = true;
  try {
    const response = await fetch("api/mappings", {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-Editor-Token": token },
      body: JSON.stringify({ revision, data }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "保存失败");
    if (typeof result.revision !== "string") throw new Error("服务未确认保存成功");
    const saved = await loadJSON("api/mappings");
    if (saved.revision !== result.revision ||
        JSON.stringify(saved.data) !== JSON.stringify(data))
      throw new Error("保存后的文件与当前选择不一致，请刷新恢复草稿并核对");
    revision = result.revision;
    baseline = structuredClone(data);
    recoveredConflicts = [];
  } catch (error) {
    showError(`未保存成功：${error.message}。当前选择仍保留；草稿备份可用时，在此标签页刷新会自动恢复。`);
    $("#editor-error").scrollIntoView({ block: "nearest" });
  } finally {
    saving = false;
    update();
  }
});
try {
  const [session, source] = await Promise.all([
    loadJSON("api/mappings"),
    loadJSON("emoji.json"),
  ]);
  data = session.data;
  revision = session.revision;
  token = session.token;
  catalog = source;
  baseline = structuredClone(data);
  try {
    const draft = sessionStorage.getItem(draftKey);
    if (draft) {
      const recovery = recoverDraft(data, JSON.parse(draft), catalog);
      data = recovery.data;
      recoveredConflicts = recovery.conflicts;
      if (recovery.restored || recovery.skipped)
        showError(`已恢复 ${recovery.restored} 项草稿，尚未保存到文件。` +
          (recovery.conflicts.length ? `其中 ${recovery.conflicts.length} 项与文件冲突，保存前需确认。` : "") +
          (recovery.skipped ? `${recovery.skipped} 项语义或素材已移除，未恢复。` : ""));
    }
  } catch {
    showError("无法读取浏览器草稿，已加载本地文件。");
  }
  for (const semantic of data.semantics) {
    for (const platform of data.platforms) {
      candidates.set(
        `${semantic.key}:${platform.id}`,
        recommendCandidates(
          semantic,
          catalog.find((p) => p.platform === platform.id).emojis,
        ),
      );
    }
  }
  update();
} catch (error) {
  $("#save-status").textContent = "未连接本地维护服务";
  $("#editor-error").textContent =
    "请在项目目录运行 npm run edit-mappings，并打开终端显示的维护页地址。";
  $("#editor-error").hidden = false;
}
