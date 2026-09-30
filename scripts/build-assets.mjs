import { copyFile, lstat, mkdtemp, readdir, rename, rm } from "node:fs/promises";
import { basename, dirname, extname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const imageExtensions = new Set([".avif", ".gif", ".webp", ".png", ".jpg", ".jpeg"]);
const noticeNames = ["LICENSE", "THIRD_PARTY_NOTICES.md"];

async function assertDirectoryOrMissing(path) {
  try {
    const stat = await lstat(path);
    if (!stat.isDirectory() || stat.isSymbolicLink()) {
      throw new Error(`Refusing to replace a non-directory or symbolic link: ${path}`);
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

async function collectImages(directory) {
  const stat = await lstat(directory);
  if (!stat.isDirectory() || stat.isSymbolicLink()) {
    throw new Error(`Image source must be a directory, not a symbolic link: ${directory}`);
  }
  const images = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isSymbolicLink()) {
      throw new Error(`Symbolic links are not supported in output: ${path}`);
    }
    if (entry.isDirectory()) images.push(...(await collectImages(path)));
    else if (entry.isFile() && imageExtensions.has(extname(entry.name).toLowerCase())) {
      images.push(path);
    }
  }
  return images.sort();
}

export async function cleanDist(root = projectRoot) {
  const destination = join(resolve(root), "dist");
  await assertDirectoryOrMissing(destination);
  await rm(destination, { recursive: true, force: true });
}

export async function buildAssets(root = projectRoot) {
  root = resolve(root);
  const destination = join(root, "dist");
  await assertDirectoryOrMissing(destination);
  const files = await collectImages(join(root, "output"));
  const filenames = new Map();
  for (const file of files) {
    // Case-insensitive checks also protect archives unpacked on macOS/Windows.
    const name = basename(file).toLowerCase();
    if (filenames.has(name)) {
      throw new Error(`Duplicate image filename: ${filenames.get(name)} and ${file}`);
    }
    filenames.set(name, file);
  }
  for (const name of noticeNames) {
    const stat = await lstat(join(root, name));
    if (!stat.isFile() || stat.isSymbolicLink()) {
      throw new Error(`Required notice must be a regular file: ${name}`);
    }
  }

  // Stage a complete flat package before replacing the previous build.
  const staging = await mkdtemp(join(root, ".dist-build-"));
  try {
    for (const file of files) await copyFile(file, join(staging, basename(file)));
    for (const name of noticeNames) await copyFile(join(root, name), join(staging, name));
    await cleanDist(root);
    await rename(staging, destination);
  } finally {
    await rm(staging, { recursive: true, force: true });
  }
  return files.length;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    if (process.argv.slice(2).length === 1 && process.argv[2] === "--clean") {
      await cleanDist();
      console.log("Dist directory cleaned");
    } else if (process.argv.length === 2) {
      const count = await buildAssets();
      console.log(`Copied ${count} images and ${noticeNames.length} notices to dist/`);
    } else {
      throw new Error("Usage: node scripts/build-assets.mjs [--clean]");
    }
  } catch (error) {
    console.error(`Asset build failed: ${error.message}`);
    process.exitCode = 1;
  }
}
