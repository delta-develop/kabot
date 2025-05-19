import asyncio

from app.services.storage.relational_storage import RelationalStorage
from app.services.storage.search_engine_storage import SearchEngineStorage


async def setup_all() -> None:
    """Initialize all storage backends asynchronously.

    This function initializes the relational and search engine storage
    components concurrently using asyncio.
    """
    print("Initializing PostgreSQL...")
    relational_storage = RelationalStorage()
    print("Initializing OpenSearch...")
    search_engine_storage = SearchEngineStorage()
    await asyncio.gather(relational_storage.setup(), search_engine_storage.setup())


if __name__ == "__main__":
    """Run the setup process when the script is executed directly."""
    asyncio.run(setup_all())
