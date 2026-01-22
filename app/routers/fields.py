from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.fields import Field
from app.models.cost_centers import CostCenter
from app.schemas.fields import FieldCreate, FieldOut, FieldUpdate

router = APIRouter(prefix="", tags=["fields"])


@router.post("/fields", response_model=FieldOut)
def create_field(payload: FieldCreate, db: Session = Depends(get_db)):
    if len(payload.polygon) < 3:
        raise HTTPException(status_code=400, detail="El polígono debe tener al menos 3 puntos.")

    field = Field(
        name=payload.name,
        cost_center_id=payload.cost_center_id,
        color=payload.color,
        polygon=[p.model_dump() for p in payload.polygon],
    )
    db.add(field)
    db.commit()
    db.refresh(field)

    return FieldOut(
        id=field.id,
        name=field.name,
        cost_center_id=field.cost_center_id,
        cost_center_name=field.cost_center.name if field.cost_center else None,
        color=field.color,
        polygon=field.polygon,
        created_at=field.created_at,
    )


@router.get("/fields", response_model=List[FieldOut])
def list_fields(db: Session = Depends(get_db)):
    fields = (
        db.query(Field)
        .outerjoin(CostCenter, Field.cost_center_id == CostCenter.id)
        .order_by(Field.created_at.desc())
        .all()
    )

    result: List[FieldOut] = []
    for f in fields:
        result.append(
            FieldOut(
                id=f.id,
                name=f.name,
                cost_center_id=f.cost_center_id,
                cost_center_name=f.cost_center.name if f.cost_center else None,
                color=f.color,
                polygon=f.polygon,
                created_at=f.created_at,
            )
        )
    return result


@router.put("/fields/{field_id}", response_model=FieldOut)
def update_field(field_id: int, payload: FieldUpdate, db: Session = Depends(get_db)):
    field = db.query(Field).get(field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    if payload.name is not None:
        field.name = payload.name
    if payload.cost_center_id is not None:
        field.cost_center_id = payload.cost_center_id
    if payload.color is not None:
        field.color = payload.color
    if payload.polygon is not None:
        if len(payload.polygon) < 3:
            raise HTTPException(status_code=400, detail="El polígono debe tener al menos 3 puntos.")
        field.polygon = [p.model_dump() for p in payload.polygon]

    db.commit()
    db.refresh(field)

    return FieldOut(
        id=field.id,
        name=field.name,
        cost_center_id=field.cost_center_id,
        cost_center_name=field.cost_center.name if field.cost_center else None,
        color=field.color,
        polygon=field.polygon,
        created_at=field.created_at,
    )
