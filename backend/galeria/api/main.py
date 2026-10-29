import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from galeria.api.jobs import IndexJobs
from galeria.api.routes import index, media, search
from galeria.config import Settings
from galeria.core.encoder import Encoder
from galeria.services import open_services

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, encoder: Encoder | None = None) -> FastAPI:
    """Build the app. Tests pass a FakeEncoder; production loads CLIP from settings."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services = open_services(settings, encoder)
        started = time.perf_counter()
        # Load weights and run one pass now, so the first user query is not the slow one.
        services.encoder.warmup()
        log.info("encoder ready in %.1fs", time.perf_counter() - started)
        app.state.services = services
        app.state.jobs = IndexJobs(services.indexer)
        try:
            yield
        finally:
            app.state.jobs.wait(timeout=5)
            services.close()

    app = FastAPI(
        title="Galeria",
        description="Semantic photo & video search with multilingual CLIP and FAISS.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    for router in (search.router, index.router, media.router):
        app.include_router(router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
