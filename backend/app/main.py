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
