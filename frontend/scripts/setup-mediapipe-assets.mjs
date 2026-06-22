import { copyFile, mkdir, stat } from "node:fs/promises";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
const wasmSourceDir = path.join(frontendRoot, "node_modules", "@mediapipe", "tasks-vision", "wasm");
const publicRoot = path.join(frontendRoot, "public", "mediapipe");
const wasmTargetDir = path.join(publicRoot, "wasm");
const modelTargetDir = path.join(publicRoot, "models");

const wasmFiles = [
  "vision_wasm_internal.js",
  "vision_wasm_internal.wasm",
  "vision_wasm_module_internal.js",
  "vision_wasm_module_internal.wasm",
  "vision_wasm_nosimd_internal.js",
  "vision_wasm_nosimd_internal.wasm"
];

const models = [
  {
    name: "pose_landmarker_lite.task",
    url: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
  },
  {
    name: "hand_landmarker.task",
    url: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
  }
];

await mkdir(wasmTargetDir, { recursive: true });
await mkdir(modelTargetDir, { recursive: true });

for (const file of wasmFiles) {
  await copyFile(path.join(wasmSourceDir, file), path.join(wasmTargetDir, file));
  console.log(`copied wasm/${file}`);
}

for (const model of models) {
  const target = path.join(modelTargetDir, model.name);
  if (await exists(target)) {
    console.log(`kept models/${model.name}`);
    continue;
  }
  await download(model.url, target);
  console.log(`downloaded models/${model.name}`);
}

console.log("MediaPipe browser assets are ready under frontend/public/mediapipe.");

async function exists(filePath) {
  try {
    const fileStat = await stat(filePath);
    return fileStat.isFile() && fileStat.size > 0;
  } catch {
    return false;
  }
}

async function download(url, target, redirectCount = 0) {
  if (redirectCount > 5) {
    throw new Error(`Too many redirects while downloading ${url}`);
  }

  await new Promise((resolve, reject) => {
    const request = https.get(url, (response) => {
      if (
        response.statusCode &&
        response.statusCode >= 300 &&
        response.statusCode < 400 &&
        response.headers.location
      ) {
        response.resume();
        download(new URL(response.headers.location, url).toString(), target, redirectCount + 1)
          .then(resolve)
          .catch(reject);
        return;
      }

      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`Download failed for ${url}: HTTP ${response.statusCode}`));
        return;
      }

      import("node:fs").then(({ createWriteStream }) => {
        const file = createWriteStream(target);
        response.pipe(file);
        file.on("finish", () => {
          file.close(resolve);
        });
        file.on("error", reject);
      }).catch(reject);
    });

    request.on("error", reject);
  });
}
