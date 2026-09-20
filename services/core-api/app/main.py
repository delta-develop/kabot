from contextlib import asynccontextmanager

import dotenv
import logfire
from fastapi import FastAPI

from app.api.routes.memory import router as memory_router
from app.api.routes.meta import router as meta_router
from app.api.routes.vehicles import router as vehicles_router
from app.api.routes.whatsapp import router as whatsapp_router
from app.services.storage.relational_storage import RelationalStorage

dotenv.load_dotenv()

logfire.configure(send_to_logfire="if-token-present")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: create_all on boot instead of migrations. Move to Alembic when
    # the schema starts changing between releases.
    await RelationalStorage().setup()
    yield


app = FastAPI(lifespan=lifespan)
logfire.instrument_fastapi(app)
logfire.instrument_httpx()
logfire.instrument_asyncpg()
logfire.instrument_redis()
logfire.instrument_pymongo()

app.include_router(vehicles_router)
app.include_router(whatsapp_router)
app.include_router(memory_router)
app.include_router(meta_router)
