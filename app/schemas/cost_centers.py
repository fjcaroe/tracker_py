from typing import Optional
from pydantic import BaseModel, ConfigDict


class CostCenterCreate(BaseModel):
    name: str
    external_id: Optional[str] = None
    hectares: Optional[float] = None


class CostCenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    external_id: Optional[str] = None
    hectares: Optional[float] = None
