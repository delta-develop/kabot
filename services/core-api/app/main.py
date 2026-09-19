from contextlib import asynccontextmanager

import dotenv
from fastapi import FastAPI

from app.api.routes.memory import router as memory_router
from app.api.routes.meta import router as meta_router
from app.api.routes.vehicles import router as vehicles_router
from app.api.routes.whatsapp import router as whatsapp_router
from app.services.storage.relational_storage import RelationalStorage

dotenv.load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: create_all on boot instead of migrations. Move to Alembic when
    # the schema starts changing between releases.
    await RelationalStorage().setup()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(vehicles_router)
app.include_router(whatsapp_router)
app.include_router(memory_router)
app.include_router(meta_router)
