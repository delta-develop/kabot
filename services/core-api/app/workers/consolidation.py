"""The sleep phase: a worker that drains the consolidation stream.

Closing a session queues it; this process turns the queued session into
long-term memory. It runs apart from the API so that restarting one never
interrupts the other.
"""

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime, timedelta

import dotenv
import logfire

from app.services.memory.cognitive_orchestrator import CognitiveOrchestrator
from app.services.memory.working_memory import SESSION_TTL_SECONDS, WorkingMemory
from app.services.storage.consolidation_stream import (
    Message,
    ack,
    claim_stale,
    dead_letter,
    enqueue,
    ensure_group,
    read_new,
)
from app.services.storage.relational_storage import RelationalStorage

MAX_RETRIES = int(os.getenv("CONSOLIDATION_MAX_RETRIES", "3"))
SWEEP_INTERVAL = int(os.getenv("CONSOLIDATION_SWEEP_INTERVAL", "60"))
SWEEP_MARGIN_SECONDS = int(os.getenv("CONSOLIDATION_SWEEP_MARGIN_SECONDS", "300"))
BATCH = 10
BLOCK_MS = 5000

logger = logging.getLogger(__name__)


async def consolidate_session(
    orchestrator: CognitiveOrchestrator, working_memory: WorkingMemory, session_id: str
) -> None:
    """Turns one session's working memory into long-term memory.

    Args:
        orchestrator (CognitiveOrchestrator): The memory layers to write through.
        working_memory (WorkingMemory): The session store and its open index.
        session_id (str): The session to consolidate.
    """
    session = await working_memory.retrieve_from_memory(session_id)
    if session is None:
        # The key expired or the subject was erased: there is nothing left to
        # consolidate, only an index entry pointing at it.
        await working_memory.drop_from_open(session_id)
        return
    if session.status in ("consolidated", "failed"):
        return
    if session.status != "consolidating":
        session.status = "consolidating"
        await working_memory.store_in_memory(session_id, session)
    await orchestrator.persist_conversation_closure(session.subject_id, session_id)


async def mark_failed(working_memory: WorkingMemory, session_id: str) -> None:
    """Leaves an exhausted session diagnosable instead of stuck.

    Args:
        working_memory (WorkingMemory): The session store and its open index.
        session_id (str): The session that ran out of attempts.
    """
    session = await working_memory.retrieve_from_memory(session_id)
    if session is None:
        await working_memory.drop_from_open(session_id)
        return
    session.status = "failed"
    await working_memory.store_in_memory(session_id, session)


async def handle_message(
    orchestrator: CognitiveOrchestrator,
    working_memory: WorkingMemory,
    message: Message,
) -> None:
    """Consolidates one queued session and acknowledges it only once done.

    A failure with attempts left returns without acknowledging, so the message
    stays pending and the next XAUTOCLAIM picks it up.

    Args:
        orchestrator (CognitiveOrchestrator): The memory layers to write through.
        working_memory (WorkingMemory): The session store and its open index.
        message (Message): The stream message with its delivery count.
    """
    message_id, fields, delivery_count = message
    session_id = fields["session_id"]
    try:
        await consolidate_session(orchestrator, working_memory, session_id)
    except Exception as error:
        logger.exception(
            "Consolidation attempt %s/%s failed for session %s",
            delivery_count,
            MAX_RETRIES,
            session_id,
        )
        if delivery_count < MAX_RETRIES:
            return
        await dead_letter(fields, repr(error))
        await mark_failed(working_memory, session_id)
        await ack(message_id)
        return
    await ack(message_id)


async def consume_once(
    orchestrator: CognitiveOrchestrator, working_memory: WorkingMemory, consumer: str
) -> int:
    """Handles one batch, preferring messages a dead worker left behind.

    Args:
        orchestrator (CognitiveOrchestrator): The memory layers to write through.
        working_memory (WorkingMemory): The session store and its open index.
        consumer (str): This worker's consumer name.

    Returns:
        int: How many messages were handled.
    """
    messages = await claim_stale(consumer, BATCH)
    if not messages:
        messages = await read_new(consumer, BATCH, BLOCK_MS)
    for message in messages:
        await handle_message(orchestrator, working_memory, message)
    return len(messages)


async def sweep_once(working_memory: WorkingMemory) -> list[str]:
    """Queues the sessions that went quiet and will never be closed.

    The cutoff sits one margin before the Redis TTL erases the key: sweeping
    late means the SessionDocument is already gone and the conversation with it.

    Args:
        working_memory (WorkingMemory): The session store and its open index.

    Returns:
        list[str]: The sessions queued by this pass.
    """
    cutoff = datetime.now(UTC) - timedelta(
        seconds=SESSION_TTL_SECONDS - SWEEP_MARGIN_SECONDS
    )
    abandoned = await working_memory.open_sessions_before(cutoff)
    for session_id in abandoned:
        # The sweep enqueues and never consolidates: one path, two triggers.
        await enqueue(session_id)
    return abandoned


async def consume_loop(
    orchestrator: CognitiveOrchestrator, working_memory: WorkingMemory, consumer: str
) -> None:
    while True:
        await consume_once(orchestrator, working_memory, consumer)


async def sweep_loop(working_memory: WorkingMemory) -> None:
    while True:
        await sweep_once(working_memory)
        await asyncio.sleep(SWEEP_INTERVAL)


async def main() -> None:
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO)
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_httpx()
    logfire.instrument_asyncpg()
    logfire.instrument_redis()
    logfire.instrument_pymongo()

    # The API populates the engine globals in its lifespan; this process has no
    # lifespan and has to do it itself.
    await RelationalStorage().setup()
    await ensure_group()

    orchestrator = await CognitiveOrchestrator.from_defaults()
    working_memory = WorkingMemory()
    consumer = socket.gethostname()
    logger.info("Consolidation worker %s draining %s", consumer, "consolidation")
    await asyncio.gather(
        consume_loop(orchestrator, working_memory, consumer),
        sweep_loop(working_memory),
    )


if __name__ == "__main__":
    asyncio.run(main())
