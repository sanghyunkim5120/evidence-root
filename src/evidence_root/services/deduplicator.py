"""중복/재인용 자료를 근거 계통(cluster)으로 묶는다 (스펙 15장)."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from ..schemas import Evidence

_TRACKING_PARAMS_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "cid")


def normalize_url(url: str) -> str:
    if not url:
        return url
    parts = urlsplit(url)
    query_pairs = [
        kv for kv in parts.query.split("&") if kv and not kv.split("=")[0].lower().startswith(_TRACKING_PARAMS_PREFIXES)
    ]
    path = re.sub(r"/$", "", parts.path)
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, "&".join(query_pairs), ""))


def _title_key(title: str) -> str:
    return re.sub(r"\s+", "", (title or "").lower())


def _body_hash(text: str) -> str:
    normalized = re.sub(r"\s+", "", (text or "")[:2000].lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def deduplicate(evidences: list[Evidence], fuzzy_threshold: int = 88) -> list[Evidence]:
    """canonical URL/제목/본문 해시 1차 병합 후, 남은 것들을 n-gram 유사도로 군집화한다."""
    if not evidences:
        return evidences

    for e in evidences:
        e.canonical_url = normalize_url(e.canonical_url or e.url)

    groups: dict[str, list[Evidence]] = {}
    order: list[str] = []
    for e in evidences:
        key = e.canonical_url or _body_hash(e.body_text or e.snippet)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e)

    representatives = [group[0] for group in (groups[k] for k in order)]

    if len(representatives) > 1:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            texts = [
                (r.title + " " + (r.body_text or r.snippet))[:3000] for r in representatives
            ]
            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=5000)
            matrix = vectorizer.fit_transform(texts)
            sim_matrix = cosine_similarity(matrix)
        except Exception:
            sim_matrix = None

        from rapidfuzz import fuzz

        cluster_id_of: dict[int, int] = {}
        next_cluster = 0
        for i in range(len(representatives)):
            if i in cluster_id_of:
                continue
            cluster_id_of[i] = next_cluster
            for j in range(i + 1, len(representatives)):
                if j in cluster_id_of:
                    continue
                tfidf_sim = sim_matrix[i][j] if sim_matrix is not None else 0.0
                title_sim = fuzz.ratio(_title_key(representatives[i].title), _title_key(representatives[j].title))
                # 제목만 비슷한 건 같은 사건을 서로 다른 언론사가 독립 취재한 경우에도 흔히 발생하므로
                # (예: "OO동물원 늑대 탈출" 류 제목은 어느 언론사든 비슷하게 붙는다) 제목 유사도만으로는
                # 재인용으로 판단하지 않는다. 본문이 사실상 동일할 때만("[속보]" 같은 제목 장식은 무시하고)
                # 재인용으로 묶고, 본문이 어느 정도 겹치면서 제목까지 매우 비슷할 때만 보조적으로 묶는다.
                is_same_body = tfidf_sim >= 0.85
                is_paraphrased_reprint = tfidf_sim >= 0.5 and title_sim >= 90
                if is_same_body or is_paraphrased_reprint:
                    cluster_id_of[j] = next_cluster
            next_cluster += 1
    else:
        cluster_id_of = {0: 0} if representatives else {}

    for group_key, cluster_idx in zip(order, range(len(representatives))):
        actual_cluster = cluster_id_of.get(cluster_idx, cluster_idx)
        cluster_label = f"cluster-{actual_cluster}"
        for e in groups[group_key]:
            e.duplicate_cluster_id = cluster_label

    return evidences
