import pytest

from market_research.models import Brief, Competitor, Critique
from market_research.search import SearchResult


class FakeSearch:
    name = "Fake search"

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results or []
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.queries.append(query)
        return self.results[:max_results]


@pytest.fixture
def search_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Report A", url="https://a.example", content="Foodmandu leads in Nepal."
        ),
        SearchResult(
            title="Report B", url="https://b.example", content="Pathao Food grows in Nepal."
        ),
    ]


@pytest.fixture
def good_brief() -> Brief:
    return Brief(
        summary="Two platforms lead food delivery in Nepal [F1, F2].",
        competitors=[
            Competitor(name="Foodmandu", note="Leader", finding_ids=["F1"]),
            Competitor(name="Pathao Food", note="Challenger", finding_ids=["F2"]),
        ],
        observations=["Foodmandu leads the market [F1]", "Pathao Food is growing [F2]"],
        missing_information=["Market size"],
    )


@pytest.fixture
def bad_brief() -> Brief:
    return Brief(summary="Big market.", observations=["Revenue is huge [F9]"])


APPROVE = Critique(approved=True)
REJECT = Critique(approved=False, issues=["Too vague"], revision_request="Be specific")
