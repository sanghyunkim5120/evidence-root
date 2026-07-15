import json

from evidence_root.security.secret_store import FernetFileSecretStore, mask_key


def test_set_get_delete(tmp_path):
    store = FernetFileSecretStore(data_dir=tmp_path)
    store.set("GEMINI_API_KEY", "sk-super-secret-value")
    assert store.get("GEMINI_API_KEY") == "sk-super-secret-value"

    store.delete("GEMINI_API_KEY")
    assert store.get("GEMINI_API_KEY") is None


def test_plaintext_not_in_file(tmp_path):
    store = FernetFileSecretStore(data_dir=tmp_path)
    secret_value = "sk-super-secret-value-12345"
    store.set("GEMINI_API_KEY", secret_value)

    raw = (tmp_path / "encrypted_secrets.json").read_text(encoding="utf-8")
    assert secret_value not in raw

    parsed = json.loads(raw)
    assert all(secret_value not in v for v in parsed.values())


def test_mask_key():
    assert mask_key(None) == "(저장된 값 없음)"
    assert mask_key("AIzaSyABCDEFG7K2P") == "AIza••••7K2P"
    assert mask_key("abc") == "•••"
