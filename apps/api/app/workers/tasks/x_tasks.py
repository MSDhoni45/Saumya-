"""Celery tasks for X (Twitter) automation.

Three scheduled/on-demand tasks:
  1. run_x_lead_scan   — searches X for prospects matching active search configs
  2. post_scheduled_x  — posts any tweets/threads whose scheduled_at has passed
  3. refresh_x_tokens  — refreshes expiring OAuth 2.0 user tokens
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.agent import Lead
from app.models.x_automation import XAccount, XLeadSearch, XOutreach, XPost
from app.services.encryption import decrypt_secret, encrypt_secret
from app.services.x_client import XApiError, XAppClient, XUserClient
from app.services.x_outreach_service import score_and_draft_outreach
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


# ---------------------------------------------------------------------------
# Task 1: Lead scan
# ---------------------------------------------------------------------------


@celery_app.task(name="x.run_lead_scan", bind=True, max_retries=2, default_retry_delay=30)
def run_x_lead_scan(self, *, search_id: str) -> None:
    """Search X for prospects matching the given XLeadSearch config.

    For every returned tweet author:
      - skip if already in x_outreach for this business (UNIQUE constraint)
      - score the profile with the AI
      - store an XOutreach row (status='pending')
      - if score >= 60, also create a Lead in the CRM
    """
    try:
        _get_worker_loop().run_until_complete(_run_lead_scan(uuid.UUID(search_id)))
    except Exception as exc:
        logger.exception("X lead scan failed for search_id=%s", search_id)
        raise self.retry(exc=exc) from exc


async def _run_lead_scan(search_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        try:
            await _do_lead_scan(session, search_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _do_lead_scan(session: AsyncSession, search_id: uuid.UUID) -> None:
    search = await session.get(XLeadSearch, search_id)
    if search is None or not search.is_active:
        logger.info("X lead search %s not found or inactive — skipping", search_id)
        return

    query = _build_search_query(search)
    client = XAppClient()

    try:
        results = await client.search_recent(query=query, max_results=25)
    except XApiError as exc:
        logger.error("X search API error for search_id=%s: %s", search_id, exc)
        return

    tweets = results.get("data", [])
    users_by_id: dict[str, dict] = {
        u["id"]: u for u in results.get("includes", {}).get("users", [])
    }

    for tweet in tweets:
        author_id = tweet.get("author_id", "")
        user = users_by_id.get(author_id, {})
        if not user:
            continue

        username = user.get("username", "")
        tweet_id = tweet.get("id", "")

        # Skip duplicates (UNIQUE on business_id + x_user_id + tweet_id)
        existing = await session.scalar(
            select(XOutreach).where(
                XOutreach.business_id == search.business_id,
                XOutreach.x_user_id == author_id,
                XOutreach.tweet_id == tweet_id,
            )
        )
        if existing:
            continue

        public_metrics = user.get("public_metrics", {})
        followers = public_metrics.get("followers_count", 0)

        if followers < search.min_followers:
            continue

        scoring = await score_and_draft_outreach(
            username=username,
            display_name=user.get("name"),
            bio=user.get("description"),
            followers=followers,
            following=public_metrics.get("following_count"),
            tweet_text=tweet.get("text", ""),
        )

        lead_id: uuid.UUID | None = None
        if scoring["score"] >= 60:
            lead = Lead(
                business_id=search.business_id,
                name=user.get("name"),
                stage="new",
                source="x_twitter",
                notes=f"@{username} — {scoring['reason']}\n\nTweet: {tweet.get('text', '')}",
            )
            session.add(lead)
            await session.flush()
            lead_id = lead.id

        outreach = XOutreach(
            business_id=search.business_id,
            lead_id=lead_id,
            search_id=search_id,
            x_user_id=author_id,
            username=username,
            display_name=user.get("name"),
            profile_bio=user.get("description"),
            followers_count=followers,
            following_count=public_metrics.get("following_count"),
            tweet_text=tweet.get("text"),
            tweet_id=tweet_id,
            ai_score=scoring["score"],
            ai_score_reason=scoring["reason"],
            outreach_message=scoring["outreach_message"],
            status="pending",
        )
        session.add(outreach)

    search.last_run_at = datetime.now(tz=timezone.utc)
    logger.info(
        "X lead scan complete for search_id=%s — processed %d tweets",
        search_id,
        len(tweets),
    )


def _build_search_query(search: XLeadSearch) -> str:
    """Compose an X v2 search query from the config's keyword lists."""
    include = " OR ".join(f'"{kw}"' if " " in kw else kw for kw in search.keywords)
    base = f"({include})"
    if search.exclude_keywords:
        excludes = " ".join(f'-"{kw}"' if " " in kw else f"-{kw}" for kw in search.exclude_keywords)
        base = f"{base} {excludes}"
    base += f" lang:{search.language} -is:retweet -is:reply is:verified_or_low_verification"
    return base


# ---------------------------------------------------------------------------
# Task 2: Post scheduled tweets/threads
# ---------------------------------------------------------------------------


@celery_app.task(name="x.post_scheduled", bind=True, max_retries=3, default_retry_delay=60)
def post_scheduled_x_content(self) -> None:
    """Post all x_posts rows with status='scheduled' whose scheduled_at is past."""
    try:
        _get_worker_loop().run_until_complete(_post_scheduled())
    except Exception as exc:
        logger.exception("Scheduled X posting task failed")
        raise self.retry(exc=exc) from exc


async def _post_scheduled() -> None:
    async with async_session_factory() as session:
        now = datetime.now(tz=timezone.utc)
        stmt = (
            select(XPost)
            .where(XPost.status == "scheduled", XPost.scheduled_at <= now)
            .order_by(XPost.scheduled_at.asc())
            .limit(20)
        )
        posts = list((await session.execute(stmt)).scalars().all())

        for post in posts:
            try:
                await _send_post(session, post)
                await session.commit()
            except Exception:
                await session.rollback()
                post.status = "failed"
                post.error_message = "Failed during posting — see worker logs"
                post.updated_at = datetime.now(tz=timezone.utc)
                await session.commit()
                logger.exception("Failed to post XPost id=%s", post.id)


async def _send_post(session: AsyncSession, post: XPost) -> None:
    account = await session.get(XAccount, post.x_account_id)
    if account is None or not account.is_active:
        post.status = "failed"
        post.error_message = "X account not found or inactive"
        post.updated_at = datetime.now(tz=timezone.utc)
        return

    access_token = decrypt_secret(account.access_token)
    client = XUserClient(access_token=access_token)

    now = datetime.now(tz=timezone.utc)

    thread = post.thread_tweets  # list of {"text": "..."} dicts
    if thread and len(thread) > 1:
        texts = [t["text"] for t in thread if t.get("text")]
        results = await client.post_thread(texts)
        post.tweet_ids = [r["data"]["id"] for r in results]
    else:
        result = await client.post_tweet(post.content)
        post.tweet_ids = [result["data"]["id"]]

    post.status = "posted"
    post.posted_at = now
    post.updated_at = now
    logger.info("Posted XPost id=%s tweet_ids=%s", post.id, post.tweet_ids)


# ---------------------------------------------------------------------------
# Task 3: Refresh expiring OAuth tokens
# ---------------------------------------------------------------------------


@celery_app.task(name="x.refresh_tokens", bind=True, max_retries=2, default_retry_delay=60)
def refresh_x_tokens(self) -> None:
    """Refresh X OAuth 2.0 user tokens that are about to expire (within 1 hour)."""
    try:
        _get_worker_loop().run_until_complete(_refresh_tokens())
    except Exception as exc:
        logger.exception("X token refresh task failed")
        raise self.retry(exc=exc) from exc


async def _refresh_tokens() -> None:
    from app.core.config import settings

    async with async_session_factory() as session:
        now = datetime.now(tz=timezone.utc)
        stmt = select(XAccount).where(
            XAccount.is_active.is_(True),
            XAccount.refresh_token.isnot(None),
            XAccount.token_expires_at.isnot(None),
        )
        accounts = list((await session.execute(stmt)).scalars().all())

        for account in accounts:
            if account.token_expires_at is None:
                continue
            seconds_left = (account.token_expires_at - now).total_seconds()
            if seconds_left > 3600:
                continue

            try:
                from datetime import timedelta

                from app.services.x_oauth import refresh_access_token

                raw_refresh = decrypt_secret(account.refresh_token)  # type: ignore[arg-type]
                token_data = await refresh_access_token(raw_refresh)

                account.access_token = encrypt_secret(token_data["access_token"])
                if token_data.get("refresh_token"):
                    account.refresh_token = encrypt_secret(token_data["refresh_token"])
                expires_in = token_data.get("expires_in", 7200)
                account.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
                account.updated_at = datetime.now(tz=timezone.utc)
                await session.commit()
                logger.info("Refreshed X token for account @%s", account.username)
            except Exception:
                await session.rollback()
                logger.exception("Failed to refresh X token for account @%s", account.username)
