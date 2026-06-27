"""製品BOM階層マスタ API — 製品マスタ・ユニットマスタ・構成BOM・案件展開（製品NO/ユニットNO/発注NO）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.db.models import (
    get_db, ProductMaster, UnitMaster, ProductUnitBom, UnitMaterialBom,
    ProjectProduct, ProjectUnit, ProjectOrder, MaterialMaster, MaterialOrder,
)

router = APIRouter()

# =============================================
# 製品マスタ
# =============================================

@router.get("/products")
def list_products(search: str = Query(None), product_type: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(ProductMaster).filter(ProductMaster.is_active == True)
    if search:
        q = q.filter(or_(
            ProductMaster.product_name.ilike(f"%{search}%"),
            ProductMaster.product_code.ilike(f"%{search}%"),
            ProductMaster.model_no.ilike(f"%{search}%"),
        ))
    if product_type:
        q = q.filter(ProductMaster.product_type == product_type)
    return [_product_dict(p) for p in q.order_by(ProductMaster.product_code).all()]

@router.post("/products")
def create_product(data: dict, db: Session = Depends(get_db)):
    p = ProductMaster(**_pick(data, [
        "product_code", "product_name", "product_type", "model_no",
        "standard_price", "standard_hours", "spec_json", "estimate_ref", "notes",
    ]))
    db.add(p); db.commit(); db.refresh(p)
    return _product_dict(p)

@router.put("/products/{product_id}")
def update_product(product_id: str, data: dict, db: Session = Depends(get_db)):
    p = db.query(ProductMaster).filter(ProductMaster.id == product_id).first()
    if not p: raise HTTPException(404, "製品マスタが見つかりません")
    for k in ["product_code", "product_name", "product_type", "model_no",
              "standard_price", "standard_hours", "spec_json", "estimate_ref", "notes"]:
        if k in data: setattr(p, k, data[k])
    db.commit(); db.refresh(p)
    return _product_dict(p)

@router.delete("/products/{product_id}")
def delete_product(product_id: str, db: Session = Depends(get_db)):
    p = db.query(ProductMaster).filter(ProductMaster.id == product_id).first()
    if not p: raise HTTPException(404)
    p.is_active = False; db.commit()
    return {"ok": True}

def _product_dict(p: ProductMaster):
    return {
        "id": str(p.id), "product_code": p.product_code, "product_name": p.product_name,
        "product_type": p.product_type, "model_no": p.model_no,
        "standard_price": float(p.standard_price) if p.standard_price is not None else None,
        "standard_hours": float(p.standard_hours) if p.standard_hours is not None else None,
        "spec_json": p.spec_json, "estimate_ref": p.estimate_ref, "notes": p.notes,
        "unit_count": len(p.units) if p.units else 0,
    }

# =============================================
# ユニットマスタ（型式）
# =============================================

@router.get("/units")
def list_units(search: str = Query(None), unit_type: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(UnitMaster).filter(UnitMaster.is_active == True)
    if search:
        q = q.filter(or_(
            UnitMaster.unit_name.ilike(f"%{search}%"),
            UnitMaster.unit_code.ilike(f"%{search}%"),
            UnitMaster.model_no.ilike(f"%{search}%"),
        ))
    if unit_type:
        q = q.filter(UnitMaster.unit_type == unit_type)
    return [_unit_dict(u) for u in q.order_by(UnitMaster.unit_code).all()]

@router.post("/units")
def create_unit(data: dict, db: Session = Depends(get_db)):
    u = UnitMaster(**_pick(data, [
        "unit_code", "unit_name", "unit_type", "model_no",
        "standard_price", "standard_hours", "spec_json", "estimate_ref", "notes",
    ]))
    db.add(u); db.commit(); db.refresh(u)
    return _unit_dict(u)

@router.put("/units/{unit_id}")
def update_unit(unit_id: str, data: dict, db: Session = Depends(get_db)):
    u = db.query(UnitMaster).filter(UnitMaster.id == unit_id).first()
    if not u: raise HTTPException(404, "ユニットマスタが見つかりません")
    for k in ["unit_code", "unit_name", "unit_type", "model_no",
              "standard_price", "standard_hours", "spec_json", "estimate_ref", "notes"]:
        if k in data: setattr(u, k, data[k])
    db.commit(); db.refresh(u)
    return _unit_dict(u)

@router.delete("/units/{unit_id}")
def delete_unit(unit_id: str, db: Session = Depends(get_db)):
    u = db.query(UnitMaster).filter(UnitMaster.id == unit_id).first()
    if not u: raise HTTPException(404)
    u.is_active = False; db.commit()
    return {"ok": True}

def _unit_dict(u: UnitMaster):
    return {
        "id": str(u.id), "unit_code": u.unit_code, "unit_name": u.unit_name,
        "unit_type": u.unit_type, "model_no": u.model_no,
        "standard_price": float(u.standard_price) if u.standard_price is not None else None,
        "standard_hours": float(u.standard_hours) if u.standard_hours is not None else None,
        "spec_json": u.spec_json, "estimate_ref": u.estimate_ref, "notes": u.notes,
        "material_count": len(u.materials) if u.materials else 0,
    }

# =============================================
# 製品構成BOM（製品 → ユニット）
# =============================================

@router.get("/products/{product_id}/units")
def list_product_units(product_id: str, db: Session = Depends(get_db)):
    rows = db.query(ProductUnitBom).options(joinedload(ProductUnitBom.unit)).filter(
        ProductUnitBom.product_id == product_id
    ).order_by(ProductUnitBom.sort_order).all()
    return [_pu_dict(r) for r in rows]

@router.post("/product-units")
def create_product_unit(data: dict, db: Session = Depends(get_db)):
    r = ProductUnitBom(
        product_id=data["product_id"], unit_id=data["unit_id"],
        quantity=data.get("quantity", 1), sort_order=data.get("sort_order", 0),
        notes=data.get("notes"),
    )
    db.add(r); db.commit(); db.refresh(r)
    return _pu_dict(r)

@router.put("/product-units/{pu_id}")
def update_product_unit(pu_id: str, data: dict, db: Session = Depends(get_db)):
    r = db.query(ProductUnitBom).filter(ProductUnitBom.id == pu_id).first()
    if not r: raise HTTPException(404)
    for k in ["unit_id", "quantity", "sort_order", "notes"]:
        if k in data: setattr(r, k, data[k])
    db.commit(); db.refresh(r)
    return _pu_dict(r)

@router.delete("/product-units/{pu_id}")
def delete_product_unit(pu_id: str, db: Session = Depends(get_db)):
    r = db.query(ProductUnitBom).filter(ProductUnitBom.id == pu_id).first()
    if not r: raise HTTPException(404)
    db.delete(r); db.commit()
    return {"ok": True}

def _pu_dict(r: ProductUnitBom):
    return {
        "id": str(r.id), "product_id": str(r.product_id), "unit_id": str(r.unit_id),
        "unit_code": r.unit.unit_code if r.unit else None,
        "unit_name": r.unit.unit_name if r.unit else None,
        "unit_type": r.unit.unit_type if r.unit else None,
        "model_no": r.unit.model_no if r.unit else None,
        "quantity": float(r.quantity), "sort_order": r.sort_order, "notes": r.notes,
    }

# =============================================
# ユニット構成BOM（ユニット → 部品）
# =============================================

@router.get("/units/{unit_id}/materials")
def list_unit_materials(unit_id: str, db: Session = Depends(get_db)):
    rows = db.query(UnitMaterialBom).options(joinedload(UnitMaterialBom.material)).filter(
        UnitMaterialBom.unit_id == unit_id
    ).order_by(UnitMaterialBom.sort_order).all()
    return [_um_dict(r) for r in rows]

@router.post("/unit-materials")
def create_unit_material(data: dict, db: Session = Depends(get_db)):
    r = UnitMaterialBom(
        unit_id=data["unit_id"], material_id=data["material_id"],
        quantity=data.get("quantity", 1), sort_order=data.get("sort_order", 0),
        notes=data.get("notes"),
    )
    db.add(r); db.commit(); db.refresh(r)
    return _um_dict(r)

@router.put("/unit-materials/{um_id}")
def update_unit_material(um_id: str, data: dict, db: Session = Depends(get_db)):
    r = db.query(UnitMaterialBom).filter(UnitMaterialBom.id == um_id).first()
    if not r: raise HTTPException(404)
    for k in ["material_id", "quantity", "sort_order", "notes"]:
        if k in data: setattr(r, k, data[k])
    db.commit(); db.refresh(r)
    return _um_dict(r)

@router.delete("/unit-materials/{um_id}")
def delete_unit_material(um_id: str, db: Session = Depends(get_db)):
    r = db.query(UnitMaterialBom).filter(UnitMaterialBom.id == um_id).first()
    if not r: raise HTTPException(404)
    db.delete(r); db.commit()
    return {"ok": True}

def _um_dict(r: UnitMaterialBom):
    return {
        "id": str(r.id), "unit_id": str(r.unit_id), "material_id": str(r.material_id),
        "material_code": r.material.material_code if r.material else None,
        "material_name": r.material.material_name if r.material else None,
        "unit": r.material.unit if r.material else None,
        "quantity": float(r.quantity), "sort_order": r.sort_order, "notes": r.notes,
    }

# =============================================
# 案件展開（製品NO / ユニットNO / 発注NO 採番）
# =============================================

@router.post("/expand")
def expand_product(data: dict, db: Session = Depends(get_db)):
    """案件子IDに製品マスタを適用し、製品NO→ユニットNO（→発注NO）を採番展開"""
    project_order_id = data.get("project_order_id")
    product_master_id = data.get("product_master_id")
    qty = float(data.get("quantity", 1) or 1)
    generate_orders = bool(data.get("generate_orders", False))

    po = db.query(ProjectOrder).filter(ProjectOrder.id == project_order_id).first()
    if not po: raise HTTPException(404, "案件子IDが見つかりません")
    pm = db.query(ProductMaster).filter(ProductMaster.id == product_master_id).first()
    if not pm: raise HTTPException(404, "製品マスタが見つかりません")

    # 製品NO採番: {child_no}-P01
    p_seq = db.query(ProjectProduct).filter(ProjectProduct.project_order_id == project_order_id).count() + 1
    product_no = f"{po.child_no}-P{p_seq:02d}"
    pp = ProjectProduct(
        product_no=product_no, project_order_id=po.id, product_master_id=pm.id,
        product_name=pm.product_name, product_type=pm.product_type,
        model_no=pm.model_no, quantity=qty,
    )
    db.add(pp); db.flush()

    # ユニット展開（製品構成BOMをたどる）
    bom_units = db.query(ProductUnitBom).options(joinedload(ProductUnitBom.unit)).filter(
        ProductUnitBom.product_id == pm.id
    ).order_by(ProductUnitBom.sort_order).all()

    order_seq = db.query(MaterialOrder).filter(MaterialOrder.project_order_id == project_order_id).count()
    created_units = 0
    created_orders = 0
    for u_idx, bu in enumerate(bom_units, start=1):
        um = bu.unit
        if not um:
            continue
        unit_qty = float(bu.quantity) * qty
        unit_no = f"{product_no}-U{u_idx:02d}"
        pu = ProjectUnit(
            unit_no=unit_no, project_product_id=pp.id, unit_master_id=um.id,
            unit_name=um.unit_name, unit_type=um.unit_type, model_no=um.model_no,
            quantity=unit_qty,
        )
        db.add(pu); db.flush()
        created_units += 1

        # 発注生成（オプション）: ユニット構成BOMをたどって部材発注を起票
        if generate_orders:
            mat_boms = db.query(UnitMaterialBom).options(joinedload(UnitMaterialBom.material)).filter(
                UnitMaterialBom.unit_id == um.id
            ).order_by(UnitMaterialBom.sort_order).all()
            for mb in mat_boms:
                order_seq += 1
                order_no = f"{po.child_no}-O{order_seq:03d}"
                mat = mb.material
                db.add(MaterialOrder(
                    order_no=order_no, project_order_id=po.id, project_unit_id=pu.id,
                    material_id=mb.material_id,
                    supplier_id=mat.default_supplier_id if mat else None,
                    order_qty=float(mb.quantity) * unit_qty,
                    status="未発注",
                ))
                created_orders += 1

    db.commit()
    return {
        "ok": True, "product_no": product_no,
        "created_units": created_units, "created_orders": created_orders,
        "message": f"製品NO {product_no} を展開（ユニット{created_units}件" +
                   (f"・発注{created_orders}件" if generate_orders else "") + "）",
    }

# =============================================
# 案件ツリー表示（製品NO → ユニットNO → 発注NO）
# =============================================

@router.get("/project-tree")
def project_tree(project_order_id: str = Query(...), db: Session = Depends(get_db)):
    po = db.query(ProjectOrder).filter(ProjectOrder.id == project_order_id).first()
    if not po: raise HTTPException(404)

    products = db.query(ProjectProduct).filter(
        ProjectProduct.project_order_id == project_order_id
    ).order_by(ProjectProduct.product_no).all()

    # ユニット毎の発注をまとめて取得
    orders_by_unit: dict = {}
    for mo in db.query(MaterialOrder).options(
        joinedload(MaterialOrder.material), joinedload(MaterialOrder.supplier)
    ).filter(MaterialOrder.project_order_id == project_order_id).all():
        if mo.project_unit_id:
            orders_by_unit.setdefault(str(mo.project_unit_id), []).append(mo)

    tree = []
    for pp in products:
        units = db.query(ProjectUnit).filter(
            ProjectUnit.project_product_id == pp.id
        ).order_by(ProjectUnit.unit_no).all()
        tree.append({
            "id": str(pp.id), "product_no": pp.product_no, "product_name": pp.product_name,
            "product_type": pp.product_type, "model_no": pp.model_no,
            "quantity": float(pp.quantity) if pp.quantity is not None else 1,
            "status": pp.status,
            "units": [{
                "id": str(u.id), "unit_no": u.unit_no, "unit_name": u.unit_name,
                "unit_type": u.unit_type, "model_no": u.model_no,
                "quantity": float(u.quantity) if u.quantity is not None else 1,
                "status": u.status, "assigned_to": u.assigned_to,
                "orders": [{
                    "id": str(mo.id), "order_no": mo.order_no,
                    "material_name": mo.material.material_name if mo.material else None,
                    "supplier_name": mo.supplier.name if mo.supplier else None,
                    "order_qty": float(mo.order_qty) if mo.order_qty is not None else None,
                    "status": mo.status,
                } for mo in orders_by_unit.get(str(u.id), [])],
            } for u in units],
        })
    return {"child_no": po.child_no, "products": tree}

@router.delete("/project-products/{pp_id}")
def delete_project_product(pp_id: str, db: Session = Depends(get_db)):
    pp = db.query(ProjectProduct).filter(ProjectProduct.id == pp_id).first()
    if not pp: raise HTTPException(404)
    # 紐付く発注も削除
    unit_ids = [str(u.id) for u in db.query(ProjectUnit).filter(ProjectUnit.project_product_id == pp.id).all()]
    if unit_ids:
        db.query(MaterialOrder).filter(MaterialOrder.project_unit_id.in_(unit_ids)).delete(synchronize_session=False)
    db.delete(pp); db.commit()
    return {"ok": True}

@router.patch("/project-units/{pu_id}")
def update_project_unit(pu_id: str, data: dict, db: Session = Depends(get_db)):
    u = db.query(ProjectUnit).filter(ProjectUnit.id == pu_id).first()
    if not u: raise HTTPException(404)
    for k in ["status", "assigned_to", "quantity", "model_no", "notes"]:
        if k in data: setattr(u, k, data[k])
    db.commit(); db.refresh(u)
    return {"ok": True, "status": u.status}


def _pick(data: dict, keys: list):
    return {k: data.get(k) for k in keys if k in data}
