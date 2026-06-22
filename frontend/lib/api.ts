import type {
  ActuationResponse,
  ActionEventRecordRequest,
  ActionEventsResponse,
  ActionEventType,
  ActionRuntimeStatusResponse,
  ActionTelemetryEvaluateRequest,
  ActionTelemetryEvaluateResponse,
  ActivityTimelineResponse,
  AfferensLatestResponse,
  AfferensStatus,
  AcknowledgeFamilyMessageResponse,
  AcknowledgeWellnessCheckRequest,
  AcknowledgeWellnessCheckResponse,
  AlertAckResponse,
  AlertsResponse,
  AmbientStartRequest,
  AmbientStartResponse,
  AmbientStatusResponse,
  AmbientStopResponse,
  AssistantAskResponse,
  CareNoteAudience,
  CareNotesResponse,
  CreateHydrationEventRequest,
  CreateHydrationEventResponse,
  CreateFamilyMessageRequest,
  CreateFamilyMessageResponse,
  CreateHomeZoneRequest,
  CreateHomeZoneResponse,
  DiaryResponse,
  EnrichmentLatestRequest,
  EnrichmentLatestResponse,
  FamilyMessagesResponse,
  FallInferFrameRequest,
  GenerateCareNoteResponse,
  GenerateDiaryResponse,
  GenerateWellnessChecksResponse,
  GuidedRecoveryStartResponse,
  HealthResponse,
  HomeZonesResponse,
  HydrationSummaryResponse,
  LatestEnrichmentResponse,
  LatestObservationResponse,
  MemoryAskResponse,
  ObjectsResponse,
  PerceptionModalitiesResponse,
  ProvidersStatusResponse,
  QueryResponse,
  RuntimeMonitorStartRequest,
  RuntimeMonitorStartResponse,
  RuntimeMonitorStatus,
  RuntimeMonitorStatusResponse,
  RuntimeMonitorStopResponse,
  SemanticMemoryReindexRequest,
  SemanticMemoryReindexResponse,
  SemanticMemoryResult,
  SemanticMemorySearchResponse,
  SemanticMemorySourceType,
  SyncResponse,
  TaskResolveResponse,
  TaskVerifyResponse,
  TasksResponse,
  WellnessChecksResponse,
  VoiceQueryResponse
} from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;

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
  timeoutMs?: number;
};

async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { bodyJson, headers, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, signal, ...rest } = options;
  const controller = signal ? null : new AbortController();
  const timeoutId =
    controller && timeoutMs > 0
      ? setTimeout(() => controller.abort(), timeoutMs)
      : undefined;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      cache: "no-store",
      signal: signal ?? controller?.signal,
      headers: {
        Accept: "application/json",
        ...(bodyJson ? { "Content-Type": "application/json" } : {}),
        ...headers
      },
      body: bodyJson ? JSON.stringify(bodyJson) : rest.body
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError(`Backend request timed out after ${Math.round(timeoutMs / 1000)} seconds.`);
    }
    throw new ApiError(
      error instanceof Error
        ? `Backend unavailable: ${error.message}`
        : "Backend unavailable."
    );
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
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

export function getLatestEnrichment(): Promise<LatestEnrichmentResponse> {
  return requestJson<LatestEnrichmentResponse>("/api/enrichment/latest");
}

export function reviewLatestEnrichment(
  request: EnrichmentLatestRequest = {}
): Promise<EnrichmentLatestResponse> {
  return requestJson<EnrichmentLatestResponse>("/api/enrichment/latest", {
    method: "POST",
    bodyJson: {
      provider: request.provider ?? "auto",
      focus: request.focus ?? "label_quality",
      persist: request.persist ?? true
    }
  });
}

export function getObjects(): Promise<ObjectsResponse> {
  return requestJson<ObjectsResponse>("/api/objects/last-seen");
}

export function getHomeZones(): Promise<HomeZonesResponse> {
  return requestJson<HomeZonesResponse>("/api/home-zones");
}

export function createHomeZone(request: CreateHomeZoneRequest): Promise<CreateHomeZoneResponse> {
  return requestJson<CreateHomeZoneResponse>("/api/home-zones", {
    method: "POST",
    bodyJson: request
  });
}

export function getAmbientStatus(): Promise<AmbientStatusResponse> {
  return requestJson<AmbientStatusResponse>("/api/ambient/status");
}

export function startAmbientMonitor(request: AmbientStartRequest): Promise<AmbientStartResponse> {
  return requestJson<AmbientStartResponse>("/api/ambient/start", {
    method: "POST",
    bodyJson: request
  });
}

export function stopAmbientMonitor(): Promise<AmbientStopResponse> {
  return requestJson<AmbientStopResponse>("/api/ambient/stop", {
    method: "POST"
  });
}

export function getRuntimeMonitorStatus(): Promise<RuntimeMonitorStatusResponse> {
  return requestJson<RuntimeMonitorStatusResponse>("/api/runtime/monitor/status");
}

export function startRuntimeMonitor(
  request: RuntimeMonitorStartRequest
): Promise<RuntimeMonitorStartResponse> {
  return requestJson<RuntimeMonitorStartResponse>("/api/runtime/monitor/start", {
    method: "POST",
    bodyJson: request
  });
}

export function stopRuntimeMonitor(): Promise<RuntimeMonitorStopResponse> {
  return requestJson<RuntimeMonitorStopResponse>("/api/runtime/monitor/stop", {
    method: "POST"
  });
}

export async function getHomeMemoryStatus(): Promise<RuntimeMonitorStatusResponse> {
  try {
    return await getRuntimeMonitorStatus();
  } catch (error) {
    if (error instanceof ApiError && isUnavailableEndpoint(error.status)) {
      const legacy = await getAmbientStatus();
      return {
        ok: true,
        monitor: ambientToRuntimeMonitor(legacy.monitor),
        message: "Using legacy ambient monitor status until the autonomous runtime endpoint is available."
      };
    }

    throw error;
  }
}

export async function startHomeMemory(
  request: RuntimeMonitorStartRequest
): Promise<RuntimeMonitorStartResponse> {
  try {
    return await startRuntimeMonitor(request);
  } catch (error) {
    if (error instanceof ApiError && isUnavailableEndpoint(error.status)) {
      const legacy = await startAmbientMonitor({
        duration_seconds: request.duration_seconds ?? undefined,
        mode: request.mode === "active_recovery" ? "active_recovery" : "ambient",
        poll_interval_seconds: request.poll_interval_seconds,
        target_object_key: request.target_object_key ?? undefined,
        zone_id: request.zone_id
      });
      return {
        ok: true,
        monitor: ambientToRuntimeMonitor(legacy.monitor),
        message: "Home memory is using the legacy ambient monitor until the autonomous runtime endpoint is available."
      };
    }

    throw error;
  }
}

export async function stopHomeMemory(): Promise<RuntimeMonitorStopResponse> {
  try {
    return await stopRuntimeMonitor();
  } catch (error) {
    if (error instanceof ApiError && isUnavailableEndpoint(error.status)) {
      const legacy = await stopAmbientMonitor();
      return {
        ok: true,
        monitor: ambientToRuntimeMonitor(legacy.monitor),
        message: "Home memory stopped through the legacy ambient monitor."
      };
    }

    throw error;
  }
}

export function getTasks(): Promise<TasksResponse> {
  return requestJson<TasksResponse>("/api/tasks");
}

export function verifyTask(taskId: string): Promise<TaskVerifyResponse> {
  return requestJson<TaskVerifyResponse>(`/api/tasks/${encodeURIComponent(taskId)}/verify`, {
    method: "POST",
    bodyJson: {
      room_id: "default_home_zone"
    }
  });
}

export function resolveTask(taskId: string, resolutionNote: string): Promise<TaskResolveResponse> {
  return requestJson<TaskResolveResponse>(`/api/tasks/${encodeURIComponent(taskId)}/resolve`, {
    method: "POST",
    bodyJson: {
      resolved_by: "user",
      resolution_note: resolutionNote
    }
  });
}

export function getAlerts(): Promise<AlertsResponse> {
  return requestJson<AlertsResponse>("/api/alerts");
}

export function getActionEvents({
  date,
  limit = 25,
  type
}: {
  date?: string;
  limit?: number;
  type?: ActionEventType | "";
} = {}): Promise<ActionEventsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });

  if (date) {
    params.set("date", date);
  }
  if (type) {
    params.set("type", type);
  }

  return requestJson<ActionEventsResponse>(`/api/action-events?${params.toString()}`);
}

export function getActionRuntimeStatus(): Promise<ActionRuntimeStatusResponse> {
  return requestJson<ActionRuntimeStatusResponse>("/api/action-events/runtime/status");
}

export function recordActionEvent(
  request: ActionEventRecordRequest
): Promise<ActionTelemetryEvaluateResponse> {
  return requestJson<ActionTelemetryEvaluateResponse>("/api/action-events", {
    method: "POST",
    bodyJson: request
  });
}

export function evaluateFallActionTelemetry(
  request: ActionTelemetryEvaluateRequest
): Promise<ActionTelemetryEvaluateResponse> {
  return requestJson<ActionTelemetryEvaluateResponse>("/api/action-events/fall/evaluate", {
    method: "POST",
    bodyJson: request
  });
}

export function evaluateDrinkActionTelemetry(
  request: ActionTelemetryEvaluateRequest
): Promise<ActionTelemetryEvaluateResponse> {
  return requestJson<ActionTelemetryEvaluateResponse>("/api/action-events/drink/evaluate", {
    method: "POST",
    bodyJson: request
  });
}

export function inferFallFromFrame({
  evidenceIds = [],
  frame,
  occurredAt,
  persistInconclusive,
  sourceNodeId,
  zoneId
}: FallInferFrameRequest): Promise<ActionTelemetryEvaluateResponse> {
  const formData = new FormData();
  formData.append("frame", frame, "action-node-frame.jpg");
  if (sourceNodeId) {
    formData.append("source_node_id", sourceNodeId);
  }
  if (zoneId) {
    formData.append("zone_id", zoneId);
  }
  if (evidenceIds.length) {
    formData.append("evidence_ids", evidenceIds.join(","));
  }
  if (occurredAt) {
    formData.append("occurred_at", occurredAt);
  }
  if (persistInconclusive !== undefined) {
    formData.append("persist_inconclusive", String(persistInconclusive));
  }

  return requestJson<ActionTelemetryEvaluateResponse>("/api/action-events/fall/infer-frame", {
    body: formData,
    method: "POST"
  });
}

export function acknowledgeAlert(alertId: string, note?: string): Promise<AlertAckResponse> {
  return requestJson<AlertAckResponse>(`/api/alerts/${encodeURIComponent(alertId)}/ack`, {
    method: "POST",
    bodyJson: {
      acknowledged_by: "caregiver",
      note: note?.trim() || "Acknowledged in dashboard."
    }
  });
}

export function triggerAssistiveAlarm({
  reason,
  severity,
  taskId
}: {
  reason: string;
  severity: "low" | "medium" | "high";
  taskId?: string | null;
}): Promise<ActuationResponse> {
  return requestJson<ActuationResponse>("/api/actuate/alarm", {
    method: "POST",
    bodyJson: {
      reason,
      severity,
      task_id: taskId,
      use_afferens: true
    }
  });
}

export function captureFrameForTask({
  taskId,
  targetNodeId
}: {
  taskId?: string | null;
  targetNodeId?: string | null;
}): Promise<ActuationResponse> {
  return requestJson<ActuationResponse>("/api/actuate/capture-frame", {
    method: "POST",
    bodyJson: {
      task_id: taskId,
      target_node_id: targetNodeId,
      reason: "caregiver_review_verification"
    }
  });
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

export function askAssistant({
  query,
  session_id: sessionId,
  voice = false
}: {
  query: string;
  session_id: string;
  voice?: boolean;
}): Promise<AssistantAskResponse> {
  return requestJson<AssistantAskResponse>("/api/assistant/ask", {
    method: "POST",
    bodyJson: {
      query,
      session_id: sessionId,
      voice
    }
  });
}

export type PatientAssistantResult = {
  endpoint: "assistant" | "query_fallback";
  fallbackReason?: string;
  queryResult: QueryResponse;
  spokenText?: string | null;
};

export async function askPatientAssistant(
  query: string,
  sessionId: string,
  voice = false
): Promise<PatientAssistantResult> {
  try {
    const assistant = await askAssistant({ query, session_id: sessionId, voice });
    const queryResult = assistantToQueryResponse(assistant);
    return {
      endpoint: "assistant",
      queryResult,
      spokenText: `${assistant.answer}${assistant.next_step ? ` ${assistant.next_step}` : ""}`
    };
  } catch (error) {
    if (error instanceof ApiError && isUnavailableEndpoint(error.status)) {
      const fallback = await askQuery(query, sessionId);
      return {
        endpoint: "query_fallback",
        fallbackReason: "Unified assistant is not available yet; I used object memory instead.",
        queryResult: fallback,
        spokenText: fallback.answer
      };
    }

    throw error;
  }
}

export function getPerceptionModalities(): Promise<PerceptionModalitiesResponse> {
  return requestJson<PerceptionModalitiesResponse>("/api/perception/modalities");
}

export function getProvidersStatus(): Promise<ProvidersStatusResponse> {
  return requestJson<ProvidersStatusResponse>("/api/providers/status");
}

export function askSemanticMemory(question: string): Promise<MemoryAskResponse> {
  return requestJson<unknown>("/api/memory/ask", {
    method: "POST",
    bodyJson: {
      limit: 8,
      query: question,
      question
    }
  }).then(normalizeMemoryAskResponse);
}

export function searchSemanticMemory({
  limit = 10,
  query,
  sourceType
}: {
  limit?: number;
  query: string;
  sourceType?: SemanticMemorySourceType | "";
}): Promise<SemanticMemorySearchResponse> {
  const params = new URLSearchParams({
    query,
    q: query,
    limit: String(limit)
  });

  if (sourceType) {
    params.set("source_type", sourceType);
  }

  return requestJson<unknown>(`/api/memory/semantic?${params.toString()}`).then(
    normalizeSemanticMemorySearchResponse
  );
}

export function reindexSemanticMemory(
  request: SemanticMemoryReindexRequest = {}
): Promise<SemanticMemoryReindexResponse> {
  return requestJson<unknown>("/api/memory/reindex", {
    method: "POST",
    bodyJson: request
  }).then(normalizeSemanticMemoryReindexResponse);
}

export function startGuidedRecovery(
  objectKey: string,
  sessionId: string
): Promise<GuidedRecoveryStartResponse> {
  return requestJson<GuidedRecoveryStartResponse>("/api/guidance/recovery/start", {
    method: "POST",
    bodyJson: {
      object_key: objectKey,
      session_id: sessionId
    }
  });
}

export function getActivityTimeline(date: string): Promise<ActivityTimelineResponse> {
  return requestJson<ActivityTimelineResponse>(`/api/activity/timeline?date=${encodeURIComponent(date)}`);
}

export function getDiary(date: string): Promise<DiaryResponse> {
  return requestJson<DiaryResponse>(`/api/diary?date=${encodeURIComponent(date)}`);
}

export function generateDiary(date?: string): Promise<GenerateDiaryResponse> {
  return requestJson<GenerateDiaryResponse>("/api/diary/generate", {
    method: "POST",
    bodyJson: date ? { date } : {}
  });
}

export function getCareNotes(date: string): Promise<CareNotesResponse> {
  return requestJson<CareNotesResponse>(`/api/care-notes?date=${encodeURIComponent(date)}`);
}

export function generateCareNote({
  audience,
  date
}: {
  audience?: CareNoteAudience;
  date?: string;
} = {}): Promise<GenerateCareNoteResponse> {
  return requestJson<GenerateCareNoteResponse>("/api/care-notes/generate", {
    method: "POST",
    bodyJson: {
      ...(date ? { date } : {}),
      ...(audience ? { audience } : {})
    }
  });
}

export function getFamilyMessages(includeAcknowledged = false): Promise<FamilyMessagesResponse> {
  return requestJson<FamilyMessagesResponse>(
    `/api/family-messages?include_acknowledged=${includeAcknowledged ? "true" : "false"}`
  );
}

export function getActiveFamilyMessages(): Promise<FamilyMessagesResponse> {
  return requestJson<FamilyMessagesResponse>("/api/family-messages/active");
}

export function getHydrationSummary(date: string): Promise<HydrationSummaryResponse> {
  return requestJson<HydrationSummaryResponse>(
    `/api/hydration/summary?date=${encodeURIComponent(date)}`
  );
}

export function recordHydrationEvent(
  request: CreateHydrationEventRequest = {}
): Promise<CreateHydrationEventResponse> {
  return requestJson<CreateHydrationEventResponse>("/api/hydration/events", {
    method: "POST",
    bodyJson: request
  });
}

export function getWellnessChecks(date: string): Promise<WellnessChecksResponse> {
  return requestJson<WellnessChecksResponse>(
    `/api/wellness/checks?date=${encodeURIComponent(date)}`
  );
}

export function generateWellnessChecks(date?: string): Promise<GenerateWellnessChecksResponse> {
  return requestJson<GenerateWellnessChecksResponse>("/api/wellness/checks/generate", {
    method: "POST",
    bodyJson: date ? { date } : {}
  });
}

export function acknowledgeWellnessCheck(
  checkId: string,
  request: AcknowledgeWellnessCheckRequest = {}
): Promise<AcknowledgeWellnessCheckResponse> {
  return requestJson<AcknowledgeWellnessCheckResponse>(
    `/api/wellness/checks/${encodeURIComponent(checkId)}/ack`,
    {
      method: "POST",
      bodyJson: {
        acknowledged_by: request.acknowledged_by ?? "caregiver",
        note: request.note?.trim() || "Reviewed in caregiver mode."
      }
    }
  );
}

export function createFamilyMessage(
  request: CreateFamilyMessageRequest
): Promise<CreateFamilyMessageResponse> {
  return requestJson<CreateFamilyMessageResponse>("/api/family-messages", {
    method: "POST",
    bodyJson: request
  });
}

export function acknowledgeFamilyMessage(messageId: string): Promise<AcknowledgeFamilyMessageResponse> {
  return requestJson<AcknowledgeFamilyMessageResponse>(
    `/api/family-messages/${encodeURIComponent(messageId)}/ack`,
    {
      method: "POST"
    }
  );
}

export type VoiceQueryResult = {
  endpoint: "voice" | "query_fallback";
  fallbackReason?: string;
  queryResult: QueryResponse;
  spokenText?: string | null;
};

export async function voiceQuery(query: string, sessionId: string, speak: boolean): Promise<VoiceQueryResult> {
  try {
    const payload = await requestJson<VoiceQueryResponse | QueryResponse>("/api/voice/query", {
      method: "POST",
      bodyJson: {
        query,
        session_id: sessionId,
        speak
      }
    });

    if ("query_result" in payload) {
      return {
        endpoint: "voice",
        queryResult: payload.query_result,
        spokenText: payload.spoken_text
      };
    }

    return {
      endpoint: "voice",
      queryResult: payload,
      spokenText: payload.answer
    };
  } catch (error) {
    if (error instanceof ApiError && isUnavailableEndpoint(error.status)) {
      const fallback = await askQuery(query, sessionId);
      return {
        endpoint: "query_fallback",
        fallbackReason: "Voice query endpoint is not available yet; sent the transcript to text query.",
        queryResult: fallback,
        spokenText: fallback.answer
      };
    }

    throw error;
  }
}

export function isUnavailableEndpoint(status?: number): boolean {
  return status === 404 || status === 405 || status === 501;
}

function ambientToRuntimeMonitor(monitor: AmbientStatusResponse["monitor"]): RuntimeMonitorStatus {
  return {
    state: monitor.state,
    mode: monitor.mode === "ambient" ? "home_memory" : monitor.mode,
    poll_interval_seconds: monitor.poll_interval_seconds,
    token_budget: monitor.estimated_afferens_tokens_per_call
      ? {
          estimated_tokens_per_call: monitor.estimated_afferens_tokens_per_call
        }
      : null,
    last_tick_at: monitor.last_sync_at ?? null,
    last_error: monitor.last_error ?? null,
    source: "legacy_ambient_monitor",
    target_object_key: monitor.target_object_key ?? null
  };
}

function assistantToQueryResponse(response: AssistantAskResponse): QueryResponse {
  return {
    answer: response.answer,
    confidence: response.confidence,
    evidence_ids: response.evidence_ids,
    evidence_observation_ids: response.evidence_ids,
    intent: response.intent,
    needs_human_verification: response.needs_human_verification,
    next_step: response.next_step ?? null,
    provider: response.provider ?? null,
    route_metadata: response.route_metadata ?? null,
    source_ids: response.source_ids ?? [],
    task_id: response.task_id ?? null,
    used_current_perception: response.used_current_perception,
    used_memory: response.used_memory
  };
}

function normalizeSemanticMemorySearchResponse(payload: unknown): SemanticMemorySearchResponse {
  const data = isRecord(payload) ? payload : {};
  const rawItems = Array.isArray(data.items)
    ? data.items
    : Array.isArray(data.results)
      ? data.results
      : [];

  return {
    ok: typeof data.ok === "boolean" ? data.ok : true,
    items: rawItems.map(normalizeSemanticMemoryResult),
    provider: asOptionalString(data.provider),
    query: asOptionalString(data.query),
    reindex_recommended: typeof data.reindex_recommended === "boolean" ? data.reindex_recommended : undefined
  };
}

function normalizeSemanticMemoryReindexResponse(payload: unknown): SemanticMemoryReindexResponse {
  const data = isRecord(payload) ? payload : {};
  const indexedCount = asNumber(data.indexed_count) ?? asNumber(data.indexed) ?? 0;
  const skippedCount = asNumber(data.skipped_count) ?? asNumber(data.skipped) ?? 0;

  return {
    ok: typeof data.ok === "boolean" ? data.ok : true,
    created_count: asNumber(data.created_count) ?? 0,
    indexed_count: indexedCount,
    message: asOptionalString(data.message),
    provider: asOptionalString(data.provider),
    skipped_count: skippedCount,
    updated_count: asNumber(data.updated_count) ?? 0
  };
}

function normalizeMemoryAskResponse(payload: unknown): MemoryAskResponse {
  const data = isRecord(payload) ? payload : {};
  const citations = Array.isArray(data.citations)
    ? data.citations.map(normalizeSemanticMemoryResult)
    : [];
  const evidenceIds = asStringArray(data.evidence_ids);

  return {
    answer: asOptionalString(data.answer) || "I do not have enough cited memory to answer that yet.",
    citations,
    confidence: data.confidence === "high" || data.confidence === "medium" ? data.confidence : "low",
    evidence_ids: evidenceIds,
    needs_human_verification:
      typeof data.needs_human_verification === "boolean" ? data.needs_human_verification : true,
    ok: typeof data.ok === "boolean" ? data.ok : undefined,
    provider: asOptionalString(data.provider),
    safety_disclaimer: asOptionalString(data.safety_disclaimer),
    source_ids: asStringArray(data.source_ids),
    used_memory:
      typeof data.used_memory === "boolean"
        ? data.used_memory
        : evidenceIds.length > 0 || citations.length > 0
  };
}

function normalizeSemanticMemoryResult(payload: unknown): SemanticMemoryResult {
  const data = isRecord(payload) ? payload : {};
  const fallbackId = asOptionalString(data.source_id) || asOptionalString(data.id) || "memory";
  return {
    created_at: asOptionalString(data.created_at) || asOptionalString(data.occurred_at) || "",
    evidence_ids: asStringArray(data.evidence_ids),
    id: asOptionalString(data.id) || fallbackId,
    match_reasons: asStringArray(data.match_reasons).length
      ? asStringArray(data.match_reasons)
      : asStringArray(data.tags),
    metadata: isRecord(data.metadata) ? data.metadata : {},
    occurred_at: asOptionalString(data.occurred_at),
    score: asNumber(data.score),
    source_id: asOptionalString(data.source_id) || fallbackId,
    source_ids: asStringArray(data.source_ids),
    source_type: asOptionalString(data.source_type) || "observation",
    text: asOptionalString(data.text) || asOptionalString(data.body) || "",
    title: asOptionalString(data.title) || "Memory evidence"
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
