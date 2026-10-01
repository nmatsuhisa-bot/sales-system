"""発注管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime
from app.db.models import get_db, PurchaseOrder, PurchaseOrderItem, Supplier

router = APIRouter()

class POItemIn(BaseModel):
    line_no: int
    product_id: Optional[str] = None
    item_name: str
    quantity: float = 1
    unit: str = "式"
    unit_price: int = 0
    notes: Optional[str] = None

class POCreate(BaseModel):
    supplier_id: str
    order_id: Optional[str] = None
    issue_date: date
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    items: List[POItemIn] = []

def po_to_dict(p):
    return {
        "id": str(p.id), "purchase_order_no": p.purchase_order_no,
        "supplier_id": str(p.supplier_id),
        "supplier_name": p.supplier.name if hasattr(p, 'supplier') and p.supplier else None,
        "issue_date": p.issue_date.isoformat() if p.issue_date else None,
        "expected_date": p.expected_date.isoformat() if p.expected_date else None,
        "status": p.status, "total_amount": int(p.total_amount or 0),
        "notes": p.notes,
        "items": [{"id": str(i.id), "line_no": i.line_no, "item_name": i.item_name,
                   "quantity": float(i.quantity or 1), "unit": i.unit,
                   "unit_price": int(i.unit_price or 0), "amount": int(i.amount or 0),
                   "received_quantity": float(i.received_quantity or 0)} for i in p.items]
    }

@router.get("/")
def list_purchase_orders(
    page: int = Query(1, ge=1), per_page: int = Query(20),
    status: Optional[str] = None, db: Session = Depends(get_db)
):
    q = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.supplier), joinedload(PurchaseOrder.items))
    if status:
        q = q.filter(PurchaseOrder.status == status)
    total = q.count()
    items = q.order_by(desc(PurchaseOrder.created_at)).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "items": [po_to_dict(p) for p in items]}

@router.post("/", status_code=201)
def create_purchase_order(data: POCreate, db: Session = Depends(get_db)):
    year = datetime.now().year
    prefix = f"PO{year}-"
    last = db.query(PurchaseOrder).filter(PurchaseOrder.purchase_order_no.like(f"{prefix}%")).order_by(desc(PurchaseOrder.purchase_order_no)).first()
    po_no = f"{prefix}{(int(last.purchase_order_no.split('-')[-1]) + 1 if last else 1):04d}"
    subtotal = sum(int(i.unit_price * i.quantity) for i in data.items)
    tax = int(subtotal * 0.10)
    po = PurchaseOrder(
        purchase_order_no=po_no, supplier_id=data.supplier_id,
        order_id=data.order_id, issue_date=data.issue_date,
        expected_date=data.expected_date, notes=data.notes,
        subtotal=subtotal, tax_amount=tax, total_amount=subtotal+tax
    )
    db.add(po)
    db.flush()
    for i in data.items:
        db.add(PurchaseOrderItem(
            purchase_order_id=po.id, line_no=i.line_no, product_id=i.product_id,
            item_name=i.item_name, quantity=i.quantity, unit=i.unit,
            unit_price=i.unit_price, amount=int(i.unit_price * i.quantity), notes=i.notes
        ))
    db.commit()
    db.refresh(po)
    return {"purchase_order_no": po_no, "id": str(po.id)}

@router.patch("/{po_id}/status")
def update_po_status(po_id: str, status: str, db: Session = Depends(get_db)):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(404)
    po.status = status
    db.commit()
    return {"status": status}
