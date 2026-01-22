from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.work_orders import WorkOrder
from app.models.implements import Implement
from app.schemas.work_orders import WorkOrderCreate, WorkOrderOut, WorkOrderUpdate

router = APIRouter(prefix="", tags=["work_orders"])


@router.post("/work_orders", response_model=WorkOrderOut)
def create_work_order(payload: WorkOrderCreate, db: Session = Depends(get_db)):
    if payload.implement_id is not None:
        imp = db.query(Implement).get(payload.implement_id)
        if not imp:
            raise HTTPException(status_code=404, detail="Implement not found")

    wo = WorkOrder(
        code=payload.code,
        work_date=payload.work_date,
        season=payload.season,
        activity_id=payload.activity_id,
        labor_id=payload.labor_id,
        cost_center_id=payload.cost_center_id,
        field_id=payload.field_id,
        machine_id=payload.machine_id,
        notes=payload.notes,

        implement_id=payload.implement_id,
        hourmeter_initial=payload.hourmeter_initial,
        hourmeter_final=payload.hourmeter_final,
        fuel_tank_start_liters=payload.fuel_tank_start_liters,
        fuel_refill_liters=payload.fuel_refill_liters,
        fuel_tank_end_liters=payload.fuel_tank_end_liters,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


@router.get("/work_orders", response_model=List[WorkOrderOut])
def list_work_orders(date: datetime | None = None, season: str | None = None, db: Session = Depends(get_db)):
    q = db.query(WorkOrder)
    if date is not None:
        q = q.filter(func.date(WorkOrder.work_date) == func.date(date))
    if season is not None:
        q = q.filter(WorkOrder.season == season)
    return q.order_by(WorkOrder.work_date.desc(), WorkOrder.code).all()


@router.put("/work_orders/{work_order_id}", response_model=WorkOrderOut)
def update_work_order(work_order_id: int, payload: WorkOrderUpdate, db: Session = Depends(get_db)):
    wo = db.query(WorkOrder).get(work_order_id)
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(wo, k, v)

    db.commit()
    db.refresh(wo)
    return wo
