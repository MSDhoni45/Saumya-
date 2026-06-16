"""Thin async wrapper over the X (Twitter) API v2.

Mirrors the WhatsAppClient pattern: one client per call site, scoped to a
specific user's access token. App-only bearer token is used for read-only
search; user tokens are required for posting and DMs.
"""

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

_BASE_URL = "https://api.twitter.com/2"
_MAX_TWEET_LEN = 280


class XApiError(Exception):
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"X API error ({status_code}): {payload}")


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, XApiError) and exc.status_code >= 500


class XAppClient:
    """App-only bearer token client — read operations (search, user lookup)."""

    def __init__(self):
        self._bearer = settings.x_bearer_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._bearer}"}

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, XApiError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{_BASE_URL}/{path}", params=params, headers=self._headers())
        if response.is_error:
            raise XApiError(response.status_code, response.json() if response.content else None)
        return response.json()

    async def search_recent(
        self,
        query: str,
        max_results: int = 10,
        tweet_fields: list[str] | None = None,
        user_fields: list[str] | None = None,
        expansions: list[str] | None = None,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        """Search recent tweets (last 7 days). Requires Basic or higher API tier."""
        params: dict[str, Any] = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": ",".join(tweet_fields or ["author_id", "created_at", "text", "public_metrics"]),
            "user.fields": ",".join(user_fields or ["name", "username", "description", "public_metrics"]),
            "expansions": ",".join(expansions or ["author_id"]),
        }
        if next_token:
            params["next_token"] = next_token
        return await self._get("tweets/search/recent", params=params)

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        return await self._get(
            f"users/by/username/{username}",
            params={"user.fields": "description,public_metrics,profile_image_url,url"},
        )

    async def get_user_by_id(self, user_id: str) -> dict[str, Any]:
        return await self._get(
            f"users/{user_id}",
            params={"user.fields": "description,public_metrics,profile_image_url,url"},
        )


class XUserClient:
    """OAuth 2.0 user-token client — write operations (post, DM)."""

    def __init__(self, access_token: str):
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, XApiError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{_BASE_URL}/{path}", json=json, headers=self._headers())
        if response.is_error:
            raise XApiError(response.status_code, response.json() if response.content else None)
        return response.json()

    async def post_tweet(self, text: str, reply_to_id: str | None = None) -> dict[str, Any]:
        """Post a single tweet. Returns the created tweet object."""
        payload: dict[str, Any] = {"text": text[:_MAX_TWEET_LEN]}
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
        return await self._post("tweets", payload)

    async def post_thread(self, tweets: list[str]) -> list[dict[str, Any]]:
        """Post a sequence of tweets as a thread. Returns list of created tweet objects."""
        results: list[dict[str, Any]] = []
        previous_id: str | None = None
        for text in tweets:
            result = await self.post_tweet(text, reply_to_id=previous_id)
            results.append(result)
            previous_id = result["data"]["id"]
        return results

    async def send_dm(self, participant_id: str, text: str) -> dict[str, Any]:
        """Send a direct message to a user (requires DM permissions)."""
        return await self._post(
            f"dm_conversations/with/{participant_id}/messages",
            {"text": text, "event_type": "MessageCreate"},
        )

    async def get_me(self) -> dict[str, Any]:
        """Fetch the authenticated user's profile (validates token health)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_BASE_URL}/users/me",
                params={"user.fields": "description,public_metrics"},
                headers=self._headers(),
            )
        if response.is_error:
            raise XApiError(response.status_code, response.json() if response.content else None)
        return response.json()
