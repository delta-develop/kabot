import pytest
from typesafe_sdk import TypeSafeError


@pytest.fixture(autouse=True)
def no_real_typesafe_call(mocker):
    """No test reaches api.typesafe.ai.

    The re-ranker sits in the recall path, so every context test would call the
    real service the moment a developer has TYPESAFE_API_KEY exported. Failing
    the client puts the whole suite on the documented fallback — cosine order —
    which is also what the assertions written before the re-ranker expect.
    A test that wants the re-rank patches this target again with its own client.
    """
    mocker.patch(
        "app.services.memory.reranker.get_typesafe_client",
        side_effect=TypeSafeError("no TypeSafe client in tests"),
    )
