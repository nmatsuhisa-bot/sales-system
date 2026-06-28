"""在庫管理 API（部材ベース：在庫 = 入荷 − 利用）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_, case
from pydantic import BaseModel
from typing import Optional
from datetime import date
from app.db.models import (
    get_db, Product, StockMovement,
    MaterialMaster, MaterialStockMovement, ProjectOrder,
)

router = APIRouter()

# 符号: 入荷=+ / 利用・引当=- / 調整=指定符号のまま
def _signed_qty(movement_type: str, qty: float) -> float:
    qty = abs(float(qty))
    if movement_type in ("利用", "引当"):
        return -qty
    return qty  # 入荷 / 調整(+)

# =============================================
# 部材在庫
# =============================================

@router.get("/materials")
def list_material_stock(search: Optional[str] = Query(None), low_only: bool = Query(False), db: Session = Depends(get_db)):
    """在庫が動いた部材ごとに 入荷累計・利用累計・在庫数 を返す"""
    received = func.sum(case((MaterialStockMovement.quantity > 0, MaterialStockMovement.quantity), else_=0))
    used = func.sum(case((MaterialStockMovement.quantity < 0, -MaterialStockMovement.quantity), else_=0))
    stock = func.sum(MaterialStockMovement.quantity)
    agg = db.query(
        MaterialStockMovement.material_id.label("mid"),
        received.label("received"), used.label("used"), stock.label("stock"),
    ).group_by(MaterialStockMovement.material_id).subquery()

    q = db.query(MaterialMaster, agg.c.received, agg.c.used, agg.c.stock).join(agg, MaterialMaster.id == agg.c.mid)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(MaterialMaster.material_name.ilike(like), MaterialMaster.material_code.ilike(like)))
    rows = q.order_by(MaterialMaster.material_code).limit(300).all()
    out = []
    for m, rcv, usd, stk in rows:
        s = float(stk or 0)
        if low_only and s > 0:
            continue
        out.append({
            "material_id": str(m.id), "material_code": m.material_code, "material_name": m.material_name,
            "unit": m.unit, "received": float(rcv or 0), "used": float(usd or 0), "stock": s,
            "is_low": s <= 0,
        })
    return out

class MovementIn(BaseModel):
    material_id: str
    movement_type: str            # 入荷 / 利用 / 引当 / 調整
    quantity: float
    movement_date: Optional[str] = None
    project_order_id: Optional[str] = None
    purchase_order_id: Optional[str] = None
    notes: Optional[str] = None

@router.post("/material-movements")
def add_material_movement(data: MovementIn, db: Session = Depends(get_db)):
    m = db.query(MaterialMaster).filter(MaterialMaster.id == data.material_id).first()
    if not m:
        raise HTTPException(404, "部材が見つかりません")
    mv = MaterialStockMovement(
        material_id=data.material_id, movement_type=data.movement_type,
        quantity=_signed_qty(data.movement_type, data.quantity),
        movement_date=data.movement_date or date.today().isoformat(),
        project_order_id=data.project_order_id or None,
        purchase_order_id=data.purchase_order_id or None,
        notes=data.notes,
    )
    db.add(mv); db.commit(); db.refresh(mv)
    stock = db.query(func.coalesce(func.sum(MaterialStockMovement.quantity), 0)).filter(
        MaterialStockMovement.material_id == data.material_id).scalar()
    return {"ok": True, "stock": float(stock or 0)}

@router.get("/material-movements/{material_id}")
def material_movement_history(material_id: str, db: Session = Depends(get_db)):
    mvs = db.query(MaterialStockMovement).options(joinedload(MaterialStockMovement.project_order)).filter(
        MaterialStockMovement.material_id == material_id
    ).order_by(desc(MaterialStockMovement.created_at)).limit(100).all()
    return [{
        "id": str(mv.id), "movement_type": mv.movement_type, "quantity": float(mv.quantity),
        "movement_date": str(mv.movement_date) if mv.movement_date else None,
        "child_no": mv.project_order.child_no if mv.project_order else None,
        "notes": mv.notes,
        "created_at": mv.created_at.isoformat() if mv.created_at else None,
    } for mv in mvs]

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
