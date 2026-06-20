import json

from app.config import settings as settings_module


def test_resolve_openai_api_key_uses_opencode_env_for_zen(monkeypatch):
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "zen-key")

    value = settings_module._resolve_openai_api_key(
        "sk-or-v1-old-openrouter-key",
        "https://opencode.ai/zen/v1",
    )

    assert value == "zen-key"


def test_resolve_openai_api_key_uses_opencode_auth_file_for_stale_openrouter_key(tmp_path, monkeypatch):
    auth_dir = tmp_path / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text(
        json.dumps({"opencode": {"type": "api", "key": "zen-auth-key"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_module.Path, "home", lambda: tmp_path)
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)

    value = settings_module._resolve_openai_api_key(
        "sk-or-v1-old-openrouter-key",
        "https://opencode.ai/zen/v1",
    )

    assert value == "zen-auth-key"


def test_resolve_openai_api_key_preserves_explicit_non_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "zen-key")

    value = settings_module._resolve_openai_api_key(
        "explicit-provider-key",
        "https://opencode.ai/zen/v1",
    )

    assert value == "explicit-provider-key"
