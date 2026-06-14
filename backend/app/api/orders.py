"""受注管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
from app.db.models import get_db, Order, OrderItem, Customer

router = APIRouter()

class OrderItemIn(BaseModel):
    line_no: int
    product_id: Optional[str] = None
    item_name: str
    description: Optional[str] = None
    quantity: float = 1
    unit: str = "式"
    unit_price: int = 0
    notes: Optional[str] = None

class OrderCreate(BaseModel):
    customer_id: str
    title: Optional[str] = None
    order_date: date
    delivery_date: Optional[date] = None
    delivery_location: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    items: List[OrderItemIn] = []

def order_to_dict(o: Order):
    return {
        "id": str(o.id),
        "order_no": o.order_no,
        "customer_id": str(o.customer_id),
        "customer_name": o.customer.name if o.customer else None,
        "title": o.title,
        "order_date": o.order_date.isoformat() if o.order_date else None,
        "delivery_date": o.delivery_date.isoformat() if o.delivery_date else None,
        "status": o.status,
        "total_amount": int(o.total_amount or 0),
        "tax_amount": int(o.tax_amount or 0),
        "subtotal": int(o.subtotal or 0),
        "delivery_location": o.delivery_location,
        "payment_terms": o.payment_terms,
        "notes": o.notes,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "items": [
            {
                "id": str(i.id), "line_no": i.line_no,
                "item_name": i.item_name, "description": i.description,
                "quantity": float(i.quantity or 1), "unit": i.unit,
                "unit_price": int(i.unit_price or 0), "amount": int(i.amount or 0),
                "notes": i.notes
            } for i in sorted(o.items, key=lambda x: x.line_no)
        ]
    }

@router.get("/")
def list_orders(
    page: int = Query(1, ge=1), per_page: int = Query(20),
    status: Optional[str] = None, customer_id: Optional[str] = None,
    search: Optional[str] = None, db: Session = Depends(get_db)
):
    q = db.query(Order).options(joinedload(Order.customer))
    if status:
        q = q.filter(Order.status == status)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    if search:
        q = q.join(Customer).filter(
            Order.order_no.ilike(f"%{search}%") | Customer.name.ilike(f"%{search}%")
        )
    total = q.count()
    items = q.order_by(desc(Order.created_at)).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "items": [order_to_dict(i) for i in items]}

@router.post("/", status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    from datetime import datetime
    year = datetime.now().year
    prefix = f"SO{year}-"
    last = db.query(Order).filter(Order.order_no.like(f"{prefix}%")).order_by(desc(Order.order_no)).first()
    order_no = f"{prefix}{(int(last.order_no.split('-')[-1]) + 1 if last else 1):04d}"
    subtotal = sum(int(i.unit_price * i.quantity) for i in data.items)
    tax = int(subtotal * 0.10)
    o = Order(
        order_no=order_no, customer_id=data.customer_id, title=data.title,
        order_date=data.order_date, delivery_date=data.delivery_date,
        delivery_location=data.delivery_location, payment_terms=data.payment_terms,
        notes=data.notes, subtotal=subtotal, tax_amount=tax, total_amount=subtotal+tax
    )
    db.add(o)
    db.flush()
    for i in data.items:
        db.add(OrderItem(
            order_id=o.id, line_no=i.line_no, product_id=i.product_id,
            item_name=i.item_name, description=i.description, quantity=i.quantity,
            unit=i.unit, unit_price=i.unit_price, amount=int(i.unit_price * i.quantity), notes=i.notes
        ))
    db.commit()
    db.refresh(o)
    return order_to_dict(o)

@router.get("/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    o = db.query(Order).options(joinedload(Order.customer), joinedload(Order.items)).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(404)
    return order_to_dict(o)

@router.patch("/{order_id}/status")
def update_order_status(order_id: str, status: str, db: Session = Depends(get_db)):
    o = db.query(Order).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(404)
    o.status = status
    db.commit()
    return {"status": status}
