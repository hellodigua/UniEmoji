import http from "node:http";
import {
  readFileSync,
  writeFileSync,
  renameSync,
  realpathSync,
  unlinkSync,
} from "node:fs";
import { resolve, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash, randomBytes } from "node:crypto";

const revisionOf = (bytes) => createHash("sha256").update(bytes).digest("hex");
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export function validateMappings(data, current, catalog) {
  if (
    !data ||
    data.schemaVersion !== 1 ||
    !equal(data.platforms, current.platforms) ||
    !Array.isArray(data.semantics) ||
    data.semantics.length !== current.semantics.length
  ) {
    throw new Error("映射结构或平台定义不匹配");
  }
  const urls = new Map(
    catalog.map((p) => [p.platform, new Set(p.emojis.map((e) => e.url))]),
  );
  const expectedPlatforms = current.platforms.map((p) => p.id).sort();
  data.semantics.forEach((row, i) => {
    const expected = current.semantics[i];
    if (
      !row ||
      row.key !== expected.key ||
      row.emoji !== expected.emoji ||
      row.label !== expected.label ||
      !row.mappings ||
      !equal(Object.keys(row.mappings).sort(), expectedPlatforms)
    ) {
      throw new Error("第一版仅允许修改图片映射，不能修改语义定义");
    }
    for (const platform of current.platforms) {
      const url = row.mappings[platform.id];
      if (url !== null && !urls.get(platform.id)?.has(url))
        throw new Error(
          `${row.key} 的 ${platform.name} 图片不属于该平台素材库`,
        );
    }
  });
  // Persist only supported fields, in a stable order for readable Git diffs.
  return {
    schemaVersion: 1,
    platforms: current.platforms,
    semantics: data.semantics.map((row) => ({
      key: row.key,
      emoji: row.emoji,
      label: row.label,
      mappings: Object.fromEntries(
        current.platforms.map((p) => [p.id, row.mappings[p.id]]),
      ),
    })),
  };
}

export function createEditorServer(root) {
  root = realpathSync(root);
  const mappingPath = resolve(root, "semantic-mappings.json");
  const token = randomBytes(32).toString("hex");
  const sendJSON = (res, status, value) => {
    res.writeHead(status, {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify(value));
  };
  return http.createServer(async (req, res) => {
    const host = `127.0.0.1:${req.socket.localPort}`;
    if (
      req.headers.host !== host ||
      (req.headers.origin && req.headers.origin !== `http://${host}`)
    )
      return sendJSON(res, 403, { error: "仅允许本地维护页面访问" });
    let pathname;
    try {
      pathname = decodeURIComponent(
        new URL(req.url, `http://${host}`).pathname,
      );
    } catch {
      return sendJSON(res, 400, { error: "无效地址" });
    }
    if (pathname === "/api/mappings") {
      try {
        if (req.method === "GET") {
          const bytes = readFileSync(mappingPath);
          return sendJSON(res, 200, {
            data: JSON.parse(bytes),
            revision: revisionOf(bytes),
            token,
          });
        }
        if (req.method !== "PUT")
          return sendJSON(res, 405, { error: "不支持的请求方式" });
        if (
          req.headers["x-editor-token"] !== token ||
          req.headers["content-type"] !== "application/json"
        )
          return sendJSON(res, 403, {
            error: "保存凭证无效，请重新打开维护页",
          });
        const chunks = [];
        let size = 0;
        for await (const chunk of req) {
          size += chunk.length;
          if (size > 256 * 1024)
            return sendJSON(res, 413, { error: "保存数据过大" });
          chunks.push(chunk);
        }
        let payload;
        try {
          payload = JSON.parse(Buffer.concat(chunks).toString());
        } catch {
          return sendJSON(res, 400, { error: "无效 JSON" });
        }
        const current = readFileSync(mappingPath);
        if (payload?.revision !== revisionOf(current))
          return sendJSON(res, 409, {
            error:
              "本地映射已被其他窗口或工具修改，请先保留当前选择，再刷新页面核对",
          });
        let validated;
        try {
          validated = validateMappings(
            payload.data,
            JSON.parse(current),
            JSON.parse(readFileSync(resolve(root, "emoji.json"))),
          );
        } catch (error) {
          return sendJSON(res, 400, { error: error.message });
        }
        const bytes = JSON.stringify(validated, null, 2) + "\n";
        const temporary = `${mappingPath}.${randomBytes(8).toString("hex")}.tmp`;
        try {
          writeFileSync(temporary, bytes, { flag: "wx" });
          renameSync(temporary, mappingPath);
        } finally {
          try {
            unlinkSync(temporary);
          } catch (error) {
            if (error.code !== "ENOENT") throw error;
          }
        }
        return sendJSON(res, 200, { revision: revisionOf(bytes) });
      } catch {
        return sendJSON(res, 500, {
          error: "无法读取或保存本地文件，请检查终端及文件权限",
        });
      }
    }
    if (!["GET", "HEAD"].includes(req.method))
      return sendJSON(res, 405, { error: "不支持的请求方式" });
    const relative =
      pathname === "/" ? "mapping-editor.html" : pathname.slice(1);
    const publicFiles = new Set([
      "index.html",
      "mapping-editor.html",
      "protocol.html",
      "gallery.html",
      "emoji.json",
      "semantic-mappings.json",
      "THIRD_PARTY_NOTICES.md",
    ]);
    if (!publicFiles.has(relative) && !/^(assets|output)\//.test(relative))
      return sendJSON(res, 404, { error: "文件不存在" });
    try {
      const file = realpathSync(resolve(root, relative));
      if (
        !file.startsWith(root + sep) ||
        ((relative.startsWith("assets/") || relative.startsWith("output/")) &&
          !file.startsWith(resolve(root, relative.split("/")[0]) + sep))
      )
        return sendJSON(res, 403, { error: "不可访问该文件" });
      const bytes = readFileSync(file);
      const mime =
        {
          ".html": "text/html; charset=utf-8",
          ".js": "text/javascript; charset=utf-8",
          ".mjs": "text/javascript; charset=utf-8",
          ".css": "text/css; charset=utf-8",
          ".json": "application/json; charset=utf-8",
          ".avif": "image/avif",
          ".svg": "image/svg+xml",
          ".md": "text/plain; charset=utf-8",
        }[extname(file)] || "application/octet-stream";
      res.writeHead(200, {
        "Content-Type": mime,
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      });
      res.end(req.method === "HEAD" ? undefined : bytes);
    } catch {
      sendJSON(res, 404, { error: "文件不存在" });
    }
  });
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const root = fileURLToPath(new URL("../", import.meta.url));
  const port = Number(process.env.PORT || 4174);
  const server = createEditorServer(root);
  server.on("error", (error) => {
    console.error(`维护服务启动失败：${error.message}`);
    process.exitCode = 1;
  });
  server.listen(port, "127.0.0.1", () =>
    console.log(
      `表情映射维护：http://127.0.0.1:${server.address().port}/mapping-editor.html`,
    ),
  );
}
