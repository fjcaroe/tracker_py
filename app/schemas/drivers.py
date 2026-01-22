from typing import Optional
from pydantic import BaseModel, ConfigDict


class DriverCreate(BaseModel):
    name: str
    rut: Optional[str] = None


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rut: Optional[str]
