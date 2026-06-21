"""案件管理 API（親案件 + 子受注NO）
親ID: 案件ID_親（例: 260010）
子ID: 案件ID_子（例: 260010_02）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, func
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
from app.db.models import get_db, Project, ProjectOrder, ProjectOrderQuotation

router = APIRouter()

class ProjectOrderQuotationIn(BaseModel):
    quotation_no: Optional[str] = None
    quotation_total: Optional[int] = None
    quotation_issue_date: Optional[date] = None
    quotation_id: Optional[str] = None

class ProjectOrderCreate(BaseModel):
    child_no: Optional[str] = None
    project_name: Optional[str] = None
    project_summary: Optional[str] = None
    customer_code: Optional[str] = None
    customer_name: Optional[str] = None
    agency_code: Optional[str] = None
    agency_name: Optional[str] = None
    sales_person_name: Optional[str] = None
    sales_person_code: Optional[str] = None
    status: Optional[str] = None
    quotation_amount: Optional[int] = None
    budget_amount: Optional[int] = None
    sales_date: Optional[date] = None
    inquiry_date: Optional[date] = None
    order_date: Optional[date] = None
    expected_order_date: Optional[date] = None
    shipment_date: Optional[date] = None
    expected_shipment_date: Optional[date] = None
    quotation_no: Optional[str] = None
    quotation_total: Optional[int] = None
    quotation_issue_date: Optional[date] = None
    linked_quotations: List[ProjectOrderQuotationIn] = []
    notes: Optional[str] = None

class ProjectCreate(BaseModel):
    project_no: str
    seq_no: Optional[str] = None
    project_name: Optional[str] = None
    project_summary: Optional[str] = None
    customer_code_1: Optional[str] = None
    customer_name_1: Optional[str] = None
    customer_code_2: Optional[str] = None
    customer_name_2: Optional[str] = None
    sales_person_name: Optional[str] = None
    sales_person_code: Optional[str] = None
    status: str = "営業中"
    distribution_type: Optional[str] = None
    budget_amount: Optional[int] = None
    estimated_sales_total: Optional[int] = None
    final_order_amount: Optional[int] = None
    cost_price: Optional[int] = None
    profit_amount: Optional[int] = None
    profit_rate: Optional[float] = None
    inquiry_date: Optional[date] = None
    sales_date: Optional[date] = None
    drawing_request_date: Optional[date] = None
    order_date: Optional[date] = None
    expected_order_date: Optional[date] = None
    expected_shipment_date: Optional[date] = None
    created_date: Optional[date] = None
    notes: Optional[str] = None
    orders: List[ProjectOrderCreate] = []

class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    project_summary: Optional[str] = None
    customer_code_1: Optional[str] = None
    customer_name_1: Optional[str] = None
    customer_code_2: Optional[str] = None
    customer_name_2: Optional[str] = None
    sales_person_name: Optional[str] = None
    sales_person_code: Optional[str] = None
    status: Optional[str] = None
    distribution_type: Optional[str] = None
    budget_amount: Optional[int] = None
    estimated_sales_total: Optional[int] = None
    final_order_amount: Optional[int] = None
    cost_price: Optional[int] = None
    profit_amount: Optional[int] = None
    profit_rate: Optional[float] = None
    inquiry_date: Optional[date] = None
    sales_date: Optional[date] = None
    drawing_request_date: Optional[date] = None
    order_date: Optional[date] = None
    expected_order_date: Optional[date] = None
    expected_shipment_date: Optional[date] = None
    notes: Optional[str] = None

def _d(v): return v.isoformat() if v else None
def _i(v): return int(v) if v is not None else None

def order_to_dict(o: ProjectOrder) -> dict:
    return {
        "id": str(o.id), "child_no": o.child_no,
        "project_id": str(o.project_id), "project_no": o.project_no,
        "project_name": o.project_name, "project_summary": o.project_summary,
        "customer_code": o.customer_code, "customer_name": o.customer_name,
        "agency_code": o.agency_code, "agency_name": o.agency_name,
        "sales_person_name": o.sales_person_name, "sales_person_code": o.sales_person_code,
        "status": o.status,
        "quotation_amount": _i(o.quotation_amount), "budget_amount": _i(o.budget_amount),
        "sales_date": _d(o.sales_date), "inquiry_date": _d(o.inquiry_date),
        "order_date": _d(o.order_date), "expected_order_date": _d(o.expected_order_date),
        "shipment_date": _d(o.shipment_date), "expected_shipment_date": _d(o.expected_shipment_date),
        "quotation_no": o.quotation_no, "quotation_total": _i(o.quotation_total),
        "quotation_issue_date": _d(o.quotation_issue_date),
        "quotation_id": str(o.quotation_id) if o.quotation_id else None,
        "order_id": str(o.order_id) if o.order_id else None,
        "notes": o.notes,
        "linked_quotations": [
            {"id": str(q.id), "quotation_no": q.quotation_no,
             "quotation_total": _i(q.quotation_total), "quotation_issue_date": _d(q.quotation_issue_date)}
            for q in (o.linked_quotations or [])
        ],
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }

def project_to_dict(p: Project, include_orders: bool = True) -> dict:
    d = {
        "id": str(p.id), "project_no": p.project_no, "seq_no": p.seq_no,
        "project_name": p.project_name, "project_summary": p.project_summary,
        "customer_code_1": p.customer_code_1, "customer_name_1": p.customer_name_1,
        "customer_code_2": p.customer_code_2, "customer_name_2": p.customer_name_2,
        "sales_person_name": p.sales_person_name, "sales_person_code": p.sales_person_code,
        "status": p.status, "distribution_type": p.distribution_type,
        "budget_amount": _i(p.budget_amount), "estimated_sales_total": _i(p.estimated_sales_total),
        "final_order_amount": _i(p.final_order_amount), "cost_price": _i(p.cost_price),
        "profit_amount": _i(p.profit_amount),
        "profit_rate": float(p.profit_rate) if p.profit_rate is not None else None,
        "inquiry_date": _d(p.inquiry_date), "sales_date": _d(p.sales_date),
        "drawing_request_date": _d(p.drawing_request_date),
        "order_date": _d(p.order_date), "expected_order_date": _d(p.expected_order_date),
        "expected_shipment_date": _d(p.expected_shipment_date),
        "created_date": _d(p.created_date), "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if include_orders and hasattr(p, 'project_orders'):
        orders = sorted(p.project_orders, key=lambda x: x.child_no or "")
        d["orders"] = [order_to_dict(o) for o in orders]
        d["order_count"] = len(orders)
        d["total_quotation_amount"] = sum(_i(o.quotation_amount) or 0 for o in orders)
    return d

def generate_child_no(project_no: str, db: Session) -> str:
    from sqlalchemy import text as sa_text
    db.execute(sa_text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"child_no_{project_no}"})
    existing = db.query(ProjectOrder).filter(ProjectOrder.project_no == project_no).all()
    max_seq = max(
        (int(o.child_no.split("_")[-1]) for o in existing
         if o.child_no and "_" in o.child_no and o.child_no.split("_")[-1].isdigit()),
        default=0
    )
    return f"{project_no}_{(max_seq + 1):02d}"

def _make_order(data: ProjectOrderCreate, project_id, project_no: str, db: Session) -> ProjectOrder:
    child_no = data.child_no or generate_child_no(project_no, db)
    fields = data.dict(exclude={"child_no", "linked_quotations"})
    o = ProjectOrder(child_no=child_no, project_id=project_id, project_no=project_no, **fields)
    db.add(o)
    db.flush()
    for qd in data.linked_quotations:
        db.add(ProjectOrderQuotation(project_order_id=o.id, **qd.dict()))
    return o

@router.get("/stats")
def project_stats(db: Session = Depends(get_db)):
    status_counts = db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
    dist_counts = db.query(Project.distribution_type, func.count(Project.id)).group_by(Project.distribution_type).all()
    person_stats = db.query(
        Project.sales_person_name, func.count(Project.id).label("cnt"), func.sum(Project.final_order_amount).label("total")
    ).filter(Project.sales_person_name.isnot(None)).group_by(Project.sales_person_name).order_by(desc("cnt")).all()
    return {
        "status_counts": {(s or "未設定"): c for s, c in status_counts},
        "distribution_counts": {(d or "未設定"): c for d, c in dist_counts},
        "by_sales_person": [{"name": n, "count": c, "total": _i(t)} for n, c, t in person_stats],
    }

@router.get("/")
def list_projects(
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None, sales_person_code: Optional[str] = None,
    distribution_type: Optional[str] = None, search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Project).options(joinedload(Project.project_orders).joinedload(ProjectOrder.linked_quotations))
    if status: q = q.filter(Project.status == status)
    if sales_person_code: q = q.filter(Project.sales_person_code == sales_person_code)
    if distribution_type: q = q.filter(Project.distribution_type == distribution_type)
    if search:
        q = q.filter(or_(
            Project.project_no.ilike(f"%{search}%"), Project.project_name.ilike(f"%{search}%"),
            Project.customer_name_1.ilike(f"%{search}%"), Project.customer_name_2.ilike(f"%{search}%"),
            Project.sales_person_name.ilike(f"%{search}%"),
        ))
    total = q.count()
    items = q.order_by(desc(Project.project_no)).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "page": page, "per_page": per_page, "items": [project_to_dict(p) for p in items]}

@router.post("/", status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    from sqlalchemy import text as sa_text
    db.execute(sa_text("SELECT pg_advisory_xact_lock(hashtext('project_no_lock'))"))
    if db.query(Project).filter(Project.project_no == data.project_no).first():
        raise HTTPException(400, f"案件NO {data.project_no} は既に存在します")
    p = Project(**data.dict(exclude={"orders"}))
    db.add(p)
    db.flush()
    for od in data.orders:
        _make_order(od, p.id, data.project_no, db)
    db.commit()
    db.refresh(p)
    return project_to_dict(p)

@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    p = db.query(Project).options(
        joinedload(Project.project_orders).joinedload(ProjectOrder.linked_quotations)
    ).filter(or_(Project.id == project_id, Project.project_no == project_id)).first()
    if not p: raise HTTPException(404, "案件が見つかりません")
    return project_to_dict(p)

@router.put("/{project_id}")
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.query(Project).filter(or_(Project.id == project_id, Project.project_no == project_id)).first()
    if not p: raise HTTPException(404)
    for k, v in data.dict(exclude_none=True).items():
        setattr(p, k, v)
    db.commit()
    return project_to_dict(p, include_orders=False)

@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    p = db.query(Project).filter(or_(Project.id == project_id, Project.project_no == project_id)).first()
    if not p: raise HTTPException(404)
    db.delete(p); db.commit()

@router.post("/{project_id}/orders", status_code=201)
def add_project_order(project_id: str, data: ProjectOrderCreate, db: Session = Depends(get_db)):
    p = db.query(Project).filter(or_(Project.id == project_id, Project.project_no == project_id)).first()
    if not p: raise HTTPException(404)
    o = _make_order(data, p.id, p.project_no, db)
    db.commit(); db.refresh(o)
    return order_to_dict(o)

@router.get("/orders/search")
def search_project_orders(q: str = Query(""), db: Session = Depends(get_db)):
    """案件ID（親）または子IDで受注を検索。製造計画・工程管理の子ID選択に使用。"""
    if not q.strip():
        return []
    keyword = q.strip()
    orders = db.query(ProjectOrder).filter(
        or_(
            ProjectOrder.child_no.ilike(f"%{keyword}%"),
            ProjectOrder.project_no.ilike(f"%{keyword}%"),
            ProjectOrder.project_name.ilike(f"%{keyword}%"),
            ProjectOrder.customer_name.ilike(f"%{keyword}%"),
        )
    ).order_by(ProjectOrder.child_no).limit(30).all()
    return [
        {
            "id": str(o.id),
            "child_no": o.child_no,
            "project_no": o.project_no,
            "project_name": o.project_name,
            "customer_name": o.customer_name,
            "sales_person_name": o.sales_person_name,
            "sales_date": str(o.sales_date) if o.sales_date else None,
            "status": o.status,
        }
        for o in orders
    ]

@router.get("/orders/{order_id}")
def get_project_order(order_id: str, db: Session = Depends(get_db)):
    """子受注（案件ID_子）を単体取得。見積作成時の顧客名・納入先の自動補完に使用。"""
    o = db.query(ProjectOrder).options(
        joinedload(ProjectOrder.linked_quotations)
    ).filter(or_(ProjectOrder.id == order_id, ProjectOrder.child_no == order_id)).first()
    if not o: raise HTTPException(404, "受注が見つかりません")
    return order_to_dict(o)

@router.put("/orders/{order_id}")
def update_project_order(order_id: str, data: ProjectOrderCreate, db: Session = Depends(get_db)):
    o = db.query(ProjectOrder).filter(or_(ProjectOrder.id == order_id, ProjectOrder.child_no == order_id)).first()
    if not o: raise HTTPException(404)
    for k, v in data.dict(exclude={"child_no", "linked_quotations"}, exclude_none=True).items():
        setattr(o, k, v)
    if data.linked_quotations is not None:
        for lq in o.linked_quotations: db.delete(lq)
        db.flush()
        for qd in data.linked_quotations:
            db.add(ProjectOrderQuotation(project_order_id=o.id, **qd.dict()))
    db.commit(); db.refresh(o)
    return order_to_dict(o)

@router.delete("/orders/{order_id}", status_code=204)
def delete_project_order(order_id: str, db: Session = Depends(get_db)):
    o = db.query(ProjectOrder).filter(or_(ProjectOrder.id == order_id, ProjectOrder.child_no == order_id)).first()
    if not o: raise HTTPException(404)
    db.delete(o); db.commit()

@router.post("/orders/{order_id}/link-quotation")
def link_quotation(order_id: str, quotation_id: str, db: Session = Depends(get_db)):
    # B003修正: 旧Quotationモデルから新QuotationHeaderモデルへ
    from app.db.models import QuotationHeader
    o = db.query(ProjectOrder).filter(or_(ProjectOrder.id == order_id, ProjectOrder.child_no == order_id)).first()
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not o or not q: raise HTTPException(404)
    # project_orders.quotation_id はFK制約が旧テーブルを参照するため書き込まない
    o.quotation_no = q.quotation_no
    o.quotation_total = q.total_amount
    o.quotation_amount = q.total_amount
    o.quotation_issue_date = q.issue_date
    exists = db.query(ProjectOrderQuotation).filter(
        ProjectOrderQuotation.project_order_id == o.id,
        ProjectOrderQuotation.quotation_no == q.quotation_no
    ).first()
    if not exists:
        # B001対応: ProjectOrderQuotationのquotation_idも旧FK制約があるため書き込まない
        db.add(ProjectOrderQuotation(project_order_id=o.id, quotation_no=q.quotation_no,
            quotation_total=q.total_amount, quotation_issue_date=q.issue_date))
    db.flush()
    # 親案件の最終受注金額を子ID合計で自動更新
    if o.project_id:
        total = db.query(func.sum(ProjectOrder.quotation_total)).filter(
            ProjectOrder.project_id == o.project_id
        ).scalar() or 0
        parent = db.query(Project).filter(Project.id == o.project_id).first()
        if parent:
            parent.final_order_amount = int(total)
    db.commit()
    return {"message": "見積を紐付けました", "quotation_no": q.quotation_no}
