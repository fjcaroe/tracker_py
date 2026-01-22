from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.activities import Activity
from app.schemas.activities import ActivityCreate, ActivityOut, ActivityUpdate

router = APIRouter(prefix="", tags=["activities"])


@router.post("/activities", response_model=ActivityOut)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    act = Activity(name=payload.name, code=payload.code)
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


@router.get("/activities", response_model=List[ActivityOut])
def list_activities(db: Session = Depends(get_db)):
    return db.query(Activity).filter(Activity.is_active == True).order_by(Activity.name).all()


@router.put("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(activity_id: int, payload: ActivityUpdate, db: Session = Depends(get_db)):
    act = db.query(Activity).get(activity_id)
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(act, k, v)

    db.commit()
    db.refresh(act)
    return act
