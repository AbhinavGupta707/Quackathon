"use client";

import type {
  HandLandmarker,
  HandLandmarkerResult,
  NormalizedLandmark
} from "@mediapipe/tasks-vision";
import {
  installMediaPipeConsoleNoiseFilter,
  withSuppressedMediaPipeConsoleNoise
} from "./mediapipeConsole";
import { MediaPipeAssetLoadError } from "./mediapipePoseRuntime";

export type HandRuntimeLandmark = {
  x: number;
  y: number;
  z?: number;
};

export type HandRuntimeDetection = {
  handednesses: string[];
  landmarks: HandRuntimeLandmark[][] | null;
};

export type HandRuntimeDiagnostics = {
  assetPreflight: "not_run" | "ok" | "cors_unverified";
  modelUrl: string;
  wasmBaseUrl: string;
};

export type HandRuntime = {
  close: () => void;
  detectForVideo: (video: HTMLVideoElement, timestamp: number) => HandRuntimeDetection;
  diagnostics: HandRuntimeDiagnostics;
};

type CreateHandRuntimeOptions = {
  modelUrl: string;
  wasmBaseUrl: string;
};

export async function createMediaPipeHandRuntime({
  modelUrl,
  wasmBaseUrl
}: CreateHandRuntimeOptions): Promise<HandRuntime> {
  const assetPreflight = await preflightModelAsset(modelUrl);
  installMediaPipeConsoleNoiseFilter();

  try {
    const { FilesetResolver, HandLandmarker } = await import("@mediapipe/tasks-vision");
    const vision = await FilesetResolver.forVisionTasks(wasmBaseUrl);
    const handLandmarker: HandLandmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: modelUrl
      },
      minHandDetectionConfidence: 0.55,
      minHandPresenceConfidence: 0.55,
      minTrackingConfidence: 0.55,
      numHands: 2,
      runningMode: "VIDEO"
    });

    return {
      close: () => handLandmarker.close(),
      detectForVideo: (video, timestamp) =>
        withSuppressedMediaPipeConsoleNoise(() =>
          normalizeDetection(handLandmarker.detectForVideo(video, timestamp))
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
      error instanceof Error ? error.message : "MediaPipe hand model or wasm asset failed to load.",
      "runtime"
    );
  }
}

async function preflightModelAsset(modelUrl: string): Promise<HandRuntimeDiagnostics["assetPreflight"]> {
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
        `MediaPipe hand model asset returned HTTP ${response.status}.`,
        "model"
      );
    }
    return "ok";
  } catch (error) {
    if (error instanceof MediaPipeAssetLoadError) {
      throw error;
    }
    return "cors_unverified";
  }
}

function normalizeDetection(result: HandLandmarkerResult): HandRuntimeDetection {
  return {
    handednesses: result.handednesses.map((categories) => categories[0]?.categoryName ?? "unknown"),
    landmarks: result.landmarks.map((landmarks) => landmarks.map(normalizeLandmark))
  };
}

function normalizeLandmark(landmark: NormalizedLandmark): HandRuntimeLandmark {
  return {
    x: landmark.x,
    y: landmark.y,
    z: landmark.z
  };
}
