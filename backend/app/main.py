from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.assets.api import router as assets_router
from app.modules.auth.api import router as auth_router
from app.modules.portfolios.api import router as portfolios_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Tables are managed by Alembic migrations.
    yield


app = FastAPI(title="Found Tracker", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(portfolios_router)


@app.get("/")
def root():
    return {"status": "ok"}
