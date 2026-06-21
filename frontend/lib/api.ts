import type {
  AfferensLatestResponse,
  AfferensStatus,
  AlertsResponse,
  HealthResponse,
  LatestObservationResponse,
  ObjectsResponse,
  QueryResponse,
  SyncResponse,
  TasksResponse
} from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/$/, "");

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type RequestOptions = RequestInit & {
  bodyJson?: unknown;
};

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { bodyJson, headers, ...rest } = options;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(bodyJson ? { "Content-Type": "application/json" } : {}),
        ...headers
      },
      body: bodyJson ? JSON.stringify(bodyJson) : rest.body
    });
  } catch (error) {
    throw new ApiError(
      error instanceof Error
        ? `Backend unavailable: ${error.message}`
        : "Backend unavailable."
    );
  }

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      // Non-JSON backend errors are still surfaced with the HTTP status.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health");
}

export function getAfferensStatus(): Promise<AfferensStatus> {
  return requestJson<AfferensStatus>("/api/afferens/status");
}

export function getAfferensLatest(): Promise<AfferensLatestResponse> {
  return requestJson<AfferensLatestResponse>("/api/afferens/latest");
}

export function syncPerception(): Promise<SyncResponse> {
  return requestJson<SyncResponse>("/api/perception/sync", {
    method: "POST",
    bodyJson: {
      limit: 1,
      room_id: "default_home_zone"
    }
  });
}

export function getLatestObservation(): Promise<LatestObservationResponse> {
  return requestJson<LatestObservationResponse>("/api/observations/latest");
}

export function getObjects(): Promise<ObjectsResponse> {
  return requestJson<ObjectsResponse>("/api/objects/last-seen");
}

export function getTasks(): Promise<TasksResponse> {
  return requestJson<TasksResponse>("/api/tasks");
}

export function getAlerts(): Promise<AlertsResponse> {
  return requestJson<AlertsResponse>("/api/alerts");
}

export function askQuery(query: string, sessionId: string): Promise<QueryResponse> {
  return requestJson<QueryResponse>("/api/query", {
    method: "POST",
    bodyJson: {
      query,
      session_id: sessionId
    }
  });
}
