import { loadJSON, renderTable } from "./mapping-table.js";
const status = document.querySelector("#mapping-status");
try {
  const [data, catalog] = await Promise.all([
    loadJSON("semantic-mappings.json"),
    loadJSON("emoji.json"),
  ]);
  renderTable(document.querySelector("#mapping-table"), data, catalog);
  status.hidden = true;
} catch (error) {
  status.textContent = `映射加载失败，请刷新重试。${error.message}`;
}
