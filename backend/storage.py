"""Cloudflare R2 (S3-compatible) document storage."""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from io import BytesIO
from uuid import uuid4

import boto3
from botocore.client import Config
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger("helm")

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")

MAX_IMAGE_EDGE = 2000
JPEG_QUALITY = 85
_IMAGE_FORMATS = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
}


def r2_configured() -> bool:
    return bool(R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_ENDPOINT)


@lru_cache(maxsize=1)
def _client():
    """Reuse one thread-safe boto3 client and its HTTP connection pool."""
    if not r2_configured():
        raise RuntimeError("R2 storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _content_type_key(content_type: str) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def maybe_compress_image(file_bytes: bytes, content_type: str, filename: str = "") -> bytes:
    """Resize and re-encode image uploads. PDFs and other non-images are unchanged."""
    out_format = _IMAGE_FORMATS.get(_content_type_key(content_type))
    if not out_format or not file_bytes:
        return file_bytes

    label = filename or "upload"
    before = len(file_bytes)
    img = None
    try:
        img = Image.open(BytesIO(file_bytes))
        img.load()
        transposed = ImageOps.exif_transpose(img)
        if transposed is not None:
            img = transposed

        width, height = img.size
        longest = max(width, height)
        if longest > MAX_IMAGE_EDGE:
            scale = MAX_IMAGE_EDGE / longest
            img = img.resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.LANCZOS,
            )

        buf = BytesIO()
        if out_format == "JPEG":
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                rgba = img.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[-1])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        else:
            if img.mode == "P":
                img = img.convert("RGBA") if "transparency" in img.info else img.convert("RGB")
            elif img.mode in ("I", "F"):
                img = img.convert("RGBA")
            img.save(buf, format="PNG", optimize=True)
        compressed = buf.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        logger.warning("image compression skipped for %s (unreadable)", label)
        return file_bytes
    except Exception:
        logger.exception("image compression failed for %s; storing original", label)
        return file_bytes
    finally:
        if img is not None:
            img.close()

    after = len(compressed)
    if after >= before:
        logger.info(
            "image compression skipped for %s: %d bytes (re-encode was %d)",
            label, before, after,
        )
        return file_bytes

    logger.info(
        "image compressed %s: %d -> %d bytes (%.0f%% of original)",
        label, before, after, 100.0 * after / before,
    )
    return compressed


def upload_document(workspace_id: str, file_bytes: bytes, filename: str, content_type: str) -> str:
    safe_name = (filename or "document").replace("/", "_").replace("\\", "_")[:200]
    body = maybe_compress_image(file_bytes, content_type, safe_name)
    key = f"{workspace_id}/{uuid4()}-{safe_name}"
    _client().put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=body,
        ContentType=content_type,
        CacheControl="private, no-store",
    )
    return key


def get_document_bytes(key: str) -> bytes:
    resp = _client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
    return resp["Body"].read()


def get_presigned_url(key: str, expires_in: int = 900) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in,
    )


def delete_document(key: str) -> None:
    _client().delete_object(Bucket=R2_BUCKET_NAME, Key=key)
