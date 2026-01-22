from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.drivers import Driver
from app.schemas.drivers import DriverCreate, DriverOut

router = APIRouter(prefix="", tags=["drivers"])


@router.post("/drivers", response_model=DriverOut)
def create_driver(payload: DriverCreate, db: Session = Depends(get_db)):
    driver = Driver(name=payload.name, rut=payload.rut, is_active=True, created_at=datetime.utcnow())
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


@router.get("/drivers", response_model=List[DriverOut])
def list_drivers(db: Session = Depends(get_db)):
    return db.query(Driver).order_by(Driver.id).all()
