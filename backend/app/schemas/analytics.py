from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AnalyticsPeriod = Literal["today", "7d", "30d"]


class AnalyticsVisitIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)

    @field_validator("path")
    @classmethod
    def same_site_path(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/") or value.startswith("//"):
            raise ValueError("path must be a same-site absolute path")
        return value


class AnalyticsProductViewIn(BaseModel):
    product_id: int = Field(gt=0)


class AnalyticsLocationOut(BaseModel):
    name: str
    sessions: int


class AnalyticsProductOut(BaseModel):
    product_id: int
    name: str
    slug: str
    views: int
    product_exists: bool


class AnalyticsSummaryOut(BaseModel):
    period: AnalyticsPeriod
    range_start: datetime
    range_end: datetime
    location_tracking_configured: bool
    sessions: int
    unique_visitors: int
    top_locations: list[AnalyticsLocationOut]
    top_products: list[AnalyticsProductOut]
