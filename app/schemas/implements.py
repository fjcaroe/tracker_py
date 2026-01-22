from datetime import datetime
from pydantic import BaseModel, ConfigDict, constr


class ImplementCreate(BaseModel):
    name: constr(strip_whitespace=True, min_length=1)


class ImplementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
