import logfire
from typesafe_sdk import Noul, NoulCriteria, TypeSafeError

from app.models.turn import Fragment
from app.prompts.conversation import render_turn
from app.services.storage.connections import get_typesafe_client

# Measured against api.typesafe.ai on the fragments the stack really retrieved:
# signal 0.80 against noise 0.03 and 0.07, where cosine put the signal last.
# Rewording it invalidates that measurement.
INSTRUCTIONS = (
    "The user just sent `message` in an ongoing conversation. The candidate is an "
    "excerpt of an earlier conversation with the same user, from a different session. "
    "Would putting this excerpt in front of the assistant change or improve its reply?"
)
CRITERIA = NoulCriteria(
    true=(
        "The excerpt carries a fact, preference, constraint or past experience that "
        "the assistant needs in order to answer this particular message well."
    ),
    false=(
        "The excerpt is merely another thing this user talked about. It does not "
        "bear on what this message is asking for."
    ),
)


def _candidate_text(fragment: Fragment) -> str:
    """Render a candidate exactly as the prompt would render it."""
    return "".join(render_turn(turn) for turn in fragment.turns)


def _by_cosine(fragments: list[Fragment], reason: str) -> list[Fragment]:
    logfire.warn(
        "recall re-rank skipped, keeping cosine order: {reason}", reason=reason
    )
    return fragments


async def rerank(message: str, fragments: list[Fragment]) -> list[Fragment]:
    """Reorder recalled fragments by how much they help answer `message`.

    Cosine similarity ranks a fragment by what it is about; a noul ranks it by
    whether it helps. Only the order changes — nothing is filtered, because a
    threshold needs a distribution of nouls that does not exist yet.

    All the candidates travel in one `state` and each one gets its own question,
    which costs one round trip on the hot path instead of k.
    """
    if len(fragments) <= 1:
        return fragments

    try:
        client = await get_typesafe_client()
        state = {
            "message": message,
            "candidates": [
                {"id": index, "text": _candidate_text(fragment)}
                for index, fragment in enumerate(fragments)
            ],
        }
        questions = {
            str(index): Noul(
                instructions=(
                    f"{INSTRUCTIONS} The candidate is `candidates[{index}].text`."
                ),
                criteria=CRITERIA,
            )
            for index in range(len(fragments))
        }
        # logfire.instrument_httpx() does not reach this call: the SDK is on httpx2.
        with logfire.span("rerank", candidates=len(fragments)):
            answer = await client.system_one(state=state, questions=questions)
    except TypeSafeError as error:
        # Missing key, timeout, bad response: every one of them is the boundary
        # failing, and recall already has an order that works without it.
        return _by_cosine(fragments, str(error))

    nouls = answer.nouls
    if nouls.keys() != questions.keys():
        # The SDK drops answers whose type it does not model and defaults the
        # answer set to empty, so a complete response is not a type guarantee.
        return _by_cosine(fragments, "the service answered only part of the state")

    ranked = sorted(
        (
            (nouls[name].noul, fragment)
            for name, fragment in zip(questions, fragments, strict=True)
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [
        fragment.model_copy(update={"usefulness": noul}) for noul, fragment in ranked
    ]
