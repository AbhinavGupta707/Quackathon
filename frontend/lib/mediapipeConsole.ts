"use client";

const SUPPRESSED_MEDIAPIPE_CONSOLE_PATTERNS = [
  /^INFO:\s*Created TensorFlow Lite XNNPACK delegate for CPU\.?$/i
];

let consoleNoiseFilterInstalled = false;

export function installMediaPipeConsoleNoiseFilter() {
  if (consoleNoiseFilterInstalled || typeof console === "undefined") {
    return;
  }

  const originalError = console.error.bind(console);
  const originalWarn = console.warn.bind(console);

  console.error = (...args: Parameters<typeof console.error>) => {
    if (isSuppressedMediaPipeConsoleNoise(args)) {
      return;
    }
    originalError(...args);
  };

  console.warn = (...args: Parameters<typeof console.warn>) => {
    if (isSuppressedMediaPipeConsoleNoise(args)) {
      return;
    }
    originalWarn(...args);
  };

  consoleNoiseFilterInstalled = true;
}

export function withSuppressedMediaPipeConsoleNoise<T>(operation: () => T): T {
  if (typeof console === "undefined") {
    return operation();
  }

  const originalError = console.error;
  console.error = (...args: Parameters<typeof console.error>) => {
    const message = args.map(formatConsoleArg).join(" ").trim();
    if (SUPPRESSED_MEDIAPIPE_CONSOLE_PATTERNS.some((pattern) => pattern.test(message))) {
      return;
    }
    originalError(...args);
  };

  try {
    return operation();
  } finally {
    console.error = originalError;
  }
}

function isSuppressedMediaPipeConsoleNoise(args: unknown[]): boolean {
  const message = args.map(formatConsoleArg).join(" ").trim();
  return SUPPRESSED_MEDIAPIPE_CONSOLE_PATTERNS.some((pattern) => pattern.test(message));
}

function formatConsoleArg(arg: unknown): string {
  if (typeof arg === "string") {
    return arg;
  }
  if (arg instanceof Error) {
    return arg.message;
  }
  try {
    return JSON.stringify(arg);
  } catch {
    return String(arg);
  }
}
