#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/auto",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
}


def main() -> int:
    args = parse_args()
    api_key = args["api_key"]
    provider = args["provider"]
    base_url = args["base_url"]
    model = args["model"]

    error = validate_key_shape(api_key)
    if error:
        print(f"ERROR: {error}")
        return 1

    write_env(api_key=api_key, base_url=base_url, model=model)
    print(f".env configured for provider={provider}, model={model}.")

    ok, message = validate_with_provider(api_key=api_key, base_url=base_url)
    if not ok:
        print(f"ERROR: {message}")
        print("The key was written to .env, but OpenAI validation failed.")
        return 1

    print("OpenAI key validation: OK")
    print("You can now run: make ask Q=\"Quiero transferir dinero\"")
    return 0


def parse_args() -> dict[str, str]:
    values = {
        "provider": os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        "api_key": "",
        "base_url": "",
        "model": "",
    }
    index = 1
    while index < len(sys.argv):
        arg = sys.argv[index]
        if arg in {"--key", "-k"} and index + 1 < len(sys.argv):
            values["api_key"] = sys.argv[index + 1].strip()
            index += 2
        elif arg == "--provider" and index + 1 < len(sys.argv):
            values["provider"] = sys.argv[index + 1].strip().lower()
            index += 2
        elif arg == "--base-url" and index + 1 < len(sys.argv):
            values["base_url"] = sys.argv[index + 1].strip()
            index += 2
        elif arg == "--model" and index + 1 < len(sys.argv):
            values["model"] = sys.argv[index + 1].strip()
            index += 2
        elif not values["api_key"]:
            values["api_key"] = arg.strip()
            index += 1
        else:
            index += 1

    provider_defaults = PROVIDERS.get(values["provider"], {})
    values["base_url"] = values["base_url"] or provider_defaults.get("base_url", "")
    values["model"] = values["model"] or provider_defaults.get("model", "")
    if not values["base_url"]:
        values["base_url"] = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not values["model"]:
        values["model"] = os.getenv("INTENT_LLM_MODEL", "gpt-4o-mini")
    if not values["api_key"]:
        values["api_key"] = getpass.getpass("LLM API key: ").strip()
    return values


def validate_key_shape(api_key: str) -> str | None:
    if not api_key:
        return "Missing API key."
    if api_key in {"tu_api_key", "PEGA_AQUI_TU_KEY", "sk-tu_key_real", "sk-tu_key_nueva"}:
        return "The value is still a placeholder."
    if len(api_key) < 40:
        return "The key looks too short."
    if any(char.isspace() for char in api_key):
        return "The key contains whitespace."
    return None


def write_env(api_key: str, base_url: str, model: str) -> None:
    values = read_env()
    values.update(
        {
            "NEO4J_URI": values.get("NEO4J_URI", "bolt://localhost:7687"),
            "NEO4J_USER": values.get("NEO4J_USER", "neo4j"),
            "NEO4J_PASSWORD": values.get("NEO4J_PASSWORD", "banking-intent-dev"),
            "OPENAI_API_KEY": api_key,
            "OPENAI_BASE_URL": base_url,
            "INTENT_LLM_MODEL": model,
            "USE_AI_PROVIDERS": "true",
            "QDRANT_HOST": values.get("QDRANT_HOST", "http://localhost:6333"),
            "QDRANT_API_KEY": values.get("QDRANT_API_KEY", ""),
        }
    )

    ordered_keys = [
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "INTENT_LLM_MODEL",
        "USE_AI_PROVIDERS",
        "QDRANT_HOST",
        "QDRANT_API_KEY",
    ]
    lines = []
    for key in ordered_keys:
        lines.append(f"{key}={values.get(key, '')}")
        if key in {"NEO4J_PASSWORD", "USE_AI_PROVIDERS"}:
            lines.append("")
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    values: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def validate_with_provider(api_key: str, base_url: str) -> tuple[bool, str]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status == 200:
                body = json.loads(response.read().decode("utf-8"))
                count = len(body.get("data", []))
                return True, f"Validated with {count} available models."
            return False, f"Unexpected provider response status: {response.status}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            return False, "Provider rejected the key with 401 invalid_api_key."
        return False, f"Provider request failed: HTTP {exc.code} {detail}"
    except urllib.error.URLError as exc:
        return False, f"Could not reach provider API: {exc.reason}"
    except TimeoutError:
        return False, "Provider validation timed out."


if __name__ == "__main__":
    raise SystemExit(main())
