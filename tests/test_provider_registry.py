import evidence_root.config as config
from evidence_root.provider_registry import ProviderRegistry


def test_registry_rebuilds_on_key_change(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "resolve_secret", lambda name: None)
    registry = ProviderRegistry()
    gemini_before = registry.get("gemini")
    assert gemini_before.api_key is None

    values = {"GEMINI_API_KEY": "new-key-value"}
    monkeypatch.setattr(config, "resolve_secret", lambda name: values.get(name))

    gemini_after = registry.get("gemini")
    assert gemini_after is not gemini_before
    assert gemini_after.api_key == "new-key-value"
