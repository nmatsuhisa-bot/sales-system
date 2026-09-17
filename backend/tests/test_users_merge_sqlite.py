# -*- coding: utf-8 -*-
"""ユーザーマスタ（従業員マスタ統合後）の通しテスト（SQLite）

実行:  cd backend && DATABASE_URL=sqlite:///tests/_users.db python3 tests/test_users_merge_sqlite.py
従業員ID付きの作成・更新・重複チェック、/team の function_roles、旧・従業員マスタの取込（プレビュー→実行→再実行の冪等）を通す。
jwt / bcrypt が無い環境でも動くようスタブする（bcrypt.hashpw はダミーの bytes を返す）。
"""
import os
import sys
import types
import uuid

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(HERE, "_users.db"))
db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
if db_path and os.path.exists(db_path):
    os.remove(db_path)

for name in ("jwt", "bcrypt"):
    try:
        __import__(name)
    except ImportError:
        m = types.ModuleType(name)
        m.encode = m.decode = lambda *a, **k: "t"
        m.hashpw = lambda pw, salt: b"$2b$12$stub"
        m.gensalt = lambda: b"salt"
        m.checkpw = lambda *a, **k: True
        m.ExpiredSignatureError = m.InvalidTokenError = Exception
        sys.modules[name] = m

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.db import models as M  # noqa: E402
from app.api import auth  # noqa: E402
from app.api.auth import get_current_user, require_admin  # noqa: E402

M.Base.metadata.create_all(bind=M.engine, tables=[M.User.__table__, M.Employee.__table__])
db = M.SessionLocal()
admin = M.User(id=uuid.uuid4(), email="admin@example.com", hashed_password="x", full_name="管理者", role="admin")
db.add(admin)
# 旧・従業員マスタ: 1 人は既存ユーザーと氏名一致、1 人は不一致、1 人は退職（無効）
db.add(M.User(email="goto@example.com", hashed_password="x", full_name="後藤 宗人", role="staff", function_roles=["approver"]))
db.add(M.Employee(employee_code="20202", employee_name="後藤 宗人", department="営業"))
db.add(M.Employee(employee_code="20309", employee_name="國立 信和"))
db.add(M.Employee(employee_code="99999", employee_name="退職 太郎", is_active=False))
db.commit()
db.refresh(admin); db.expunge(admin); db.close()

app = FastAPI()
app.include_router(auth.router, prefix="/api/auth")
app.dependency_overrides[get_current_user] = lambda: admin
app.dependency_overrides[require_admin] = lambda: admin
client = TestClient(app)
failures = []


def ok(r, what):
    if r.status_code >= 300:
        print("NG", what, r.status_code, r.text[:300]); failures.append(what); return None
    print("OK", what); return r.json()


def check(cond, what):
    print(("OK " if cond else "NG ") + what)
    if not cond:
        failures.append(what)


roles = ok(client.get("/api/auth/function-roles"), "function-roles")
check(any(r["key"] == "sales_person" for r in roles["function_roles"]), "機能権限に「営業担当」がある")

u = ok(client.post("/api/auth/users", json={"email": "a@example.com", "password": "p", "full_name": "山田 太郎", "employee_code": "10001",
                                            "function_roles": ["sales_person"], "department": "営業"}), "ユーザー作成（従業員ID付き）")
check(u["employee_code"] == "10001" and u["function_roles"] == ["sales_person"], "作成結果に従業員IDと営業担当")
r = client.post("/api/auth/users", json={"email": "b@example.com", "password": "p", "full_name": "山田 次郎", "employee_code": "10001"})
check(r.status_code == 400 and "10001" in r.text, "従業員IDの重複は 400")
u2 = ok(client.post("/api/auth/users", json={"email": "b@example.com", "password": "p", "full_name": "山田 次郎", "employee_code": ""}), "従業員ID空欄で作成")
check(u2["employee_code"] is None, "空欄は None")
ok(client.put(f"/api/auth/users/{u2['id']}", json={"employee_code": "10002"}), "従業員IDを更新")
r = client.put(f"/api/auth/users/{u2['id']}", json={"employee_code": "10001"})
check(r.status_code == 400, "更新時の重複も 400")
ok(client.put(f"/api/auth/users/{u2['id']}", json={"employee_code": "10002"}), "自分と同じIDは可")
team = ok(client.get("/api/auth/team"), "team")
sp = [t for t in team if "sales_person" in t["function_roles"]]
check(len(sp) == 1 and sp[0]["employee_code"] == "10001", "/team に function_roles と employee_code が出て営業担当で絞れる")
lst = ok(client.get("/api/auth/users"), "users")
check(all("employee_code" in x for x in lst), "一覧に employee_code")

# 旧・従業員マスタの取込
pv = ok(client.post("/api/auth/users/merge-employees", params={"apply": "false"}), "取込プレビュー")
check(pv["applied"] is False and pv["summary"] == {"matched": 1, "created": 1, "skipped": 0}, f"プレビュー: 一致1・追加1 → {pv['summary']}")
check(client.get("/api/auth/users").json() == lst, "プレビューでは何も変わらない")
ap = ok(client.post("/api/auth/users/merge-employees", params={"apply": "true"}), "取込実行")
users = {x["full_name"]: x for x in client.get("/api/auth/users").json()}
g = users["後藤 宗人"]
check(g["employee_code"] == "20202" and g["department"] == "営業" and set(g["function_roles"]) == {"approver", "sales_person"},
      "一致した既存ユーザーに従業員ID・部門・営業担当が付き、承認権限は残る")
k = users.get("國立 信和")
check(k is not None and k["email"] == "emp-20309@noreply.local" and k["employee_code"] == "20309" and k["function_roles"] == ["sales_person"],
      "一致しない従業員は仮ユーザーとして追加")
check("退職 太郎" not in users, "無効な従業員は取り込まない")
ap2 = ok(client.post("/api/auth/users/merge-employees", params={"apply": "true"}), "再実行（冪等）")
check(ap2["summary"]["created"] == 0 and len(client.get("/api/auth/users").json()) == len(users), "再実行で増えない")
team = client.get("/api/auth/team").json()
check(sorted(t["full_name"] for t in team if "sales_person" in t["function_roles"]) == ["國立 信和", "山田 太郎", "後藤 宗人"], "営業担当の候補 3 名")

print("\n==== 結果:", "すべて通過" if not failures else f"失敗 {len(failures)} 件: {failures}")
sys.exit(1 if failures else 0)
