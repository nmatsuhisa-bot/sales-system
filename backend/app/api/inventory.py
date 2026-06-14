"""在庫管理 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional
from app.db.models import get_db, Product, StockMovement

router = APIRouter()

class StockMovementIn(BaseModel):
    product_id: str
    movement_type: str  # in, out, adjust
    quantity: float
    unit_price: Optional[int] = None
    reference_type: Optional[str] = None
    notes: Optional[str] = None

@router.get("/")
def list_inventory(db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.is_active == True).all()
    return [
        {
            "product_id": str(p.id), "product_code": p.product_code, "name": p.name,
            "product_type": p.product_type, "unit": p.unit,
            "stock_quantity": float(p.stock_quantity or 0),
            "min_stock_quantity": float(p.min_stock_quantity or 0),
            "is_low_stock": (p.stock_quantity or 0) <= (p.min_stock_quantity or 0)
        }
        for p in products
    ]

@router.post("/movements")
def add_movement(data: StockMovementIn, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == data.product_id).first()
    if not p:
        from fastapi import HTTPException
        raise HTTPException(404, "商品が見つかりません")
    if data.movement_type == "in":
        p.stock_quantity = (p.stock_quantity or 0) + data.quantity
    elif data.movement_type == "out":
        p.stock_quantity = (p.stock_quantity or 0) - data.quantity
    else:
        p.stock_quantity = data.quantity
    mv = StockMovement(
        product_id=data.product_id, movement_type=data.movement_type,
        quantity=data.quantity, unit_price=data.unit_price,
        reference_type=data.reference_type, notes=data.notes
    )
    db.add(mv)
    db.commit()
    return {"stock_quantity": float(p.stock_quantity)}

@router.get("/movements/{product_id}")
def get_movements(product_id: str, db: Session = Depends(get_db)):
    mvs = db.query(StockMovement).filter(StockMovement.product_id == product_id).order_by(desc(StockMovement.created_at)).limit(50).all()
    return [
        {"id": str(m.id), "movement_type": m.movement_type, "quantity": float(m.quantity),
         "unit_price": int(m.unit_price or 0), "notes": m.notes,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in mvs
    ]
