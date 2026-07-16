import evidence_root.config as config
from evidence_root.provider_registry import ProviderRegistry


def test_registry_rebuilds_on_key_change(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "resolve_secret", lambda name: None)
    registry = ProviderRegistry()
    groq_before = registry.get("groq")
    assert groq_before.api_key is None

    values = {"GROQ_API_KEY": "new-key-value"}
    monkeypatch.setattr(config, "resolve_secret", lambda name: values.get(name))

    groq_after = registry.get("groq")
    assert groq_after is not groq_before
    assert groq_after.api_key == "new-key-value"
