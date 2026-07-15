import evidence_root.config as config


def test_required_keys_not_configured_when_all_sources_empty(monkeypatch):
    monkeypatch.setattr(config, "_session_value", lambda name: None)
    monkeypatch.setattr(config, "_st_secrets_value", lambda name: None)
    monkeypatch.setattr(config.get_secret_store(), "get", lambda name: None)
    for key in config.REQUIRED_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert config.required_keys_configured() is False


def test_required_keys_configured_when_env_set(monkeypatch):
    monkeypatch.setattr(config, "_session_value", lambda name: None)
    monkeypatch.setattr(config, "_st_secrets_value", lambda name: None)
    monkeypatch.setattr(config.get_secret_store(), "get", lambda name: None)
    for key in config.REQUIRED_KEYS:
        monkeypatch.setenv(key, "dummy-value")

    assert config.required_keys_configured() is True
