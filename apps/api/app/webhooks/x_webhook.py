"""X (Twitter) Account Activity API webhook.

Two responsibilities:
  GET  /webhooks/x  — CRC challenge (X verifies ownership every 90 days)
  POST /webhooks/x  — Real-time event delivery (DM replies, mentions)

X signs POST payloads with HMAC-SHA256 using the consumer secret (our
x_client_secret).  We verify the signature before processing.

DM reply flow:
  1. Prospect replies to our outreach DM.
  2. X delivers a `direct_message_events` payload here.
  3. We match the sender_id to an XOutreach row with status 'dm_sent'.
  4. We store reply_text + replied_at and flip status to 'replied'.
"""

import base64
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.x_automation import XOutreach

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/x", tags=["webhooks"])


def _compute_crc_response(crc_token: str) -> str:
    """HMAC-SHA256 of crc_token signed with x_client_secret, base64-encoded."""
    secret = (settings.x_client_secret or "").encode("utf-8")
    digest = hmac.new(secret, crc_token.encode("utf-8"), hashlib.sha256).digest()
    return "sha256=" + base64.b64encode(digest).decode()


def _verify_signature(body: bytes, x_twitter_webhooks_signature: str) -> bool:
    """Return True if the X-Twitter-Webhooks-Signature header matches the body."""
    secret = (settings.x_client_secret or "").encode("utf-8")
    expected = "sha256=" + base64.b64encode(
        hmac.new(secret, body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, x_twitter_webhooks_signature)


@router.get("")
async def x_crc_challenge(
    crc_token: str = Query(...),
) -> dict[str, str]:
    """X calls this GET with ?crc_token=... every ~90 days to verify webhook ownership."""
    if not settings.x_client_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="X not configured")
    return {"response_token": _compute_crc_response(crc_token)}


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def x_activity_event(
    request: Request,
    x_twitter_webhooks_signature: str | None = Header(None),
) -> Response:
    """Receive X Account Activity events — DM replies, mentions, follows."""
    if not settings.x_client_secret:
        # Webhook not configured — return 200 so X doesn't disable the endpoint.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    body = await request.body()

    if x_twitter_webhooks_signature:
        if not _verify_signature(body, x_twitter_webhooks_signature):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload: dict = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    dm_events: list[dict] = payload.get("direct_message_events", [])
    if dm_events:
        await _process_dm_replies(dm_events)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _process_dm_replies(events: list[dict]) -> None:
    """For each incoming DM, check if it's a reply from a prospect we DM'd."""
    from datetime import datetime, timezone

    async with async_session_factory() as session:
        for event in events:
            if event.get("type") != "message_create":
                continue

            msg_create = event.get("message_create", {})
            sender_id: str = msg_create.get("sender_id", "")
            text: str = msg_create.get("message_data", {}).get("text", "")
            created_ts = event.get("created_timestamp")

            if not sender_id or not text:
                continue

            # Find the most recent dm_sent outreach for this prospect
            outreach = await session.scalar(
                select(XOutreach)
                .where(
                    XOutreach.x_user_id == sender_id,
                    XOutreach.status == "dm_sent",
                    XOutreach.reply_text.is_(None),
                )
                .order_by(XOutreach.dm_sent_at.desc().nulls_last())
                .limit(1)
            )

            if outreach is None:
                continue

            try:
                replied_at = (
                    datetime.fromtimestamp(int(created_ts) / 1000, tz=timezone.utc)
                    if created_ts
                    else datetime.now(tz=timezone.utc)
                )
            except (TypeError, ValueError):
                replied_at = datetime.now(tz=timezone.utc)

            outreach.reply_text = text
            outreach.replied_at = replied_at
            outreach.status = "replied"
            outreach.updated_at = datetime.now(tz=timezone.utc)
            logger.info(
                "X DM reply captured: outreach_id=%s sender=@%s",
                outreach.id,
                outreach.username,
            )

        try:
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to store X DM reply events")
