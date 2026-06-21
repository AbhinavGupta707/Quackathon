# Afferens Memory Guardian API Contract

This file is master-owned. Backend and frontend workstreams should implement against it and propose changes rather than independently changing endpoint names or response shapes.

All runtime perception is live-only. Test fixtures may be used in tests, but product endpoints must not serve cached or replayed perception as if it were live.

## Common Types

### ServiceStatus

```json
{
  "state": "ok | degraded | error",
  "message": "string",
  "checked_at": "2026-06-21T16:00:00Z"
}
```

### AfferensStatus

```json
{
  "configured": true,
  "base_url": "https://afferens.com",
  "state": "missing_key | invalid_key | inactive_key | no_live_events | live | error",
  "message": "Live Afferens Vision event available.",
  "latest_event_id": "LIVE-VIS-MP0SH76G",
  "latest_timestamp_utc": "2026-06-21T16:00:00Z",
  "source_node_id": "IPHONE-IOS-01",
  "modality": "VISION"
}
```

Never return the API key or any part of it.

### Observation

```json
{
  "id": "obs_01HY...",
  "raw_event_id": "aff_01HY...",
  "timestamp_utc": "2026-06-21T16:00:00Z",
  "source": "afferens",
  "source_node_id": "IPHONE-IOS-01",
  "modality": "VISION",
  "classification": "iphone_camera_coco",
  "confidence": 1.0,
  "room_id": "default_home_zone",
  "scene_summary": "Keys, a bottle, and medicine are visible on the table.",
  "human_presence": "visible | not_visible | unknown",
  "objects": [
    {
      "object_key": "keys",
      "label": "keys",
      "display_name": "keys",
      "confidence": 0.82,
      "relative_location": "left side of the table beside the blue bottle",
      "bbox": null,
      "source": "afferens"
    }
  ],
  "risk_signals": []
}
```

### LastSeenObject

```json
{
  "object_key": "keys",
  "display_name": "keys",
  "last_seen_at": "2026-06-21T16:00:00Z",
  "last_seen_room": "default_home_zone",
  "last_seen_relative_location": "left side of the table beside the blue bottle",
  "last_seen_observation_id": "obs_01HY...",
  "last_confidence": 0.82,
  "status": "visible_now | visible_recently | not_seen_recently | unknown"
}
```

### Task

```json
{
  "id": "task_01HY...",
  "type": "object_recovery | safety_alert",
  "state": "open | waiting_for_human | actuation_attempted | verification_pending | verified_resolved | escalated | dismissed | failed_verification",
  "title": "Find keys",
  "body": "I last saw your keys on the left side of the table.",
  "recommended_action": "Check the table near the blue bottle.",
  "evidence_observation_ids": ["obs_01HY..."],
  "created_at": "2026-06-21T16:00:00Z",
  "updated_at": "2026-06-21T16:02:00Z",
  "resolved_at": null
}
```

### Alert

```json
{
  "id": "alert_01HY...",
  "task_id": "task_01HY...",
  "hazard_type": "medicine_left_out | unattended_cooking_possible | sensor_offline | possible_fall_demo",
  "severity": "low | medium | high",
  "title": "Possible medicine left out",
  "body": "Medicine appears visible in the home zone. Please verify in person.",
  "recommended_action": "Move medicine to the safe zone or acknowledge if intentional.",
  "status": "open | acknowledged | dismissed | resolved",
  "evidence_observation_ids": ["obs_01HY..."],
  "created_at": "2026-06-21T16:00:00Z",
  "acknowledged_at": null
}
```

### QueryResponse

```json
{
  "answer": "I last saw your keys on the left side of the table beside the blue bottle about 2 minutes ago.",
  "confidence": "low | medium | high",
  "intent": "object_location | recent_activity | safety_status | unknown",
  "used_current_perception": false,
  "used_memory": true,
  "needs_human_verification": true,
  "evidence_observation_ids": ["obs_01HY..."],
  "task_id": "task_01HY...",
  "safety_disclaimer": "This is an assistive prototype. Please verify important items in person."
}
```

## Endpoints

### GET /api/health

Returns backend health and provider configuration state without secrets.

```json
{
  "ok": true,
  "version": "0.1.0",
  "environment": "development",
  "services": {
    "database": {
      "state": "ok",
      "message": "Connected",
      "checked_at": "2026-06-21T16:00:00Z"
    },
    "afferens": {
      "state": "degraded",
      "message": "No live events yet",
      "checked_at": "2026-06-21T16:00:00Z"
    }
  }
}
```

### GET /api/afferens/status

Checks Afferens configuration and latest live event availability.

Response: `AfferensStatus`.

### GET /api/afferens/latest

Attempts to fetch the latest live Afferens Vision event.

```json
{
  "ok": true,
  "raw_event": {},
  "status": {
    "configured": true,
    "state": "live",
    "message": "Live event available",
    "latest_event_id": "LIVE-VIS-MP0SH76G"
  }
}
```

### POST /api/perception/sync

Fetches one or more live Afferens Vision events, persists raw events, normalizes observations, updates memory, and may create tasks/alerts.

Request:

```json
{
  "limit": 1,
  "room_id": "default_home_zone"
}
```

Response:

```json
{
  "ok": true,
  "observations": [],
  "objects_updated": [],
  "tasks_created": [],
  "alerts_created": []
}
```

### GET /api/observations/latest

Returns the latest normalized observation and the raw event ID.

Response:

```json
{
  "observation": {}
}
```

### GET /api/objects/last-seen

Returns all last-seen object memories.

Response:

```json
{
  "objects": []
}
```

### POST /api/query

Answers a user question using current perception first, then durable memory.

Request:

```json
{
  "query": "Where are my keys?",
  "session_id": "browser-session"
}
```

Response: `QueryResponse`.

### GET /api/tasks

Returns active and recent tasks.

Query parameters:

- `state`: optional state filter.
- `type`: optional task type filter.

Response:

```json
{
  "tasks": []
}
```

### POST /api/tasks/{task_id}/verify

Attempts a live Afferens verification check for a task.

Request:

```json
{
  "room_id": "default_home_zone"
}
```

Response:

```json
{
  "ok": true,
  "task": {},
  "verification": {
    "id": "verify_01HY...",
    "state": "verified | not_verified | inconclusive",
    "observation_id": "obs_01HY...",
    "message": "Keys are visible again in the home zone."
  }
}
```

### POST /api/tasks/{task_id}/resolve

Allows explicit human resolution when live verification is not possible.

Request:

```json
{
  "resolution_note": "I found the keys.",
  "resolved_by": "user"
}
```

Response:

```json
{
  "ok": true,
  "task": {}
}
```

### GET /api/alerts

Returns alerts.

Query parameters:

- `status`: optional status filter.

Response:

```json
{
  "alerts": []
}
```

### POST /api/alerts/{alert_id}/ack

Acknowledges an alert.

Request:

```json
{
  "acknowledged_by": "caregiver",
  "note": "Checking now."
}
```

Response:

```json
{
  "ok": true,
  "alert": {}
}
```

### POST /api/actuate/alarm

Attempts a browser/dashboard alarm and optionally an Afferens actuation command.

Request:

```json
{
  "reason": "unattended_cooking_possible",
  "severity": "medium",
  "task_id": "task_01HY...",
  "use_afferens": true
}
```

Response:

```json
{
  "ok": true,
  "attempt": {
    "id": "act_01HY...",
    "provider": "afferens",
    "state": "succeeded | failed | skipped",
    "message": "Alarm command accepted."
  }
}
```

### GET /api/events/stream

SSE stream for frontend live updates.

Event types:

- `afferens_status`
- `observation_created`
- `object_memory_updated`
- `task_updated`
- `alert_updated`
- `actuation_attempted`
- `verification_completed`

