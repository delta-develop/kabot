from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.services.storage import relational_storage
from app.services.storage.relational_storage import RelationalStorage


def engine_raising(error: Exception | None) -> MagicMock:
    """An engine whose `begin()` context raises once, then behaves."""
    connection = AsyncMock()
    if error is not None:
        connection.execute.side_effect = error
        connection.run_sync.side_effect = error
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.begin.return_value = context
    engine.dispose = AsyncMock()
    return engine


@pytest.mark.parametrize(
    "error",
    [
        IntegrityError("CREATE EXTENSION", None, Exception("duplicate key")),
        ProgrammingError("CREATE EXTENSION", None, Exception("duplicate object")),
    ],
)
@pytest.mark.asyncio
async def test_setup_survives_losing_the_extension_race(mocker, error):
    """Two services booting against a fresh volume both create the extension.

    `IF NOT EXISTS` checks and creates in two steps, so the loser takes a
    duplicate error. Startup must not die on it — the extension is there.
    """
    bootstrap = engine_raising(error)
    working = engine_raising(None)
    mocker.patch.object(
        relational_storage,
        "create_async_engine",
        side_effect=[bootstrap, working],
    )
    mocker.patch.object(relational_storage, "async_sessionmaker")

    await RelationalStorage().setup()

    bootstrap.dispose.assert_awaited_once()
    working.begin.assert_called_once()


@pytest.mark.asyncio
async def test_setup_retries_create_all_once_and_reraises_a_real_failure(mocker):
    """A lost race resolves on the retry; a genuine schema error still raises."""
    bootstrap = engine_raising(None)
    working = engine_raising(ProgrammingError("CREATE TABLE", None, Exception("boom")))
    mocker.patch.object(
        relational_storage,
        "create_async_engine",
        side_effect=[bootstrap, working],
    )
    mocker.patch.object(relational_storage, "async_sessionmaker")

    with pytest.raises(ProgrammingError):
        await RelationalStorage().setup()

    assert working.begin.call_count == 2
