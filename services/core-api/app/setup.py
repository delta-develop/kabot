import asyncio

from app.services.storage.relational_storage import RelationalStorage


async def setup_all() -> None:
    """Initialize all storage backends asynchronously.
    """
    print("Initializing PostgreSQL...")
    relational_storage = RelationalStorage()
    await asyncio.gather(relational_storage.setup())


if __name__ == "__main__":
    """Run the setup process when the script is executed directly."""
    asyncio.run(setup_all())
