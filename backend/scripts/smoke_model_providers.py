from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(REPO_ROOT / ".env")

from app.config import get_settings  # noqa: E402
from app.observability import langsmith_status  # noqa: E402
from app.providers.fireworks import (  # noqa: E402
    FireworksProviderError,
    FireworksProviderUnavailable,
    FireworksReasoningAdapter,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke model provider readiness without printing secrets.")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Return non-zero when FIREWORKS_API_KEY is missing instead of accepting deterministic fallback.",
    )
    args = parser.parse_args()

    get_settings.cache_clear()
    settings = get_settings()

    fireworks_status = FireworksReasoningAdapter(settings).status()
    langsmith = langsmith_status(settings)

    print("Model provider smoke")
    print(f"Fireworks: {fireworks_status.state} - {fireworks_status.message}")
    print(f"LangSmith: {langsmith.state} - {langsmith.message}")

    if not settings.fireworks_configured:
        print("SKIP Fireworks live call: FIREWORKS_API_KEY is not configured.")
        return 2 if args.require_live else 0

    adapter = FireworksReasoningAdapter(settings)
    try:
        result = await adapter.route_query(
            query="Where is the bottle?",
            known_object_keys=["bottle", "keys"],
        )
    except (FireworksProviderUnavailable, FireworksProviderError, ValueError) as exc:
        print(f"FAIL Fireworks structured call: {exc}")
        return 1

    print("OK Fireworks structured call")
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    if settings.langsmith_runtime_enabled:
        print("OK LangSmith tracing was enabled for this provider call.")
    else:
        print("SKIP LangSmith trace upload: tracing is disabled or no key is configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
