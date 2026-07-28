import time

import httpx

from dialogue_os.hermes.model_router import FeatherlessModelRouter


async def test_catalog_filters_short_context_and_completion(monkeypatch):
    async def fake_get(self, url, *, params):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "data": [
                    {
                        "id": "good/model",
                        "context_length": 131072,
                        "max_completion_tokens": 8192,
                    },
                    {
                        "id": "short/context",
                        "context_length": 32768,
                        "max_completion_tokens": 8192,
                    },
                    {
                        "id": "short/output",
                        "context_length": 131072,
                        "max_completion_tokens": 2048,
                    },
                ]
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    router = FeatherlessModelRouter()

    assert await router.candidates("research-lead") == ["good/model"]


def test_failure_quarantines_and_success_sticks():
    router = FeatherlessModelRouter()
    router._models = ["one", "two"]
    router._last_refresh = time.time()

    router.failure("one", "HTTP 500")
    router.success("builder-lead", "two")

    snapshot = router.snapshot()
    assert "one" in snapshot["quarantined"]
    assert snapshot["profile_models"]["builder-lead"] == "two"


def test_only_provider_and_model_errors_rotate():
    assert FeatherlessModelRouter.should_rotate(status=500)
    assert FeatherlessModelRouter.should_rotate(text="context too large")
    assert not FeatherlessModelRouter.should_rotate(
        status=400, text="tool argument validation failed"
    )
