from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings


class WhatsAppApiError(Exception):
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"WhatsApp Graph API error ({status_code}): {payload}")


def _retryable(exc: BaseException) -> bool:
    # Retry on transient network errors and 5xx — not on 4xx (bad request/auth/rate-limit
    # shape errors are not fixed by retrying immediately).
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, WhatsAppApiError) and exc.status_code >= 500


class WhatsAppClient:
    """Thin async wrapper over the Meta WhatsApp Cloud API (Graph API).

    One client is constructed per outbound call site, scoped to a specific
    connected number (``phone_number_id`` + that number's access token) — the
    org never shares a token across tenants.
    """

    def __init__(self, phone_number_id: str, access_token: str):
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._base_url = settings.whatsapp_graph_api_url

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, WhatsAppApiError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self._base_url}/{path}", json=json, headers=self._headers())

        if response.is_error:
            error = WhatsAppApiError(response.status_code, response.json() if response.content else None)
            if not _retryable(error):
                raise error
            raise error

        return response.json()

    # --- Outbound messages ----------------------------------------------------

    async def send_text_message(self, to: str, body: str) -> dict[str, Any]:
        return await self._post(
            f"{self._phone_number_id}/messages",
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"body": body, "preview_url": False},
            },
        )

    async def send_image_message(self, to: str, link: str, caption: str | None = None) -> dict[str, Any]:
        image: dict[str, Any] = {"link": link}
        if caption:
            image["caption"] = caption
        return await self._post(
            f"{self._phone_number_id}/messages",
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "image",
                "image": image,
            },
        )

    async def send_document_message(
        self, to: str, link: str, filename: str | None = None, caption: str | None = None
    ) -> dict[str, Any]:
        document: dict[str, Any] = {"link": link}
        if filename:
            document["filename"] = filename
        if caption:
            document["caption"] = caption
        return await self._post(
            f"{self._phone_number_id}/messages",
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "document",
                "document": document,
            },
        )

    # --- Inbound media retrieval ------------------------------------------------
    # Media sent *to* a business arrives as an opaque `media_id`; the binary must
    # be fetched in two hops: resolve the id to a short-lived CDN URL, then
    # download the bytes (both calls require the bearer token).

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, WhatsAppApiError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def get_media_url(self, media_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self._base_url}/{media_id}", headers=self._headers())
        if response.is_error:
            raise WhatsAppApiError(response.status_code, response.json() if response.content else None)
        return response.json()

    async def download_media(self, media_url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(media_url, headers=self._headers())
        if response.is_error:
            raise WhatsAppApiError(response.status_code, None)
        return response.content
