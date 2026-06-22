export type ServiceState = "ok" | "degraded" | "error";

export type AfferensState =
  | "missing_key"
  | "invalid_key"
  | "inactive_key"
  | "no_live_events"
  | "live"
  | "error";

export type ServiceStatus = {
  state: ServiceState;
  message: string;
  checked_at: string;
};

export type HealthResponse = {
  ok: boolean;
  version: string;
  environment: string;
  services: Record<string, ServiceStatus>;
};

export type AfferensStatus = {
  configured: boolean;
  base_url?: string;
  state: AfferensState;
  message: string;
  latest_event_id?: string | null;
  latest_timestamp_utc?: string | null;
  source_node_id?: string | null;
  modality?: string | null;
};

export type AfferensLatestResponse = {
  ok: boolean;
  raw_event?: unknown;
  status: AfferensStatus;
};

export type ObservationObject = {
  object_key: string;
  label: string;
  display_name: string;
  confidence: number | null;
  relative_location?: string | null;
  bbox?: unknown;
  source: string;
};

export type Observation = {
  id: string;
  raw_event_id: string;
  timestamp_utc: string;
  source: string;
  source_node_id?: string | null;
  modality?: string | null;
  classification?: string | null;
  confidence?: number | null;
  room_id?: string | null;
  scene_summary?: string | null;
  human_presence?: "visible" | "not_visible" | "unknown";
  objects?: ObservationObject[] | null;
  risk_signals?: unknown[] | null;
};

export type LatestObservationResponse = {
  observation?: Observation | null;
};

export type EnrichmentProvider = "auto" | "fireworks" | "gemini" | "deterministic";

export type EnrichmentFocus = "label_quality" | "safety" | "scene_context" | "all";

export type EnrichmentProviderState = "used" | "fallback" | "skipped" | "unavailable";

export type ModelRun = {
  id: string;
  provider: string;
  model: string;
  state: string;
  started_at: string;
  completed_at?: string | null;
  latency_ms?: number | null;
  error_message?: string | null;
};

export type EnrichmentLabelSuggestion =
  | string
  | {
      afferens_label?: string | null;
      ambiguity?: string | null;
      confidence?: number | null;
      disagreement?: string | null;
      label?: string | null;
      object_key?: string | null;
      original_label?: string | null;
      rationale?: string | null;
      reason?: string | null;
      suggested_label?: string | null;
      [key: string]: unknown;
    };

export type ObservationEnrichment = {
  id: string;
  observation_id: string;
  source_provider: string;
  source_model?: string | null;
  summary?: string | null;
  label_suggestions?: EnrichmentLabelSuggestion[] | null;
  safety_notes?: string[] | string | null;
  spatial_notes?: string[] | string | null;
  evidence_observation_ids?: string[] | null;
  created_at: string;
};

export type EnrichmentLatestRequest = {
  provider?: EnrichmentProvider;
  focus?: EnrichmentFocus;
  persist?: boolean;
};

export type EnrichmentLatestResponse = {
  ok: boolean;
  observation_id?: string | null;
  provider?: EnrichmentProvider | string | null;
  provider_state?: EnrichmentProviderState | string | null;
  model_run?: ModelRun | null;
  enrichment?: ObservationEnrichment | null;
  message?: string | null;
};

export type LatestEnrichmentResponse = {
  enrichment?: ObservationEnrichment | null;
};

export type LastSeenObject = {
  object_key: string;
  display_name: string;
  last_seen_at?: string | null;
  last_seen_room?: string | null;
  last_seen_relative_location?: string | null;
  last_seen_observation_id?: string | null;
  last_confidence?: number | null;
  status: "visible_now" | "visible_recently" | "not_seen_recently" | "unknown";
};

export type ObjectsResponse = {
  objects: LastSeenObject[];
};

export type HomeZoneRoomType =
  | "study"
  | "kitchen"
  | "bedroom"
  | "living_room"
  | "hallway"
  | "bathroom"
  | "other";

export type HomeZone = {
  id: string;
  name: string;
  room_type: HomeZoneRoomType;
  aliases: string[];
  is_default: boolean;
  created_at: string;
};

export type HomeZonesResponse = {
  zones: HomeZone[];
};

export type CreateHomeZoneRequest = {
  name: string;
  room_type: HomeZoneRoomType;
  aliases: string[];
  is_default: boolean;
};

export type CreateHomeZoneResponse = {
  ok: boolean;
  zone: HomeZone;
};

export type AmbientMode = "ambient" | "active_recovery";

export type AmbientMonitorStatus = {
  state: string;
  mode: AmbientMode | string;
  poll_interval_seconds: number;
  last_sync_at?: string | null;
  last_error?: string | null;
  estimated_afferens_tokens_per_call?: number | null;
  target_object_key?: string | null;
};

export type AmbientStatusResponse = {
  monitor: AmbientMonitorStatus;
};

export type AmbientStartRequest = {
  mode: AmbientMode;
  poll_interval_seconds: number;
  duration_seconds?: number;
  target_object_key?: string;
  zone_id?: string;
};

export type AmbientStartResponse = {
  ok: boolean;
  monitor: AmbientMonitorStatus;
};

export type AmbientStopResponse = {
  ok: boolean;
  monitor: AmbientMonitorStatus;
};

export type RuntimeMonitorMode = "home_memory" | "active_recovery";

export type RuntimeMonitorState = "off" | "running" | "paused" | "degraded" | "completed" | string;

export type RuntimeTokenBudget = {
  max_tokens_per_hour?: number | null;
  estimated_tokens_used_this_hour?: number | null;
  estimated_tokens_per_call?: number | null;
};

export type RuntimeMonitorStatus = {
  state: RuntimeMonitorState;
  mode: RuntimeMonitorMode | string;
  poll_interval_seconds: number;
  token_budget?: RuntimeTokenBudget | null;
  last_tick_at?: string | null;
  next_tick_at?: string | null;
  observations_synced?: number | null;
  last_observation_id?: string | null;
  last_error?: string | null;
  source?: string | null;
  target_object_key?: string | null;
};

export type RuntimeMonitorStatusResponse = {
  ok?: boolean;
  monitor: RuntimeMonitorStatus;
  message?: string | null;
};

export type RuntimeMonitorStartRequest = {
  mode: RuntimeMonitorMode;
  poll_interval_seconds: number;
  zone_id?: string;
  target_object_key?: string | null;
  duration_seconds?: number | null;
  max_tokens_per_hour?: number;
};

export type RuntimeMonitorStartResponse = {
  ok: boolean;
  monitor: RuntimeMonitorStatus;
  message?: string | null;
};

export type RuntimeMonitorStopResponse = {
  ok: boolean;
  monitor: RuntimeMonitorStatus;
  message?: string | null;
};

export type Task = {
  id: string;
  type: "object_recovery" | "safety_alert";
  state:
    | "open"
    | "waiting_for_human"
    | "actuation_attempted"
    | "verification_pending"
    | "verified_resolved"
    | "escalated"
    | "dismissed"
    | "failed_verification";
  title: string;
  body: string;
  recommended_action?: string | null;
  evidence_observation_ids: string[];
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
};

export type TasksResponse = {
  tasks: Task[];
};

export type TaskVerificationState = "verified" | "not_verified" | "inconclusive";

export type TaskVerification = {
  id: string;
  state: TaskVerificationState;
  observation_id?: string | null;
  message: string;
};

export type TaskVerifyResponse = {
  ok: boolean;
  task: Task;
  verification: TaskVerification;
};

export type TaskResolveResponse = {
  ok: boolean;
  task: Task;
};

export type Alert = {
  id: string;
  task_id?: string | null;
  hazard_type: string;
  severity: "low" | "medium" | "high";
  title: string;
  body: string;
  recommended_action?: string | null;
  status: "open" | "acknowledged" | "dismissed" | "resolved";
  evidence_observation_ids: string[];
  created_at: string;
  acknowledged_at?: string | null;
};

export type AlertsResponse = {
  alerts: Alert[];
};

export type AlertAckResponse = {
  ok: boolean;
  alert: Alert;
};

export type ActuationAttempt = {
  id: string;
  provider: "afferens" | "browser" | string;
  state: "succeeded" | "failed" | "skipped" | string;
  message: string;
};

export type ActuationResponse = {
  ok: boolean;
  attempt: ActuationAttempt;
};

export type SyncResponse = {
  ok: boolean;
  observations?: Observation[] | null;
  objects_updated?: LastSeenObject[] | null;
  tasks_created?: Task[] | null;
  alerts_created?: Alert[] | null;
};

export type QueryResponse = {
  answer: string;
  confidence: "low" | "medium" | "high";
  intent:
    | "object_location"
    | "guided_recovery"
    | "semantic_memory"
    | "diary"
    | "family_message"
    | "hydration"
    | "wellness"
    | "setup_status"
    | "recent_activity"
    | "safety_status"
    | "unsupported"
    | "unknown";
  used_current_perception: boolean;
  used_memory: boolean;
  needs_human_verification: boolean;
  evidence_observation_ids: string[];
  evidence_ids?: string[];
  source_ids?: string[];
  task_id?: string | null;
  next_step?: string | null;
  provider?: string | null;
  route_metadata?: Record<string, unknown> | null;
  safety_disclaimer?: string | null;
};

export type AssistantAskRequest = {
  query: string;
  session_id: string;
  voice?: boolean;
};

export type AssistantAskResponse = {
  ok?: boolean;
  intent: QueryResponse["intent"];
  answer: string;
  next_step?: string | null;
  confidence: "low" | "medium" | "high";
  provider?: "deterministic" | "fireworks" | string | null;
  used_current_perception: boolean;
  used_memory: boolean;
  needs_human_verification: boolean;
  evidence_ids: string[];
  source_ids?: string[];
  task_id?: string | null;
  route_metadata?: Record<string, unknown> | null;
};

export type PerceptionModalityState = "available" | "no_live_events" | "unavailable" | "error" | string;

export type PerceptionModalityStatus = {
  modality: string;
  state: PerceptionModalityState;
  message: string;
  latest_event_id?: string | null;
  latest_timestamp_utc?: string | null;
  source_node_id?: string | null;
  checked_at?: string | null;
};

export type PerceptionModalitiesResponse = {
  modalities: PerceptionModalityStatus[];
};

export type ProviderStatusState =
  | "configured"
  | "missing_key"
  | "live"
  | "degraded"
  | "unavailable"
  | "disabled"
  | "deferred"
  | string;

export type ProviderStatus = {
  provider: string;
  state: ProviderStatusState;
  message: string;
  details?: Record<string, unknown>;
};

export type ProvidersStatusResponse = {
  ok?: boolean;
  providers: ProviderStatus[];
};

export type SemanticMemorySourceType =
  | "observation"
  | "object_memory"
  | "diary_entry"
  | "care_note"
  | "family_message"
  | "hydration_event"
  | "wellness_check";

export type SemanticMemoryResult = {
  id: string;
  source_type: SemanticMemorySourceType | string;
  source_id: string;
  title: string;
  text: string;
  occurred_at?: string | null;
  created_at: string;
  score?: number | null;
  evidence_ids: string[];
  source_ids: string[];
  match_reasons: string[];
  metadata: Record<string, unknown>;
};

export type SemanticMemorySearchResponse = {
  ok: boolean;
  query?: string | null;
  items: SemanticMemoryResult[];
  provider?: string | null;
  reindex_recommended?: boolean;
};

export type SemanticMemoryReindexRequest = {
  force?: boolean;
  source_types?: SemanticMemorySourceType[];
};

export type SemanticMemoryReindexResponse = {
  ok: boolean;
  indexed_count: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  provider?: string | null;
  message?: string | null;
};

export type MemoryAskResponse = {
  ok?: boolean;
  answer: string;
  confidence: "low" | "medium" | "high";
  evidence_ids: string[];
  source_ids?: string[];
  citations?: SemanticMemoryResult[];
  provider?: string | null;
  used_memory?: boolean;
  needs_human_verification: boolean;
  safety_disclaimer?: string;
};

export type VoiceQueryResponse = {
  ok: boolean;
  query_result: QueryResponse;
  spoken_text?: string | null;
};

export type GuidedRecoveryStartResponse = {
  ok: boolean;
  task?: Task | null;
  next_instruction: string;
};

export type ActivityConfidence = "low" | "medium" | "high" | string;

export type WellnessConfidence = "low" | "medium" | "high";

export type HydrationEventType = "water_visible" | "drink_candidate" | "caregiver_reported";

export type HydrationStatus = "unknown" | "okay" | "consider_prompting";

export type HydrationEvent = {
  id: string;
  type: HydrationEventType | string;
  occurred_at: string;
  confidence: WellnessConfidence | string;
  zone_id?: string | null;
  zone_name?: string | null;
  evidence_ids?: string[] | null;
  metadata?: Record<string, unknown> | null;
};

export type HydrationSummary = {
  date: string;
  status: HydrationStatus | string;
  water_events: number;
  latest_event_at?: string | null;
  message: string;
  evidence_ids: string[];
  events: HydrationEvent[];
};

export type HydrationSummaryResponse = {
  date: string;
  summary: HydrationSummary;
};

export type CreateHydrationEventRequest = {
  type?: HydrationEventType;
  occurred_at?: string;
  confidence?: WellnessConfidence;
  zone_id?: string;
  evidence_ids?: string[];
  metadata?: Record<string, unknown>;
};

export type CreateHydrationEventResponse = {
  ok: boolean;
  event: HydrationEvent;
};

export type WellnessCheckType =
  | "hydration_prompt"
  | "possible_fall_check"
  | "unusual_stillness_check"
  | "caregiver_review";

export type WellnessCheckSeverity = "low" | "medium" | "high";

export type WellnessCheckStatus = "open" | "acknowledged" | "dismissed";

export type WellnessCheck = {
  id: string;
  type: WellnessCheckType | string;
  severity: WellnessCheckSeverity | string;
  status: WellnessCheckStatus | string;
  title: string;
  body: string;
  confidence: WellnessConfidence | string;
  occurred_at: string;
  created_at: string;
  acknowledged_at?: string | null;
  zone_id?: string | null;
  zone_name?: string | null;
  evidence_ids: string[];
  metadata: Record<string, unknown>;
};

export type WellnessChecksResponse = {
  date: string;
  checks: WellnessCheck[];
};

export type ActionEventType =
  | "fall_candidate"
  | "fall_escalated"
  | "drink_candidate"
  | "action_inconclusive";

export type ActionEventSource =
  | "browser_mediapipe"
  | "browser_manual_test"
  | "local_yolo_fall"
  | "patient_help_request"
  | (string & {});

export type ActionEvent = {
  id: string;
  type: ActionEventType | string;
  occurred_at: string;
  created_at?: string | null;
  confidence: WellnessConfidence | string;
  score?: number | null;
  source: ActionEventSource;
  source_node_id?: string | null;
  zone_id?: string | null;
  zone_name?: string | null;
  evidence_ids: string[];
  metadata: Record<string, unknown>;
};

export type ActionEventsResponse = {
  date?: string | null;
  events: ActionEvent[];
};

export type ActionEventRecordRequest = {
  type: ActionEventType;
  occurred_at?: string;
  confidence: WellnessConfidence;
  score?: number;
  source: ActionEventSource;
  source_node_id?: string;
  zone_id?: string;
  evidence_ids?: string[];
  metadata?: Record<string, unknown>;
};

export type ActionTelemetryEvaluateRequest = {
  occurred_at?: string;
  source?: ActionEventSource;
  source_node_id?: string;
  zone_id?: string;
  evidence_ids?: string[];
  posture_state?: string;
  fallen?: boolean;
  persistence_seconds?: number;
  require_model_runtime?: boolean;
  object_keys?: string[];
  object_visible?: boolean;
  hand_object_contact?: boolean;
  hand_to_mouth_motion?: boolean;
  object_near_mouth?: boolean;
  explicit_action_telemetry?: boolean;
  temporal_window_seconds?: number;
  confidence?: WellnessConfidence;
  score?: number;
  metadata?: Record<string, unknown>;
};

export type ActionTelemetryEvaluateResponse = {
  ok: boolean;
  decision?: ActionEventType | string;
  event?: ActionEvent | null;
  action_event?: ActionEvent | null;
  hydration_event_id?: string | null;
  wellness_check_id?: string | null;
  message?: string | null;
};

export type ActionRuntimeProviderStatus = {
  available: boolean;
  enabled?: boolean;
  labels?: string[];
  message?: string | null;
  model_loaded?: boolean;
  model_path_configured?: boolean;
  provider?: string | null;
};

export type ActionRuntimePrivacyStatus = {
  raw_frames_persisted?: boolean;
  raw_video_storage_enabled?: boolean;
};

export type ActionRuntimeStatusResponse = {
  ok: boolean;
  drink?: ActionRuntimeProviderStatus | null;
  fall?: ActionRuntimeProviderStatus | null;
  privacy?: ActionRuntimePrivacyStatus | null;
};

export type FallInferFrameRequest = {
  evidenceIds?: string[];
  frame: Blob;
  occurredAt?: string;
  persistInconclusive?: boolean;
  sourceNodeId?: string;
  zoneId?: string;
};

export type GenerateWellnessChecksResponse = {
  ok: boolean;
  checks: WellnessCheck[];
};

export type AcknowledgeWellnessCheckRequest = {
  acknowledged_by?: "caregiver" | "family" | "user";
  note?: string;
};

export type AcknowledgeWellnessCheckResponse = {
  ok: boolean;
  check: WellnessCheck;
};

export type ActivityEvent = {
  id: string;
  type: string;
  title: string;
  body: string;
  occurred_at: string;
  source: string;
  confidence: ActivityConfidence;
  zone_id?: string | null;
  zone_name?: string | null;
  evidence_ids: string[];
  metadata: Record<string, unknown>;
};

export type ActivityTimelineResponse = {
  date: string;
  events: ActivityEvent[];
};

export type DailyDiaryEntry = {
  id: string;
  date: string;
  summary: string;
  highlights: string[];
  needs_review: string[];
  evidence_ids: string[];
  generated_at: string;
  source: string;
};

export type DiaryResponse = {
  date: string;
  diary: DailyDiaryEntry | null;
};

export type GenerateDiaryRequest = {
  date?: string;
};

export type GenerateDiaryResponse = {
  ok: boolean;
  diary: DailyDiaryEntry;
};

export type CareNoteAudience = "family" | "care_home";

export type CareNote = {
  id: string;
  date: string;
  audience: CareNoteAudience | string;
  summary: string;
  bullets: string[];
  risks: string[];
  follow_ups: string[];
  evidence_ids: string[];
  created_at: string;
  source: string;
};

export type CareNotesResponse = {
  date: string;
  notes: CareNote[];
};

export type GenerateCareNoteRequest = {
  date?: string;
  audience?: CareNoteAudience;
};

export type GenerateCareNoteResponse = {
  ok: boolean;
  note: CareNote;
};

export type FamilyMessagePriority = "low" | "normal" | "high";

export type FamilyMessage = {
  id: string;
  title: string;
  body: string;
  priority: FamilyMessagePriority | string;
  status: string;
  trigger_object_key?: string | null;
  trigger_zone_id?: string | null;
  starts_at?: string | null;
  expires_at?: string | null;
  created_at: string;
  acknowledged_at?: string | null;
  metadata: Record<string, unknown>;
};

export type FamilyMessagesResponse = {
  messages: FamilyMessage[];
};

export type CreateFamilyMessageRequest = {
  title: string;
  body: string;
  priority?: FamilyMessagePriority;
  trigger_object_key?: string;
  trigger_zone_id?: string;
  starts_at?: string;
  expires_at?: string;
};

export type CreateFamilyMessageResponse = {
  ok: boolean;
  message: FamilyMessage;
};

export type AcknowledgeFamilyMessageResponse = {
  ok: boolean;
  message: FamilyMessage;
};

export type Loadable<T> = {
  data?: T;
  error?: string;
  loading: boolean;
};
