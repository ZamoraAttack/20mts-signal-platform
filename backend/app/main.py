import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import analytics as analytics_routes
from .api.routes import config as config_routes
from .api.routes import journal as journal_routes
from .api.routes import sessions as session_routes
from .api.routes import signals as signal_routes
from .api.routes import status as status_routes
from .api.websockets import live as live_ws
from .config import settings
from .data_feed import FeedManager, ReplayFeed, SchwabFeed, SimulatedFeed
from .database import create_tables
from .engine.runner import EngineRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()

    if settings.data_feed_provider == "schwab":
        feed = SchwabFeed()
    elif settings.data_feed_provider == "replay":
        feed = ReplayFeed(file_path=settings.replay_file_path, speed=settings.replay_speed)
    else:
        feed = SimulatedFeed(seed=42)
    feed_manager = FeedManager(feed)
    await feed_manager.connect()
    runner = EngineRunner(feed_manager, settings)
    await runner.startup()

    status_routes.engine_runner = runner

    async def _run_feed():
        try:
            await feed_manager.start()
        finally:
            await runner.flush_pending_ticks()

    feed_task = asyncio.create_task(_run_feed())

    yield

    await feed_manager.stop()
    feed_task.cancel()


app = FastAPI(title="20 MTS Signal Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signal_routes.router)
app.include_router(journal_routes.router)
app.include_router(config_routes.router)
app.include_router(session_routes.router)
app.include_router(status_routes.router)
app.include_router(analytics_routes.router)
app.include_router(live_ws.router)


@app.get("/")
async def root():
    return {"name": "20 MTS Signal Platform", "status": "running"}
