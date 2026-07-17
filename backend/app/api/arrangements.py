# -*- coding: utf-8 -*-
"""手配書 API（クレーン手配書・送り状・宿泊予約票）子IDに紐づく"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, Any
from pydantic import BaseModel
import io
from app.db.models import (
    pk_or_code,
    get_db, ProjectOrder,
    CraneArrangement, ShippingArrangement, HotelArrangement, ArrangementVendor,
)

router = APIRouter()

# =============================================
# 手配業者マスタ
# =============================================

def _vendor_dict(v: ArrangementVendor):
    return {
        "id": str(v.id), "category": v.category, "name": v.name, "branch": v.branch,
        "contact_person": v.contact_person, "phone": v.phone, "fax": v.fax,
        "postal_code": v.postal_code, "address": v.address, "notes": v.notes,
    }

@router.get("/vendors")
def list_vendors(category: Optional[str] = None, search: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ArrangementVendor).filter(ArrangementVendor.is_active == True)
    if category:
        q = q.filter(ArrangementVendor.category == category)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(ArrangementVendor.name.ilike(like), ArrangementVendor.branch.ilike(like),
                         ArrangementVendor.contact_person.ilike(like)))
    return [_vendor_dict(v) for v in q.order_by(ArrangementVendor.name).limit(50).all()]

@router.post("/vendors")
def create_vendor(data: dict, db: Session = Depends(get_db)):
    v = ArrangementVendor(**{k: data.get(k) for k in
        ["category", "name", "branch", "contact_person", "phone", "fax", "postal_code", "address", "notes", "source_tag"] if k in data})
    db.add(v); db.commit(); db.refresh(v)
    return _vendor_dict(v)

@router.put("/vendors/{vendor_id}")
def update_vendor(vendor_id: str, data: dict, db: Session = Depends(get_db)):
    v = db.query(ArrangementVendor).filter(ArrangementVendor.id == vendor_id).first()
    if not v: raise HTTPException(404)
    for k in ["category", "name", "branch", "contact_person", "phone", "fax", "postal_code", "address", "notes"]:
        if k in data: setattr(v, k, data[k])
    db.commit(); db.refresh(v)
    return _vendor_dict(v)

@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: str, db: Session = Depends(get_db)):
    v = db.query(ArrangementVendor).filter(ArrangementVendor.id == vendor_id).first()
    if not v: raise HTTPException(404)
    v.is_active = False; db.commit()
    return {"ok": True}

@router.post("/vendors/bulk")
def bulk_vendors(data: dict, db: Session = Depends(get_db)):
    """業者を一括登録。既存（同名＋同営業所）はスキップ。"""
    tag = data.get("tag")
    rows = data.get("vendors", [])
    existing = {(r[0], r[1] or "") for r in db.query(ArrangementVendor.name, ArrangementVendor.branch).all()}
    created = 0
    for r in rows:
        name = (r.get("name") or "").strip()
        branch = (r.get("branch") or "").strip()
        if not name or (name, branch) in existing:
            continue
        existing.add((name, branch))
        db.add(ArrangementVendor(
            category=r.get("category"), name=name, branch=branch,
            contact_person=r.get("contact"), phone=r.get("tel"), fax=r.get("fax"),
            source_tag=tag,
        ))
        created += 1
    db.commit()
    return {"ok": True, "created": created, "skipped": len(rows) - created}

@router.get("/vendors/count")
def vendor_count(db: Session = Depends(get_db)):
    return {"count": db.query(ArrangementVendor).filter(ArrangementVendor.is_active == True).count()}

COMPANY_FOOTER = (
    '<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">'
    '<div style="font-size:14px;font-weight:bold;margin-right:15px">井上電設株式会社</div>'
    '<div style="font-size:10px">〒460-0022 名古屋市中区金山四丁目3番17号 '
    'TEL(052)322-5271 FAX(052)332-5273</div>'
    '</div>'
)

PRINT_BAR = (
    '<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">'
    '<button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;'
    'padding:6px 16px;border-radius:5px;cursor:pointer">印刷 / PDF保存</button></div>'
)

BASE_STYLE = (
    "body{font-family:'Hiragino Sans','Yu Gothic',sans-serif;font-size:11px;margin:15mm}"
    "@media print{.no-print{display:none}}"
    "table{border-collapse:collapse;width:100%}"
    "td,th{border:1px solid #999;padding:4px 6px}"
    "th{background:#f0f0f0}"
)

def esc(v):
    if v is None:
        return ''
    return str(v).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def find_order(order_id, db):
    po = db.query(ProjectOrder).filter(
        pk_or_code(ProjectOrder.id, ProjectOrder.child_no, order_id)
    ).first()
    if not po:
        raise HTTPException(404, "子IDが見つかりません")
    return po


# =============================================
# Pydanticスキーマ
# =============================================
class CraneData(BaseModel):
    site_name: Optional[str] = None
    site_address: Optional[str] = None
    site_tel: Optional[str] = None
    site_contact: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_branch: Optional[str] = None
    vendor_contact: Optional[str] = None
    vendor_tel: Optional[str] = None
    vendor_fax: Optional[str] = None
    order_no: Optional[str] = None
    items_json: Optional[List[Any]] = None
    notes: Optional[str] = None

class ShippingData(BaseModel):
    dest_name: Optional[str] = None
    dest_address: Optional[str] = None
    dest_tel: Optional[str] = None
    carrier_name: Optional[str] = None
    carrier_contact: Optional[str] = None
    carrier_tel: Optional[str] = None
    order_no: Optional[str] = None
    items_json: Optional[List[Any]] = None
    notes: Optional[str] = None

class HotelData(BaseModel):
    site_name: Optional[str] = None
    site_address: Optional[str] = None
    items_json: Optional[List[Any]] = None
    notes: Optional[str] = None


def crane_to_dict(c):
    return {
        "id": str(c.id), "child_no": c.child_no,
        "site_name": c.site_name, "site_address": c.site_address,
        "site_tel": c.site_tel, "site_contact": c.site_contact,
        "vendor_name": c.vendor_name, "vendor_branch": c.vendor_branch,
        "vendor_contact": c.vendor_contact, "vendor_tel": c.vendor_tel,
        "vendor_fax": c.vendor_fax, "order_no": c.order_no,
        "items_json": c.items_json or [], "notes": c.notes,
    }

def shipping_to_dict(s):
    return {
        "id": str(s.id), "child_no": s.child_no,
        "dest_name": s.dest_name, "dest_address": s.dest_address,
        "dest_tel": s.dest_tel, "carrier_name": s.carrier_name,
        "carrier_contact": s.carrier_contact, "carrier_tel": s.carrier_tel,
        "order_no": s.order_no, "items_json": s.items_json or [], "notes": s.notes,
    }

def hotel_to_dict(h):
    return {
        "id": str(h.id), "child_no": h.child_no,
        "site_name": h.site_name, "site_address": h.site_address,
        "items_json": h.items_json or [], "notes": h.notes,
    }


# =============================================
# クレーン手配書
# =============================================
@router.get("/crane/{order_id}")
def get_crane(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    c = db.query(CraneArrangement).filter(CraneArrangement.project_order_id == po.id).first()
    if not c:
        # 初期データ（子IDの情報を引き継ぎ）
        return {
            "id": None, "child_no": po.child_no,
            "site_name": po.customer_name or '', "site_address": '',
            "site_tel": '', "site_contact": '',
            "vendor_name": '', "vendor_branch": '', "vendor_contact": '',
            "vendor_tel": '', "vendor_fax": '', "order_no": po.child_no or '',
            "items_json": [], "notes": '',
        }
    return crane_to_dict(c)

@router.put("/crane/{order_id}")
def save_crane(order_id: str, data: CraneData, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    c = db.query(CraneArrangement).filter(CraneArrangement.project_order_id == po.id).first()
    if not c:
        c = CraneArrangement(project_order_id=po.id, child_no=po.child_no)
        db.add(c)
    for k, v in data.dict(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return crane_to_dict(c)

@router.get("/crane/{order_id}/pdf")
def crane_pdf(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    c = db.query(CraneArrangement).filter(CraneArrangement.project_order_id == po.id).first()
    d = crane_to_dict(c) if c else {"child_no": po.child_no, "site_name": po.customer_name, "items_json": []}

    rows = ''
    for it in (d.get("items_json") or []):
        rows += (
            '<table style="margin-bottom:8px">'
            '<tr><td style="background:#f0f0f0;width:70px">機械名</td>'
            '<td style="min-width:150px">' + esc(it.get('machine')) + '</td>'
            '<td style="background:#f0f0f0;width:70px">重量/仕様</td>'
            '<td>' + esc(it.get('spec')) + '</td></tr>'
            '<tr><td style="background:#f0f0f0">使用開始</td><td>' + esc(it.get('start')) + '</td>'
            '<td style="background:#f0f0f0">使用終了</td><td>' + esc(it.get('end')) + '</td></tr>'
            '<tr><td style="background:#f0f0f0">納品方法</td><td>' + esc(it.get('delivery')) + '</td>'
            '<td style="background:#f0f0f0">返却方法</td><td>' + esc(it.get('return_method')) + '</td></tr>'
            '<tr><td style="background:#f0f0f0">備考</td><td colspan="3">' + esc(it.get('note')) + '</td></tr>'
            '</table>'
        )
    if not rows:
        rows = '<p style="color:#999">明細がありません</p>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>クレーン・作業車等依頼書</title><style>' + BASE_STYLE + '</style></head><body>'
        + PRINT_BAR
        + '<div style="font-size:16px;font-weight:bold;letter-spacing:2px">クレーン・作業車等 依頼書</div>'
        + '<table style="margin:10px 0">'
        + '<tr><td style="background:#f0f0f0;width:70px">現場名</td><td>' + esc(d.get('site_name'))
        + '</td><td style="background:#f0f0f0;width:50px">注番</td>'
        + '<td style="color:red;font-weight:bold">' + esc(d.get('order_no')) + '</td></tr>'
        + '<tr><td style="background:#f0f0f0">住所</td><td colspan="3">' + esc(d.get('site_address')) + '</td></tr>'
        + '<tr><td style="background:#f0f0f0">TEL</td><td>' + esc(d.get('site_tel'))
        + '</td><td style="background:#f0f0f0">現場担当</td><td>' + esc(d.get('site_contact')) + '</td></tr>'
        + '</table>'
        + '<table style="margin-bottom:10px">'
        + '<tr><td style="background:#f0f0f0;width:70px">依頼業者</td><td>' + esc(d.get('vendor_name'))
        + '</td><td style="background:#f0f0f0;width:50px">営業所</td><td>' + esc(d.get('vendor_branch')) + '</td></tr>'
        + '<tr><td style="background:#f0f0f0">ご担当</td><td>' + esc(d.get('vendor_contact'))
        + '</td><td style="background:#f0f0f0">TEL/FAX</td><td>' + esc(d.get('vendor_tel')) + ' / ' + esc(d.get('vendor_fax')) + '</td></tr>'
        + '</table>'
        + '<p style="font-size:10px">下記、手配お願い致します。※請求書には右上の注番を記入してください。</p>'
        + rows + COMPANY_FOOTER + '</body></html>'
    )
    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html")


# =============================================
# 送り状
# =============================================
@router.get("/shipping/{order_id}")
def get_shipping(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    s = db.query(ShippingArrangement).filter(ShippingArrangement.project_order_id == po.id).first()
    if not s:
        return {
            "id": None, "child_no": po.child_no,
            "dest_name": po.customer_name or '', "dest_address": '', "dest_tel": '',
            "carrier_name": '', "carrier_contact": '', "carrier_tel": '',
            "order_no": po.child_no or '', "items_json": [], "notes": '',
        }
    return shipping_to_dict(s)

@router.put("/shipping/{order_id}")
def save_shipping(order_id: str, data: ShippingData, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    s = db.query(ShippingArrangement).filter(ShippingArrangement.project_order_id == po.id).first()
    if not s:
        s = ShippingArrangement(project_order_id=po.id, child_no=po.child_no)
        db.add(s)
    for k, v in data.dict(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return shipping_to_dict(s)

@router.get("/shipping/{order_id}/pdf")
def shipping_pdf(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    s = db.query(ShippingArrangement).filter(ShippingArrangement.project_order_id == po.id).first()
    d = shipping_to_dict(s) if s else {"child_no": po.child_no, "dest_name": po.customer_name, "items_json": []}

    rows = ''
    for it in (d.get("items_json") or []):
        rows += (
            '<table style="margin-bottom:8px">'
            '<tr><td style="background:#f0f0f0;width:70px">車種</td>'
            '<td style="background:#fff3cd;min-width:120px">' + esc(it.get('truck')) + '</td>'
            '<td style="background:#f0f0f0;width:50px">積込日</td><td>' + esc(it.get('load_date')) + '</td>'
            '<td style="background:#f0f0f0;width:50px">到着日</td><td>' + esc(it.get('arrive_date')) + '</td></tr>'
            '<tr><td style="background:#f0f0f0">積込場所</td><td colspan="5">' + esc(it.get('load_place')) + '</td></tr>'
            '<tr><td style="background:#f0f0f0">積込内容</td><td colspan="5">' + esc(it.get('content')) + '</td></tr>'
            '<tr><td style="background:#f0f0f0">備考</td><td colspan="5">' + esc(it.get('note')) + '</td></tr>'
            '</table>'
        )
    if not rows:
        rows = '<p style="color:#999">明細がありません</p>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>送り状</title><style>' + BASE_STYLE + '</style></head><body>'
        + PRINT_BAR
        + '<h2 style="font-size:18px;font-weight:bold">送 り 状</h2>'
        + '<table style="margin-bottom:10px">'
        + '<tr><td style="background:#ff4444;color:#fff;font-weight:bold;width:70px">送り先</td>'
        + '<td style="font-weight:bold">' + esc(d.get('dest_name')) + '</td>'
        + '<td style="background:#f0f0f0;width:50px">注番</td><td>' + esc(d.get('order_no')) + '</td></tr>'
        + '<tr><td style="background:#f0f0f0">住所</td><td colspan="3">' + esc(d.get('dest_address')) + '</td></tr>'
        + '<tr><td style="background:#f0f0f0">TEL</td><td colspan="3">' + esc(d.get('dest_tel')) + '</td></tr>'
        + '</table>'
        + '<table style="margin-bottom:10px">'
        + '<tr><td style="background:#f0f0f0;width:70px">運送業者</td><td>' + esc(d.get('carrier_name'))
        + '</td><td style="background:#f0f0f0;width:50px">担当</td><td>' + esc(d.get('carrier_contact'))
        + '</td><td style="background:#f0f0f0;width:40px">TEL</td><td>' + esc(d.get('carrier_tel')) + '</td></tr>'
        + '</table>'
        + rows + COMPANY_FOOTER + '</body></html>'
    )
    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html")


# =============================================
# 宿泊予約票
# =============================================
@router.get("/hotel/{order_id}")
def get_hotel(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    h = db.query(HotelArrangement).filter(HotelArrangement.project_order_id == po.id).first()
    if not h:
        return {
            "id": None, "child_no": po.child_no,
            "site_name": po.customer_name or '', "site_address": '',
            "items_json": [], "notes": '',
        }
    return hotel_to_dict(h)

@router.put("/hotel/{order_id}")
def save_hotel(order_id: str, data: HotelData, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    h = db.query(HotelArrangement).filter(HotelArrangement.project_order_id == po.id).first()
    if not h:
        h = HotelArrangement(project_order_id=po.id, child_no=po.child_no)
        db.add(h)
    for k, v in data.dict(exclude_unset=True).items():
        setattr(h, k, v)
    db.commit(); db.refresh(h)
    return hotel_to_dict(h)

@router.get("/hotel/{order_id}/pdf")
def hotel_pdf(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    h = db.query(HotelArrangement).filter(HotelArrangement.project_order_id == po.id).first()
    d = hotel_to_dict(h) if h else {"child_no": po.child_no, "site_name": po.customer_name, "items_json": []}

    rows = ''
    for it in (d.get("items_json") or []):
        rows += (
            '<tr><td>' + esc(it.get('hotel')) + '</td>'
            '<td>' + esc(it.get('tel')) + '</td>'
            '<td>' + esc(it.get('checkin')) + '</td>'
            '<td>' + esc(it.get('checkout')) + '</td>'
            '<td style="text-align:center">' + esc(it.get('nights')) + '</td>'
            '<td style="text-align:center">' + esc(it.get('persons')) + '</td>'
            '<td style="text-align:right">' + esc(it.get('price')) + '</td>'
            '<td>' + esc(it.get('guests')) + '</td>'
            '<td>' + esc(it.get('note')) + '</td></tr>'
        )
    if not rows:
        rows = '<tr><td colspan="9" style="color:#999;text-align:center">明細がありません</td></tr>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>宿泊予約票</title><style>' + BASE_STYLE + '</style></head><body>'
        + PRINT_BAR
        + '<h2 style="font-size:16px;font-weight:bold;margin-bottom:4px">宿泊予約票</h2>'
        + '<p style="font-size:9px;color:#666;margin-bottom:10px">'
        + '※基本は朝食なしで！変更・キャンセルは必ず宿へ連絡！予約したら旅費の領収書を忘れずに！</p>'
        + '<table style="margin-bottom:8px"><tr>'
        + '<td style="background:#f0f0f0;width:70px">現場</td><td>' + esc(d.get('site_name')) + '</td>'
        + '<td style="background:#f0f0f0;width:70px">受注番号</td><td>' + esc(d.get('child_no')) + '</td></tr>'
        + '<tr><td style="background:#f0f0f0">住所</td><td colspan="3">' + esc(d.get('site_address')) + '</td></tr></table>'
        + '<table><thead><tr>'
        + '<th>ホテル名</th><th style="width:90px">TEL</th><th style="width:60px">IN</th>'
        + '<th style="width:60px">OUT</th><th style="width:30px">泊</th><th style="width:30px">人</th>'
        + '<th style="width:60px">値段/泊</th><th>宿泊者</th><th>備考</th></tr></thead>'
        + '<tbody>' + rows + '</tbody></table>'
        + COMPANY_FOOTER + '</body></html>'
    )
    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html")


# =============================================
# 手配書テーブル作成（初回のみ実行）
# =============================================
@router.get("/setup-tables")
def setup_arrangement_tables(db: Session = Depends(get_db)):
    from app.db.models import Base, engine
    Base.metadata.create_all(engine)
    return {"message": "手配書テーブル作成完了"}
