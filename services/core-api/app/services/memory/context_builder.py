import json
import os
from typing import Any

from app.models.context import BlockSource, Context, ContextBlock, FragmentRef
from app.models.session import SessionDocument, TurnDraft
from app.models.turn import Fragment, Turn
from app.prompts.conversation import (
    escape_markup,
    render_user_message,
    scaffolding_tokens,
)
from app.services.memory.memory import EpisodicLog, KeyedMemory
from app.utils.openai_utils import MAX_EMBEDDING_INPUT_BYTES, get_embedding
from app.utils.token_utils import count_tokens

MIN_CONTEXT_BUDGET = int(os.getenv("MIN_CONTEXT_BUDGET", "200"))
DEFAULT_CONTEXT_BUDGET = int(os.getenv("DEFAULT_CONTEXT_BUDGET", "2000"))
RECALL_MIN_BUDGET = int(os.getenv("RECALL_MIN_BUDGET", "200"))
RECALL_K = int(os.getenv("RECALL_K", "5"))

# Section headers and role prefixes instead of XML tags: measured on o200k_base,
# tags cost 9 tokens per turn against 4, which is 7.5% of a 2000-token budget on
# a 30-turn conversation. "User:" costs the same as "U:", so it stays readable.
FACTS_HEADER = "## hechos\n"
SUMMARY_HEADER = "## resumen\n"
RECALL_HEADER = "## recordado\n"
WORKING_HEADER = "## en curso\n"

# Blocks are spent by priority and read in a different order: working memory sits
# next to the question because it is the immediate context, and recall comes
# before it so the model reads it as background rather than as what just happened.
RENDER_ORDER: tuple[str, ...] = ("facts", "summary", "recall", "working")


def build_recall_query(prev: TurnDraft | None, message: str) -> str:
    """Build the text to embed for recall.

    The previous turn goes in front of the message because pronouns and ellipsis
    are the common case, not the rare one: "¿y eso?" embedded on its own is
    noise. The prefix is truncated to fit the embedding limit; the message never
    is, because the message is the query.
    """
    if prev is None:
        return message

    room = MAX_EMBEDDING_INPUT_BYTES - len(message.encode("utf-8")) - 1
    if room <= 0:
        return message

    prefix = f"{prev.user_text} {prev.assistant_text}"
    encoded = prefix.encode("utf-8")
    if len(encoded) > room:
        prefix = encoded[:room].decode("utf-8", errors="ignore")
    if not prefix:
        return message
    return f"{prefix}\n{message}"


def render_turn(turn: TurnDraft | Turn) -> str:
    return (
        f"User: {escape_markup(turn.user_text)}\n"
        f"Assistant: {escape_markup(turn.assistant_text)}\n"
    )


def render_fragment(fragment: Fragment) -> str:
    """Render one fragment with its date visible.

    Without the date the model cannot tell a fact extracted months ago from a
    turn that contradicts it last week.
    """
    turns = "".join(render_turn(turn) for turn in fragment.turns)
    return f"[{fragment.ts:%Y-%m-%d}]\n{turns}"


def _headed_block(
    source: BlockSource, header: str, body: str, left: int
) -> ContextBlock | None:
    content = f"{header}{escape_markup(body)}\n"
    tokens = count_tokens(content)
    if tokens > left:
        return None
    return ContextBlock(source=source, tokens=tokens, content=content)


def _working_block(session: SessionDocument, left: int) -> ContextBlock | None:
    room = left - count_tokens(WORKING_HEADER)
    if room <= 0:
        return None

    rendered: list[str] = []
    for turn in reversed(session.turns):
        piece = render_turn(turn)
        cost = count_tokens(piece)
        if cost > room:
            # Recency is an order: skipping a turn would break the continuity
            # that makes working memory worth reading. Stop instead.
            break
        rendered.insert(0, piece)
        room -= cost

    if not rendered:
        return None
    content = WORKING_HEADER + "".join(rendered)
    return ContextBlock(source="working", tokens=count_tokens(content), content=content)


def _recall_block(fragments: list[Fragment], left: int) -> ContextBlock | None:
    room = left - count_tokens(RECALL_HEADER)
    if room <= 0:
        return None

    admitted: list[tuple[Fragment, str]] = []
    for fragment in fragments:
        piece = render_fragment(fragment)
        cost = count_tokens(piece)
        if cost > room:
            # Unlike working memory, relevance is not an order to preserve: a
            # later fragment may be smaller and still fit.
            continue
        admitted.append((fragment, piece))
        room -= cost

    if not admitted:
        return None

    # similar() returns by relevance, which decides what gets in; the prompt
    # reads chronologically, which is how contradictions resolve.
    admitted.sort(key=lambda item: (item[0].ts, item[0].session_id))
    content = RECALL_HEADER + "".join(piece for _, piece in admitted)
    return ContextBlock(
        source="recall",
        tokens=count_tokens(content),
        content=content,
        fragments=[
            FragmentRef(
                session_id=fragment.session_id,
                ts=fragment.ts,
                similarity=fragment.similarity,
                seqs=[turn.seq for turn in fragment.turns],
            )
            for fragment, _ in admitted
        ],
    )


async def assemble(
    session_id: str,
    session: SessionDocument,
    q: str,
    budget: int,
    fact_memory: KeyedMemory[Any],
    summary_memory: KeyedMemory[Any],
    episodic_memory: EpisodicLog,
) -> Context:
    """Fit the best context available into `budget` tokens.

    Spent by priority — facts, summary, working, recall — and never truncated
    mid-block: a block goes in whole or stays out. A halved summary is worse
    than no summary, and a halved fragment stops being readable, which was the
    reason to keep fragments whole in the first place.
    """
    subject_id = session.subject_id
    blocks: dict[str, ContextBlock] = {}
    left = budget

    facts = await fact_memory.retrieve_from_memory(subject_id)
    if facts:
        # Facts are a dict in production; the layer is typed Any, so a plain
        # string goes through untouched instead of being quoted by json.
        body = (
            facts if isinstance(facts, str) else json.dumps(facts, ensure_ascii=False)
        )
        block = _headed_block("facts", FACTS_HEADER, body, left)
        if block is not None:
            blocks["facts"] = block
            left -= block.tokens

    summary = await summary_memory.retrieve_from_memory(subject_id)
    if summary:
        block = _headed_block("summary", SUMMARY_HEADER, str(summary), left)
        if block is not None:
            blocks["summary"] = block
            left -= block.tokens

    working = _working_block(session, left)
    if working is not None:
        blocks["working"] = working
        left -= working.tokens

    if left > RECALL_MIN_BUDGET and await episodic_memory.has_turns(
        subject_id, exclude_session=session_id
    ):
        last_turn = session.turns[-1] if session.turns else None
        vector = await get_embedding(build_recall_query(last_turn, q))
        fragments = await episodic_memory.similar(
            subject_id, vector, RECALL_K, session_id
        )
        recall = _recall_block(fragments, left)
        if recall is not None:
            blocks["recall"] = recall
            left -= recall.tokens

    ordered = [blocks[source] for source in RENDER_ORDER if source in blocks]
    return Context(
        budget=budget,
        used=budget - left,
        system_tokens=scaffolding_tokens(),
        message_tokens=count_tokens(render_user_message(q)),
        blocks=ordered,
    )
