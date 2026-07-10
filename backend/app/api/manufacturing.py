"""製造計画 API — 製造計画・生産能力マスタ・製品所要工数マスタ"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract, or_, and_
import calendar as _cal
from app.db.models import get_db, ManufacturingPlan, ProductionCapacity, ProductHours, ProjectOrder
from datetime import date, timedelta

router = APIRouter()

def _norm_model(product_type, model):
    """型番の表記ゆれを吸収（全角×→X・空白除去・製品種別の接頭辞除去・大文字化）"""
    if not model:
        return ""
    m = str(model).upper().replace("×", "X").replace(" ", "").replace("　", "")
    pt = (product_type or "").upper()
    if pt and m.startswith(pt):
        m = m[len(pt):]
    return m

def _build_ph_lookup(db: Session):
    """所要工数マスタを正規化キーで引けるmap と 製品種別平均 を返す"""
    all_ph = db.query(ProductHours).all()
    ph_map = {(h.product_type, _norm_model(h.product_type, h.model_no)): float(h.required_hours or 0) for h in all_ph}
    pt_sum, pt_cnt = {}, {}
    for h in all_ph:
        pt_sum[h.product_type] = pt_sum.get(h.product_type, 0) + float(h.required_hours or 0)
        pt_cnt[h.product_type] = pt_cnt.get(h.product_type, 0) + 1
    pt_avg = {k: pt_sum[k] / pt_cnt[k] for k in pt_sum if pt_cnt[k]}
    return ph_map, pt_avg

def _plan_required_hours(plan, ph_map, pt_avg):
    """計画の所要工数（正規化突合→無ければ本体のみ種別平均）と、月別按分の内訳を返す。
    副ユニット（is_primary=False）は工数マスタ未登録なら0とし、負荷の重複計上を防ぐ。"""
    hrs = ph_map.get((plan.product_type, _norm_model(plan.product_type, plan.model_no)))
    if not hrs:
        hrs = pt_avg.get(plan.product_type, 0) if getattr(plan, "is_primary", True) else 0
    monthly = {}
    if plan.planned_start and plan.planned_end and hrs:
        td = max((plan.planned_end - plan.planned_start).days, 0) + 1
        cur = plan.planned_start
        while cur <= plan.planned_end:
            monthly[cur.month] = round(monthly.get(cur.month, 0) + hrs / td, 1)
            cur += timedelta(days=1)
    return round(hrs or 0, 1), monthly

# ---- 製造計画 ----

@router.get("/plans")
def list_plans(year: int = Query(None), status: str = Query(None), db: Session = Depends(get_db)):
    """year は年度(3月〜翌2月)。期間内の計画＋日付未設定(未スケジュール)の計画を表示。"""
    q = db.query(ManufacturingPlan).options(joinedload(ManufacturingPlan.project_order))
    if year:
        fy_start = date(year, 3, 1)
        fy_end = date(year + 1, 2, _cal.monthrange(year + 1, 2)[1])
        q = q.filter(
            or_(
                and_(ManufacturingPlan.planned_start >= fy_start, ManufacturingPlan.planned_start <= fy_end),
                and_(ManufacturingPlan.planned_end >= fy_start, ManufacturingPlan.planned_end <= fy_end),
                and_(ManufacturingPlan.planned_start.is_(None), ManufacturingPlan.planned_end.is_(None)),
            )
        )
    if status: q = q.filter(ManufacturingPlan.status == status)
    plans = q.order_by(ManufacturingPlan.planned_start).all()
    ph_map, pt_avg = _build_ph_lookup(db)
    out = []
    for p in plans:
        d = _plan_dict(p)
        total, monthly = _plan_required_hours(p, ph_map, pt_avg)
        d["total_hours"] = total
        d["monthly_hours"] = monthly
        out.append(d)
    return out

@router.post("/plans")
def create_plan(data: dict, db: Session = Depends(get_db)):
    if not data.get("project_order_id"):
        raise HTTPException(400, "案件子IDを選択してください")
    p = ManufacturingPlan(
        project_order_id=data["project_order_id"],
        breakdown_no=data.get("breakdown_no"),
        unit_name=data.get("unit_name"),
        is_primary=data.get("is_primary", True),
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

def _unit_model_of(item):
    """見積明細の spec_json からユニット型式と種別キーを返す（本体>ファン>RV>サイクロン）。無ければNone。"""
    sj = item.spec_json or {}
    for key in ("model", "fan_model", "rv_model", "cyclone_model"):
        v = sj.get(key)
        if v:
            return str(v), key
    return None

def _line_breakdown_map(q):
    """見積明細に内訳番号「{大分類No}-{明細No}」を割り当て {line_item_id: breakdown_no} を返す（見積PDF・発注と同一採番）。"""
    sections = {}
    for item in sorted(q.line_items, key=lambda x: x.line_no):
        sections.setdefault(item.section or "", []).append(item)
    m = {}
    for sec_no, (sec, items) in enumerate(sections.items(), 1):
        for item_no, item in enumerate(items, 1):
            m[str(item.id)] = f"{sec_no}-{item_no}"
    return m

@router.post("/plans/draft-from-estimate")
def draft_from_estimate(data: dict, db: Session = Depends(get_db)):
    """案件子IDの受注採用見積から、ユニット（見積内訳行）ごとに製造計画ドラフトを作成。
    納期(sales_date)を完了予定とし、所要工数から仮の工期を逆算して開始予定を設定する。
    行=ユニット（本体/ファン/RV/サイクロン等）。内訳番号は見積・発注と一致。"""
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
    bmap = _line_breakdown_map(q)
    created, skipped = 0, 0
    for it in q.line_items:
        um = _unit_model_of(it)   # (ユニット型式, 種別キー)
        if not um:
            continue
        model, key = um
        is_primary = (key == "model")   # 本体ラインのみ種別平均フォールバック対象
        ptype = it.product_type
        bno = bmap.get(str(it.id))
        # 重複スキップ（同じ子ID＋型番の計画が既にあれば作らない）。旧・本体のみ計画には内訳番号を補完
        exists = db.query(ManufacturingPlan).filter(
            ManufacturingPlan.project_order_id == po.id,
            ManufacturingPlan.model_no == model,
        ).first()
        if exists:
            if not exists.breakdown_no:
                exists.breakdown_no = bno
                exists.unit_name = exists.unit_name or it.item_name
            skipped += 1
            continue
        # 仮工期: 本体のみ種別平均で代替（副ユニットは実マスタ一致のみ）。無ければ14日
        target = _norm_model(ptype, model)
        cand = db.query(ProductHours).filter(ProductHours.product_type == ptype).all()
        req = next((float(h.required_hours) for h in cand
                    if _norm_model(h.product_type, h.model_no) == target and h.required_hours), None)
        if req is None and is_primary and cand:
            vals = [float(h.required_hours) for h in cand if h.required_hours]
            req = (sum(vals) / len(vals)) if vals else None
        days = max(7, int(math.ceil(req / 16.0))) if req else 14
        planned_start = (end - timedelta(days=days)) if end else None
        db.add(ManufacturingPlan(
            project_order_id=po.id, breakdown_no=bno, unit_name=it.item_name, is_primary=is_primary,
            product_type=ptype, model_no=model,
            planned_start=planned_start, planned_end=end,
            status="未着手", notes=f"見積ドラフト自動作成（内訳{bno}・仮工期{days}日）",
        ))
        created += 1

    db.commit()
    if created == 0 and skipped == 0:
        return {"ok": False, "created": 0, "skipped": 0,
                "message": "見積にユニット（型式）ラインが見つかりませんでした"}
    msg = f"見積から製造計画（ユニット単位）を {created}件 作成しました（仮日程）"
    if skipped:
        msg += f" / 既存 {skipped}件 はスキップ（内訳番号を補完）"
    return {"ok": True, "created": created, "skipped": skipped, "message": msg}

@router.put("/plans/{plan_id}")
def update_plan(plan_id: str, data: dict, db: Session = Depends(get_db)):
    p = db.query(ManufacturingPlan).filter(ManufacturingPlan.id == plan_id).first()
    if not p: raise HTTPException(404)
    for k in ["breakdown_no","unit_name","is_primary","product_type","model_no","planned_start","planned_end","actual_start","actual_end","assigned_to","status","notes"]:
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
        "breakdown_no": p.breakdown_no, "unit_name": p.unit_name, "is_primary": p.is_primary,
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
    ph_map, pt_avg = _build_ph_lookup(db)

    monthly_load = {}
    for p in plans:
        if not p.planned_start or not p.planned_end: continue
        _, monthly = _plan_required_hours(p, ph_map, pt_avg)
        for m, h in monthly.items():
            monthly_load[m] = monthly_load.get(m, 0) + h

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
