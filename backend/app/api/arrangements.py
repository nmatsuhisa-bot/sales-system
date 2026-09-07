# -*- coding: utf-8 -*-
"""手配書 API（クレーン依頼書・トラック送り状・排風機注文確認書/ファン作業指示書・宿泊予約票）

子IDに紐づく。案件（ProjectOrder）と見積（QuotationHeader）から自動補完し、
不足分は画面で加筆・修正してからPDF出力する。
帳票の様式は井上電設様の原紙（ｸﾚｰﾝ・作業車等手配一覧・依頼書.xlsx /
ﾄﾗｯｸ手配一覧・送り状.xlsx / 排風機2011年～.xlsx）に準拠。
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, Any
from pydantic import BaseModel, field_validator
from datetime import date
import io
import re
from app.db.models import (
    pk_or_code,
    get_db, ProjectOrder,
    CraneArrangement, ShippingArrangement, HotelArrangement, ArrangementVendor,
    FanArrangement,
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


WD = "月火水木金土日"


def jp_date(d):
    """2026-09-25 → 「9月25日(金)」。Noneや空は空文字。"""
    if not d:
        return ''
    try:
        return "%d月%d日(%s)" % (d.month, d.day, WD[d.weekday()])
    except Exception:
        return str(d)


def form_response(html: str, filename: str, as_pdf: bool):
    """?format=pdf ならPDFの実体を、既定はブラウザ印刷用のHTMLを返す。

    PDFは見積書と同じ xhtml2pdf + CIDフォントの経路を使う。
    日本語ファイル名は latin-1 に載らないため RFC5987 で渡す。
    """
    from urllib.parse import quote
    if as_pdf:
        from app.pdf import html_to_pdf
        blob = html_to_pdf(html)
        if blob:
            return StreamingResponse(
                io.BytesIO(blob), media_type="application/pdf",
                headers={"Content-Disposition":
                         "inline; filename*=UTF-8''%s.pdf" % quote(filename)})
    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition":
                 "inline; filename*=UTF-8''%s.html" % quote(filename)})


def latest_quotation(po, db):
    """子IDに紐づく見積のうち最新のもの。自動補完の情報源。"""
    from app.db.models import QuotationHeader
    return (db.query(QuotationHeader)
              .filter(QuotationHeader.project_order_id == po.id)
              .order_by(QuotationHeader.created_at.desc())
              .first())


def _pick(*vals):
    """最初に値のあるものを返す（自動補完の優先順位づけ用）"""
    for v in vals:
        if v not in (None, ''):
            return v
    return ''


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
# Pydanticスキーマ
# =============================================
class _FormBase(BaseModel):
    """画面から送られる帳票データの共通の親。

    日付欄を空にすると "" が送られてくるが、date へは変換できず 422 になる。
    保存できないと加筆の途中で詰まるため、空文字は未入力(None)として扱う。
    """

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return None if v == "" else v


class CraneData(_FormBase):
    site_name: Optional[str] = None
    site_address: Optional[str] = None
    site_tel: Optional[str] = None
    site_dept: Optional[str] = None
    site_contact: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_branch: Optional[str] = None
    vendor_contact: Optional[str] = None
    vendor_tel: Optional[str] = None
    vendor_fax: Optional[str] = None
    order_no: Optional[str] = None
    issue_date: Optional[date] = None
    staff_name: Optional[str] = None
    creator_name: Optional[str] = None
    items_json: Optional[List[Any]] = None
    notes: Optional[str] = None


class ShippingData(_FormBase):
    dest_name: Optional[str] = None
    dest_address: Optional[str] = None
    dest_tel: Optional[str] = None
    dest_dept: Optional[str] = None
    dest_contact: Optional[str] = None
    carrier_name: Optional[str] = None
    carrier_contact: Optional[str] = None
    carrier_tel: Optional[str] = None
    carrier_fax: Optional[str] = None
    order_no: Optional[str] = None
    issue_date: Optional[date] = None
    staff_name: Optional[str] = None
    creator_name: Optional[str] = None
    items_json: Optional[List[Any]] = None
    notes: Optional[str] = None


class FanData(_FormBase):
    form_type: Optional[str] = None
    order_no: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_contact: Optional[str] = None
    user_name: Optional[str] = None
    user_plant: Optional[str] = None
    user_address: Optional[str] = None
    user_tel: Optional[str] = None
    user_contact: Optional[str] = None
    ship_to_name: Optional[str] = None
    ship_to_plant: Optional[str] = None
    ship_to_address: Optional[str] = None
    ship_to_tel: Optional[str] = None
    ship_to_contact: Optional[str] = None
    ship_date: Optional[date] = None
    transport_method: Optional[str] = None
    product_name: Optional[str] = None
    model: Optional[str] = None
    serial_no: Optional[str] = None
    drive_type: Optional[str] = None
    spec_json: Optional[dict] = None
    instruction_json: Optional[dict] = None
    sales_person_name: Optional[str] = None
    creator_name: Optional[str] = None
    notes: Optional[str] = None


class HotelData(_FormBase):
    site_name: Optional[str] = None
    site_address: Optional[str] = None
    items_json: Optional[List[Any]] = None
    notes: Optional[str] = None


def crane_to_dict(c):
    return {
        "id": str(c.id), "child_no": c.child_no,
        "site_name": c.site_name, "site_address": c.site_address,
        "site_tel": c.site_tel, "site_dept": c.site_dept, "site_contact": c.site_contact,
        "vendor_name": c.vendor_name, "vendor_branch": c.vendor_branch,
        "vendor_contact": c.vendor_contact, "vendor_tel": c.vendor_tel,
        "vendor_fax": c.vendor_fax, "order_no": c.order_no,
        "issue_date": c.issue_date.isoformat() if c.issue_date else None,
        "staff_name": c.staff_name, "creator_name": c.creator_name,
        "items_json": c.items_json or [], "notes": c.notes,
    }


def shipping_to_dict(s):
    return {
        "id": str(s.id), "child_no": s.child_no,
        "dest_name": s.dest_name, "dest_address": s.dest_address,
        "dest_tel": s.dest_tel, "dest_dept": s.dest_dept, "dest_contact": s.dest_contact,
        "carrier_name": s.carrier_name, "carrier_contact": s.carrier_contact,
        "carrier_tel": s.carrier_tel, "carrier_fax": s.carrier_fax,
        "order_no": s.order_no,
        "issue_date": s.issue_date.isoformat() if s.issue_date else None,
        "staff_name": s.staff_name, "creator_name": s.creator_name,
        "items_json": s.items_json or [], "notes": s.notes,
    }


def fan_to_dict(f):
    return {
        "id": str(f.id), "child_no": f.child_no, "order_no": f.order_no,
        "form_type": f.form_type or "PL",
        "vendor_name": f.vendor_name, "vendor_contact": f.vendor_contact,
        "user_name": f.user_name, "user_plant": f.user_plant,
        "user_address": f.user_address, "user_tel": f.user_tel,
        "user_contact": f.user_contact,
        "ship_to_name": f.ship_to_name, "ship_to_plant": f.ship_to_plant,
        "ship_to_address": f.ship_to_address, "ship_to_tel": f.ship_to_tel,
        "ship_to_contact": f.ship_to_contact,
        "ship_date": f.ship_date.isoformat() if f.ship_date else None,
        "transport_method": f.transport_method,
        "product_name": f.product_name, "model": f.model,
        "serial_no": f.serial_no, "drive_type": f.drive_type,
        "spec_json": f.spec_json or {}, "instruction_json": f.instruction_json or {},
        "sales_person_name": f.sales_person_name, "creator_name": f.creator_name,
        "notes": f.notes,
    }


def hotel_to_dict(h):
    return {
        "id": str(h.id), "child_no": h.child_no,
        "site_name": h.site_name, "site_address": h.site_address,
        "items_json": h.items_json or [], "notes": h.notes,
    }


# =============================================
# 案件・見積からの自動補完
# =============================================
def _order_context(po, db):
    """案件と見積から、手配書に流用できる情報をまとめて取り出す。

    見積は納入先（delivery_name / delivery_place）を持っているので、
    現場名・住所はそちらを優先する。無ければ案件の顧客名で埋める。
    """
    q = latest_quotation(po, db)
    ctx = {
        "child_no": po.child_no or '',
        "customer_name": po.customer_name or '',
        "project_name": po.project_name or '',
        "sales_person_name": po.sales_person_name or '',
        "site_name": po.customer_name or '',
        "site_address": '',
        "site_tel": '',
        "site_contact": '',
        "ship_date": po.shipment_date or po.expected_shipment_date,
        "quotation_no": po.quotation_no or '',
        "line_items": [],
    }
    if q:
        ctx["site_name"] = _pick(q.delivery_name, q.customer_name, ctx["site_name"])
        ctx["site_address"] = _pick(q.delivery_place, '')
        ctx["site_contact"] = _pick(q.customer_contact, '')
        ctx["sales_person_name"] = _pick(q.sales_person_name, ctx["sales_person_name"])
        ctx["creator_name"] = _pick(q.created_by_name, '')
        ctx["quotation_no"] = _pick(q.quotation_no, ctx["quotation_no"])
        try:
            ctx["line_items"] = list(q.line_items or [])
        except Exception:
            ctx["line_items"] = []
    ctx.setdefault("creator_name", '')
    return ctx


# =============================================
# クレーン・作業車等 依頼書
# =============================================
@router.get("/crane/{order_id}")
def get_crane(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    c = db.query(CraneArrangement).filter(CraneArrangement.project_order_id == po.id).first()
    if c:
        return crane_to_dict(c)
    # 未作成のときは案件・見積から自動補完した初期値を返す（保存はしない）
    ctx = _order_context(po, db)
    return {
        "id": None, "child_no": po.child_no,
        "site_name": ctx["site_name"], "site_address": ctx["site_address"],
        "site_tel": ctx["site_tel"], "site_dept": '', "site_contact": ctx["site_contact"],
        "vendor_name": '', "vendor_branch": '', "vendor_contact": '',
        "vendor_tel": '', "vendor_fax": '',
        "order_no": po.child_no or '',
        "issue_date": date.today().isoformat(),
        "staff_name": ctx["sales_person_name"], "creator_name": ctx["creator_name"],
        "items_json": [], "notes": '',
        "_autofilled": True,
    }


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


def h4(c1, c2, c3, c4):
    """宛先ブロックの1行（4列）。

    空欄が多いと列が潰れるため、全行の全セルに width を指定する
    （xhtml2pdf は CSS width を無視し、内容から幅を決めてしまう）。
    """
    L = 'style="background:#f0f0f0"'
    return ('<tr><td width="62" ' + L + '>' + c1 + '</td><td width="230">' + c2 + '</td>'
            '<td width="42" ' + L + '>' + c3 + '</td><td width="176">' + c4 + '</td></tr>')


def h4wide(c1, body):
    L = 'style="background:#f0f0f0"'
    return ('<tr><td width="62" ' + L + '>' + c1 + '</td>'
            '<td colspan="3">' + body + '</td></tr>')


def h2(c1, c2):
    L = 'style="background:#f0f0f0"'
    return ('<tr><td width="62" ' + L + '>' + c1 + '</td>'
            '<td width="448">' + c2 + '</td></tr>')


def _crane_item_block(it, idx):
    """依頼書の明細1件分（原紙は1件＝4行の枠）。

    xhtml2pdf は td の CSS width を無視するため列幅は width 属性で指定する。
    さらに、空セルのある行で列が潰れるため全行の全セルに width を付ける。
    """
    L = 'style="background:#f0f0f0"'
    W = (24, 62, 150, 52, 222)   # 合計510pt＝A4の本文幅

    def r(c1, c2, c3, c4, c5, h=''):
        return (
            '<tr>'
            '<td width="%d" %s style="background:#f0f0f0;text-align:center">%s</td>' % (W[0], L, c1) +
            '<td width="%d" %s>%s</td>' % (W[1], L, c2) +
            '<td width="%d">%s</td>' % (W[2], c3) +
            '<td width="%d" %s>%s</td>' % (W[3], L, c4) +
            '<td width="%d"%s>%s</td>' % (W[4], h, c5) +
            '</tr>'
        )
    return (
        '<table style="margin-bottom:6px">'
        + r(str(idx), '機械名', esc(it.get('machine')), '使用期間',
            esc(it.get('start_date')) + '　' + esc(it.get('start_time')) + ' ～')
        + r('&nbsp;', '重量・仕様', esc(it.get('spec')), '&nbsp;',
            esc(it.get('end_date')) + '　' + esc(it.get('end_time')) + ' まで')
        + r('&nbsp;', '納品方法', esc(it.get('delivery')), '備考', esc(it.get('note')))
        + r('&nbsp;', '返却方法', esc(it.get('return_method')), '確認印', '&nbsp;',
            ' style="height:26px"')
        + '</table>'
    )


@router.get("/crane/{order_id}/pdf")
def crane_pdf(order_id: str, format: str = "html", db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    c = db.query(CraneArrangement).filter(CraneArrangement.project_order_id == po.id).first()
    d = crane_to_dict(c) if c else get_crane(order_id, db)

    items = d.get("items_json") or []
    blocks = ''.join(_crane_item_block(it, i + 1) for i, it in enumerate(items))
    if not blocks:
        blocks = '<p style="color:#888">明細がありません</p>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>クレーン・作業車等依頼書</title><style>' + BASE_STYLE + '</style></head><body>'
        + PRINT_BAR
        + '<table style="border:none;margin-bottom:6px"><tr>'
        + '<td style="border:none;font-size:16px;font-weight:bold;letter-spacing:2px">'
          'ｸﾚｰﾝ・作業車等 依頼書</td>'
        + '<td style="border:none;text-align:right;font-size:10px">作成 '
          + esc(d.get('issue_date')) + '</td></tr></table>'
        + '<table style="margin-bottom:6px">'
        + h4('現場名', esc(d.get('site_name')) + ' 御中', '注番',
             '<span style="color:#c00;font-weight:bold">' + esc(d.get('order_no')) + '</span>')
        + h4wide('住　所', esc(d.get('site_address')))
        + h4('TEL', esc(d.get('site_tel')), 'ご担当',
             esc(d.get('site_dept')) + ' ' + esc(d.get('site_contact')) + ' 様')
        + '</table>'
        + '<table style="margin-bottom:6px">'
        + h2('依頼業者', esc(d.get('vendor_name')) + ' ' + esc(d.get('vendor_branch')) + ' 御中')
        + h2('ご担当', esc(d.get('vendor_contact')) + ' 様　　TEL ' + esc(d.get('vendor_tel'))
             + '　　FAX ' + esc(d.get('vendor_fax')))
        + '</table>'
        + '<div style="font-size:10px;margin:6px 0">下記、手配お願い致します。'
          '※請求書には右上の注番を記入してください。</div>'
        + blocks
        + ('<div style="font-size:10px;margin-top:6px">備考：' + esc(d.get('notes')) + '</div>'
           if d.get('notes') else '')
        + '<table style="margin-top:10px;border:none"><tr>'
        + '<td style="border:none;font-size:11px">井上電設株式会社<br>'
          '<span style="font-size:9px">〒460-0022 愛知県名古屋市中区金山4-3-17<br>'
          'TEL：052-322-5271　FAX：052-332-5273</span></td>'
        + '<td style="border:none;text-align:right;font-size:10px">担当：'
          + esc(d.get('staff_name')) + '<br>作成：' + esc(d.get('creator_name')) + '</td>'
        + '</tr></table>'
        + '</body></html>'
    )
    return form_response(html, "%s_クレーン作業車依頼書" % (d.get('order_no') or po.child_no),
                         format == "pdf")


# =============================================
# トラック手配 送り状
# =============================================
@router.get("/shipping/{order_id}")
def get_shipping(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    s = db.query(ShippingArrangement).filter(ShippingArrangement.project_order_id == po.id).first()
    if s:
        return shipping_to_dict(s)
    ctx = _order_context(po, db)
    return {
        "id": None, "child_no": po.child_no,
        "dest_name": ctx["site_name"], "dest_address": ctx["site_address"],
        "dest_tel": ctx["site_tel"], "dest_dept": '', "dest_contact": ctx["site_contact"],
        "carrier_name": '', "carrier_contact": '', "carrier_tel": '', "carrier_fax": '',
        "order_no": po.child_no or '',
        "issue_date": date.today().isoformat(),
        "staff_name": ctx["sales_person_name"], "creator_name": ctx["creator_name"],
        "items_json": [], "notes": '',
        "_autofilled": True,
    }


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


def _shipping_item_block(it, idx):
    """送り状の明細1件分。

    原紙は積込①〜③と、運送業者に記入してもらう欄（社名・運転手・携帯№・車番）を持つ。
    テーブルの入れ子は xhtml2pdf で幅計算が壊れるため1つの表で組み、
    列幅は width 属性を全行に付けて固定する。
    """
    L = 'style="background:#f0f0f0"'
    W = (22, 54, 80, 38, 78, 50, 188)  # 合計510pt

    def r(c1, c2, c3, c4, c5, c6, c7, h=''):
        return (
            '<tr>'
            '<td width="%d" %s style="background:#f0f0f0;text-align:center">%s</td>' % (W[0], L, c1) +
            '<td width="%d" %s>%s</td>' % (W[1], L, c2) +
            '<td width="%d">%s</td>' % (W[2], c3) +
            '<td width="%d" %s>%s</td>' % (W[3], L, c4) +
            '<td width="%d">%s</td>' % (W[4], c5) +
            '<td width="%d" %s>%s</td>' % (W[5], L, c6) +
            '<td width="%d"%s>%s</td>' % (W[6], h, c7) +
            '</tr>'
        )
    return (
        '<table style="margin-bottom:8px">'
        + r(str(idx), '車種', esc(it.get('truck_type')), '積込', esc(it.get('load_date')),
            '到着', esc(it.get('arrive_date')) + '　' + esc(it.get('arrive_time')))
        + '<tr><td width="%d" %s>&nbsp;</td><td width="%d" %s>積込内容</td>'
          '<td colspan="5">%s</td></tr>' % (W[0], L, W[1], L, esc(it.get('cargo')))
        + r('&nbsp;', '積込①', esc(it.get('load1_place')), '時間', esc(it.get('load1_time')),
            '社名', '&nbsp;', ' style="height:20px"')
        + r('&nbsp;', '積込②', esc(it.get('load2_place')), '時間', esc(it.get('load2_time')),
            '運転手', '&nbsp;', ' style="height:20px"')
        + r('&nbsp;', '積込③', esc(it.get('load3_place')), '時間', esc(it.get('load3_time')),
            '携帯№', '&nbsp;', ' style="height:20px"')
        + '<tr><td width="%d" %s>&nbsp;</td><td width="%d" %s>備考</td>'
          '<td colspan="3">%s</td>'
          '<td width="%d" %s>車番</td>'
          '<td width="%d" style="height:20px">&nbsp;</td></tr>'
          % (W[0], L, W[1], L, esc(it.get('note')), W[5], L, W[6])
        + '</table>'
    )


@router.get("/shipping/{order_id}/pdf")
def shipping_pdf(order_id: str, format: str = "html", db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    s = db.query(ShippingArrangement).filter(ShippingArrangement.project_order_id == po.id).first()
    d = shipping_to_dict(s) if s else get_shipping(order_id, db)

    items = d.get("items_json") or []
    blocks = ''.join(_shipping_item_block(it, i + 1) for i, it in enumerate(items))
    if not blocks:
        blocks = '<p style="color:#888">明細がありません</p>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>送り状</title><style>' + BASE_STYLE + '</style></head><body>'
        + PRINT_BAR
        + '<table style="border:none;margin-bottom:6px"><tr>'
        + '<td style="border:none;font-size:16px;font-weight:bold;letter-spacing:4px">送 り 状</td>'
        + '<td style="border:none;text-align:right;font-size:10px">作成 '
          + esc(d.get('issue_date')) + '</td></tr></table>'
        + '<table style="margin-bottom:6px">'
        + h4('送り先', esc(d.get('dest_name')) + ' 御中', '注番',
             '<span style="color:#c00;font-weight:bold">' + esc(d.get('order_no')) + '</span>')
        + h4wide('住　所', esc(d.get('dest_address')))
        + h4('TEL', esc(d.get('dest_tel')), 'ご担当',
             esc(d.get('dest_dept')) + ' ' + esc(d.get('dest_contact')) + ' 様')
        + '</table>'
        + '<table style="margin-bottom:6px">'
        + h2('運送業者', esc(d.get('carrier_name')) + ' 御中')
        + h2('ご担当', esc(d.get('carrier_contact')) + ' 様　　TEL ' + esc(d.get('carrier_tel'))
             + '　　FAX ' + esc(d.get('carrier_fax')))
        + '</table>'
        + '<div style="font-size:10px;margin:6px 0">下記トラックの手配お願い致します。'
          'トラックの社名・車番等が分かりましたら、記入して送り返して下さい。<br>'
          '積込場所で左端の番号を伝えて下さい。（積込の順番・内容を間違えない為）</div>'
        + ('<table style="margin-bottom:6px"><tr>'
           '<td width="62" style="background:#f0f0f0">備　考</td>'
           '<td>' + esc(d.get('notes')) + '</td></tr></table>' if d.get('notes') else '')
        + blocks
        + '<table style="margin-top:10px;border:none"><tr>'
        + '<td style="border:none;font-size:11px">井上電設株式会社<br>'
          '<span style="font-size:9px">〒460-0022 愛知県名古屋市中区金山4-3-17<br>'
          'TEL：052-322-5271　FAX：052-332-5273</span></td>'
        + '<td style="border:none;text-align:right;font-size:10px">担当：'
          + esc(d.get('staff_name')) + '<br>作成：' + esc(d.get('creator_name')) + '</td>'
        + '</tr></table>'
        + '</body></html>'
    )
    return form_response(html, "%s_送り状" % (d.get('order_no') or po.child_no), format == "pdf")


# =============================================
# 排風機 注文確認書 / ファン作業指示書
# =============================================
FAN_MODEL_RE = re.compile(r'\b(PLD?[\d.]+[A-Z0-9\-]*|RTD?[\d.]+[A-Z0-9\-]*)', re.IGNORECASE)
FAN_KW_RE = re.compile(r'([\d.]+)\s*[kK][wW]')
FAN_POLE_RE = re.compile(r'(\d+)\s*[pP]\b')
FAN_DIA_RE = re.compile(r'[φΦ]\s*(\d{2,4})')


def _fan_autofill(po, db):
    """見積明細から排風機の型式・出力・極数・口径を拾って初期値にする。

    見積の品名/仕様に「排風機 PLD7.5」「7.5kw 4P」「φ380」等が入っているため、
    そこから読み取る。読めない項目は空欄のままとし、画面で加筆してもらう。
    """
    ctx = _order_context(po, db)
    model = kw = pole = ''
    dias = []
    for it in ctx["line_items"]:
        text = ' '.join(str(x or '') for x in (
            getattr(it, 'item_name', ''), getattr(it, 'spec_detail', '')))
        if not text.strip():
            continue
        if not model:
            m = FAN_MODEL_RE.search(text)
            if m and ('排風機' in text or 'ファン' in text or 'ﾌｧﾝ' in text or m.group(1)[:2].upper() in ('PL', 'RT')):
                model = m.group(1).upper()
        if '排風機' in text or 'ファン' in text or 'ﾌｧﾝ' in text:
            if not kw:
                m = FAN_KW_RE.search(text)
                if m:
                    kw = m.group(1)
            if not pole:
                m = FAN_POLE_RE.search(text)
                if m:
                    pole = m.group(1)
            dias += FAN_DIA_RE.findall(text)
    return ctx, model, kw, pole, dias


@router.get("/fan/{order_id}")
def get_fan(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    f = db.query(FanArrangement).filter(FanArrangement.project_order_id == po.id).first()
    if f:
        return fan_to_dict(f)
    ctx, model, kw, pole, dias = _fan_autofill(po, db)
    return {
        "id": None, "child_no": po.child_no, "order_no": po.child_no or '',
        "form_type": "PL",
        "vendor_name": '', "vendor_contact": '',
        "user_name": ctx["customer_name"], "user_plant": '',
        "user_address": ctx["site_address"], "user_tel": ctx["site_tel"],
        "user_contact": ctx["site_contact"],
        "ship_to_name": ctx["site_name"], "ship_to_plant": '',
        "ship_to_address": ctx["site_address"], "ship_to_tel": ctx["site_tel"],
        "ship_to_contact": ctx["site_contact"],
        "ship_date": ctx["ship_date"].isoformat() if ctx["ship_date"] else None,
        "transport_method": '',
        "product_name": 'プレートファン', "model": model,
        "serial_no": '', "drive_type": '',
        "spec_json": {
            "frequency": '', "voltage": '', "control_voltage": '',
            "motor_kw": kw, "motor_pole": pole, "motor_type": '',
            "motor_flange": '', "motor_maker": '', "motor_note": '',
            "spec_place": '', "intake_dia": dias[0] if dias else '',
            "exhaust_dia": dias[1] if len(dias) > 1 else '',
            "intake_flange": '', "exhaust_flange": '',
            "switch_type": '', "control_panel": '',
            "paint_color": '', "color_no": '',
        },
        "instruction_json": {
            "order_customer": ctx["customer_name"], "usage_spec": '',
            "bearing_fan": '', "bearing_pulley": '',
            "motor_pulley": '', "fan_pulley": '', "belt": '', "rpm": '',
            "cover": '', "inspection_port": '', "frame": '', "paint": '',
            "pressure": '', "airflow": '', "current": '',
        },
        "sales_person_name": ctx["sales_person_name"],
        "creator_name": ctx["creator_name"], "notes": '',
        "_autofilled": True,
    }


@router.put("/fan/{order_id}")
def save_fan(order_id: str, data: FanData, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    f = db.query(FanArrangement).filter(FanArrangement.project_order_id == po.id).first()
    if not f:
        f = FanArrangement(project_order_id=po.id, child_no=po.child_no)
        db.add(f)
    for k, v in data.dict(exclude_unset=True).items():
        setattr(f, k, v)
    db.commit(); db.refresh(f)
    return fan_to_dict(f)


def _kv(label, value, lw='72px'):
    return ('<tr><td style="background:#f0f0f0;width:' + lw + '">' + label + '</td>'
            '<td>' + esc(value) + '</td></tr>')


@router.get("/fan/{order_id}/pdf")
def fan_order_pdf(order_id: str, format: str = "html", db: Session = Depends(get_db)):
    """排風機 注文確認書（発注先へ送り、捺印して返送してもらう書面）"""
    po = find_order(order_id, db)
    f = db.query(FanArrangement).filter(FanArrangement.project_order_id == po.id).first()
    d = fan_to_dict(f) if f else get_fan(order_id, db)
    sp = d.get("spec_json") or {}

    L = 'style="background:#f0f0f0"'

    def hdr(c1, c2, c3, c4):
        """宛先・出荷先ブロック（4列・全行に幅を指定して列の潰れを防ぐ）"""
        return ('<tr><td width="72" ' + L + '>' + c1 + '</td><td width="190">' + c2 + '</td>'
                '<td width="72" ' + L + '>' + c3 + '</td><td width="176">' + c4 + '</td></tr>')

    def spec(c1, c2, c3, c4, c5, c6):
        """仕様ブロック（6列）"""
        return ('<tr><td width="72" ' + L + '>' + c1 + '</td><td width="130">' + c2 + '</td>'
                '<td width="72" ' + L + '>' + c3 + '</td><td width="100">' + c4 + '</td>'
                '<td width="64" ' + L + '>' + c5 + '</td><td width="72">' + c6 + '</td></tr>')

    def spec_wide(c1, body):
        return ('<tr><td width="72" ' + L + '>' + c1 + '</td>'
                '<td colspan="5">' + body + '</td></tr>')

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>注文確認書</title><style>' + BASE_STYLE + '</style></head><body>'
        + PRINT_BAR
        + '<div style="font-size:17px;font-weight:bold;text-align:center;letter-spacing:6px;'
          'margin-bottom:8px">注 文 確 認 書</div>'
        + '<table style="margin-bottom:6px">'
        + '<tr><td width="316" rowspan="2" style="border:none;vertical-align:top">'
          + esc(d.get('vendor_name')) + ' 御中<br>' + esc(d.get('vendor_contact')) + ' 様</td>'
        + '<td width="64" ' + L + '>受注No.</td>'
          '<td width="130" style="color:#c00;font-weight:bold">' + esc(d.get('order_no')) + '</td></tr>'
        + '<tr><td ' + L + '>御確認印</td><td style="height:38px">&nbsp;</td></tr></table>'
        + '<div style="font-size:10px;margin:6px 0">'
          'このたびはご注文を頂きありがとうございます。<br>'
          '下記内容をご確認の上、捺印後折り返しFAXにてご返送下さいますようお願い致します。</div>'
        + '<table style="margin-bottom:6px">'
        + hdr('ユーザー名', esc(d.get('user_name')) + ' 様　' + esc(d.get('user_plant')),
              'ご担当者', esc(d.get('user_contact')) + ' 様')
        + hdr('住所', esc(d.get('user_address')), 'TEL', esc(d.get('user_tel')))
        + hdr('出荷先', esc(d.get('ship_to_name')) + ' 様　' + esc(d.get('ship_to_plant')),
              'ご担当者', esc(d.get('ship_to_contact')) + ' 様')
        + hdr('住所', esc(d.get('ship_to_address')), 'TEL', esc(d.get('ship_to_tel')))
        + hdr('出荷日', esc(d.get('ship_date')), '運送方法', esc(d.get('transport_method')))
        + '</table>'
        + '<div style="font-size:9px;margin-bottom:6px">'
          '【引取：貴社手配のトラックにてお引取／パレット：宅配にてパレット梱包出荷／工事：井上工事】</div>'
        + '<table style="margin-bottom:6px">'
        + spec('名称', esc(d.get('product_name')), '駆動方式', esc(d.get('drive_type')),
               '製造No.', esc(d.get('serial_no')))
        + spec('型式', esc(d.get('model')), '周波数', esc(sp.get('frequency')) + ' Hz',
               '動力', esc(sp.get('voltage')) + ' V')
        + spec('ﾓｰﾀ',
               esc(sp.get('motor_kw')) + ' kW　' + esc(sp.get('motor_pole')) + ' P　'
               + esc(sp.get('motor_type')),
               'ﾒｰｶ', esc(sp.get('motor_maker')), '備考', esc(sp.get('motor_note')))
        + spec_wide('仕様', esc(sp.get('spec_place')) + '（屋内 / 屋外）※ご確認ください')
        + spec_wide('吸排気口',
                    '吸 φ' + esc(sp.get('intake_dia')) + '　' + esc(sp.get('intake_flange'))
                    + '　／　排 φ' + esc(sp.get('exhaust_dia')) + '　'
                    + esc(sp.get('exhaust_flange')))
        + spec_wide('ｽｲｯﾁ',
                    esc(sp.get('switch_type')) + '　制御盤：' + esc(sp.get('control_panel'))
                    + '<br><span style="font-size:9px">※必要の有無を記載願います。'
                      'なお、電気配線工事は含んでいません。</span>')
        + spec('指定色', esc(sp.get('paint_color')), '色番号', esc(sp.get('color_no')), '&nbsp;', '&nbsp;')
        + spec_wide('備考', esc(d.get('notes')))
        + '</table>'
        + '<div style="font-size:9px">※印箇所ご確認・ご指示願います。</div>'
        + '<table style="margin-top:8px"><tr>'
          '<td width="316" style="border:none">&nbsp;</td>'
          '<td width="56" ' + L + '>営業</td>'
          '<td width="66">' + esc(d.get('sales_person_name')) + '</td>'
          '<td width="36" ' + L + '>作成</td>'
          '<td width="66">' + esc(d.get('creator_name')) + '</td></tr></table>'
        + '</body></html>'
    )
    return form_response(html, "%s_排風機注文確認書" % (d.get('order_no') or po.child_no),
                         format == "pdf")


@router.get("/fan/{order_id}/instruction-pdf")
def fan_instruction_pdf(order_id: str, format: str = "html", db: Session = Depends(get_db)):
    """ファン作業指示書（社内の製造指示）"""
    po = find_order(order_id, db)
    f = db.query(FanArrangement).filter(FanArrangement.project_order_id == po.id).first()
    d = fan_to_dict(f) if f else get_fan(order_id, db)
    sp = d.get("spec_json") or {}
    ins = d.get("instruction_json") or {}

    L = 'style="background:#f0f0f0"'

    def r4(c1, c2, c3, c4, h=''):
        """4列（全行に幅を指定して列の潰れを防ぐ）"""
        return ('<tr><td width="72" ' + L + '>' + c1 + '</td>'
                '<td width="190"' + h + '>' + c2 + '</td>'
                '<td width="72" ' + L + '>' + c3 + '</td>'
                '<td width="176"' + h + '>' + c4 + '</td></tr>')

    def r4wide(c1, body):
        return ('<tr><td width="72" ' + L + '>' + c1 + '</td>'
                '<td colspan="3">' + body + '</td></tr>')

    def r6(c1, c2, c3, c4, c5, c6, h=''):
        return ('<tr><td width="72" ' + L + '>' + c1 + '</td>'
                '<td width="110"' + h + '>' + c2 + '</td>'
                '<td width="72" ' + L + '>' + c3 + '</td>'
                '<td width="110"' + h + '>' + c4 + '</td>'
                '<td width="72" ' + L + '>' + c5 + '</td>'
                '<td width="74"' + h + '>' + c6 + '</td></tr>')

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>ファン作業指示書</title><style>' + BASE_STYLE + '</style></head><body>'
        + PRINT_BAR
        + '<table style="margin-bottom:6px">'
        + '<tr><td width="316" rowspan="2" style="border:none;font-size:16px;font-weight:bold;'
          'letter-spacing:4px;vertical-align:top">フ ァ ン 作 業 指 示 書</td>'
        + '<td width="64" ' + L + '>営業担当</td>'
          '<td width="130">' + esc(d.get('sales_person_name')) + '</td></tr>'
        + '<tr><td ' + L + '>作成</td><td>' + esc(d.get('creator_name')) + '</td></tr></table>'
        + '<table style="margin-bottom:6px">'
        + r4('型式', esc(d.get('model')), '製造番号', esc(d.get('serial_no')))
        + r4('御注文主', esc(ins.get('order_customer')) + ' 殿', '受注番号',
             '<span style="color:#c00;font-weight:bold">' + esc(d.get('order_no')) + '</span>')
        + r4('納入先', esc(d.get('ship_to_name')) + ' ' + esc(d.get('ship_to_plant')) + ' 殿',
             '用途・仕様', esc(ins.get('usage_spec')))
        + r4('出荷日', esc(d.get('ship_date')), '出荷方法', esc(d.get('transport_method')))
        + '</table>'
        + '<table style="margin-bottom:6px">'
        + r4wide('ﾓｰﾀ',
                 esc(sp.get('motor_kw')) + ' kW　' + esc(sp.get('motor_pole')) + ' P　'
                 + esc(sp.get('frequency')) + ' Hz　' + esc(sp.get('voltage')) + ' V　'
                 + esc(sp.get('motor_type')) + '　' + esc(sp.get('motor_maker')))
        + r4('軸受', '羽根側：' + esc(ins.get('bearing_fan')),
             'ﾌﾟｰﾘ側', esc(ins.get('bearing_pulley')))
        + r4('ﾓｰﾀ側ﾌﾟｰﾘ', esc(ins.get('motor_pulley')), 'Vﾍﾞﾙﾄ', esc(ins.get('belt')))
        + r4('ﾌｧﾝ側ﾌﾟｰﾘ', esc(ins.get('fan_pulley')), '回転数', esc(ins.get('rpm')) + ' rpm')
        + r4('ｶﾊﾞｰ', esc(ins.get('cover')), '吸口',
             'φ' + esc(sp.get('intake_dia')) + '　' + esc(sp.get('intake_flange')))
        + r4('点検口', esc(ins.get('inspection_port')), '出口',
             'φ' + esc(sp.get('exhaust_dia')) + '　' + esc(sp.get('exhaust_flange')))
        + r4('架台', esc(ins.get('frame')), '塗装色',
             esc(_pick(ins.get('paint'), sp.get('paint_color'))))
        + r4wide('備考', esc(d.get('notes')))
        + '</table>'
        + '<div style="font-size:11px;font-weight:bold;margin:8px 0 4px">想定性能</div>'
        + '<table style="margin-bottom:6px">'
        + r6('圧力', esc(ins.get('pressure')) + ' mmaq', '風量',
             esc(ins.get('airflow')) + ' ㎥/min', '電流', esc(ins.get('current')) + ' A')
        + '</table>'
        + '<div style="font-size:11px;font-weight:bold;margin:8px 0 4px">出荷時チェックリスト</div>'
        + '<table>'
        + r6('検査者', '&nbsp;', '日付', '&nbsp;', '判定', '&nbsp;', ' style="height:22px"')
        + r6('電流値', '&nbsp;', '外観', '&nbsp;', '回転方向', '&nbsp;', ' style="height:22px"')
        + r6('異音', '&nbsp;', '振動値', '&nbsp;', '&nbsp;', '&nbsp;', ' style="height:22px"')
        + '</table>'
        + '</body></html>'
    )
    return form_response(html, "%s_ファン作業指示書" % (d.get('order_no') or po.child_no),
                         format == "pdf")


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
        + '<td width="70" style="background:#f0f0f0">現場</td><td>' + esc(d.get('site_name')) + '</td>'
        + '<td width="70" style="background:#f0f0f0">受注番号</td><td>' + esc(d.get('child_no')) + '</td></tr>'
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


@router.get("/setup-forms")
def setup_arrangement_forms(db: Session = Depends(get_db)):
    """帳票の項目追加（冪等）。

    原紙どおりの様式でPDFを出すために、クレーン依頼書・送り状へ項目を足し、
    排風機（注文確認書/ファン作業指示書）のテーブルを作る。
    """
    from sqlalchemy import text
    from app.db.models import Base, engine, FanArrangement
    Base.metadata.create_all(bind=engine, tables=[FanArrangement.__table__])
    stmts = [
        "ALTER TABLE crane_arrangements ADD COLUMN IF NOT EXISTS site_dept VARCHAR(100)",
        "ALTER TABLE crane_arrangements ADD COLUMN IF NOT EXISTS issue_date DATE",
        "ALTER TABLE crane_arrangements ADD COLUMN IF NOT EXISTS staff_name VARCHAR(100)",
        "ALTER TABLE crane_arrangements ADD COLUMN IF NOT EXISTS creator_name VARCHAR(100)",
        "ALTER TABLE shipping_arrangements ADD COLUMN IF NOT EXISTS carrier_fax VARCHAR(50)",
        "ALTER TABLE shipping_arrangements ADD COLUMN IF NOT EXISTS dest_dept VARCHAR(100)",
        "ALTER TABLE shipping_arrangements ADD COLUMN IF NOT EXISTS dest_contact VARCHAR(100)",
        "ALTER TABLE shipping_arrangements ADD COLUMN IF NOT EXISTS issue_date DATE",
        "ALTER TABLE shipping_arrangements ADD COLUMN IF NOT EXISTS staff_name VARCHAR(100)",
        "ALTER TABLE shipping_arrangements ADD COLUMN IF NOT EXISTS creator_name VARCHAR(100)",
    ]
    done = []
    for sql in stmts:
        try:
            db.execute(text(sql)); done.append(sql.split("EXISTS ")[-1])
        except Exception as e:
            done.append("NG: %s (%s)" % (sql[:60], e))
    db.commit()
    return {"ok": True, "fan_table": "fan_arrangements", "columns": done}
