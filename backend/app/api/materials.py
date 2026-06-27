"""仕入（発注）管理 API — 部材マスタ・BOMマスタ・部材発注"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.db.models import get_db, MaterialMaster, BomItem, MaterialOrder, Supplier, ProjectOrder, UnitMaster, UnitMaterialBom, QuotationHeader
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

# ---- ユニットから部材を一括取込（方式B: マスタ由来の自動セット）----

@router.get("/units")
def list_bom_units(search: str = Query(None), db: Session = Depends(get_db)):
    """発注用: ユニットマスタ一覧（部材紐付け数つき）"""
    q = db.query(UnitMaster).filter(UnitMaster.is_active == True)
    if search:
        q = q.filter(or_(
            UnitMaster.unit_name.ilike(f"%{search}%"),
            UnitMaster.unit_code.ilike(f"%{search}%"),
            UnitMaster.model_no.ilike(f"%{search}%"),
        ))
    units = q.order_by(UnitMaster.unit_code).all()
    return [{
        "id": str(u.id), "unit_code": u.unit_code, "unit_name": u.unit_name,
        "unit_type": u.unit_type, "model_no": u.model_no,
        "material_count": len(u.materials) if u.materials else 0,
    } for u in units]

@router.get("/units/{unit_id}/materials")
def preview_unit_materials(unit_id: str, db: Session = Depends(get_db)):
    """発注プレビュー: ユニットに紐づく部材（員数つき）"""
    rows = db.query(UnitMaterialBom).options(joinedload(UnitMaterialBom.material)).filter(
        UnitMaterialBom.unit_id == unit_id
    ).order_by(UnitMaterialBom.sort_order).all()
    return [{
        "material_id": str(r.material_id),
        "material_code": r.material.material_code if r.material else None,
        "material_name": r.material.material_name if r.material else None,
        "unit": r.material.unit if r.material else None,
        "quantity": float(r.quantity),
        "default_supplier_id": str(r.material.default_supplier_id) if r.material and r.material.default_supplier_id else None,
        "default_supplier_name": r.material.default_supplier.name if r.material and r.material.default_supplier else None,
    } for r in rows]

def _unit_brief(u: UnitMaster, quantity: float):
    return {
        "unit_id": str(u.id), "unit_code": u.unit_code, "unit_name": u.unit_name,
        "unit_type": u.unit_type, "model_no": u.model_no,
        "quantity": quantity,
        "material_count": len(u.materials) if u.materials else 0,
    }

@router.get("/adopted-units")
def adopted_units(project_order_id: str = Query(...), db: Session = Depends(get_db)):
    """案件子IDの受注採用見積（status=adopted）の明細から、選択されているユニットを抽出。
    見積明細の spec_json（fan_model / rv_model / cyclone_model / model）を
    ユニットマスタの model_no と突合する。"""
    po = db.query(ProjectOrder).filter(ProjectOrder.id == project_order_id).first()

    # 採用見積の特定: ①status=adopted を優先 ②案件子IDに記録された採用見積番号(po.quotation_no)で補完
    q = db.query(QuotationHeader).filter(
        QuotationHeader.project_order_id == project_order_id,
        QuotationHeader.status == "adopted",
    ).first()
    if not q and po and po.quotation_no:
        q = db.query(QuotationHeader).filter(
            QuotationHeader.quotation_no == po.quotation_no
        ).order_by(QuotationHeader.created_at.desc()).first()
    if not q:
        return {"quotation_no": None, "units": [], "message": "受注採用された見積がありません"}

    # 明細から (model識別子, 数量) を収集
    candidates = []
    for it in q.line_items:
        sj = it.spec_json or {}
        qty = float(it.quantity or 1)
        for key in ("fan_model", "rv_model", "cyclone_model", "model"):
            val = sj.get(key)
            if val:
                candidates.append((str(val), qty))

    # ユニットマスタの model_no と突合（重複ユニットは数量を合算）
    matched: dict = {}
    for model_no, qty in candidates:
        u = db.query(UnitMaster).filter(
            UnitMaster.model_no == model_no, UnitMaster.is_active == True
        ).first()
        if not u:
            continue
        key = str(u.id)
        if key in matched:
            matched[key]["quantity"] += qty
        else:
            matched[key] = _unit_brief(u, qty)

    return {"quotation_no": q.quotation_no, "units": list(matched.values())}

@router.post("/material-orders/from-units")
def create_orders_from_units(data: dict, db: Session = Depends(get_db)):
    """複数ユニットの部材をまとめて発注起票。units=[{unit_id, multiplier}]"""
    project_order_id = data.get("project_order_id") or None
    due_date = data.get("due_date")
    units = data.get("units") or []
    if not units:
        raise HTTPException(400, "ユニットが選択されていません")

    total = 0
    for entry in units:
        unit_id = entry.get("unit_id")
        multiplier = float(entry.get("multiplier", 1) or 1)
        unit = db.query(UnitMaster).filter(UnitMaster.id == unit_id).first()
        if not unit:
            continue
        rows = db.query(UnitMaterialBom).options(joinedload(UnitMaterialBom.material)).filter(
            UnitMaterialBom.unit_id == unit_id
        ).order_by(UnitMaterialBom.sort_order).all()
        for r in rows:
            mat = r.material
            db.add(MaterialOrder(
                project_order_id=project_order_id,
                material_id=r.material_id,
                supplier_id=mat.default_supplier_id if mat else None,
                order_qty=float(r.quantity) * multiplier,
                due_date=due_date,
                status="未発注",
                notes=f"ユニット取込: {unit.unit_code} {unit.unit_name}",
            ))
            total += 1
    db.commit()
    return {"ok": True, "created": total, "message": f"{len(units)}ユニットの部材 {total}件を発注起票しました"}

@router.post("/material-orders/from-unit")
def create_orders_from_unit(data: dict, db: Session = Depends(get_db)):
    """ユニットに紐づく部材を一括で発注起票（員数 × 台数）。優先仕入先を自動セット"""
    unit_id = data.get("unit_id")
    project_order_id = data.get("project_order_id") or None
    multiplier = float(data.get("multiplier", 1) or 1)
    due_date = data.get("due_date")

    unit = db.query(UnitMaster).filter(UnitMaster.id == unit_id).first()
    if not unit:
        raise HTTPException(404, "ユニットが見つかりません")

    rows = db.query(UnitMaterialBom).options(joinedload(UnitMaterialBom.material)).filter(
        UnitMaterialBom.unit_id == unit_id
    ).order_by(UnitMaterialBom.sort_order).all()
    if not rows:
        raise HTTPException(400, "このユニットに紐づく部材がありません")

    created = 0
    for r in rows:
        mat = r.material
        db.add(MaterialOrder(
            project_order_id=project_order_id,
            material_id=r.material_id,
            supplier_id=mat.default_supplier_id if mat else None,
            order_qty=float(r.quantity) * multiplier,
            due_date=due_date,
            status="未発注",
            notes=f"ユニット取込: {unit.unit_code} {unit.unit_name}",
        ))
        created += 1
    db.commit()
    return {"ok": True, "created": created, "message": f"{unit.unit_name} の部材 {created}件を発注起票しました"}

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
