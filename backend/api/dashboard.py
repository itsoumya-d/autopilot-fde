from fastapi import APIRouter

from .. import database
from ..models.schema import DashboardSummary

router = APIRouter()


@router.get("/", response_model=DashboardSummary)
async def get_dashboard() -> DashboardSummary:
    return await database.dashboard_summary()
