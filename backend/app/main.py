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
    allow_origins=["*"],
    allow_credentials=False,
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

@app.on_event("startup")
async def startup_event():
    from app.db.models import Base, engine
    Base.metadata.create_all(engine)

@app.get("/")
def root():
    return {"message": "販売管理システム API v1.0"}

@app.get("/setup")
def setup_db():
    from app.db.models import Base, engine
    Base.metadata.create_all(engine)
    return {"message": "テーブル作成完了！"}

@app.get("/reset-password")
def reset_password_get(email: str, new_password: str):
    from app.db.models import SessionLocal, User
    import bcrypt
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"error": "ユーザーが見つかりません"}
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    user.hashed_password = hashed
    db.commit()
    db.close()
    return {"message": "パスワードを更新しました"}

@app.get("/seed-masters")
def seed_masters():
    from app.db.models import SessionLocal, Agency, DeliveryDestination, Employee
    db = SessionLocal()
    try:
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

        employees = [
            {"employee_code": "20202", "employee_name": "後藤 宗人"},
            {"employee_code": "20309", "employee_name": "國立 信和"},
            {"employee_code": "10107", "employee_name": "井上 雄一朗"},
        ]
        for e in employees:
            if not db.query(Employee).filter(Employee.employee_code == e["employee_code"]).first():
                db.add(Employee(**e))

        db.commit()
        return {"message": "マスタデータ投入完了"}
    finally:
        db.close()

@app.get("/seed-estimate-patterns")
def seed_estimate_patterns():
    from app.db.models import SessionLocal, EstimateBfrBody, EstimateBfrFan, EstimateBfrRv, EstimateScaBody, EstimatePlFan, EstimateCyclone, EstimateLaborItem
    db = SessionLocal()
    try:
        # BFR本体
        if db.query(EstimateBfrBody).count() == 0:
            bfr_bodies = [
                {"model_code": "BFR3S×4", "base_price": 4156000, "airflow": 330, "filter_length": "2810L", "filter_type": "標準", "filter_price": 4000, "filter_count": 96},
                {"model_code": "BFR3S×4", "base_price": 4156000, "airflow": 330, "filter_length": "2810L", "filter_type": "帯電防止品", "filter_price": 4400, "filter_count": 96},
                {"model_code": "BFR3×4", "base_price": 4328000, "airflow": 370, "filter_length": "2810L", "filter_type": "標準", "filter_price": 4000, "filter_count": 108},
                {"model_code": "BFR3×4", "base_price": 4328000, "airflow": 370, "filter_length": "2810L", "filter_type": "帯電防止品", "filter_price": 4400, "filter_count": 108},
                {"model_code": "BFR3×5", "base_price": 6120000, "airflow": 460, "filter_length": "2810L", "filter_type": "標準", "filter_price": 4000, "filter_count": 135},
                {"model_code": "BFR3×5", "base_price": 6120000, "airflow": 460, "filter_length": "2810L", "filter_type": "帯電防止品", "filter_price": 4400, "filter_count": 135},
                {"model_code": "BFR3×6", "base_price": 6892000, "airflow": 550, "filter_length": "2810L", "filter_type": "標準", "filter_price": 4000, "filter_count": 162},
                {"model_code": "BFR3×6", "base_price": 6892000, "airflow": 550, "filter_length": "2810L", "filter_type": "帯電防止品", "filter_price": 4400, "filter_count": 162},
                {"model_code": "BFR4×6", "base_price": 6936000, "airflow": 730, "filter_length": "2810L", "filter_type": "標準", "filter_price": 4000, "filter_count": 216},
                {"model_code": "BFR5×6", "base_price": 7630000, "airflow": 920, "filter_length": "2810L", "filter_type": "標準", "filter_price": 4000, "filter_count": 270},
            ]
            for b in bfr_bodies:
                db.add(EstimateBfrBody(**b))

        # BFRファン
        if db.query(EstimateBfrFan).count() == 0:
            fans = [
                {"bfr_model": "BFR3S×4", "fan_model": "TVS11kw", "price": 640000, "quantity": 1},
                {"bfr_model": "BFR3S×4", "fan_model": "TVS15kw", "price": 710000, "quantity": 1},
                {"bfr_model": "BFR3×4", "fan_model": "TVS11kw", "price": 640000, "quantity": 2},
                {"bfr_model": "BFR3×4", "fan_model": "TVS15kw", "price": 710000, "quantity": 1},
                {"bfr_model": "BFR3×4", "fan_model": "TVS22kw", "price": 1100000, "quantity": 1},
                {"bfr_model": "BFR3×5", "fan_model": "TVS11kw", "price": 640000, "quantity": 3},
                {"bfr_model": "BFR3×5", "fan_model": "TVS15kw", "price": 710000, "quantity": 2},
                {"bfr_model": "BFR3×5", "fan_model": "TVS18.5kw", "price": 870000, "quantity": 2},
                {"bfr_model": "BFR3×6", "fan_model": "TVS11kw", "price": 640000, "quantity": 3},
                {"bfr_model": "BFR3×6", "fan_model": "TVS15kw", "price": 710000, "quantity": 2},
                {"bfr_model": "BFR3×6", "fan_model": "TVS22kw", "price": 1100000, "quantity": 2},
                {"bfr_model": "BFR4×6", "fan_model": "TVS22kw", "price": 1100000, "quantity": 2},
                {"bfr_model": "BFR5×6", "fan_model": "TVS22kw", "price": 1100000, "quantity": 3},
            ]
            for f in fans:
                db.add(EstimateBfrFan(**f))

        # BFR RV
        if db.query(EstimateBfrRv).count() == 0:
            rvs = [
                {"bfr_model": "BFR3S×4", "rv_model": "RV25×40", "kw": 0.2, "price": 290000, "quantity": 1},
                {"bfr_model": "BFR3S×4", "rv_model": "RV25×60", "kw": 0.2, "price": 320000, "quantity": 1},
                {"bfr_model": "BFR3×4", "rv_model": "RV25×40", "kw": 0.2, "price": 290000, "quantity": 1},
                {"bfr_model": "BFR3×4", "rv_model": "RV25×60", "kw": 0.2, "price": 320000, "quantity": 1},
                {"bfr_model": "BFR3×5", "rv_model": "RV25×60", "kw": 0.2, "price": 320000, "quantity": 1},
                {"bfr_model": "BFR3×5", "rv_model": "RV25×80", "kw": 0.4, "price": 390000, "quantity": 1},
                {"bfr_model": "BFR3×5", "rv_model": "RV30×80", "kw": 0.75, "price": 480000, "quantity": 1},
                {"bfr_model": "BFR3×6", "rv_model": "RV25×60", "kw": 0.4, "price": 320000, "quantity": 1},
                {"bfr_model": "BFR3×6", "rv_model": "RV25×80", "kw": 0.4, "price": 390000, "quantity": 1},
                {"bfr_model": "BFR3×6", "rv_model": "RV30×80", "kw": 0.75, "price": 480000, "quantity": 1},
                {"bfr_model": "BFR4×6", "rv_model": "RV30×80", "kw": 0.75, "price": 480000, "quantity": 1},
                {"bfr_model": "BFR5×6", "rv_model": "RV35×90", "kw": 2.2, "price": 570000, "quantity": 1},
            ]
            for r in rvs:
                db.add(EstimateBfrRv(**r))

        # SCA本体
        if db.query(EstimateScaBody).count() == 0:
            scas = [
                {"model_code": "SCD4", "diameter": 1145, "capacity": 5, "base_price": 1650000, "ab_kw": 0.4, "sc_count": 1, "sc1_kw": 0.4, "rv1_model": "RV20×35", "rv1_kw": 0.2},
                {"model_code": "SCD5", "diameter": 2000, "capacity": 10, "base_price": 2200000, "ab_kw": 0.4, "sc_count": 1, "sc1_kw": 0.4, "rv1_model": "RV20×35", "rv1_kw": 0.2},
                {"model_code": "SCA25", "diameter": 2500, "capacity": 15, "base_price": 3000000, "ab_kw": 1.5, "sc_count": 1, "sc1_kw": 0.75, "rv1_model": "RV25×40", "rv1_kw": 0.4},
                {"model_code": "SCA30", "diameter": 3000, "capacity": 20, "base_price": 3700000, "ab_kw": 1.5, "sc_count": 1, "sc1_kw": 0.4, "rv1_model": "RV25×40", "rv1_kw": 0.4},
                {"model_code": "SCA35", "diameter": 3500, "capacity": 30, "base_price": 4200000, "ab_kw": 1.5, "sc_count": 1, "sc1_kw": 0.75, "rv1_model": "RV25×40", "rv1_kw": 0.4},
                {"model_code": "SCA400", "diameter": 4000, "capacity": 50, "base_price": 5450000, "ab_kw": 1.5, "sc_count": 1, "sc1_kw": 0.75, "rv1_model": "RV25×40", "rv1_kw": 0.4},
                {"model_code": "SCA500", "diameter": 5000, "capacity": 100, "base_price": 8200000, "ab_kw": 1.5, "sc_count": 1, "sc1_kw": 0.75, "rv1_model": "RV25×40", "rv1_kw": 0.4},
                {"model_code": "SCA675", "diameter": 6750, "capacity": 200, "base_price": 15700000, "ab_kw": 3.7, "sc_count": 2, "sc1_kw": 1.5, "rv1_model": "RV25×60", "rv1_kw": 0.75},
            ]
            for s in scas:
                db.add(EstimateScaBody(**s))

        # PLファン
        if db.query(EstimatePlFan).count() == 0:
            pls = [
                {"model_code": "PL200", "kw": 3.7, "price": 390000},
                {"model_code": "PL200", "kw": 5.5, "price": 460000},
                {"model_code": "PL250", "kw": 5.5, "price": 480000},
                {"model_code": "PL250", "kw": 7.5, "price": 510000},
                {"model_code": "PL300", "kw": 7.5, "price": 520000},
                {"model_code": "PL300", "kw": 11, "price": 580000},
                {"model_code": "PL350", "kw": 11, "price": 610000},
                {"model_code": "PL350", "kw": 15, "price": 700000},
            ]
            for p in pls:
                db.add(EstimatePlFan(**p))

        # サイクロン
        if db.query(EstimateCyclone).count() == 0:
            cyclones = [
                {"model_code": "CY500", "shape": "標準", "material": "鉄", "price": 280000},
                {"model_code": "CY550", "shape": "シュート式", "material": "鉄", "price": 330000},
                {"model_code": "CY550", "shape": "シュート式", "material": "SUS", "price": 660000},
                {"model_code": "CY700", "shape": "標準", "material": "鉄", "price": 390000},
                {"model_code": "CY900", "shape": "標準", "material": "鉄", "price": 500000},
            ]
            for c in cyclones:
                db.add(EstimateCyclone(**c))

        # 社内工数マスタ
        if db.query(EstimateLaborItem).count() == 0:
            labors = [
                {"category": "工事作業", "item_name": "準備", "unit": "人日", "unit_price": 40000, "sort_order": 1},
                {"category": "工事作業", "item_name": "既設撤去", "unit": "人日", "unit_price": 40000, "sort_order": 2},
                {"category": "工事作業", "item_name": "組立", "unit": "人日", "unit_price": 40000, "sort_order": 3},
                {"category": "工事作業", "item_name": "屋外ダクト", "unit": "人日", "unit_price": 40000, "sort_order": 4},
                {"category": "工事作業", "item_name": "空気輸送", "unit": "人日", "unit_price": 40000, "sort_order": 5},
                {"category": "工事作業", "item_name": "屋内ダクト", "unit": "人日", "unit_price": 40000, "sort_order": 6},
                {"category": "工事作業", "item_name": "仕上げ", "unit": "人日", "unit_price": 40000, "sort_order": 7},
                {"category": "工事作業", "item_name": "帰社", "unit": "人日", "unit_price": 40000, "sort_order": 8},
                {"category": "重機", "item_name": "レッカー(10t普)", "unit": "台", "unit_price": 100000, "sort_order": 10},
                {"category": "重機", "item_name": "レッカー(10t低)", "unit": "台", "unit_price": 105000, "sort_order": 11},
                {"category": "重機", "item_name": "高所作業車", "unit": "台", "unit_price": 50000, "sort_order": 12},
                {"category": "宿泊", "item_name": "宿泊費", "unit": "泊", "unit_price": 7000, "sort_order": 20},
                {"category": "運送", "item_name": "運送交通費", "unit": "式", "unit_price": 0, "sort_order": 30},
                {"category": "消耗品", "item_name": "工事消耗品", "unit": "式", "unit_price": 0, "sort_order": 31},
                {"category": "試運転", "item_name": "試運転調整費", "unit": "式", "unit_price": 0, "sort_order": 32},
                {"category": "諸経費", "item_name": "諸経費", "unit": "式", "unit_price": 0, "sort_order": 33},
            ]
            for l in labors:
                db.add(EstimateLaborItem(**l))

        db.commit()
        return {"message": "見積パターンデータ投入完了"}
    finally:
        db.close()
