"""製品BOM階層マスタ API — 製品マスタ・ユニットマスタ・構成BOM（型式→ユニット→部材の紐付け定義）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.db.models import (
    get_db, ProductMaster, UnitMaster, ProductUnitBom, UnitMaterialBom, MaterialMaster, MaterialOrder,
)

router = APIRouter()

# サンプル取込データの識別タグ（notes先頭に付与し、一括削除に使う）
SAMPLE_TAG = "〔サンプル取込〕"

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


# =============================================
# サンプル一括取込（部品マスタ / ユニット＋部品紐付け）— notes先頭にタグを付け一括削除可能
# =============================================

@router.post("/import/materials")
def import_materials(data: dict, db: Session = Depends(get_db)):
    """部品マスタを一括登録。既存コードはスキップ。notes先頭にサンプルタグを付与。"""
    tag = data.get("tag", SAMPLE_TAG)
    materials = data.get("materials", [])
    existing = {row[0] for row in db.query(MaterialMaster.material_code).all()}
    created = 0
    for m in materials:
        code = str(m.get("material_code", "")).strip()
        if not code or code in existing:
            continue
        existing.add(code)
        name = (m.get("material_name") or code).strip()[:300]
        extra = m.get("note_extra") or ""
        db.add(MaterialMaster(
            material_code=code, material_name=name,
            unit=(m.get("unit") or "個")[:20],
            notes=(tag + " " + extra).strip(),
        ))
        created += 1
    db.commit()
    return {"ok": True, "created": created, "skipped": len(materials) - created}

@router.post("/import/units")
def import_units(data: dict, db: Session = Depends(get_db)):
    """ユニット＋部品紐付け（ユニット構成BOM）を一括登録。部品はコードで突合。"""
    tag = data.get("tag", SAMPLE_TAG)
    units = data.get("units", [])
    existing_u = {row[0] for row in db.query(UnitMaster.unit_code).all()}
    mat_map = {mc: mid for mc, mid in db.query(MaterialMaster.material_code, MaterialMaster.id).all()}
    created_u, created_links, missing = 0, 0, 0
    for u in units:
        ucode = str(u.get("unit_code", "")).strip()
        if not ucode or ucode in existing_u:
            continue
        existing_u.add(ucode)
        um = UnitMaster(
            unit_code=ucode[:50], unit_name=(u.get("unit_name") or ucode)[:300],
            unit_type=u.get("unit_type"), model_no=(u.get("model_no") or None),
            notes=tag,
        )
        db.add(um); db.flush()
        created_u += 1
        for idx, it in enumerate(u.get("items", [])):
            code = str(it.get("material_code", "")).strip()
            mid = mat_map.get(code)
            if not mid:
                missing += 1
                continue
            db.add(UnitMaterialBom(
                unit_id=um.id, material_id=mid,
                quantity=it.get("quantity", 1) or 1, sort_order=idx, notes=it.get("notes"),
            ))
            created_links += 1
    db.commit()
    return {"ok": True, "units": created_u, "links": created_links, "missing_materials": missing}

@router.get("/import/sample-count")
def sample_count(db: Session = Depends(get_db)):
    mc = db.query(MaterialMaster).filter(MaterialMaster.notes.like(SAMPLE_TAG + "%")).count()
    uc = db.query(UnitMaster).filter(UnitMaster.notes.like(SAMPLE_TAG + "%")).count()
    return {"materials": mc, "units": uc}

@router.delete("/import/sample-data")
def delete_sample_data(db: Session = Depends(get_db)):
    """サンプルタグの付いたユニット・部品マスタを一括削除（紐付けはカスケード/明示削除）。"""
    # サンプルユニット削除（UnitMaterialBomはカスケード）
    sample_units = db.query(UnitMaster).filter(UnitMaster.notes.like(SAMPLE_TAG + "%")).all()
    deleted_units = len(sample_units)
    for u in sample_units:
        db.delete(u)
    db.flush()
    # サンプル部品: 残存する紐付け・発注を外してから削除
    mat_ids = [m.id for m in db.query(MaterialMaster.id).filter(MaterialMaster.notes.like(SAMPLE_TAG + "%")).all()]
    if mat_ids:
        db.query(UnitMaterialBom).filter(UnitMaterialBom.material_id.in_(mat_ids)).delete(synchronize_session=False)
        db.query(MaterialOrder).filter(MaterialOrder.material_id.in_(mat_ids)).delete(synchronize_session=False)
    deleted_materials = db.query(MaterialMaster).filter(
        MaterialMaster.notes.like(SAMPLE_TAG + "%")
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted_units": deleted_units, "deleted_materials": deleted_materials}


# =============================================
# 見積パターンから型式を取込（既存の見積パターン → 製品/ユニットマスタ）
# =============================================

@router.post("/seed-from-estimate-patterns")
def seed_from_estimate_patterns(db: Session = Depends(get_db)):
    """既存の見積パターン（BFR本体/ファン/RV・BFQ本体/排風機/RV・SCA本体・PLファン・サイクロン・自動ダンパー）を
    製品マスタ・ユニットマスタへ取込み、本体↔ファン/RV を製品構成BOMで紐付ける。
    既存コードはスキップ（再実行で重複しない）。"""
    from app.db.models import (
        EstimateBfrBody, EstimateBfrFan, EstimateBfrRv,
        EstimateBfqBody, EstimateBfqFan, EstimateBfqOption,
        EstimateScaBody, EstimatePlFan, EstimateCyclone, EstimateAutoDamper,
    )
    stats = {"products": 0, "units": 0, "links": 0}

    def ensure_product(code, name, ptype, model_no, price, ref):
        ex = db.query(ProductMaster).filter(ProductMaster.product_code == code).first()
        if ex:
            return ex, False
        p = ProductMaster(product_code=code, product_name=name, product_type=ptype,
                          model_no=model_no, standard_price=price, estimate_ref=ref)
        db.add(p); db.flush()
        stats["products"] += 1
        return p, True

    def ensure_unit(code, name, utype, model_no, price, ref):
        ex = db.query(UnitMaster).filter(UnitMaster.unit_code == code).first()
        if ex:
            return ex, False
        u = UnitMaster(unit_code=code, unit_name=name, unit_type=utype,
                       model_no=model_no, standard_price=price, estimate_ref=ref)
        db.add(u); db.flush()
        stats["units"] += 1
        return u, True

    def link(prod, unit, qty):
        if not prod or not unit:
            return
        ex = db.query(ProductUnitBom).filter(
            ProductUnitBom.product_id == prod.id, ProductUnitBom.unit_id == unit.id
        ).first()
        if not ex:
            db.add(ProductUnitBom(product_id=prod.id, unit_id=unit.id, quantity=qty or 1))
            stats["links"] += 1

    # BFR本体 → 製品マスタ
    for b in db.query(EstimateBfrBody).filter(EstimateBfrBody.is_active == True).all():
        ensure_product(f"BFR-{b.model_code}", f"BFR本体 {b.model_code}", "BFR", b.model_code, b.base_price, b.model_code)

    # SCA本体 → 製品マスタ
    for b in db.query(EstimateScaBody).filter(EstimateScaBody.is_active == True).all():
        ensure_product(f"SCA-{b.model_code}", f"SCA本体 {b.model_code}", "SCA", b.model_code, b.base_price, b.model_code)

    # BFRファン → ユニット + BFR本体への紐付け
    for f in db.query(EstimateBfrFan).filter(EstimateBfrFan.is_active == True).all():
        if not f.fan_model:
            continue
        u, _ = ensure_unit(f"FAN-{f.fan_model}", f"ターボファン {f.fan_model}", "ファン", f.fan_model, f.price, f.fan_model)
        prod = db.query(ProductMaster).filter(ProductMaster.product_code == f"BFR-{f.bfr_model}").first()
        link(prod, u, f.quantity)

    # BFR RV → ユニット + BFR本体への紐付け
    for r in db.query(EstimateBfrRv).filter(EstimateBfrRv.is_active == True).all():
        if not r.rv_model:
            continue
        u, _ = ensure_unit(f"RV-{r.rv_model}", f"ロータリーバルブ {r.rv_model}", "RV", r.rv_model, r.price, r.rv_model)
        prod = db.query(ProductMaster).filter(ProductMaster.product_code == f"BFR-{r.bfr_model}").first()
        link(prod, u, r.quantity)

    # BFQ本体 → 製品マスタ（本体価格が未設定の型式も型式管理のため取込む）
    for b in db.query(EstimateBfqBody).filter(EstimateBfqBody.is_active == True).all():
        ensure_product(f"BFQ-{b.model_code}", f"BFQ本体 {b.model_code}", "BFQ", b.model_code, b.base_price, b.model_code)

    # BFQ排風機（周波数別）→ ユニット + BFQ本体（同系列）への紐付け
    for f in db.query(EstimateBfqFan).filter(EstimateBfqFan.is_active == True).all():
        if not f.fan_model:
            continue
        u, _ = ensure_unit(f"FAN-{f.fan_model}", f"排風機 {f.fan_model}", "ファン", f.fan_model, None, f.fan_model)
        for b in db.query(EstimateBfqBody).filter(
            EstimateBfqBody.series == f.series, EstimateBfqBody.is_active == True
        ).all():
            link(db.query(ProductMaster).filter(ProductMaster.product_code == f"BFQ-{b.model_code}").first(), u, 1)

    # BFQ RVオプション → ユニット
    for o in db.query(EstimateBfqOption).filter(
        EstimateBfqOption.category == "RV", EstimateBfqOption.is_active == True
    ).all():
        ensure_unit(f"RV-{o.option_name}", f"ロータリーバルブ {o.option_name}", "RV", o.option_name, o.price, o.option_name)

    # PLファン → ユニット
    for f in db.query(EstimatePlFan).filter(EstimatePlFan.is_active == True).all():
        ensure_unit(f"PLFAN-{f.model_code}", f"PLファン {f.model_code}", "ファン", f.model_code, f.price, f.model_code)

    # サイクロン → ユニット
    for c in db.query(EstimateCyclone).filter(EstimateCyclone.is_active == True).all():
        ensure_unit(f"CY-{c.model_code}", f"サイクロン {c.model_code}", "サイクロン", c.model_code, c.price, c.model_code)

    # 自動ダンパー → ユニット
    for d in db.query(EstimateAutoDamper).filter(EstimateAutoDamper.is_active == True).all():
        ensure_unit(f"DMP-{d.model_code}", f"自動ダンパー {d.model_code}", "ダンパー", d.model_code, d.price, d.model_code)

    db.commit()
    return {
        "ok": True, **stats,
        "message": f"見積パターンから取込完了: 製品{stats['products']}件・ユニット{stats['units']}件・製品構成{stats['links']}件",
    }
