import type { ActionEventRecordRequest } from "./types";

const PRIVACY_METADATA = {
  raw_video_stored: false,
  raw_frames_sent: false,
  third_party_frames_sent: false,
  adapter_version: "browser_action_node_v1"
};

export function buildPatientHelpRequest(nodeId: string): ActionEventRecordRequest {
  return {
    type: "action_inconclusive",
    occurred_at: new Date().toISOString(),
    confidence: "low",
    source: "patient_help_request",
    source_node_id: nodeId,
    evidence_ids: [],
    metadata: {
      ...PRIVACY_METADATA,
      reason: "patient_requested_caregiver_check",
      patient_safe_summary: "caregiver check requested by patient"
    }
  };
}
