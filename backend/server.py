"""Helm API entrypoint — mounts domain routers and configures middleware."""
import asyncio
import logging
import os

import clerk_auth
import llm as helm_llm
import storage as doc_storage
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from db import (
    APP_URL,
    CORS_ORIGINS,
    CORS_ORIGIN_REGEX,
    ENVIRONMENT,
    FRONTEND_URL,
    SESSION_SECRET,
    ALLOW_DEMO_LOGIN,
    _INSECURE_SESSION_SECRETS,
    _mongo_candidate_urls,
    client,
    connect_mongo_at_startup,
    db,
    ensure_indexes,
)
from helpers import log_activity
from routes import (
    admin,
    ai,
    auth,
    billing,
    decisions,
    financials,
    integrations,
    people,
    pipeline,
    tasks,
    workspaces,
)
from routes.integrations import GOOGLE_SCOPES
from static_frontend import mount_static_frontend, should_serve_static

logger = logging.getLogger("helm")


def _enforce_production_config() -> None:
    """Refuse to boot with known-insecure settings when ENVIRONMENT=production."""
    if ENVIRONMENT != "production":
        return
    problems: list[str] = []
    raw_session = (SESSION_SECRET or "").strip()
    if not raw_session or SESSION_SECRET in _INSECURE_SESSION_SECRETS:
        problems.append("SESSION_SECRET must be set to a strong random value (not a placeholder)")
    if not (os.environ.get("OAUTH_STATE_SECRET") or "").strip():
        problems.append("OAUTH_STATE_SECRET must be set explicitly in production")
    if not CORS_ORIGINS:
        problems.append("CORS_ORIGINS must list your frontend origin(s)")
    if ALLOW_DEMO_LOGIN:
        problems.append("ALLOW_DEMO_LOGIN must be false in production")
    if problems:
        raise RuntimeError(
            "Production configuration invalid (ENVIRONMENT=production):\n"
            + "\n".join(f"  - {p}" for p in problems)
            + "\nSee DEPLOY.md and the config header in db.py."
        )


_enforce_production_config()

app = FastAPI()

_API_ROUTERS = (
    auth,
    workspaces,
    financials,
    pipeline,
    tasks,
    people,
    decisions,
    integrations,
    billing,
    ai,
    admin,
)

for module in _API_ROUTERS:
    app.include_router(module.router, prefix="/api")

_serve_static = should_serve_static()
if not _serve_static:

    @app.get("/")
    async def api_root():
        """Friendly response when someone opens the Render host directly (API-only)."""
        return {
            "service": "Helm CEO Operating System API",
            "message": "This URL is the API backend. Open your Vercel app to use Helm.",
            "health": "/api/health",
            "auth": "/api/auth/config",
            "frontend": FRONTEND_URL or None,
        }

_cors_origins = list(dict.fromkeys(
    CORS_ORIGINS + clerk_auth.helm_frontend_origins()
)) or (clerk_auth.helm_frontend_origins() or ["http://localhost:3000"])
_cors_regex = CORS_ORIGIN_REGEX
if not _cors_regex and any("emergentagent.com" in o for o in _cors_origins):
    _cors_regex = r"https://.*\.emergentagent\.com"
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

if _serve_static:
    mount_static_frontend(app)


@app.on_event("startup")
async def startup():
    await connect_mongo_at_startup()
    asyncio.create_task(ensure_indexes())
    asyncio.create_task(clerk_auth.sync_clerk_instance())
    if clerk_auth.clerk_configured():
        asyncio.create_task(clerk_auth.prefetch_jwks())


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


from deps import _allowed_auth_redirect, get_principal  # noqa: E402

__all__ = [
    "app",
    "APP_URL",
    "_allowed_auth_redirect",
    "_enforce_production_config",
    "_mongo_candidate_urls",
    "GOOGLE_SCOPES",
    "_cors_regex",
    "ENVIRONMENT",
    "SESSION_SECRET",
    "CORS_ORIGINS",
    "ALLOW_DEMO_LOGIN",
    "db",
    "get_principal",
    "doc_storage",
    "helm_llm",
    "log_activity",
]
