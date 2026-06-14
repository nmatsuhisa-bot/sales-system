from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import date, datetime
import io
import uuid

from app.db.models import get_db, Quotation, QuotationItem, QuotationItemOption, Customer, Order, OrderItem
from pydantic import BaseModel

router = APIRouter()

# =============================================
# Pydantic スキーマ
# =============================================

class QuotationItemOptionIn(BaseModel):
    option_id: Optional[str] = None
    option_name: str
    price: int = 0
    notes: Optional[str] = None

class QuotationItemIn(BaseModel):
    line_no: int
    product_id: Optional[str] = None
    item_name: str
    description: Optional[str] = None
    quantity: float = 1
    unit: str = "式"
    unit_price: int = 0
    notes: Optional[str] = None
    options: List[QuotationItemOptionIn] = []

class QuotationCreate(BaseModel):
    customer_id: str
    title: Optional[str] = None
    issue_date: date
    valid_until: Optional[date] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_location: Optional[str] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    items: List[QuotationItemIn] = []

class QuotationUpdate(BaseModel):
    title: Optional[str] = None
    valid_until: Optional[date] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    delivery_location: Optional[str] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    status: Optional[str] = None
    items: Optional[List[QuotationItemIn]] = None

# =============================================
# ヘルパー関数
# =============================================

def generate_quotation_no(db: Session) -> str:
    year = datetime.now().year
    prefix = f"Q{year}-"
    last = db.query(Quotation).filter(
        Quotation.quotation_no.like(f"{prefix}%")
    ).order_by(desc(Quotation.quotation_no)).first()
    if last:
        seq = int(last.quotation_no.split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"

def calc_totals(items: List[QuotationItemIn]):
    subtotal = 0
    for item in items:
        item_amount = int(item.unit_price * item.quantity)
        option_total = sum(opt.price for opt in item.options)
        subtotal += item_amount + option_total
    tax = int(subtotal * 0.10)
    return subtotal, tax, subtotal + tax

def quotation_to_dict(q: Quotation):
    return {
        "id": str(q.id),
        "quotation_no": q.quotation_no,
        "customer_id": str(q.customer_id),
        "customer_name": q.customer.name if q.customer else None,
        "title": q.title,
        "issue_date": q.issue_date.isoformat() if q.issue_date else None,
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "status": q.status,
        "subtotal": int(q.subtotal or 0),
        "tax_rate": float(q.tax_rate or 10),
        "tax_amount": int(q.tax_amount or 0),
        "total_amount": int(q.total_amount or 0),
        "delivery_terms": q.delivery_terms,
        "payment_terms": q.payment_terms,
        "delivery_location": q.delivery_location,
        "notes": q.notes,
        "internal_notes": q.internal_notes,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        "items": [
            {
                "id": str(item.id),
                "line_no": item.line_no,
                "product_id": str(item.product_id) if item.product_id else None,
                "item_name": item.item_name,
                "description": item.description,
                "quantity": float(item.quantity or 1),
                "unit": item.unit,
                "unit_price": int(item.unit_price or 0),
                "amount": int(item.amount or 0),
                "notes": item.notes,
                "options": [
                    {
                        "id": str(opt.id),
                        "option_id": str(opt.option_id) if opt.option_id else None,
                        "option_name": opt.option_name,
                        "price": int(opt.price or 0),
                        "notes": opt.notes,
                    }
                    for opt in item.options
                ]
            }
            for item in sorted(q.items, key=lambda x: x.line_no)
        ]
    }

# =============================================
# エンドポイント
# =============================================

@router.get("/")
def list_quotations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Quotation).options(joinedload(Quotation.customer))
    if status:
        q = q.filter(Quotation.status == status)
    if customer_id:
        q = q.filter(Quotation.customer_id == customer_id)
    if search:
        q = q.join(Customer).filter(
            (Quotation.quotation_no.ilike(f"%{search}%")) |
            (Quotation.title.ilike(f"%{search}%")) |
            (Customer.name.ilike(f"%{search}%"))
        )
    total = q.count()
    items = q.order_by(desc(Quotation.created_at)).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [quotation_to_dict(item) for item in items]
    }


@router.post("/", status_code=201)
def create_quotation(data: QuotationCreate, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == data.customer_id).first()
    if not customer:
        raise HTTPException(404, "顧客が見つかりません")

    subtotal, tax, total = calc_totals(data.items)

    q = Quotation(
        quotation_no=generate_quotation_no(db),
        customer_id=data.customer_id,
        title=data.title,
        issue_date=data.issue_date,
        valid_until=data.valid_until,
        delivery_terms=data.delivery_terms,
        payment_terms=data.payment_terms,
        delivery_location=data.delivery_location,
        notes=data.notes,
        internal_notes=data.internal_notes,
        subtotal=subtotal,
        tax_amount=tax,
        total_amount=total,
    )
    db.add(q)
    db.flush()

    for item_data in data.items:
        item_amount = int(item_data.unit_price * item_data.quantity)
        option_total = sum(opt.price for opt in item_data.options)
        item = QuotationItem(
            quotation_id=q.id,
            line_no=item_data.line_no,
            product_id=item_data.product_id,
            item_name=item_data.item_name,
            description=item_data.description,
            quantity=item_data.quantity,
            unit=item_data.unit,
            unit_price=item_data.unit_price,
            amount=item_amount + option_total,
            notes=item_data.notes,
        )
        db.add(item)
        db.flush()

        for opt_data in item_data.options:
            opt = QuotationItemOption(
                quotation_item_id=item.id,
                option_id=opt_data.option_id,
                option_name=opt_data.option_name,
                price=opt_data.price,
                notes=opt_data.notes,
            )
            db.add(opt)

    db.commit()
    db.refresh(q)
    return quotation_to_dict(q)


@router.get("/{quotation_id}")
def get_quotation(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(Quotation).options(
        joinedload(Quotation.customer),
        joinedload(Quotation.items).joinedload(QuotationItem.options)
    ).filter(Quotation.id == quotation_id).first()
    if not q:
        raise HTTPException(404, "見積が見つかりません")
    return quotation_to_dict(q)


@router.put("/{quotation_id}")
def update_quotation(quotation_id: str, data: QuotationUpdate, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not q:
        raise HTTPException(404, "見積が見つかりません")

    for field, value in data.dict(exclude_none=True, exclude={"items"}).items():
        setattr(q, field, value)

    if data.items is not None:
        # 既存明細削除
        for item in q.items:
            db.delete(item)
        db.flush()

        subtotal, tax, total = calc_totals(data.items)
        q.subtotal = subtotal
        q.tax_amount = tax
        q.total_amount = total

        for item_data in data.items:
            item_amount = int(item_data.unit_price * item_data.quantity)
            option_total = sum(opt.price for opt in item_data.options)
            item = QuotationItem(
                quotation_id=q.id,
                line_no=item_data.line_no,
                product_id=item_data.product_id,
                item_name=item_data.item_name,
                description=item_data.description,
                quantity=item_data.quantity,
                unit=item_data.unit,
                unit_price=item_data.unit_price,
                amount=item_amount + option_total,
                notes=item_data.notes,
            )
            db.add(item)
            db.flush()
            for opt_data in item_data.options:
                opt = QuotationItemOption(
                    quotation_item_id=item.id,
                    option_id=opt_data.option_id,
                    option_name=opt_data.option_name,
                    price=opt_data.price,
                    notes=opt_data.notes,
                )
                db.add(opt)

    db.commit()
    db.refresh(q)
    return quotation_to_dict(q)


@router.post("/{quotation_id}/convert-to-order")
def convert_to_order(quotation_id: str, db: Session = Depends(get_db)):
    """見積から受注に変換"""
    q = db.query(Quotation).options(
        joinedload(Quotation.items).joinedload(QuotationItem.options)
    ).filter(Quotation.id == quotation_id).first()
    if not q:
        raise HTTPException(404, "見積が見つかりません")
    if q.status == "converted":
        raise HTTPException(400, "既に受注変換済みです")

    year = datetime.now().year
    prefix = f"SO{year}-"
    last = db.query(Order).filter(Order.order_no.like(f"{prefix}%")).order_by(desc(Order.order_no)).first()
    order_no = f"{prefix}{(int(last.order_no.split('-')[-1]) + 1 if last else 1):04d}"

    order = Order(
        order_no=order_no,
        quotation_id=q.id,
        customer_id=q.customer_id,
        title=q.title,
        order_date=date.today(),
        status="received",
        subtotal=q.subtotal,
        tax_rate=q.tax_rate,
        tax_amount=q.tax_amount,
        total_amount=q.total_amount,
        delivery_location=q.delivery_location,
        payment_terms=q.payment_terms,
        notes=q.notes,
    )
    db.add(order)
    db.flush()

    for i, qi in enumerate(q.items, 1):
        oi = OrderItem(
            order_id=order.id,
            line_no=qi.line_no,
            product_id=qi.product_id,
            item_name=qi.item_name,
            description=qi.description,
            quantity=qi.quantity,
            unit=qi.unit,
            unit_price=qi.unit_price,
            amount=qi.amount,
            notes=qi.notes,
        )
        db.add(oi)

    q.status = "converted"
    db.commit()
    return {"message": "受注に変換しました", "order_no": order_no, "order_id": str(order.id)}


@router.delete("/{quotation_id}", status_code=204)
def delete_quotation(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not q:
        raise HTTPException(404, "見積が見つかりません")
    db.delete(q)
    db.commit()
