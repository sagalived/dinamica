from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class McByBuildingRowDTO(BaseModel):
    building_id: str
    building_name: str
    receita_operacional: float = 0.0
    mc: float = 0.0
    mc_percent: float = 0.0


class McByBuildingTotalDTO(BaseModel):
    receita_operacional: float = 0.0
    mc: float = 0.0
    mc_percent: float = 0.0


class McByBuildingResponseDTO(BaseModel):
    rows: list[McByBuildingRowDTO] = Field(default_factory=list)
    total: McByBuildingTotalDTO = Field(default_factory=McByBuildingTotalDTO)
    filters: dict[str, Any] = Field(default_factory=dict)
    diagnostic: dict[str, Any] | None = None
