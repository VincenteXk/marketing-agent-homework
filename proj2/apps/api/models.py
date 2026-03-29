from __future__ import annotations

from pydantic import BaseModel, Field


class PromotionRequest(BaseModel):
    product: str = Field(..., min_length=1, description="产品描述")
    goal: str = Field(..., min_length=1, description="推广目标")
    budget: str = Field("", description="总预算")
    channels: str = Field("", description="渠道")
