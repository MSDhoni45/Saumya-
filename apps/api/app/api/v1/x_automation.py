"""X (Twitter) Automation API endpoints.

Routes:
  /x/{business_id}/accounts         — connect & list X accounts
  /x/{business_id}/posts            — CRUD for scheduled/draft posts
  /x/{business_id}/searches         — keyword search configs for lead finding
  /x/{business_id}/outreach         — view & update discovered X leads
  /x/{business_id}/outreach/{id}/send — push the outreach message as a reply
  /x/{business_id}/content-ideas    — AI-generated tweet ideas
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, require_business_access
from app.db.session import get_db_session
from app.models.x_automation import XAccount, XLeadSearch, XOutreach, XPost
from app.schemas.x_automation import (
    ContentIdeasRequest,
    ContentIdeaResponse,
    PaginatedXOutreach,
    PaginatedXPosts,
    XAccountConnectRequest,
    XAccountResponse,
    XLeadSearchCreateRequest,
    XLeadSearchResponse,
    XOutreachResponse,
    XOutreachUpdateRequest,
    XPostCreateRequest,
    XPostResponse,
)
from app.services.encryption import decrypt_secret, encrypt_secret
from app.services.x_client import XApiError, XUserClient
from app.services.x_outreach_service import generate_content_ideas

router = APIRouter(prefix="/x", tags=["x-automation"])

_DEFAULT_PAGE = 25
_MAX_PAGE = 100


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


@router.post("/{business_id}/accounts", response_model=XAccountResponse, status_code=status.HTTP_201_CREATED)
async def connect_x_account(
    business_id: uuid.UUID,
    payload: XAccountConnectRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> XAccountResponse:
    """Connect an X account by storing its OAuth 2.0 tokens (encrypted at rest)."""
    require_business_access(ctx, business_id)

    account = XAccount(
        business_id=business_id,
        x_user_id=payload.x_user_id,
        username=payload.username,
        display_name=payload.display_name,
        access_token=encrypt_secret(payload.access_token),
        refresh_token=encrypt_secret(payload.refresh_token) if payload.refresh_token else None,
        token_expires_at=payload.token_expires_at,
        is_active=True,
    )
    session.add(account)
    await session.flush()
    await session.refresh(account)
    return XAccountResponse.model_validate(account)


@router.get("/{business_id}/accounts", response_model=list[XAccountResponse])
async def list_x_accounts(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[XAccountResponse]:
    require_business_access(ctx, business_id)
    stmt = select(XAccount).where(XAccount.business_id == business_id).order_by(XAccount.created_at.asc())
    accounts = list((await session.execute(stmt)).scalars().all())
    return [XAccountResponse.model_validate(a) for a in accounts]


@router.delete("/{business_id}/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_x_account(
    business_id: uuid.UUID,
    account_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    require_business_access(ctx, business_id)
    account = await _get_account_or_404(session, business_id, account_id)
    await session.delete(account)


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------


@router.get("/{business_id}/posts", response_model=PaginatedXPosts)
async def list_x_posts(
    business_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(_DEFAULT_PAGE, ge=1, le=_MAX_PAGE),
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedXPosts:
    require_business_access(ctx, business_id)
    stmt = select(XPost).where(XPost.business_id == business_id)
    if status_filter:
        stmt = stmt.where(XPost.status == status_filter)
    stmt = stmt.order_by(XPost.created_at.desc())

    total: int = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    posts = list((await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all())
    return PaginatedXPosts(
        items=[XPostResponse.model_validate(p) for p in posts],
        total=total, page=page, page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/{business_id}/posts", response_model=XPostResponse, status_code=status.HTTP_201_CREATED)
async def create_x_post(
    business_id: uuid.UUID,
    payload: XPostCreateRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> XPostResponse:
    require_business_access(ctx, business_id)
    await _get_account_or_404(session, business_id, payload.x_account_id)

    post_status = "scheduled" if payload.scheduled_at else "draft"
    thread = [t.model_dump() for t in payload.thread_tweets]

    post = XPost(
        business_id=business_id,
        x_account_id=payload.x_account_id,
        content=payload.content,
        thread_tweets=thread,
        status=post_status,
        scheduled_at=payload.scheduled_at,
    )
    session.add(post)
    await session.flush()
    await session.refresh(post)
    return XPostResponse.model_validate(post)


@router.post("/{business_id}/posts/{post_id}/publish", response_model=XPostResponse)
async def publish_x_post_now(
    business_id: uuid.UUID,
    post_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> XPostResponse:
    """Immediately publish a draft post (bypasses the scheduler)."""
    require_business_access(ctx, business_id)
    post = await _get_post_or_404(session, business_id, post_id)
    if post.status == "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Post already published")

    account = await _get_account_or_404(session, business_id, post.x_account_id)
    access_token = decrypt_secret(account.access_token)
    client = XUserClient(access_token=access_token)
    now = datetime.now(tz=timezone.utc)

    try:
        thread = post.thread_tweets
        if thread and len(thread) > 1:
            texts = [t["text"] for t in thread if t.get("text")]
            results = await client.post_thread(texts)
            post.tweet_ids = [r["data"]["id"] for r in results]
        else:
            result = await client.post_tweet(post.content)
            post.tweet_ids = [result["data"]["id"]]
    except XApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"X API error: {exc.status_code}") from exc

    post.status = "posted"
    post.posted_at = now
    post.updated_at = now
    await session.flush()
    await session.refresh(post)
    return XPostResponse.model_validate(post)


@router.delete("/{business_id}/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_x_post(
    business_id: uuid.UUID,
    post_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    require_business_access(ctx, business_id)
    post = await _get_post_or_404(session, business_id, post_id)
    if post.status == "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot delete a published post")
    await session.delete(post)


# ---------------------------------------------------------------------------
# Lead searches
# ---------------------------------------------------------------------------


@router.get("/{business_id}/searches", response_model=list[XLeadSearchResponse])
async def list_lead_searches(
    business_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[XLeadSearchResponse]:
    require_business_access(ctx, business_id)
    stmt = select(XLeadSearch).where(XLeadSearch.business_id == business_id)
    rows = list((await session.execute(stmt)).scalars().all())
    return [XLeadSearchResponse.model_validate(r) for r in rows]


@router.post("/{business_id}/searches", response_model=XLeadSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_search(
    business_id: uuid.UUID,
    payload: XLeadSearchCreateRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> XLeadSearchResponse:
    require_business_access(ctx, business_id)
    search = XLeadSearch(
        business_id=business_id,
        name=payload.name,
        keywords=payload.keywords,
        exclude_keywords=payload.exclude_keywords,
        min_followers=payload.min_followers,
        language=payload.language,
        is_active=True,
    )
    session.add(search)
    await session.flush()
    await session.refresh(search)
    return XLeadSearchResponse.model_validate(search)


@router.post("/{business_id}/searches/{search_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_lead_scan(
    business_id: uuid.UUID,
    search_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Enqueue an immediate X lead scan for this search config."""
    require_business_access(ctx, business_id)
    search = await session.get(XLeadSearch, search_id)
    if search is None or search.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Search config not found")
    if not search.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Search is inactive")

    from app.workers.tasks.x_tasks import run_x_lead_scan
    run_x_lead_scan.delay(search_id=str(search_id))

    return {"queued": True, "search_id": str(search_id)}


@router.delete("/{business_id}/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead_search(
    business_id: uuid.UUID,
    search_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    require_business_access(ctx, business_id)
    search = await session.get(XLeadSearch, search_id)
    if search is None or search.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Search config not found")
    await session.delete(search)


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------


@router.get("/{business_id}/outreach", response_model=PaginatedXOutreach)
async def list_outreach(
    business_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status"),
    min_score: int | None = Query(None, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(_DEFAULT_PAGE, ge=1, le=_MAX_PAGE),
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedXOutreach:
    require_business_access(ctx, business_id)
    stmt = select(XOutreach).where(XOutreach.business_id == business_id)
    if status_filter:
        stmt = stmt.where(XOutreach.status == status_filter)
    if min_score is not None:
        stmt = stmt.where(XOutreach.ai_score >= min_score)
    stmt = stmt.order_by(XOutreach.ai_score.desc().nulls_last(), XOutreach.created_at.desc())

    total: int = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = list((await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all())
    return PaginatedXOutreach(
        items=[XOutreachResponse.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.patch("/{business_id}/outreach/{outreach_id}", response_model=XOutreachResponse)
async def update_outreach(
    business_id: uuid.UUID,
    outreach_id: uuid.UUID,
    payload: XOutreachUpdateRequest,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> XOutreachResponse:
    """Edit the outreach message or mark it as skipped/reviewed before sending."""
    require_business_access(ctx, business_id)
    outreach = await _get_outreach_or_404(session, business_id, outreach_id)
    if payload.status is not None:
        outreach.status = payload.status
    if payload.outreach_message is not None:
        outreach.outreach_message = payload.outreach_message
    outreach.updated_at = datetime.now(tz=timezone.utc)
    await session.flush()
    await session.refresh(outreach)
    return XOutreachResponse.model_validate(outreach)


@router.post("/{business_id}/outreach/{outreach_id}/send", response_model=XOutreachResponse)
async def send_outreach_reply(
    business_id: uuid.UUID,
    outreach_id: uuid.UUID,
    account_id: uuid.UUID = Query(..., description="X account to reply from"),
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> XOutreachResponse:
    """Post the outreach message as a public reply to the prospect's tweet."""
    require_business_access(ctx, business_id)
    outreach = await _get_outreach_or_404(session, business_id, outreach_id)

    if outreach.status == "sent":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Outreach already sent")
    if not outreach.outreach_message:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No outreach message to send")
    if not outreach.tweet_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No tweet ID — cannot reply")

    account = await _get_account_or_404(session, business_id, account_id)
    access_token = decrypt_secret(account.access_token)
    client = XUserClient(access_token=access_token)

    try:
        await client.post_tweet(outreach.outreach_message, reply_to_id=outreach.tweet_id)
    except XApiError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"X API error: {exc.status_code}") from exc

    now = datetime.now(tz=timezone.utc)
    outreach.status = "sent"
    outreach.sent_at = now
    outreach.x_account_id = account.id
    outreach.updated_at = now
    await session.flush()
    await session.refresh(outreach)
    return XOutreachResponse.model_validate(outreach)


# ---------------------------------------------------------------------------
# Content ideas
# ---------------------------------------------------------------------------


@router.post("/{business_id}/content-ideas", response_model=list[ContentIdeaResponse])
async def get_content_ideas(
    business_id: uuid.UUID,
    payload: ContentIdeasRequest,
    ctx: BusinessContext = Depends(get_current_business),
) -> list[ContentIdeaResponse]:
    """Generate AI-powered tweet/thread ideas for Influnexus content marketing."""
    require_business_access(ctx, business_id)
    ideas = await generate_content_ideas(
        business_name=payload.business_name,
        services=payload.services,
        count=payload.count,
    )
    return [ContentIdeaResponse(**idea) for idea in ideas if isinstance(idea, dict)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_account_or_404(session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID) -> XAccount:
    account = await session.get(XAccount, account_id)
    if account is None or account.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="X account not found")
    return account


async def _get_post_or_404(session: AsyncSession, business_id: uuid.UUID, post_id: uuid.UUID) -> XPost:
    post = await session.get(XPost, post_id)
    if post is None or post.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


async def _get_outreach_or_404(session: AsyncSession, business_id: uuid.UUID, outreach_id: uuid.UUID) -> XOutreach:
    outreach = await session.get(XOutreach, outreach_id)
    if outreach is None or outreach.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Outreach item not found")
    return outreach
