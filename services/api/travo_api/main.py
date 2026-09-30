from __future__ import annotations

from fastapi import FastAPI

from travo_api.config import check_production, get_settings
from travo_api.routes import admin, auth, documents, findings, matters, me, playbooks, reviews


def create_app() -> FastAPI:
    check_production(get_settings())
    app = FastAPI(title="Travo API", version="0.1.0-p1")
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(matters.router)
    app.include_router(documents.router)
    app.include_router(reviews.router)
    app.include_router(findings.router)
    app.include_router(playbooks.router)
    app.include_router(admin.router)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
