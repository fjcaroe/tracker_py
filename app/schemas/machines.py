from typing import Optional
from pydantic import BaseModel, ConfigDict


class MachineCreate(BaseModel):
    external_id: str | None = None
    name: str
    plate: str | None = None
    description: str | None = None
    cost_center_id: int | None = None
    tank_capacity_liters: float | None = None
    fuel_consumption_lph: float | None = None
    fuel_consumption_lpkm: float | None = None
    default_activity_id: int | None = None
    default_labor_id: int | None = None


class MachineUpdate(BaseModel):
    external_id: str | None = None
    name: str | None = None
    plate: str | None = None
    description: str | None = None
    cost_center_id: int | None = None
    tank_capacity_liters: float | None = None
    fuel_consumption_lph: float | None = None
    fuel_consumption_lpkm: float | None = None
    default_activity_id: int | None = None
    default_labor_id: int | None = None


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None = None
    name: str
    plate: str | None = None
    description: str | None = None
    cost_center_id: int | None = None
    tank_capacity_liters: float | None = None
    fuel_consumption_lph: float | None = None
    fuel_consumption_lpkm: float | None = None
    default_activity_id: int | None = None
    default_labor_id: int | None = None


class FuelStatusOut(BaseModel):
    machine_id: int
    tank_capacity_liters: float | None = None
    last_liters: float | None = None
    last_work_order_id: int | None = None
    as_of: Optional[str] = None


class MachineOdometerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_distance_m: float
    total_sessions: int
    last_session_at: Optional[str] = None
