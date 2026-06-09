import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, require_business_access
from app.db.session import get_db_session
from app.models.agent import Lead, LeadEvent, LeadNote
from app.schemas.leads import (
    AddNoteRequest,
    LeadEventResponse,
    LeadNoteResponse,
    LeadResponse,
    LeadTimelineResponse,
    LeadUpdateRequest,
    PaginatedLeads,
)

router = APIRouter(prefix="/leads", tags=["leads"])

_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 25

# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("/{business_id}", response_model=PaginatedLeads)
async def list_leads(
    business_id: uuid.UUID,
    q: str | None = Query(None, description="Search name / phone / email"),
    stage: str | None = Query(None, description="Comma-separated stage values, e.g. new,contacted"),
    source: str | None = Query(None, description="Comma-separated source values"),
    assigned: str | None = Query("all", description="all | me | unassigned"),
    sort: str = Query("updated_desc", description="updated_desc | created_asc | stage_asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedLeads:
    require_business_access(ctx, business_id)
    stmt = select(Lead).where(Lead.business_id == business_id)

    # --- Search ---
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Lead.name.ilike(term),
                Lead.phone.ilike(term),
                Lead.email.ilike(term),
            )
        )

    # --- Stage filter ---
    if stage:
        stages = [s.strip() for s in stage.split(",") if s.strip()]
        if stages:
            stmt = stmt.where(Lead.stage.in_(stages))

    # --- Source filter ---
    if source:
        sources = [s.strip() for s in source.split(",") if s.strip()]
        if sources:
            stmt = stmt.where(Lead.source.in_(sources))

    # --- Assignment filter — "me" uses the authenticated user's ID ---
    if assigned == "me":
        stmt = stmt.where(Lead.assigned_user_id == ctx.user_id)
    elif assigned == "unassigned":
        stmt = stmt.where(Lead.assigned_user_id.is_(None))

    # --- Sort ---
    if sort == "created_asc":
        stmt = stmt.order_by(Lead.created_at.asc())
    elif sort == "stage_asc":
        stmt = stmt.order_by(Lead.stage.asc(), Lead.updated_at.desc())
    else:  # updated_desc (default)
        stmt = stmt.order_by(Lead.updated_at.desc())

    # --- Total count (same filters, no pagination) ---
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await session.execute(count_stmt)).scalar_one()

    # --- Paginate ---
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    leads = list((await session.execute(stmt)).scalars().all())

    return PaginatedLeads(
        items=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


@router.get("/{business_id}/{lead_id}", response_model=LeadResponse)
async def get_lead(
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    require_business_access(ctx, business_id)
    lead = await _get_lead_or_404(session, business_id, lead_id)
    return LeadResponse.model_validate(lead)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.patch("/{business_id}/{lead_id}", response_model=LeadResponse)
async def update_lead(
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadUpdateRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Partial update for stage transitions, field edits, and assignment changes.

    Writes a `LeadEvent` for every meaningful change so the timeline stays
    accurate. Stage changes also update `stage_changed_at`.
    """
    require_business_access(ctx, business_id)
    lead = await _get_lead_or_404(session, business_id, lead_id)
    fields_set = payload.model_fields_set
    events_to_write: list[dict[str, Any]] = []

    # Stage change
    if "stage" in fields_set and payload.stage is not None and payload.stage != lead.stage:
        events_to_write.append({
            "event_type": "stage_changed",
            "payload": {"from": lead.stage, "to": payload.stage},
        })
        lead.stage = payload.stage
        lead.stage_changed_at = datetime.now(tz=timezone.utc)

    # Assignment change
    if "assigned_user_id" in fields_set and payload.assigned_user_id != lead.assigned_user_id:
        events_to_write.append({
            "event_type": "assigned",
            "payload": {"assigned_to": str(payload.assigned_user_id) if payload.assigned_user_id else None},
        })
        lead.assigned_user_id = payload.assigned_user_id

    # Scalar field changes
    _SCALAR_FIELDS = ("name", "phone", "email", "budget", "service_interested")
    for field in _SCALAR_FIELDS:
        if field not in fields_set:
            continue
        new_value = getattr(payload, field)
        old_value = getattr(lead, field)
        if new_value != old_value:
            events_to_write.append({
                "event_type": "field_updated",
                "payload": {"field": field, "from": old_value, "to": new_value},
            })
            setattr(lead, field, new_value)

    lead.updated_at = datetime.now(tz=timezone.utc)

    for event_data in events_to_write:
        session.add(
            LeadEvent(
                lead_id=lead.id,
                business_id=business_id,
                actor_id=ctx.user_id,
                **event_data,
            )
        )

    await session.flush()
    await session.refresh(lead)
    return LeadResponse.model_validate(lead)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


@router.get("/{business_id}/{lead_id}/timeline", response_model=LeadTimelineResponse)
async def get_lead_timeline(
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> LeadTimelineResponse:
    require_business_access(ctx, business_id)
    await _get_lead_or_404(session, business_id, lead_id)

    events_stmt = (
        select(LeadEvent)
        .where(LeadEvent.lead_id == lead_id, LeadEvent.business_id == business_id)
        .order_by(LeadEvent.created_at.asc())
    )
    notes_stmt = (
        select(LeadNote)
        .where(LeadNote.lead_id == lead_id, LeadNote.business_id == business_id)
        .order_by(LeadNote.created_at.asc())
    )

    events = list((await session.execute(events_stmt)).scalars().all())
    notes = list((await session.execute(notes_stmt)).scalars().all())

    return LeadTimelineResponse(
        events=[LeadEventResponse.model_validate(e) for e in events],
        notes=[LeadNoteResponse.model_validate(n) for n in notes],
    )


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


@router.post("/{business_id}/{lead_id}/notes", response_model=LeadNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_note(
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: AddNoteRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> LeadNoteResponse:
    require_business_access(ctx, business_id)
    lead = await _get_lead_or_404(session, business_id, lead_id)

    note = LeadNote(
        lead_id=lead.id,
        business_id=business_id,
        author_id=ctx.user_id,
        content=payload.content,
    )
    session.add(note)
    await session.flush()

    preview = payload.content[:120] + ("…" if len(payload.content) > 120 else "")
    session.add(
        LeadEvent(
            lead_id=lead.id,
            business_id=business_id,
            actor_id=ctx.user_id,
            event_type="note_added",
            payload={"note_id": str(note.id), "preview": preview},
        )
    )

    lead.updated_at = datetime.now(tz=timezone.utc)

    await session.flush()
    await session.refresh(note)
    return LeadNoteResponse.model_validate(note)


@router.delete("/{business_id}/{lead_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    note_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    require_business_access(ctx, business_id)
    await _get_lead_or_404(session, business_id, lead_id)

    note = await session.get(LeadNote, note_id)
    if note is None or note.lead_id != lead_id or note.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Note not found")

    preview = note.content[:120] + ("…" if len(note.content) > 120 else "")
    session.add(
        LeadEvent(
            lead_id=lead_id,
            business_id=business_id,
            actor_id=ctx.user_id,
            event_type="note_deleted",
            payload={"content_preview": preview},
        )
    )

    await session.delete(note)
    await session.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_lead_or_404(session: AsyncSession, business_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
    lead = await session.get(Lead, lead_id)
    if lead is None or lead.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead
