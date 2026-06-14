from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, customers, products, quotations, orders, purchase_orders, inventory, reports, projects, masters, estimate_quotations

app = FastAPI(
    title="販売管理・見積管理システム API",
    description="井上電設株式会社 販売・見積管理システム",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["認証"])
app.include_router(customers.router, prefix="/api/customers", tags=["顧客管理"])
app.include_router(products.router, prefix="/api/products", tags=["商品管理"])
app.include_router(quotations.router, prefix="/api/quotations", tags=["見積管理"])
app.include_router(orders.router, prefix="/api/orders", tags=["受注管理"])
app.include_router(purchase_orders.router, prefix="/api/purchase-orders", tags=["発注管理"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["在庫管理"])
app.include_router(reports.router, prefix="/api/reports", tags=["レポート"])
app.include_router(projects.router, prefix="/api/projects", tags=["案件管理"])
app.include_router(masters.router, prefix="/api/masters", tags=["マスタ管理"])
app.include_router(estimate_quotations.router, prefix="/api/estimate-quotations", tags=["見積管理（新）"])

@app.get("/")
def root():
    return {"message": "販売管理システム API v1.0"}

@app.get("/seed-masters")
def seed_masters():
    from app.db.models import SessionLocal, Agency, DeliveryDestination, Employee
    db = SessionLocal()
    try:
        # 商社
        agencies = [
            {"agency_code": "1001", "agency_name": "株式会社名古屋マシンセンター"},
            {"agency_code": "1002", "agency_name": "株式会社タクマ"},
            {"agency_code": "1003", "agency_name": "株式会社タカハシキカン"},
            {"agency_code": "1004", "agency_name": "共進機械株式会社"},
            {"agency_code": "1006", "agency_name": "朝日工業株式会社"},
        ]
        for a in agencies:
            if not db.query(Agency).filter(Agency.agency_code == a["agency_code"]).first():
                db.add(Agency(**a))

        # 納入先
        destinations = [
            {"customer_id": "1000009", "company_name": "朝日工業株式会社", "factory_name": "AAAAA"},
            {"customer_id": "1000008", "company_name": "株式会社ケイテック", "factory_name": "AAAAA"},
            {"customer_id": "1000007", "company_name": "共和成産株式会社", "factory_name": "AAAAA"},
            {"customer_id": "1000006", "company_name": "セーレン株式会社", "factory_name": "新田事業所"},
            {"customer_id": "1000005", "company_name": "院庄林業株式会社", "factory_name": "岡山第2工場"},
            {"customer_id": "1000004", "company_name": "リージョナルパワー株式会社", "factory_name": "鹿島D2工場"},
            {"customer_id": "1000003", "company_name": "ウッドリンク株式会社", "factory_name": "製材"},
            {"customer_id": "1000002", "company_name": "リージョナルパワー株式会社", "factory_name": "能代1号"},
            {"customer_id": "1000001", "company_name": "株式会社木環の杜", "factory_name": "四倉工場"},
        ]
        for d in destinations:
            if not db.query(DeliveryDestination).filter(DeliveryDestination.customer_id == d["customer_id"]).first():
                db.add(DeliveryDestination(**d))

        # 従業員
        employees = [
            {"employee_code": "20202", "employee_name": "後藤 宗人"},
            {"employee_code": "20309", "employee_name": "國立 信和"},
            {"employee_code": "10107", "employee_name": "井上 雄一朗"},
        ]
        for e in employees:
            from app.db.models import Employee
            if not db.query(Employee).filter(Employee.employee_code == e["employee_code"]).first():
                db.add(Employee(**e))

        db.commit()
        return {"message": "マスタデータ投入完了"}
    finally:
        db.close()
