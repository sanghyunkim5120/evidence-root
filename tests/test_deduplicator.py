from evidence_root.schemas import Evidence
from evidence_root.services.deduplicator import deduplicate, normalize_url


def _evidence(idx, url, title, body, publisher=""):
    return Evidence(
        evidence_id=f"E{idx}",
        claim_id="C1",
        url=url,
        canonical_url=url,
        title=title,
        body_text=body,
        publisher=publisher,
    )


def test_republished_articles_share_cluster():
    body = "정부는 15일 긴급 브리핑을 열고 재난 대책을 발표했다. 총 500억원의 예산을 투입한다고 밝혔다."
    evidences = [
        _evidence(1, "https://a.com/news/1?utm_source=x", "정부, 재난 대책 발표", body, "언론사A"),
        _evidence(2, "https://b.com/news/2", "정부, 재난 대책 발표", body, "언론사B"),
        _evidence(3, "https://c.com/news/3", "[속보] 정부, 재난 대책 발표", body, "언론사C"),
    ]
    result = deduplicate(evidences)
    cluster_ids = {e.duplicate_cluster_id for e in result}
    assert len(cluster_ids) == 1


def test_independent_reporting_gets_separate_cluster():
    body_a = "정부는 15일 긴급 브리핑을 열고 재난 대책을 발표했다. 총 500억원의 예산을 투입한다고 밝혔다."
    body_b = "본지 취재 결과 지역 주민들은 이번 대책에 대해 엇갈린 반응을 보였다. 일부는 환영했고 일부는 우려를 표했다."
    evidences = [
        _evidence(1, "https://a.com/news/1", "정부, 재난 대책 발표", body_a, "언론사A"),
        _evidence(2, "https://d.com/news/9", "주민 반응 엇갈려... 현장 취재", body_b, "언론사D"),
    ]
    result = deduplicate(evidences)
    cluster_ids = {e.duplicate_cluster_id for e in result}
    assert len(cluster_ids) == 2


def test_same_event_similar_titles_but_independently_written_stay_separate():
    """제목에 같은 사건 키워드가 들어가도, 본문을 서로 다르게 독자 취재했으면 별도 근거로 남아야 한다."""
    body_a = (
        "○○동물원에서 늑대 한 마리가 우리를 탈출해 인근 야산으로 달아났다. 동물원 측은 마취총을 이용해 "
        "포획 작전을 벌였고, 사고 발생 4시간 만에 늑대를 무사히 붙잡았다고 밝혔다."
    )
    body_b = (
        "지역 주민들은 늑대가 탈출했다는 소식에 큰 불안감을 느꼈다고 전했다. 인근 학교는 등하교 시간을 조정했으며, "
        "경찰은 순찰을 강화했다고 밝혔다. 전문가들은 이번 사건을 계기로 사육 시설 안전 점검이 필요하다고 지적했다."
    )
    evidences = [
        _evidence(1, "https://a.com/news/1", "동물원 늑대 탈출...4시간만에 포획", body_a, "언론사A"),
        _evidence(2, "https://b.com/news/2", "늑대 탈출에 지역 주민 불안...안전 점검 목소리", body_b, "언론사B"),
    ]
    result = deduplicate(evidences)
    cluster_ids = {e.duplicate_cluster_id for e in result}
    assert len(cluster_ids) == 2


def test_normalize_url_strips_tracking_params():
    assert normalize_url("https://Example.com/path/?utm_source=fb&id=1") == "https://example.com/path?id=1"
