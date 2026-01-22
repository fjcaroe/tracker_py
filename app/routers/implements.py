from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.implements import Implement
from app.schemas.implements import ImplementCreate, ImplementOut

router = APIRouter(prefix="", tags=["implements"])


@router.post("/implements", response_model=ImplementOut)
def create_implement(payload: ImplementCreate, db: Session = Depends(get_db)):
    exists = db.query(Implement).filter(func.lower(Implement.name) == payload.name.lower()).first()
    if exists:
        return exists

    imp = Implement(name=payload.name)
    db.add(imp)
    db.commit()
    db.refresh(imp)
    return imp


@router.get("/implements", response_model=List[ImplementOut])
def list_implements(db: Session = Depends(get_db)):
    return db.query(Implement).order_by(Implement.name.asc()).all()
