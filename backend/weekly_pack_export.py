"""Render the Weekly CEO Pack markdown to a simple, shareable PDF."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

_GOLD = HexColor("#8a7340")
_INK = HexColor("#18181b")
_MUTED = HexColor("#52525b")
_MAX_CHARS = 200_000

_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")
_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_INLINE_ITAL = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def slug_filename_part(name: str, fallback: str = "workspace") -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", "-", (name or "").strip())
    raw = raw.strip("-")[:40] or fallback
    return raw


def pdf_filename(workspace_name: str, when: datetime | None = None) -> str:
    day = (when or datetime.now(timezone.utc)).date().isoformat()
    return f"Helm-Weekly-Pack-{slug_filename_part(workspace_name)}-{day}.pdf"


def _inline_xml(text: str) -> str:
    escaped = html.escape(text or "", quote=False)
    escaped = _INLINE_BOLD.sub(r"<b>\1</b>", escaped)
    escaped = _INLINE_ITAL.sub(r"<i>\1</i>", escaped)
    return escaped.replace("\n", "<br/>")


def _styles():
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "PackKicker",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            textColor=_MUTED,
            spaceAfter=2,
            tracking=1,
        ),
        "title": ParagraphStyle(
            "PackTitle",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=18,
            textColor=_INK,
            spaceAfter=4,
            leading=22,
        ),
        "meta": ParagraphStyle(
            "PackMeta",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            textColor=_MUTED,
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "PackH1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=14,
            textColor=_INK,
            spaceBefore=14,
            spaceAfter=6,
            leading=18,
        ),
        "h2": ParagraphStyle(
            "PackH2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=12,
            textColor=_INK,
            spaceBefore=10,
            spaceAfter=4,
            leading=16,
        ),
        "h3": ParagraphStyle(
            "PackH3",
            parent=base["Heading3"],
            fontName="Times-Bold",
            fontSize=11,
            textColor=_INK,
            spaceBefore=8,
            spaceAfter=3,
            leading=14,
        ),
        "body": ParagraphStyle(
            "PackBody",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            textColor=_INK,
            leading=15,
            spaceAfter=8,
            alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "PackBullet",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            textColor=_INK,
            leading=15,
            leftIndent=16,
            bulletIndent=4,
            spaceAfter=3,
        ),
        "footer": ParagraphStyle(
            "PackFooter",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=8,
            textColor=_MUTED,
        ),
    }


def markdown_to_flowables(markdown: str, styles: dict) -> list:
    story = []
    para_buf: list[str] = []

    def flush_para():
        text = " ".join(para_buf).strip()
        para_buf.clear()
        if text:
            story.append(Paragraph(_inline_xml(text), styles["body"]))

    for raw in (markdown or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            continue
        heading = _HEADING.match(line.strip())
        if heading:
            flush_para()
            level = len(heading.group(1))
            style = styles["h1"] if level == 1 else styles["h2"] if level == 2 else styles["h3"]
            story.append(Paragraph(_inline_xml(heading.group(2).strip()), style))
            continue
        bullet = _BULLET.match(line.strip())
        if bullet:
            flush_para()
            story.append(Paragraph("• " + _inline_xml(bullet.group(1).strip()), styles["bullet"]))
            continue
        para_buf.append(line.strip())
    flush_para()
    return story


def render_weekly_pack_pdf(
    content: str,
    *,
    workspace_name: str,
    generated_at: datetime | None = None,
) -> bytes:
    body = (content or "").strip()
    if not body:
        raise ValueError("Pack content is empty")
    if len(body) > _MAX_CHARS:
        body = body[:_MAX_CHARS]

    when = generated_at or datetime.now(timezone.utc)
    date_label = when.strftime("%B %d, %Y").replace(" 0", " ")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"Weekly CEO Pack — {workspace_name}",
        author="Helm",
    )
    styles = _styles()
    story = [
        Paragraph("Weekly CEO Pack", styles["kicker"]),
        Paragraph(_inline_xml(workspace_name or "Company"), styles["title"]),
        Paragraph(_inline_xml(date_label), styles["meta"]),
        HRFlowable(width="100%", thickness=0.6, color=_GOLD, spaceAfter=12),
    ]
    story.extend(markdown_to_flowables(body, styles))
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.4, color=HexColor("#d4d4d8"), spaceBefore=8, spaceAfter=8))
    story.append(Paragraph("Generated with Helm — share with your leadership team, investors, or accountant.", styles["footer"]))
    doc.build(story)
    return buf.getvalue()
