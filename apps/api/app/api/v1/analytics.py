from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, require_business_access
from app.db.session import get_db_session
from app.schemas.analytics import AnalyticsOverview
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/{business_id}/overview", response_model=AnalyticsOverview)
async def get_overview(
    business_id: uuid.UUID,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsOverview:
    require_business_access(ctx, business_id)
    return await analytics_service.get_overview(session, business_id=business_id, days=days)
