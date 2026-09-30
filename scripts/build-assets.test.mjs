import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { buildAssets, cleanDist } from "./build-assets.mjs";

async function fixture(t, files = {}) {
  const root = await mkdtemp(join(tmpdir(), "uniemoji-build-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "output"));
  for (const [name, contents] of Object.entries({
    LICENSE: "project license",
    "THIRD_PARTY_NOTICES.md": "third-party notices",
    ...files,
  })) {
    await mkdir(dirname(join(root, name)), { recursive: true });
    await writeFile(join(root, name), contents);
  }
  return root;
}

test("build flattens every supported format, preserves bytes and notices, and removes stale files", async (t) => {
  const formats = ["avif", "gif", "webp", "png", "jpg", "jpeg"];
  const sources = Object.fromEntries(formats.map((format) => [
    `output/group/nested/image-${format}.${format}`, `original ${format} bytes`,
  ]));
  const root = await fixture(t, {
    ...sources,
    "output/group/ignore.txt": "not an image",
    "dist/stale.avif": "old build",
  });
  assert.equal(await buildAssets(root), formats.length);
  assert.deepEqual((await readdir(join(root, "dist"))).sort(), [
    "LICENSE", "THIRD_PARTY_NOTICES.md", ...formats.map((format) => `image-${format}.${format}`),
  ].sort());
  for (const format of formats) {
    assert.equal(await readFile(join(root, "dist", `image-${format}.${format}`), "utf8"), `original ${format} bytes`);
  }
  assert.equal(await readFile(join(root, "dist", "THIRD_PARTY_NOTICES.md"), "utf8"), "third-party notices");
});

test("case-insensitive filename collisions fail before altering the previous build", async (t) => {
  const root = await fixture(t, {
    "output/one/shared.gif": "one",
    "output/two/SHARED.GIF": "two",
    "dist/previous.gif": "previous build",
  });
  await assert.rejects(buildAssets(root), /Duplicate image filename/);
  assert.equal(await readFile(join(root, "dist/previous.gif"), "utf8"), "previous build");
});

test("a missing notice fails before altering the previous build", async (t) => {
  const root = await fixture(t, { "dist/previous.gif": "previous build" });
  await rm(join(root, "THIRD_PARTY_NOTICES.md"));
  await assert.rejects(buildAssets(root), /ENOENT/);
  assert.equal(await readFile(join(root, "dist/previous.gif"), "utf8"), "previous build");
});

test("build and clean refuse a dist symlink and preserve its target", async (t) => {
  const root = await fixture(t, { "important/keep.txt": "keep" });
  await symlink(join(root, "important"), join(root, "dist"), "dir");
  await assert.rejects(buildAssets(root), /symbolic link/);
  await assert.rejects(cleanDist(root), /symbolic link/);
  assert.equal(await readFile(join(root, "important/keep.txt"), "utf8"), "keep");
});

test("source symlinks cannot bring files from outside output into the package", async (t) => {
  const root = await fixture(t, { "private.gif": "private" });
  await symlink(join(root, "private.gif"), join(root, "output/private.gif"));
  await assert.rejects(buildAssets(root), /Symbolic links are not supported/);
});

test("the output directory itself cannot be a symlink", async (t) => {
  const root = await fixture(t, { "private/secret.gif": "private" });
  await rm(join(root, "output"), { recursive: true });
  await symlink(join(root, "private"), join(root, "output"), "dir");
  await assert.rejects(buildAssets(root), /not a symbolic link/);
});
