from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, customers, products, quotations, orders, purchase_orders, inventory, reports, projects, masters, estimate_quotations, arrangements, materials as procurement_api, manufacturing

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
app.include_router(arrangements.router, prefix="/api/arrangements", tags=["手配書"])
app.include_router(procurement_api.router, prefix="/api/procurement", tags=["仕入（発注）管理"])
app.include_router(manufacturing.router, prefix="/api/manufacturing", tags=["製造計画"])


@app.get("/seed-users")
def seed_users():
    """初期ユーザーを投入（後藤・國立・井上）"""
    import bcrypt
    from app.db.models import SessionLocal, User
    db = SessionLocal()
    try:
        users = [
            {"email": "goto@inoue-densetsu.co.jp", "full_name": "後藤 宗人", "role": "user"},
            {"email": "kunitachi@inoue-densetsu.co.jp", "full_name": "國立 信和", "role": "user"},
            {"email": "inoue@inoue-densetsu.co.jp", "full_name": "井上 雄一朗", "role": "user"},
        ]
        hashed = bcrypt.hashpw("user1234".encode(), bcrypt.gensalt()).decode()
        for u in users:
            if not db.query(User).filter(User.email == u["email"]).first():
                db.add(User(email=u["email"], full_name=u["full_name"], hashed_password=hashed, role=u["role"]))
        db.commit()
        return {"message": "ユーザー投入完了（パスワード: user1234）"}
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "販売管理システム API v1.0"}


@app.get("/setup-add-is-active")
def setup_add_is_active():
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            conn.execute(text("UPDATE order_tickets SET is_active = TRUE WHERE is_active IS NULL"))
            conn.commit()
            return {"status": "ok", "message": "is_activeカラム追加完了"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


@app.get("/setup-fix-duplicate-tickets")
def setup_fix_duplicate_tickets():
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            # 子IDごとに最新1件(created_atが最も新しい)のみis_active=true、残りfalse
            conn.execute(text("""
                UPDATE order_tickets SET is_active = FALSE
                WHERE id NOT IN (
                    SELECT DISTINCT ON (child_no) id
                    FROM order_tickets
                    WHERE child_no IS NOT NULL
                    ORDER BY child_no, created_at DESC
                )
                AND child_no IS NOT NULL
            """))
            conn.commit()
            return {"status": "ok", "message": "重複受注票を非表示に設定しました"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


@app.get("/setup-manufacturing-tables")
def setup_manufacturing_tables():
    from app.db.models import engine, Base, MaterialMaster, BomItem, MaterialOrder, ProductionCapacity, ProductHours, ManufacturingPlan
    from sqlalchemy import text
    Base.metadata.create_all(engine, tables=[
        MaterialMaster.__table__, BomItem.__table__, MaterialOrder.__table__,
        ProductionCapacity.__table__, ProductHours.__table__, ManufacturingPlan.__table__
    ])
    # seed product_hours
    from app.db.models import SessionLocal
    db = SessionLocal()
    try:
        seed_data = [
            ("BFR","3X6",240),("BFR","4X6",272),("BFR","5X6",358),
            ("BFR","3X6L",242),("BFR","4X6L",352),("BFR","5X6L",410),
            ("BFR","5WX6L",403),("BFR","5WWX6L",424),
            ("BFP","84",212),("BFP","180",361),
            ("SCA","500",433),("SCA","590",455),("SCA","675",485),("SCA","844",744),
            ("SRR","2000X2(架台)",962),("SRR","2000X3(架台)",1284),("SRR","2000X2(ﾋﾟｯﾄ)",591),
            ("FLT","800上送り",447),
            ("CY","1000(架台含)",112),("CY","1350(架台含)",122),
            ("LRG","120",872),
        ]
        from app.db.models import ProductHours
        for pt, mn, rh in seed_data:
            if not db.query(ProductHours).filter(ProductHours.product_type==pt, ProductHours.model_no==mn).first():
                db.add(ProductHours(product_type=pt, model_no=mn, required_hours=rh))
        # seed production_capacity for 2025-2027
        from app.db.models import ProductionCapacity
        cap_data = [
            (2025,3,21),(2025,4,22),(2025,5,21),(2025,6,21),(2025,7,23),(2025,8,17),
            (2025,9,22),(2025,10,24),(2025,11,20),(2025,12,20),(2026,1,20),(2026,2,20),
            (2026,3,21),(2026,4,22),(2026,5,21),(2026,6,21),(2026,7,23),(2026,8,17),
            (2026,9,22),(2026,10,24),(2026,11,20),(2026,12,20),(2027,1,20),(2027,2,20),
        ]
        for fy, mo, wd in cap_data:
            if not db.query(ProductionCapacity).filter(ProductionCapacity.factory=="小牧",ProductionCapacity.fiscal_year==fy,ProductionCapacity.month==mo).first():
                db.add(ProductionCapacity(factory="小牧",fiscal_year=fy,month=mo,work_days=wd))
        db.commit()
        return {"status": "ok", "message": "製造計画・仕入管理テーブル作成完了"}
    finally:
        db.close()
