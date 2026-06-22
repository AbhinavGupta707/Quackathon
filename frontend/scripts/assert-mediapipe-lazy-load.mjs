import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const scanRoots = ["app", "components", "lib"].map((segment) => path.join(root, segment));
const allowedFiles = new Set([
  path.join(root, "lib", "mediapipeHandRuntime.ts"),
  path.join(root, "lib", "mediapipePoseRuntime.ts")
]);
const forbiddenImportPattern =
  /(?:from\s+["']@mediapipe\/tasks-vision["']|import\s*\(\s*["']@mediapipe\/tasks-vision["']\s*\))/;

const violations = [];

for (const scanRoot of scanRoots) {
  await scanDirectory(scanRoot);
}

if (violations.length) {
  console.error("MediaPipe must stay out of the initial app path. Move imports behind the Action Node lazy runtime:");
  for (const file of violations) {
    console.error(`- ${path.relative(root, file)}`);
  }
  process.exit(1);
}

console.log("MediaPipe lazy-load scan passed: only lazy Action Node runtimes reference the package.");

async function scanDirectory(directory) {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      await scanDirectory(fullPath);
      continue;
    }
    if (!/\.(tsx?|jsx?)$/.test(entry.name) || allowedFiles.has(fullPath)) {
      continue;
    }
    const contents = await readFile(fullPath, "utf8");
    if (forbiddenImportPattern.test(contents)) {
      violations.push(fullPath);
    }
  }
}
