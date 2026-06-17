"""レポート API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date
from app.db.models import get_db, Project, QuotationHeader, OrderTicket

router = APIRouter()

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = date.today()
    year = today.year
    month = today.month

    # 案件ステータス集計
    project_statuses = db.query(
        Project.status, func.count(Project.id)
    ).group_by(Project.status).all()

    # 今月の見積件数・金額
    monthly_quotes = db.query(func.count(QuotationHeader.id)).filter(
        extract('year', QuotationHeader.issue_date) == year,
        extract('month', QuotationHeader.issue_date) == month
    ).scalar() or 0

    monthly_quote_amount = db.query(func.sum(QuotationHeader.total_amount)).filter(
        extract('year', QuotationHeader.issue_date) == year,
        extract('month', QuotationHeader.issue_date) == month
    ).scalar() or 0

    # 受注票ベースの受注件数・金額（今年累計）
    order_count = db.query(func.count(OrderTicket.id)).filter(
        extract('year', OrderTicket.order_date) == year,
        OrderTicket.is_active == True
    ).scalar() or 0

    order_amount = db.query(func.sum(OrderTicket.total_amount)).filter(
        extract('year', OrderTicket.order_date) == year,
        OrderTicket.is_active == True
    ).scalar() or 0

    # 月別見積金額推移（今年）
    monthly_estimates = db.query(
        extract('month', QuotationHeader.issue_date).label('month'),
        func.count(QuotationHeader.id).label('count'),
        func.sum(QuotationHeader.total_amount).label('total')
    ).filter(
        extract('year', QuotationHeader.issue_date) == year
    ).group_by('month').order_by('month').all()

    # 月別受注金額推移（今年）
    monthly_orders = db.query(
        extract('month', OrderTicket.order_date).label('month'),
        func.count(OrderTicket.id).label('count'),
        func.sum(OrderTicket.total_amount).label('total')
    ).filter(
        extract('year', OrderTicket.order_date) == year,
        OrderTicket.is_active == True
    ).group_by('month').order_by('month').all()

    return {
        "project_status_counts": {(s or "未設定"): c for s, c in project_statuses},
        "monthly_quotations_count": monthly_quotes,
        "monthly_quotations_amount": int(monthly_quote_amount),
        "order_count": order_count,
        "order_amount": int(order_amount or 0),
        "monthly_estimates": [
            {"month": int(m), "count": c, "total": int(t or 0)}
            for m, c, t in monthly_estimates
        ],
        "monthly_orders": [
            {"month": int(m), "count": c, "total": int(t or 0)}
            for m, c, t in monthly_orders
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
