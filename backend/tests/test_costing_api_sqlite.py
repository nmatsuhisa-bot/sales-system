# -*- coding: utf-8 -*-
"""API の通しテスト（SQLite でテーブルを作り、取込→計算→検証→Excel 出力まで実行する）

実行:  cd backend && DATABASE_URL=sqlite:///tests/_costing.db python3 tests/test_costing_api_sqlite.py <原価ブック.xlsx> [...]
PostgreSQL が無い環境向け。本番は PostgreSQL のため UUID 型などの挙動は完全には同じでない。
jwt / bcrypt が無い環境でも動くよう、認証モジュールはスタブする。
"""
import os
import sys
import types
import uuid

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(HERE, "_costing.db"))
db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
if db_path and os.path.exists(db_path):
    os.remove(db_path)

for name in ("jwt", "bcrypt"):
    try:
        __import__(name)
    except ImportError:
        m = types.ModuleType(name)
        m.encode = m.decode = m.hashpw = m.gensalt = m.checkpw = lambda *a, **k: None
        m.ExpiredSignatureError = m.InvalidTokenError = Exception
        sys.modules[name] = m

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.db import models as M  # noqa: E402
from app.api import costing  # noqa: E402
from app.api.auth import require_admin  # noqa: E402

tables = [t.__table__ for t in (
    M.User, M.Supplier, M.MaterialMaster, M.UnitMaster, M.ProductHours, M.ProductMaster,
    M.EstimateBfrBody, M.EstimateBfqBody, M.EstimatePlFan,
    M.CostMaterialExt, M.CostMaterialAlias, M.CostMaterialPrice, M.CostPriceAdjustment,
    M.CostBomLine, M.CostSetting, M.CostScenario, M.CostCalculation,
)]
M.Base.metadata.create_all(bind=M.engine, tables=tables)

db = M.SessionLocal()
admin = M.User(id=uuid.uuid4(), email="admin@example.com", hashed_password="x", full_name="admin", role="admin")
db.add(admin)
db.add(M.ProductHours(product_type="BFR", model_no="3X6", required_hours=240))
db.add(M.EstimateBfrBody(model_code="BFR3×6", base_price=6892000, airflow=550, filter_type="標準", filter_price=4000, filter_count=162))
sup = M.Supplier(supplier_code="S001", name="テスト鋼材")
db.add(sup)
db.commit()

app = FastAPI()
app.include_router(costing.router, prefix="/api/costing")
app.dependency_overrides[require_admin] = lambda: admin
client = TestClient(app)


def ok(r, what):
    if r.status_code >= 300:
        print("NG", what, r.status_code, r.text[:500])
        sys.exit(1)
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else r


def main(paths):
    print(ok(client.get("/api/costing/setup-tables"), "setup"))
    print("settings:", ok(client.get("/api/costing/settings"), "settings")["current"])
    for p in paths:
        with open(p, "rb") as f:
            pre = ok(client.post("/api/costing/import/excel", params={"apply": "false"},
                                 files={"file": (os.path.basename(p), f, "application/octet-stream")}), "preview " + p)
        print(f"preview {os.path.basename(p)}: units={len(pre['units'])} materials={pre['materials']} warnings={len(pre['warnings'])}")
        with open(p, "rb") as f:
            res = ok(client.post("/api/costing/import/excel", params={"apply": "true"},
                                 files={"file": (os.path.basename(p), f, "application/octet-stream")}), "apply " + p)
        print("  applied:", res["stats"])
    units = ok(client.get("/api/costing/units"), "units")
    print("units:", len(units), [u["unit_code"] for u in units][:12], "...")
    ov = ok(client.get("/api/costing/overview"), "overview")
    print("overview:", {k: ov[k] for k in ("materials", "prices", "units", "lines")}, "dates:", ov["price_dates"])

    bfr = next((u for u in units if u["unit_code"] == "BFR3X6"), None)
    if bfr:
        r = ok(client.post("/api/costing/calculate", json={"unit_id": bfr["id"], "price_date": "2025-09-17", "compare_date": "2020-02-25"}), "calculate")
        m = r["material"]
        print(f"BFR3X6 材料費 {m['total']:,.0f} 鋼材 {m['steel_ratio']:.0%} 加工費 {r['labor_cost']:,.0f} 製造原価 {r['manufacturing_cost']:,.0f} "
              f"販売価格 {r['standard_price']:,.0f} 粗利率 {r['gross_margin_rate']:.1%} 未解決 {len(m['warnings'])} 2020比 {r['compare']['diff_rate']:+.1%}")
        assert abs(m["total"] - 3149767) < 5, m["total"]
        # 未解決行に別名を付けて解決する（ﾕﾆｸﾛ平W-M10 → ﾕﾆｸﾛ丸W-M10、RVｼｭｰﾄ/2.3t → SPHC-5*10 2.3t）
        mats = ok(client.get("/api/costing/materials", params={"search": "丸W-M10"}), "materials")
        maru = next(x for x in mats if x["material_name"] == "ﾕﾆｸﾛ丸W-M10")
        ok(client.post(f"/api/costing/materials/{maru['id']}/aliases", json={"alias": "ﾕﾆｸﾛ平W-M10"}), "alias")
        # 別名を付けた後、未解決だった資材（仮コード）の行を付け替える
        lines = ok(client.get(f"/api/costing/units/{bfr['id']}/lines"), "lines")["lines"]
        for l in lines:
            if l["label"] == "ﾕﾆｸﾛ平W-M10":
                ok(client.put(f"/api/costing/lines/{l['id']}", json={"material_id": maru["id"]}), "line update")
        sheet = next(x for x in ok(client.get("/api/costing/materials", params={"search": "SPHC-5*10 2.3t"}), "m2") if x["material_name"] == "SPHC-5*10 2.3t")
        for l in lines:
            if l["label"] == "RVｼｭｰﾄ/2.3t":
                ok(client.put(f"/api/costing/lines/{l['id']}", json={"material_id": sheet["id"]}), "line update 2")
        r2 = ok(client.post("/api/costing/calculate", json={"unit_id": bfr["id"], "price_date": "2025-09-17"}), "calculate2")
        print(f"別名解決後 材料費 {r2['material']['total']:,.0f} 未解決 {len(r2['material']['warnings'])}")
        # 仕入先別単価と値引き調整
        ok(client.post(f"/api/costing/materials/{sheet['id']}/prices", json={"supplier_id": str(sup.id), "effective_date": "2025-10-01", "price": 95}), "price")
        ok(client.post(f"/api/costing/materials/{sheet['id']}/adjustments", json={"party_id": str(sup.id), "adjust_type": "percent", "value": -5}), "adj")
        cmp = ok(client.get(f"/api/costing/materials/{sheet['id']}/compare", params={"price_date": "2025-10-15"}), "compare")
        print("仕入先比較:", [(c["supplier_name"], c["price"]) for c in cmp["candidates"]], "採用:", cmp["chosen_supplier_name"], cmp["chosen_price"], cmp["source"])
        ok(client.put(f"/api/costing/materials/{sheet['id']}/ext", json={"price_policy": "cheapest"}), "ext")
        cmp2 = ok(client.get(f"/api/costing/materials/{sheet['id']}/compare", params={"price_date": "2025-10-15"}), "compare2")
        print("最安ポリシー:", cmp2["chosen_supplier_name"], cmp2["chosen_price"])
        # シナリオ・一括
        batch = ok(client.post("/api/costing/calculate/batch", json={"unit_ids": [u["id"] for u in units[:6]], "price_date": "2025-09-17",
                                                                   "scenario": {"steel_pct": 10, "category_factors": {"購入品": 1.15}, "target_margin_rate": 30}}), "batch")
        for b in batch:
            if "error" in b:
                print("  batch error", b)
            else:
                print(f"  {b['unit_code']:<16} 基準 {b['base']['material_cost']:>12,.0f} 条件 {b['scenario']['material_cost']:>12,.0f} 必要売価 {b['scenario']['required_price'] or 0:>12,.0f}")
        ok(client.post("/api/costing/scenarios", json={"name": "鋼材+10%", "adjustments": {"steel_pct": 10}}), "scenario")
        ok(client.post("/api/costing/calculations", json={"unit_id": bfr["id"], "price_date": "2025-09-17", "label": "テスト"}), "save calc")
        print("saved:", len(ok(client.get("/api/costing/calculations", params={"unit_id": bfr["id"]}), "calcs")))
        x = ok(client.get(f"/api/costing/export/{bfr['id']}.xlsx", params={"price_date": "2025-09-17", "compare_date": "2020-02-25"}), "export")
        print("export bytes:", len(x.content), x.headers.get("content-disposition", "")[:60])
    # レポート（時系列 / サマリ）
    if bfr:
        ts = ok(client.get("/api/costing/report/timeseries", params={"unit_id": bfr["id"]}), "ts")
        print("時系列:", [(p["date"], round(p["material_cost"])) for p in ts["points"]], "変化", f"{ts['change_rate']:+.1%}", "要因", len(ts["movers"]), "部位", len(ts["section_names"]))
        x = ok(client.get("/api/costing/report/timeseries.xlsx", params={"unit_id": bfr["id"], "dates": "2020-02-25,2025-09-17"}), "ts xlsx")
        print("時系列 xlsx bytes:", len(x.content))
        pdf = ok(client.get("/api/costing/report/timeseries.pdf", params={"unit_id": bfr["id"]}), "ts pdf")
        print("時系列 pdf:", pdf.headers.get("content-type"), len(pdf.content))
    sm = ok(client.get("/api/costing/report/summary"), "summary")
    print("サマリ:", len(sm["rows"]), "型式", sm["dates"], "合計", {k: round(v) for k, v in sm["totals"].items()})
    sm2 = ok(client.get("/api/costing/report/summary", params={"include_options": "true"}), "summary2")
    print("サマリ（オプション込み）:", len(sm2["rows"]))
    x = ok(client.get("/api/costing/report/summary.xlsx"), "summary xlsx")
    print("サマリ xlsx bytes:", len(x.content))
    pdf = ok(client.get("/api/costing/report/summary.pdf"), "summary pdf")
    print("サマリ pdf:", pdf.headers.get("content-type"), len(pdf.content))
    v = ok(client.get("/api/costing/verify", params={"price_date": "2025-09-17"}), "verify")
    print("verify:", v["counts"], "units:", len(v["units"]))
    ok(client.post("/api/costing/settings", json={"key": "overhead_rate", "value": 12, "effective_date": "2026-01-01"}), "setting")
    print("settings now:", ok(client.get("/api/costing/settings"), "settings")["current"])
    print("\nAPI 通しテスト: OK")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1:])
