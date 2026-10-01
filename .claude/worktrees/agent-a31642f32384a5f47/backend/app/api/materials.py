"""仕入（発注）管理 API — 部材マスタ・BOMマスタ・部材発注"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.db.models import get_db, MaterialMaster, BomItem, MaterialOrder, Supplier, ProjectOrder
import uuid
from datetime import date

router = APIRouter()

# ---- 部材マスタ ----

@router.get("/materials")
def list_materials(search: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(MaterialMaster).filter(MaterialMaster.is_active == True)
    if search:
        q = q.filter(or_(
            MaterialMaster.material_name.ilike(f"%{search}%"),
            MaterialMaster.material_code.ilike(f"%{search}%")
        ))
    items = q.order_by(MaterialMaster.material_code).all()
    return [_mat_dict(m) for m in items]

@router.post("/materials")
def create_material(data: dict, db: Session = Depends(get_db)):
    m = MaterialMaster(
        material_code=data["material_code"],
        material_name=data["material_name"],
        unit=data.get("unit", "個"),
        default_supplier_id=data.get("default_supplier_id"),
        standard_lead_days=data.get("standard_lead_days", 14),
        notes=data.get("notes"),
    )
    db.add(m); db.commit(); db.refresh(m)
    return _mat_dict(m)

@router.put("/materials/{material_id}")
def update_material(material_id: str, data: dict, db: Session = Depends(get_db)):
    m = db.query(MaterialMaster).filter(MaterialMaster.id == material_id).first()
    if not m: raise HTTPException(404, "部材が見つかりません")
    for k in ["material_code","material_name","unit","default_supplier_id","standard_lead_days","notes"]:
        if k in data: setattr(m, k, data[k])
    db.commit(); db.refresh(m)
    return _mat_dict(m)

@router.delete("/materials/{material_id}")
def delete_material(material_id: str, db: Session = Depends(get_db)):
    m = db.query(MaterialMaster).filter(MaterialMaster.id == material_id).first()
    if not m: raise HTTPException(404)
    m.is_active = False; db.commit()
    return {"ok": True}

def _mat_dict(m: MaterialMaster):
    return {
        "id": str(m.id), "material_code": m.material_code, "material_name": m.material_name,
        "unit": m.unit, "default_supplier_id": str(m.default_supplier_id) if m.default_supplier_id else None,
        "default_supplier_name": m.default_supplier.name if m.default_supplier else None,
        "standard_lead_days": m.standard_lead_days, "notes": m.notes,
    }

# ---- BOMマスタ ----

@router.get("/bom")
def list_bom(product_type: str = Query(None), model_no: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(BomItem).options(joinedload(BomItem.material))
    if product_type: q = q.filter(BomItem.product_type == product_type)
    if model_no: q = q.filter(BomItem.model_no == model_no)
    return [_bom_dict(b) for b in q.order_by(BomItem.product_type, BomItem.model_no).all()]

@router.post("/bom")
def create_bom(data: dict, db: Session = Depends(get_db)):
    b = BomItem(
        product_type=data["product_type"], model_no=data["model_no"],
        material_id=data["material_id"], quantity=data.get("quantity", 1),
        unit=data.get("unit"), notes=data.get("notes"),
    )
    db.add(b); db.commit(); db.refresh(b)
    return _bom_dict(b)

@router.put("/bom/{bom_id}")
def update_bom(bom_id: str, data: dict, db: Session = Depends(get_db)):
    b = db.query(BomItem).filter(BomItem.id == bom_id).first()
    if not b: raise HTTPException(404)
    for k in ["product_type","model_no","material_id","quantity","unit","notes"]:
        if k in data: setattr(b, k, data[k])
    db.commit(); db.refresh(b)
    return _bom_dict(b)

@router.delete("/bom/{bom_id}")
def delete_bom(bom_id: str, db: Session = Depends(get_db)):
    b = db.query(BomItem).filter(BomItem.id == bom_id).first()
    if not b: raise HTTPException(404)
    db.delete(b); db.commit()
    return {"ok": True}

def _bom_dict(b: BomItem):
    return {
        "id": str(b.id), "product_type": b.product_type, "model_no": b.model_no,
        "material_id": str(b.material_id),
        "material_name": b.material.material_name if b.material else None,
        "material_code": b.material.material_code if b.material else None,
        "quantity": float(b.quantity), "unit": b.unit or (b.material.unit if b.material else None),
        "notes": b.notes,
    }

# ---- BOM展開（受注から必要部材を自動展開）----

@router.get("/bom/expand")
def expand_bom(order_id: str = Query(...), db: Session = Depends(get_db)):
    """受注IDから見積の型番を読み取り、BOMマスタで展開して必要部材リストを返す"""
    from app.db.models import QuotationHeader, QuotationLineItem
    # 受注に紐づく見積書の明細から product_type + model_no を取得
    order = db.query(ProjectOrder).filter(ProjectOrder.id == order_id).first()
    if not order: raise HTTPException(404)

    # QuotationLineItemのspec_jsonまたはitem_nameから型番マッチング
    quotations = db.query(QuotationHeader).filter(
        QuotationHeader.project_order_id == order_id
    ).all()
    if not quotations and order.quotation_id:
        quotations = db.query(QuotationHeader).filter(
            QuotationHeader.id == order.quotation_id
        ).all()

    # 見積明細から product_type を収集
    needed_types = set()
    for q in quotations:
        for item in q.line_items:
            if item.product_type:
                needed_types.add((item.product_type, item.spec_detail or ""))

    # BOMマスタで展開
    result = []
    for pt, spec in needed_types:
        # model_no部分マッチ
        bom_items = db.query(BomItem).options(joinedload(BomItem.material)).filter(
            BomItem.product_type == pt
        ).all()
        # specからmodel_noを推測（部分一致）
        matched = [b for b in bom_items if not b.model_no or b.model_no.lower() in (spec or "").lower()]
        if not matched:
            matched = bom_items  # マッチしなければ全件
        for b in matched:
            result.append({
                **_bom_dict(b),
                "product_type": pt, "spec": spec,
            })

    # 既存の発注状況もマージ
    existing_orders = {str(mo.material_id): mo for mo in
        db.query(MaterialOrder).filter(MaterialOrder.project_order_id == order_id).all()}

    for r in result:
        mo = existing_orders.get(r["material_id"])
        r["order_status"] = mo.status if mo else "未発注"
        r["material_order_id"] = str(mo.id) if mo else None

    return {"order_id": order_id, "child_no": order.child_no, "items": result}

# ---- 部材発注管理 ----

@router.get("/material-orders")
def list_material_orders(order_id: str = Query(None), status: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(MaterialOrder).options(
        joinedload(MaterialOrder.material), joinedload(MaterialOrder.supplier),
        joinedload(MaterialOrder.project_order)
    )
    if order_id: q = q.filter(MaterialOrder.project_order_id == order_id)
    if status: q = q.filter(MaterialOrder.status == status)
    return [_mo_dict(mo) for mo in q.order_by(MaterialOrder.created_at.desc()).all()]

@router.post("/material-orders")
def create_material_order(data: dict, db: Session = Depends(get_db)):
    mo = MaterialOrder(
        project_order_id=data.get("project_order_id"),
        material_id=data["material_id"],
        supplier_id=data.get("supplier_id"),
        order_qty=data.get("order_qty"),
        unit_price=data.get("unit_price"),
        order_date=data.get("order_date"),
        due_date=data.get("due_date"),
        status=data.get("status", "未発注"),
        notes=data.get("notes"),
    )
    db.add(mo); db.commit(); db.refresh(mo)
    return _mo_dict(mo)

@router.put("/material-orders/{mo_id}")
def update_material_order(mo_id: str, data: dict, db: Session = Depends(get_db)):
    mo = db.query(MaterialOrder).filter(MaterialOrder.id == mo_id).first()
    if not mo: raise HTTPException(404)
    for k in ["supplier_id","order_qty","unit_price","order_date","due_date","received_date","status","notes"]:
        if k in data: setattr(mo, k, data[k])
    db.commit(); db.refresh(mo)
    return _mo_dict(mo)

@router.delete("/material-orders/{mo_id}")
def delete_material_order(mo_id: str, db: Session = Depends(get_db)):
    mo = db.query(MaterialOrder).filter(MaterialOrder.id == mo_id).first()
    if not mo: raise HTTPException(404)
    db.delete(mo); db.commit()
    return {"ok": True}

@router.get("/suppliers")
def list_suppliers(search: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Supplier).filter(Supplier.is_active == True)
    if search: q = q.filter(Supplier.name.ilike(f"%{search}%"))
    return [{"id": str(s.id), "name": s.name, "supplier_code": s.supplier_code,
             "contact_person": s.contact_person, "phone": s.phone, "email": s.email}
            for s in q.order_by(Supplier.supplier_code).all()]

def _mo_dict(mo: MaterialOrder):
    return {
        "id": str(mo.id),
        "project_order_id": str(mo.project_order_id) if mo.project_order_id else None,
        "child_no": mo.project_order.child_no if mo.project_order else None,
        "material_id": str(mo.material_id),
        "material_name": mo.material.material_name if mo.material else None,
        "material_code": mo.material.material_code if mo.material else None,
        "unit": mo.material.unit if mo.material else None,
        "supplier_id": str(mo.supplier_id) if mo.supplier_id else None,
        "supplier_name": mo.supplier.name if mo.supplier else None,
        "order_qty": float(mo.order_qty) if mo.order_qty else None,
        "unit_price": float(mo.unit_price) if mo.unit_price else None,
        "order_date": str(mo.order_date) if mo.order_date else None,
        "due_date": str(mo.due_date) if mo.due_date else None,
        "received_date": str(mo.received_date) if mo.received_date else None,
        "status": mo.status, "notes": mo.notes,
    }
