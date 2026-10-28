from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import require_shop_owner
from app.config import get_settings
from app.database import get_db
from app.services.export import khata_csv
from app.time_utils import utc_now

router = APIRouter(
    prefix="/shops/{shop_id}", tags=["privacy"], dependencies=[Depends(require_shop_owner)]
)
DB = Annotated[Session, Depends(get_db)]


@router.get("/export.csv", response_class=Response)
def export_khata(shop_id: int, db: DB):
    """The full khata as CSV (UTF-8 with BOM, opens in Excel with Bangla intact)."""
    settings = get_settings()
    day = utc_now().astimezone(settings.tz).date().isoformat()
    return Response(
        content=khata_csv(db, shop_id, settings.tz).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="baki-khata-{day}.csv"',
            "Cache-Control": "no-store",
        },
    )
