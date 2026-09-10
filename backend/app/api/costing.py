# -*- coding: utf-8 -*-
"""製品原価検証 API（管理者専用）

docs/原価検証システム_要件整理と実装方針_20260907.md の ①検証 ②シミュレーション ③レポート。
既存テーブル（material_masters / unit_masters / suppliers / product_hours / estimate_*）を参照し、
原価固有のデータは cost_* テーブルに持つ。計算は app/costing_engine.py（純粋関数）。
"""
from __future__ import annotations
import io
import re
import uuid
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc

from app.db.models import (
    get_db, User, MaterialMaster, UnitMaster, Supplier, ProductHours,
    CostMaterialExt, CostMaterialAlias, CostMaterialPrice, CostPriceAdjustment,
    CostBomLine, CostSetting, CostScenario, CostCalculation,
)
from app.api.auth import require_admin
from app import costing_engine as eng
from app import costing_import as imp

router = APIRouter(dependencies=[Depends(require_admin)])

SETTING_DEFAULTS = {"labor_rate_per_hour": 2500, "overhead_rate": None, "target_margin_rate": None}
SETTING_LABELS = {"labor_rate_per_hour": "時間単価（円/h）", "overhead_rate": "経費率（%）", "target_margin_rate": "目標粗利率（%）"}
COST_UNIT_TYPE = "原価ユニット"


def _f(v):
    return float(v) if isinstance(v, (int, float, Decimal)) else None


def _d(v) -> Optional[dt.date]:
    if v in (None, ""):
        return None
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


def _uuid(v, required: bool = True):
    """リクエストの ID を UUID に揃える（不正な文字列で 500 にせず 400 を返す。SQLite でも動く）"""
    if v in (None, ""):
        if required:
            raise HTTPException(400, "ID が指定されていません")
        return None
    try:
        return uuid.UUID(str(v))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(400, f"ID の形式が不正です: {v}")


def _num(v):
    """画面からの数値（文字列のことがある）を float に。空・不正は None"""
    if v in (None, "", False):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean_scenario(sc) -> dict:
    """シナリオの数値項目を正規化する。倍率 1 は「指定なし」として落とす"""
    sc = dict(sc or {})
    out = {}
    for k in ("steel_pct", "labor_rate", "overhead_rate", "target_margin_rate"):
        v = _num(sc.get(k))
        if v is not None:
            out[k] = v
    cf = {}
    for c, v in (sc.get("category_factors") or {}).items():
        f = _num(v)
        if f is not None and f > 0 and abs(f - 1.0) > 1e-9:
            cf[c] = f
    if cf:
        out["category_factors"] = cf
    mo = {}
    for mid, v in (sc.get("material_overrides") or {}).items():
        f = _num(v)
        if f is not None:
            mo[str(mid)] = f
    if mo:
        out["material_overrides"] = mo
    for k in ("supplier_overrides", "party_id"):
        if sc.get(k):
            out[k] = sc[k]
    if sc.get("apply_line_markup"):
        out["apply_line_markup"] = True
    return out


def _norm_code(s: str) -> str:
    return re.sub(r"[\s×xX*]", "X", (s or "").upper()).replace("XX", "X")


# ------------------------------------------------------------
# セットアップ
# ------------------------------------------------------------
@router.get("/setup-tables")
def setup_tables(db: Session = Depends(get_db)):
    """cost_* テーブルを作成し、時間単価の初期値（2,500 円/h）を投入する（冪等）"""
    from app.db.models import Base, engine
    tables = [m.__table__ for m in (CostMaterialExt, CostMaterialAlias, CostMaterialPrice, CostPriceAdjustment,
                                     CostBomLine, CostSetting, CostScenario, CostCalculation)]
    Base.metadata.create_all(bind=engine, tables=tables)
    if not db.query(CostSetting).filter(CostSetting.key == "labor_rate_per_hour").first():
        db.add(CostSetting(key="labor_rate_per_hour", value=2500, effective_date=dt.date(2020, 1, 1),
                           notes="初期値（2026-09-08 井上電設様回答）"))
        db.commit()
    return {"ok": True, "message": "原価検証テーブルを作成しました"}


# ------------------------------------------------------------
# 設定
# ------------------------------------------------------------
def _settings_as_of(db: Session, date: dt.date) -> dict:
    out = dict(SETTING_DEFAULTS)
    rows = (db.query(CostSetting).filter(CostSetting.effective_date <= date)
            .order_by(CostSetting.key, CostSetting.effective_date.desc(), CostSetting.created_at.desc()).all())
    seen = set()
    for r in rows:
        if r.key in seen:
            continue
        seen.add(r.key)
        out[r.key] = _f(r.value)
    return out


@router.get("/settings")
def list_settings(db: Session = Depends(get_db)):
    rows = db.query(CostSetting).order_by(CostSetting.key, CostSetting.effective_date.desc()).all()
    return {
        "current": _settings_as_of(db, dt.date.today()),
        "labels": SETTING_LABELS,
        "history": [{"id": str(r.id), "key": r.key, "label": SETTING_LABELS.get(r.key, r.key), "value": _f(r.value),
                     "effective_date": r.effective_date.isoformat(), "notes": r.notes} for r in rows],
    }


@router.post("/settings")
def add_setting(data: dict, db: Session = Depends(get_db)):
    key = data.get("key")
    if key not in SETTING_DEFAULTS:
        raise HTTPException(400, "不明な設定キーです")
    row = CostSetting(key=key, value=data.get("value"), effective_date=_d(data.get("effective_date")) or dt.date.today(),
                      notes=data.get("notes"))
    db.add(row); db.commit()
    return {"ok": True, "id": str(row.id)}


@router.delete("/settings/{setting_id}")
def delete_setting(setting_id: str, db: Session = Depends(get_db)):
    r = db.query(CostSetting).filter(CostSetting.id == _uuid(setting_id)).first()
    if not r:
        raise HTTPException(404)
    db.delete(r); db.commit()
    return {"ok": True}


# ------------------------------------------------------------
# コンテキスト（DB → 計算エンジン入力）
# ------------------------------------------------------------
def _load_ctx(db: Session, unit_ids: Optional[list] = None) -> dict:
    mats = {}
    q = db.query(MaterialMaster, CostMaterialExt).outerjoin(CostMaterialExt, CostMaterialExt.material_id == MaterialMaster.id)
    for m, ext in q.all():
        mats[str(m.id)] = {
            "id": str(m.id), "code": m.material_code, "name": m.material_name,
            "category": ext.category if ext else None, "price_unit": (ext.price_unit if ext else None) or m.unit,
            "preferred_supplier_id": str(ext.preferred_supplier_id) if ext and ext.preferred_supplier_id else None,
            "price_policy": (ext.price_policy if ext else None) or "preferred",
        }
    prices = defaultdict(list)
    for p in db.query(CostMaterialPrice).all():
        prices[str(p.material_id)].append({"supplier_id": str(p.supplier_id) if p.supplier_id else None,
                                           "effective_date": p.effective_date, "price": float(p.price)})
    adjustments = defaultdict(list)
    for a in db.query(CostPriceAdjustment).all():
        adjustments[str(a.material_id)].append({
            "party_type": a.party_type, "party_id": str(a.party_id) if a.party_id else None,
            "adjust_type": a.adjust_type, "value": float(a.value),
            "effective_from": a.effective_from, "effective_to": a.effective_to, "party_name": a.party_name,
        })
    units = {}
    for u in db.query(UnitMaster).all():
        units[str(u.id)] = {"id": str(u.id), "code": u.unit_code, "name": u.unit_name, "unit_type": u.unit_type, "lines": []}
    for ln in db.query(CostBomLine).order_by(CostBomLine.sort_order, CostBomLine.created_at).all():
        uid = str(ln.unit_id)
        if uid not in units:
            continue
        units[uid]["lines"].append({
            "id": str(ln.id), "section": ln.section, "label": ln.label, "line_type": ln.line_type,
            "material_id": str(ln.material_id) if ln.material_id else None,
            "sub_unit_id": str(ln.sub_unit_id) if ln.sub_unit_id else None,
            "qty": float(ln.qty or 0), "qty_expr": ln.qty_expr, "markup_factor": float(ln.markup_factor or 1),
            "note": ln.notes, "is_option": ln.is_option,
        })
    return {"materials": mats, "prices": dict(prices), "adjustments": dict(adjustments), "units": units}


def _hours_for(db: Session, code: str):
    """product_hours（例 BFR / 3X6）を型式コード（BFR3X6）で引く"""
    target = _norm_code(code)
    for ph in db.query(ProductHours).all():
        if _norm_code((ph.product_type or "") + (ph.model_no or "")) == target:
            return float(ph.required_hours)
    return None


def _std_price_for(db: Session, unit: UnitMaster):
    if unit.standard_price:
        return float(unit.standard_price)
    target = _norm_code(unit.unit_code)
    try:
        from app.db.models import EstimateBfrBody, EstimateBfqBody, EstimatePlFan
        for model in (EstimateBfrBody, EstimateBfqBody, EstimatePlFan):
            for r in db.query(model).all():
                code = getattr(r, "model_code", None)
                price = getattr(r, "base_price", None) or getattr(r, "price", None)
                if code and price and _norm_code(code) == target:
                    return float(price)
    except Exception:
        return None
    return None


# ------------------------------------------------------------
# ユニット（型式）と明細
# ------------------------------------------------------------
def _unit_dict(u: UnitMaster, line_count: int, sections: list) -> dict:
    return {"id": str(u.id), "unit_code": u.unit_code, "unit_name": u.unit_name, "unit_type": u.unit_type,
            "model_no": u.model_no, "standard_price": _f(u.standard_price), "standard_hours": _f(u.standard_hours),
            "line_count": line_count, "sections": sections, "notes": u.notes}


@router.get("/units")
def list_units(search: Optional[str] = None, db: Session = Depends(get_db)):
    counts = dict(db.query(CostBomLine.unit_id, sqlfunc.count(CostBomLine.id)).group_by(CostBomLine.unit_id).all())
    secs = defaultdict(list)
    for uid, sec in db.query(CostBomLine.unit_id, CostBomLine.section).distinct().all():
        if sec and sec not in secs[uid]:
            secs[uid].append(sec)
    q = db.query(UnitMaster).filter(UnitMaster.id.in_(list(counts.keys())) if counts else False)
    if search:
        q = q.filter(or_(UnitMaster.unit_code.ilike(f"%{search}%"), UnitMaster.unit_name.ilike(f"%{search}%")))
    rows = [_unit_dict(u, counts.get(u.id, 0), secs.get(u.id, [])) for u in q.order_by(UnitMaster.unit_code).all()]
    return rows


@router.get("/units/{unit_id}/lines")
def list_lines(unit_id: str, db: Session = Depends(get_db)):
    u = db.query(UnitMaster).filter(UnitMaster.id == _uuid(unit_id)).first()
    if not u:
        raise HTTPException(404, "ユニットが見つかりません")
    rows = db.query(CostBomLine).filter(CostBomLine.unit_id == _uuid(unit_id)).order_by(CostBomLine.sort_order).all()
    return {"unit": _unit_dict(u, len(rows), []), "lines": [_line_dict(l) for l in rows]}


def _line_dict(l: CostBomLine) -> dict:
    return {
        "id": str(l.id), "unit_id": str(l.unit_id), "section": l.section, "label": l.label, "line_type": l.line_type,
        "material_id": str(l.material_id) if l.material_id else None,
        "material_code": l.material.material_code if l.material else None,
        "material_name": l.material.material_name if l.material else None,
        "sub_unit_id": str(l.sub_unit_id) if l.sub_unit_id else None,
        "sub_unit_code": l.sub_unit.unit_code if l.sub_unit else None,
        "qty": _f(l.qty), "qty_expr": l.qty_expr, "yield_basis": l.yield_basis,
        "markup_factor": _f(l.markup_factor), "is_option": l.is_option, "source_ref": l.source_ref,
        "sort_order": l.sort_order, "notes": l.notes,
    }


@router.post("/units/{unit_id}/lines")
def add_line(unit_id: str, data: dict, db: Session = Depends(get_db)):
    if not db.query(UnitMaster).filter(UnitMaster.id == _uuid(unit_id)).first():
        raise HTTPException(404, "ユニットが見つかりません")
    if data.get("line_type") not in ("weight", "measure", "count", "subcontract", "paint", "subassembly"):
        raise HTTPException(400, "line_type が不正です")
    if data["line_type"] == "subassembly" and not data.get("sub_unit_id"):
        raise HTTPException(400, "サブアセンブリ行には sub_unit_id が必要です")
    if data["line_type"] != "subassembly" and not data.get("material_id"):
        raise HTTPException(400, "資材を選択してください")
    max_sort = db.query(sqlfunc.max(CostBomLine.sort_order)).filter(CostBomLine.unit_id == _uuid(unit_id)).scalar() or 0
    l = CostBomLine(unit_id=_uuid(unit_id), section=data.get("section"), label=data.get("label"), line_type=data["line_type"],
                    material_id=_uuid(data.get("material_id"), False), sub_unit_id=_uuid(data.get("sub_unit_id"), False),
                    qty=data.get("qty") or 0, qty_expr=data.get("qty_expr"), yield_basis=data.get("yield_basis"),
                    markup_factor=data.get("markup_factor") or 1, is_option=bool(data.get("is_option")),
                    sort_order=data.get("sort_order") if data.get("sort_order") is not None else max_sort + 1,
                    notes=data.get("notes"), source_ref="手入力")
    db.add(l); db.commit(); db.refresh(l)
    return _line_dict(l)


@router.put("/lines/{line_id}")
def update_line(line_id: str, data: dict, db: Session = Depends(get_db)):
    l = db.query(CostBomLine).filter(CostBomLine.id == _uuid(line_id)).first()
    if not l:
        raise HTTPException(404)
    for k in ("section", "label", "line_type", "material_id", "sub_unit_id", "qty", "qty_expr", "yield_basis",
              "markup_factor", "is_option", "sort_order", "notes"):
        if k in data:
            v = data[k] if data[k] != "" else None
            if k in ("material_id", "sub_unit_id"):
                v = _uuid(v, False)
            setattr(l, k, v)
    db.commit(); db.refresh(l)
    return _line_dict(l)


@router.delete("/lines/{line_id}")
def delete_line(line_id: str, db: Session = Depends(get_db)):
    l = db.query(CostBomLine).filter(CostBomLine.id == _uuid(line_id)).first()
    if not l:
        raise HTTPException(404)
    db.delete(l); db.commit()
    return {"ok": True}


# ------------------------------------------------------------
# 計算
# ------------------------------------------------------------
def _calc(db: Session, ctx: dict, unit: UnitMaster, price_date: dt.date, scenario: dict) -> dict:
    settings = _settings_as_of(db, price_date)
    hours = _f(unit.standard_hours) or _hours_for(db, unit.unit_code)
    return eng.calc_product(ctx, str(unit.id), price_date, scenario, standard_hours=hours,
                            standard_price=_std_price_for(db, unit), settings=settings)


@router.post("/calculate")
def calculate(data: dict, db: Session = Depends(get_db)):
    """{unit_id, price_date, scenario?, compare_date?} → 製品原価。compare_date を渡すと差分要因も返す"""
    unit = db.query(UnitMaster).filter(UnitMaster.id == _uuid(data.get("unit_id"))).first()
    if not unit:
        raise HTTPException(404, "ユニットが見つかりません")
    price_date = _d(data.get("price_date")) or dt.date.today()
    scenario = _clean_scenario(data.get("scenario"))
    ctx = _load_ctx(db)
    try:
        res = _calc(db, ctx, unit, price_date, scenario)
        cmp_date = _d(data.get("compare_date"))
        if cmp_date:
            base = eng.calc_unit(ctx, str(unit.id), cmp_date, {})
            res["compare"] = {"date": cmp_date.isoformat(), **eng.diff_results(base, res["material"])}
        if scenario:
            base = _calc(db, ctx, unit, price_date, {})
            res["base"] = {"material_cost": base["material_cost"], "manufacturing_cost": base["manufacturing_cost"],
                           "gross_margin_rate": base["gross_margin_rate"], "required_price": base["required_price"]}
    except eng.CostError as e:
        raise HTTPException(400, str(e))
    # supplier 名を付ける
    names = {str(s.id): s.name for s in db.query(Supplier).all()}
    for l in res["material"]["lines"]:
        l["supplier_name"] = names.get(l.get("supplier_id"))
    res["unit"] = _unit_dict(unit, len(res["material"]["lines"]), [s["section"] for s in res["material"]["sections"]])
    return res


@router.post("/calculate/batch")
def calculate_batch(data: dict, db: Session = Depends(get_db)):
    """{unit_ids[], price_date, scenario} → 型式横断の一覧（ベースとシナリオの両方）"""
    price_date = _d(data.get("price_date")) or dt.date.today()
    scenario = _clean_scenario(data.get("scenario"))
    ctx = _load_ctx(db)
    out = []
    for uid in data.get("unit_ids") or []:
        unit = db.query(UnitMaster).filter(UnitMaster.id == _uuid(uid)).first()
        if not unit:
            continue
        try:
            base = _calc(db, ctx, unit, price_date, {})
            sc = _calc(db, ctx, unit, price_date, scenario) if scenario else base
        except eng.CostError as e:
            out.append({"unit_id": uid, "unit_code": unit.unit_code, "error": str(e)})
            continue
        out.append({
            "unit_id": uid, "unit_code": unit.unit_code, "unit_name": unit.unit_name,
            "base": _summary(base), "scenario": _summary(sc),
            "warnings": len(sc["material"]["warnings"]),
        })
    return out


def _summary(r: dict) -> dict:
    return {k: r.get(k) for k in ("material_cost", "labor_cost", "overhead_cost", "manufacturing_cost",
                                  "standard_price", "gross_margin", "gross_margin_rate", "required_price")} | {
        "steel_total": r["material"]["steel_total"], "purchased_total": r["material"]["purchased_total"],
        "steel_ratio": r["material"]["steel_ratio"]}


@router.post("/calculations")
def save_calculation(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    unit = db.query(UnitMaster).filter(UnitMaster.id == _uuid(data.get("unit_id"))).first()
    if not unit:
        raise HTTPException(404)
    price_date = _d(data.get("price_date")) or dt.date.today()
    scenario = _clean_scenario(data.get("scenario"))
    res = _calc(db, _load_ctx(db), unit, price_date, scenario)
    row = CostCalculation(unit_id=unit.id, price_date=price_date, scenario_id=_uuid(data.get("scenario_id"), False),
                          total=res["material_cost"], steel_total=res["material"]["steel_total"],
                          purchased_total=res["material"]["purchased_total"], manufacturing_cost=res["manufacturing_cost"],
                          result={"summary": _summary(res), "sections": res["material"]["sections"], "scenario": scenario},
                          label=data.get("label"), created_by=current_user.id)
    db.add(row); db.commit()
    return {"ok": True, "id": str(row.id)}


@router.get("/calculations")
def list_calculations(unit_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(CostCalculation)
    if unit_id:
        q = q.filter(CostCalculation.unit_id == _uuid(unit_id))
    rows = q.order_by(CostCalculation.created_at.desc()).limit(200).all()
    return [{"id": str(r.id), "unit_id": str(r.unit_id), "unit_code": r.unit.unit_code if r.unit else None,
             "price_date": r.price_date.isoformat(), "total": _f(r.total), "steel_total": _f(r.steel_total),
             "purchased_total": _f(r.purchased_total), "manufacturing_cost": _f(r.manufacturing_cost),
             "label": r.label, "created_at": r.created_at.isoformat() if r.created_at else None,
             "summary": (r.result or {}).get("summary")} for r in rows]


# ------------------------------------------------------------
# シナリオ
# ------------------------------------------------------------
@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    return [{"id": str(s.id), "name": s.name, "adjustments": s.adjustments or {}, "notes": s.notes,
             "updated_at": s.updated_at.isoformat() if s.updated_at else None}
            for s in db.query(CostScenario).order_by(CostScenario.updated_at.desc()).all()]


@router.post("/scenarios")
def save_scenario(data: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not data.get("name"):
        raise HTTPException(400, "シナリオ名は必須です")
    s = db.query(CostScenario).filter(CostScenario.id == _uuid(data["id"])).first() if data.get("id") else None
    if s is None:
        s = CostScenario(name=data["name"], created_by=current_user.id)
        db.add(s)
    s.name = data["name"]; s.adjustments = data.get("adjustments") or {}; s.notes = data.get("notes")
    db.commit(); db.refresh(s)
    return {"ok": True, "id": str(s.id)}


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str, db: Session = Depends(get_db)):
    s = db.query(CostScenario).filter(CostScenario.id == _uuid(scenario_id)).first()
    if not s:
        raise HTTPException(404)
    db.delete(s); db.commit()
    return {"ok": True}


# ------------------------------------------------------------
# 資材・単価
# ------------------------------------------------------------
def _material_dict(m: MaterialMaster, ext: Optional[CostMaterialExt], latest: dict, aliases: list, usage: int,
                   supplier_names: dict) -> dict:
    return {
        "id": str(m.id), "material_code": m.material_code, "material_name": m.material_name, "unit": m.unit,
        "category": ext.category if ext else None, "price_unit": (ext.price_unit if ext else None) or m.unit,
        "steel_grade": ext.steel_grade if ext else None, "thickness_mm": _f(ext.thickness_mm) if ext else None,
        "stock_size": ext.stock_size if ext else None,
        "piece_weight_kg": _f(ext.piece_weight_kg) if ext else None, "piece_length_m": _f(ext.piece_length_m) if ext else None,
        "sheet_area_m2": _f(ext.sheet_area_m2) if ext else None, "density": _f(ext.density) if ext else None,
        "code_source": ext.code_source if ext else None,
        "preferred_supplier_id": str(ext.preferred_supplier_id) if ext and ext.preferred_supplier_id else None,
        "preferred_supplier_name": supplier_names.get(str(ext.preferred_supplier_id)) if ext and ext.preferred_supplier_id else None,
        "price_policy": (ext.price_policy if ext else None) or "preferred",
        "basis_note": ext.basis_note if ext else None, "notes": ext.notes if ext else m.notes,
        "latest_prices": latest, "aliases": aliases, "usage": usage,
    }


@router.get("/materials")
def list_materials(search: Optional[str] = None, category: Optional[str] = None,
                   only_costing: bool = True, limit: int = Query(500, le=2000), db: Session = Depends(get_db)):
    """資材一覧（原価属性・仕入先別の最新単価・別名・使用行数つき）"""
    q = db.query(MaterialMaster, CostMaterialExt).outerjoin(CostMaterialExt, CostMaterialExt.material_id == MaterialMaster.id)
    if only_costing:
        q = q.filter(CostMaterialExt.material_id.isnot(None))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(MaterialMaster.material_name.ilike(like), MaterialMaster.material_code.ilike(like),
                         MaterialMaster.id.in_(db.query(CostMaterialAlias.material_id).filter(CostMaterialAlias.alias.ilike(like)))))
    if category:
        q = q.filter(CostMaterialExt.category == category)
    rows = q.order_by(MaterialMaster.material_code).limit(limit).all()
    ids = [m.id for m, _ in rows]
    supplier_names = {str(s.id): s.name for s in db.query(Supplier).all()}
    latest = defaultdict(dict)
    if ids:
        for p in db.query(CostMaterialPrice).filter(CostMaterialPrice.material_id.in_(ids)).order_by(CostMaterialPrice.effective_date).all():
            sid = str(p.supplier_id) if p.supplier_id else "-"
            latest[str(p.material_id)][sid] = {"supplier_id": sid if sid != "-" else None,
                                               "supplier_name": supplier_names.get(sid, "（仕入先未指定）"),
                                               "price": float(p.price), "effective_date": p.effective_date.isoformat(),
                                               "price_unit": p.price_unit}
    aliases = defaultdict(list)
    if ids:
        for a in db.query(CostMaterialAlias).filter(CostMaterialAlias.material_id.in_(ids)).all():
            aliases[str(a.material_id)].append({"id": str(a.id), "alias": a.alias})
    usage = dict(db.query(CostBomLine.material_id, sqlfunc.count(CostBomLine.id)).group_by(CostBomLine.material_id).all())
    return [_material_dict(m, ext, list(latest[str(m.id)].values()), aliases[str(m.id)], usage.get(m.id, 0), supplier_names)
            for m, ext in rows]


@router.post("/materials")
def create_material(data: dict, db: Session = Depends(get_db)):
    """資材を新規登録（既存の material_masters に行を追加し、原価属性を付ける）"""
    name = (data.get("material_name") or "").strip()
    if not name:
        raise HTTPException(400, "資材名は必須です")
    code = (data.get("material_code") or "").strip() or imp.temp_code(name)
    if db.query(MaterialMaster).filter(MaterialMaster.material_code == code).first():
        raise HTTPException(400, f"資材コード {code} は既に存在します")
    m = MaterialMaster(material_code=code, material_name=name, unit=data.get("price_unit") or "個")
    db.add(m); db.flush()
    ext = CostMaterialExt(material_id=m.id, category=data.get("category") or "購入品", price_unit=data.get("price_unit") or "個",
                          code_source="TECHS" if data.get("material_code") else "仮")
    db.add(ext)
    if data.get("alias"):
        db.add(CostMaterialAlias(alias=data["alias"], material_id=m.id))
    db.commit()
    return {"ok": True, "id": str(m.id), "material_code": code}


@router.put("/materials/{material_id}/ext")
def update_material_ext(material_id: str, data: dict, db: Session = Depends(get_db)):
    m = db.query(MaterialMaster).filter(MaterialMaster.id == _uuid(material_id)).first()
    if not m:
        raise HTTPException(404, "資材が見つかりません")
    ext = db.query(CostMaterialExt).filter(CostMaterialExt.material_id == _uuid(material_id)).first()
    if ext is None:
        ext = CostMaterialExt(material_id=m.id)
        db.add(ext)
    for k in ("category", "price_unit", "steel_grade", "thickness_mm", "stock_size", "piece_weight_kg", "piece_length_m",
              "sheet_area_m2", "density", "code_source", "preferred_supplier_id", "price_policy", "basis_note", "notes"):
        if k in data:
            v = data[k] if data[k] != "" else None
            if k == "preferred_supplier_id":
                v = _uuid(v, False)
            setattr(ext, k, v)
    if data.get("material_name"):
        m.material_name = data["material_name"]
    if data.get("material_code") and data["material_code"] != m.material_code:
        if db.query(MaterialMaster).filter(MaterialMaster.material_code == data["material_code"]).first():
            raise HTTPException(400, "その資材コードは既に使われています")
        m.material_code = data["material_code"]
        ext.code_source = "TECHS"
    db.commit()
    return {"ok": True}


@router.post("/materials/{material_id}/aliases")
def add_alias(material_id: str, data: dict, db: Session = Depends(get_db)):
    alias = imp.norm_label(data.get("alias"))
    if not alias:
        raise HTTPException(400, "別名を入力してください")
    ex = db.query(CostMaterialAlias).filter(CostMaterialAlias.alias == alias).first()
    if ex:
        ex.material_id = _uuid(material_id)
    else:
        db.add(CostMaterialAlias(alias=alias, material_id=_uuid(material_id)))
    db.commit()
    return {"ok": True}


@router.delete("/aliases/{alias_id}")
def delete_alias(alias_id: str, db: Session = Depends(get_db)):
    a = db.query(CostMaterialAlias).filter(CostMaterialAlias.id == _uuid(alias_id)).first()
    if not a:
        raise HTTPException(404)
    db.delete(a); db.commit()
    return {"ok": True}


@router.get("/materials/{material_id}/prices")
def list_prices(material_id: str, db: Session = Depends(get_db)):
    names = {str(s.id): s.name for s in db.query(Supplier).all()}
    rows = (db.query(CostMaterialPrice).filter(CostMaterialPrice.material_id == _uuid(material_id))
            .order_by(CostMaterialPrice.effective_date.desc()).all())
    return [{"id": str(p.id), "supplier_id": str(p.supplier_id) if p.supplier_id else None,
             "supplier_name": names.get(str(p.supplier_id), "（仕入先未指定）"), "effective_date": p.effective_date.isoformat(),
             "price": float(p.price), "price_unit": p.price_unit, "basis_expr": p.basis_expr, "source": p.source,
             "notes": p.notes} for p in rows]


@router.post("/materials/{material_id}/prices")
def add_price(material_id: str, data: dict, db: Session = Depends(get_db)):
    if data.get("price") in (None, ""):
        raise HTTPException(400, "単価を入力してください")
    ext = db.query(CostMaterialExt).filter(CostMaterialExt.material_id == _uuid(material_id)).first()
    p = CostMaterialPrice(material_id=_uuid(material_id), supplier_id=_uuid(data.get("supplier_id"), False),
                          effective_date=_d(data.get("effective_date")) or dt.date.today(), price=data["price"],
                          price_unit=data.get("price_unit") or (ext.price_unit if ext else None),
                          basis_expr=data.get("basis_expr"), source=data.get("source") or "手入力", notes=data.get("notes"))
    db.add(p); db.commit()
    return {"ok": True, "id": str(p.id)}


@router.delete("/prices/{price_id}")
def delete_price(price_id: str, db: Session = Depends(get_db)):
    p = db.query(CostMaterialPrice).filter(CostMaterialPrice.id == _uuid(price_id)).first()
    if not p:
        raise HTTPException(404)
    db.delete(p); db.commit()
    return {"ok": True}


@router.post("/prices/bulk")
def bulk_prices(data: dict, db: Session = Depends(get_db)):
    """単価の一括改定 {effective_date, supplier_id?, source?, rows:[{material_id|material_code|alias, price}]}"""
    eff = _d(data.get("effective_date")) or dt.date.today()
    created, missing = 0, []
    alias_map = {a.alias: a.material_id for a in db.query(CostMaterialAlias).all()}
    code_map = {m.material_code: m.id for m in db.query(MaterialMaster).all()}
    for r in data.get("rows") or []:
        mid = _uuid(r.get("material_id"), False) or code_map.get(r.get("material_code")) or alias_map.get(imp.norm_label(r.get("alias")))
        if not mid or r.get("price") in (None, ""):
            missing.append(r)
            continue
        db.add(CostMaterialPrice(material_id=_uuid(mid), supplier_id=_uuid(data.get("supplier_id"), False), effective_date=eff,
                                 price=r["price"], source=data.get("source") or "スプレッドシート", notes=r.get("notes")))
        created += 1
    db.commit()
    return {"ok": True, "created": created, "missing": missing}


@router.get("/materials/{material_id}/adjustments")
def list_adjustments(material_id: str, db: Session = Depends(get_db)):
    rows = db.query(CostPriceAdjustment).filter(CostPriceAdjustment.material_id == _uuid(material_id)).all()
    return [{"id": str(a.id), "party_type": a.party_type, "party_id": str(a.party_id) if a.party_id else None,
             "party_name": a.party_name, "adjust_type": a.adjust_type, "value": float(a.value),
             "effective_from": a.effective_from.isoformat() if a.effective_from else None,
             "effective_to": a.effective_to.isoformat() if a.effective_to else None, "notes": a.notes} for a in rows]


@router.post("/materials/{material_id}/adjustments")
def add_adjustment(material_id: str, data: dict, db: Session = Depends(get_db)):
    if data.get("value") in (None, ""):
        raise HTTPException(400, "調整値を入力してください")
    party_name = data.get("party_name")
    if data.get("party_id") and not party_name:
        s = db.query(Supplier).filter(Supplier.id == _uuid(data["party_id"])).first()
        party_name = s.name if s else None
    a = CostPriceAdjustment(material_id=_uuid(material_id), party_type=data.get("party_type") or "supplier",
                            party_id=_uuid(data.get("party_id"), False), party_name=party_name,
                            adjust_type=data.get("adjust_type") or "percent", value=data["value"],
                            effective_from=_d(data.get("effective_from")), effective_to=_d(data.get("effective_to")),
                            notes=data.get("notes"))
    db.add(a); db.commit()
    return {"ok": True, "id": str(a.id)}


@router.delete("/adjustments/{adj_id}")
def delete_adjustment(adj_id: str, db: Session = Depends(get_db)):
    a = db.query(CostPriceAdjustment).filter(CostPriceAdjustment.id == _uuid(adj_id)).first()
    if not a:
        raise HTTPException(404)
    db.delete(a); db.commit()
    return {"ok": True}


@router.get("/materials/{material_id}/compare")
def compare_suppliers(material_id: str, price_date: Optional[str] = None, db: Session = Depends(get_db)):
    """仕入先別の単価比較（指定日時点）と、採用される単価"""
    ctx = _load_ctx(db)
    d = _d(price_date) or dt.date.today()
    rp = eng.resolve_price(ctx, material_id, d, {})
    names = {str(s.id): s.name for s in db.query(Supplier).all()}
    return {"price_date": d.isoformat(), "chosen_price": rp["price"], "chosen_supplier_id": rp["supplier_id"],
            "chosen_supplier_name": names.get(str(rp["supplier_id"]), "（仕入先未指定）") if rp["price"] is not None else None,
            "source": rp["source"], "adjustment": rp.get("adjustment"),
            "candidates": [{**c, "supplier_name": names.get(str(c["supplier_id"]), "（仕入先未指定）"),
                            "effective_date": c["effective_date"].isoformat()} for c in rp["candidates"]]}


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db)):
    return [{"id": str(s.id), "name": s.name, "supplier_code": s.supplier_code}
            for s in db.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name).all()]  # noqa: E712


@router.get("/price-dates")
def price_dates(db: Session = Depends(get_db)):
    rows = db.query(CostMaterialPrice.effective_date).distinct().order_by(CostMaterialPrice.effective_date.desc()).all()
    return [r[0].isoformat() for r in rows]


# ------------------------------------------------------------
# 検証
# ------------------------------------------------------------
@router.get("/verify")
def verify(price_date: Optional[str] = None, stale_days: int = 400, db: Session = Depends(get_db)):
    """全ユニットを計算し、単価未解決・資材属性なし・古い単価・別名重複・小計外（取込時の警告）を一覧にする"""
    d = _d(price_date) or dt.date.today()
    ctx = _load_ctx(db)
    findings = []
    unit_totals = []
    for uid, u in ctx["units"].items():
        if not u["lines"]:
            continue
        try:
            res = eng.calc_unit(ctx, uid, d, {})
        except eng.CostError as e:
            findings.append({"kind": "cycle", "unit_code": u["code"], "message": str(e)})
            continue
        unit_totals.append({"unit_id": uid, "unit_code": u["code"], "total": res["total"],
                            "warnings": len(res["warnings"])})
        for w in res["warnings"]:
            if w.get("via"):
                continue
            findings.append({"kind": "unresolved_price", "unit_id": uid, "unit_code": u["code"], "section": w.get("section"),
                             "label": w.get("label"), "material_id": w.get("material_id"), "line_id": w.get("line_id"),
                             "message": w["message"]})
        for l in res["lines"]:
            if l.get("material_id") and l.get("price_date") and (d - eng._to_date(l["price_date"])).days > stale_days:
                findings.append({"kind": "stale_price", "unit_id": uid, "unit_code": u["code"], "section": l["section"],
                                 "label": l["label"], "material_id": l["material_id"],
                                 "message": f"単価の時点が古い（{l['price_date']}）"})
    # 資材属性（種別）なし
    for mid, m in ctx["materials"].items():
        if mid in ctx["prices"] and not m.get("category"):
            findings.append({"kind": "no_category", "material_id": mid, "label": m["name"], "message": "原価属性（種別・単価単位）が未設定"})
    # 取込時に小計外だった行（notes に印）
    for l in db.query(CostBomLine).filter(CostBomLine.notes.like("%小計外%")).all():
        findings.append({"kind": "orphan_import", "unit_id": str(l.unit_id), "unit_code": l.unit.unit_code if l.unit else None,
                         "section": l.section, "label": l.label, "line_id": str(l.id),
                         "message": "Excel では部位小計に含まれていなかった行（取込時に採用済み）"})
    kinds = defaultdict(int)
    for f in findings:
        kinds[f["kind"]] += 1
    return {"price_date": d.isoformat(), "units": unit_totals, "findings": findings, "counts": dict(kinds)}


# ------------------------------------------------------------
# Excel 取込
# ------------------------------------------------------------
@router.post("/import/excel")
async def import_excel(file: UploadFile = File(...), apply: bool = False, include_orphans: bool = False,
                       db: Session = Depends(get_db)):
    """原価ブック（BFR/PLD/BFQ 様式）を解析。apply=false ならプレビュー（Excel 合計との突合）だけ返す。"""
    content = await file.read()
    try:
        parsed = imp.parse_workbook(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"解析できません: {e}")
    ctx_mem = imp.build_context(parsed, include_orphans=include_orphans)
    new_date = parsed["master"]["price_dates"]["new"]
    preview = []
    for u in parsed["units"]:
        try:
            res = eng.calc_unit(ctx_mem, u["unit_code"], new_date, {"apply_line_markup": True})
            res_std = eng.calc_unit(ctx_mem, u["unit_code"], new_date, {})
            total, total_std, warn = res["total"], res_std["total"], len(res["warnings"])
        except eng.CostError as e:
            total, total_std, warn = None, None, 1
            u["warnings"].append({"kind": "cycle", "sheet": u["sheet"], "row": 0, "label": "", "message": str(e)})
        preview.append({
            "sheet": u["sheet"], "unit_code": u["unit_code"], "unit_name": u["unit_name"], "lines": len(u["lines"]),
            "options": len([l for l in u["lines"] if l.get("is_option")]),
            "orphans": len([l for l in u["lines"] if l["orphan"]]),
            "excel_total": u["excel_total"], "computed_total": total, "computed_total_std": total_std,
            "diff": (total - u["excel_total"]) if (total is not None and u["excel_total"] is not None) else None,
            "unresolved": warn,
        })
    result = {"file": file.filename, "price_dates": {k: v.isoformat() for k, v in parsed["master"]["price_dates"].items()},
              "materials": len(parsed["master"]["materials"]), "units": preview, "warnings": parsed["warnings"][:500],
              "applied": False}
    if not apply:
        return result
    result.update(_apply_import(db, parsed, include_orphans, file.filename))
    result["applied"] = True
    return result


def _apply_import(db: Session, parsed: dict, include_orphans: bool, filename: str) -> dict:
    stats = defaultdict(int)
    alias_rows = {a.alias: a for a in db.query(CostMaterialAlias).all()}
    code_rows = {m.material_code: m for m in db.query(MaterialMaster).all()}
    ext_cache = {e.material_id: e for e in db.query(CostMaterialExt).all()}
    key_to_mid = {}

    # TECHS 品番: 明細行に併記された品番を名称→コードの候補として集める
    techs_by_label = {}
    for u in parsed["units"]:
        for ln in u["lines"]:
            if ln.get("techs_code") and ln["label"]:
                techs_by_label.setdefault(ln["label"], ln["techs_code"])
    techs_used = {}   # 品番 → 資材名（同じ品番が別名称に付いていたら 2 つ目は仮コードにする）

    def _ensure_ext(mm: MaterialMaster, m: dict, is_techs: bool = False):
        # セッションは autoflush=False のため、同じ取込内で作った ext は DB 検索に出ない。キャッシュで二重登録を防ぐ
        ext = ext_cache.get(mm.id)
        if ext is None:
            ext = CostMaterialExt(material_id=mm.id, category=m["category"], price_unit=m["price_unit"],
                                  steel_grade=m.get("steel_grade"), thickness_mm=m.get("thickness_mm"),
                                  stock_size=m.get("stock_size"), basis_note=m.get("basis"), notes=m.get("note"),
                                  code_source="TECHS" if (is_techs or not mm.material_code.startswith("T-")) else "仮")
            db.add(ext); db.flush()
            ext_cache[mm.id] = ext
            stats["ext_created"] += 1
        elif ext.category is None:
            ext.category, ext.price_unit = m["category"], m["price_unit"]

    def ensure_material(key: str, m: dict):
        if key in key_to_mid:
            return key_to_mid[key]
        # 既存の別名から引く
        for al in m["aliases"] + [m["name"]]:
            a = alias_rows.get(imp.norm_label(al))
            if a:
                key_to_mid[key] = a.material_id
                mm = db.query(MaterialMaster).filter(MaterialMaster.id == a.material_id).first()
                _ensure_ext(mm, m)
                return a.material_id
        techs = next((techs_by_label[al] for al in m["aliases"] if al in techs_by_label), None)
        if techs and techs_used.get(techs, m["name"]) != m["name"]:
            techs = None
        if techs:
            techs_used[techs] = m["name"]
        code = techs or imp.temp_code(m["name"])
        mm = code_rows.get(code)
        if mm is None:
            mm = MaterialMaster(material_code=code, material_name=m["name"][:300], unit=m["price_unit"],
                                notes=f"原価表取込（{filename}）")
            db.add(mm); db.flush()
            code_rows[code] = mm
            stats["materials_created"] += 1
        _ensure_ext(mm, m, techs is not None)
        key_to_mid[key] = mm.id
        return mm.id

    # 1) 資材・別名・単価
    existing_prices = {(str(p.material_id), p.effective_date, str(p.supplier_id) if p.supplier_id else None): float(p.price)
                       for p in db.query(CostMaterialPrice).all()}
    conflicts = []   # 同じ資材・同じ時点で既登録と単価が違う（ブック間の不整合。先に取り込んだ値を残す）
    for key, m in parsed["master"]["materials"].items():
        mid = ensure_material(key, m)
        for al in set(m["aliases"] + [m["name"]]):
            al_n = imp.norm_label(al)
            if al_n and al_n not in alias_rows:
                a = CostMaterialAlias(alias=al_n, material_id=mid)
                db.add(a); alias_rows[al_n] = a
                stats["aliases_created"] += 1
        for p in m["prices"]:
            k = (str(mid), p["date"], None)
            if k in existing_prices:
                if abs(existing_prices[k] - p["price"]) > 0.005:
                    conflicts.append({"material": m["name"], "date": p["date"].isoformat(),
                                      "existing": existing_prices[k], "in_file": p["price"]})
                    stats["price_conflicts"] += 1
                continue
            db.add(CostMaterialPrice(material_id=mid, supplier_id=None, effective_date=p["date"], price=p["price"],
                                     price_unit=m["price_unit"], basis_expr=m.get("basis"), source="Excel取込",
                                     notes=filename))
            existing_prices[k] = p["price"]
            stats["prices_created"] += 1
    db.flush()

    # 2) ユニット（型式シート）とオプション部位のユニット
    unit_rows = {u.unit_code: u for u in db.query(UnitMaster).all()}

    def ensure_unit(code: str, name: str, notes: str):
        u = unit_rows.get(code)
        if u is None:
            u = UnitMaster(unit_code=code[:50], unit_name=name[:300], unit_type=COST_UNIT_TYPE, model_no=code[:100], notes=notes)
            db.add(u); db.flush()
            unit_rows[code] = u
            stats["units_created"] += 1
        return u

    for u in parsed["units"]:
        ensure_unit(u["unit_code"], u["unit_name"], f"原価表取込（{filename} / {u['sheet']}）")
        for sec in sorted({ln["section"] or "オプション" for ln in u["lines"] if ln.get("is_option")}):
            ensure_unit(f"{u['unit_code']}/{sec}", f"{u['unit_name']} {sec}（オプション）", f"原価表取込 オプション部位（{u['sheet']}）")
    db.flush()

    # 3) 明細行（同じシートからの取込分を置き換える）
    for u in parsed["units"]:
        base_unit = unit_rows[u["unit_code"]]
        targets = [base_unit.id] + [unit_rows[f"{u['unit_code']}/{s}"].id for s in
                                    {ln["section"] or "オプション" for ln in u["lines"] if ln.get("is_option")}]
        deleted = db.query(CostBomLine).filter(CostBomLine.unit_id.in_(targets),
                                               CostBomLine.source_ref.like(f"{u['sheet']}#%")).delete(synchronize_session=False)
        stats["lines_replaced"] += deleted
        sort = 0
        for ln in u["lines"]:
            if ln["orphan"] and not include_orphans:
                stats["orphans_skipped"] += 1
                continue
            sort += 1
            unit_row = base_unit if not ln.get("is_option") else unit_rows[f"{u['unit_code']}/{ln['section'] or 'オプション'}"]
            mid, sub_id = None, None
            if ln["line_type"] == "subassembly":
                sub = unit_rows.get(ln["sub_unit_code"])
                if sub is None:
                    sub = ensure_unit(ln["sub_unit_code"], ln["sub_unit_code"], "原価表取込（参照先シート）")
                sub_id = sub.id
            else:
                key = ln.get("material_key") or ("PART|" + ln["label"])
                if key not in parsed["master"]["materials"]:
                    cat, unit = imp.classify_material(ln["label"])
                    parsed["master"]["materials"][key] = {"key": key, "name": ln["label"], "category": cat, "price_unit": unit,
                                                          "steel_grade": None, "thickness_mm": None, "stock_size": None,
                                                          "basis": None, "note": "取込時に単価マスタ未登録", "prices": [], "aliases": [ln["label"]]}
                    stats["unresolved_materials"] += 1
                mid = ensure_material(key, parsed["master"]["materials"][key])
                al_n = imp.norm_label(ln["label"])
                if al_n and al_n not in alias_rows:
                    a = CostMaterialAlias(alias=al_n, material_id=mid); db.add(a); alias_rows[al_n] = a
            notes = ln.get("note")
            if ln["orphan"]:
                notes = ((notes + " / ") if notes else "") + "Excel では小計外"
            yb = {"pieces": ln["pieces"]} if ln.get("pieces") else None
            db.add(CostBomLine(unit_id=unit_row.id, section=ln["section"], label=ln["label"], line_type=ln["line_type"],
                               material_id=mid, sub_unit_id=sub_id, qty=ln["qty"] or 0, qty_expr=ln["qty_expr"],
                               yield_basis=yb, markup_factor=ln["markup"], is_option=bool(ln.get("is_option")),
                               source_ref=f"{u['sheet']}#{ln['row']}", sort_order=sort, notes=notes))
            stats["lines_created"] += 1
    db.commit()
    return {"stats": dict(stats), "price_conflicts": conflicts[:200]}


# ------------------------------------------------------------
# Excel 出力（原価表）
# ------------------------------------------------------------
@router.get("/export/{unit_id}.xlsx")
def export_excel(unit_id: str, price_date: Optional[str] = None, compare_date: Optional[str] = None,
                 db: Session = Depends(get_db)):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(500, "openpyxl がインストールされていません")
    unit = db.query(UnitMaster).filter(UnitMaster.id == _uuid(unit_id)).first()
    if not unit:
        raise HTTPException(404)
    d = _d(price_date) or dt.date.today()
    ctx = _load_ctx(db)
    res = _calc(db, ctx, unit, d, {})
    mat = res["material"]
    cmp = None
    if compare_date:
        base = eng.calc_unit(ctx, str(unit.id), _d(compare_date), {})
        cmp = eng.diff_results(base, mat)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = unit.unit_code[:30]
    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="DDE5EE")
    ws["A1"] = unit.unit_code; ws["A1"].font = Font(bold=True, size=14)
    ws["B1"] = unit.unit_name
    ws["A2"] = "単価時点"; ws["B2"] = d.isoformat()
    ws["A3"] = "材料費合計"; ws["B3"] = round(mat["total"]); ws["B3"].number_format = "#,##0"
    ws["C3"] = "鋼材"; ws["D3"] = round(mat["steel_total"]); ws["D3"].number_format = "#,##0"
    ws["E3"] = "購入/外注"; ws["F3"] = round(mat["purchased_total"]); ws["F3"].number_format = "#,##0"
    ws["A4"] = "加工費"; ws["B4"] = round(res["labor_cost"]) if res["labor_cost"] is not None else "（工数未設定）"
    ws["C4"] = "標準工数(h)"; ws["D4"] = res["standard_hours"]; ws["E4"] = "時間単価"; ws["F4"] = res["labor_rate"]
    ws["A5"] = "製造原価"; ws["B5"] = round(res["manufacturing_cost"]); ws["B5"].number_format = "#,##0"
    ws["C5"] = "販売価格"; ws["D5"] = res["standard_price"]; ws["E5"] = "粗利率"
    ws["F5"] = res["gross_margin_rate"]; ws["F5"].number_format = "0.0%"
    if cmp:
        ws["A6"] = f"{compare_date} 比"; ws["B6"] = round(cmp["diff"]); ws["C6"] = cmp["diff_rate"]; ws["C6"].number_format = "+0.0%;-0.0%"

    r = 8
    ws.cell(r, 1, "部位別"); ws.cell(r, 1).font = bold
    r += 1
    for h, c in (("部位", 1), ("鋼材", 2), ("購入/外注", 3), ("小計", 4)):
        ws.cell(r, c, h).font = bold; ws.cell(r, c).fill = head_fill
    for s in mat["sections"]:
        r += 1
        ws.cell(r, 1, s["section"]); ws.cell(r, 2, round(s["steel"])); ws.cell(r, 3, round(s["purchased"])); ws.cell(r, 4, round(s["total"]))
        for c in (2, 3, 4):
            ws.cell(r, c).number_format = "#,##0"
    r += 2
    ws.cell(r, 1, "内訳"); ws.cell(r, 1).font = bold
    r += 1
    headers = ["部位", "名称", "種別", "資材コード", "資材名", "数量", "単位", "単価", "原価", "仕入先", "単価時点", "数量の式", "備考"]
    for i, h in enumerate(headers, 1):
        ws.cell(r, i, h).font = bold; ws.cell(r, i).fill = head_fill
    names = {str(s.id): s.name for s in db.query(Supplier).all()}
    for l in mat["lines"]:
        r += 1
        vals = [l["section"], l["label"], l["line_type"], l.get("material_code"), l.get("material_name"), l["qty"],
                l.get("price_unit"), l.get("unit_price"), round(l["amount"], 2), names.get(str(l.get("supplier_id")), ""),
                str(l.get("price_date") or ""), l.get("qty_expr"), (l.get("warning") or "") + (" " + l["note"] if l.get("note") else "")]
        for i, v in enumerate(vals, 1):
            ws.cell(r, i, v)
        ws.cell(r, 9).number_format = "#,##0"
    for col, w in zip("ABCDEFGHIJKLM", (16, 34, 10, 14, 30, 10, 6, 10, 12, 16, 12, 24, 30)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = ws.cell(r - len(mat["lines"]) + 1, 1)
    if cmp:
        ws2 = wb.create_sheet("差分要因")
        for i, h in enumerate(["部位", "名称", "旧単価", "新単価", "旧数量", "新数量", "旧原価", "新原価", "差額", "単価要因", "数量要因"], 1):
            ws2.cell(1, i, h).font = bold; ws2.cell(1, i).fill = head_fill
        for i, row in enumerate(cmp["rows"], 2):
            for j, k in enumerate(["section", "label", "base_price", "other_price", "base_qty", "other_qty", "base_amount",
                                   "other_amount", "diff", "price_effect", "qty_effect"], 1):
                ws2.cell(i, j, row[k])
    out = io.BytesIO()
    wb.save(out); out.seek(0)
    fname = f"原価表_{unit.unit_code}_{d.isoformat()}.xlsx"
    from urllib.parse import quote
    return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})


# ------------------------------------------------------------
# レポート（製品ごとの時系列 / 全製品サマリ）— JSON でプレビュー、xlsx / pdf で出力
# ------------------------------------------------------------
def _report_dates(db: Session, dates: Optional[str]) -> list:
    """レポートの単価時点。指定が無ければ登録済みの単価時点すべて＋本日"""
    if dates:
        out = sorted({_d(x.strip()) for x in dates.split(",") if x.strip()})
        return [d for d in out if d]
    out = sorted({r[0] for r in db.query(CostMaterialPrice.effective_date).distinct().all()})
    today = dt.date.today()
    if not out or out[-1] < today:
        out.append(today)
    return out


def _series_for_unit(db: Session, ctx: dict, unit: UnitMaster, dates: list) -> dict:
    hours = _f(unit.standard_hours) or _hours_for(db, unit.unit_code)
    std_price = _std_price_for(db, unit)
    points, results = [], []
    for d in dates:
        try:
            r = eng.calc_product(ctx, str(unit.id), d, {}, standard_hours=hours, standard_price=std_price,
                                 settings=_settings_as_of(db, d))
        except eng.CostError as e:
            points.append({"date": d.isoformat(), "error": str(e)})
            results.append(None)
            continue
        m = r["material"]
        points.append({
            "date": d.isoformat(), "material_cost": m["total"], "steel_total": m["steel_total"],
            "purchased_total": m["purchased_total"], "steel_ratio": m["steel_ratio"],
            "labor_cost": r["labor_cost"], "overhead_cost": r["overhead_cost"], "manufacturing_cost": r["manufacturing_cost"],
            "standard_price": r["standard_price"], "gross_margin_rate": r["gross_margin_rate"],
            "required_price": r["required_price"], "unresolved": len(m["warnings"]),
            "sections": {s["section"]: s["total"] for s in m["sections"]},
        })
        results.append(m)
    valid = [p for p in points if "error" not in p]
    first, last = (valid[0], valid[-1]) if valid else (None, None)
    change = None
    if first and last and first["material_cost"]:
        change = last["material_cost"] / first["material_cost"] - 1
    movers = []
    rs = [r for r in results if r]
    if len(rs) >= 2:
        movers = eng.diff_results(rs[0], rs[-1])["rows"][:20]
    section_names = []
    for p in valid:
        for s in p["sections"]:
            if s not in section_names:
                section_names.append(s)
    return {
        "unit": _unit_dict(unit, 0, section_names), "dates": [d.isoformat() for d in dates], "points": points,
        "change_rate": change, "first": first, "last": last, "movers": movers, "section_names": section_names,
        "standard_hours": hours, "standard_price": std_price,
    }


@router.get("/report/timeseries")
def report_timeseries(unit_id: str, dates: Optional[str] = None, db: Session = Depends(get_db)):
    """製品ごとの時系列分析（単価時点ごとの材料費・製造原価・粗利率、部位別推移、上昇要因）"""
    unit = db.query(UnitMaster).filter(UnitMaster.id == _uuid(unit_id)).first()
    if not unit:
        raise HTTPException(404, "ユニットが見つかりません")
    ds = _report_dates(db, dates)
    ctx = _load_ctx(db)
    out = _series_for_unit(db, ctx, unit, ds)
    saved = (db.query(CostCalculation).filter(CostCalculation.unit_id == unit.id)
             .order_by(CostCalculation.price_date).all())
    out["saved"] = [{"price_date": c.price_date.isoformat(), "total": _f(c.total), "manufacturing_cost": _f(c.manufacturing_cost),
                     "label": c.label, "created_at": c.created_at.isoformat() if c.created_at else None} for c in saved]
    out["generated_at"] = dt.datetime.now().isoformat(timespec="minutes")
    return out


@router.get("/report/summary")
def report_summary(dates: Optional[str] = None, include_options: bool = False, db: Session = Depends(get_db)):
    """全製品のサマリ（型式 × 単価時点の材料費、変化率、製造原価、販売価格、粗利率、鋼材比率、未解決）"""
    ds = _report_dates(db, dates)
    ctx = _load_ctx(db)
    ids = [r[0] for r in db.query(CostBomLine.unit_id).distinct().all()]
    units = db.query(UnitMaster).filter(UnitMaster.id.in_(ids)).order_by(UnitMaster.unit_code).all() if ids else []
    rows = []
    for u in units:
        if not include_options and "/" in (u.unit_code or ""):
            continue
        s = _series_for_unit(db, ctx, u, ds)
        last = s["last"] or {}
        unresolved_series = {p["date"]: p.get("unresolved") or 0 for p in s["points"]}
        rows.append({
            "unit_id": str(u.id), "unit_code": u.unit_code, "unit_name": u.unit_name,
            "series": {p["date"]: p.get("material_cost") for p in s["points"]},
            "unresolved_series": unresolved_series,
            "change_rate": s["change_rate"],
            # 端点のどちらかに単価未解決の行があると、その時点の材料費が過小になり変化率が信用できない
            "change_unreliable": bool(s["first"] and s["last"] and (s["first"].get("unresolved") or s["last"].get("unresolved"))),
            "material_cost": last.get("material_cost"), "manufacturing_cost": last.get("manufacturing_cost"),
            "labor_cost": last.get("labor_cost"), "standard_price": last.get("standard_price"),
            "gross_margin_rate": last.get("gross_margin_rate"), "required_price": last.get("required_price"),
            "steel_ratio": last.get("steel_ratio"), "unresolved": last.get("unresolved"),
            "top_mover": (s["movers"][0]["label"] if s["movers"] else None),
            "top_mover_diff": (s["movers"][0]["diff"] if s["movers"] else None),
        })
    totals = {d.isoformat(): sum((r["series"].get(d.isoformat()) or 0) for r in rows) for d in ds}
    return {"dates": [d.isoformat() for d in ds], "rows": rows, "totals": totals,
            "settings": _settings_as_of(db, ds[-1] if ds else dt.date.today()),
            "generated_at": dt.datetime.now().isoformat(timespec="minutes")}


def _html_doc(title: str, body: str, landscape: bool = False, font_px: int = 11) -> str:
    # フォント指定は app/pdf.py が PDF 用に上書きする（日本語 CID フォント）。ここでは指定しない。
    # @page は pdf.py の CSS（縦）より後に評価させるため body 先頭に置く。
    page = "<style>@page{size:A4 landscape;margin:10mm}</style>" if landscape else ""
    return (
        "<html><head><meta charset='utf-8'><title>" + title + "</title><style>"
        f"body{{font-size:{font_px}px;margin:20px}}h1{{font-size:16px;margin:0 0 4px}}h2{{font-size:13px;margin:16px 0 4px}}"
        "table{border-collapse:collapse;width:100%;margin-bottom:8px}th,td{border:1px solid #999;padding:2px 4px;vertical-align:top}"
        "th{background:#e8edf2;text-align:left}td.n,th.n{text-align:right;white-space:nowrap}.muted{color:#666}.up{color:#b3261e}.down{color:#1e7d4e}"
        ".code{white-space:nowrap;font-weight:bold}.w{color:#9a6700}"
        "</style></head><body>" + page + body + "</body></html>"
    )


def _fmt(v, kind="yen"):
    if v is None:
        return "—"
    if kind == "pct":
        return f"{v * 100:+.1f}%"
    if kind == "rate":
        return f"{v * 100:.1f}%"
    return f"{v:,.0f}"


def _short(s, n=24):
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def _warn_mark(n) -> str:
    return f"<span class='w'>※{n}</span>" if n else ""


def _timeseries_html(s: dict) -> str:
    u = s["unit"]
    b = [f"<h1>製品原価 時系列分析　{u['unit_code']}</h1>",
         f"<div class='muted'>{u['unit_name']}　作成 {s.get('generated_at', '')}　"
         f"標準工数 {s['standard_hours'] or '未登録'} h　販売価格 {_fmt(s['standard_price'])} 円</div>"]
    if s["change_rate"] is not None:
        cls = "up" if s["change_rate"] > 0 else "down"
        b.append(f"<p>材料費の変化（{s['first']['date']} → {s['last']['date']}）: <b class='{cls}'>{_fmt(s['change_rate'], 'pct')}</b>"
                 f"（{_fmt(s['first']['material_cost'])} → {_fmt(s['last']['material_cost'])} 円）</p>")
    b.append("<h2>時点別</h2><table><tr><th>単価時点</th><th class='n'>材料費</th><th class='n'>鋼材</th><th class='n'>購入/外注</th>"
             "<th class='n'>鋼材比率</th><th class='n'>加工費</th><th class='n'>製造原価</th><th class='n'>販売価格</th><th class='n'>粗利率</th><th class='n'>未解決</th></tr>")
    for p in s["points"]:
        if "error" in p:
            b.append(f"<tr><td>{p['date']}</td><td colspan='9'>{p['error']}</td></tr>")
            continue
        b.append(f"<tr><td>{p['date']}</td><td class='n'>{_fmt(p['material_cost'])}{_warn_mark(p['unresolved'])}</td><td class='n'>{_fmt(p['steel_total'])}</td>"
                 f"<td class='n'>{_fmt(p['purchased_total'])}</td><td class='n'>{_fmt(p['steel_ratio'], 'rate')}</td><td class='n'>{_fmt(p['labor_cost'])}</td>"
                 f"<td class='n'>{_fmt(p['manufacturing_cost'])}</td><td class='n'>{_fmt(p['standard_price'])}</td>"
                 f"<td class='n'>{_fmt(p['gross_margin_rate'], 'rate')}</td><td class='n'>{p['unresolved'] or ''}</td></tr>")
    b.append("</table>")
    if any(p.get("unresolved") for p in s["points"] if "error" not in p):
        b.append("<p class='muted'>※n: その時点で単価が解決できない明細が n 行あり、材料費はその分だけ過小。単価履歴か別名を登録すると解消する。</p>")
    if s["section_names"]:
        b.append("<h2>部位別の推移</h2><table><tr><th>部位</th>" + "".join(f"<th class='n'>{d}</th>" for d in s["dates"]) + "<th class='n'>変化</th></tr>")
        for sec in s["section_names"]:
            vals = [p.get("sections", {}).get(sec) for p in s["points"]]
            v = [x for x in vals if x is not None]
            ch = (v[-1] / v[0] - 1) if len(v) >= 2 and v[0] else None
            b.append(f"<tr><td>{sec}</td>" + "".join(f"<td class='n'>{_fmt(x)}</td>" for x in vals) + f"<td class='n'>{_fmt(ch, 'pct')}</td></tr>")
        b.append("</table>")
    if s["movers"]:
        b.append("<h2>上昇・下落の主要因（明細）</h2><table><tr><th>部位</th><th>名称</th><th class='n'>旧単価</th><th class='n'>新単価</th>"
                 "<th class='n'>数量</th><th class='n'>差額</th><th class='n'>単価要因</th><th class='n'>数量要因</th></tr>")
        for r in s["movers"]:
            cls = "up" if r["diff"] > 0 else "down"
            b.append(f"<tr><td>{r['section']}</td><td>{_short(r['label'], 40)}</td><td class='n'>{r['base_price']:,.2f}</td><td class='n'>{r['other_price']:,.2f}</td>"
                     f"<td class='n'>{r['other_qty']:,.3f}</td><td class='n {cls}'>{_fmt(r['diff'])}</td><td class='n'>{_fmt(r['price_effect'])}</td><td class='n'>{_fmt(r['qty_effect'])}</td></tr>")
        b.append("</table>")
    if s.get("saved"):
        b.append("<h2>保存済みの計算</h2><table><tr><th>単価時点</th><th class='n'>材料費</th><th class='n'>製造原価</th><th>メモ</th><th>保存日</th></tr>")
        for c in s["saved"]:
            b.append(f"<tr><td>{c['price_date']}</td><td class='n'>{_fmt(c['total'])}</td><td class='n'>{_fmt(c['manufacturing_cost'])}</td><td>{c['label'] or ''}</td><td>{(c['created_at'] or '')[:10]}</td></tr>")
        b.append("</table>")
    return _html_doc(f"時系列分析 {u['unit_code']}", "".join(b))


def _summary_html(s: dict) -> str:
    st = s["settings"]
    b = [f"<h1>製品原価 サマリ（全製品）</h1><div class='muted'>作成 {s['generated_at']}　時間単価 {_fmt(st.get('labor_rate_per_hour'))} 円/h　"
         f"経費率 {st.get('overhead_rate') if st.get('overhead_rate') is not None else '未設定'}　目標粗利率 {st.get('target_margin_rate') if st.get('target_margin_rate') is not None else '未設定'}</div>",
         "<table><tr><th style='width:22mm'>型式</th>" + "".join(f"<th class='n'>{d}</th>" for d in s["dates"]) +
         "<th class='n'>変化</th><th class='n'>製造原価</th><th class='n'>販売価格</th><th class='n'>粗利率</th><th class='n'>必要売価</th><th class='n'>鋼材比率</th><th style='width:38mm'>主要因（差額）</th><th class='n'>未解決</th></tr>"]
    any_warn = False
    for r in s["rows"]:
        ch = r["change_rate"]
        cls = "muted" if r.get("change_unreliable") else ("up" if (ch or 0) > 0 else "down")
        cells = []
        for d in s["dates"]:
            n = (r.get("unresolved_series") or {}).get(d)
            any_warn = any_warn or bool(n)
            cells.append(f"<td class='n'>{_fmt(r['series'].get(d))}{_warn_mark(n)}</td>")
        b.append(f"<tr><td class='code'>{r['unit_code']}</td>" + "".join(cells) +
                 f"<td class='n {cls}'>{_fmt(ch, 'pct')}{'※' if r.get('change_unreliable') else ''}</td><td class='n'>{_fmt(r['manufacturing_cost'])}</td><td class='n'>{_fmt(r['standard_price'])}</td>"
                 f"<td class='n'>{_fmt(r['gross_margin_rate'], 'rate')}</td><td class='n'>{_fmt(r['required_price'])}</td><td class='n'>{_fmt(r['steel_ratio'], 'rate')}</td>"
                 f"<td>{_short(r['top_mover'], 22)}{('（' + _fmt(r['top_mover_diff']) + '）') if r['top_mover_diff'] is not None else ''}</td><td class='n'>{r['unresolved'] or ''}</td></tr>")
    b.append("<tr><th>合計</th>" + "".join(f"<th class='n'>{_fmt(s['totals'].get(d))}</th>" for d in s["dates"]) + "<th colspan='8'></th></tr></table>")
    if any_warn:
        b.append("<p class='muted'>※n: その時点で単価が解決できない明細が n 行あり、材料費はその分だけ過小（変化率も参考値）。単価履歴か別名を登録すると解消する。</p>")
    return _html_doc("製品原価サマリ", "".join(b), landscape=True, font_px=9)


def _xlsx_response(wb, fname: str):
    out = io.BytesIO()
    wb.save(out); out.seek(0)
    from urllib.parse import quote
    return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})


def _pdf_or_html_response(html: str, fname: str):
    from app.pdf import html_to_pdf
    from urllib.parse import quote
    pdf = html_to_pdf(html)
    if pdf:
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"})
    # PDF 変換ができない環境ではブラウザ印刷用の HTML を返す
    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html; charset=utf-8")


@router.get("/report/timeseries.{fmt}")
def report_timeseries_file(fmt: str, unit_id: str, dates: Optional[str] = None, db: Session = Depends(get_db)):
    s = report_timeseries(unit_id, dates, db)
    code = s["unit"]["unit_code"]
    if fmt == "pdf" or fmt == "html":
        html = _timeseries_html(s)
        if fmt == "html":
            return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html; charset=utf-8")
        return _pdf_or_html_response(html, f"時系列分析_{code}.pdf")
    if fmt != "xlsx":
        raise HTTPException(400, "fmt は xlsx / pdf / html")
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "時点別"
    bold, fill = Font(bold=True), PatternFill("solid", fgColor="DDE5EE")
    ws["A1"] = f"製品原価 時系列分析 {code}"; ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = s["unit"]["unit_name"]; ws["C2"] = "標準工数(h)"; ws["D2"] = s["standard_hours"]; ws["E2"] = "販売価格"; ws["F2"] = s["standard_price"]
    heads = ["単価時点", "材料費", "鋼材", "購入/外注", "鋼材比率", "加工費", "経費", "製造原価", "販売価格", "粗利率", "必要売価", "未解決"]
    for i, h in enumerate(heads, 1):
        ws.cell(4, i, h).font = bold; ws.cell(4, i).fill = fill
    r = 4
    for p in s["points"]:
        r += 1
        if "error" in p:
            ws.cell(r, 1, p["date"]); ws.cell(r, 2, p["error"]); continue
        for i, k in enumerate(["date", "material_cost", "steel_total", "purchased_total", "steel_ratio", "labor_cost", "overhead_cost",
                               "manufacturing_cost", "standard_price", "gross_margin_rate", "required_price", "unresolved"], 1):
            ws.cell(r, i, p.get(k))
            if k in ("steel_ratio", "gross_margin_rate"):
                ws.cell(r, i).number_format = "0.0%"
            elif k not in ("date", "unresolved"):
                ws.cell(r, i).number_format = "#,##0"
    r += 2
    ws.cell(r, 1, "部位別の推移").font = bold
    r += 1
    ws.cell(r, 1, "部位").font = bold
    for j, d in enumerate(s["dates"], 2):
        ws.cell(r, j, d).font = bold; ws.cell(r, j).fill = fill
    ws.cell(r, len(s["dates"]) + 2, "変化").font = bold
    for sec in s["section_names"]:
        r += 1
        ws.cell(r, 1, sec)
        vals = [p.get("sections", {}).get(sec) for p in s["points"]]
        for j, v in enumerate(vals, 2):
            ws.cell(r, j, v); ws.cell(r, j).number_format = "#,##0"
        v = [x for x in vals if x is not None]
        if len(v) >= 2 and v[0]:
            c = ws.cell(r, len(s["dates"]) + 2, v[-1] / v[0] - 1); c.number_format = "+0.0%;-0.0%"
    for col, w in zip("ABCDEFGHIJKL", (22, 14, 14, 14, 10, 12, 12, 14, 14, 10, 14, 8)):
        ws.column_dimensions[col].width = w
    ws2 = wb.create_sheet("要因")
    for i, h in enumerate(["部位", "名称", "旧単価", "新単価", "旧数量", "新数量", "旧原価", "新原価", "差額", "単価要因", "数量要因"], 1):
        ws2.cell(1, i, h).font = bold; ws2.cell(1, i).fill = fill
    for i, row in enumerate(s["movers"], 2):
        for j, k in enumerate(["section", "label", "base_price", "other_price", "base_qty", "other_qty", "base_amount", "other_amount", "diff", "price_effect", "qty_effect"], 1):
            ws2.cell(i, j, row[k])
    ws2.column_dimensions["A"].width = 18; ws2.column_dimensions["B"].width = 36
    return _xlsx_response(wb, f"時系列分析_{code}.xlsx")


@router.get("/report/summary.{fmt}")
def report_summary_file(fmt: str, dates: Optional[str] = None, include_options: bool = False, db: Session = Depends(get_db)):
    s = report_summary(dates, include_options, db)
    if fmt in ("pdf", "html"):
        html = _summary_html(s)
        if fmt == "html":
            return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html; charset=utf-8")
        return _pdf_or_html_response(html, "製品原価サマリ.pdf")
    if fmt != "xlsx":
        raise HTTPException(400, "fmt は xlsx / pdf / html")
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "サマリ"
    bold, fill = Font(bold=True), PatternFill("solid", fgColor="DDE5EE")
    ws["A1"] = "製品原価 サマリ（全製品）"; ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = f"作成 {s['generated_at']}"
    heads = ["型式", "名称"] + s["dates"] + ["変化", "加工費", "製造原価", "販売価格", "粗利率", "必要売価", "鋼材比率", "主要因", "主要因の差額", "未解決"]
    for i, h in enumerate(heads, 1):
        ws.cell(4, i, h).font = bold; ws.cell(4, i).fill = fill
    r = 4
    nd = len(s["dates"])
    for row in s["rows"]:
        r += 1
        ws.cell(r, 1, row["unit_code"]); ws.cell(r, 2, row["unit_name"])
        for j, d in enumerate(s["dates"], 3):
            ws.cell(r, j, row["series"].get(d)); ws.cell(r, j).number_format = "#,##0"
            n = (row.get("unresolved_series") or {}).get(d)
            if n:
                from openpyxl.comments import Comment
                ws.cell(r, j).comment = Comment(f"単価未解決 {n} 行（材料費は過小）", "原価検証")
        vals = [row["change_rate"], row["labor_cost"], row["manufacturing_cost"], row["standard_price"], row["gross_margin_rate"],
                row["required_price"], row["steel_ratio"], row["top_mover"], row["top_mover_diff"], row["unresolved"]]
        fmts = ["+0.0%;-0.0%", "#,##0", "#,##0", "#,##0", "0.0%", "#,##0", "0.0%", None, "#,##0", None]
        for j, (v, f) in enumerate(zip(vals, fmts), 3 + nd):
            ws.cell(r, j, v)
            if f:
                ws.cell(r, j).number_format = f
    r += 1
    ws.cell(r, 1, "合計").font = bold
    for j, d in enumerate(s["dates"], 3):
        ws.cell(r, j, s["totals"].get(d)).font = bold; ws.cell(r, j).number_format = "#,##0"
    ws.column_dimensions["A"].width = 18; ws.column_dimensions["B"].width = 26
    for j in range(3, 3 + nd + 10):
        ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = 13
    ws.freeze_panes = "C5"
    return _xlsx_response(wb, "製品原価サマリ.xlsx")


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return {
        "materials": db.query(CostMaterialExt).count(),
        "prices": db.query(CostMaterialPrice).count(),
        "units": db.query(CostBomLine.unit_id).distinct().count(),
        "lines": db.query(CostBomLine).count(),
        "price_dates": price_dates(db),
        "settings": _settings_as_of(db, dt.date.today()),
    }
