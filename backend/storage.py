"""Cloudflare R2 (S3-compatible) document storage."""
from __future__ import annotations

import os
from uuid import uuid4

import boto3
from botocore.client import Config

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")


def r2_configured() -> bool:
    return bool(R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME and R2_ENDPOINT)


def _client():
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


def upload_document(workspace_id: str, file_bytes: bytes, filename: str, content_type: str) -> str:
    safe_name = (filename or "document").replace("/", "_").replace("\\", "_")[:200]
    key = f"{workspace_id}/{uuid4()}-{safe_name}"
    _client().put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


def get_document_bytes(key: str) -> bytes:
    resp = _client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
    return resp["Body"].read()


def get_presigned_url(key: str, expires_in: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in,
    )
