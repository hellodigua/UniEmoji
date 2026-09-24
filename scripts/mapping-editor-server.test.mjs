import { test } from "node:test";
import http from "node:http";
import assert from "node:assert/strict";
import { mkdtempSync, copyFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createEditorServer } from "./mapping-editor-server.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
test("本地维护服务：保存、重载、校验与覆盖保护", async (t) => {
  const fixture = mkdtempSync(join(tmpdir(), "uniemoji-mapping-"));
  for (const file of ["semantic-mappings.json", "emoji.json", "index.html"])
    copyFileSync(join(root, file), join(fixture, file));
  const server = createEditorServer(fixture);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    rmSync(fixture, { recursive: true, force: true });
  });
  const base = `http://127.0.0.1:${server.address().port}`;
  const load = () => fetch(`${base}/api/mappings`).then((r) => r.json());
  const save = (session, data, headers = {}) =>
    fetch(`${base}/api/mappings`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Editor-Token": session.token,
        ...headers,
      },
      body: JSON.stringify({ revision: session.revision, data }),
    });
  await t.test("保留 40 个语义和各平台有效素材引用", async () => {
    const { data } = await load();
    assert.equal(data.semantics.length, 40);
    const catalog = JSON.parse(readFileSync(join(fixture, "emoji.json")));
    for (const row of data.semantics)
      for (const platform of data.platforms) {
        const url = row.mappings[platform.id];
        assert.ok(
          url === null ||
            catalog
              .find((p) => p.platform === platform.id)
              .emojis.some((e) => e.url === url),
        );
        if (url) assert.ok(readFileSync(join(root, url)).length > 0);
      }
  });
  await t.test(
    "修改、复用、留空均能持久化，静态官网读取同一份数据",
    async () => {
      const session = await load();
      const edited = structuredClone(session.data);
      const catalog = JSON.parse(readFileSync(join(fixture, "emoji.json")));
      const alternative = catalog
        .find((p) => p.platform === "tieba")
        .emojis.find((e) => e.url !== edited.semantics[0].mappings.tieba).url;
      edited.semantics[0].mappings.tieba = alternative;
      edited.semantics[1].mappings.tieba = alternative;
      edited.semantics[0].mappings.weibo = null;
      assert.equal((await save(session, edited)).status, 200);
      assert.deepEqual((await load()).data, edited);
      assert.deepEqual(
        await fetch(`${base}/semantic-mappings.json`).then((r) => r.json()),
        edited,
      );
      assert.deepEqual(
        JSON.parse(readFileSync(join(fixture, "semantic-mappings.json"))),
        edited,
      );
      assert.equal((await save(session, session.data)).status, 409);
      assert.deepEqual((await load()).data, edited);
    },
  );
  await t.test("拒绝跨平台图片和语义增删修改，失败不写文件", async () => {
    const session = await load();
    for (const mutate of [
      (d) => (d.semantics[0].mappings.tieba = "output/weibo/wb_12.avif"),
      (d) => (d.semantics[0].key = "other"),
      (d) => d.semantics.pop(),
      (d) => delete d.semantics[0].mappings.qq,
    ]) {
      const data = structuredClone(session.data);
      mutate(data);
      assert.equal((await save(session, data)).status, 400);
      assert.deepEqual((await load()).data, session.data);
    }
  });
  await t.test("拒绝外站写入、无凭证写入和非公开文件访问", async () => {
    const session = await load();
    assert.equal(
      (await save(session, session.data, { Origin: "https://example.com" }))
        .status,
      403,
    );
    assert.equal(
      (await save(session, session.data, { "X-Editor-Token": "" })).status,
      403,
    );
    assert.equal(
      await new Promise((resolve, reject) => {
        http
          .get(
            `${base}/api/mappings`,
            { headers: { Host: "example.com" } },
            (response) => {
              response.resume();
              resolve(response.statusCode);
            },
          )
          .on("error", reject);
      }),
      403,
    );
    assert.equal((await fetch(`${base}/.git/config`)).status, 404);
    assert.equal((await fetch(`${base}/package.json`)).status, 404);
  });
});
