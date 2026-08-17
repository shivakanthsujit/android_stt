#!/usr/bin/env python3
"""Check the pinned vLLM LoRA endpoint without external Python dependencies."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "training/config/vllm-serving-v1.json"


def request_json(url: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{url} did not return a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    server = config["server"]
    adapter_name = config["adapter"]["served_name"]
    base_url = f"http://{server['host']}:{server['port']}"
    models = request_json(base_url + "/v1/models")
    model_ids = {
        item.get("id") for item in models.get("data", []) if isinstance(item, dict)
    }
    if adapter_name not in model_ids:
        raise RuntimeError(f"configured LoRA is absent from /v1/models: {model_ids}")
    response = request_json(
        base_url + "/v1/chat/completions",
        {
            "model": adapter_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Output only the user's text with no explanation.",
                },
                {"role": "user", "content": "server smoke test"},
            ],
            "temperature": 0,
            "max_tokens": 16,
            "seed": 23,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("chat completion returned no choices")
    content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("chat completion returned empty content")
    print(json.dumps({"models": sorted(model_ids), "smoke_output": content.strip()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
