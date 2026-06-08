import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Lead
from app.schemas.agent import StructuredAgentReply

# Maps the structured-reply's dedicated identity fields onto `leads` columns;
# everything else in `extracted_lead_fields` is merged into `notes`/known
# qualification data by the caller (sales_agent_service) via `qualification_fields`.
_IDENTITY_FIELD_COLUMNS = {"name": "lead_name", "email": "lead_email", "phone": "lead_phone"}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DIRECT_LEAD_COLUMNS = {"budget", "service_interested"}


def _is_plausible_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


async def get_or_create_lead(
    session: AsyncSession,
    *,
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    contact_phone: str,
    contact_name: str | None,
) -> Lead:
    """Fetch the lead tied to this conversation, or start one from the contact's WhatsApp profile.

    One lead per conversation keeps the funnel view simple and matches how a
    sales rep would think about a single WhatsApp thread.
    """
    existing = await session.scalar(select(Lead).where(Lead.conversation_id == conversation_id))
    if existing is not None:
        return existing

    lead = Lead(
        business_id=business_id,
        conversation_id=conversation_id,
        name=contact_name,
        phone=contact_phone,
        stage="new",
        source="whatsapp",
    )
    session.add(lead)
    await session.flush()
    return lead


def apply_extracted_fields(
    lead: Lead, structured: StructuredAgentReply, qualification_keys: set[str]
) -> dict[str, str]:
    """Merge newly-volunteered data onto `lead` in place; never overwrite known values.

    Returns only the fields that were *actually applied* this turn — callers
    persist this subset onto `ai_interactions.extracted_lead_fields` as the
    audit record of "what did we learn from this exchange?".
    """
    applied: dict[str, str] = {}

    if structured.lead_name and not lead.name:
        lead.name = structured.lead_name
        applied["name"] = structured.lead_name

    if structured.lead_email and not lead.email and _is_plausible_email(structured.lead_email):
        lead.email = structured.lead_email
        applied["email"] = structured.lead_email

    if structured.lead_phone and not lead.phone:
        lead.phone = structured.lead_phone
        applied["phone"] = structured.lead_phone

    for key, value in structured.extracted_lead_fields.items():
        if key not in qualification_keys or not value:
            continue
        if key in _DIRECT_LEAD_COLUMNS:
            if getattr(lead, key):
                continue
            setattr(lead, key, value)
        else:
            # Generic qualification fields (beyond the first-class lead columns)
            # accumulate as readable notes so nothing volunteered is lost.
            note_line = f"{key}: {value}"
            if lead.notes and note_line in lead.notes:
                continue
            lead.notes = f"{lead.notes}\n{note_line}" if lead.notes else note_line
        applied[key] = value

    if applied and lead.stage == "new":
        lead.stage = "contacted"

    return applied


def known_qualification_values(lead: Lead, qualification_keys: set[str]) -> dict[str, str]:
    """Surface what we already know about `lead` for the given qualification keys.

    Fed back into the agent's prompt so it never re-asks for data it has —
    the most common failure mode of naive "always ask the next question" bots.
    """
    known: dict[str, str] = {}
    for key in qualification_keys:
        if key in _DIRECT_LEAD_COLUMNS:
            value = getattr(lead, key, None)
        else:
            value = None
        if value:
            known[key] = value

    if lead.name:
        known.setdefault("name", lead.name)
    if lead.email:
        known.setdefault("email", lead.email)
    if lead.phone:
        known.setdefault("phone", lead.phone)

    return known
