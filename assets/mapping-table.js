export async function loadJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`无法读取 ${url}（${response.status}）`);
  return response.json();
}

export function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

export function imageFor(url, name, size = 32) {
  const image = document.createElement("img");
  image.src = url;
  image.alt = name;
  image.width = image.height = size;
  image.loading = "lazy";
  return image;
}

export function renderTable(
  table,
  data,
  catalog,
  {
    onSelect,
    onChoose,
    candidates,
    disabled = false,
    onlyMissing = false,
    changed = new Set(),
  } = {},
) {
  const names = new Map(
    catalog.flatMap((p) => p.emojis.map((e) => [e.url, e.name])),
  );
  const head = table.createTHead();
  head.replaceChildren();
  const headings = head.insertRow();
  for (const title of ["Emoji / 语义", ...data.platforms.map((p) => p.name)]) {
    const th = element("th", title);
    th.scope = "col";
    headings.append(th);
  }
  const body = document.createElement("tbody");
  for (const semantic of data.semantics) {
    if (onlyMissing && data.platforms.every((p) => semantic.mappings[p.id]))
      continue;
    const row = body.insertRow();
    const heading = element("th");
    heading.scope = "row";
    const label = element("span", semantic.label, "mapping-label");
    label.append(element("code", semantic.key));
    heading.append(element("span", semantic.emoji, "mapping-emoji"), label);
    row.append(heading);
    for (const platform of data.platforms) {
      const url = semantic.mappings[platform.id];
      const name = names.get(url) || "";
      const cell = row.insertCell();
      const content = url
        ? imageFor(url, name)
        : element("span", "—", "unmapped");
      if (onSelect) {
        const button = element("button", undefined, "mapping-cell");
        button.type = "button";
        button.disabled = disabled;
        button.dataset.key = semantic.key;
        button.dataset.platform = platform.id;
        button.setAttribute(
          "aria-label",
          `${semantic.label} · ${platform.name}：${name || "暂未映射"}，点击修改`,
        );
        button.title = name || "选择表情";
        if (changed.has(`${semantic.key}:${platform.id}`))
          button.classList.add("changed");
        button.append(content);
        button.addEventListener("click", () => onSelect(semantic, platform));
        cell.append(button);
        const suggestions =
          candidates?.get(`${semantic.key}:${platform.id}`) || [];
        if (onChoose && !url && suggestions.length) {
          cell.classList.add("has-candidates");
          button.append(element("span", "更多…", "mapping-more"));
          const choices = element("div", undefined, "inline-candidates");
          choices.setAttribute("role", "group");
          choices.setAttribute(
            "aria-label",
            `${semantic.label} · ${platform.name}候选`,
          );
          for (const item of suggestions) {
            const choice = element("button", undefined, "inline-candidate");
            choice.type = "button";
            choice.disabled = disabled;
            choice.dataset.url = item.url;
            choice.dataset.key = semantic.key;
            choice.dataset.platform = platform.id;
            choice.setAttribute(
              "aria-label",
              `选用${item.name}作为${semantic.label} · ${platform.name}`,
            );
            choice.setAttribute("aria-pressed", String(item.url === url));
            choice.title = item.name;
            choice.append(
              imageFor(item.url, "", 32),
              element("span", item.name),
            );
            choice.addEventListener("click", () =>
              onChoose(semantic, platform, item.url),
            );
            choices.append(choice);
          }
          const hint = element("span", "候选 · 点选", "inline-candidate-hint");
          cell.append(hint, choices);
        }
      } else {
        cell.title = `${platform.name} · ${name || "暂未映射"}`;
        cell.append(content);
      }
    }
  }
  table.tBodies[0]?.remove();
  table.append(body);
}
