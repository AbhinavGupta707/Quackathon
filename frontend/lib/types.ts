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
  intent: "object_location" | "recent_activity" | "safety_status" | "unknown";
  used_current_perception: boolean;
  used_memory: boolean;
  needs_human_verification: boolean;
  evidence_observation_ids: string[];
  task_id?: string | null;
  safety_disclaimer?: string | null;
};

export type Loadable<T> = {
  data?: T;
  error?: string;
  loading: boolean;
};
