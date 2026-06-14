"""商品管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from app.db.models import get_db, Product, ProductOption

router = APIRouter()

class ProductCreate(BaseModel):
    product_code: str
    name: str
    product_type: Optional[str] = None
    category: Optional[str] = None
    unit: str = "式"
    standard_price: int = 0
    cost_price: int = 0
    description: Optional[str] = None
    spec_json: Optional[dict] = None

def prod_to_dict(p):
    return {k: (str(v) if hasattr(v, 'hex') else (float(v) if hasattr(v, 'as_integer_ratio') else v))
            for k, v in p.__dict__.items() if not k.startswith('_')}

@router.get("/")
def list_products(
    page: int = Query(1, ge=1), per_page: int = Query(50),
    product_type: Optional[str] = None, search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Product).filter(Product.is_active == True)
    if product_type:
        q = q.filter(Product.product_type == product_type)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%") | Product.product_code.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(Product.product_code).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "items": [prod_to_dict(p) for p in items]}

@router.post("/", status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    p = Product(**data.dict())
    db.add(p)
    db.commit()
    db.refresh(p)
    return prod_to_dict(p)

@router.get("/options")
def list_options(product_type: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ProductOption).filter(ProductOption.is_active == True)
    if product_type:
        q = q.filter(ProductOption.applicable_product_type == product_type)
    return [prod_to_dict(o) for o in q.all()]

@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "商品が見つかりません")
    return prod_to_dict(p)

@router.put("/{product_id}")
def update_product(product_id: str, data: ProductCreate, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404)
    for k, v in data.dict().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return prod_to_dict(p)
