import uuid

import httpx

from app.core.config import settings

_INBOUND_MEDIA_BUCKET = "whatsapp-media"


async def upload_inbound_media(content: bytes, mime_type: str | None, filename: str | None) -> str:
    """Re-host inbound WhatsApp media in Supabase Storage and return a stable URL.

    Meta's media URLs are short-lived (minutes) and require a bearer token to
    fetch — neither is acceptable for a chat history users revisit later, so we
    persist the bytes ourselves immediately on receipt.
    """
    object_path = f"{uuid.uuid4()}/{filename or 'file'}"
    upload_url = f"{settings.supabase_url}/storage/v1/object/{_INBOUND_MEDIA_BUCKET}/{object_path}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            upload_url,
            content=content,
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": mime_type or "application/octet-stream",
                "x-upsert": "false",
            },
        )
    response.raise_for_status()

    return f"{settings.supabase_url}/storage/v1/object/public/{_INBOUND_MEDIA_BUCKET}/{object_path}"
