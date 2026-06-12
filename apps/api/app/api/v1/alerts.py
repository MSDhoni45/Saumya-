import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import BusinessContext, get_current_business, require_business_access
from app.db.session import get_db_session
from app.schemas.alerts import OperatorAlertResponse
from app.services import operator_alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/{business_id}", response_model=list[OperatorAlertResponse])
async def list_operator_alerts(
    business_id: uuid.UUID,
    unack_only: bool = Query(False, description="Only return alerts that have not been acknowledged"),
    limit: int = Query(100, ge=1, le=500),
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> list[OperatorAlertResponse]:
    require_business_access(ctx, business_id)
    alerts = await operator_alert_service.list_alerts(
        session, business_id=business_id, unack_only=unack_only, limit=limit
    )
    return [OperatorAlertResponse.model_validate(a) for a in alerts]


@router.post("/{business_id}/{alert_id}/ack", response_model=OperatorAlertResponse)
async def acknowledge_operator_alert(
    business_id: uuid.UUID,
    alert_id: uuid.UUID,
    ctx: BusinessContext = Depends(get_current_business),
    session: AsyncSession = Depends(get_db_session),
) -> OperatorAlertResponse:
    require_business_access(ctx, business_id)
    alert = await operator_alert_service.acknowledge_alert(
        session, business_id=business_id, alert_id=alert_id, user_id=ctx.user_id
    )
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return OperatorAlertResponse.model_validate(alert)
