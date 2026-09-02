import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

import llm as helm_llm
import storage as doc_storage
from db import db
from deps import get_principal, perms_for, require_pro_perm
from helpers import compute_financials, fmt_money, log_activity

logger = logging.getLogger("helm")

router = APIRouter()

@router.get("/financials")
async def financials(principal=Depends(get_principal)):
    fin = await compute_financials(principal["workspace_id"])
    entries = await db.financial_entries.find({"workspace_id": principal["workspace_id"]}, {"_id": 0}).sort("month", -1).to_list(5000)
    return {**fin, "entries": entries, "can_write": "finance:write" in perms_for(principal["pack"]),
            "can_manage": "integrations:manage" in perms_for(principal["pack"])}


class FinEntryInput(BaseModel):
    type: str
    category: str
    amount: float
    month: str
    recurring: bool = False
    note: Optional[str] = ""
    source_document_id: Optional[str] = None


ALLOWED_DOC_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})
MAX_DOC_BYTES = 15 * 1024 * 1024


@router.post("/documents/upload")
async def upload_financial_document(
    file: UploadFile = File(...),
    principal=Depends(require_pro_perm("finance:write")),
):
    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed. Upload PDF, PNG, or JPEG.")
    data = await file.read()
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 15MB.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if not doc_storage.r2_configured():
        raise HTTPException(status_code=503, detail="Document storage is not configured")
    filename = (file.filename or "document").replace("/", "_").replace("\\", "_")[:200]
    try:
        storage_key = doc_storage.upload_document(
            principal["workspace_id"], data, filename, file.content_type,
        )
    except Exception as exc:
        logger.exception("document upload failed")
        raise HTTPException(status_code=500, detail="Could not store document") from exc
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    doc = {
        "id": doc_id,
        "workspace_id": principal["workspace_id"],
        "storage_key": storage_key,
        "filename": filename,
        "content_type": file.content_type,
        "uploaded_by": principal["user_id"],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "status": "uploaded",
        "extracted_data": None,
        "linked_entry_id": None,
    }
    await db.documents.insert_one(doc)
    await log_activity(principal, "financials", "document.upload", f"Uploaded bill · {filename}")
    return {"document_id": doc_id, "status": "uploaded"}


@router.post("/documents/{document_id}/extract")
async def extract_financial_document_route(
    document_id: str,
    principal=Depends(require_pro_perm("finance:write")),
):
    doc = await db.documents.find_one(
        {"id": document_id, "workspace_id": principal["workspace_id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not helm_llm.anthropic_configured():
        raise HTTPException(status_code=503, detail="AI extraction is not configured")
    try:
        file_bytes = doc_storage.get_document_bytes(doc["storage_key"])
        extracted = await helm_llm.extract_financial_document(file_bytes, doc["content_type"])
        status = "failed" if extracted.get("error") == "not_financial" else "extracted"
        await db.documents.update_one(
            {"id": document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": status, "extracted_data": extracted}},
        )
        if status == "extracted":
            await log_activity(
                principal, "financials", "document.extract",
                f"Extracted bill data · {doc['filename']}",
            )
        return extracted
    except ValueError as exc:
        await db.documents.update_one(
            {"id": document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": "failed", "extracted_data": {"error": "parse_failed"}}},
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("document extract failed for %s", document_id)
        await db.documents.update_one(
            {"id": document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": "failed", "extracted_data": {"error": "extract_failed"}}},
        )
        raise HTTPException(status_code=500, detail="Could not extract document") from exc


@router.get("/documents/{document_id}")
async def get_financial_document(
    document_id: str,
    principal=Depends(require_pro_perm("finance:write")),
):
    doc = await db.documents.find_one(
        {"id": document_id, "workspace_id": principal["workspace_id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        presigned_url = doc_storage.get_presigned_url(doc["storage_key"])
    except Exception as exc:
        logger.exception("presigned url failed for %s", document_id)
        raise HTTPException(status_code=500, detail="Could not generate document URL") from exc
    return {**doc, "presigned_url": presigned_url}


@router.post("/financials/entries")
async def add_fin_entry(payload: FinEntryInput, principal=Depends(require_pro_perm("finance:write"))):
    if payload.type not in ("revenue", "expense"):
        raise HTTPException(status_code=400, detail="type must be revenue or expense")
    source = "manual"
    source_document_id = None
    if payload.source_document_id:
        src_doc = await db.documents.find_one(
            {"id": payload.source_document_id, "workspace_id": principal["workspace_id"]}, {"_id": 0},
        )
        if not src_doc:
            raise HTTPException(status_code=400, detail="Source document not found")
        if src_doc.get("status") == "committed":
            raise HTTPException(status_code=400, detail="Document already committed to an entry")
        source = "ai_upload"
        source_document_id = payload.source_document_id
    entry = {"id": f"fe_{uuid.uuid4().hex[:10]}", "workspace_id": principal["workspace_id"],
             "type": payload.type, "category": payload.category.strip() or "Other",
             "amount": round(payload.amount, 2), "month": payload.month, "recurring": payload.recurring,
             "note": (payload.note or "").strip(), "source": source, "created_by": principal["user_id"],
             "created_at": datetime.now(timezone.utc).isoformat()}
    if source_document_id:
        entry["source_document_id"] = source_document_id
    await db.financial_entries.insert_one(entry)
    entry.pop("_id", None)
    if source_document_id:
        await db.documents.update_one(
            {"id": source_document_id, "workspace_id": principal["workspace_id"]},
            {"$set": {"status": "committed", "linked_entry_id": entry["id"]}},
        )
    await log_activity(principal, "financials", "entry.add",
                       f"Logged {payload.type} · {entry['category']} {fmt_money(entry['amount'])} ({payload.month})",
                       {"type": payload.type, "amount": entry["amount"], "month": payload.month})
    return {"ok": True, "entry": entry}


@router.patch("/financials/entries/{entry_id}")
async def edit_fin_entry(entry_id: str, payload: FinEntryInput, principal=Depends(require_pro_perm("finance:write"))):
    res = await db.financial_entries.update_one(
        {"id": entry_id, "workspace_id": principal["workspace_id"]},
        {"$set": {"type": payload.type, "category": payload.category.strip() or "Other",
                  "amount": round(payload.amount, 2), "month": payload.month,
                  "recurring": payload.recurring, "note": (payload.note or "").strip()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    await log_activity(principal, "financials", "entry.edit",
                       f"Updated a {payload.type} entry · {payload.category.strip() or 'Other'} ({payload.month})")
    return {"ok": True}


@router.delete("/financials/entries/{entry_id}")
async def delete_fin_entry(entry_id: str, principal=Depends(require_pro_perm("finance:write"))):
    doc = await db.financial_entries.find_one({"id": entry_id, "workspace_id": principal["workspace_id"]}, {"_id": 0})
    await db.financial_entries.delete_one({"id": entry_id, "workspace_id": principal["workspace_id"]})
    if doc:
        await log_activity(principal, "financials", "entry.delete",
                           f"Removed a {doc.get('type')} entry · {doc.get('category')} ({doc.get('month')})")
    return {"ok": True}


class FinSettingsInput(BaseModel):
    cash: float
    gross_margin: Optional[float] = None


@router.put("/financials/settings")
async def update_fin_settings(payload: FinSettingsInput, principal=Depends(require_pro_perm("finance:write"))):
    await db.workspaces.update_one({"workspace_id": principal["workspace_id"]},
                                   {"$set": {"financial_settings.cash": round(payload.cash, 2),
                                             "financial_settings.gross_margin": payload.gross_margin}})
    fin = await compute_financials(principal["workspace_id"])
    runway = fin["runway_months"]
    await log_activity(principal, "financials", "settings.update",
                       f"Updated cash to {fmt_money(payload.cash)}" + (f" — runway now {runway}mo" if runway else ""),
                       {"cash": payload.cash, "runway_months": runway})
    return {"ok": True}
