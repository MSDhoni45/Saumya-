import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.whatsapp import Business
from app.schemas.business import BusinessResponse, BusinessUpdateRequest

router = APIRouter(prefix="/business", tags=["business"])


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Business:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return business


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: uuid.UUID,
    payload: BusinessUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Business:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(business, field, value)
    business.updated_at = datetime.now(tz=timezone.utc)

    await session.flush()
    await session.refresh(business)
    return business
