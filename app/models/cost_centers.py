from sqlalchemy import Column, Integer, String, Text, Numeric, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class CostCenter(Base):
    __tablename__ = "cost_centers"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64))
    name = Column(Text, nullable=False)
    hectares = Column(Numeric(10, 2))
    created_at = Column(TIMESTAMP(timezone=True))


class CostCenterPolygon(Base):
    __tablename__ = "cost_center_polygons"

    id = Column(Integer, primary_key=True)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"), nullable=False)
    name = Column(Text, nullable=False)
    geojson = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True))

    cost_center = relationship("CostCenter")
