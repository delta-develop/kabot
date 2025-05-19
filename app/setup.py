import asyncio
from app.services.storage.relational_storage import RelationalStorage
from app.services.storage.search_engine_storage import SearchEngineStorage


async def setup_all() -> None:
    """Asynchronously initialize all storage backends."""
    print("Initializing PostgreSQL...")
    relational_storage = RelationalStorage()
    print("Initializing OpenSearch...")
    search_engine_storage = SearchEngineStorage()
    # await both setups in parallel
    await asyncio.gather(
        relational_storage.setup(),
        search_engine_storage.setup()
    )


if __name__ == "__main__":
    """Entry point for setup script."""
    asyncio.run(setup_all())
