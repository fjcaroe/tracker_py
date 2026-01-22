from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.security import get_current_user, allowed_cost_center_ids
from app.core.utils import haversine_m, _f, duration_hours, estimate_fuel_liters
from app.models.users import User
from app.models.enums import TrackingStatus
from app.models.sessions import TrackingSession, TrackingPoint
from app.models.machines import Machine
from app.models.drivers import Driver
from app.models.cost_centers import CostCenter
from app.models.work_orders import WorkOrder
from app.models.activities import Labor
from app.schemas.sessions import (
    SessionStart,
    TrackingSessionOut,
    PointsBatchIn,
    SessionSummaryOut,
    TrackingPointOut,
)
from fastapi import Query

router = APIRouter(prefix="", tags=["sessions"])


@router.post("/sessions/start", response_model=TrackingSessionOut)
def start_session(
    payload: SessionStart,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    machine = db.query(Machine).get(payload.machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    work_order = None
    if payload.work_order_id is not None:
        work_order = db.query(WorkOrder).get(payload.work_order_id)
        if not work_order:
            raise HTTPException(status_code=404, detail="Work order not found")

    started_at = payload.started_at or datetime.utcnow()
    cc_id = payload.cost_center_id or (work_order.cost_center_id if work_order else None) or machine.cost_center_id

    session_obj = TrackingSession(
        machine_id=payload.machine_id,
        driver_id=payload.driver_id,
        cost_center_id=cc_id,
        work_order_id=payload.work_order_id,
        started_at=started_at,
        status=TrackingStatus.open,
        created_at=datetime.utcnow(),
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return session_obj

@router.get("/sessions/search", response_model=List[SessionSummaryOut])
def search_sessions(
    # rango: inclusive en from, exclusive en to (patrón típico)
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    limit: int = 200,
    status: Optional[str] = Query(None),
    cost_center_id: int | None = None,
    machine_id: int | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="'to' must be greater than 'from'")

    subq = (
        db.query(
            TrackingPoint.session_id.label("session_id"),
            func.count(TrackingPoint.id).label("points_count"),
        )
        .group_by(TrackingPoint.session_id)
        .subquery()
    )

    q = (
        db.query(
            TrackingSession,
            Machine.name.label("machine_name"),
            Driver.name.label("driver_name"),
            CostCenter.name.label("cost_center_name"),
            func.coalesce(subq.c.points_count, 0).label("points_count"),
            WorkOrder.id.label("work_order_id"),
            WorkOrder.labor_id.label("labor_id"),
            Labor.effort_factor.label("effort_factor"),
            Labor.target_speed_kmh.label("target_speed_kmh"),
            Machine.fuel_consumption_lph.label("machine_lph"),
            Machine.fuel_consumption_lpkm.label("machine_lpkm"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .outerjoin(subq, subq.c.session_id == TrackingSession.id)
        .outerjoin(WorkOrder, TrackingSession.work_order_id == WorkOrder.id)
        .outerjoin(Labor, WorkOrder.labor_id == Labor.id)
        # filtro principal por fecha: sessions cuyo started_at cae en el rango
        .filter(TrackingSession.started_at >= date_from)
        .filter(TrackingSession.started_at < date_to)
        .order_by(TrackingSession.started_at.desc())
        .limit(limit)
    )

    # permisos
    if not current.is_admin:
        allowed_ids = allowed_cost_center_ids(db, current.id)
        if not allowed_ids:
            return []
        q = q.filter(TrackingSession.cost_center_id.in_(allowed_ids))

    # filtros opcionales
    if status is not None:
        status_norm = status.strip().lower()
        if status_norm not in ("open", "closed"):
            raise HTTPException(status_code=400, detail="Invalid status. Use: open|closed")
        q = q.filter(TrackingSession.status == status_norm)

    if cost_center_id is not None:
        if not current.is_admin:
            allowed_ids = set(allowed_cost_center_ids(db, current.id))
            if cost_center_id not in allowed_ids:
                raise HTTPException(status_code=403, detail="Not allowed cost center")
        q = q.filter(TrackingSession.cost_center_id == cost_center_id)

    if machine_id is not None:
        q = q.filter(TrackingSession.machine_id == machine_id)

    rows = q.all()

    out: List[SessionSummaryOut] = []
    for (
        s, machine_name, driver_name, cost_center_name, points_count,
        work_order_id, labor_id, effort_factor, target_speed_kmh,
        machine_lph, machine_lpkm
    ) in rows:
        dur_h = duration_hours(s.started_at, s.ended_at)
        ef = _f(effort_factor)
        eff_h = (dur_h * ef) if (dur_h is not None and ef is not None) else None

        total_dist_m = _f(s.total_distance_m)
        avg_kmh = _f(s.avg_speed_kmh)

        est_fuel = estimate_fuel_liters(
            duration_h=dur_h,
            total_distance_m=total_dist_m,
            machine_lph=_f(machine_lph),
            machine_lpkm=_f(machine_lpkm),
            effort_factor=ef,
        )

        out.append(
            SessionSummaryOut(
                id=s.id,
                machine_id=s.machine_id,
                machine_name=machine_name,
                driver_name=driver_name,
                cost_center_name=cost_center_name,
                started_at=s.started_at,
                ended_at=s.ended_at,
                status=s.status,
                points_count=int(points_count or 0),
                work_order_id=work_order_id,
                labor_id=labor_id,
                effort_factor=ef,
                target_speed_kmh=_f(target_speed_kmh),
                total_distance_m=total_dist_m,
                avg_speed_kmh=avg_kmh,
                duration_hours=dur_h,
                effective_hours=eff_h,
                estimated_fuel_liters=est_fuel,
            )
        )
    return out


@router.post("/sessions/{session_id:uuid}/points")
def add_points(session_id: uuid.UUID, payload: PointsBatchIn, db: Session = Depends(get_db)):
    session = db.query(TrackingSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != TrackingStatus.open:
        raise HTTPException(status_code=400, detail="Session is closed; no more points can be recorded.")

    now = datetime.utcnow()
    for p in payload.points:
        point = TrackingPoint(
            session_id=session_id,
            ts=p.timestamp,
            lat=p.lat,
            lon=p.lon,
            speed_mps=p.speed_mps,
            accuracy_m=p.accuracy_m,
            extra=p.extra,
            created_at=now,
        )
        db.add(point)

    db.commit()
    return {"inserted": len(payload.points)}


@router.post("/sessions/{session_id:uuid}/close", response_model=TrackingSessionOut)
def close_session(session_id: uuid.UUID, ended_at: Optional[datetime] = None, db: Session = Depends(get_db)):
    session_obj = db.query(TrackingSession).get(session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_obj.status == TrackingStatus.closed:
        return session_obj

    points = (
        db.query(TrackingPoint)
        .filter(TrackingPoint.session_id == session_id)
        .order_by(TrackingPoint.ts.asc())
        .all()
    )

    if len(points) >= 2:
        total_distance_m = 0.0
        start_ts = points[0].ts
        end_ts = points[-1].ts

        prev = points[0]
        for p in points[1:]:
            total_distance_m += haversine_m(prev.lat, prev.lon, p.lat, p.lon)
            prev = p

        duration_h = (end_ts - start_ts).total_seconds() / 3600.0
        avg_speed_kmh = ((total_distance_m / 1000.0) / duration_h) if duration_h > 0 else 0.0

        session_obj.total_distance_m = total_distance_m
        session_obj.avg_speed_kmh = avg_speed_kmh

    session_obj.status = TrackingStatus.closed
    session_obj.ended_at = ended_at or datetime.utcnow()

    db.commit()
    db.refresh(session_obj)
    return session_obj


@router.get("/sessions/{session_id:uuid}", response_model=TrackingSessionOut)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if not current.is_admin:
        allowed_ids = set(allowed_cost_center_ids(db, current.id))
        if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed")

    return s


@router.get("/sessions/{session_id:uuid}/points", response_model=List[TrackingPointOut])
def get_session_points(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if not current.is_admin:
        allowed_ids = set(allowed_cost_center_ids(db, current.id))
        if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed")

    return (
        db.query(TrackingPoint)
        .filter(TrackingPoint.session_id == session_id)
        .order_by(TrackingPoint.ts.asc())
        .all()
    )


@router.get("/sessions/my", response_model=List[SessionSummaryOut])
def my_sessions(
    limit: int = 50,
    status: TrackingStatus | None = None,
    cost_center_id: int | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    allowed_ids = allowed_cost_center_ids(db, current.id)
    if not allowed_ids:
        return []

    subq = (
        db.query(
            TrackingPoint.session_id.label("session_id"),
            func.count(TrackingPoint.id).label("points_count"),
        )
        .group_by(TrackingPoint.session_id)
        .subquery()
    )

    q = (
        db.query(
            TrackingSession,
            Machine.name.label("machine_name"),
            Driver.name.label("driver_name"),
            CostCenter.name.label("cost_center_name"),
            func.coalesce(subq.c.points_count, 0).label("points_count"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .outerjoin(subq, subq.c.session_id == TrackingSession.id)
        .filter(TrackingSession.cost_center_id.in_(allowed_ids))
        .order_by(TrackingSession.started_at.desc())
        .limit(limit)
    )

    if status is not None:
        q = q.filter(TrackingSession.status == status)

    if cost_center_id is not None:
        if cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed cost center")
        q = q.filter(TrackingSession.cost_center_id == cost_center_id)

    rows = q.all()

    out: List[SessionSummaryOut] = []
    for s, machine_name, driver_name, cost_center_name, points_count in rows:
        out.append(
            SessionSummaryOut(
                id=s.id,
                machine_id=s.machine_id,
                machine_name=machine_name,
                driver_name=driver_name,
                cost_center_name=cost_center_name,
                started_at=s.started_at,
                ended_at=s.ended_at,
                status=s.status,
                points_count=int(points_count or 0),
            )
        )
    return out


@router.get("/sessions_active", response_model=List[SessionSummaryOut])
def list_active_sessions(db: Session = Depends(get_db)):
    subq = (
        db.query(
            TrackingPoint.session_id.label("session_id"),
            func.count(TrackingPoint.id).label("points_count"),
        )
        .group_by(TrackingPoint.session_id)
        .subquery()
    )

    rows = (
        db.query(
            TrackingSession,
            Machine.name.label("machine_name"),
            Driver.name.label("driver_name"),
            CostCenter.name.label("cost_center_name"),
            func.coalesce(subq.c.points_count, 0).label("points_count"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .outerjoin(subq, subq.c.session_id == TrackingSession.id)
        .filter(TrackingSession.status == TrackingStatus.open)
        .order_by(TrackingSession.started_at.desc())
        .all()
    )

    result: List[SessionSummaryOut] = []
    for s, machine_name, driver_name, cost_center_name, points_count in rows:
        result.append(
            SessionSummaryOut(
                id=s.id,
                machine_id=s.machine_id,
                machine_name=machine_name,
                driver_name=driver_name,
                cost_center_name=cost_center_name,
                started_at=s.started_at,
                ended_at=s.ended_at,
                status=s.status,
                points_count=int(points_count or 0),
            )
        )
    return result


@router.get("/sessions/{session_id:uuid}/points_range", response_model=List[TrackingPointOut])
def get_session_points_range(
    session_id: uuid.UUID,
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    limit: int = 5000,

    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="'to' must be greater than 'from'")

    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if not current.is_admin:
        allowed_ids = set(allowed_cost_center_ids(db, current.id))
        if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed")

    return (
        db.query(TrackingPoint)
        .filter(TrackingPoint.session_id == session_id)
        .filter(TrackingPoint.ts >= date_from)
        .filter(TrackingPoint.ts < date_to)
        .order_by(TrackingPoint.ts.asc())
        .limit(limit)
        .all()
    )

# ÚNICA versión "recent" que conservamos (la más completa): /sessions_recent
@router.get("/sessions_recent", response_model=List[SessionSummaryOut])
def list_recent_sessions(
    limit: int = 50,
    status: TrackingStatus | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    subq = (
        db.query(
            TrackingPoint.session_id.label("session_id"),
            func.count(TrackingPoint.id).label("points_count"),
        )
        .group_by(TrackingPoint.session_id)
        .subquery()
    )

    q = (
        db.query(
            TrackingSession,
            Machine.name.label("machine_name"),
            Driver.name.label("driver_name"),
            CostCenter.name.label("cost_center_name"),
            func.coalesce(subq.c.points_count, 0).label("points_count"),
            WorkOrder.id.label("work_order_id"),
            WorkOrder.labor_id.label("labor_id"),
            Labor.effort_factor.label("effort_factor"),
            Labor.target_speed_kmh.label("target_speed_kmh"),
            Machine.fuel_consumption_lph.label("machine_lph"),
            Machine.fuel_consumption_lpkm.label("machine_lpkm"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .outerjoin(subq, subq.c.session_id == TrackingSession.id)
        .outerjoin(WorkOrder, TrackingSession.work_order_id == WorkOrder.id)
        .outerjoin(Labor, WorkOrder.labor_id == Labor.id)
        .order_by(TrackingSession.started_at.desc())
        .limit(limit)
    )

    if not current.is_admin:
        allowed_ids = allowed_cost_center_ids(db, current.id)
        if not allowed_ids:
            return []
        q = q.filter(TrackingSession.cost_center_id.in_(allowed_ids))

    if status is not None:
        q = q.filter(TrackingSession.status == status)

    rows = q.all()

    out: List[SessionSummaryOut] = []
    for (
        s, machine_name, driver_name, cost_center_name, points_count,
        work_order_id, labor_id, effort_factor, target_speed_kmh,
        machine_lph, machine_lpkm
    ) in rows:
        dur_h = duration_hours(s.started_at, s.ended_at)
        ef = _f(effort_factor)
        eff_h = (dur_h * ef) if (dur_h is not None and ef is not None) else None

        total_dist_m = _f(s.total_distance_m)
        avg_kmh = _f(s.avg_speed_kmh)

        est_fuel = estimate_fuel_liters(
            duration_h=dur_h,
            total_distance_m=total_dist_m,
            machine_lph=_f(machine_lph),
            machine_lpkm=_f(machine_lpkm),
            effort_factor=ef,
        )

        out.append(
            SessionSummaryOut(
                id=s.id,
                machine_id=s.machine_id,
                machine_name=machine_name,
                driver_name=driver_name,
                cost_center_name=cost_center_name,
                started_at=s.started_at,
                ended_at=s.ended_at,
                status=s.status,
                points_count=int(points_count or 0),
                work_order_id=work_order_id,
                labor_id=labor_id,
                effort_factor=ef,
                target_speed_kmh=_f(target_speed_kmh),
                total_distance_m=total_dist_m,
                avg_speed_kmh=avg_kmh,
                duration_hours=dur_h,
                effective_hours=eff_h,
                estimated_fuel_liters=est_fuel,
            )
        )
    return out
