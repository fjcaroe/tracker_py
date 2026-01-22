from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.cost_centers import CostCenter
from app.schemas.cost_centers import CostCenterCreate, CostCenterOut

router = APIRouter(prefix="", tags=["cost_centers"])


@router.post("/cost_centers", response_model=CostCenterOut)
def create_cost_center(payload: CostCenterCreate, db: Session = Depends(get_db)):
    cc = CostCenter(
        name=payload.name,
        external_id=payload.external_id,
        hectares=payload.hectares,
        created_at=datetime.utcnow(),
    )
    db.add(cc)
    db.commit()
    db.refresh(cc)
    return cc


@router.get("/cost_centers", response_model=List[CostCenterOut])
def list_cost_centers(db: Session = Depends(get_db)):
    return db.query(CostCenter).order_by(CostCenter.id).all()
