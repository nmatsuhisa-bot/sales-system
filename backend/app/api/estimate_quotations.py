"""見積書 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime
import io, uuid

from app.db.models import (
    get_db, QuotationHeader, QuotationLineItem, QuotationLaborDetail,
    OrderTicket, ProjectOrder, Project,
    EstimateBfrBody, EstimateBfrFan, EstimateBfrRv,
    EstimateScaBody, EstimatePlFan, EstimateCyclone, EstimateLaborItem
)

router = APIRouter()

# =============================================
# 見積パターンマスタ取得
# =============================================
@router.get("/patterns/bfr-bodies")
def get_bfr_bodies(db: Session = Depends(get_db)):
    items = db.query(EstimateBfrBody).filter(EstimateBfrBody.is_active == True).order_by(EstimateBfrBody.model_code).all()
    result = {}
    for i in items:
        key = i.model_code
        if key not in result:
            result[key] = {"model_code": key, "airflow": i.airflow, "filter_length": i.filter_length, "variants": []}
        result[key]["variants"].append({
            "id": str(i.id), "filter_type": i.filter_type,
            "base_price": int(i.base_price or 0), "filter_price": int(i.filter_price or 0),
            "filter_count": i.filter_count
        })
    return list(result.values())

@router.get("/patterns/bfr-fans/{bfr_model}")
def get_bfr_fans(bfr_model: str, db: Session = Depends(get_db)):
    items = db.query(EstimateBfrFan).filter(EstimateBfrFan.bfr_model == bfr_model, EstimateBfrFan.is_active == True).all()
    return [{"id": str(i.id), "fan_model": i.fan_model, "price": int(i.price or 0), "quantity": i.quantity} for i in items]

@router.get("/patterns/bfr-rvs/{bfr_model}")
def get_bfr_rvs(bfr_model: str, db: Session = Depends(get_db)):
    items = db.query(EstimateBfrRv).filter(EstimateBfrRv.bfr_model == bfr_model, EstimateBfrRv.is_active == True).all()
    return [{"id": str(i.id), "rv_model": i.rv_model, "kw": float(i.kw or 0), "price": int(i.price or 0), "quantity": i.quantity} for i in items]

@router.get("/patterns/sca-bodies")
def get_sca_bodies(db: Session = Depends(get_db)):
    items = db.query(EstimateScaBody).filter(EstimateScaBody.is_active == True).order_by(EstimateScaBody.model_code).all()
    return [{
        "id": str(i.id), "model_code": i.model_code, "diameter": i.diameter,
        "capacity": float(i.capacity or 0), "base_price": int(i.base_price or 0),
        "ab_kw": float(i.ab_kw or 0), "sc_count": i.sc_count,
        "sc1_kw": float(i.sc1_kw or 0), "rv1_model": i.rv1_model,
        "rv1_kw": float(i.rv1_kw or 0), "slope_sc": i.slope_sc
    } for i in items]

@router.get("/patterns/pl-fans")
def get_pl_fans(db: Session = Depends(get_db)):
    items = db.query(EstimatePlFan).filter(EstimatePlFan.is_active == True).order_by(EstimatePlFan.model_code, EstimatePlFan.kw).all()
    return [{"id": str(i.id), "model_code": i.model_code, "kw": float(i.kw or 0), "price": int(i.price or 0)} for i in items]

@router.get("/patterns/cyclones")
def get_cyclones(db: Session = Depends(get_db)):
    items = db.query(EstimateCyclone).filter(EstimateCyclone.is_active == True).all()
    return [{"id": str(i.id), "model_code": i.model_code, "shape": i.shape, "material": i.material, "price": int(i.price or 0)} for i in items]

@router.get("/labor-items")
def get_labor_items(db: Session = Depends(get_db)):
    items = db.query(EstimateLaborItem).filter(EstimateLaborItem.is_active == True).order_by(EstimateLaborItem.sort_order).all()
    return [{
        "id": str(i.id), "category": i.category, "item_name": i.item_name,
        "unit": i.unit, "unit_price": int(i.unit_price or 0)
    } for i in items]

# =============================================
# 見積書 CRUD
# =============================================
class LaborDetailIn(BaseModel):
    labor_item_id: Optional[str] = None
    item_name: str
    quantity: float = 0
    unit: str = '人日'
    unit_price: int = 0
    crane_type: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0

class LineItemIn(BaseModel):
    line_no: int
    section: Optional[str] = None
    sub_section: Optional[str] = None
    item_name: str
    spec_detail: Optional[str] = None
    quantity: float = 1
    unit: str = '式'
    unit_price: int = 0
    product_type: Optional[str] = None
    spec_json: Optional[dict] = None

class QuotationHeaderCreate(BaseModel):
    project_order_id: Optional[str] = None
    child_no: Optional[str] = None
    customer_name: Optional[str] = None
    delivery_name: Optional[str] = None
    title: Optional[str] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    valid_until: Optional[date] = None
    issue_date: Optional[date] = None
    sales_person_name: Optional[str] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    line_items: List[LineItemIn] = []
    labor_details: List[LaborDetailIn] = []

def _gen_quotation_no(db: Session) -> str:
    year = datetime.now().year
    prefix = f"Q{year}-"
    last = db.query(QuotationHeader).filter(QuotationHeader.quotation_no.like(f"{prefix}%")).order_by(desc(QuotationHeader.quotation_no)).first()
    seq = int(last.quotation_no.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"

def _calc_totals(line_items, labor_details):
    subtotal = sum(int(i.unit_price * i.quantity) for i in line_items)
    labor_total = sum(int(l.unit_price * l.quantity) for l in labor_details)
    total_before_tax = subtotal + labor_total
    tax = int(total_before_tax * 0.1)
    return subtotal, labor_total, tax, total_before_tax + tax

def _q_to_dict(q: QuotationHeader) -> dict:
    return {
        "id": str(q.id), "quotation_no": q.quotation_no,
        "project_order_id": str(q.project_order_id) if q.project_order_id else None,
        "child_no": q.child_no, "customer_name": q.customer_name,
        "delivery_name": q.delivery_name, "title": q.title,
        "delivery_terms": q.delivery_terms, "payment_terms": q.payment_terms,
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "issue_date": q.issue_date.isoformat() if q.issue_date else None,
        "sales_person_name": q.sales_person_name,
        "subtotal": int(q.subtotal or 0), "tax_rate": float(q.tax_rate or 10),
        "tax_amount": int(q.tax_amount or 0), "total_amount": int(q.total_amount or 0),
        "labor_total": int(q.labor_total or 0), "status": q.status,
        "notes": q.notes, "internal_notes": q.internal_notes,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "line_items": sorted([{
            "id": str(i.id), "line_no": i.line_no, "section": i.section,
            "sub_section": i.sub_section, "item_name": i.item_name,
            "spec_detail": i.spec_detail, "quantity": float(i.quantity or 1),
            "unit": i.unit, "unit_price": int(i.unit_price or 0),
            "amount": int(i.amount or 0), "product_type": i.product_type,
            "spec_json": i.spec_json
        } for i in q.line_items], key=lambda x: x["line_no"]),
        "labor_details": sorted([{
            "id": str(l.id), "item_name": l.item_name,
            "quantity": float(l.quantity or 0), "unit": l.unit,
            "unit_price": int(l.unit_price or 0), "amount": int(l.amount or 0),
            "crane_type": l.crane_type, "notes": l.notes, "sort_order": l.sort_order
        } for l in q.labor_details], key=lambda x: x["sort_order"])
    }

@router.get("/")
def list_quotations(
    child_no: Optional[str] = None, project_order_id: Optional[str] = None,
    page: int = Query(1, ge=1), per_page: int = Query(20),
    db: Session = Depends(get_db)
):
    q = db.query(QuotationHeader).options(joinedload(QuotationHeader.line_items), joinedload(QuotationHeader.labor_details))
    if child_no: q = q.filter(QuotationHeader.child_no == child_no)
    if project_order_id: q = q.filter(QuotationHeader.project_order_id == project_order_id)
    total = q.count()
    items = q.order_by(desc(QuotationHeader.created_at)).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "items": [_q_to_dict(i) for i in items]}

@router.post("/", status_code=201)
def create_quotation(data: QuotationHeaderCreate, db: Session = Depends(get_db)):
    subtotal, labor_total, tax, total = _calc_totals(data.line_items, data.labor_details)

    # 子IDから案件情報を自動参照
    customer_name = data.customer_name
    delivery_name = data.delivery_name
    sales_person_name = data.sales_person_name
    title = data.title
    if data.project_order_id:
        po = db.query(ProjectOrder).filter(ProjectOrder.id == data.project_order_id).first()
        if po:
            customer_name = customer_name or po.customer_name or po.agency_name
            delivery_name = delivery_name or po.customer_name
            sales_person_name = sales_person_name or po.sales_person_name
            title = title or po.project_name

    q = QuotationHeader(
        quotation_no=_gen_quotation_no(db),
        project_order_id=data.project_order_id,
        child_no=data.child_no,
        customer_name=customer_name, delivery_name=delivery_name,
        title=title, delivery_terms=data.delivery_terms,
        payment_terms=data.payment_terms, valid_until=data.valid_until,
        issue_date=data.issue_date or date.today(),
        sales_person_name=sales_person_name,
        subtotal=subtotal, tax_amount=tax, total_amount=total, labor_total=labor_total,
        notes=data.notes, internal_notes=data.internal_notes,
    )
    db.add(q)
    db.flush()

    for item in data.line_items:
        db.add(QuotationLineItem(
            quotation_id=q.id, line_no=item.line_no, section=item.section,
            sub_section=item.sub_section, item_name=item.item_name,
            spec_detail=item.spec_detail, quantity=item.quantity, unit=item.unit,
            unit_price=item.unit_price, amount=int(item.unit_price * item.quantity),
            product_type=item.product_type, spec_json=item.spec_json
        ))

    for labor in data.labor_details:
        db.add(QuotationLaborDetail(
            quotation_id=q.id, labor_item_id=labor.labor_item_id,
            item_name=labor.item_name, quantity=labor.quantity, unit=labor.unit,
            unit_price=labor.unit_price, amount=int(labor.unit_price * labor.quantity),
            crane_type=labor.crane_type, notes=labor.notes, sort_order=labor.sort_order
        ))

    db.commit()
    db.refresh(q)
    return _q_to_dict(q)

@router.get("/{quotation_id}")
def get_quotation(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items), joinedload(QuotationHeader.labor_details)
    ).filter(or_(QuotationHeader.id == quotation_id, QuotationHeader.quotation_no == quotation_id)).first()
    if not q: raise HTTPException(404)
    return _q_to_dict(q)

@router.put("/{quotation_id}")
def update_quotation(quotation_id: str, data: QuotationHeaderCreate, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)
    subtotal, labor_total, tax, total = _calc_totals(data.line_items, data.labor_details)
    for k, v in data.dict(exclude={"line_items", "labor_details"}, exclude_none=True).items():
        setattr(q, k, v)
    q.subtotal = subtotal; q.labor_total = labor_total; q.tax_amount = tax; q.total_amount = total
    for i in q.line_items: db.delete(i)
    for l in q.labor_details: db.delete(l)
    db.flush()
    for item in data.line_items:
        db.add(QuotationLineItem(
            quotation_id=q.id, line_no=item.line_no, section=item.section,
            sub_section=item.sub_section, item_name=item.item_name,
            spec_detail=item.spec_detail, quantity=item.quantity, unit=item.unit,
            unit_price=item.unit_price, amount=int(item.unit_price * item.quantity),
            product_type=item.product_type, spec_json=item.spec_json
        ))
    for labor in data.labor_details:
        db.add(QuotationLaborDetail(
            quotation_id=q.id, labor_item_id=labor.labor_item_id,
            item_name=labor.item_name, quantity=labor.quantity, unit=labor.unit,
            unit_price=labor.unit_price, amount=int(labor.unit_price * labor.quantity),
            crane_type=labor.crane_type, notes=labor.notes, sort_order=labor.sort_order
        ))
    db.commit(); db.refresh(q)
    return _q_to_dict(q)

@router.delete("/{quotation_id}", status_code=204)
def delete_quotation(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)
    db.delete(q); db.commit()

# =============================================
# PDF出力（ケイテック形式）
# =============================================
@router.get("/{quotation_id}/pdf")
def export_pdf(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items), joinedload(QuotationHeader.labor_details)
    ).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)

    html = _build_quotation_html(q)
    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")),
        media_type="text/html",
        headers={"Content-Disposition": f"inline; filename={q.quotation_no}.html"}
    )

def _build_quotation_html(q: QuotationHeader) -> str:
    items_html = ""
    sections = {}
    for item in sorted(q.line_items, key=lambda x: x.line_no):
        sec = item.section or ""
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(item)

    line_no = 1
    for sec, items in sections.items():
        sec_total = sum(int(i.amount or 0) for i in items)
        for item in items:
            items_html += f"""
            <tr>
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{line_no}</td>
                <td style="border:1px solid #ccc;padding:4px 8px">{item.item_name}</td>
                <td style="border:1px solid #ccc;padding:4px 8px;font-size:11px;white-space:pre-wrap">{item.spec_detail or ''}</td>
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{int(item.quantity or 1)}</td>
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{item.unit or '式'}</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">{"　" if not item.unit_price else f"¥{int(item.unit_price):,}"}</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">¥{int(item.amount or 0):,}</td>
            </tr>"""
            line_no += 1
        if sec:
            items_html += f"""
            <tr style="background:#f5f5f5;font-weight:bold">
                <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:4px 8px">{sec} 小計金額</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">¥{sec_total:,}</td>
            </tr>"""

    # 工数明細
    labor_html = ""
    if q.labor_details:
        labor_html = """<div style="margin-top:20px;page-break-before:always">
        <h3 style="font-size:14px">■ 社内工数内訳</h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px">
        <tr style="background:#f0f0f0">
            <th style="border:1px solid #ccc;padding:4px 8px">作業項目</th>
            <th style="border:1px solid #ccc;padding:4px 8px;width:80px">数量</th>
            <th style="border:1px solid #ccc;padding:4px 8px;width:60px">単位</th>
            <th style="border:1px solid #ccc;padding:4px 8px;width:100px">単価</th>
            <th style="border:1px solid #ccc;padding:4px 8px;width:120px">金額</th>
        </tr>"""
        for l in sorted(q.labor_details, key=lambda x: x.sort_order):
            labor_html += f"""<tr>
                <td style="border:1px solid #ccc;padding:4px 8px">{l.item_name}{f' ({l.crane_type})' if l.crane_type else ''}</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">{float(l.quantity or 0)}</td>
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{l.unit}</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">¥{int(l.unit_price or 0):,}</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">¥{int(l.amount or 0):,}</td>
            </tr>"""
        labor_html += f"""<tr style="font-weight:bold;background:#f5f5f5">
            <td colspan="4" style="text-align:right;border:1px solid #ccc;padding:4px 8px">工数合計</td>
            <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">¥{int(q.labor_total or 0):,}</td>
        </tr></table></div>"""

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{q.quotation_no} 御見積書</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; margin:20px; font-size:12px; }}
  @media print {{ .no-print{{ display:none }} body{{margin:10mm}} }}
  .header-table td {{ padding: 4px 8px; }}
</style>
</head><body>
<div class="no-print" style="background:#e0f2fe;padding:10px;margin-bottom:15px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px">🖨️ PDF印刷</button>
  <span style="margin-left:15px;font-size:12px;color:#555">印刷ダイアログで「PDFに保存」を選択してください</span>
</div>

<!-- 1枚目: ヘッダー -->
<div style="text-align:right;margin-bottom:8px">No. {q.quotation_no}</div>
<div style="text-align:right;margin-bottom:4px">日付　{q.issue_date or '　　　　'}</div>

<h1 style="text-align:center;font-size:24px;margin:10px 0;letter-spacing:8px">御　見　積　書</h1>

<table style="width:100%;margin-bottom:15px" cellspacing="0">
  <tr>
    <td style="width:55%;vertical-align:bottom">
      <div style="font-size:18px;font-weight:bold;border-bottom:2px solid #000;padding-bottom:4px">
        {q.customer_name or '　'} &nbsp; 殿
      </div>
      <div style="margin-top:6px;font-size:12px">納入先: {q.delivery_name or '　'}</div>
    </td>
    <td style="width:45%;vertical-align:top;padding-left:20px">
      <table cellspacing="0" style="font-size:11px">
        <tr><td colspan="2" style="font-size:18px;font-weight:bold">合計金額 ￥&nbsp;
          <span style="font-size:22px">{int(q.total_amount or 0):,}</span>
        </td></tr>
        <tr><td style="color:#888">（消費税込み）</td></tr>
        <tr><td colspan="2" style="padding-top:8px">
          <table style="font-size:11px;border-collapse:collapse;width:100%">
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">納入期限</td><td style="border:1px solid #ccc;padding:3px 8px">{q.delivery_terms or '　'}</td></tr>
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">受渡場所</td><td style="border:1px solid #ccc;padding:3px 8px">{q.delivery_name or '　'}</td></tr>
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">見積有効期限</td><td style="border:1px solid #ccc;padding:3px 8px">{q.valid_until or '　'}</td></tr>
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">御支払条件</td><td style="border:1px solid #ccc;padding:3px 8px">{q.payment_terms or '　'}</td></tr>
          </table>
        </td></tr>
      </table>
    </td>
  </tr>
</table>

<table style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:12px">
  <tr style="border-bottom:1px solid #000">
    <td style="width:50%;padding:4px">件名: {q.title or '　'}</td>
    <td style="width:50%;text-align:right;padding:4px">
      担当: {q.sales_person_name or '　'}
    </td>
  </tr>
</table>

<!-- 金額サマリ（1枚目） -->
<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:20px">
<thead>
  <tr style="background:#2c3e50;color:#fff">
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:center;width:40px">番号</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:left">品名・仕様</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:left;width:200px">詳細</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:center;width:50px">数量</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:center;width:40px">単位</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:right;width:110px">単価</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:right;width:120px">金額</th>
  </tr>
</thead>
<tbody>
{items_html}
</tbody>
<tfoot>
  <tr style="font-weight:bold">
    <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:5px 8px">小計</td>
    <td style="text-align:right;border:1px solid #ccc;padding:5px 8px">¥{int(q.subtotal or 0):,}</td>
  </tr>
  <tr style="font-weight:bold">
    <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:5px 8px">工事工数</td>
    <td style="text-align:right;border:1px solid #ccc;padding:5px 8px">¥{int(q.labor_total or 0):,}</td>
  </tr>
  <tr style="font-weight:bold">
    <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:5px 8px">消費税（{int(q.tax_rate or 10)}%）</td>
    <td style="text-align:right;border:1px solid #ccc;padding:5px 8px">¥{int(q.tax_amount or 0):,}</td>
  </tr>
  <tr style="font-weight:bold;background:#fff9c4;font-size:14px">
    <td colspan="6" style="text-align:right;border:2px solid #000;padding:6px 8px">合計金額</td>
    <td style="text-align:right;border:2px solid #000;padding:6px 8px">¥{int(q.total_amount or 0):,}</td>
  </tr>
</tfoot>
</table>

{labor_html}

<!-- 会社情報フッター -->
<div style="margin-top:30px;border:2px solid #000;padding:10px;display:flex;align-items:center">
  <div style="font-size:22px;font-weight:bold;margin-right:20px">井上電設株式会社</div>
  <div style="font-size:11px;color:#333">
    〒460-0022 名古屋市中区金山四丁目3番17号<br>
    TEL (052) 322-5271　FAX (052) 332-5273<br>
    E-mail: tech@inoue-d.co.jp
  </div>
  <div style="margin-left:auto;font-size:11px">
    担当: {q.sales_person_name or '　'}<br>
    作成: 　　　　<br>
    検印: 　　　　
  </div>
</div>
</body></html>"""


# =============================================
# 受注票発行
# =============================================
@router.post("/{quotation_id}/issue-order-ticket")
def issue_order_ticket(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)

    total = int(q.total_amount or 0)
    ticket_type = "koban" if total >= 1000000 else "tanban"

    year = datetime.now().year
    prefix = f"OT{year}-"
    last = db.query(OrderTicket).filter(OrderTicket.ticket_no.like(f"{prefix}%")).order_by(desc(OrderTicket.ticket_no)).first()
    seq = int(last.ticket_no.split("-")[-1]) + 1 if last else 1
    ticket_no = f"{prefix}{seq:04d}"

    ticket = OrderTicket(
        ticket_no=ticket_no, ticket_type=ticket_type,
        project_order_id=q.project_order_id, child_no=q.child_no,
        quotation_id=q.id, total_amount=total,
        customer_name=q.customer_name, delivery_name=q.delivery_name,
        sales_person_name=q.sales_person_name, order_date=date.today(),
    )
    db.add(ticket); db.commit(); db.refresh(ticket)
    return {"ticket_no": ticket_no, "ticket_type": ticket_type, "id": str(ticket.id)}


@router.get("/order-ticket/{ticket_id}/pdf")
def order_ticket_pdf(ticket_id: str, db: Session = Depends(get_db)):
    t = db.query(OrderTicket).options(
        joinedload(OrderTicket.quotation).joinedload(QuotationHeader.line_items)
    ).filter(or_(OrderTicket.id == ticket_id, OrderTicket.ticket_no == ticket_id)).first()
    if not t: raise HTTPException(404)

    q = t.quotation
    is_koban = t.ticket_type == "koban"
    title = "受 注 票【工番】" if is_koban else "受 注 票【単番】"

    items_html = ""
    if q:
        for i, item in enumerate(sorted(q.line_items, key=lambda x: x.line_no), 1):
            items_html += f"""<tr>
                <td style="border:1px solid #999;padding:3px 6px">{item.item_name}</td>
                <td style="border:1px solid #999;padding:3px 6px;font-size:10px">{item.spec_detail or ''}</td>
                <td style="text-align:center;border:1px solid #999;padding:3px 6px">{int(item.quantity or 1)}</td>
                <td style="text-align:center;border:1px solid #999;padding:3px 6px">{item.unit}</td>
                <td style="text-align:right;border:1px solid #999;padding:3px 6px">¥{int(item.unit_price or 0):,}</td>
                <td style="text-align:right;border:1px solid #999;padding:3px 6px">¥{int(item.amount or 0):,}</td>
            </tr>"""

    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<title>{t.ticket_no} {title}</title>
<style>
  body{{font-family:'Hiragino Sans','Yu Gothic',sans-serif;font-size:11px;margin:15mm}}
  @media print{{.no-print{{display:none}}}}
  table{{border-collapse:collapse;width:100%}}
  th{{background:#eee;border:1px solid #999;padding:4px 6px}}
</style></head><body>
<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<div style="text-align:right">受注NO: <strong>{t.ticket_no}</strong></div>
<h2 style="text-align:center;font-size:18px;border-bottom:2px solid #000;padding-bottom:6px">{title}</h2>

<table style="margin-bottom:12px;font-size:11px" cellspacing="0">
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px;width:100px">受注日</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.order_date or '　'}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px;width:100px">見積書No.</td>
    <td style="border:1px solid #999;padding:4px 8px">{q.quotation_no if q else '　'}</td>
  </tr>
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">ユーザー/納入先</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.delivery_name or '　'}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">売上先</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.customer_name or '　'}</td>
  </tr>
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">担当者</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.sales_person_name or '　'}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">区分</td>
    <td style="border:1px solid #999;padding:4px 8px">{'工番（100万円以上）' if is_koban else '単番（100万円未満）'}</td>
  </tr>
</table>

<table style="margin-bottom:12px;font-size:11px">
  <thead><tr>
    <th style="width:200px">品名・仕様</th>
    <th>詳細</th>
    <th style="width:50px">数量</th>
    <th style="width:40px">単位</th>
    <th style="width:100px">単価</th>
    <th style="width:110px">金額</th>
  </tr></thead>
  <tbody>{items_html}</tbody>
  <tfoot>
    <tr style="font-weight:bold;background:#fff9c4">
      <td colspan="5" style="text-align:right;border:1px solid #999;padding:4px 8px">合計金額</td>
      <td style="text-align:right;border:1px solid #999;padding:4px 8px">¥{int(t.total_amount or 0):,}</td>
    </tr>
  </tfoot>
</table>

{'<div style="border:1px solid #999;padding:8px;margin-top:10px;font-size:10px"><b>前受金</b>：有 ・ 無<br>①（　月　日付）税込/税抜 ¥　　　入金済<br>②（　月　日付）税込/税抜 ¥　　　入金済</div>' if is_koban else ''}

<div style="margin-top:20px;border:1px solid #999;padding:8px;font-size:10px">
  <table style="width:100%"><tr>
    <td>出荷方法: □トラック出荷 □宅配出荷 □井上納品 □引取</td>
    <td style="text-align:right">出荷日: 　　年　　月　　日</td>
  </tr></table>
  <div style="margin-top:6px">図面: 有 ・ 無　　注文書: 有 ・ 無{'　　契約書: 有 ・ 無' if is_koban else ''}</div>
</div>

<table style="margin-top:15px;font-size:10px;width:100%">
  <tr>
    <th style="border:1px solid #999;padding:4px;width:70px">社長</th>
    <th style="border:1px solid #999;padding:4px;width:70px">柴田</th>
    <th style="border:1px solid #999;padding:4px;width:70px">後藤</th>
    <th style="border:1px solid #999;padding:4px;width:70px">江里口</th>
    <th style="border:1px solid #999;padding:4px;width:70px">国立</th>
    <th style="border:1px solid #999;padding:4px;width:70px">担当</th>
  </tr>
  <tr><td style="border:1px solid #999;height:30px"></td><td style="border:1px solid #999"></td><td style="border:1px solid #999"></td><td style="border:1px solid #999"></td><td style="border:1px solid #999"></td><td style="border:1px solid #999"></td></tr>
</table>

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:16px;font-weight:bold">井上電設株式会社</div>
  <div style="margin-left:15px;font-size:10px">〒460-0022 名古屋市中区金山4丁目3-17　TEL(052)322-5271　FAX(052)332-5273</div>
</div>
</body></html>"""

    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename={t.ticket_no}.html"}
    )


# =============================================
# 採用見積を子IDに反映
# =============================================
@router.post("/{quotation_id}/adopt")
def adopt_quotation(quotation_id: str, db: Session = Depends(get_db)):
    """見積を採用として子IDに反映。後から変更可能。"""
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q:
        raise HTTPException(404, "見積が見つかりません")
    if not q.project_order_id:
        raise HTTPException(400, "この見積は子IDに紐付いていません")
    po = db.query(ProjectOrder).filter(ProjectOrder.id == q.project_order_id).first()
    if not po:
        raise HTTPException(404, "子IDが見つかりません")
    po.quotation_id = q.id
    po.quotation_no = q.quotation_no
    po.quotation_total = q.total_amount
    po.quotation_issue_date = q.issue_date
    po.quotation_amount = q.total_amount
    db.commit()
    return {"message": f"見積 {q.quotation_no} を採用しました", "quotation_no": q.quotation_no, "total_amount": int(q.total_amount or 0), "child_no": po.child_no}

@router.delete("/{quotation_id}/adopt")
def unadopt_quotation(quotation_id: str, db: Session = Depends(get_db)):
    """採用見積を解除"""
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q or not q.project_order_id:
        raise HTTPException(404)
    po = db.query(ProjectOrder).filter(ProjectOrder.id == q.project_order_id).first()
    if po and po.quotation_id == q.id:
        po.quotation_id = None
        po.quotation_no = None
        po.quotation_total = None
        po.quotation_issue_date = None
        db.commit()
    return {"message": "採用を解除しました"}
