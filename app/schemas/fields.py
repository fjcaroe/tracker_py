from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field as PydanticField, constr


class LatLon(BaseModel):
    lat: float
    lon: float


class FieldCreate(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)
    cost_center_id: Optional[int] = None
    color: Optional[str] = None
    polygon: List[LatLon]


class FieldUpdate(BaseModel):
    name: Optional[constr(strip_whitespace=True, min_length=1)] = None
    cost_center_id: Optional[int] = None
    color: Optional[str] = None
    polygon: Optional[List[LatLon]] = None


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cost_center_id: Optional[int]
    cost_center_name: Optional[str]
    color: Optional[str]
    polygon: List[LatLon]
    created_at: datetime
