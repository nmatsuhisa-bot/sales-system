"""顧客管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from pydantic import BaseModel
from app.db.models import get_db, Customer

router = APIRouter()

class CustomerCreate(BaseModel):
    customer_code: str
    name: str
    name_kana: Optional[str] = None
    postal_code: Optional[str] = None
    prefecture: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    contact_person: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None

def customer_to_dict(c):
    return {k: (str(v) if hasattr(v, 'hex') else v)
            for k, v in c.__dict__.items() if not k.startswith('_')}

@router.get("/")
def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Customer).filter(Customer.is_active == True)
    if search:
        q = q.filter(Customer.name.ilike(f"%{search}%") | Customer.customer_code.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(Customer.name).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "items": [customer_to_dict(c) for c in items]}

@router.post("/", status_code=201)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    c = Customer(**data.dict())
    db.add(c)
    db.commit()
    db.refresh(c)
    return customer_to_dict(c)

@router.get("/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(404, "顧客が見つかりません")
    return customer_to_dict(c)

@router.put("/{customer_id}")
def update_customer(customer_id: str, data: CustomerCreate, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(404, "顧客が見つかりません")
    for k, v in data.dict().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return customer_to_dict(c)

@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: str, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(404)
    c.is_active = False
    db.commit()
