from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, customers, products, quotations, orders, purchase_orders, inventory, reports, projects

app = FastAPI(
    title="販売管理・見積管理システム API",
    description="井上電設株式会社 販売・見積管理システム",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
