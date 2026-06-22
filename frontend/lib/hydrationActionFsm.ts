import type { WellnessConfidence } from "./types";

export type HydrationFsmStage =
  | "waiting_context"
  | "waiting_pose"
  | "waiting_hand"
  | "tracking_approach"
  | "mouth_dwell"
  | "exit_cooldown"
  | "candidate_ready";

export type HydrationCandidateSnapshot = {
  confidence: WellnessConfidence;
  dwellMs: number;
  exitDistance: number;
  handMouthApproachDelta: number;
  minHandMouthDistance: number;
  occurredAt: string;
  score: number;
  temporalWindowSeconds: number;
};

export type HydrationFrameSignal = {
  handMouthDistance?: number;
  handRuntimeAvailable: boolean;
  handVisible: boolean;
  mouthVisible: boolean;
  objectContext: boolean;
  phoneContext?: boolean;
  poseVisible: boolean;
  stale?: boolean;
  timestamp: number;
  wallClockMs: number;
};

export type HydrationFsmSnapshot = {
  candidate: HydrationCandidateSnapshot | null;
  disabledReason: string;
  minHandMouthDistance?: number;
  stage: HydrationFsmStage;
};

const APPROACH_ENTRY_DISTANCE = 0.22;
const APPROACH_REQUIRED_DELTA = 0.055;
const CANDIDATE_VALID_MS = 12000;
const COOLDOWN_MS = 2800;
const DWELL_MS = 850;
const EXIT_DISTANCE = 0.19;
const NEAR_MOUTH_DISTANCE = 0.125;

export function createHydrationActionFsm() {
  let approachStartedAt = 0;
  let candidate: HydrationCandidateSnapshot | null = null;
  let cooldownUntil = 0;
  let dwellStartedAt = 0;
  let farthestDistance = 0;
  let minDistance = Number.POSITIVE_INFINITY;
  let stage: HydrationFsmStage = "waiting_context";

  function reset(nextStage: HydrationFsmStage) {
    approachStartedAt = 0;
    dwellStartedAt = 0;
    farthestDistance = 0;
    minDistance = Number.POSITIVE_INFINITY;
    stage = nextStage;
  }

  function update(signal: HydrationFrameSignal): HydrationFsmSnapshot {
    const freshCandidate =
      candidate && signal.wallClockMs - Date.parse(candidate.occurredAt) <= CANDIDATE_VALID_MS
        ? candidate
        : null;
    candidate = freshCandidate;

    if (signal.timestamp < cooldownUntil) {
      stage = candidate ? "candidate_ready" : "exit_cooldown";
      return snapshot("Waiting for cooldown before another drink-action candidate.");
    }

    if (!signal.objectContext) {
      reset("waiting_context");
      return snapshot("Cup, bottle, or water context is required; visibility alone is still context only.");
    }

    if (signal.phoneContext) {
      reset("waiting_hand");
      return snapshot("Phone-to-face context is not treated as hydration.");
    }

    if (signal.stale || !signal.poseVisible || !signal.mouthVisible) {
      reset("waiting_pose");
      return snapshot("Fresh pose and mouth landmarks are required.");
    }

    if (!signal.handRuntimeAvailable) {
      reset("waiting_hand");
      return snapshot("Hand landmark runtime is unavailable, so pose-only hydration stays inconclusive.");
    }

    if (!signal.handVisible || typeof signal.handMouthDistance !== "number") {
      if (stage === "mouth_dwell" && dwellStartedAt > 0) {
        const dwellMs = signal.timestamp - dwellStartedAt;
        if (dwellMs >= DWELL_MS) {
          candidate = buildCandidate(signal, dwellMs, minDistance, EXIT_DISTANCE);
          cooldownUntil = signal.timestamp + COOLDOWN_MS;
          reset("candidate_ready");
          return snapshot("Drink-action sequence completed; ready for backend review.");
        }
      }

      reset("waiting_hand");
      return snapshot("Fresh hand landmarks are required; wrist-near-mouth pose alone is not enough.");
    }

    const distance = signal.handMouthDistance;
    minDistance = Math.min(minDistance, distance);
    farthestDistance = Math.max(farthestDistance, distance);

    if (distance >= APPROACH_ENTRY_DISTANCE && stage !== "mouth_dwell") {
      stage = "tracking_approach";
      return snapshot("Hand context is visible; waiting for a hand-to-mouth approach.");
    }

    const hasApproach = farthestDistance - distance >= APPROACH_REQUIRED_DELTA;

    if (!hasApproach && stage !== "mouth_dwell") {
      stage = "tracking_approach";
      return snapshot("Waiting for hand-to-mouth approach, not just a hand near the face.");
    }

    if (distance <= NEAR_MOUTH_DISTANCE) {
      if (!approachStartedAt) {
        approachStartedAt = signal.timestamp;
      }
      if (!dwellStartedAt) {
        dwellStartedAt = signal.timestamp;
      }
      stage = "mouth_dwell";
      return snapshot("Hand reached mouth area; waiting for brief dwell and exit.");
    }

    if (stage === "mouth_dwell" && dwellStartedAt > 0) {
      const dwellMs = signal.timestamp - dwellStartedAt;
      if (dwellMs >= DWELL_MS && distance >= EXIT_DISTANCE) {
        candidate = buildCandidate(signal, dwellMs, minDistance, distance);
        cooldownUntil = signal.timestamp + COOLDOWN_MS;
        reset("candidate_ready");
        return snapshot("Drink-action sequence completed; ready for backend review.");
      }
    }

    stage = approachStartedAt ? "mouth_dwell" : "tracking_approach";
    return snapshot("Waiting for mouth dwell and exit before submitting.");
  }

  function getSnapshot(wallClockMs = Date.now()): HydrationFsmSnapshot {
    if (candidate && wallClockMs - Date.parse(candidate.occurredAt) > CANDIDATE_VALID_MS) {
      candidate = null;
      reset("waiting_context");
    }
    return snapshot("Waiting for object context, hand approach, mouth dwell, and exit.");
  }

  function clear() {
    candidate = null;
    cooldownUntil = 0;
    reset("waiting_context");
  }

  function snapshot(disabledReason: string): HydrationFsmSnapshot {
    return {
      candidate,
      disabledReason: candidate ? "" : disabledReason,
      minHandMouthDistance: Number.isFinite(minDistance) ? minDistance : undefined,
      stage
    };
  }

  return {
    clear,
    getSnapshot,
    update
  };
}

function buildCandidate(
  signal: HydrationFrameSignal,
  dwellMs: number,
  minHandMouthDistance: number,
  exitDistance: number
): HydrationCandidateSnapshot {
  const approachDelta = Math.max(0, Math.min(0.35, Math.abs(exitDistance - minHandMouthDistance)));
  const temporalWindowSeconds = Math.max(1, dwellMs / 1000);
  const score = clamp(0.58 + dwellMs / 5000 + approachDelta, 0.62, 0.9);

  return {
    confidence: score >= 0.78 ? "medium" : "low",
    dwellMs,
    exitDistance,
    handMouthApproachDelta: approachDelta,
    minHandMouthDistance,
    occurredAt: new Date(signal.wallClockMs).toISOString(),
    score,
    temporalWindowSeconds
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
