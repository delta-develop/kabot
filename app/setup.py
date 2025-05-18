from app.services.storage.relational_storage import RelationalStorage
from app.services.storage.search_engine_storage import SearchEngineStorage

import time
from opensearchpy.exceptions import ConnectionError


def setup_all() -> None:
    """Initialize all storage backends (PostgreSQL and OpenSearch).

    This function sets up the PostgreSQL relational storage and the OpenSearch
    search engine storage by creating their respective clients and running
    their setup procedures.
    """
    print("Initializing PostgreSQL...")
    relational_storage = RelationalStorage()
    relational_storage.setup()

    print("Initializing OpenSearch...")
    search_engine_storage = SearchEngineStorage()
    search_engine_storage.setup()


if __name__ == "__main__":
    """Entry point for setup script.

    Runs the setup procedure for all storage backends.
    """
    setup_all()
