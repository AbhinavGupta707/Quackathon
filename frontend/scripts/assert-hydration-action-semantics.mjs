import { readFile } from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";
import ts from "typescript";

const root = process.cwd();
const sourcePath = path.join(root, "lib", "hydrationActionFsm.ts");
const source = await readFile(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022
  },
  fileName: sourcePath
}).outputText;

const sandboxModule = { exports: {} };
vm.runInNewContext(compiled, {
  exports: sandboxModule.exports,
  module: sandboxModule,
  require: () => ({})
});

const { createHydrationActionFsm } = sandboxModule.exports;

assertNoCandidate("bottle visible only", [
  frame({ objectContext: true, poseVisible: true, mouthVisible: true, handVisible: false }),
  frame({ objectContext: true, poseVisible: true, mouthVisible: true, handVisible: false }, 250)
]);

assertNoCandidate("cup visible only", [
  frame({ objectContext: true, poseVisible: true, mouthVisible: true, handVisible: false }),
  frame({ objectContext: true, poseVisible: true, mouthVisible: true, handVisible: false }, 500)
]);

assertNoCandidate("hand-to-face without cup context", approachFrames({ objectContext: false }));
assertNoCandidate("static hand already near mouth with cup context", [
  frame({ handMouthDistance: 0.1, handVisible: true, mouthVisible: true, objectContext: true, poseVisible: true }),
  frame({ handMouthDistance: 0.1, handVisible: true, mouthVisible: true, objectContext: true, poseVisible: true }, 900),
  frame({ handMouthDistance: 0.22, handVisible: true, mouthVisible: true, objectContext: true, poseVisible: true }, 1300)
]);
assertNoCandidate("phone-to-face context", approachFrames({ objectContext: true, phoneContext: true }));
assertNoCandidate("stale pose", approachFrames({ objectContext: true, stale: true }));
assertCandidate("object context plus hand approach, mouth dwell, and exit", approachFrames({ objectContext: true }));

console.log("Hydration FSM scan passed: weak visibility, pose-only, phone, and stale signals stay inconclusive.");

function assertNoCandidate(name, frames) {
  const fsm = createHydrationActionFsm();
  const candidate = runFrames(fsm, frames);
  if (candidate) {
    throw new Error(`${name} unexpectedly produced a drink candidate.`);
  }
}

function assertCandidate(name, frames) {
  const fsm = createHydrationActionFsm();
  const candidate = runFrames(fsm, frames);
  if (!candidate) {
    throw new Error(`${name} did not produce the expected drink candidate.`);
  }
}

function runFrames(fsm, frames) {
  let snapshot = fsm.getSnapshot(1_700_000_000_000);
  for (const signal of frames) {
    snapshot = fsm.update(signal);
  }
  return snapshot.candidate;
}

function approachFrames(overrides = {}) {
  return [
    frame({ handMouthDistance: 0.25, handVisible: true, mouthVisible: true, poseVisible: true, ...overrides }),
    frame({ handMouthDistance: 0.18, handVisible: true, mouthVisible: true, poseVisible: true, ...overrides }, 220),
    frame({ handMouthDistance: 0.1, handVisible: true, mouthVisible: true, poseVisible: true, ...overrides }, 500),
    frame({ handMouthDistance: 0.1, handVisible: true, mouthVisible: true, poseVisible: true, ...overrides }, 1450),
    frame({ handMouthDistance: 0.22, handVisible: true, mouthVisible: true, poseVisible: true, ...overrides }, 1750)
  ];
}

function frame(overrides = {}, offset = 0) {
  return {
    handRuntimeAvailable: true,
    handVisible: false,
    mouthVisible: false,
    objectContext: false,
    poseVisible: false,
    timestamp: offset,
    wallClockMs: 1_700_000_000_000 + offset,
    ...overrides
  };
}
