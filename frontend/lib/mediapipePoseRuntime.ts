"use client";

import type {
  NormalizedLandmark,
  PoseLandmarker,
  PoseLandmarkerResult
} from "@mediapipe/tasks-vision";
import {
  installMediaPipeConsoleNoiseFilter,
  withSuppressedMediaPipeConsoleNoise
} from "./mediapipeConsole";

export type PoseRuntimeLandmark = {
  visibility?: number;
  x: number;
  y: number;
  z?: number;
};

export type PoseRuntimeDetection = {
  landmarks: PoseRuntimeLandmark[][] | null;
};

export type PoseRuntimeDiagnostics = {
  assetPreflight: "not_run" | "ok" | "cors_unverified";
  modelUrl: string;
  wasmBaseUrl: string;
};

export type PoseRuntime = {
  close: () => void;
  detectForVideo: (video: HTMLVideoElement, timestamp: number) => PoseRuntimeDetection;
  diagnostics: PoseRuntimeDiagnostics;
};

export class MediaPipeAssetLoadError extends Error {
  constructor(
    message: string,
    readonly assetType: "model" | "wasm" | "runtime"
  ) {
    super(message);
    this.name = "MediaPipeAssetLoadError";
  }
}

type CreatePoseRuntimeOptions = {
  modelUrl: string;
  wasmBaseUrl: string;
};

export async function createMediaPipePoseRuntime({
  modelUrl,
  wasmBaseUrl
}: CreatePoseRuntimeOptions): Promise<PoseRuntime> {
  const assetPreflight = await preflightModelAsset(modelUrl);
  installMediaPipeConsoleNoiseFilter();

  try {
    const { FilesetResolver, PoseLandmarker } = await import("@mediapipe/tasks-vision");
    const vision = await FilesetResolver.forVisionTasks(wasmBaseUrl);
    const poseLandmarker: PoseLandmarker = await PoseLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: modelUrl
      },
      minPoseDetectionConfidence: 0.55,
      minPosePresenceConfidence: 0.55,
      minTrackingConfidence: 0.55,
      numPoses: 1,
      outputSegmentationMasks: false,
      runningMode: "VIDEO"
    });

    return {
      close: () => poseLandmarker.close(),
      detectForVideo: (video, timestamp) =>
        withSuppressedMediaPipeConsoleNoise(() =>
          normalizeDetection(poseLandmarker.detectForVideo(video, timestamp))
        ),
      diagnostics: {
        assetPreflight,
        modelUrl,
        wasmBaseUrl
      }
    };
  } catch (error) {
    if (error instanceof MediaPipeAssetLoadError) {
      throw error;
    }
    throw new MediaPipeAssetLoadError(
      error instanceof Error ? error.message : "MediaPipe model or wasm asset failed to load.",
      "runtime"
    );
  }
}

async function preflightModelAsset(modelUrl: string): Promise<PoseRuntimeDiagnostics["assetPreflight"]> {
  if (!modelUrl || modelUrl.startsWith("data:") || modelUrl.startsWith("blob:")) {
    return "not_run";
  }

  try {
    const response = await fetch(modelUrl, {
      cache: "no-store",
      method: "HEAD"
    });
    if (!response.ok) {
      throw new MediaPipeAssetLoadError(
        `MediaPipe model asset returned HTTP ${response.status}.`,
        "model"
      );
    }
    return "ok";
  } catch (error) {
    if (error instanceof MediaPipeAssetLoadError) {
      throw error;
    }

    // Some CDNs allow the MediaPipe loader but reject explicit browser HEAD
    // probes. Continue and let createFromOptions be the authoritative load.
    return "cors_unverified";
  }
}

function normalizeDetection(result: PoseLandmarkerResult): PoseRuntimeDetection {
  return {
    landmarks: result.landmarks.map((landmarks) => landmarks.map(normalizeLandmark))
  };
}

function normalizeLandmark(landmark: NormalizedLandmark): PoseRuntimeLandmark {
  return {
    visibility: landmark.visibility,
    x: landmark.x,
    y: landmark.y,
    z: landmark.z
  };
}
