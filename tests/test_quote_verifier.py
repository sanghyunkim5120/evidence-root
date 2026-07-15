from evidence_root.utils.quote_verifier import quote_exists_in_text


def test_quote_exists():
    source = "정부는 15일 오전 서울에서 긴급 브리핑을 열고 관련 대책을 발표했다."
    assert quote_exists_in_text("정부는 15일 오전 서울에서 긴급 브리핑을 열고", source)


def test_quote_not_exists():
    source = "정부는 15일 오전 서울에서 긴급 브리핑을 열고 관련 대책을 발표했다."
    assert not quote_exists_in_text("대통령이 사퇴를 선언했다", source)


def test_empty_quote():
    assert not quote_exists_in_text("", "아무 내용")
    assert not quote_exists_in_text("ab", "ab는 짧다")
