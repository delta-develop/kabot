import dotenv
from fastapi import FastAPI

from app.api.routes.memory import router as memory_router
from app.api.routes.meta import router as meta_router
from app.api.routes.vehicles import router as vehicles_router
from app.api.routes.whatsapp import router as whatsapp_router

dotenv.load_dotenv()
app = FastAPI()
app.include_router(vehicles_router)
app.include_router(whatsapp_router)
app.include_router(memory_router)
app.include_router(meta_router)
