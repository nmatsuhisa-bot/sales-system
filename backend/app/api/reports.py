"""レポート API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date
from app.db.models import get_db, Project, QuotationHeader, OrderTicket

router = APIRouter()


def _fiscal_range(year: int):
    """会計年度の開始日・終了日を返す（2/21〜翌2/20）"""
    return date(year, 2, 21), date(year + 1, 2, 20)


def _current_fiscal_year(today: date) -> int:
    if today.month > 2 or (today.month == 2 and today.day > 20):
        return today.year
    return today.year - 1


@router.get("/dashboard")
def dashboard(year: int = Query(default=None), db: Session = Depends(get_db)):
    from app.db.models import ProjectOrder

    today = date.today()
    if year is None:
        year = _current_fiscal_year(today)

    fiscal_start, fiscal_end = _fiscal_range(year)
    cur_year = today.year
    cur_month = today.month

    # 案件ステータス集計（全期間）
    project_statuses = db.query(
        Project.status, func.count(Project.id)
    ).group_by(Project.status).all()

    # ステータス別金額（ProjectOrder）
    status_amounts_q = db.query(
        ProjectOrder.status,
        func.sum(func.coalesce(ProjectOrder.quotation_amount, ProjectOrder.quotation_total, 0))
    ).group_by(ProjectOrder.status).all()
    project_status_amounts = {(s or "未設定"): int(a or 0) for s, a in status_amounts_q}

    # 今月の見積件数・金額
    monthly_quotes = db.query(func.count(QuotationHeader.id)).filter(
        extract('year', QuotationHeader.issue_date) == cur_year,
        extract('month', QuotationHeader.issue_date) == cur_month
    ).scalar() or 0

    monthly_quote_amount = db.query(func.sum(QuotationHeader.total_amount)).filter(
        extract('year', QuotationHeader.issue_date) == cur_year,
        extract('month', QuotationHeader.issue_date) == cur_month
    ).scalar() or 0

    # 今月の受注票ベース件数・金額
    order_count = db.query(func.count(OrderTicket.id)).filter(
        extract('year', OrderTicket.order_date) == cur_year,
        extract('month', OrderTicket.order_date) == cur_month,
        OrderTicket.is_active == True
    ).scalar() or 0

    order_amount = db.query(func.sum(OrderTicket.total_amount)).filter(
        extract('year', OrderTicket.order_date) == cur_year,
        extract('month', OrderTicket.order_date) == cur_month,
        OrderTicket.is_active == True
    ).scalar() or 0

    # 受注中案件の合計金額（ステータス="受注"のProjectOrder）
    active_orders_amount = db.query(
        func.sum(func.coalesce(ProjectOrder.quotation_amount, ProjectOrder.quotation_total, 0))
    ).filter(ProjectOrder.status == '受注').scalar() or 0

    active_orders_count = db.query(func.count(ProjectOrder.id)).filter(
        ProjectOrder.status == '受注'
    ).scalar() or 0

    # 見積ステータス別件数
    quotation_statuses = db.query(
        QuotationHeader.status, func.count(QuotationHeader.id)
    ).group_by(QuotationHeader.status).all()

    # 月別推移（受注月ベース）：ProjectOrder.order_date で年度フィルタ
    monthly_orders_order = db.query(
        extract('month', ProjectOrder.order_date).label('month'),
        func.sum(func.coalesce(ProjectOrder.quotation_amount, ProjectOrder.quotation_total, 0)).label('total')
    ).filter(
        ProjectOrder.order_date != None,
        ProjectOrder.order_date >= fiscal_start,
        ProjectOrder.order_date <= fiscal_end
    ).group_by('month').order_by('month').all()

    # 月別推移（納品月ベース）：ProjectOrder.sales_date で年度フィルタ
    monthly_orders_delivery = db.query(
        extract('month', ProjectOrder.sales_date).label('month'),
        func.sum(func.coalesce(ProjectOrder.quotation_amount, ProjectOrder.quotation_total, 0)).label('total')
    ).filter(
        ProjectOrder.sales_date != None,
        ProjectOrder.sales_date >= fiscal_start,
        ProjectOrder.sales_date <= fiscal_end
    ).group_by('month').order_by('month').all()

    return {
        "fiscal_year": year,
        "project_status_counts": {(s or "未設定"): c for s, c in project_statuses},
        "project_status_amounts": project_status_amounts,
        "quotation_status_counts": {(s or "draft"): c for s, c in quotation_statuses},
        "monthly_quotations_count": monthly_quotes,
        "monthly_quotations_amount": int(monthly_quote_amount),
        "order_count": order_count,
        "order_amount": int(order_amount or 0),
        "active_orders_count": active_orders_count,
        "active_orders_amount": int(active_orders_amount),
        "monthly_orders": [
            {"month": int(m), "total": int(t or 0)}
            for m, t in monthly_orders_order
        ],
        "monthly_orders_by_delivery": [
            {"month": int(m), "total": int(t or 0)}
            for m, t in monthly_orders_delivery
        ],
    }


@router.get("/sales")
def sales_report(year: int = Query(default=datetime.now().year), db: Session = Depends(get_db)):
    monthly = db.query(
        extract('month', OrderTicket.order_date).label('month'),
        func.count(OrderTicket.id).label('count'),
        func.sum(OrderTicket.total_amount).label('total')
    ).filter(
        extract('year', OrderTicket.order_date) == year
    ).group_by('month').order_by('month').all()

    return {
        "year": year,
        "monthly": [{"month": int(m), "count": c, "total": int(t or 0)} for m, c, t in monthly]
    }


@router.get("/sales-plan")
def sales_plan(year: int = Query(default=None), db: Session = Depends(get_db)):
    from app.db.models import ProjectOrder

    today = date.today()
    if year is None:
        year = _current_fiscal_year(today)

    fiscal_start, fiscal_end = _fiscal_range(year)

    orders = db.query(ProjectOrder).filter(
        ProjectOrder.sales_date != None,
        ProjectOrder.sales_date >= fiscal_start,
        ProjectOrder.sales_date <= fiscal_end
    ).all()

    rows = []
    for o in orders:
        if not o.sales_date:
            continue
        amount = int(o.quotation_amount or o.quotation_total or 0)
        rows.append({
            "child_no": o.child_no or "",
            "project_no": o.project_no or "",
            "project_name": o.project_name or "",
            "customer_name": o.customer_name or "",
            "agency_name": o.agency_name or "",
            "delivery_name": o.customer_name or "",
            "sales_person_name": o.sales_person_name or "",
            "status": o.status or "",
            "sales_date": str(o.sales_date),
            "month": o.sales_date.month,
            "amount": amount,
        })

    return {"year": year, "rows": rows}
