from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from typesafe_sdk import NoulAnswer, SystemOneResponse, TypeSafeError, Usage

from app.models.turn import Fragment, Turn
from app.services.memory.reranker import rerank

VECTOR = [0.123456789] * 1536
TS = datetime(2026, 1, 1, tzinfo=UTC)


def fragment(text: str, similarity: float) -> Fragment:
    turn = Turn(
        subject_id="u1",
        session_id="s1",
        seq=0,
        ts=TS,
        user_text=text,
        assistant_text="respuesta archivada",
        embedding=VECTOR,
    )
    return Fragment(turns=[turn], session_id="s1", ts=TS, similarity=similarity)


def answered(*nouls: float) -> SystemOneResponse:
    return SystemOneResponse(
        model="jev-latest",
        usage=Usage(input_tokens=1, output_tokens=1),
        answers={str(index): NoulAnswer(noul=noul) for index, noul in enumerate(nouls)},
    )


def patch_client(mocker, **kwargs) -> AsyncMock:
    client = AsyncMock()
    client.system_one = AsyncMock(**kwargs)
    mocker.patch(
        "app.services.memory.reranker.get_typesafe_client",
        AsyncMock(return_value=client),
    )
    return client


@pytest.mark.asyncio
async def test_fragments_come_back_in_noul_order_with_usefulness_set(mocker):
    patch_client(mocker, return_value=answered(0.03, 0.80))
    fragments = [fragment("pasaporte", 0.3282), fragment("vegetariano", 0.1455)]

    ranked = await rerank("¿dónde los llevo a cenar?", fragments)

    assert [turn.user_text for f in ranked for turn in f.turns] == [
        "vegetariano",
        "pasaporte",
    ]
    assert [f.usefulness for f in ranked] == [0.80, 0.03]
    assert [f.similarity for f in ranked] == [0.1455, 0.3282]


@pytest.mark.asyncio
async def test_a_typesafe_failure_leaves_the_cosine_order_untouched(mocker):
    patch_client(mocker, side_effect=TypeSafeError("service is down"))
    fragments = [fragment("pasaporte", 0.3282), fragment("vegetariano", 0.1455)]

    ranked = await rerank("¿dónde los llevo a cenar?", fragments)

    assert ranked == fragments
    assert [f.usefulness for f in ranked] == [None, None]


@pytest.mark.asyncio
async def test_a_missing_answer_leaves_the_cosine_order_untouched(mocker):
    patch_client(mocker, return_value=answered(0.03))
    fragments = [fragment("pasaporte", 0.3282), fragment("vegetariano", 0.1455)]

    ranked = await rerank("¿dónde los llevo a cenar?", fragments)

    assert ranked == fragments
    assert [f.usefulness for f in ranked] == [None, None]


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [0, 1])
async def test_nothing_to_reorder_never_reaches_the_service(size, mocker):
    client = patch_client(mocker, return_value=answered(0.80))
    fragments = [fragment("vegetariano", 0.1455) for _ in range(size)]

    ranked = await rerank("¿dónde los llevo a cenar?", fragments)

    assert ranked == fragments
    client.system_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_message_and_every_candidate_reach_the_same_state(mocker):
    client = patch_client(mocker, return_value=answered(0.03, 0.80))
    fragments = [fragment("pasaporte", 0.3282), fragment("vegetariano", 0.1455)]

    await rerank("¿dónde los llevo a cenar?", fragments)

    state = client.system_one.await_args.kwargs["state"]
    questions = client.system_one.await_args.kwargs["questions"]
    assert state["message"] == "¿dónde los llevo a cenar?"
    assert [candidate["id"] for candidate in state["candidates"]] == [0, 1]
    assert state["candidates"][0]["text"] == (
        "User: pasaporte\nAssistant: respuesta archivada\n"
    )
    assert set(questions) == {"0", "1"}
    assert questions["1"].instructions.endswith(
        "The candidate is `candidates[1].text`."
    )
