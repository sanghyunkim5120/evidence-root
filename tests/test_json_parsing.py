from evidence_root.providers.base import parse_json_response


def test_parses_clean_json_array():
    result = parse_json_response('[{"id": "E1", "stance": "support"}]')
    assert result == [{"id": "E1", "stance": "support"}]


def test_salvages_complete_items_from_truncated_array():
    truncated = '[{"id": "E1", "stance": "support"}, {"id": "E2", "stance": "refute"}, {"id": "E3", "sta'
    result = parse_json_response(truncated)
    assert result == [{"id": "E1", "stance": "support"}, {"id": "E2", "stance": "refute"}]


def test_returns_none_for_unsalvageable_garbage():
    assert parse_json_response("이건 그냥 텍스트고 JSON이 아님") is None


def test_returns_none_for_empty():
    assert parse_json_response("") is None
    assert parse_json_response(None) is None
