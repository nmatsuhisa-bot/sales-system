"""仕入（発注）管理 API — 部材マスタ・BOMマスタ・部材発注・発注書"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func as safunc
from app.db.models import (
    get_db, MaterialMaster, BomItem, MaterialOrder, Supplier, ProjectOrder,
    UnitMaster, UnitMaterialBom, QuotationHeader, MaterialPurchaseOrder, MaterialStockMovement,
)
import uuid, io
from datetime import date

router = APIRouter()

PO_STATUS = ["作成中", "発注済", "一部入荷", "入荷済", "キャンセル"]

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
    po_id = data.get("purchase_order_id") or None
    project_order_id = data.get("project_order_id")
    supplier_id = data.get("supplier_id")
    # 発注書配下の明細は、案件子ID・仕入先をヘッダーから継承（未指定時）
    if po_id:
        po = db.query(MaterialPurchaseOrder).filter(MaterialPurchaseOrder.id == po_id).first()
        if po:
            project_order_id = project_order_id or (str(po.project_order_id) if po.project_order_id else None)
            supplier_id = supplier_id or (str(po.supplier_id) if po.supplier_id else None)
    mo = MaterialOrder(
        purchase_order_id=po_id,
        project_order_id=project_order_id,
        material_id=data["material_id"],
        supplier_id=supplier_id,
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
    if total == 0:
        return {"ok": False, "created": 0,
                "message": "部材が未登録のため起票されませんでした。製品BOMマスタ→ユニット構成で各ユニットに部材を登録してください"}
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

@router.post("/material-orders/{mo_id}/allocate-stock")
def allocate_from_stock(mo_id: str, db: Session = Depends(get_db)):
    """発注明細を在庫から引き当て（在庫を order_qty 分減算し、明細を「在庫引当」にする）"""
    mo = db.query(MaterialOrder).filter(MaterialOrder.id == mo_id).first()
    if not mo: raise HTTPException(404)
    qty = float(mo.order_qty or 0)
    if qty <= 0: raise HTTPException(400, "数量が未設定です")
    db.add(MaterialStockMovement(
        material_id=mo.material_id, movement_type="引当", quantity=-qty,
        movement_date=date.today().isoformat(),
        project_order_id=mo.project_order_id,
        purchase_order_id=mo.purchase_order_id,
        notes=f"発注明細から在庫引当",
    ))
    mo.status = "在庫引当"
    db.commit()
    stock = db.query(safunc.coalesce(safunc.sum(MaterialStockMovement.quantity), 0)).filter(
        MaterialStockMovement.material_id == mo.material_id).scalar()
    return {"ok": True, "stock": float(stock or 0)}

@router.post("/material-orders/{mo_id}/receive")
def receive_material_order_line(mo_id: str, data: dict, db: Session = Depends(get_db)):
    """発注明細の入荷登録：実入荷数量を在庫に加算（入荷）し、明細を入荷済にする。"""
    mo = db.query(MaterialOrder).filter(MaterialOrder.id == mo_id).first()
    if not mo: raise HTTPException(404)
    qty = float(data.get("quantity") if data.get("quantity") not in (None, "") else (mo.order_qty or 0))
    if qty <= 0: raise HTTPException(400, "入荷数量が未設定です")
    db.add(MaterialStockMovement(
        material_id=mo.material_id, movement_type="入荷", quantity=qty,
        movement_date=data.get("received_date") or date.today().isoformat(),
        project_order_id=mo.project_order_id, purchase_order_id=mo.purchase_order_id,
        notes="発注入荷",
    ))
    mo.received_date = data.get("received_date") or date.today().isoformat()
    mo.status = "入荷済"
    db.commit()
    stock = db.query(safunc.coalesce(safunc.sum(MaterialStockMovement.quantity), 0)).filter(
        MaterialStockMovement.material_id == mo.material_id).scalar()
    return {"ok": True, "stock": float(stock or 0)}

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
        "purchase_order_id": str(mo.purchase_order_id) if mo.purchase_order_id else None,
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


# =============================================
# 発注書（発注番号ヘッダー）
# =============================================

def _gen_po_no(db: Session) -> str:
    year = date.today().year
    prefix = f"PO{year}-"
    last = db.query(MaterialPurchaseOrder).filter(
        MaterialPurchaseOrder.po_no.like(f"{prefix}%")
    ).order_by(MaterialPurchaseOrder.po_no.desc()).first()
    seq = (int(last.po_no.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:04d}"

def _po_dict(po: MaterialPurchaseOrder, with_lines: bool = False):
    lines = po.lines or []
    total = sum(float(l.order_qty or 0) * float(l.unit_price or 0) for l in lines)
    d = {
        "id": str(po.id), "po_no": po.po_no, "status": po.status,
        "project_order_id": str(po.project_order_id) if po.project_order_id else None,
        "child_no": po.project_order.child_no if po.project_order else None,
        "project_name": po.project_order.project_name if po.project_order else None,
        "supplier_id": str(po.supplier_id) if po.supplier_id else None,
        "supplier_name": po.supplier.name if po.supplier else None,
        "order_date": str(po.order_date) if po.order_date else None,
        "delivery_place": po.delivery_place, "seiban": po.seiban, "title": po.title,
        "notes": po.notes, "line_count": len(lines), "total_amount": int(total),
    }
    if with_lines:
        d["lines"] = [_mo_dict(l) for l in sorted(lines, key=lambda x: str(x.created_at))]
    return d

@router.post("/purchase-orders")
def create_purchase_order(data: dict, db: Session = Depends(get_db)):
    """発注書を手動で新規作成（発番）。明細は別途 material-orders で追加。"""
    header = MaterialPurchaseOrder(
        po_no=_gen_po_no(db),
        project_order_id=data.get("project_order_id") or None,
        supplier_id=data.get("supplier_id") or None,
        order_date=data.get("order_date") or date.today(),
        delivery_place=data.get("delivery_place"),
        seiban=data.get("seiban"),
        title=data.get("title"),
        status=data.get("status", "作成中"),
        notes=data.get("notes"),
    )
    db.add(header); db.commit(); db.refresh(header)
    return _po_dict(header)

@router.get("/purchase-orders")
def list_purchase_orders(status: str = Query(None), project_order_id: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(MaterialPurchaseOrder).options(
        joinedload(MaterialPurchaseOrder.supplier),
        joinedload(MaterialPurchaseOrder.project_order),
        joinedload(MaterialPurchaseOrder.lines),
    )
    if status: q = q.filter(MaterialPurchaseOrder.status == status)
    if project_order_id: q = q.filter(MaterialPurchaseOrder.project_order_id == project_order_id)
    pos = q.order_by(MaterialPurchaseOrder.po_no.desc()).all()
    return [_po_dict(po) for po in pos]

@router.get("/purchase-orders/{po_id}")
def get_purchase_order(po_id: str, db: Session = Depends(get_db)):
    po = db.query(MaterialPurchaseOrder).filter(MaterialPurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404)
    return _po_dict(po, with_lines=True)

@router.put("/purchase-orders/{po_id}")
def update_purchase_order(po_id: str, data: dict, db: Session = Depends(get_db)):
    po = db.query(MaterialPurchaseOrder).filter(MaterialPurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404)
    for k in ["supplier_id", "order_date", "delivery_place", "seiban", "title", "status", "notes"]:
        if k in data: setattr(po, k, data[k])
    db.commit(); db.refresh(po)
    return _po_dict(po)

@router.patch("/purchase-orders/{po_id}/status")
def update_po_status(po_id: str, status: str = Query(...), db: Session = Depends(get_db)):
    po = db.query(MaterialPurchaseOrder).filter(MaterialPurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404)
    po.status = status
    # 明細にも反映（一部入荷以外）
    if status in ("発注済", "入荷済", "キャンセル"):
        for l in po.lines:
            l.status = "入荷済" if status == "入荷済" else ("未発注" if status == "キャンセル" else "発注済")
    db.commit()
    return {"ok": True, "status": po.status}

@router.post("/purchase-orders/{po_id}/receive-stock")
def receive_po_stock(po_id: str, db: Session = Depends(get_db)):
    """発注書の入荷登録：各明細を在庫に加算（入荷）し、発注書を入荷済にする。在庫引当の明細は除外。"""
    po = db.query(MaterialPurchaseOrder).filter(MaterialPurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404)
    dup = db.query(MaterialStockMovement).filter(
        MaterialStockMovement.purchase_order_id == po_id,
        MaterialStockMovement.movement_type == "入荷").first()
    if dup:
        raise HTTPException(400, "この発注書は既に入荷登録済みです")
    created = 0
    for l in po.lines:
        if l.status == "在庫引当":
            continue
        qty = float(l.order_qty or 0)
        if qty <= 0:
            continue
        db.add(MaterialStockMovement(
            material_id=l.material_id, movement_type="入荷", quantity=qty,
            movement_date=date.today().isoformat(),
            project_order_id=l.project_order_id, purchase_order_id=po.id, notes="発注入荷",
        ))
        l.status = "入荷済"
        created += 1
    po.status = "入荷済"
    db.commit()
    return {"ok": True, "created": created, "message": f"{created}明細を入荷登録しました"}

@router.delete("/purchase-orders/{po_id}")
def delete_purchase_order(po_id: str, db: Session = Depends(get_db)):
    po = db.query(MaterialPurchaseOrder).filter(MaterialPurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404)
    db.delete(po); db.commit()
    return {"ok": True}

@router.post("/purchase-orders/from-units")
def po_from_units(data: dict, db: Session = Depends(get_db)):
    """選択ユニットの部材を仕入先ごとにまとめて発注書を発番作成。
    units=[{unit_id, multiplier}]。1案件子IDに対し仕入先数だけ発注書が作られる。"""
    project_order_id = data.get("project_order_id") or None
    due_date = data.get("due_date")
    units = data.get("units") or []
    if not units:
        raise HTTPException(400, "ユニットが選択されていません")

    po = db.query(ProjectOrder).filter(ProjectOrder.id == project_order_id).first() if project_order_id else None

    # 仕入先ごとに明細を集約
    groups = {}  # supplier_id(str or "") -> list of (bom_row, multiplier, unit)
    for entry in units:
        unit = db.query(UnitMaster).filter(UnitMaster.id == entry.get("unit_id")).first()
        if not unit:
            continue
        mult = float(entry.get("multiplier", 1) or 1)
        rows = db.query(UnitMaterialBom).options(joinedload(UnitMaterialBom.material)).filter(
            UnitMaterialBom.unit_id == unit.id
        ).order_by(UnitMaterialBom.sort_order).all()
        for r in rows:
            sup = str(r.material.default_supplier_id) if r.material and r.material.default_supplier_id else ""
            groups.setdefault(sup, []).append((r, mult, unit))

    if not groups:
        return {"ok": False, "created_pos": [], "message": "部材が未登録のため発注書を作成できませんでした"}

    created = []
    for sup_id, items in groups.items():
        po_no = _gen_po_no(db)
        header = MaterialPurchaseOrder(
            po_no=po_no, project_order_id=project_order_id,
            supplier_id=(sup_id or None), order_date=date.today(),
            delivery_place=(po.customer_name if po else None),
            seiban=(po.child_no if po else None),
            title=(po.project_name if po else None),
            status="作成中",
        )
        db.add(header); db.flush()
        for r, mult, unit in items:
            db.add(MaterialOrder(
                purchase_order_id=header.id, project_order_id=project_order_id,
                material_id=r.material_id, supplier_id=(sup_id or None),
                order_qty=float(r.quantity) * mult, due_date=due_date,
                status="未発注", notes=f"ユニット: {unit.unit_code}",
            ))
        created.append(po_no)
    db.commit()
    return {"ok": True, "created_pos": created, "count": len(created),
            "message": f"発注書を {len(created)}件 発番作成しました（{', '.join(created)}）"}

@router.get("/purchase-orders/{po_id}/pdf")
def purchase_order_pdf(po_id: str, db: Session = Depends(get_db)):
    po = db.query(MaterialPurchaseOrder).filter(MaterialPurchaseOrder.id == po_id).first()
    if not po: raise HTTPException(404)
    html = _build_po_html(po)
    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename={po.po_no}.html"})

def _build_po_html(po: MaterialPurchaseOrder) -> str:
    sup = po.supplier
    sup_name = sup.name if sup else "（仕入先未指定）"
    sup_post = f"〒{sup.postal_code}" if sup and sup.postal_code else ""
    sup_addr = sup.address if sup and sup.address else ""
    sup_tel = sup.phone if sup and sup.phone else ""
    sup_person = (sup.contact_person + " 様") if sup and sup.contact_person else ""
    order_date = po.order_date.strftime("%Y/%m/%d") if po.order_date else ""

    MIN_ROWS = 5
    lines = sorted(po.lines or [], key=lambda x: str(x.created_at))
    rows_html = ""
    for l in lines:
        mat = l.material
        code = mat.material_code if mat else ""
        name = mat.material_name if mat else ""
        unit = mat.unit if mat else ""
        qty = ("%g" % float(l.order_qty)) if l.order_qty is not None else ""
        price = ("¥%s" % format(int(l.unit_price), ",")) if l.unit_price else ""
        amount = ("¥%s" % format(int(float(l.order_qty or 0) * float(l.unit_price or 0)), ","))
        due = l.due_date.strftime("%Y/%m/%d") if l.due_date else ""
        rows_html += f"""
        <tr>
          <td class="c">{po.po_no}</td>
          <td>{l.notes or ""}</td>
          <td>{code}</td>
          <td>{name}</td>
          <td class="r">{qty}</td><td class="c">{unit}</td>
          <td class="r">{price}</td><td class="r">{amount}</td>
          <td class="c">{due}</td>
        </tr>"""
    for _ in range(max(0, MIN_ROWS - len(lines))):
        rows_html += '<tr><td>&nbsp;</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td class="c">／</td></tr>'

    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><title>{po.po_no}</title>
<style>
  @page {{ size: A4 landscape; margin: 10mm; }}
  body {{ font-family: 'Hiragino Kaku Gothic ProN','Yu Gothic','Meiryo',sans-serif; font-size: 11px; color:#111; }}
  .title {{ text-align:center; font-size: 22px; font-weight:bold; letter-spacing: 8px; margin: 2px 0 6px; }}
  .top {{ display:flex; justify-content:space-between; align-items:flex-start; }}
  .sup {{ font-size: 12px; line-height: 1.6; }}
  .sup .nm {{ font-size: 15px; font-weight:bold; }}
  .meta td {{ border:1px solid #000; padding:2px 8px; font-size:12px; }}
  table.grid {{ width:100%; border-collapse:collapse; margin-top:6px; }}
  table.grid th, table.grid td {{ border:1px solid #000; padding:3px 5px; }}
  table.grid th {{ background:#f0f0f0; font-size:11px; }}
  td.r {{ text-align:right; }} td.c {{ text-align:center; }}
  .foot {{ display:flex; justify-content:space-between; align-items:flex-end; margin-top:8px; }}
  .me {{ font-size:12px; line-height:1.5; }} .me .nm {{ font-size:14px; font-weight:bold; }}
  .seal td {{ border:1px solid #000; width:42px; height:42px; }}
  .note {{ font-size:11px; }}
</style></head><body>
  <div class="top">
    <div class="sup">
      <div>{sup_post}</div><div>{sup_addr}</div>
      <div class="nm">{sup_name}</div>
      <div style="margin-left:1em;">{sup_person}</div>
      <div style="margin-left:1em;">TEL: {sup_tel}</div>
    </div>
    <div style="text-align:right;">
      <div class="title">注文書</div>
      <table class="meta" style="border-collapse:collapse; margin-left:auto;">
        <tr><td>注文日</td><td>{order_date}</td></tr>
      </table>
    </div>
  </div>

  <table class="grid">
    <thead>
      <tr>
        <th>注文No.</th><th>ユニット/備考</th><th>品番図番</th><th>品名／形式寸法</th>
        <th>数量</th><th>単位</th><th>単価</th><th>金額</th><th>納期</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  <div class="foot">
    <div class="me">
      <div>〒460-0022　愛知県名古屋市中区金山4-3-17</div>
      <div class="nm">井上電設株式会社</div>
      <div>TEL: 052-322-5271　FAX: 052-332-5273</div>
      <div class="note" style="margin-top:6px;">納品書に必ず注文No./納入場所/製番の順に記入下さい。※確認後折返しFAX下さい。</div>
    </div>
    <table class="seal" style="border-collapse:collapse;"><tr><td></td><td></td></tr></table>
  </div>
</body></html>"""
