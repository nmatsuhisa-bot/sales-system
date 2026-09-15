# -*- coding: utf-8 -*-
"""工場機械管理 API の通しテスト（SQLite でテーブルを作り、取込→紐付け→配置→確定→時点復元まで実行する）

実行:  cd backend && DATABASE_URL=sqlite:///tests/_equipment.db python3 tests/test_equipment_api_sqlite.py \
           <機械一覧表.csv> <固定資産台帳.csv> [図面.png ...]
CSV を省略すると小さな内蔵データで動く。PostgreSQL が無い環境向け。本番は PostgreSQL のため UUID 型などの挙動は完全には同じでない。
jwt / bcrypt が無い環境でも動くよう、認証モジュールはスタブする。
"""
import os
import sys
import types
import uuid
import datetime as dt

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(HERE, "_equipment.db"))
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
from app.api import equipment  # noqa: E402
from app.api.auth import get_current_user, require_admin  # noqa: E402

M.Base.metadata.create_all(bind=M.engine, tables=[M.User.__table__])
db = M.SessionLocal()
admin = M.User(id=uuid.uuid4(), email="admin@example.com", hashed_password="x", full_name="管理者", role="admin")
db.add(admin); db.commit()

app = FastAPI()
app.include_router(equipment.router, prefix="/api/equipment")
app.dependency_overrides[get_current_user] = lambda: admin
app.dependency_overrides[require_admin] = lambda: admin
client = TestClient(app)
failures = []


def ok(r, what, expect=None):
    if r.status_code >= 300:
        print("NG", what, r.status_code, r.text[:400]); failures.append(what)
        return None
    print("OK", what)
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else r.content


def check(cond, what):
    print(("OK " if cond else "NG ") + what)
    if not cond:
        failures.append(what)


MINI_MACHINES = (
    "工場,決算資産記載,償却資,価格,2022.2残額,2024.2,管理番号,機器名,分類1,分類2,メーカ,商社,型式・仕様,製造年,電気仕様,備考,工場作業内容,法令点検,検査委託先,修理記録\n"
    "桜田北,有,有,\"5,800,000\",1,1,S1-13,ﾌﾟﾚｽﾌﾞﾚｰｷ,曲げ,200V,ｱﾏﾀﾞ,,RG-80,1990,5.5kW,,曲げ加工,,,\n"
    "桜田北,有,有,\"28,300,000\",1,1,SK-17,複合加工機,切削,200V,ﾔﾏｻﾞｷﾏｻﾞｯｸ,,INTEGREX J-200,2020.2,15kW,,,,,\n"
    "桜田北,,,\"540,000\",,,SK-17,宮井電気工事,,,,,,2020.2,,,,,,\n"
    "桜田北,,,\"424,800\",,,SK-17,宮井電気工事,,,,,,2020.2,,,,,,\n"
    "桜田北,有,有,\"9,500,000\",1,1,F-10,ｿﾘｯﾄﾞｽﾄｯｶｰ,,,,,KSL-2009,1987,,,,,,\n"
    ",,,\"1,125,000\",,,,桜田工場移設,,,,,,2017,,,,,,\n"
    "桜田北,除去,除去,,,,S1-03,ｱｲｱﾝﾜｰｶｰ,切断,200V,ｱﾏﾀﾞ,,SPI-30,1988,,,,,,\n"
    "桜田,有,,\"781,000\",,,,機械移設工事,,,,,,2016.4,,,,,,\n"
    "小牧,有,,\"6,100,000\",,,K-36,ｱｲｱﾝﾜｰｶｰ,,,,,IW-453,2019.6,,,,,,\n"
)
MINI_LEDGER = (
    "\"固定資産名\",\"管理番号\",\"取得日\",\"事業供用開始日\",\"取得価額\",\"勘定科目\",\"数量又は面積\",\"部門\",\"未償却残高\",\"摘要\",\"除却日\",\"売却日\",\"仕訳摘要\"\n"
    "\"SKS1-13 プレスブレーキ RG-80\",\"0000000943\",\"1990-01-21\",\"1990-01-21\",\"5800000\",\"機械装置\",\"1台\",\"\",\"1\",\"均等償却\",\"\",\"\",\"桜田\"\n"
    "\"SK-17 ﾔﾏｻﾞｷﾏｻﾞｯｸ複合旋盤 INTEGREX J-200\",\"0000001250\",\"2020-02-08\",\"2020-02-08\",\"29264800\",\"機械装置\",\"1台\",\"\",\"1\",\"\",\"\",\"\",\"桜田\"\n"
    "\"SKF-10 ソリッドストッカー KSL-2009\",\"0000000954\",\"1992-01-21\",\"1992-01-21\",\"10625000\",\"機械装置\",\"1台\",\"\",\"1\",\"\",\"\",\"\",\"桜田\"\n"
    "\"K-36 アマダIW453 アイアンワーカー\",\"0000001247\",\"2019-06-06\",\"2019-06-06\",\"6100000\",\"機械装置\",\"1台\",\"\",\"1\",\"\",\"\",\"\",\"小牧\"\n"
    "\"SKSW-14 ﾀﾞｲﾍﾝﾃﾞｼﾞﾀﾙｵｰﾄ DM-350(S-2)\",\"0000001115\",\"2014-06-20\",\"2014-06-20\",\"330000\",\"機械装置\",\"1台\",\"\",\"1\",\"\",\"\",\"\",\"桜田\"\n"
    "\"本社倉庫鉄骨３Ｆ\",\"0000000006\",\"1972-10-21\",\"1972-10-21\",\"15661798\",\"建物\",\"1\",\"\",\"1\",\"\",\"\",\"\",\"共通部門\"\n"
    "\"RDXカートリッジ\",\"\",\"2024-03-27\",\"2024-03-27\",\"161000\",\"一括償却資産\",\"\",\"\",\"\",\"\",\"\",\"\",\"\"\n"
    "\"RDXカートリッジ\",\"\",\"2024-03-27\",\"2024-03-27\",\"161000\",\"一括償却資産\",\"\",\"\",\"\",\"\",\"\",\"\",\"\"\n"
)
# 1x1 の PNG
MINI_PNG = bytes.fromhex("89504e470d0a1a0a0000000d494844520000000100000001080200000090775"
                         "3de0000000c4944415408d763f8cfc00000030101003c3d2cb60000000049454e44ae426082")

machines_csv = open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else MINI_MACHINES.encode("utf-8-sig")
ledger_csv = open(sys.argv[2], "rb").read() if len(sys.argv) > 2 else MINI_LEDGER.encode("cp932")
drawing_pngs = [(os.path.basename(p), open(p, "rb").read()) for p in sys.argv[3:]] or [("test.png", MINI_PNG)]

# ---- セットアップ ----
ok(client.get("/api/equipment/setup-tables"), "setup-tables")
sites = ok(client.get("/api/equipment/sites"), "sites")
check(len(sites) >= 8, f"拠点の初期値 {len(sites)} 件")
site_id = sites[0]["id"]

# ---- 機械一覧表の取込 ----
pv = ok(client.post("/api/equipment/import/machines", files={"file": ("m.csv", machines_csv, "text/csv")}, data={"apply": "false"}), "機械 取込プレビュー")
print("   ", {k: v for k, v in pv.items() if k != "skipped"}, "skipped:", pv["skipped"][:5])
check(pv["applied"] is False and ok(client.get("/api/equipment/overview"), "overview(取込前)")["machines"] == 0, "プレビューでは登録されない")
res = ok(client.post("/api/equipment/import/machines", files={"file": ("m.csv", machines_csv, "text/csv")}, data={"apply": "true"}), "機械 取込確定")
print("   ", {k: v for k, v in res.items() if k != "skipped"})
ms = ok(client.get("/api/equipment/machines"), "machines")
check(len(ms) == res["machines"], f"機械 {len(ms)} 件 = 取込 {res['machines']} 件")
by_code = {m["code"]: m for m in ms}
sk17 = by_code.get("SK-17")
check(sk17 is not None and len(sk17["extra_rows"]) == 2, "SK-17 の付帯行 2 件（電気工事）")
f10 = by_code.get("F-10")
check(f10 is not None and len(f10["extra_rows"]) == 1 and f10["extra_rows"][0].get("name", "").startswith("桜田工場移設"), "F-10 の付帯行（桜田工場移設）")
check(by_code.get("S1-03", {}).get("status") == "removed", "S1-03（除去）は status=removed")
res2 = ok(client.post("/api/equipment/import/machines", files={"file": ("m.csv", machines_csv, "text/csv")}, data={"apply": "true"}), "機械 再取込（上書きなし）")
check(res2["created"] == 0 and res2["unchanged"] == res["machines"], "再取込は新規 0・据え置き全件")

# ---- 台帳の取込 ----
pv = ok(client.post("/api/equipment/import/assets", files={"file": ("2026年02月〜2027年02月期 固定資産台帳CSV.csv", ledger_csv, "text/csv")},
                    data={"apply": "false"}), "台帳 取込プレビュー")
print("    period", pv["period"], "rows", pv["rows"], "accounts", pv["accounts"])
check(pv["period"] == "2026-02", "期をファイル名から推定 2026-02")
res = ok(client.post("/api/equipment/import/assets", files={"file": ("l.csv", ledger_csv, "text/csv")}, data={"apply": "true", "period": "2026-02"}), "台帳 取込確定")
al = ok(client.get("/api/equipment/assets", params={"period": "2026-02"}), "assets")
check(len(al["items"]) == res["rows"], f"台帳 {len(al['items'])} 件 = 取込 {res['rows']} 件")
keys = [a["asset_key"] for a in al["items"]]
check(len(keys) == len(set(keys)), "asset_key が一意（管理番号空欄の同名資産も区別）")
# 翌期の再取込で差分が出る
res_next = ok(client.post("/api/equipment/import/assets", files={"file": ("l.csv", ledger_csv, "text/csv")}, data={"apply": "false", "period": "2027-02"}), "翌期プレビュー（差分）")
check(res_next["diff"]["prev_period"] == "2026-02" and res_next["diff"]["added"] == [] and res_next["diff"]["removed"] == [], "同じ CSV なら差分なし")

# ---- 自動紐付け → 突合 ----
auto = ok(client.post("/api/equipment/links/auto", json={"period": "2026-02"}), "自動紐付け")
print("   ", auto)
rec = ok(client.get("/api/equipment/reconcile", params={"period": "2026-02"}), "reconcile")
print("    summary", rec["summary"])
links = ok(client.get("/api/equipment/links"), "links")
lk = {(l["machine_code"], l["asset_key"]): l for l in links}
check(("S1-13", "0000000943") in lk and lk[("S1-13", "0000000943")]["confidence"] == "confirmed", "SKS1-13 → S1-13（価額一致で confirmed）")
check(("SK-17", "0000001250") in lk and lk[("SK-17", "0000001250")]["confidence"] == "confirmed", "SK-17 は付帯行込みの合計で価額一致")
check(("F-10", "0000000954") in lk and lk[("F-10", "0000000954")]["confidence"] == "confirmed", "SKF-10 は移設費込みで価額一致")
check(all(a["asset_key"] != "0000001115" or True for a in rec["assets_without_machine"]) and
      any(a["asset_key"] == "0000001115" for a in rec["assets_without_machine"]), "SKSW-14（一覧に無い）は未紐付けの台帳に残る")
check(not any(a["account"] == "建物" for a in rec["assets_without_machine"]), "建物は突合対象外")
# 手動紐付けと更新
m_s103 = by_code["S1-03"]
r = client.post("/api/equipment/links", json={"machine_code": "S1-03", "asset_key": "0000001115", "link_type": "その他", "note": "テスト"})
lid = ok(r, "手動紐付け")["id"]
ok(client.put(f"/api/equipment/links/{lid}", json={"confidence": "confirmed"}), "紐付け 確定に更新")
check(client.post("/api/equipment/links", json={"machine_code": "S1-03", "asset_key": "0000001115"}).status_code == 400, "重複紐付けは 400")
ok(client.delete(f"/api/equipment/links/{lid}"), "紐付け 削除")
# 紐付け CSV 取込
csv_links = "machine_code,asset_key,link_type,confidence,note\nS1-03,0000001115,その他,candidate,CSV取込\nZZ-99,0000001115,本体,,無い機械\n"
il = ok(client.post("/api/equipment/import/links", files={"file": ("links.csv", csv_links.encode("utf-8-sig"), "text/csv")}, data={"apply": "true"}), "紐付け CSV 取込")
check(il["created"] == 1 and len(il["errors"]) == 1, "紐付け CSV: 1 件登録・1 件エラー")

# ---- 図面登録 ----
dids = []
for fname, png in drawing_pngs:
    r = client.post("/api/equipment/drawings", data={"site_id": site_id, "name": fname.rsplit(".", 1)[0], "scale_note": "1/200"},
                    files={"file": (fname, png, "image/png"), "original": (fname, png, "image/png")})
    d = ok(r, f"図面登録 {fname}")
    dids.append(d["id"])
dl = ok(client.get("/api/equipment/drawings"), "drawings")
check(len(dl) == len(dids) and dl[0]["has_original"], "図面一覧（元図面あり）")
img = ok(client.get(f"/api/equipment/drawings/{dids[0]}/image"), "図面画像")
check(isinstance(img, (bytes, bytearray)) and img[:4] == b"\x89PNG", "画像は PNG バイナリ")
ok(client.get(f"/api/equipment/drawings/{dids[0]}/image", params={"original": "true"}), "元図面")
did = dids[0]

# ---- 配置：下書き → 取り消し → 確定 ----
board = ok(client.get(f"/api/equipment/drawings/{did}/board"), "board(初期)")
check(board["placements"] == [] and len(board["unplaced"]) > 0, f"初期は配置なし・未配置 {len(board['unplaced'])} 件（除去済みは除く）")
check(not any(u["code"] == "S1-03" for u in board["unplaced"]), "除去済み S1-03 は未配置リストに出ない")
mv1 = ok(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "S1-13", "kind": "place", "x": 0.2, "y": 0.3}), "place S1-13")
mv2 = ok(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "SK-17", "kind": "place", "x": 0.5, "y": 0.5}), "place SK-17")
mv3 = ok(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "S1-13", "kind": "move", "x": 0.25, "y": 0.35}), "move S1-13")
mv4 = ok(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "S1-13", "kind": "move", "x": 0.9, "y": 0.9}), "move S1-13 (取り消す)")
check(mv3["from_x"] == 0.2 and mv3["kind"] == "move", "2 回目は from に直前の下書き座標が入り kind=move")
check(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "S1-13", "kind": "move", "x": 1.5, "y": 0}).status_code == 400, "範囲外の座標は 400")
u = ok(client.post(f"/api/equipment/drawings/{did}/moves/undo"), "undo")
check(u["undone"]["id"] == mv4["id"] and u["remaining"] == 3, "最後の下書きが取り消される")
board = ok(client.get(f"/api/equipment/drawings/{did}/board"), "board(下書き)")
pos = {p["code"]: (p["x"], p["y"], p["draft"]) for p in board["placements"]}
check(pos.get("S1-13") == (0.25, 0.35, "move") and pos.get("SK-17") == (0.5, 0.5, "place"), "下書き適用後の座標")
check(len(board["draft_moves"]) == 3 and not any(u["code"] in ("S1-13", "SK-17") for u in board["unplaced"]), "下書き 3 件・配置済みは未配置から消える")
c1 = ok(client.post(f"/api/equipment/drawings/{did}/commit", json={"memo": "初期配置"}), "commit 1")
check(c1["changed"] == 2 and c1["commit"]["move_count"] == 3, "確定: 2 台の配置が作られ、下書き 3 件（取消含まず）が紐づく")
t_after_c1 = dt.datetime.utcnow()
board = ok(client.get(f"/api/equipment/drawings/{did}/board"), "board(確定後)")
check(all(p["draft"] is None for p in board["placements"]) and board["draft_moves"] == [], "確定後は下書きなし")
check(board["last_commit"]["memo"] == "初期配置", "最終確定のメモ")

# ---- 2 回目：移動＋外す → 時点復元 ----
import time; time.sleep(1.1)  # 時点復元の判定を秒単位で分けるため
ok(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "S1-13", "kind": "move", "x": 0.6, "y": 0.6}), "move S1-13 (2回目)")
ok(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "SK-17", "kind": "remove"}), "remove SK-17")
board = ok(client.get(f"/api/equipment/drawings/{did}/board"), "board(2回目下書き)")
check([p["code"] for p in board["placements"]] == ["S1-13"] and [r["code"] for r in board["removed_in_draft"]] == ["SK-17"], "外した機械は removed_in_draft に出る")
check(client.post(f"/api/equipment/drawings/{did}/moves", json={"machine_code": "K-36", "kind": "remove"}).status_code == 400, "配置されていない機械は外せない")
c2 = ok(client.post(f"/api/equipment/drawings/{did}/commit", json={}), "commit 2")
check(c2["changed"] == 2, "確定 2: 移動 1・除去 1")
now_board = ok(client.get(f"/api/equipment/drawings/{did}/board"), "board(現在)")
check({p["code"]: (p["x"], p["y"]) for p in now_board["placements"]} == {"S1-13": (0.6, 0.6)}, "現在: S1-13 のみ (0.6,0.6)")
past = ok(client.get(f"/api/equipment/drawings/{did}/board", params={"as_of": t_after_c1.isoformat()}), "board(as_of 確定1直後)")
check({p["code"]: (p["x"], p["y"]) for p in past["placements"]} == {"S1-13": (0.25, 0.35), "SK-17": (0.5, 0.5)}, "過去時点: 確定 1 の配置が再現される")
past0 = ok(client.get(f"/api/equipment/drawings/{did}/board", params={"as_of": "2000-01-01"}), "board(as_of 2000-01-01)")
check(past0["placements"] == [], "取込前の日付では配置なし")
check(any(u["code"] == "SK-17" for u in now_board["unplaced"]), "外した SK-17 は未配置に戻る")

# ---- 別図面へ移す（place すると確定時に元図面の配置が閉じる） ----
if len(dids) > 1:
    did2 = dids[1]
    ok(client.post(f"/api/equipment/drawings/{did2}/moves", json={"machine_code": "S1-13", "kind": "place", "x": 0.1, "y": 0.1}), "別図面に S1-13 を place")
    ok(client.post(f"/api/equipment/drawings/{did2}/commit", json={"memo": "移設"}), "別図面 commit")
    b1 = ok(client.get(f"/api/equipment/drawings/{did}/board"), "元図面 board")
    check(not any(p["code"] == "S1-13" for p in b1["placements"]), "元図面から S1-13 が消える")

# ---- 履歴 ----
h = ok(client.get(f"/api/equipment/machines/{by_code['S1-13']['id']}/history"), "machine history")
check(len(h["placements"]) >= 2 and h["placements"][-1]["valid_to"] is not None, "S1-13 の配置履歴に有効終了が入っている")
undone = [m for m in h["moves"] if m["undone_at"]]
check(len(undone) == 1 and undone[0]["commit_id"] == c1["commit"]["id"], "取り消した下書きも確定に紐づいて履歴に残る")
cl = ok(client.get(f"/api/equipment/drawings/{did}/commits"), "commits")
check(len(cl) == 2, "図面の確定履歴 2 件")
cd = ok(client.get(f"/api/equipment/commits/{cl[-1]['id']}"), "commit detail")
check(len(cd["moves"]) == 4, "確定 1 の明細 4 件（取消 1 件を含む）")
mvl = ok(client.get("/api/equipment/moves", params={"drawing_id": did}), "moves list")
check(len(mvl) == 6, f"移動履歴 {len(mvl)} 件")
ok(client.get("/api/equipment/machines", params={"placed": "yes"}), "machines?placed=yes")
ok(client.get("/api/equipment/machines", params={"link_state": "unlinked"}), "machines?link_state=unlinked")
ov = ok(client.get("/api/equipment/overview"), "overview")
print("    overview", ov)

# ---- 図面削除は履歴があると無効化にとどまる ----
r = ok(client.delete(f"/api/equipment/drawings/{did}"), "図面削除")
check("無効化" in r["message"], "履歴のある図面は無効化")

print("\n==== 結果:", "すべて通過" if not failures else f"失敗 {len(failures)} 件: {failures}")
sys.exit(1 if failures else 0)
