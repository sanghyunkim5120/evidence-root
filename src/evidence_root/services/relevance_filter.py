"""관련성 필터링: 1차 TF-IDF/RapidFuzz/키워드 일치, 2차 Gemini 평가 (스펙 14장)."""
from __future__ import annotations

import logging

from ..providers.gemini_provider import GeminiProvider
from ..schemas import Claim, Evidence

logger = logging.getLogger("evidence_root.services.relevance_filter")


def _text_of(evidence: Evidence) -> str:
    return " ".join(filter(None, [evidence.title, evidence.snippet, evidence.body_text[:1000]]))


def prefilter_relevance(claim: Claim, evidences: list[Evidence], threshold: float) -> list[Evidence]:
    """TF-IDF 코사인 유사도 + 키워드/날짜 일치로 1차 필터링."""
    if not evidences:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        claim_text = claim.claim_text + " " + " ".join(claim.keywords)
        corpus = [claim_text] + [_text_of(e) for e in evidences]
        vectorizer = TfidfVectorizer(max_features=4000)
        matrix = vectorizer.fit_transform(corpus)
        sims = cosine_similarity(matrix[0:1], matrix[1:])[0]
    except Exception as exc:
        logger.warning("TF-IDF 계산 실패, RapidFuzz만 사용: %s", exc)
        sims = [0.0] * len(evidences)

    from rapidfuzz import fuzz

    kept: list[Evidence] = []
    for evidence, sim in zip(evidences, sims):
        fuzzy = fuzz.token_set_ratio(claim.claim_text, _text_of(evidence)) / 100.0
        keyword_hit = any(kw and kw in _text_of(evidence) for kw in claim.keywords)
        score = max(sim, fuzzy * 0.8) + (0.1 if keyword_hit else 0.0)
        evidence.relevance_score = round(float(score), 4)
        if score >= threshold:
            kept.append(evidence)
    return kept


BATCH_PROMPT_TEMPLATE = """다음 주장과 자료 목록을 보고 각 자료가 실제로 관련있는지 평가하라. 동명이인, 다른 사건,
다른 지역/기간의 통계는 관련 없음으로 판단하라.

주장: {claim_text}

자료 목록:
{items}

각 자료의 id에 대해 JSON 배열로만 응답하라:
[{{"id": "E1", "relevant": true/false}}, ...]
"""


def gemini_relevance_check(claim: Claim, evidences: list[Evidence], gemini: GeminiProvider) -> list[Evidence]:
    """2차 Gemini 평가. 미설정 시 1차 필터 결과를 그대로 통과시킨다.

    분당 토큰 한도(TPM)를 넘기지 않도록 작은 묶음으로 나눠 보낸다.
    """
    if not gemini.is_configured() or not evidences:
        return evidences

    relevant_map: dict[str, bool] = {}
    chunk_size = 4
    for i in range(0, len(evidences), chunk_size):
        chunk = evidences[i : i + chunk_size]
        items = "\n\n".join(
            f"id: {e.evidence_id}\n제목: {e.title}\n내용: {(e.body_text or e.snippet)[:400]}" for e in chunk
        )
        raw = gemini.generate_json(BATCH_PROMPT_TEMPLATE.format(claim_text=claim.claim_text, items=items))
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("id"):
                    relevant_map[item["id"]] = item.get("relevant", True)

    return [e for e in evidences if relevant_map.get(e.evidence_id, True) is not False]
