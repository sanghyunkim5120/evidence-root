"""Pydantic 데이터 모델. 스펙 9/13/16장 구조를 그대로 반영한다."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    event = "event"
    numerical = "numerical"
    comparison = "comparison"
    causal = "causal"
    intent = "intent"
    quote = "quote"
    image_context = "image_context"
    generalization = "generalization"
    other = "other"


class Checkability(str, Enum):
    checkable = "checkable"
    partially_checkable = "partially_checkable"
    opinion = "opinion"
    unverifiable = "unverifiable"


class SourceType(str, Enum):
    official_statement = "official_statement"
    official_statistics = "official_statistics"
    legal_document = "legal_document"
    corporate_disclosure = "corporate_disclosure"
    academic_or_research = "academic_or_research"
    original_reporting = "original_reporting"
    news_report = "news_report"
    news_republication = "news_republication"
    fact_check = "fact_check"
    social_post = "social_post"
    blog = "blog"
    community = "community"
    image_match = "image_match"
    unknown = "unknown"


class Stance(str, Enum):
    support = "support"
    refute = "refute"
    mixed = "mixed"
    insufficient = "insufficient"
    unrelated = "unrelated"


class RelationType(str, Enum):
    cites = "cites"
    republishes = "republishes"
    summarizes = "summarizes"
    derived_from = "derived_from"
    independently_reports = "independently_reports"
    unknown = "unknown"


class VerdictStatus(str, Enum):
    confirmed = "confirmed"
    likely_true = "likely_true"
    partially_supported = "partially_supported"
    mixed = "mixed"
    insufficient_evidence = "insufficient_evidence"
    likely_false = "likely_false"
    false = "false"
    unverifiable = "unverifiable"


class Claim(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    checkability: Checkability
    entities: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    quantities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    evidence_id: str
    claim_id: str
    url: str = ""
    canonical_url: str = ""
    title: str = ""
    publisher: str = ""
    author: str = ""
    published_at: Optional[str] = None
    source_type: SourceType = SourceType.unknown
    search_provider: str = ""
    snippet: str = ""
    body_text: str = ""
    full_text_available: bool = False
    outbound_links: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    duplicate_cluster_id: Optional[str] = None


class ProvenanceEdge(BaseModel):
    source_evidence_id: str
    target_evidence_id: str
    relation: RelationType
    is_estimated: bool = True
    reason: str = ""


class StanceResult(BaseModel):
    claim_id: str
    evidence_id: str
    stance: Stance
    confidence: float = 0.0
    relevant_quote: str = ""
    reason: str = ""
    limitations: list[str] = Field(default_factory=list)
    quote_verified: bool = False


class ClaimScore(BaseModel):
    claim_id: str
    support_strength: float = 0.0
    refute_strength: float = 0.0
    evidence_coverage: float = 0.0
    independent_support_count: int = 0
    independent_refute_count: int = 0
    source_conflict: float = 0.0
    uncertainty: float = 1.0
    duplicate_ratio: float = 0.0


class ClaimVerdict(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    status: VerdictStatus
    confidence_label: str
    verification_scope: str
    confirmed_points: list[str] = Field(default_factory=list)
    insufficient_points: list[str] = Field(default_factory=list)
    reasoning: str = ""
    limitations: list[str] = Field(default_factory=list)
    score: ClaimScore


class AnalysisResult(BaseModel):
    input_summary: str
    claims: list[Claim]
    evidences: list[Evidence]
    stances: list[StanceResult]
    provenance_edges: list[ProvenanceEdge]
    verdicts: list[ClaimVerdict]
    overall_summary: str
    followup_questions: list[str]
    process_log: dict = Field(default_factory=dict)
