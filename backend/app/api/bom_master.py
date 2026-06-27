"""製品BOM階層マスタ API — 製品マスタ・ユニットマスタ・構成BOM（型式→ユニット→部材の紐付け定義）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.db.models import (
    get_db, ProductMaster, UnitMaster, ProductUnitBom, UnitMaterialBom,
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

def _pick(data: dict, keys: list):
    return {k: data.get(k) for k in keys if k in data}
