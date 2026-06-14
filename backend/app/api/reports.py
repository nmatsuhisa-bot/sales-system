"""レポート API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, desc
from datetime import datetime, date
from app.db.models import get_db, Order, Quotation, Customer

router = APIRouter()

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = date.today()
    year = today.year
    month = today.month

    # 今月の受注
    monthly_orders = db.query(func.count(Order.id), func.sum(Order.total_amount)).filter(
        extract('year', Order.order_date) == year,
        extract('month', Order.order_date) == month
    ).first()

    # 今月の見積
    monthly_quotes = db.query(func.count(Quotation.id)).filter(
        extract('year', Quotation.issue_date) == year,
        extract('month', Quotation.issue_date) == month
    ).scalar()

    # ステータス別受注数
    order_statuses = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()

    # 月別売上（今年）
    monthly_sales = db.query(
        extract('month', Order.order_date).label('month'),
        func.sum(Order.total_amount).label('total')
    ).filter(
        extract('year', Order.order_date) == year
    ).group_by('month').order_by('month').all()

    # 見積ステータス
    quote_statuses = db.query(Quotation.status, func.count(Quotation.id)).group_by(Quotation.status).all()

    return {
        "monthly_orders_count": monthly_orders[0] or 0,
        "monthly_orders_amount": int(monthly_orders[1] or 0),
        "monthly_quotations_count": monthly_quotes or 0,
        "order_statuses": {s: c for s, c in order_statuses},
        "quotation_statuses": {s: c for s, c in quote_statuses},
        "monthly_sales": [{"month": int(m), "total": int(t or 0)} for m, t in monthly_sales],
    }

@router.get("/sales")
def sales_report(year: int = Query(default=datetime.now().year), db: Session = Depends(get_db)):
    monthly = db.query(
        extract('month', Order.order_date).label('month'),
        func.count(Order.id).label('count'),
        func.sum(Order.total_amount).label('total')
    ).filter(
        extract('year', Order.order_date) == year,
        Order.status.not_in(['cancelled'])
    ).group_by('month').order_by('month').all()

    return {
        "year": year,
        "monthly": [{"month": int(m), "count": c, "total": int(t or 0)} for m, c, t in monthly]
    }
