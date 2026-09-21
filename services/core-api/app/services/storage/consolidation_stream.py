import os

from app.services.storage.connections import get_redis_client

# Why a Redis Stream and not a plain list: a stream gives offsets, consumer
# groups, replay, and XACK per message. A list gives none of that, so a worker
# that dies mid-consolidation loses the item.
#
# Why not Kafka: Kafka earns its operational cost with a *second* consumer —
# when analytics and audit read the same event at their own pace and need
# independent offsets. Until then it is one log replacing another log, and the
# mental model here is already the right one, so the migration is a swap of
# transport rather than a redesign.
STREAM = "consolidation"
GROUP = "consolidators"
FAILED_STREAM = "consolidation:failed"

CLAIM_IDLE_MS = int(os.getenv("CONSOLIDATION_CLAIM_IDLE_SECONDS", "300")) * 1000

Message = tuple[str, dict[str, str], int]


async def enqueue(session_id: str) -> str:
    """Queues a session for consolidation.

    Args:
        session_id (str): The session to consolidate.

    Returns:
        str: The stream message identifier.
    """
    redis = await get_redis_client()
    return await redis.xadd(STREAM, {"session_id": session_id})


async def ensure_group() -> None:
    """Creates the consumer group, and the stream with it, if absent."""
    redis = await get_redis_client()
    try:
        await redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except Exception as error:
        if "BUSYGROUP" not in str(error):
            raise


async def read_new(consumer: str, count: int, block_ms: int) -> list[Message]:
    """Reads messages never delivered to this group.

    Args:
        consumer (str): This worker's consumer name.
        count (int): How many messages to take at most.
        block_ms (int): How long to wait when the stream is empty.

    Returns:
        list[Message]: Each message with a delivery count of one.
    """
    redis = await get_redis_client()
    response = await redis.xreadgroup(
        GROUP, consumer, {STREAM: ">"}, count=count, block=block_ms
    )
    if not response:
        return []
    return [(message_id, fields, 1) for message_id, fields in response[0][1]]


async def claim_stale(consumer: str, count: int) -> list[Message]:
    """Takes over messages another consumer left pending.

    The delivery count comes from the stream and not from this process, since
    the worker that failed the previous attempt may no longer exist.

    Args:
        consumer (str): This worker's consumer name.
        count (int): How many messages to take at most.

    Returns:
        list[Message]: Each message with the times it has been delivered.
    """
    redis = await get_redis_client()
    response = await redis.xautoclaim(
        STREAM, GROUP, consumer, min_idle_time=CLAIM_IDLE_MS, count=count
    )
    messages = response[1]
    if not messages:
        return []
    pending = await redis.xpending_range(
        STREAM, GROUP, min="-", max="+", count=count, consumername=consumer
    )
    delivered = {entry["message_id"]: entry["times_delivered"] for entry in pending}
    return [
        (message_id, fields, delivered.get(message_id, 1))
        for message_id, fields in messages
    ]


async def ack(message_id: str) -> None:
    """Marks a message as fully processed.

    Args:
        message_id (str): The message to acknowledge.
    """
    redis = await get_redis_client()
    await redis.xack(STREAM, GROUP, message_id)


async def dead_letter(fields: dict[str, str], error: str) -> str:
    """Moves an exhausted message to the failed stream.

    Args:
        fields (dict[str, str]): The original message payload.
        error (str): The last failure, kept so the message is diagnosable.

    Returns:
        str: The failed-stream message identifier.
    """
    redis = await get_redis_client()
    return await redis.xadd(FAILED_STREAM, {**fields, "error": error})
