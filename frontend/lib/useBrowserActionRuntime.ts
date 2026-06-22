"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createHydrationActionFsm,
  type HydrationCandidateSnapshot,
  type HydrationFsmStage
} from "./hydrationActionFsm";
import type { HandRuntime, HandRuntimeDetection } from "./mediapipeHandRuntime";
import type {
  PoseRuntime,
  PoseRuntimeDetection,
  PoseRuntimeLandmark
} from "./mediapipePoseRuntime";
import type { ActionTelemetryEvaluateRequest } from "./types";

export type CameraState = "idle" | "starting" | "on" | "unsupported" | "blocked";

export type MediaPipeRuntimeState =
  | "idle"
  | "unavailable"
  | "loading"
  | "ready"
  | "degraded"
  | "error"
  | "camera_permission_denied"
  | "asset_load_failure"
  | "stale_no_pose";

export type BrowserActionRuntimeMetrics = {
  assetStatus: "not_checked" | "not_run" | "ok" | "cors_unverified" | "failed";
  detectionIntervalMs: number;
  drinkCandidateReady: boolean;
  framesAnalyzed: number;
  handAssetStatus: "not_checked" | "not_run" | "ok" | "cors_unverified" | "failed";
  handRuntimeAvailable: boolean;
  handSignalState: "idle" | "loading" | "ready" | "unavailable" | "error";
  handVisible: boolean;
  hydrationDisabledReason: string;
  hydrationFsmStage: HydrationFsmStage;
  lastCandidateAt?: string;
  lastError?: string;
  lastFrameAt?: string;
  lastHandAt?: string;
  lastPoseAt?: string;
  minHandMouthDistance?: number;
  poseVisible: boolean;
  runtimeMode: "idle" | "main_thread_throttled";
  signalWindowSeconds: number;
  slowFrameCount: number;
};

type DrinkTelemetryInput = {
  cupOrBottleContext: boolean;
  evidenceIds: string[];
  nodeId: string;
  objectKeys?: string[];
  zoneId?: string;
};

const MEDIAPIPE_WASM_BASE_URL =
  process.env.NEXT_PUBLIC_MEDIAPIPE_WASM_BASE_URL ||
  "/mediapipe/wasm";

// Default to same-origin assets prepared by `npm run setup:mediapipe`.
// Public env overrides can point at another reachable static host.
const POSE_LANDMARKER_MODEL_URL =
  process.env.NEXT_PUBLIC_MEDIAPIPE_POSE_MODEL_URL ||
  "/mediapipe/models/pose_landmarker_lite.task";

const HAND_LANDMARKER_MODEL_URL =
  process.env.NEXT_PUBLIC_MEDIAPIPE_HAND_MODEL_URL ||
  "/mediapipe/models/hand_landmarker.task";

const DEFAULT_DETECTION_INTERVAL_MS = 180;
const DEGRADED_DETECTION_INTERVAL_MS = 360;
const UI_SAMPLE_INTERVAL_MS = 650;
const CANDIDATE_VALID_MS = 12000;
const STALE_POSE_MS = 4500;
const STALE_HAND_MS = 4500;
const VISIBILITY_THRESHOLD = 0.45;
const SLOW_DETECTION_MS = 120;
const HAND_PROXIMITY_LANDMARKS = [0, 4, 8, 12, 16, 20];

export function browserCameraSupported(): boolean {
  return typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
}

export function useBrowserActionRuntime() {
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [mediaPipeState, setMediaPipeState] = useState<MediaPipeRuntimeState>("idle");
  const [metrics, setMetrics] = useState<BrowserActionRuntimeMetrics>(() => emptyMetrics());

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const poseRuntimeRef = useRef<PoseRuntime | null>(null);
  const handRuntimeRef = useRef<HandRuntime | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastDetectAtRef = useRef(0);
  const lastUiSampleAtRef = useRef(0);
  const latestFrameAtRef = useRef(0);
  const latestHandAtRef = useRef(0);
  const latestPoseAtRef = useRef(0);
  const framesAnalyzedRef = useRef(0);
  const slowFrameCountRef = useRef(0);
  const consecutiveDetectionErrorsRef = useRef(0);
  const consecutiveHandErrorsRef = useRef(0);
  const detectionIntervalRef = useRef(DEFAULT_DETECTION_INTERVAL_MS);
  const drinkObjectContextRef = useRef(false);
  const hydrationFsmRef = useRef(createHydrationActionFsm());
  const latestDrinkCandidateRef = useRef<HydrationCandidateSnapshot | null>(null);
  const startingRef = useRef(false);

  useEffect(() => {
    if (!browserCameraSupported()) {
      setCameraState("unsupported");
    }
  }, []);

  const stop = useCallback(() => {
    if (animationFrameRef.current !== null) {
      window.cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    poseRuntimeRef.current?.close();
    poseRuntimeRef.current = null;
    handRuntimeRef.current?.close();
    handRuntimeRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    lastDetectAtRef.current = 0;
    lastUiSampleAtRef.current = 0;
    latestFrameAtRef.current = 0;
    latestHandAtRef.current = 0;
    latestPoseAtRef.current = 0;
    framesAnalyzedRef.current = 0;
    slowFrameCountRef.current = 0;
    consecutiveDetectionErrorsRef.current = 0;
    consecutiveHandErrorsRef.current = 0;
    detectionIntervalRef.current = DEFAULT_DETECTION_INTERVAL_MS;
    hydrationFsmRef.current.clear();
    latestDrinkCandidateRef.current = null;
    startingRef.current = false;
    setMetrics(emptyMetrics());
    setMediaPipeState("idle");
    setCameraState(browserCameraSupported() ? "idle" : "unsupported");
  }, []);

  async function start() {
    if (!browserCameraSupported()) {
      setCameraState("unsupported");
      setMediaPipeState("unavailable");
      return { ok: false, message: "This browser does not expose webcam access." };
    }

    if (startingRef.current || cameraState === "on") {
      return { ok: true };
    }

    startingRef.current = true;
    setCameraState("starting");
    setMediaPipeState("idle");
    setMetrics(emptyMetrics());

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: "user",
          width: { ideal: 960 },
          height: { ideal: 540 }
        }
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setCameraState("on");
      setMediaPipeState("loading");

      const { createMediaPipePoseRuntime } = await import("./mediapipePoseRuntime");
      const poseRuntime = await createMediaPipePoseRuntime({
        modelUrl: POSE_LANDMARKER_MODEL_URL,
        wasmBaseUrl: MEDIAPIPE_WASM_BASE_URL
      });

      let handRuntime: HandRuntime | null = null;
      let handAssetStatus: BrowserActionRuntimeMetrics["handAssetStatus"] = "not_checked";
      let handRuntimeError: string | undefined;
      try {
        const { createMediaPipeHandRuntime } = await import("./mediapipeHandRuntime");
        handRuntime = await createMediaPipeHandRuntime({
          modelUrl: HAND_LANDMARKER_MODEL_URL,
          wasmBaseUrl: MEDIAPIPE_WASM_BASE_URL
        });
        handAssetStatus = handRuntime.diagnostics.assetPreflight;
      } catch (handError) {
        handRuntimeError =
          handError instanceof Error
            ? handError.message
            : "MediaPipe hand landmark runtime failed to initialize.";
      }

      poseRuntimeRef.current = poseRuntime;
      handRuntimeRef.current = handRuntime;
      setMetrics((previous) => ({
        ...previous,
        assetStatus: poseRuntime.diagnostics.assetPreflight,
        detectionIntervalMs: detectionIntervalRef.current,
        handAssetStatus,
        handRuntimeAvailable: Boolean(handRuntime),
        handSignalState: handRuntime ? "ready" : "unavailable",
        hydrationDisabledReason:
          handRuntimeError ||
          "Waiting for cup/bottle context and a hand-to-mouth approach sequence.",
        lastError: undefined,
        runtimeMode: "main_thread_throttled"
      }));
      setMediaPipeState(handRuntime ? "ready" : "degraded");
      animationFrameRef.current = window.requestAnimationFrame(runDetectionLoop);
      return { ok: true };
    } catch (error) {
      const { message, state } = classifyStartupError(error);
      setMetrics((previous) => ({
        ...previous,
        assetStatus: state === "asset_load_failure" ? "failed" : previous.assetStatus,
        lastError: message
      }));
      setMediaPipeState(state);
      setCameraState(state === "camera_permission_denied" ? "blocked" : streamRef.current ? "on" : "blocked");
      return { ok: false, message };
    } finally {
      startingRef.current = false;
    }
  }

  const setDrinkObjectContext = useCallback((enabled: boolean) => {
    drinkObjectContextRef.current = enabled;
    if (!enabled) {
      hydrationFsmRef.current.clear();
      latestDrinkCandidateRef.current = null;
    }
    setMetrics((previous) => ({
      ...previous,
      drinkCandidateReady: enabled ? previous.drinkCandidateReady : false,
      hydrationDisabledReason: enabled
        ? previous.hydrationDisabledReason
        : "Cup, bottle, or water context is required before drink-action submission."
    }));
  }, []);

  const captureFrame = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      return null;
    }

    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
      return null;
    }

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      return null;
    }

    context.drawImage(video, 0, 0, width, height);
    return new Promise((resolve) => {
      canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.82);
    });
  }, []);

  const buildDrinkTelemetry = useCallback(
    ({
      cupOrBottleContext,
      evidenceIds,
      nodeId,
      objectKeys = [],
      zoneId
    }: DrinkTelemetryInput): ActionTelemetryEvaluateRequest | null => {
      const candidate = latestDrinkCandidateRef.current;
      if (
        !cupOrBottleContext ||
        !candidate ||
        Date.now() - Date.parse(candidate.occurredAt) > CANDIDATE_VALID_MS
      ) {
        return null;
      }

      return {
        occurred_at: candidate.occurredAt,
        source: "browser_mediapipe",
        source_node_id: nodeId,
        zone_id: zoneId,
        evidence_ids: evidenceIds,
        object_keys: cupOrBottleContext ? objectKeys.length ? objectKeys : ["cup_or_bottle_context"] : [],
        object_visible: cupOrBottleContext,
        hand_object_contact: true,
        hand_to_mouth_motion: true,
        object_near_mouth: true,
        explicit_action_telemetry: true,
        temporal_window_seconds: candidate.temporalWindowSeconds,
        confidence: candidate.confidence,
        score: candidate.score,
        metadata: {
          raw_video_stored: false,
          raw_frames_sent: false,
          third_party_frames_sent: false,
          adapter_version: "browser_mediapipe_pose_hand_fsm_v1",
          model: "mediapipe_pose_landmarker_lite_and_hand_landmarker",
          pose_model_url: POSE_LANDMARKER_MODEL_URL,
          hand_model_url: HAND_LANDMARKER_MODEL_URL,
          wasm_base_url: MEDIAPIPE_WASM_BASE_URL,
          cup_or_bottle_context: cupOrBottleContext,
          drink_context_object_keys: objectKeys,
          drink_context_evidence_ids: evidenceIds,
          hydration_fsm_state: "candidate_ready",
          object_visibility_is_context_only: true,
          object_context_required: true,
          object_context_source: "afferens_latest_observation",
          pose_only_wrist_near_mouth_rejected: true,
          hand_landmark_required: true,
          hand_signal_source: "mediapipe_hand_landmarker",
          hand_object_contact_proxy: "hand_landmark_with_cup_or_bottle_context_gate",
          object_near_mouth_proxy: "cup_or_bottle_context_plus_hand_mouth_fsm",
          required_sequence: ["object_context", "hand_approach", "mouth_dwell", "exit_cooldown"],
          detection_interval_ms: detectionIntervalRef.current,
          runtime_mode: "main_thread_throttled",
          mouth_dwell_ms: candidate.dwellMs,
          exit_distance: candidate.exitDistance,
          hand_mouth_approach_delta: candidate.handMouthApproachDelta,
          min_hand_mouth_distance: candidate.minHandMouthDistance,
          patient_safe_summary: "possible drink-action candidate; not confirmed hydration"
        }
      };
    },
    []
  );

  useEffect(() => stop, [stop]);

  function runDetectionLoop(timestamp: number) {
    const video = videoRef.current;
    const runtime = poseRuntimeRef.current;

    if (!video || !runtime || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      animationFrameRef.current = window.requestAnimationFrame(runDetectionLoop);
      return;
    }

    if (timestamp - lastDetectAtRef.current >= detectionIntervalRef.current) {
      lastDetectAtRef.current = timestamp;
      latestFrameAtRef.current = Date.now();
      try {
        const detectStartedAt = performance.now();
        const poseResult = runtime.detectForVideo(video, timestamp);
        const handResult = detectHands(video, timestamp);
        const detectDuration = performance.now() - detectStartedAt;
        consecutiveDetectionErrorsRef.current = 0;
        framesAnalyzedRef.current += 1;
        updatePerformanceMode(detectDuration);
        updateDrinkCandidate(poseResult, handResult, timestamp);
      } catch (error) {
        consecutiveDetectionErrorsRef.current += 1;
        setMetrics((previous) => ({
          ...previous,
          lastError:
            error instanceof Error ? error.message : "MediaPipe pose detection failed during runtime."
        }));
        setMediaPipeState(consecutiveDetectionErrorsRef.current >= 3 ? "error" : "degraded");
      }
    }

    animationFrameRef.current = window.requestAnimationFrame(runDetectionLoop);
  }

  function detectHands(video: HTMLVideoElement, timestamp: number): HandRuntimeDetection | null {
    const handRuntime = handRuntimeRef.current;
    if (!handRuntime) {
      return null;
    }

    try {
      const result = handRuntime.detectForVideo(video, timestamp);
      consecutiveHandErrorsRef.current = 0;
      return result;
    } catch (error) {
      consecutiveHandErrorsRef.current += 1;
      if (consecutiveHandErrorsRef.current >= 3) {
        handRuntime.close();
        handRuntimeRef.current = null;
        setMediaPipeState("degraded");
        setMetrics((previous) => ({
          ...previous,
          handRuntimeAvailable: false,
          handSignalState: "error",
          hydrationDisabledReason:
            error instanceof Error
              ? error.message
              : "Hand landmark detection failed, so hydration stays inconclusive."
        }));
      }
      return null;
    }
  }

  function updatePerformanceMode(detectDurationMs: number) {
    if (detectDurationMs > SLOW_DETECTION_MS) {
      slowFrameCountRef.current += 1;
      detectionIntervalRef.current = DEGRADED_DETECTION_INTERVAL_MS;
      setMediaPipeState("degraded");
      return;
    }

    if (detectionIntervalRef.current !== DEFAULT_DETECTION_INTERVAL_MS) {
      detectionIntervalRef.current = DEFAULT_DETECTION_INTERVAL_MS;
      setMediaPipeState("ready");
    }
  }

  function updateDrinkCandidate(
    poseResult: PoseRuntimeDetection,
    handResult: HandRuntimeDetection | null,
    timestamp: number
  ) {
    const wallClockMs = Date.now();
    const poseSignal = readPoseSignal(poseResult);
    const handSignal = poseSignal.mouth ? readHandMouthSignal(handResult, poseSignal.mouth) : null;

    if (poseSignal.poseVisible) {
      latestPoseAtRef.current = wallClockMs;
    }
    if (handSignal?.handVisible) {
      latestHandAtRef.current = wallClockMs;
    }

    const fsmSnapshot = hydrationFsmRef.current.update({
      handMouthDistance: handSignal?.distance,
      handRuntimeAvailable: Boolean(handRuntimeRef.current),
      handVisible: Boolean(handSignal?.handVisible),
      mouthVisible: poseSignal.mouthVisible,
      objectContext: drinkObjectContextRef.current,
      poseVisible: poseSignal.poseVisible,
      timestamp,
      wallClockMs
    });
    latestDrinkCandidateRef.current = fsmSnapshot.candidate;

    if (timestamp - lastUiSampleAtRef.current >= UI_SAMPLE_INTERVAL_MS) {
      lastUiSampleAtRef.current = timestamp;
      const latestCandidate = latestDrinkCandidateRef.current;
      const candidateReady =
        Boolean(latestCandidate) &&
        Date.now() - Date.parse(latestCandidate?.occurredAt ?? "") <= CANDIDATE_VALID_MS;
      const poseIsFresh =
        latestPoseAtRef.current > 0 && Date.now() - latestPoseAtRef.current <= STALE_POSE_MS;
      const handIsFresh =
        latestHandAtRef.current > 0 && Date.now() - latestHandAtRef.current <= STALE_HAND_MS;

      if (!poseIsFresh && framesAnalyzedRef.current > 0) {
        setMediaPipeState("stale_no_pose");
      } else if (poseIsFresh && consecutiveDetectionErrorsRef.current < 3) {
        setMediaPipeState(detectionIntervalRef.current > DEFAULT_DETECTION_INTERVAL_MS ? "degraded" : "ready");
      }

      setMetrics((previous) => ({
        ...previous,
        detectionIntervalMs: detectionIntervalRef.current,
        drinkCandidateReady: candidateReady,
        framesAnalyzed: framesAnalyzedRef.current,
        handRuntimeAvailable: Boolean(handRuntimeRef.current),
        handSignalState: handRuntimeRef.current ? (handIsFresh ? "ready" : "loading") : "unavailable",
        handVisible: handIsFresh,
        hydrationDisabledReason: fsmSnapshot.disabledReason,
        hydrationFsmStage: fsmSnapshot.stage,
        lastCandidateAt: latestCandidate?.occurredAt,
        lastFrameAt: latestFrameAtRef.current ? new Date(latestFrameAtRef.current).toISOString() : undefined,
        lastHandAt: latestHandAtRef.current ? new Date(latestHandAtRef.current).toISOString() : undefined,
        lastPoseAt: latestPoseAtRef.current ? new Date(latestPoseAtRef.current).toISOString() : undefined,
        minHandMouthDistance: fsmSnapshot.minHandMouthDistance,
        poseVisible: poseIsFresh,
        runtimeMode: "main_thread_throttled",
        signalWindowSeconds: latestCandidate?.temporalWindowSeconds ?? 0,
        slowFrameCount: slowFrameCountRef.current
      }));
    }
  }

  return {
    buildDrinkTelemetry,
    cameraState,
    captureFrame,
    mediaPipeState,
    metrics,
    setDrinkObjectContext,
    start,
    stop,
    videoRef
  };
}

function emptyMetrics(): BrowserActionRuntimeMetrics {
  return {
    assetStatus: "not_checked",
    detectionIntervalMs: DEFAULT_DETECTION_INTERVAL_MS,
    drinkCandidateReady: false,
    framesAnalyzed: 0,
    handAssetStatus: "not_checked",
    handRuntimeAvailable: false,
    handSignalState: "idle",
    handVisible: false,
    hydrationDisabledReason: "Start the Action Node and provide cup/bottle context.",
    hydrationFsmStage: "waiting_context",
    poseVisible: false,
    runtimeMode: "idle",
    signalWindowSeconds: 0,
    slowFrameCount: 0
  };
}

function readPoseSignal(result: PoseRuntimeDetection): {
  mouth: PoseRuntimeLandmark | null;
  mouthVisible: boolean;
  poseVisible: boolean;
} {
  const landmarks = result.landmarks?.[0];
  if (!landmarks) {
    return {
      mouth: null,
      mouthVisible: false,
      poseVisible: false
    };
  }

  const mouth = midpoint(landmarks[9], landmarks[10]);

  return {
    mouth,
    mouthVisible: Boolean(mouth),
    poseVisible: true
  };
}

function readHandMouthSignal(
  result: HandRuntimeDetection | null,
  mouth: PoseRuntimeLandmark
): { distance: number; handVisible: boolean } | null {
  const hands = result?.landmarks;
  if (!hands?.length) {
    return null;
  }

  const distances = hands.flatMap((hand) =>
    HAND_PROXIMITY_LANDMARKS.map((index) => hand[index])
      .filter((landmark): landmark is PoseRuntimeLandmark => Boolean(landmark))
      .map((landmark) => distance2d(landmark, mouth))
  );

  if (!distances.length) {
    return null;
  }

  return {
    distance: Math.min(...distances),
    handVisible: true
  };
}

function visibleLandmark(landmark?: PoseRuntimeLandmark): PoseRuntimeLandmark | null {
  if (!landmark || (landmark.visibility ?? 1) < VISIBILITY_THRESHOLD) {
    return null;
  }
  return landmark;
}

function midpoint(
  first?: PoseRuntimeLandmark,
  second?: PoseRuntimeLandmark
): PoseRuntimeLandmark | null {
  const visibleFirst = visibleLandmark(first);
  const visibleSecond = visibleLandmark(second);

  if (!visibleFirst || !visibleSecond) {
    return null;
  }

  return {
    visibility: Math.min(visibleFirst.visibility ?? 1, visibleSecond.visibility ?? 1),
    x: (visibleFirst.x + visibleSecond.x) / 2,
    y: (visibleFirst.y + visibleSecond.y) / 2,
    z: ((visibleFirst.z ?? 0) + (visibleSecond.z ?? 0)) / 2
  };
}

function distance2d(first: PoseRuntimeLandmark, second: PoseRuntimeLandmark): number {
  return Math.hypot(first.x - second.x, first.y - second.y);
}

function classifyStartupError(error: unknown): { message: string; state: MediaPipeRuntimeState } {
  const message =
    error instanceof Error ? error.message : "MediaPipe or camera initialization failed.";
  const errorName = error instanceof Error ? error.name : "";

  if (errorName === "NotAllowedError" || errorName === "SecurityError") {
    return {
      message: "Camera permission was denied. Allow camera access to start the Action Node.",
      state: "camera_permission_denied"
    };
  }

  if (errorName === "NotFoundError" || errorName === "OverconstrainedError") {
    return {
      message: "No usable camera was found for this browser Action Node.",
      state: "unavailable"
    };
  }

  if (errorName === "MediaPipeAssetLoadError" || /model|wasm|asset|fetch|load/i.test(message)) {
    return {
      message,
      state: "asset_load_failure"
    };
  }

  return {
    message,
    state: "error"
  };
}
