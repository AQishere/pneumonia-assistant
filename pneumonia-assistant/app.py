"""Vercel entrypoint: Vercel loads the top-level `app`. Locally, use
`uvicorn api.main:create_app --factory` instead."""

from api.main import create_app

app = create_app()
