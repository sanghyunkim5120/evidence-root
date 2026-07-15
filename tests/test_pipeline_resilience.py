from evidence_root.schemas import Claim
from evidence_root.services.evidence_search import collect_raw_results
from evidence_root.providers.base import RawSearchResult


class WorkingProvider:
    provider_name = "working"

    def is_configured(self):
        return True

    def search(self, query, display=10):
        return [RawSearchResult(url=f"https://ok.com/{query}", title="정상 결과", snippet="s", search_provider="working")]


class FailingProvider:
    provider_name = "failing"

    def is_configured(self):
        return True

    def search(self, query, display=10):
        raise RuntimeError("provider down")


class UnconfiguredProvider:
    provider_name = "unconfigured"

    def is_configured(self):
        return False

    def search(self, query, display=10):
        raise AssertionError("설정되지 않은 provider는 호출되면 안 된다")


def test_one_provider_failure_does_not_block_others():
    claim = Claim(claim_id="C1", claim_text="테스트 주장", claim_type="event", checkability="checkable", keywords=["테스트"])
    process_log = {}
    result = collect_raw_results(
        claim, ["테스트"], [WorkingProvider(), FailingProvider(), UnconfiguredProvider()], 10, 40, process_log
    )
    assert len(result) == 1
    assert result[0].search_provider == "working"
