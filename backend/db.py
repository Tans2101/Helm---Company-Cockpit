"""Database connection and environment configuration."""
import os
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

import clerk_auth
from helm_config import HELM_CANONICAL_ORIGIN, is_stale_deploy_url

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helm")


def _mongo_candidate_urls() -> list[str]:
    """Ordered Mongo URLs to try — Render pserv first unless USE_ATLAS_MONGO=true."""
    seen: set[str] = set()
    urls: list[str] = []

    def add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    use_atlas = os.environ.get("USE_ATLAS_MONGO", "").lower() in ("1", "true", "yes")
    hostport = os.environ.get("MONGO_HOSTPORT", "").strip()
    host = os.environ.get("MONGO_HOST", "").strip()
    atlas = os.environ.get("MONGO_URL", "").strip()

    def add_pserv() -> None:
        if hostport:
            add(f"mongodb://{hostport}")
            return
        if not host and os.environ.get("RENDER"):
            host_local = "helm-mongo"
        else:
            host_local = host
        if host_local:
            add(f"mongodb://{host_local}:27017")

    if use_atlas:
        if atlas:
            add(atlas)
        return urls

    add_pserv()
    if atlas:
        add(atlas)
    return urls


def _redact_mongo_url(url: str) -> str:
    if "@" not in url:
        return url
    prefix, rest = url.split("@", 1)
    return f"{prefix.split('://')[0]}://***@{rest}"


def _mongo_source_label(url: str) -> str:
    if url.startswith("mongodb+srv://"):
        return "atlas"
    if "helm-mongo" in url or os.environ.get("MONGO_HOST", "").strip() in url:
        return "render_pserv"
    if os.environ.get("MONGO_HOST", "").strip():
        return "mongo_host"
    return "mongo_url"


def _resolve_mongo_url() -> tuple[str, str]:
    """Pick Mongo URL without blocking import — health check probes connectivity."""
    candidates = _mongo_candidate_urls()
    if not candidates:
        raise RuntimeError("Set MONGO_URL (Atlas) or sync render.yaml for MONGO_HOST / helm-mongo")
    url = candidates[0]
    return url, _mongo_source_label(url)


DB_NAME = os.environ["DB_NAME"]

# -----------------------------------------------------------------------------
# Environment configuration — see DEPLOY.md and README go-live checklist.
# -----------------------------------------------------------------------------

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()


def _make_mongo_client(url: str) -> AsyncIOMotorClient:
    is_atlas = url.startswith("mongodb+srv://")
    return AsyncIOMotorClient(
        url,
        serverSelectionTimeoutMS=8000 if is_atlas else 3000,
        connectTimeoutMS=8000 if is_atlas else 3000,
        socketTimeoutMS=10000,
    )


mongo_url, MONGO_SOURCE = _resolve_mongo_url()
client = _make_mongo_client(mongo_url)
db = client[DB_NAME]

SESSION_SECRET = os.environ.get("SESSION_SECRET", "change-me-in-production")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
if is_stale_deploy_url(FRONTEND_URL):
    FRONTEND_URL = HELM_CANONICAL_ORIGIN
ALLOW_DEMO_LOGIN = os.environ.get("ALLOW_DEMO_LOGIN", "false").lower() in ("1", "true", "yes")
DEMO_RESET_ENABLED = os.environ.get("DEMO_RESET_ENABLED", "false").lower() in ("1", "true", "yes")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax")
OAUTH_STATE_SECRET = os.environ.get("OAUTH_STATE_SECRET", "")
if not OAUTH_STATE_SECRET:
    OAUTH_STATE_SECRET = SESSION_SECRET
APP_URL = (os.environ.get("APP_URL") or FRONTEND_URL or "").rstrip("/")
if is_stale_deploy_url(APP_URL):
    APP_URL = HELM_CANONICAL_ORIGIN
PRO_PRICE = float(os.environ.get("PRO_PRICE", "8"))
BILLING_ENFORCED = os.environ.get("BILLING_ENFORCED", "false").lower() in ("1", "true", "yes")
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", "").strip() or None

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
QB_CLIENT_ID = os.environ.get("QUICKBOOKS_CLIENT_ID", "")
QB_CLIENT_SECRET = os.environ.get("QUICKBOOKS_CLIENT_SECRET", "")
QB_ENV = os.environ.get("QUICKBOOKS_ENV", "sandbox")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
PADDLE_API_KEY = os.environ.get("PADDLE_API_KEY", "")
PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")
PADDLE_PRICE_ID = os.environ.get("PADDLE_PRICE_ID", "")
PADDLE_WEBHOOK_SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
PADDLE_ENV = os.environ.get("PADDLE_ENV", "sandbox")
PADDLE_API_BASE = "https://sandbox-api.paddle.com" if PADDLE_ENV == "sandbox" else "https://api.paddle.com"
CLERK_PUBLISHABLE_KEY = clerk_auth.resolve_clerk_publishable_key()
SETUP_SECRET = os.environ.get("SETUP_SECRET", "").strip()

_INSECURE_SESSION_SECRETS = frozenset({
    "change-me-in-production",
    "change-me-to-a-long-random-string",
})


def enforce_production_config() -> None:
    """Refuse to boot with known-insecure settings when ENVIRONMENT=production."""
    if ENVIRONMENT != "production":
        return
    problems: list[str] = []
    raw_session = (os.environ.get("SESSION_SECRET") or "").strip()
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


async def mongo_ping() -> bool:
    try:
        await asyncio.wait_for(db.command("ping", maxTimeMS=2000), timeout=3.0)
        return True
    except Exception:
        return False


async def connect_mongo_at_startup() -> None:
    """Probe candidate URLs and bind to the first reachable Mongo."""
    global client, db, mongo_url, MONGO_SOURCE
    candidates = _mongo_candidate_urls()
    if not candidates:
        logger.error("No Mongo URL configured — set MONGO_URL or sync render.yaml")
        return

    for attempt in range(1, 6):
        for url in candidates:
            probe = _make_mongo_client(url)
            try:
                await asyncio.wait_for(
                    probe.admin.command("ping", maxTimeMS=3000),
                    timeout=5.0,
                )
            except Exception as exc:
                probe.close()
                logger.warning(
                    "Mongo unreachable attempt %d (%s): %s",
                    attempt, _redact_mongo_url(url), exc,
                )
                continue
            if probe is not client:
                client.close()
            client = probe
            db = client[DB_NAME]
            mongo_url = url
            MONGO_SOURCE = _mongo_source_label(url)
            logger.info("Mongo connected via %s (%s)", MONGO_SOURCE, _redact_mongo_url(url))
            return
        if attempt < 5:
            await asyncio.sleep(min(2 * attempt, 8))

    logger.error("Mongo unavailable after probing %d candidate URL(s)", len(candidates))


async def require_mongo() -> None:
    from fastapi import HTTPException

    if await mongo_ping():
        return
    await connect_mongo_at_startup()
    if not await mongo_ping():
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Check MONGO_URL and Atlas Network Access on Render.",
        )


async def ensure_indexes() -> None:
    specs = [
        (db.users, [("email", 1)], {"unique": True}),
        (db.users, [("google_sub", 1)], {"unique": True, "sparse": True}),
        (db.users, [("clerk_id", 1)], {"unique": True, "sparse": True}),
        (db.memberships, [("user_id", 1), ("workspace_id", 1)], {}),
        (db.memberships, [("email", 1), ("status", 1)], {}),
        (db.workspaces, [("workspace_id", 1)], {"unique": True}),
        (db.workspaces, [("join_code", 1)], {"unique": True, "sparse": True}),
        (db.user_sessions, [("session_token", 1)], {"unique": True}),
        (db.user_sessions, [("expires_at", 1)], {"expireAfterSeconds": 0}),
        (db.paddle_events, [("_id", 1)], {"unique": True}),
        (db.paddle_intents, [("_id", 1)], {"unique": True}),
        (db.paddle_intents, [("created_at", 1)], {"expireAfterSeconds": 3600}),
        (db.deals, [("workspace_id", 1)], {}),
        (db.financial_entries, [("workspace_id", 1)], {}),
        (db.financial_entries, [("workspace_id", 1), ("qb_txn_id", 1)], {"unique": True, "sparse": True}),
        (db.documents, [("workspace_id", 1)], {}),
        (db.documents, [("id", 1)], {"unique": True}),
        (db.activities, [("workspace_id", 1)], {}),
        (db.updates, [("workspace_id", 1)], {}),
        (db.chat_messages, [("workspace_id", 1)], {}),
    ]
    for collection, keys, opts in specs:
        try:
            await asyncio.wait_for(collection.create_index(keys, **opts), timeout=1.5)
        except Exception:
            logger.debug("index ensure skipped for %s", keys, exc_info=True)
