#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings  # noqa: E402
from app.yolo_fall_adapter import UltralyticsFallAdapter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate local Ultralytics YOLO fall-model setup without committing "
            "or inspecting model weights."
        )
    )
    parser.add_argument(
        "--sample-frame",
        type=Path,
        help="Optional local image path for a single sample inference smoke.",
    )
    parser.add_argument(
        "--model-path",
        help="Optional override for ACTION_YOLO_FALL_MODEL_PATH.",
    )
    parser.add_argument(
        "--enable-yolo",
        action="store_true",
        help="Override ACTION_YOLO_FALL_ENABLED=true for this validation run.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero unless the model runtime is fully ready.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human-readable checklist.",
    )
    args = parser.parse_args()

    settings_kwargs: dict[str, Any] = {}
    if args.model_path:
        settings_kwargs["action_yolo_fall_model_path"] = args.model_path
    if args.enable_yolo:
        settings_kwargs["action_yolo_fall_enabled"] = True

    sample_frame_bytes = None
    if args.sample_frame is not None:
        if not args.sample_frame.is_file():
            print(f"Sample frame was not found: {args.sample_frame}", file=sys.stderr)
            return 2
        sample_frame_bytes = args.sample_frame.read_bytes()

    settings = Settings(**settings_kwargs)
    adapter = UltralyticsFallAdapter(settings)
    result = adapter.validate_setup(sample_frame_bytes=sample_frame_bytes)

    if args.json:
        print(json.dumps(_result_to_json(result), indent=2, sort_keys=True))
    else:
        _print_human(result)

    if args.require_ready and not result.ready:
        return 1
    return 0


def _result_to_json(result) -> dict[str, Any]:
    payload = {
        "ready": result.ready,
        "available": result.available,
        "status": result.status.model_dump(mode="json"),
        "checks": {
            name: asdict(check)
            for name, check in result.checks.items()
        },
    }
    if result.sample_inference is not None:
        payload["sample_inference"] = asdict(result.sample_inference)
    return payload


def _print_human(result) -> None:
    status = result.status
    state = "ready" if result.ready else status.unavailable_reason or "unavailable"
    print("YOLO fall model validation")
    print(f"State: {state}")
    print(f"Message: {status.message}")
    print(f"Provider: {status.provider}")
    print(f"Model path configured: {status.model_path_configured}")
    print(f"Model file exists: {status.model_file_exists}")
    print(f"Model loaded: {status.model_loaded}")
    if status.labels:
        print(f"Labels: {', '.join(status.labels)}")
    print("")
    print("Checks:")
    for name, check in result.checks.items():
        reason = f" ({check.reason})" if check.reason else ""
        print(f"- {name}: {check.state}{reason} - {check.message}")
    if result.sample_inference is not None:
        inference = result.sample_inference
        print("")
        print("Sample inference:")
        print(f"- available: {inference.available}")
        print(f"- fallen candidate: {inference.fallen}")
        print(f"- label: {inference.label}")
        print(f"- confidence: {inference.confidence}")
        print(f"- message: {inference.message}")
    if not result.ready:
        print("")
        print(
            "Unavailable is acceptable until a compatible local model is configured; "
            "the runtime will stay inconclusive and will not fabricate possible-fall evidence."
        )


if __name__ == "__main__":
    raise SystemExit(main())
