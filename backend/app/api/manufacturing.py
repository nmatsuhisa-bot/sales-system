"""製造計画 API — 製造計画・生産能力マスタ・製品所要工数マスタ"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
from app.db.models import get_db, ManufacturingPlan, ProductionCapacity, ProductHours, ProjectOrder
from datetime import date

router = APIRouter()

# ---- 製造計画 ----

@router.get("/plans")
def list_plans(year: int = Query(None), status: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(ManufacturingPlan).options(joinedload(ManufacturingPlan.project_order))
    if year:
        q = q.filter(
            (extract('year', ManufacturingPlan.planned_start) == year) |
            (extract('year', ManufacturingPlan.planned_end) == year)
        )
    if status: q = q.filter(ManufacturingPlan.status == status)
    plans = q.order_by(ManufacturingPlan.planned_start).all()
    return [_plan_dict(p) for p in plans]

@router.post("/plans")
def create_plan(data: dict, db: Session = Depends(get_db)):
    p = ManufacturingPlan(
        project_order_id=data["project_order_id"],
        product_type=data.get("product_type"),
        model_no=data.get("model_no"),
        planned_start=data.get("planned_start"),
        planned_end=data.get("planned_end"),
        assigned_to=data.get("assigned_to"),
        status=data.get("status", "未着手"),
        notes=data.get("notes"),
    )
    db.add(p); db.commit(); db.refresh(p)
    return _plan_dict(p)

@router.post("/plans/draft-from-estimate")
def draft_from_estimate(data: dict, db: Session = Depends(get_db)):
    """案件子IDの受注採用見積から、本体（型式）ごとに製造計画ドラフトを作成。
    納期(sales_date)を完了予定とし、所要工数から仮の工期を逆算して開始予定を設定する。"""
    from app.db.models import QuotationHeader
    from datetime import timedelta
    import math

    project_order_id = data.get("project_order_id")
    po = db.query(ProjectOrder).filter(ProjectOrder.id == project_order_id).first()
    if not po:
        raise HTTPException(404, "案件子IDが見つかりません")

    # 採用見積を特定（status=adopted 優先、無ければ採用見積番号で補完）
    q = db.query(QuotationHeader).filter(
        QuotationHeader.project_order_id == project_order_id,
        QuotationHeader.status == "adopted",
    ).first()
    if not q and po.quotation_no:
        q = db.query(QuotationHeader).filter(
            QuotationHeader.quotation_no == po.quotation_no
        ).order_by(QuotationHeader.created_at.desc()).first()
    if not q:
        raise HTTPException(400, "受注採用された見積がありません")

    end = po.sales_date  # 納期 → 完了予定
    created, skipped = 0, 0
    for it in q.line_items:
        sj = it.spec_json or {}
        model = sj.get("model")   # 本体ラインのみ 'model' を持つ
        if not model:
            continue
        ptype = it.product_type
        # 重複スキップ（同じ子ID＋型番の計画が既にあれば作らない）
        exists = db.query(ManufacturingPlan).filter(
            ManufacturingPlan.project_order_id == po.id,
            ManufacturingPlan.model_no == model,
        ).first()
        if exists:
            skipped += 1
            continue
        # 仮工期: 所要工数から概算（2名×8h想定）、無ければ14日
        ph = db.query(ProductHours).filter(
            ProductHours.product_type == ptype, ProductHours.model_no == model
        ).first()
        if ph and ph.required_hours:
            days = max(7, int(math.ceil(float(ph.required_hours) / 16.0)))
        else:
            days = 14
        planned_start = (end - timedelta(days=days)) if end else None
        db.add(ManufacturingPlan(
            project_order_id=po.id, product_type=ptype, model_no=model,
            planned_start=planned_start, planned_end=end,
            status="未着手", notes=f"見積ドラフト自動作成（仮日程・工期{days}日）",
        ))
        created += 1

    db.commit()
    if created == 0 and skipped == 0:
        return {"ok": False, "created": 0, "skipped": 0,
                "message": "見積に本体（型式）ラインが見つかりませんでした"}
    msg = f"見積から製造計画を {created}件 作成しました（仮日程）"
    if skipped:
        msg += f" / 既存 {skipped}件 はスキップ"
    return {"ok": True, "created": created, "skipped": skipped, "message": msg}

@router.put("/plans/{plan_id}")
def update_plan(plan_id: str, data: dict, db: Session = Depends(get_db)):
    p = db.query(ManufacturingPlan).filter(ManufacturingPlan.id == plan_id).first()
    if not p: raise HTTPException(404)
    for k in ["product_type","model_no","planned_start","planned_end","actual_start","actual_end","assigned_to","status","notes"]:
        if k in data: setattr(p, k, data[k])
    db.commit(); db.refresh(p)
    return _plan_dict(p)

@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: str, db: Session = Depends(get_db)):
    p = db.query(ManufacturingPlan).filter(ManufacturingPlan.id == plan_id).first()
    if not p: raise HTTPException(404)
    db.delete(p); db.commit()
    return {"ok": True}

def _plan_dict(p: ManufacturingPlan):
    return {
        "id": str(p.id),
        "project_order_id": str(p.project_order_id),
        "child_no": p.project_order.child_no if p.project_order else None,
        "project_name": p.project_order.project_name if p.project_order else None,
        "customer_name": p.project_order.customer_name if p.project_order else None,
        "delivery_date": str(p.project_order.sales_date) if p.project_order and p.project_order.sales_date else None,
        "product_type": p.product_type, "model_no": p.model_no,
        "planned_start": str(p.planned_start) if p.planned_start else None,
        "planned_end": str(p.planned_end) if p.planned_end else None,
        "actual_start": str(p.actual_start) if p.actual_start else None,
        "actual_end": str(p.actual_end) if p.actual_end else None,
        "assigned_to": p.assigned_to, "status": p.status, "notes": p.notes,
    }

# ---- 生産能力マスタ ----

@router.get("/capacity")
def list_capacity(year: int = Query(None), db: Session = Depends(get_db)):
    q = db.query(ProductionCapacity)
    if year: q = q.filter(ProductionCapacity.fiscal_year == year)
    caps = q.order_by(ProductionCapacity.fiscal_year, ProductionCapacity.month).all()
    return [_cap_dict(c) for c in caps]

@router.post("/capacity")
def upsert_capacity(data: dict, db: Session = Depends(get_db)):
    factory = data.get("factory", "小牧")
    fy = data["fiscal_year"]; m = data["month"]
    existing = db.query(ProductionCapacity).filter(
        ProductionCapacity.factory == factory,
        ProductionCapacity.fiscal_year == fy,
        ProductionCapacity.month == m
    ).first()
    if existing:
        for k in ["work_days","regular_workers","temp_workers","hours_per_day"]:
            if k in data: setattr(existing, k, data[k])
        db.commit(); db.refresh(existing)
        return _cap_dict(existing)
    c = ProductionCapacity(**{k: data[k] for k in ["factory","fiscal_year","month","work_days","regular_workers","temp_workers","hours_per_day"] if k in data})
    db.add(c); db.commit(); db.refresh(c)
    return _cap_dict(c)

def _cap_dict(c: ProductionCapacity):
    available = (c.work_days or 0) * ((c.regular_workers or 0) + (c.temp_workers or 0)) * (c.hours_per_day or 8)
    return {
        "id": str(c.id), "factory": c.factory,
        "fiscal_year": c.fiscal_year, "month": c.month,
        "work_days": c.work_days, "regular_workers": c.regular_workers,
        "temp_workers": c.temp_workers, "hours_per_day": c.hours_per_day,
        "available_hours": available,
    }

# ---- 製品所要工数マスタ ----

@router.get("/product-hours")
def list_product_hours(product_type: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(ProductHours)
    if product_type: q = q.filter(ProductHours.product_type == product_type)
    return [_ph_dict(h) for h in q.order_by(ProductHours.product_type, ProductHours.model_no).all()]

@router.post("/product-hours")
def upsert_product_hours(data: dict, db: Session = Depends(get_db)):
    existing = db.query(ProductHours).filter(
        ProductHours.product_type == data["product_type"],
        ProductHours.model_no == data["model_no"]
    ).first()
    if existing:
        existing.required_hours = data["required_hours"]
        if "notes" in data: existing.notes = data["notes"]
        db.commit(); db.refresh(existing); return _ph_dict(existing)
    h = ProductHours(product_type=data["product_type"], model_no=data["model_no"],
                     required_hours=data["required_hours"], notes=data.get("notes"))
    db.add(h); db.commit(); db.refresh(h)
    return _ph_dict(h)

@router.delete("/product-hours/{ph_id}")
def delete_product_hours(ph_id: str, db: Session = Depends(get_db)):
    h = db.query(ProductHours).filter(ProductHours.id == ph_id).first()
    if not h: raise HTTPException(404)
    db.delete(h); db.commit()
    return {"ok": True}

def _ph_dict(h: ProductHours):
    return {"id": str(h.id), "product_type": h.product_type, "model_no": h.model_no,
            "required_hours": float(h.required_hours), "notes": h.notes}

# ---- 月別負荷計算 ----

@router.get("/load")
def get_monthly_load(year: int = Query(...), factory: str = Query("小牧"), db: Session = Depends(get_db)):
    """月別: 計画工数合計 vs 使用可能時間 を返す"""
    from datetime import date as dt
    caps = {c.month: c for c in db.query(ProductionCapacity).filter(
        ProductionCapacity.fiscal_year == year,
        ProductionCapacity.factory == factory
    ).all()}

    # 製造計画の期間から月別工数を集計
    plans = db.query(ManufacturingPlan).options(joinedload(ManufacturingPlan.project_order)).all()
    ph_map = {(h.product_type, h.model_no): float(h.required_hours)
              for h in db.query(ProductHours).all()}

    monthly_load = {}
    for p in plans:
        if not p.planned_start or not p.planned_end: continue
        hrs = ph_map.get((p.product_type, p.model_no), 0)
        if hrs == 0: continue
        # 製造期間を月ごとに按分
        start = p.planned_start; end = p.planned_end
        total_days = max((end - start).days, 1)
        cur = start
        while cur <= end:
            m = cur.month
            monthly_load[m] = monthly_load.get(m, 0) + hrs / total_days
            from datetime import timedelta
            cur += timedelta(days=1)

    # 3月始まり月順
    month_list = [3,4,5,6,7,8,9,10,11,12,1,2]
    result = []
    for m in month_list:
        cap = caps.get(m)
        available = (cap.work_days * (cap.regular_workers + cap.temp_workers) * cap.hours_per_day) if cap else 0
        load = round(monthly_load.get(m, 0), 1)
        result.append({
            "month": m,
            "available_hours": available,
            "planned_hours": load,
            "overloaded": load > available and available > 0,
        })
    return {"year": year, "factory": factory, "monthly": result}
