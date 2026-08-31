"""Serve the React production build from FastAPI (apexcoach.tech on Render)."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_ROOT = Path(__file__).resolve().parent / "static"


def should_serve_static() -> bool:
    if os.environ.get("HELM_SERVE_STATIC", "").strip().lower() in ("1", "true", "yes"):
        return True
    return (STATIC_ROOT / "index.html").is_file()


def mount_static_frontend(app) -> bool:
    """Mount CRA build at repo backend/static. Returns True when active."""
    if not should_serve_static():
        return False
    if not (STATIC_ROOT / "index.html").is_file():
        return False

    assets = STATIC_ROOT / "static"
    if assets.is_dir():
        app.mount("/static", StaticFiles(directory=assets), name="helm-assets")

    root_files = (
        "favicon.ico",
        "manifest.json",
        "robots.txt",
        "asset-manifest.json",
        "favicon.svg",
    )

    for name in root_files:
        path = STATIC_ROOT / name
        if not path.is_file():
            continue

        @app.get(f"/{name}", include_in_schema=False)
        async def _root_file(file_path=path):
            return FileResponse(file_path)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = STATIC_ROOT / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_ROOT / "index.html")

    return True
