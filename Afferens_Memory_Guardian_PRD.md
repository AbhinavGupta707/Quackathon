# Afferens Memory Guardian — Quackathon Hardware Track PRD

**Version:** 1.0  
**Prepared for:** Quackathon 2026 Hardware / Physical Perception track  
**Recommended build decision:** Use a **phone mounted as the primary Afferens Node**, with an optional webcam/local CV process only as a support/fallback path.  
**Product concept:** A live, assistive home-memory and safety agent that perceives a real room/table through Afferens Vision, remembers where important objects were last seen, answers object-recall questions, and triggers a caregiver-facing alert when a staged risk appears.

---

## 1. Executive Decision

### Final recommendation
Build **Afferens Memory Guardian**.

> A phone camera watches a staged home zone. The agent uses Afferens Vision as the required physical perception layer, stores grounded “last-seen” object memories, answers questions like “Where are my keys?”, and triggers an audible/visual/caregiver alert when it sees a risky scene such as unattended cooking, medicine left out, or a possible fall prop.

### Why this is the best hardware-track version
This project is strong because it is:

- **Eligible:** It uses a live physical sensor node and an Afferens perception loop, not just static uploaded images.
- **Demoable:** The judge can see an object move, ask a question, and watch the system respond based on physical perception.
- **Benevolent:** It helps older adults, people with cognitive impairment, and caregivers recover context without constant manual monitoring.
- **Technically credible:** It combines real-time vision ingestion, durable memory, semantic recall, evidence grounding, safety classification, and actuation.
- **Scoped enough for a hackathon:** The demo needs one controlled room/table, 3–5 recognizable objects, one object-finding path, and one safety-alert path.

### Phone camera vs webcam decision
Use the **phone camera as primary**.

Afferens’s own warm-up flow says to open `/node` on a phone so the phone’s camera, GPS, motion, and mic become live perception streams, and the same quest asks builders to stream real Vision data and verify it with an API call. The Afferens Node page states that the device streams real sensor data to the Afferens API. A webcam can be useful for local recording or local YOLO/Grounding DINO fallback, but the phone node is the cleanest way to prove sponsor-native hardware integration.

**Recommended physical setup:**

| Requirement | Recommendation |
|---|---|
| Primary sensor | Phone on tripod or stacked stand, using Afferens `/node` |
| Lens | Rear wide-angle if available; landscape orientation |
| Position | 1.2–1.8 m high, angled 35–55° downward over a table / kitchen counter / living-room zone |
| Scene size | Keep demo constrained: 1 table or 1 corner, not a whole apartment |
| Lighting | Bright, even lighting; avoid backlighting and glare |
| Props | Keys, medicine bottle, phone, water bottle, mug, pan/stove card, caregiver-alert card |
| Optional support sensor | USB webcam for local CV debugging and backup video capture |
| Actuator | Browser alarm + LED/buzzer/ESP32 if available; otherwise Afferens `/api/actuation` `TRIGGER_ALARM` + visible web alert |

**Key design principle:** Do not try to prove whole-home generality. Prove the closed loop in one controlled physical zone: **see → remember → answer/alert → show evidence**.

---

## 2. Hackathon Requirement Mapping

### Public Quackathon requirements
The Quackathon public site says the hardware track is about deploying AI agents into the physical world using sensors and an inference loop. It also says the Better Coding Agents track focuses on persistent memory and self-healing agents, but this PRD is for the hardware track. The public FAQ says a public GitHub repo plus a two-minute demo video counts as a submission and that working code beats a polished pitch.

Source: https://quackathon.tryproduck.com/

### Afferens hardware-track requirements
Afferens’s Quackathon page frames the track as: “Your AI agent is blind. Give it eyes this weekend.” It says Afferens provides verified perception of the physical world through a hardware-agnostic API. It explicitly says Vision is live now, other modalities are rolling out, and the bar is to build things only possible because the agent can perceive. It also says judging asks:

1. **Does it work?** A live running demo beats a deck. Show the agent perceiving.
2. **Is it shipped?** Public GitHub repo + demo video.
3. **Does it answer the brief?** Track 02 is an AI agent grounded in the physical world; perception is the point.

Source: https://afferens.com/quackathon

### Detailed brief requirements from the user-provided challenge text
The original brief says the hardware track should show a project where an AI agent uses the Afferens API to perceive its environment and act on it — a closed loop of real-world input, grounded perception, and intelligent action. It also says hardware submissions require:

- Clean, documented GitHub repository.
- Demo video, with the hardware track allowing up to 3 minutes in the detailed brief.
- Live project or detailed hardware schematics.
- Clear documentation of how Afferens was used.

**Execution implication:** Make a 2:00 version for the official public page and a 2:45–3:00 fallback version if the hardware form allows it.

### Submission checklist

| Requirement | What we will submit |
|---|---|
| Public GitHub repo | `afferens-memory-guardian` with backend, frontend, Afferens adapter, demo scripts, hardware schematic, README |
| Demo video | 2:00 primary cut showing object recall + safety alert + raw Afferens evidence |
| Live project/schematics | Local runnable app + optional deployed dashboard + phone/tripod/actuator diagram |
| Tool integration | Afferens Node, Afferens REST or MCP, Afferens Vision event log, optional `/api/actuation` call |
| Hardware proof | Physical scene in camera, live Afferens response with timestamp/source node, visible alert/actuator |
| Safety disclaimer | Prototype only; not a medical device or emergency-response replacement |

---

## 3. Product Name and Positioning

### Name
**Afferens Memory Guardian**

### Tagline
**A physical-world memory assistant that remembers where things were and warns when a home scene looks risky.**

### One-line pitch
Afferens Memory Guardian uses a live phone camera node to perceive a home zone, stores grounded last-seen memories, answers object-finding questions, and alerts a caregiver when the agent sees a possible safety risk.

### Not a medical product
This is an assistive prototype. It must not be marketed as diagnosis, treatment, fall-detection certification, elder-care replacement, or emergency-response automation. The project should say:

> Afferens Memory Guardian is a functional prototype for assistive context recovery and caregiver awareness. It is not a medical device, diagnostic system, emergency-response replacement, or substitute for supervision.

---

## 4. Problem Statement

People with dementia or cognitive decline can lose confidence in ordinary daily moments: “Where are my keys?”, “Did I leave the stove on?”, “Was I in the kitchen earlier?”, “Did I already take my medicine?” Caregivers face the opposite problem: they need enough evidence to help, but cannot watch every room event or manually review footage.

The opportunity is to turn a simple camera-equipped device into a **grounded memory and safety agent**:

- It sees objects and scene states in the physical world.
- It stores timestamped, evidence-backed memories.
- It answers questions using current perception first and historical memory second.
- It flags staged risks with evidence and recommended action.

This aligns strongly with assistive-technology literature. Reviews of dementia-focused assistive technologies repeatedly identify support for daily living, safety monitoring, memory aids, and carer support as major themes.

Sources:
- Assistive technology for memory support in dementia: https://pmc.ncbi.nlm.nih.gov/articles/PMC6481376/
- Systematic review of dementia-focused assistive technology: https://oro.open.ac.uk/43917/
- Assistive technologies in dementia care: https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2021.644587/full
- Intelligent assistive technology applications to dementia care: https://pmc.ncbi.nlm.nih.gov/articles/PMC2768007/

---

## 5. Inspiration and Differentiation

### Reference project: Project Memoria
The user-provided reference is:

https://github.com/gamefreakoneone/Project-Memoria_Dementia-Assistant

Project Memoria is highly relevant. Its README describes a dementia-support prototype that combines home monitoring, grounded memory recall, object finding, safety reasoning, patient-facing mobile guidance, MongoDB memory events, ChromaDB semantic memory, Ollama embeddings, Gemma-based reasoning, Gemini video perception/spatial localization, and OpenCV + Ultralytics YOLO for computer vision.

Useful ideas to borrow:

- Grounded memory chat.
- Current-state object finding before historical recall.
- Canonical memory events.
- Evidence-backed answers.
- Safety reasoning for caregiver alerts.
- Prototype boundary language.
- FastAPI backend pattern.
- ChromaDB semantic memory.
- YOLO-based local CV.

Do **not** port the entire repo. It is broader than needed and has dependencies that are risky in a 48-hour hardware track: multi-camera assumptions, Gemini video, mobile push, local MongoDB, hardcoded camera indices, fall-detection weights, and external credential setup. Build a lean Quackathon-specific version that uses Afferens as the required perception layer.

### Differentiation from Project Memoria

| Project Memoria | Afferens Memory Guardian |
|---|---|
| General dementia-support prototype | Quackathon-specific live perception loop |
| Webcams + local/Gemini perception | Phone Afferens Node as primary sensor |
| Large stack: MongoDB, Chroma, Gemini, Ollama, Expo | Lean stack: FastAPI + SQLite/Chroma + Afferens + React |
| Multiple possible features | Two killer demo paths: object recall + safety alert |
| Built for Gemma/Kaggle | Built for Afferens hardware track |
| Healthcare-impact prototype | Physical-perception agent with clear sponsor integration |

---

## 6. User Personas

### Persona 1 — Patient / older adult
- Wants simple answers.
- May forget object locations or recent activity.
- Needs low-friction interaction: voice/text question and large answer.
- Should not be overloaded with technical details.

### Persona 2 — Caregiver
- Needs confidence that an alert has real evidence.
- Wants recent timeline: what happened, when, where, and what action was recommended.
- Needs acknowledgement flow: “checked,” “dismissed,” “on my way.”

### Persona 3 — Hackathon judge
- Needs to see the agent perceiving in the physical world.
- Needs to see that Afferens is central, not decorative.
- Needs a clear before/after: object visible → moved → remembered; unsafe scene → alert.
- Needs proof that this is working code, not a slide.

---

## 7. Core Demo Scenarios

### Scenario A — Last-seen object finding
**Goal:** Show that the agent can use physical-world perception to answer a useful memory question.

1. Phone Afferens Node is aimed at a table.
2. Table contains keys, medicine bottle, water bottle, and phone.
3. The system ingests Afferens Vision events and stores normalized object memories.
4. User removes or moves the keys.
5. User asks: “Where are my keys?”
6. Agent checks the latest Afferens observation.
7. If keys are visible: answer with current location.
8. If keys are not visible: fall back to last-seen memory.
9. UI shows: “I last saw your keys on the table, beside the blue water bottle, at 2:14 PM.”
10. Caregiver/evidence panel shows timestamp, raw Afferens event ID, normalized objects, and optional image/frame.

### Scenario B — Safety alert
**Goal:** Show perceive → reason → actuation.

1. Place a “stove on” card, red LED, hot-pan prop, or kettle prop in view.
2. Remove the person from frame or use a “no person visible” state.
3. Afferens Vision event arrives.
4. Safety classifier generates: `unattended_cooking_possible`, severity `medium/high`, confidence `demo`.
5. Agent triggers one or more actions:
   - Browser alarm sound.
   - Visual red alert on dashboard.
   - Optional Afferens `/api/actuation` `TRIGGER_ALARM`.
   - Optional local ESP32/Arduino buzzer.
   - Optional caregiver SMS/email/Expo push if already set up.
6. UI shows evidence and recommended action: “Please check the kitchen area.”

### Scenario C — Sensor failure / fail-safe
**Goal:** Show responsible design.

1. Cover the camera or disconnect Afferens Node.
2. App shows: “Cannot verify scene. Monitoring paused. Do not rely on alerts.”
3. If an action is requested, the agent refuses to make confident claims.

---

## 8. Functional Requirements

### FR1 — Afferens Node onboarding
The system must provide a setup page with:

- Afferens API key input via environment variable only; never stored in frontend localStorage.
- Link/instructions to open `https://afferens.com/node` on phone.
- “Start Sensing” checklist.
- “Test Afferens” button that calls the backend health check.
- Last raw Afferens event preview.

### FR2 — Live Afferens perception ingestion
The backend must retrieve Afferens Vision events from one of two supported paths:

**Primary path: live Node feed**

```http
GET https://afferens.com/api/perception?modality=vision&limit=1
X-API-KEY: $AFFERENS_API_KEY
```

Afferens docs describe `/api/perception` as returning structured sensory perception data, with `modality`, `limit`, timestamps, classification, confidence, spatial coordinates, source node ID, and token usage. The docs list Vision calls as 14 Sense Tokens per call.

Source: https://afferens.com/docs

**Secondary path: frame upload / image URL**

Afferens’s Quackathon page shows a `POST /api/perception` example with an `image_url`. Because the API docs and Quackathon page present slightly different call shapes, the code should implement a `PerceptionProvider` interface and a startup smoke test to detect the available route.

Source: https://afferens.com/quackathon

### FR3 — Normalize perception events
Convert raw Afferens data into a stable internal event shape.

```json
{
  "event_id": "evt_20260621_141502_abc",
  "timestamp_utc": "2026-06-21T14:15:02Z",
  "source": "afferens",
  "source_node_id": "IPHONE-IOS-01",
  "modality": "VISION",
  "room_id": "demo_table",
  "raw_classification": "iphone_camera_coco",
  "confidence": 1.0,
  "objects": [
    {
      "label": "keys",
      "aliases": ["key", "keyring"],
      "confidence": 0.82,
      "relative_location": "left side of table beside blue bottle",
      "bbox": null,
      "source": "afferens|local_yolo|grounding_dino|manual_demo_label"
    }
  ],
  "scene_summary": "Keys, medicine bottle, and water bottle are visible on the table.",
  "human_presence": "visible|not_visible|unknown",
  "risk_signals": [],
  "raw": {}
}
```

### FR4 — Object last-seen memory
Every detected object must update a `last_seen_objects` table.

```json
{
  "object_key": "keys",
  "display_name": "keys",
  "last_seen_at": "2026-06-21T14:15:02Z",
  "last_seen_room": "demo_table",
  "last_seen_relative_location": "left side of table beside blue bottle",
  "last_seen_event_id": "evt_20260621_141502_abc",
  "last_confidence": 0.82,
  "status": "visible_recently",
  "evidence_frame_url": "/evidence/evt_20260621_141502_abc.jpg"
}
```

### FR5 — Natural-language query endpoint
The app must provide a patient-facing query endpoint.

```http
POST /api/query
Content-Type: application/json

{
  "query": "Where are my keys?",
  "session_id": "demo-session"
}
```

Expected response:

```json
{
  "answer": "I last saw your keys on the left side of the table, beside the blue water bottle, about 2 minutes ago.",
  "confidence": "medium",
  "used_current_perception": false,
  "used_memory": true,
  "evidence_event_ids": ["evt_20260621_141502_abc"],
  "safety_disclaimer": "This is an assistive prototype; please verify important items in person."
}
```

### FR6 — Safety classification
The system must classify staged safety scenes using simple deterministic rules plus optional LLM reasoning.

MVP safety triggers:

| Trigger | Condition | Action |
|---|---|---|
| `unattended_cooking_possible` | stove/pan/kettle marker visible AND no person visible for N seconds | Alert caregiver + alarm |
| `medicine_left_out` | medicine bottle visible in unsafe zone for N seconds | Reminder alert |
| `possible_fall_demo` | person/fall card or local YOLO fall class visible | High-severity demo alert |
| `sensor_offline` | no Afferens event for > 30 seconds | Monitoring paused alert |

Avoid clinical claims. Use wording like “possible,” “staged,” “needs human check.”

### FR7 — Actuation
At least one visible action must happen because of perception.

Preferred actuation path:

```http
POST https://afferens.com/api/actuation
X-API-KEY: $AFFERENS_API_KEY
Content-Type: application/json

{
  "command_type": "TRIGGER_ALARM",
  "parameters": {
    "reason": "unattended_cooking_possible",
    "severity": "high"
  }
}
```

Afferens docs list `/api/actuation` and command types including `CAPTURE_FRAME`, `TRIGGER_ALARM`, `MOVE_TO`, `ROTATE_CAMERA`, `LOCK`, `UNLOCK`, `ADJUST_SENSOR`, and `SHUTDOWN_NODE`. Each actuation command costs 5 Sense Tokens.

Source: https://afferens.com/docs

Fallback actuation options:

1. Browser alarm sound and red dashboard alert.
2. ESP32/Arduino buzzer controlled through local WebSocket or serial port.
3. Twilio SMS or email to caregiver.
4. Expo local notification if mobile app exists.

For a hackathon demo, **browser alarm + visible red alert is enough** if Afferens actuation is unreliable. A physical buzzer/LED adds wow.

### FR8 — Evidence dashboard
The dashboard must show:

- Live physical scene status.
- Last raw Afferens event.
- Normalized object list.
- Last-seen memory table.
- Active alerts.
- Evidence timeline.
- “Why did the agent answer this?” explanation.

### FR9 — Demo mode
The app must include a `DEMO_MODE=true` environment setting that:

- Allows replaying saved Afferens JSON events if the live API fails during rehearsal.
- Clearly labels replayed events as replayed.
- Keeps the live path as the main video path.

The submitted demo should show real Afferens calls, but replay mode protects development and testing.

---

## 9. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Latency | Object memory update visible within 2–8 seconds after polling in demo mode |
| Reliability | App must tolerate no Afferens events, API 401/403/404, and malformed objects |
| Privacy | Do not store raw video continuously; store only selected evidence frames/events for demo |
| Security | API keys server-side only; `.env.example` committed, real `.env` ignored |
| Explainability | Every answer/alert links to at least one event ID or says evidence is insufficient |
| Safety | Never claim diagnosis, certainty, emergency response, or autonomous medical monitoring |
| Accessibility | Large text, high-contrast UI, voice-friendly copy, caregiver-readable alert language |
| Hackathon readiness | One-command local run via `docker compose up` or documented commands |

---

## 10. Proposed Architecture

```text
[Phone Afferens Node]
        |
        | real VISION data
        v
[Afferens API / MCP]
        |
        | GET /api/perception or MCP afferens_perceive
        v
[FastAPI Backend]
        |
        +--> [AfferensAdapter]
        +--> [ObservationNormalizer]
        +--> [Optional Local CV Augmenter: YOLO / Grounding DINO]
        +--> [MemoryWriter: SQLite + Chroma]
        +--> [QueryAgent]
        +--> [SafetyAgent]
        +--> [ActuationAdapter]
        |
        v
[React/Next.js Dashboard]
        |
        +--> Patient query UI
        +--> Caregiver alerts
        +--> Evidence timeline
        +--> Live raw Afferens event panel
        +--> Alarm / buzzer control
```

### Recommended stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.11 + FastAPI + Uvicorn | Fast to build, easy API, aligns with Project Memoria style |
| Frontend | Vite React or Next.js | Fast polished demo dashboard |
| Local DB | SQLite via SQLModel or SQLAlchemy | Lowest setup friction; enough for hackathon |
| Vector memory | ChromaDB optional | Easy semantic recall and aligns with Project Memoria |
| Embeddings | Ollama `embeddinggemma`, `nomic-embed-text`, or sentence-transformers | Local/private memory search; Ollama docs support embeddings for semantic search/RAG |
| Perception sponsor | Afferens Vision | Required physical-world perception integration |
| Optional CV | Ultralytics YOLO11n / YOLOv8n | Fast local object/person/fall/class support |
| Optional open-vocab CV | Grounding DINO tiny | Detect demo objects by text prompt if Afferens labels are too generic |
| Actuation | Afferens `/api/actuation`, browser alarm, optional ESP32 buzzer | Shows perceive → act loop |
| Deployment | Local demo + optional Vercel frontend / Render backend | Local is acceptable if video proves working hardware |
| Containerization | Docker Compose optional | Helps judges run it |

---

## 11. Sponsor Integration Details

### Afferens REST integration
Afferens docs list the base URL as:

```text
https://afferens.com
```

Every request requires an API key in the `X-API-KEY` header.

Source: https://afferens.com/docs

#### Perception call
```python
import os
import requests

AFFERENS_API_KEY = os.environ["AFFERENS_API_KEY"]

response = requests.get(
    "https://afferens.com/api/perception",
    headers={"X-API-KEY": AFFERENS_API_KEY},
    params={"modality": "vision", "limit": 1},
    timeout=10,
)
response.raise_for_status()
latest = response.json()
```

#### Actuation call
```python
import os
import requests

response = requests.post(
    "https://afferens.com/api/actuation",
    headers={
        "X-API-KEY": os.environ["AFFERENS_API_KEY"],
        "Content-Type": "application/json",
    },
    json={
        "command_type": "TRIGGER_ALARM",
        "parameters": {
            "reason": "unattended_cooking_possible",
            "severity": "high",
        },
    },
    timeout=10,
)
response.raise_for_status()
```

### Afferens MCP integration
Afferens docs show a standard stdio MCP server with `@afferens/mcp-server`:

```bash
claude mcp add afferens -e AFFERENS_API_KEY=YOUR_KEY -- npx -y @afferens/mcp-server
```

The Quackathon page shows an MCP config using `@afferens/mcp` and `AFFERENS_KEY`. Because the names differ across pages, implementation should support REST first and include MCP setup docs with both variants:

```json
{
  "mcpServers": {
    "afferens": {
      "command": "npx",
      "args": ["-y", "@afferens/mcp-server"],
      "env": { "AFFERENS_API_KEY": "YOUR_KEY" }
    }
  }
}
```

If package resolution fails, try the Quackathon snippet:

```json
{
  "mcpServers": {
    "afferens": {
      "command": "npx",
      "args": ["-y", "@afferens/mcp"],
      "env": { "AFFERENS_KEY": "YOUR_KEY" }
    }
  }
}
```

Sources:
- API docs: https://afferens.com/docs
- Quackathon page: https://afferens.com/quackathon

### Token budgeting
Afferens docs list Vision calls at 14 Sense Tokens per call. The warm-up quest says free accounts get 10,000 Sense Tokens. That gives approximately:

```text
10,000 / 14 = ~714 Vision calls
```

For the demo, poll every 3–5 seconds only while actively rehearsing or recording. Do not stream continuously for hours.

Sources:
- Token/call cost: https://afferens.com/docs
- Free tier mention: https://afferens.com/quest

---

## 12. Optional Open-Source Vision Integration

Afferens must remain the primary integration. Open-source models should only augment the Afferens feed, improve object naming/localization, or provide fallback in rehearsal.

### Option A — Ultralytics YOLO
Use for fast local detection/tracking of people, bottles, phones, cups, chairs, etc. Ultralytics provides Python APIs for object detection, segmentation, classification, and model training; its tracking docs describe multi-object tracking with IDs using trackers like BoT-SORT and ByteTrack.

Sources:
- Python usage: https://docs.ultralytics.com/usage/python
- Tracking: https://docs.ultralytics.com/modes/track

Recommended MVP use:

```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")  # or yolo8n/yolo26n depending installed docs/version
results = model("frame.jpg")
```

Use only if setup is easy. The app can ship without local YOLO if Afferens results are sufficient.

### Option B — Grounding DINO
Use for open-vocabulary object detection: “keys,” “medicine bottle,” “stove knob,” “walking cane,” etc. Grounding DINO is open-set detection using text prompts. The official GitHub repo and Hugging Face docs describe text-conditioned object detection and CPU support.

Sources:
- Official repo: https://github.com/IDEA-Research/GroundingDINO
- Hugging Face docs: https://huggingface.co/docs/transformers/en/model_doc/grounding-dino

Recommended MVP use:

- Do not run Grounding DINO live unless the machine has enough resources.
- Use it as a fallback enrichment step on captured frames.
- Good for demo screenshots: draw box around “keys” or “medicine bottle.”

### Option C — MediaPipe Object Detector
MediaPipe’s Object Detector accepts still images, decoded video frames, or live video feed and outputs detected categories, probability scores, and bounding boxes. This is useful for lightweight local/browser inference if Afferens labels are too coarse.

Source: https://developers.google.com/edge/mediapipe/solutions/vision/object_detector

### Option D — ChromaDB + Ollama embeddings
Chroma is open-source AI search infrastructure with a simple Python client and collections for documents/metadata. Ollama docs describe embeddings as numeric vectors for semantic search, retrieval, and RAG.

Sources:
- Chroma: https://github.com/chroma-core/chroma
- Ollama embeddings: https://docs.ollama.com/capabilities/embeddings

Recommended use:

- Store event summaries such as: “At 2:14 PM, keys were on the left side of the table beside the blue bottle.”
- Query semantically for “Where were my keys?” or “Was I cooking earlier?”
- Keep SQLite as source of truth; Chroma is rebuildable.

---

## 13. Kaggle / Dataset Research for Optional Extension

Do not train a model during the 48-hour MVP unless necessary. If future work needs specialized detection, these datasets are relevant:

| Dataset / resource | Use | Link |
|---|---|---|
| Fall Detection Dataset | Image-based fall demo/future fine-tuning | https://www.kaggle.com/datasets/uttejkumarkandagatla/fall-detection-dataset |
| Fall Detection Dataset — 10,000 videos | Video fall-detection experimentation | https://www.kaggle.com/datasets/unidpro/fall-detection |
| CCTV Incident Dataset — Fall & Lying Down | Synthetic fall/lying-down CV tasks | https://www.kaggle.com/datasets/simuletic/cctv-incident-dataset-fall-and-lying-down-detection |
| Bottles and Cups Dataset | Household object detection | https://www.kaggle.com/datasets/dataclusterlabs/bottles-and-cups-dataset |
| Drug Name Detection Dataset | Medicine packaging recognition extension | https://www.kaggle.com/datasets/pkdarabi/the-drug-name-detection-dataset |
| Household Products | General household object recognition | https://www.kaggle.com/datasets/taru149/householdproducts |

Academic caveat: fall detection in real homes is hard. A 2022 multi-visual-modality fall detection dataset paper notes challenges like lighting, privacy, camera placement, and variability of falls. Use fall detection only as a staged demo or optional extension unless validated.

Source: https://arxiv.org/abs/2206.12740

---

## 14. Data Model

### SQLite tables

#### `observations`
```sql
CREATE TABLE observations (
  id TEXT PRIMARY KEY,
  timestamp_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  source_node_id TEXT,
  modality TEXT NOT NULL,
  room_id TEXT NOT NULL,
  scene_summary TEXT,
  human_presence TEXT,
  raw_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

#### `detected_objects`
```sql
CREATE TABLE detected_objects (
  id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL,
  object_key TEXT NOT NULL,
  label TEXT NOT NULL,
  aliases_json TEXT,
  confidence REAL,
  relative_location TEXT,
  bbox_json TEXT,
  source TEXT NOT NULL,
  FOREIGN KEY(observation_id) REFERENCES observations(id)
);
```

#### `last_seen_objects`
```sql
CREATE TABLE last_seen_objects (
  object_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  last_seen_room TEXT NOT NULL,
  last_seen_relative_location TEXT,
  last_seen_observation_id TEXT NOT NULL,
  last_confidence REAL,
  evidence_frame_url TEXT,
  updated_at TEXT NOT NULL
);
```

#### `alerts`
```sql
CREATE TABLE alerts (
  id TEXT PRIMARY KEY,
  observation_id TEXT,
  hazard_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  recommended_action TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  acknowledged_at TEXT,
  FOREIGN KEY(observation_id) REFERENCES observations(id)
);
```

#### `queries`
```sql
CREATE TABLE queries (
  id TEXT PRIMARY KEY,
  query_text TEXT NOT NULL,
  answer_text TEXT NOT NULL,
  confidence TEXT NOT NULL,
  evidence_observation_ids_json TEXT,
  created_at TEXT NOT NULL
);
```

---

## 15. API Specification

### Health
```http
GET /api/health
```

Response:
```json
{
  "ok": true,
  "version": "1.0.0",
  "afferens_configured": true,
  "demo_mode": false
}
```

### Afferens test
```http
POST /api/afferens/test
```

Response:
```json
{
  "ok": true,
  "mode": "live",
  "latest_event": {},
  "source_node_id": "IPHONE-IOS-01",
  "timestamp_utc": "2026-06-21T14:15:02Z"
}
```

### Sync one perception event
```http
POST /api/perception/sync
```

Response:
```json
{
  "ok": true,
  "observation_id": "evt_...",
  "objects_updated": ["keys", "medicine_bottle"],
  "alerts_created": []
}
```

### Query
```http
POST /api/query
```

Request:
```json
{
  "query": "Where are my keys?",
  "session_id": "demo-session"
}
```

Response:
```json
{
  "answer": "I last saw your keys on the left side of the table beside the blue bottle at 2:14 PM.",
  "confidence": "medium",
  "evidence": [
    {
      "observation_id": "evt_...",
      "timestamp": "2026-06-21T14:14:00Z",
      "summary": "Keys visible beside blue bottle."
    }
  ]
}
```

### Alerts
```http
GET /api/alerts?status=open
POST /api/alerts/{alert_id}/ack
```

### Actuate
```http
POST /api/actuate/alarm
```

Request:
```json
{
  "reason": "unattended_cooking_possible",
  "severity": "high",
  "use_afferens": true,
  "use_browser_alarm": true
}
```

---

## 16. Reasoning Agent Specification

### Query agent prompt contract
The query agent must produce structured JSON, not free-form only.

Input:

```json
{
  "user_query": "Where are my keys?",
  "latest_observation": {},
  "last_seen_memory": {},
  "semantic_memories": [],
  "safety_policy": "Prototype only; do not claim certainty or emergency response."
}
```

Output:

```json
{
  "intent": "object_location",
  "answer": "I last saw your keys on the left side of the table beside the blue bottle at 2:14 PM.",
  "confidence": "low|medium|high",
  "used_current_perception": true,
  "used_historical_memory": true,
  "evidence_observation_ids": ["evt_..."],
  "needs_human_verification": true,
  "should_alert_caregiver": false
}
```

### Safety agent prompt contract
Input:

```json
{
  "latest_observation": {},
  "active_objects": ["pan", "red stove marker"],
  "human_presence": "not_visible",
  "recent_history": [],
  "policy": "Only assistive safety alerts; do not claim emergency certainty."
}
```

Output:

```json
{
  "hazard_detected": true,
  "hazard_type": "unattended_cooking_possible",
  "severity": "medium",
  "confidence": "medium",
  "title": "Possible unattended cooking",
  "body": "The stove marker/pan is visible and no person is currently visible in the demo scene.",
  "recommended_action": "Please check the kitchen area.",
  "actuate": true,
  "evidence_observation_ids": ["evt_..."]
}
```

### Rule-first safety logic
Do not depend entirely on an LLM for safety triggers. Use deterministic rules first:

```python
if scene.has_any(["stove", "pan", "kettle", "red stove marker"]) and scene.human_presence == "not_visible":
    create_alert("unattended_cooking_possible", severity="medium")
```

LLM reasoning can improve wording and explanation only.

---

## 17. Frontend Specification

### Pages

#### `/setup`
- Afferens setup checklist.
- Phone-node instructions.
- Live status: connected/offline.
- Last raw event.

#### `/dashboard`
- Main demo dashboard.
- Large current status card.
- Last-seen object table.
- Active alerts.
- Raw Afferens event panel.
- Evidence timeline.

#### `/ask`
- Patient-facing query UI.
- Large text input: “Ask where something is…”
- Suggested prompts:
  - “Where are my keys?”
  - “Where did I leave my phone?”
  - “Was I near the kitchen earlier?”
- Large answer with evidence note.

#### `/caregiver`
- Active alerts.
- Acknowledge/dismiss buttons.
- Evidence event and recommended action.

### UI components

| Component | Purpose |
|---|---|
| `LivePerceptionCard` | Shows latest Afferens event timestamp/source node |
| `ObjectMemoryTable` | Shows object, location, last seen, confidence |
| `EvidenceTimeline` | Shows chronological physical observations |
| `AskBox` | Query input + answer |
| `AlertBanner` | Safety alert with actuation status |
| `RawJsonDrawer` | Proof of Afferens integration |
| `DemoControls` | Sync, simulate/stage label, trigger test alarm |

### Visual demo requirement
The dashboard must make the physical loop obvious:

```text
Physical scene changed → Afferens event updated → Memory updated → Answer/alert produced → Action triggered
```

---

## 18. Hardware Specification

### Required hardware

| Item | Minimum | Recommended |
|---|---|---|
| Phone | Any modern iOS/Android with camera and browser | Phone with wide-angle rear camera |
| Mount | Books/box stand | Tripod/phone clamp |
| Laptop | Runs backend/frontend | Laptop with stable Wi-Fi and screen recording |
| Props | Keys, bottle, phone, medicine box, pan/stove marker | High-contrast labeled props |
| Actuator | Browser alarm | LED/buzzer/ESP32 or smart plug prop |

### Physical scene design
Use a constrained demo scene:

```text
[ Phone Afferens Node ]
          ↓ angled down
┌───────────────────────────────────┐
│ Demo table / counter              │
│                                   │
│ [Keys]   [Blue bottle] [Medicine] │
│                                   │
│ [Phone]  [Pan/stove marker]       │
│                                   │
└───────────────────────────────────┘
```

### Field-of-view guidance

- Put the phone far enough to see the whole table, not so far that keys are tiny.
- Use landscape orientation.
- Prefer wide-angle rear camera.
- Use high-contrast objects and large labels if necessary.
- Do not use tiny dark keys on a dark table; place keys on white paper or attach a bright keychain.
- Use consistent lighting.
- In the demo, call it a “home zone” rather than a full-home deployment.

### Optional physical actuator wiring

#### ESP32/Arduino buzzer path

```text
Laptop backend --WebSocket/HTTP--> ESP32 local endpoint --> buzzer/LED
```

Minimum pseudo-code:

```cpp
// ESP32 pseudocode
if (server receives /alarm?on=true) {
  digitalWrite(LED_PIN, HIGH);
  tone(BUZZER_PIN, 2000, 1000);
}
```

If ESP32 setup takes too long, use the browser alarm and red dashboard alert.

---

## 19. Implementation Plan

### Phase 0 — 60-minute validation
Goal: prove Afferens live path before building product.

1. Sign up for Afferens key.
2. Open `https://afferens.com/node` on phone.
3. Start sensing.
4. Run curl:

```bash
curl "https://afferens.com/api/perception?modality=vision&limit=1" \
  -H "X-API-KEY: $AFFERENS_API_KEY"
```

5. Save a successful JSON response to `demo/afferens_live_sample.json`.
6. If GET route fails, test the Quackathon `POST /api/perception` `image_url` route.
7. Write down source node ID, timestamp, and object/classification fields.

Acceptance: one real Afferens event appears in terminal.

### Phase 1 — Backend skeleton

Files:

```text
backend/
  app/main.py
  app/config.py
  app/afferens_adapter.py
  app/models.py
  app/db.py
  app/normalizer.py
  app/memory.py
  app/safety.py
  app/query_agent.py
  app/actuation.py
  requirements.txt
```

Tasks:

- FastAPI app.
- `/api/health`.
- Afferens adapter.
- SQLite models.
- Perception sync endpoint.
- Save raw event and normalized observation.

### Phase 2 — Dashboard

Files:

```text
frontend/
  src/pages/Dashboard.tsx
  src/pages/Setup.tsx
  src/pages/Ask.tsx
  src/components/LivePerceptionCard.tsx
  src/components/ObjectMemoryTable.tsx
  src/components/AlertBanner.tsx
  src/components/EvidenceTimeline.tsx
```

Tasks:

- Poll backend.
- Show raw Afferens event.
- Show last-seen objects.
- Query endpoint UI.
- Active alert UI.

### Phase 3 — Memory and query

Tasks:

- Implement object aliases.
- Implement object location query routing.
- Store last-seen memory.
- Add Chroma optional semantic store.
- Add evidence-backed answer format.

### Phase 4 — Safety and actuation

Tasks:

- Implement deterministic safety rules.
- Implement alert creation.
- Implement `/api/actuate/alarm`.
- Add browser alarm.
- Add Afferens `/api/actuation` call.
- Optional ESP32 buzzer.

### Phase 5 — Demo hardening

Tasks:

- Add `DEMO_MODE` replay support.
- Add saved fixtures.
- Add “clear memory” button.
- Add README.
- Rehearse demo 5 times.
- Screen-record physical scene + dashboard side-by-side.

---

## 20. Repository Structure

```text
afferens-memory-guardian/
  README.md
  .env.example
  docker-compose.yml
  docs/
    PRD.md
    HARDWARE_SETUP.md
    AFFERENS_INTEGRATION.md
    DEMO_SCRIPT.md
    SAFETY_BOUNDARIES.md
  backend/
    app/
      main.py
      config.py
      afferens_adapter.py
      actuation.py
      db.py
      models.py
      normalizer.py
      memory.py
      safety.py
      query_agent.py
      schemas.py
    tests/
      test_normalizer.py
      test_memory.py
      test_safety.py
    requirements.txt
  frontend/
    package.json
    src/
      App.tsx
      api.ts
      pages/
      components/
  demo/
    afferens_live_sample.json
    fixtures/
      keys_visible.json
      keys_missing.json
      unattended_cooking.json
    screenshots/
    video_script.md
  hardware/
    setup_diagram.png
    wiring_optional_esp32.md
```

---

## 21. Acceptance Criteria

### Must pass before submission

| Area | Acceptance criterion |
|---|---|
| Afferens live integration | Real phone-node Vision event appears in app with timestamp/source node |
| Object memory | Placing keys in view updates last-seen memory |
| Object query | “Where are my keys?” returns answer with location and evidence |
| Historical fallback | Removing keys returns last-seen answer, not hallucinated current visibility |
| Safety alert | Staged hazard creates alert and triggers visible/audible action |
| Actuation | At least browser alarm works; Afferens actuation attempted/logged if available |
| Evidence | Every answer/alert links to raw Afferens event or normalized observation |
| Safety boundary | UI and README state prototype is not medical/emergency system |
| Demo | Video shows physical scene, Afferens event, memory/answer, alert/action |
| Repo | README has setup, environment variables, run instructions, hardware diagram |

### Nice-to-have

- Local YOLO overlay boxes on objects.
- Grounding DINO open-vocabulary enrichment for “keys” and “medicine bottle.”
- Caregiver SMS/email.
- Mobile UI.
- ESP32/Arduino buzzer.
- Multimodal Afferens when spatial/acoustic/environmental APIs become live.

---

## 22. Testing Strategy

### Unit tests

- `test_normalizer.py`: raw Afferens event → normalized observation.
- `test_memory.py`: new object observation updates `last_seen_objects`.
- `test_query_agent.py`: “Where is X?” returns current if visible, historical if not.
- `test_safety.py`: hazard rules trigger only on intended combinations.

### Integration tests

- Mock Afferens response fixture.
- Backend sync saves observation.
- Frontend displays memory table.
- Alert endpoint creates and acknowledges alerts.

### Live demo tests

Run these before recording:

1. Phone node connected.
2. Afferens API key works.
3. Latest event timestamp is current.
4. Keys visible → memory updates.
5. Keys removed → last-seen answer still correct.
6. Stove marker/person absent → alert triggers.
7. Browser alarm audible.
8. Raw JSON drawer shows Afferens response.

---

## 23. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Afferens does not label “keys” specifically | Object query may fail | Use high-contrast keychain, label card, optional Grounding DINO/local YOLO enrichment, and alias mapping |
| Field of view too wide; objects too small | Low confidence | Constrain scene to one table; use phone close enough; use bright props |
| API docs mismatch GET vs POST | Integration delay | Implement `PerceptionProvider`; smoke test both live GET and image_url POST routes |
| Token usage too high | Runs out of credits | Poll every 3–5 seconds only during demo; use fixtures during dev |
| Safety claim too strong | Judge/safety concern | Use “possible,” “assistive,” “human verification needed”; no medical claims |
| Push notification setup takes too long | No caregiver action | Use browser alarm + dashboard alert as guaranteed actuation |
| Local model setup fails | Delays MVP | Make local CV optional; Afferens live path must work alone |
| Afferens actuation target unavailable | Action gap | Browser alarm/local buzzer fallback; log attempted actuation call |
| Lighting/background issues | Bad perception | Use white table/paper, clear props, bright lights, no clutter |

---

## 24. Demo Script

### 2-minute version

**0:00–0:15 — Hook**  
“AI assistants can answer questions, but they cannot remember where real things are. Afferens Memory Guardian gives an agent live physical perception.”

**0:15–0:35 — Show hardware**  
Show phone on tripod pointed at table. Open dashboard. Show Afferens source node and latest Vision event.

**0:35–0:55 — Object memory**  
Place keys beside blue bottle. Click Sync. Dashboard updates: “keys last seen beside blue bottle.”

**0:55–1:15 — Object finding**  
Move/remove keys. Ask: “Where are my keys?” App answers with last-seen location and evidence.

**1:15–1:40 — Safety alert**  
Place stove/pan marker, leave frame/no person visible. Sync. Safety alert appears: “Possible unattended cooking.” Browser alarm/LED triggers.

**1:40–1:55 — Evidence**  
Open raw Afferens JSON drawer. Show timestamp/source node and normalized event.

**1:55–2:00 — Close**  
“This is not a camera dashboard. It is a physical perception loop: see, remember, reason, act.”

### 3-minute hardware version
Add:

- Sensor failure fail-safe.
- Caregiver acknowledgement.
- Short architecture view.

---

## 25. README Requirements

The README must include:

```md
# Afferens Memory Guardian

## One-line summary
## Demo video
## Live demo / screenshots
## Track: Hardware / Physical Perception
## What it does
## Why Afferens is central
## Hardware setup
## Architecture
## Afferens integration
## Tech stack
## How to run
## Environment variables
## Demo script
## Safety boundaries
## Limitations
## Future work
```

Required environment variables:

```env
AFFERENS_API_KEY=aff_live_...
AFFERENS_BASE_URL=https://afferens.com
DEMO_MODE=false
DATABASE_URL=sqlite:///./memory_guardian.db
CHROMA_PATH=./storage/chroma
POLL_INTERVAL_SECONDS=4
```

---

## 26. Final Build Recommendation

Build the **lean version**:

1. Phone Afferens Node.
2. FastAPI backend.
3. React dashboard.
4. SQLite object memory.
5. Optional Chroma semantic recall.
6. One object-finding path.
7. One safety-alert path.
8. Browser alarm / optional LED buzzer.
9. Raw Afferens evidence panel.

Do **not** build:

- Full mobile app unless there is extra time.
- Full fall-detection pipeline as the main demo.
- Multi-room monitoring.
- Medical-grade alerts.
- Continuous surveillance product.
- Complex caregiver auth.

The winning demo is not “we built a dementia app.” The winning demo is:

> “A real phone sensor streamed Afferens Vision into an agent. The agent remembered where a real object was, answered a human question with evidence, and triggered an action when a staged risk appeared.”

---

## 27. Source Links

### Hackathon and sponsor docs
- Quackathon public page: https://quackathon.tryproduck.com/
- Afferens docs: https://afferens.com/docs
- Afferens Quackathon page: https://afferens.com/quackathon
- Afferens Node page: https://afferens.com/node
- Afferens warm-up quest: https://afferens.com/quest
- Afferens Founders Pass / Vision status: https://afferens.com/founders-pass

### Reference project
- Project Memoria GitHub repo: https://github.com/gamefreakoneone/Project-Memoria_Dementia-Assistant
- Project Memoria raw README: https://raw.githubusercontent.com/gamefreakoneone/Project-Memoria_Dementia-Assistant/main/README.md

### Open-source / model docs
- ChromaDB GitHub: https://github.com/chroma-core/chroma
- Ollama embeddings docs: https://docs.ollama.com/capabilities/embeddings
- Ultralytics YOLO Python docs: https://docs.ultralytics.com/usage/python
- Ultralytics tracking docs: https://docs.ultralytics.com/modes/track
- Grounding DINO GitHub: https://github.com/IDEA-Research/GroundingDINO
- Grounding DINO Hugging Face docs: https://huggingface.co/docs/transformers/en/model_doc/grounding-dino
- MediaPipe Object Detector: https://developers.google.com/edge/mediapipe/solutions/vision/object_detector

### Research and datasets
- Assistive technology for memory support in dementia: https://pmc.ncbi.nlm.nih.gov/articles/PMC6481376/
- Systematic review of dementia-focused assistive technology: https://oro.open.ac.uk/43917/
- Assistive technologies in dementia care: https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2021.644587/full
- Intelligent assistive technology applications to dementia care: https://pmc.ncbi.nlm.nih.gov/articles/PMC2768007/
- Multi Visual Modality Fall Detection Dataset: https://arxiv.org/abs/2206.12740
- Kaggle Fall Detection Dataset: https://www.kaggle.com/datasets/uttejkumarkandagatla/fall-detection-dataset
- Kaggle CCTV Incident Dataset — Fall & Lying Down Detection: https://www.kaggle.com/datasets/simuletic/cctv-incident-dataset-fall-and-lying-down-detection
- Kaggle Bottles and Cups Dataset: https://www.kaggle.com/datasets/dataclusterlabs/bottles-and-cups-dataset
- Kaggle Drug Name Detection Dataset: https://www.kaggle.com/datasets/pkdarabi/the-drug-name-detection-dataset
