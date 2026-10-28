from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_shop_owner
from app.config import get_settings
from app.database import get_db
from app.schemas import Dashboard
from app.services import dashboard as service
from app.time_utils import utc_now

router = APIRouter(
    prefix="/shops/{shop_id}", tags=["dashboard"], dependencies=[Depends(require_shop_owner)]
)
DB = Annotated[Session, Depends(get_db)]


@router.get("/dashboard", response_model=Dashboard)
def get_dashboard(
    shop_id: int,
    db: DB,
    overdue_days: Annotated[
        int, Query(ge=1, le=365, description="Baki older than this many days is overdue")
    ] = 30,
):
    return service.get_dashboard(
        db, shop_id, now=utc_now(), local_tz=get_settings().tz, overdue_days=overdue_days
    )
