# -*- coding: utf-8 -*-
"""工場機械管理の画面をローカルで動かすための開発用サーバ（PostgreSQL・jwt・bcrypt が無い環境向け）

  cd backend && python3 tests/dev_equipment_server.py [port]

- DB は SQLite（tests/_equipment_dev.db）。起動時に users と eq_* テーブルを作る
- 認証はスタブ: すべてのリクエストを管理者として扱う。/api/auth/login と /api/auth/me も返す
  （画面側は localStorage に access_token と user があればログイン済み扱い）
- 本番コードは触らない。equipment ルーターをそのまま載せているので画面と API の結合確認に使う
"""
import os
import sys
import types
import uuid

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(HERE, "_equipment_dev.db"))

for name in ("jwt", "bcrypt"):
    try:
        __import__(name)
    except ImportError:
        m = types.ModuleType(name)
        m.encode = m.decode = m.hashpw = m.gensalt = m.checkpw = lambda *a, **k: None
        m.ExpiredSignatureError = m.InvalidTokenError = Exception
        sys.modules[name] = m

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from app.db import models as M  # noqa: E402
from app.api import equipment  # noqa: E402
from app.api.auth import get_current_user, require_admin  # noqa: E402

M.Base.metadata.create_all(bind=M.engine, tables=[M.User.__table__] + [t.__table__ for t in equipment.EQ_TABLES])
db = M.SessionLocal()
admin = db.query(M.User).filter(M.User.email == "dev@example.com").first()
if not admin:
    admin = M.User(id=uuid.uuid4(), email="dev@example.com", hashed_password="x", full_name="開発者", role="admin")
    db.add(admin); db.commit()
db.refresh(admin)
db.expunge(admin)   # セッションを閉じても属性を読めるように切り離す
db.close()

app = FastAPI(title="equipment dev")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(equipment.router, prefix="/api/equipment")
app.dependency_overrides[get_current_user] = lambda: admin
app.dependency_overrides[require_admin] = lambda: admin

USER = {"id": str(admin.id), "email": admin.email, "full_name": admin.full_name, "role": "admin", "function_roles": []}


@app.post("/api/auth/login")
def login():
    return {"access_token": "dev-token", "token_type": "bearer", "user": USER}


@app.get("/api/auth/me")
def me():
    return USER


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="127.0.0.1", port=port)
