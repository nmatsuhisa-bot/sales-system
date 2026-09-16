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
from urllib.parse import quote
from app.db.models import (
    pk_or_code,
    get_db, ProjectOrder,
    CraneArrangement, ShippingArrangement, HotelArrangement, ArrangementVendor,
    FanArrangement,
)
from app.form_edit import (
    ef, inject_edit, get_path, apply_fields, apply_row_op, parse_date,
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
def _norm_name(s):
    """会社名の照合用。全角半角・空白・法人格の表記ゆれを無視する。"""
    import unicodedata
    t = unicodedata.normalize('NFKC', str(s or '')).lower()
    for w in ('株式会社', '有限会社', '合同会社', '(株)', '(有)', '(同)'):
        t = t.replace(w, '')
    return re.sub(r'[\s・,.\-_()（）]', '', t)


def _site_master(po, db):
    """納入先マスタから現場の住所・TELを引く。

    案件（子ID）の顧客IDで引き、無ければ顧客名で照合する。
    住所・TELは見積に無いため、ここが唯一の自動補完の情報源になる。
    """
    from app.db.models import DeliveryDestination
    d = None
    if po.customer_code:
        d = db.query(DeliveryDestination).filter(
            DeliveryDestination.customer_id == po.customer_code).first()
    if not d and po.customer_name:
        key = _norm_name(po.customer_name)
        for cand in db.query(DeliveryDestination).limit(2000).all():
            full = cand.company_factory_name or ((cand.company_name or '') + (cand.factory_name or ''))
            if _norm_name(full) == key or _norm_name(cand.company_name) == key:
                d = cand
                break
    return d


def _order_context(po, db):
    """案件と見積から、手配書に流用できる情報をまとめて取り出す。

    見積は納入先（delivery_name / delivery_place）を持っているので、
    現場名・住所はそちらを優先する。無ければ案件の顧客名で埋める。
    住所・TELは見積にも案件にも無いため、納入先マスタから補う。
    """
    q = latest_quotation(po, db)
    ctx = {
        "child_no": po.child_no or '',
        "customer_name": po.customer_name or '',
        "agency_name": po.agency_name or '',
        "project_name": po.project_name or '',
        "sales_person_name": po.sales_person_name or '',
        "site_name": po.customer_name or '',
        "site_address": '',
        "site_tel": '',
        "site_contact": '',
        "ship_date": po.shipment_date or po.expected_shipment_date,
        "quotation_no": po.quotation_no or '',
        "quotation_title": '',
        "delivery_terms": '',
        "line_items": [],
        "labor_details": [],
    }
    if q:
        ctx["site_name"] = _pick(q.delivery_name, q.customer_name, ctx["site_name"])
        ctx["site_address"] = _pick(q.delivery_place, '')
        ctx["site_contact"] = _pick(q.customer_contact, '')
        ctx["sales_person_name"] = _pick(q.sales_person_name, ctx["sales_person_name"])
        ctx["creator_name"] = _pick(q.created_by_name, '')
        ctx["quotation_no"] = _pick(q.quotation_no, ctx["quotation_no"])
        ctx["quotation_title"] = _pick(q.title, '')
        ctx["delivery_terms"] = _pick(q.delivery_terms, '')
        ctx["agency_name"] = _pick(q.customer_name, ctx["agency_name"])
        for attr, key in (("line_items", "line_items"), ("labor_details", "labor_details")):
            try:
                ctx[key] = list(getattr(q, attr) or [])
            except Exception:
                ctx[key] = []
    m = _site_master(po, db)
    if m:
        ctx["site_address"] = _pick(ctx["site_address"], m.address)
        ctx["site_tel"] = _pick(ctx["site_tel"], m.tel)
        ctx["site_name"] = _pick(ctx["site_name"], m.company_factory_name, m.company_name)
    ctx.setdefault("creator_name", '')
    return ctx


# 社内工数・見積明細から、クレーン/作業車の手配に該当する行を拾うための語
CRANE_WORD_RE = re.compile(
    r'クレーン|ｸﾚｰﾝ|ユニック|ﾕﾆｯｸ|レッカー|ﾚｯｶｰ|ラフター|ﾗﾌﾀｰ|高所|リフト|ﾘﾌﾄ|ゴンドラ')
# 送り状に積まない（工事・役務）行
SERVICE_WORD_RE = re.compile(
    r'工事|据付|据え付け|試運転|調整|運搬|輸送|設計|製図|諸経費|出張|養生|撤去|工費|人件')


def _dstr(d):
    return d.isoformat() if hasattr(d, 'isoformat') else (d or '')


def _qty(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ''
    return str(int(f)) if f == int(f) else ('%g' % f)


def _crane_items_from_quotation(ctx):
    """見積の社内工数（レッカー種別のある行）と明細から、依頼書の明細を作る。

    工数マスタの「レッカー」「クレーン」等の行が手配対象。使用期間は出荷予定日を入れる。
    読み取れない項目（時間・納品方法・返却方法）は空欄のまま画面で加筆してもらう。
    """
    ds = _dstr(ctx.get("ship_date"))
    items = []
    for l in ctx.get("labor_details") or []:
        name = getattr(l, 'item_name', '') or ''
        crane = getattr(l, 'crane_type', '') or ''
        if not crane and not CRANE_WORD_RE.search(name):
            continue
        qty = _qty(getattr(l, 'quantity', None))
        unit = getattr(l, 'unit', '') or ''
        items.append({
            "machine": crane or name,
            "spec": ' '.join(x for x in [name if crane else '', (qty + unit) if qty else ''] if x),
            "start_date": ds, "start_time": '', "end_date": ds, "end_time": '',
            "delivery": '', "return_method": '', "note": '',
        })
    if not items:
        for it in ctx.get("line_items") or []:
            text = (getattr(it, 'item_name', '') or '')
            if CRANE_WORD_RE.search(text):
                items.append({
                    "machine": text, "spec": getattr(it, 'spec_detail', '') or '',
                    "start_date": ds, "start_time": '', "end_date": ds, "end_time": '',
                    "delivery": '', "return_method": '', "note": '',
                })
    return items[:6]


def _shipping_items_from_quotation(ctx):
    """見積明細の機械本体（工事・役務を除く行）から、送り状の積込内容を作る。

    原紙は1明細＝トラック1台のため、既定は1台分にまとめる。台数が増える場合は
    画面の「明細を追加」で増やしてもらう。
    """
    names = []
    for it in ctx.get("line_items") or []:
        nm = (getattr(it, 'item_name', '') or '').strip()
        if not nm or SERVICE_WORD_RE.search(nm):
            continue
        q = _qty(getattr(it, 'quantity', None))
        unit = getattr(it, 'unit', '') or ''
        names.append(nm + (f'　{q}{unit}' if q and q != '1' else ''))
    if not names:
        return []
    return [{
        "truck_type": '', "load_date": '', "arrive_date": _dstr(ctx.get("ship_date")),
        "arrive_time": '', "cargo": '、'.join(names[:8]),
        "load1_place": '', "load1_time": '', "load2_place": '', "load2_time": '',
        "load3_place": '', "load3_time": '', "note": '',
    }]


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
        "items_json": _crane_items_from_quotation(ctx), "notes": '',
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


def _crane_item_block(it, idx, mode="view"):
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
        + r(str(idx), '機械名', ef(mode, 'items_json.%d.machine' % (idx - 1), it.get('machine')), '使用期間',
            ef(mode, 'items_json.%d.start_date' % (idx - 1), it.get('start_date')) + '　' + ef(mode, 'items_json.%d.start_time' % (idx - 1), it.get('start_time')) + ' ～')
        + r('&nbsp;', '重量・仕様', ef(mode, 'items_json.%d.spec' % (idx - 1), it.get('spec')), '&nbsp;',
            ef(mode, 'items_json.%d.end_date' % (idx - 1), it.get('end_date')) + '　' + ef(mode, 'items_json.%d.end_time' % (idx - 1), it.get('end_time')) + ' まで')
        + r('&nbsp;', '納品方法', ef(mode, 'items_json.%d.delivery' % (idx - 1), it.get('delivery')), '備考', ef(mode, 'items_json.%d.note' % (idx - 1), it.get('note')))
        + r('&nbsp;', '返却方法', ef(mode, 'items_json.%d.return_method' % (idx - 1), it.get('return_method')), '確認印', '&nbsp;',
            ' style="height:26px"')
        + '</table>'
    )


@router.get("/crane/{order_id}/pdf")
def crane_pdf(order_id: str, format: str = "html", mode: str = "", db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    c = db.query(CraneArrangement).filter(CraneArrangement.project_order_id == po.id).first()
    d = crane_to_dict(c) if c else get_crane(order_id, db)
    M = _mode(format, mode)
    F = lambda k, v=None, block=False: ef(M, k, get_path(d, k) if v is None else v, block)

    items = d.get("items_json") or []
    blocks = ''.join(_crane_item_block(it, i + 1, M) + (_rowop(i) if M == "edit" else "") for i, it in enumerate(items))
    if not blocks:
        blocks = '<p style="color:#888">明細がありません</p>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>クレーン・作業車等依頼書</title><style>' + BASE_STYLE + '</style></head><body>'
        + (PRINT_BAR if M != "edit" else '')
        + '<table style="border:none;margin-bottom:6px"><tr>'
        + '<td style="border:none;font-size:16px;font-weight:bold;letter-spacing:2px">'
          'ｸﾚｰﾝ・作業車等 依頼書</td>'
        + '<td style="border:none;text-align:right;font-size:10px">作成 '
          + F('issue_date') + '</td></tr></table>'
        + '<table style="margin-bottom:6px">'
        + h4('現場名', F('site_name') + ' 御中', '注番',
             '<span style="color:#c00;font-weight:bold">' + F('order_no') + '</span>')
        + h4wide('住　所', F('site_address'))
        + h4('TEL', F('site_tel'), 'ご担当',
             F('site_dept') + ' ' + F('site_contact') + ' 様')
        + '</table>'
        + '<table style="margin-bottom:6px">'
        + h2('依頼業者', F('vendor_name') + ' ' + F('vendor_branch') + ' 御中')
        + h2('ご担当', F('vendor_contact') + ' 様　　TEL ' + F('vendor_tel')
             + '　　FAX ' + F('vendor_fax'))
        + '</table>'
        + '<div style="font-size:10px;margin:6px 0">下記、手配お願い致します。'
          '※請求書には右上の注番を記入してください。</div>'
        + blocks
        + ('<div style="font-size:10px;margin-top:6px">備考：' + F('notes', block=True) + '</div>'
           if (d.get('notes') or M == "edit") else '')
        + '<table style="margin-top:10px;border:none"><tr>'
        + '<td style="border:none;font-size:11px">井上電設株式会社<br>'
          '<span style="font-size:9px">〒460-0022 愛知県名古屋市中区金山4-3-17<br>'
          'TEL：052-322-5271　FAX：052-332-5273</span></td>'
        + '<td style="border:none;text-align:right;font-size:10px">担当：'
          + F('staff_name') + '<br>作成：' + F('creator_name') + '</td>'
        + '</tr></table>'
        + '</body></html>'
    )
    if M == "edit":
        html = _inject(html, "crane", order_id, "クレーン・作業車等 依頼書", db, pdf_path="pdf", rows=True, extra='')
    return form_response(html, "%s_クレーン作業車依頼書" % (d.get('order_no') or po.child_no),
                         M == "pdf")


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
        "items_json": _shipping_items_from_quotation(ctx), "notes": '',
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


def _shipping_item_block(it, idx, mode="view"):
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
        + r(str(idx), '車種', ef(mode, 'items_json.%d.truck_type' % (idx - 1), it.get('truck_type')), '積込', ef(mode, 'items_json.%d.load_date' % (idx - 1), it.get('load_date')),
            '到着', ef(mode, 'items_json.%d.arrive_date' % (idx - 1), it.get('arrive_date')) + '　' + ef(mode, 'items_json.%d.arrive_time' % (idx - 1), it.get('arrive_time')))
        + '<tr><td width="%d" %s>&nbsp;</td><td width="%d" %s>積込内容</td>'
          '<td colspan="5">%s</td></tr>' % (W[0], L, W[1], L, ef(mode, 'items_json.%d.cargo' % (idx - 1), it.get('cargo')))
        + r('&nbsp;', '積込①', ef(mode, 'items_json.%d.load1_place' % (idx - 1), it.get('load1_place')), '時間', ef(mode, 'items_json.%d.load1_time' % (idx - 1), it.get('load1_time')),
            '社名', '&nbsp;', ' style="height:20px"')
        + r('&nbsp;', '積込②', ef(mode, 'items_json.%d.load2_place' % (idx - 1), it.get('load2_place')), '時間', ef(mode, 'items_json.%d.load2_time' % (idx - 1), it.get('load2_time')),
            '運転手', '&nbsp;', ' style="height:20px"')
        + r('&nbsp;', '積込③', ef(mode, 'items_json.%d.load3_place' % (idx - 1), it.get('load3_place')), '時間', ef(mode, 'items_json.%d.load3_time' % (idx - 1), it.get('load3_time')),
            '携帯№', '&nbsp;', ' style="height:20px"')
        + '<tr><td width="%d" %s>&nbsp;</td><td width="%d" %s>備考</td>'
          '<td colspan="3">%s</td>'
          '<td width="%d" %s>車番</td>'
          '<td width="%d" style="height:20px">&nbsp;</td></tr>'
          % (W[0], L, W[1], L, ef(mode, 'items_json.%d.note' % (idx - 1), it.get('note')), W[5], L, W[6])
        + '</table>'
    )


@router.get("/shipping/{order_id}/pdf")
def shipping_pdf(order_id: str, format: str = "html", mode: str = "", db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    s = db.query(ShippingArrangement).filter(ShippingArrangement.project_order_id == po.id).first()
    d = shipping_to_dict(s) if s else get_shipping(order_id, db)
    M = _mode(format, mode)
    F = lambda k, v=None, block=False: ef(M, k, get_path(d, k) if v is None else v, block)

    items = d.get("items_json") or []
    blocks = ''.join(_shipping_item_block(it, i + 1, M) + (_rowop(i) if M == "edit" else "") for i, it in enumerate(items))
    if not blocks:
        blocks = '<p style="color:#888">明細がありません</p>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>送り状</title><style>' + BASE_STYLE + '</style></head><body>'
        + (PRINT_BAR if M != "edit" else '')
        + '<table style="border:none;margin-bottom:6px"><tr>'
        + '<td style="border:none;font-size:16px;font-weight:bold;letter-spacing:4px">送 り 状</td>'
        + '<td style="border:none;text-align:right;font-size:10px">作成 '
          + F('issue_date') + '</td></tr></table>'
        + '<table style="margin-bottom:6px">'
        + h4('送り先', F('dest_name') + ' 御中', '注番',
             '<span style="color:#c00;font-weight:bold">' + F('order_no') + '</span>')
        + h4wide('住　所', F('dest_address'))
        + h4('TEL', F('dest_tel'), 'ご担当',
             F('dest_dept') + ' ' + F('dest_contact') + ' 様')
        + '</table>'
        + '<table style="margin-bottom:6px">'
        + h2('運送業者', F('carrier_name') + ' 御中')
        + h2('ご担当', F('carrier_contact') + ' 様　　TEL ' + F('carrier_tel')
             + '　　FAX ' + F('carrier_fax'))
        + '</table>'
        + '<div style="font-size:10px;margin:6px 0">下記トラックの手配お願い致します。'
          'トラックの社名・車番等が分かりましたら、記入して送り返して下さい。<br>'
          '積込場所で左端の番号を伝えて下さい。（積込の順番・内容を間違えない為）</div>'
        + ('<table style="margin-bottom:6px"><tr>'
           '<td width="62" style="background:#f0f0f0">備　考</td>'
           '<td>' + F('notes', block=True) + '</td></tr></table>' if (d.get('notes') or M == "edit") else '')
        + blocks
        + '<table style="margin-top:10px;border:none"><tr>'
        + '<td style="border:none;font-size:11px">井上電設株式会社<br>'
          '<span style="font-size:9px">〒460-0022 愛知県名古屋市中区金山4-3-17<br>'
          'TEL：052-322-5271　FAX：052-332-5273</span></td>'
        + '<td style="border:none;text-align:right;font-size:10px">担当：'
          + F('staff_name') + '<br>作成：' + F('creator_name') + '</td>'
        + '</tr></table>'
        + '</body></html>'
    )
    if M == "edit":
        html = _inject(html, "shipping", order_id, "トラック手配 送り状", db, pdf_path="pdf", rows=True, extra='')
    return form_response(html, "%s_送り状" % (d.get('order_no') or po.child_no), M == "pdf")


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


def _fan_spec_from_quotation(ctx):
    """見積明細の spec_json（BFQ/BFRパターンで保存される仕様）から、製品名・周波数・電圧を拾う。

    パターン選択で作った明細には hz / voltage / fan_model が入っているため、
    文字列の読み取りより確実に取れる。
    """
    out = {"product_name": 'プレートファン', "frequency": '', "voltage": '', "fan_model": ''}
    for it in ctx.get("line_items") or []:
        sj = getattr(it, 'spec_json', None) or {}
        name = (getattr(it, 'item_name', '') or '') + ' ' + (getattr(it, 'spec_detail', '') or '')
        if not out["frequency"] and sj.get('hz'):
            out["frequency"] = '%sHz' % sj['hz']
        if not out["voltage"] and sj.get('voltage'):
            out["voltage"] = '%sV' % sj['voltage']
        if not out["fan_model"] and sj.get('fan_model'):
            out["fan_model"] = str(sj['fan_model'])
        if 'ターボファン' in name or 'ﾀｰﾎﾞﾌｧﾝ' in name:
            out["product_name"] = 'ターボファン'
        elif 'プレートファン' in name or 'ﾌﾟﾚｰﾄﾌｧﾝ' in name:
            out["product_name"] = 'プレートファン'
    return out


@router.get("/fan/{order_id}")
def get_fan(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    f = db.query(FanArrangement).filter(FanArrangement.project_order_id == po.id).first()
    if f:
        return fan_to_dict(f)
    ctx, model, kw, pole, dias = _fan_autofill(po, db)
    spec = _fan_spec_from_quotation(ctx)
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
        "product_name": spec["product_name"], "model": _pick(model, spec["fan_model"]),
        "serial_no": '', "drive_type": '',
        "spec_json": {
            "frequency": spec["frequency"], "voltage": spec["voltage"], "control_voltage": '',
            "motor_kw": kw, "motor_pole": pole, "motor_type": '',
            "motor_flange": '', "motor_maker": '', "motor_note": '',
            "spec_place": '', "intake_dia": dias[0] if dias else '',
            "exhaust_dia": dias[1] if len(dias) > 1 else '',
            "intake_flange": '', "exhaust_flange": '',
            "switch_type": '', "control_panel": '',
            "paint_color": '', "color_no": '',
        },
        "instruction_json": {
            "order_customer": _pick(ctx["agency_name"], ctx["customer_name"]),
            "usage_spec": _pick(ctx["quotation_title"], ctx["project_name"]),
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
def fan_order_pdf(order_id: str, format: str = "html", mode: str = "", db: Session = Depends(get_db)):
    """排風機 注文確認書（発注先へ送り、捺印して返送してもらう書面）"""
    po = find_order(order_id, db)
    f = db.query(FanArrangement).filter(FanArrangement.project_order_id == po.id).first()
    d = fan_to_dict(f) if f else get_fan(order_id, db)
    sp = d.get("spec_json") or {}
    M = _mode(format, mode)
    F = lambda k, v=None, block=False: ef(M, k, get_path(d, k) if v is None else v, block)

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
        + (PRINT_BAR if M != "edit" else '')
        + '<div style="font-size:17px;font-weight:bold;text-align:center;letter-spacing:6px;'
          'margin-bottom:8px">注 文 確 認 書</div>'
        + '<table style="margin-bottom:6px">'
        + '<tr><td width="316" rowspan="2" style="border:none;vertical-align:top">'
          + F('vendor_name') + ' 御中<br>' + F('vendor_contact') + ' 様</td>'
        + '<td width="64" ' + L + '>受注No.</td>'
          '<td width="130" style="color:#c00;font-weight:bold">' + F('order_no') + '</td></tr>'
        + '<tr><td ' + L + '>御確認印</td><td style="height:38px">&nbsp;</td></tr></table>'
        + '<div style="font-size:10px;margin:6px 0">'
          'このたびはご注文を頂きありがとうございます。<br>'
          '下記内容をご確認の上、捺印後折り返しFAXにてご返送下さいますようお願い致します。</div>'
        + '<table style="margin-bottom:6px">'
        + hdr('ユーザー名', F('user_name') + ' 様　' + F('user_plant'),
              'ご担当者', F('user_contact') + ' 様')
        + hdr('住所', F('user_address'), 'TEL', F('user_tel'))
        + hdr('出荷先', F('ship_to_name') + ' 様　' + F('ship_to_plant'),
              'ご担当者', F('ship_to_contact') + ' 様')
        + hdr('住所', F('ship_to_address'), 'TEL', F('ship_to_tel'))
        + hdr('出荷日', F('ship_date'), '運送方法', F('transport_method'))
        + '</table>'
        + '<div style="font-size:9px;margin-bottom:6px">'
          '【引取：貴社手配のトラックにてお引取／パレット：宅配にてパレット梱包出荷／工事：井上工事】</div>'
        + '<table style="margin-bottom:6px">'
        + spec('名称', F('product_name'), '駆動方式', F('drive_type'),
               '製造No.', F('serial_no'))
        + spec('型式', F('model'), '周波数', F('spec_json.frequency') + ' Hz',
               '動力', F('spec_json.voltage') + ' V')
        + spec('ﾓｰﾀ',
               F('spec_json.motor_kw') + ' kW　' + F('spec_json.motor_pole') + ' P　'
               + F('spec_json.motor_type'),
               'ﾒｰｶ', F('spec_json.motor_maker'), '備考', F('spec_json.motor_note'))
        + spec_wide('仕様', F('spec_json.spec_place') + '（屋内 / 屋外）※ご確認ください')
        + spec_wide('吸排気口',
                    '吸 φ' + F('spec_json.intake_dia') + '　' + F('spec_json.intake_flange')
                    + '　／　排 φ' + F('spec_json.exhaust_dia') + '　'
                    + F('spec_json.exhaust_flange'))
        + spec_wide('ｽｲｯﾁ',
                    F('spec_json.switch_type') + '　制御盤：' + F('spec_json.control_panel')
                    + '<br><span style="font-size:9px">※必要の有無を記載願います。'
                      'なお、電気配線工事は含んでいません。</span>')
        + spec('指定色', F('spec_json.paint_color'), '色番号', F('spec_json.color_no'), '&nbsp;', '&nbsp;')
        + spec_wide('備考', F('notes', block=True))
        + '</table>'
        + '<div style="font-size:9px">※印箇所ご確認・ご指示願います。</div>'
        + '<table style="margin-top:8px"><tr>'
          '<td width="316" style="border:none">&nbsp;</td>'
          '<td width="56" ' + L + '>営業</td>'
          '<td width="66">' + F('sales_person_name') + '</td>'
          '<td width="36" ' + L + '>作成</td>'
          '<td width="66">' + F('creator_name') + '</td></tr></table>'
        + '</body></html>'
    )
    if M == "edit":
        html = _inject(html, "fan", order_id, "排風機 注文確認書", db, pdf_path="pdf", rows=False, extra="")
    return form_response(html, "%s_排風機注文確認書" % (d.get('order_no') or po.child_no),
                         M == "pdf")


@router.get("/fan/{order_id}/instruction-pdf")
def fan_instruction_pdf(order_id: str, format: str = "html", mode: str = "", db: Session = Depends(get_db)):
    """ファン作業指示書（社内の製造指示）"""
    po = find_order(order_id, db)
    f = db.query(FanArrangement).filter(FanArrangement.project_order_id == po.id).first()
    d = fan_to_dict(f) if f else get_fan(order_id, db)
    sp = d.get("spec_json") or {}
    ins = d.get("instruction_json") or {}
    M = _mode(format, mode)
    F = lambda k, v=None, block=False: ef(M, k, get_path(d, k) if v is None else v, block)

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
        + (PRINT_BAR if M != "edit" else '')
        + '<table style="margin-bottom:6px">'
        + '<tr><td width="316" rowspan="2" style="border:none;font-size:16px;font-weight:bold;'
          'letter-spacing:4px;vertical-align:top">フ ァ ン 作 業 指 示 書</td>'
        + '<td width="64" ' + L + '>営業担当</td>'
          '<td width="130">' + F('sales_person_name') + '</td></tr>'
        + '<tr><td ' + L + '>作成</td><td>' + F('creator_name') + '</td></tr></table>'
        + '<table style="margin-bottom:6px">'
        + r4('型式', F('model'), '製造番号', F('serial_no'))
        + r4('御注文主', F('instruction_json.order_customer') + ' 殿', '受注番号',
             '<span style="color:#c00;font-weight:bold">' + F('order_no') + '</span>')
        + r4('納入先', F('ship_to_name') + ' ' + F('ship_to_plant') + ' 殿',
             '用途・仕様', F('instruction_json.usage_spec'))
        + r4('出荷日', F('ship_date'), '出荷方法', F('transport_method'))
        + '</table>'
        + '<table style="margin-bottom:6px">'
        + r4wide('ﾓｰﾀ',
                 F('spec_json.motor_kw') + ' kW　' + F('spec_json.motor_pole') + ' P　'
                 + F('spec_json.frequency') + ' Hz　' + F('spec_json.voltage') + ' V　'
                 + F('spec_json.motor_type') + '　' + F('spec_json.motor_maker'))
        + r4('軸受', '羽根側：' + F('instruction_json.bearing_fan'),
             'ﾌﾟｰﾘ側', F('instruction_json.bearing_pulley'))
        + r4('ﾓｰﾀ側ﾌﾟｰﾘ', F('instruction_json.motor_pulley'), 'Vﾍﾞﾙﾄ', F('instruction_json.belt'))
        + r4('ﾌｧﾝ側ﾌﾟｰﾘ', F('instruction_json.fan_pulley'), '回転数', F('instruction_json.rpm') + ' rpm')
        + r4('ｶﾊﾞｰ', F('instruction_json.cover'), '吸口',
             'φ' + F('spec_json.intake_dia') + '　' + F('spec_json.intake_flange'))
        + r4('点検口', F('instruction_json.inspection_port'), '出口',
             'φ' + F('spec_json.exhaust_dia') + '　' + F('spec_json.exhaust_flange'))
        + r4('架台', F('instruction_json.frame'), '塗装色',
             F('instruction_json.paint', _pick(ins.get('paint'), sp.get('paint_color'))))
        + r4wide('備考', F('notes', block=True))
        + '</table>'
        + '<div style="font-size:11px;font-weight:bold;margin:8px 0 4px">想定性能</div>'
        + '<table style="margin-bottom:6px">'
        + r6('圧力', F('instruction_json.pressure') + ' mmaq', '風量',
             F('instruction_json.airflow') + ' ㎥/min', '電流', F('instruction_json.current') + ' A')
        + '</table>'
        + '<div style="font-size:11px;font-weight:bold;margin:8px 0 4px">出荷時チェックリスト</div>'
        + '<table>'
        + r6('検査者', '&nbsp;', '日付', '&nbsp;', '判定', '&nbsp;', ' style="height:22px"')
        + r6('電流値', '&nbsp;', '外観', '&nbsp;', '回転方向', '&nbsp;', ' style="height:22px"')
        + r6('異音', '&nbsp;', '振動値', '&nbsp;', '&nbsp;', '&nbsp;', ' style="height:22px"')
        + '</table>'
        + '</body></html>'
    )
    if M == "edit":
        html = _inject(html, "fan", order_id, "ファン作業指示書", db, pdf_path="instruction-pdf", rows=False, extra="")
    return form_response(html, "%s_ファン作業指示書" % (d.get('order_no') or po.child_no),
                         M == "pdf")


# =============================================
# 宿泊予約票
# =============================================
@router.get("/hotel/{order_id}")
def get_hotel(order_id: str, db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    h = db.query(HotelArrangement).filter(HotelArrangement.project_order_id == po.id).first()
    if not h:
        ctx = _order_context(po, db)
        return {
            "id": None, "child_no": po.child_no,
            "site_name": ctx["site_name"], "site_address": ctx["site_address"],
            "items_json": [], "notes": '',
            "_autofilled": True,
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
def hotel_pdf(order_id: str, format: str = "html", mode: str = "", db: Session = Depends(get_db)):
    po = find_order(order_id, db)
    h = db.query(HotelArrangement).filter(HotelArrangement.project_order_id == po.id).first()
    d = hotel_to_dict(h) if h else get_hotel(order_id, db)
    M = _mode(format, mode)
    F = lambda k, v=None, block=False: ef(M, k, get_path(d, k) if v is None else v, block)

    rows = ''
    for i, it in enumerate(d.get("items_json") or []):
        c = lambda k: ef(M, 'items_json.%d.%s' % (i, k), it.get(k))
        rows += (
            '<tr><td>' + c('hotel') + '</td><td>' + c('tel') + '</td>'
            '<td>' + c('checkin') + '</td><td>' + c('checkout') + '</td>'
            '<td style="text-align:center">' + c('nights') + '</td>'
            '<td style="text-align:center">' + c('persons') + '</td>'
            '<td style="text-align:right">' + c('price') + '</td>'
            '<td>' + c('guests') + '</td><td>' + c('note') + '</td>'
            + ('<td class="ef-rowop"><button onclick="efDelRow(%d)">削除</button></td>' % i
               if M == "edit" else '') + '</tr>'
        )
    if not rows:
        rows = '<tr><td colspan="9" style="color:#999;text-align:center">明細がありません</td></tr>'

    html = (
        '<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">'
        '<title>宿泊予約票</title><style>' + BASE_STYLE + '</style></head><body>'
        + (PRINT_BAR if M != "edit" else '')
        + '<h2 style="font-size:16px;font-weight:bold;margin-bottom:4px">宿泊予約票</h2>'
        + '<p style="font-size:9px;color:#666;margin-bottom:10px">'
        + '※基本は朝食なしで！変更・キャンセルは必ず宿へ連絡！予約したら旅費の領収書を忘れずに！</p>'
        + '<table style="margin-bottom:8px"><tr>'
        + '<td width="70" style="background:#f0f0f0">現場</td><td>' + F('site_name') + '</td>'
        + '<td width="70" style="background:#f0f0f0">受注番号</td><td>' + esc(d.get('child_no')) + '</td></tr>'
        + '<tr><td style="background:#f0f0f0">住所</td><td colspan="3">' + F('site_address') + '</td></tr></table>'
        + '<table><thead><tr>'
        + '<th>ホテル名</th><th style="width:90px">TEL</th><th style="width:60px">IN</th>'
        + '<th style="width:60px">OUT</th><th style="width:30px">泊</th><th style="width:30px">人</th>'
        + '<th style="width:60px">値段/泊</th><th>宿泊者</th><th>備考</th></tr></thead>'
        + '<tbody>' + rows + '</tbody></table>'
        + ('<div style="margin-top:8px;font-size:10px">備考：' + F('notes', block=True) + '</div>'
           if (d.get('notes') or M == "edit") else '')
        + COMPANY_FOOTER + '</body></html>'
    )
    if M == "edit":
        html = _inject(html, "hotel", order_id, "宿泊予約票", db, rows=True)
    return form_response(html, "%s_宿泊予約票" % po.child_no, M == "pdf")



# =============================================
# 帳票画面での編集（?mode=edit）
# =============================================
def _mode(fmt, mode):
    """表示モード。PDF出力 / 印刷プレビュー / 帳票画面での編集"""
    if fmt == "pdf":
        return "pdf"
    return "edit" if mode == "edit" else "view"


def _rowop(i):
    return ('<div class="ef-rowop"><button onclick="efDelRow(%d)">%d件目の明細を削除</button></div>'
            % (i, i + 1))


# 業者マスタから選べる帳票と、マスタ項目→帳票項目の対応
VENDOR_CFG = {
    "crane": ("クレーン・作業車", {"vendor_name": "name", "vendor_branch": "branch",
                              "vendor_contact": "contact_person", "vendor_tel": "phone",
                              "vendor_fax": "fax"}),
    "shipping": ("運送（トラック）", {"carrier_name": "name", "carrier_contact": "contact_person",
                                "carrier_tel": "phone", "carrier_fax": "fax"}),
    "fan": ("排風機", {"vendor_name": "name", "vendor_contact": "contact_person"}),
}


def _inject(html, kind, order_id, title, db, pdf_path="pdf", rows=False, extra=""):
    oid = quote(str(order_id), safe="")
    base = "/api/arrangements/%s/%s" % (kind, oid)
    vendors = vmap = None
    if kind in VENDOR_CFG:
        cat, vmap = VENDOR_CFG[kind]
        vendors = [_vendor_dict(v) for v in
                   db.query(ArrangementVendor).filter(ArrangementVendor.category == cat)
                     .order_by(ArrangementVendor.name).limit(300).all()]
    btns = ('<button class="w" onclick="efOp({add_row:true})">明細を追加</button>' if rows else '') + extra
    if kind == "fan":
        # 注文確認書と作業指示書は同じデータ。画面を行き来しても入力は共有される
        other = "instruction-pdf" if pdf_path == "pdf" else "pdf"
        other_name = "ファン作業指示書" if pdf_path == "pdf" else "注文確認書"
        btns += ('<button class="g" onclick="efSave().then(function(ok){if(ok)location.href=\'%s/%s?mode=edit\'})">'
                 '%sの画面へ</button>' % (base, other, other_name))
        btns += ('<button class="p" onclick="efPdf2(\'%s/%s?format=pdf\')">保存して%sのPDF</button>'
                 % (base, other, other_name))
    return inject_edit(html, title=title, save_url=base + "/edit-save",
                       pdf_url=base + "/%s?format=pdf" % pdf_path,
                       extra_buttons=btns, vendors=vendors, vendor_map=vmap)


EDIT_KINDS = {
    "crane":    (CraneArrangement, "get_crane", CraneData, crane_to_dict, [("issue_date", "作成日")]),
    "shipping": (ShippingArrangement, "get_shipping", ShippingData, shipping_to_dict, [("issue_date", "作成日")]),
    "fan":      (FanArrangement, "get_fan", FanData, fan_to_dict, [("ship_date", "出荷日")]),
    "hotel":    (HotelArrangement, "get_hotel", HotelData, hotel_to_dict, []),
}


@router.post("/{kind}/{order_id}/edit-save")
def edit_save(kind: str, order_id: str, body: dict, db: Session = Depends(get_db)):
    """帳票画面で書き換えた内容を保存する。

    画面に出ている項目だけが送られてくるので、既存の値（未保存なら自動補完の値）に
    上書きマージする。画面に出ていない項目は消さない。
    """
    if kind not in EDIT_KINDS:
        raise HTTPException(404, "帳票の種類が正しくありません")
    Model, getter, Schema, to_dict, date_fields = EDIT_KINDS[kind]
    po = find_order(order_id, db)
    rec = db.query(Model).filter(Model.project_order_id == po.id).first()
    base = to_dict(rec) if rec else globals()[getter](order_id, db)
    data = apply_fields(base, (body or {}).get("fields") or {})
    data = apply_row_op(data, (body or {}).get("op"))
    for f, label in date_fields:
        try:
            v = parse_date(data.get(f), label)
        except ValueError as e:
            raise HTTPException(400, str(e))
        data[f] = v.isoformat() if v else None
    allowed = set(Schema.model_fields)
    obj = Schema(**{k: v for k, v in data.items() if k in allowed})
    if not rec:
        rec = Model(project_order_id=po.id, child_no=po.child_no)
        db.add(rec)
    for k, v in obj.model_dump(exclude_unset=True).items():
        setattr(rec, k, v)
    db.commit()
    return {"ok": True, "items": len(data.get("items_json") or [])}


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
    from app.db.models import Base, engine, FanArrangement, FormDocument
    Base.metadata.create_all(bind=engine, tables=[FanArrangement.__table__, FormDocument.__table__])
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
