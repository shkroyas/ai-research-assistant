from market_research.search import SampleDataSearch, TavilySearch, build_search


class FakeTavilyClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def search(self, query: str, max_results: int) -> dict:
        self.calls.append({"query": query, "max_results": max_results})
        return {
            "results": [
                {"title": "Report", "url": "https://example.com/r", "content": "Market grew."},
                {"title": "Empty", "url": "https://example.com/e", "content": ""},
            ]
        }


def test_tavily_search_maps_results_and_skips_empty_content() -> None:
    client = FakeTavilyClient()
    results = TavilySearch(api_key="unused", client=client).search("food delivery", max_results=3)
    assert client.calls == [{"query": "food delivery", "max_results": 3}]
    assert len(results) == 1
    assert results[0].url == "https://example.com/r"
    assert results[0].is_sample_data is False


def test_sample_search_labels_every_result() -> None:
    results = SampleDataSearch().search("Analyze the food delivery market in Nepal")
    assert results
    assert all(r.is_sample_data for r in results)
    assert all(r.title.startswith("Sample:") for r in results)


def test_sample_search_returns_nothing_for_unknown_topic() -> None:
    assert SampleDataSearch().search("quantum computing in Iceland") == []


def test_build_search_falls_back_to_sample_data_without_key() -> None:
    assert isinstance(build_search(None), SampleDataSearch)
