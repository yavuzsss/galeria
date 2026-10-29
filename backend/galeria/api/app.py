"""ASGI entry point for uvicorn: `uvicorn galeria.api.app:app`."""

from galeria.api.main import create_app

app = create_app()
