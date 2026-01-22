from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.machines import Machine
from app.models.work_orders import WorkOrder
from app.models.sessions import TrackingSession, TrackingPoint
from app.models.enums import TrackingStatus
from app.schemas.machines import MachineCreate, MachineOut, MachineUpdate, FuelStatusOut, MachineOdometerOut
from app.core.utils import haversine_m

router = APIRouter(prefix="", tags=["machines"])


@router.get("/machines", response_model=List[MachineOut])
def list_machines(db: Session = Depends(get_db)):
    return db.query(Machine).order_by(Machine.id).all()


@router.post("/machines", response_model=MachineOut)
def create_machine(payload: MachineCreate, db: Session = Depends(get_db)):
    machine = Machine(
        external_id=payload.external_id,
        name=payload.name,
        plate=payload.plate,
        description=payload.description,
        cost_center_id=payload.cost_center_id,
        tank_capacity_liters=payload.tank_capacity_liters,
        fuel_consumption_lph=payload.fuel_consumption_lph,
        fuel_consumption_lpkm=payload.fuel_consumption_lpkm,
        default_activity_id=payload.default_activity_id,
        default_labor_id=payload.default_labor_id,
        created_at=datetime.utcnow(),
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


@router.put("/machines/{machine_id}", response_model=MachineOut)
def update_machine(machine_id: int, payload: MachineUpdate, db: Session = Depends(get_db)):
    machine = db.query(Machine).get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(machine, field, value)

    db.commit()
    db.refresh(machine)
    return machine


@router.get("/machines/resolve", response_model=MachineOut)
def resolve_machine(external_id: str, db: Session = Depends(get_db)):
    m = db.query(Machine).filter(Machine.external_id == external_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")
    return m


@router.get("/machines/{machine_id}/fuel_status", response_model=FuelStatusOut)
def machine_fuel_status(machine_id: int, db: Session = Depends(get_db)):
    m = db.query(Machine).get(machine_id)
    if not m:
        raise HTTPException(status_code=404, detail="Machine not found")

    last_wo = (
        db.query(WorkOrder)
        .filter(WorkOrder.machine_id == machine_id)
        .order_by(WorkOrder.work_date.desc(), WorkOrder.id.desc())
        .first()
    )

    last_liters = None
    if last_wo:
        if last_wo.fuel_tank_end_liters is not None:
            last_liters = float(last_wo.fuel_tank_end_liters)
        elif last_wo.fuel_tank_start_liters is not None:
            last_liters = float(last_wo.fuel_tank_start_liters)

    return FuelStatusOut(
        machine_id=machine_id,
        tank_capacity_liters=float(m.tank_capacity_liters) if m.tank_capacity_liters is not None else None,
        last_liters=last_liters,
        last_work_order_id=last_wo.id if last_wo else None,
        as_of=last_wo.created_at.isoformat() if last_wo and last_wo.created_at else None,
    )


@router.get("/machines/{machine_id}/hourmeter")
def get_machine_hourmeter(machine_id: int, db: Session = Depends(get_db)):
    machine = db.query(Machine).get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    sessions = (
        db.query(TrackingSession)
        .filter(TrackingSession.machine_id == machine_id)
        .filter(TrackingSession.status == TrackingStatus.closed)
        .order_by(TrackingSession.started_at.asc())
        .all()
    )

    total_hours = 0.0
    last_session_at = None

    for s in sessions:
        if not s.started_at:
            continue
        end_ts = s.ended_at or s.started_at
        delta = (end_ts - s.started_at).total_seconds() / 3600.0
        if delta > 0:
            total_hours += delta
        if last_session_at is None or end_ts > last_session_at:
            last_session_at = end_ts

    return {
        "machine_id": machine_id,
        "hourmeter": round(total_hours, 1),
        "last_session_at": last_session_at,
    }


@router.get("/machines/{machine_id}/odometer", response_model=MachineOdometerOut)
def get_machine_odometer(machine_id: int, db: Session = Depends(get_db)):
    machine = db.query(Machine).get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    sessions = (
        db.query(TrackingSession)
        .filter(TrackingSession.machine_id == machine_id)
        .order_by(TrackingSession.started_at.asc())
        .all()
    )

    if not sessions:
        return MachineOdometerOut(total_distance_m=0.0, total_sessions=0, last_session_at=None)

    total_distance_m = 0.0
    last_session_at: Optional[datetime] = None

    for s in sessions:
        if s.total_distance_m is not None:
            total_distance_m += float(s.total_distance_m)
        else:
            points = (
                db.query(TrackingPoint)
                .filter(TrackingPoint.session_id == s.id)
                .order_by(TrackingPoint.ts.asc())
                .all()
            )
            if len(points) >= 2:
                prev = points[0]
                dist_s = 0.0
                for p in points[1:]:
                    dist_s += haversine_m(prev.lat, prev.lon, p.lat, p.lon)
                    prev = p
                total_distance_m += dist_s
                s.total_distance_m = dist_s

        candidate_ts = s.ended_at or s.started_at
        if candidate_ts and (last_session_at is None or candidate_ts > last_session_at):
            last_session_at = candidate_ts

    db.commit()

    return MachineOdometerOut(
        total_distance_m=total_distance_m,
        total_sessions=len(sessions),
        last_session_at=last_session_at.isoformat() if last_session_at else None,
    )
