"""マスタ管理 API（商社・納入先・従業員）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from pydantic import BaseModel
from app.db.models import get_db, pk_or_code, Agency, DeliveryDestination, Employee

router = APIRouter()

def to_dict(obj):
    return {k: (str(v) if hasattr(v, 'hex') else v)
            for k, v in obj.__dict__.items() if not k.startswith('_')}

# =============================================
# 商社マスタ
# =============================================
class AgencyIn(BaseModel):
    agency_code: str
    agency_name: str
    branch_name: Optional[str] = None
    trade_terms: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None

@router.get("/agencies")
def list_agencies(search: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Agency).filter(Agency.is_active == True)
    if search:
        q = q.filter(or_(Agency.agency_name.ilike(f"%{search}%"), Agency.agency_code.ilike(f"%{search}%")))
    return [to_dict(a) for a in q.order_by(Agency.agency_code).all()]

@router.post("/agencies", status_code=201)
def create_agency(data: AgencyIn, db: Session = Depends(get_db)):
    a = Agency(**data.dict())
    db.add(a); db.commit(); db.refresh(a)
    return to_dict(a)

@router.put("/agencies/{agency_id}")
def update_agency(agency_id: str, data: AgencyIn, db: Session = Depends(get_db)):
    a = db.query(Agency).filter(pk_or_code(Agency.id, Agency.agency_code, agency_id)).first()
    if not a: raise HTTPException(404)
    for k, v in data.dict().items(): setattr(a, k, v)
    db.commit(); db.refresh(a)
    return to_dict(a)

@router.delete("/agencies/{agency_id}", status_code=204)
def delete_agency(agency_id: str, db: Session = Depends(get_db)):
    a = db.query(Agency).filter(pk_or_code(Agency.id, Agency.agency_code, agency_id)).first()
    if not a: raise HTTPException(404)
    a.is_active = False; db.commit()

# =============================================
# 納入先マスタ
# =============================================
class DeliveryDestinationIn(BaseModel):
    customer_id: str
    company_name: str
    factory_name: Optional[str] = None
    company_factory_name: Optional[str] = None
    address: Optional[str] = None
    prefecture: Optional[str] = None
    postal_code: Optional[str] = None
    tel: Optional[str] = None
    fax: Optional[str] = None
    customer_rank: Optional[str] = None
    notes: Optional[str] = None

@router.get("/delivery-destinations")
def list_delivery_destinations(search: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(DeliveryDestination).filter(DeliveryDestination.is_active == True)
    if search:
        q = q.filter(or_(
            DeliveryDestination.company_name.ilike(f"%{search}%"),
            DeliveryDestination.factory_name.ilike(f"%{search}%"),
            DeliveryDestination.customer_id.ilike(f"%{search}%"),
        ))
    return [to_dict(d) for d in q.order_by(DeliveryDestination.customer_id).all()]

@router.post("/delivery-destinations", status_code=201)
def create_delivery_destination(data: DeliveryDestinationIn, db: Session = Depends(get_db)):
    d = DeliveryDestination(**data.dict())
    db.add(d); db.commit(); db.refresh(d)
    return to_dict(d)

@router.put("/delivery-destinations/{dest_id}")
def update_delivery_destination(dest_id: str, data: DeliveryDestinationIn, db: Session = Depends(get_db)):
    d = db.query(DeliveryDestination).filter(
        pk_or_code(DeliveryDestination.id, DeliveryDestination.customer_id, dest_id)
    ).first()
    if not d: raise HTTPException(404)
    for k, v in data.dict().items(): setattr(d, k, v)
    db.commit(); db.refresh(d)
    return to_dict(d)

@router.delete("/delivery-destinations/{dest_id}", status_code=204)
def delete_delivery_destination(dest_id: str, db: Session = Depends(get_db)):
    d = db.query(DeliveryDestination).filter(
        pk_or_code(DeliveryDestination.id, DeliveryDestination.customer_id, dest_id)
    ).first()
    if not d: raise HTTPException(404)
    d.is_active = False; db.commit()

# =============================================
# 従業員マスタ
# =============================================
class EmployeeIn(BaseModel):
    employee_code: str
    employee_name: str
    department: Optional[str] = None
    role: str = "staff"

@router.get("/employees")
def list_employees(search: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Employee).filter(Employee.is_active == True)
    if search:
        q = q.filter(or_(Employee.employee_name.ilike(f"%{search}%"), Employee.employee_code.ilike(f"%{search}%")))
    return [to_dict(e) for e in q.order_by(Employee.employee_code).all()]

@router.post("/employees", status_code=201)
def create_employee(data: EmployeeIn, db: Session = Depends(get_db)):
    e = Employee(**data.dict())
    db.add(e); db.commit(); db.refresh(e)
    return to_dict(e)

@router.put("/employees/{emp_id}")
def update_employee(emp_id: str, data: EmployeeIn, db: Session = Depends(get_db)):
    e = db.query(Employee).filter(
        pk_or_code(Employee.id, Employee.employee_code, emp_id)
    ).first()
    if not e: raise HTTPException(404)
    for k, v in data.dict().items(): setattr(e, k, v)
    db.commit(); db.refresh(e)
    return to_dict(e)

@router.delete("/employees/{emp_id}", status_code=204)
def delete_employee(emp_id: str, db: Session = Depends(get_db)):
    e = db.query(Employee).filter(
        pk_or_code(Employee.id, Employee.employee_code, emp_id)
    ).first()
    if not e: raise HTTPException(404)
    e.is_active = False; db.commit()
