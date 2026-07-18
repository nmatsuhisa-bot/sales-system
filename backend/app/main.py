from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, customers, products, quotations, orders, purchase_orders, inventory, reports, projects, masters, estimate_quotations, arrangements, materials as procurement_api, manufacturing, process_schedule, bom_master, team_schedule

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
app.include_router(process_schedule.router, prefix="/api/process", tags=["工程管理"])
app.include_router(bom_master.router, prefix="/api/bom-master", tags=["製品BOMマスタ"])
app.include_router(team_schedule.router, prefix="/api/schedules", tags=["スケジュール"])


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


@app.get("/sync-final-order-amounts")
def sync_final_order_amounts():
    """全案件の最終受注金額を子ID.quotation_total の合計で一括再計算"""
    from app.db.models import SessionLocal, Project, ProjectOrder
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = db.query(
            ProjectOrder.project_id,
            func.sum(ProjectOrder.quotation_total).label("total")
        ).filter(ProjectOrder.project_id != None).group_by(ProjectOrder.project_id).all()

        updated = 0
        for project_id, total in rows:
            p = db.query(Project).filter(Project.id == project_id).first()
            if p and total:
                p.final_order_amount = int(total)
                updated += 1
        db.commit()
        return {"status": "ok", "updated": updated, "message": f"{updated}件の案件の最終受注金額を更新しました"}
    finally:
        db.close()


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


@app.get("/setup-team-schedule")
def setup_team_schedule():
    from app.db.models import engine, Base, TeamSchedule
    Base.metadata.create_all(engine, tables=[TeamSchedule.__table__])
    return {"status": "ok", "message": "スケジュールテーブル作成完了"}


@app.get("/setup-material-stock")
def setup_material_stock():
    """部材在庫の入出庫履歴テーブルを作成"""
    from app.db.models import engine, Base, MaterialStockMovement
    Base.metadata.create_all(engine, tables=[MaterialStockMovement.__table__])
    return {"status": "ok", "message": "部材在庫テーブル作成完了"}


@app.get("/setup-arrangement-vendors")
def setup_arrangement_vendors():
    """手配業者マスタテーブルを作成"""
    from app.db.models import engine, Base, ArrangementVendor
    Base.metadata.create_all(engine, tables=[ArrangementVendor.__table__])
    return {"status": "ok", "message": "手配業者マスタ作成完了"}


@app.get("/setup-schedule-dates")
def setup_schedule_dates():
    """工程表明細に start_date/end_date（絶対日付）を追加し、既存の月内日付から移行"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE work_schedule_items ADD COLUMN IF NOT EXISTS start_date DATE"))
            conn.execute(text("ALTER TABLE work_schedule_items ADD COLUMN IF NOT EXISTS end_date DATE"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
        # 既存データ移行（無効日付はスキップ）
        migrated = 0
        try:
            r1 = conn.execute(text("""
                UPDATE work_schedule_items wi SET start_date = make_date(ws.work_year, ws.work_month, wi.start_day)
                FROM work_schedules ws
                WHERE wi.schedule_id = ws.id AND wi.start_date IS NULL AND wi.start_day IS NOT NULL
                  AND ws.work_year IS NOT NULL AND ws.work_month IS NOT NULL AND wi.start_day BETWEEN 1 AND 28
            """))
            r2 = conn.execute(text("""
                UPDATE work_schedule_items wi SET end_date = make_date(ws.work_year, ws.work_month, wi.end_day)
                FROM work_schedules ws
                WHERE wi.schedule_id = ws.id AND wi.end_date IS NULL AND wi.end_day IS NOT NULL
                  AND ws.work_year IS NOT NULL AND ws.work_month IS NOT NULL AND wi.end_day BETWEEN 1 AND 28
            """))
            conn.commit()
            migrated = (r1.rowcount or 0) + (r2.rowcount or 0)
        except Exception as e:
            return {"status": "partial", "message": f"列追加OK・移行スキップ: {e}"}
    return {"status": "ok", "message": f"start_date/end_date 追加完了（移行 {migrated} 件）"}


@app.get("/setup-purchase-order-tables")
def setup_purchase_order_tables():
    """発注書ヘッダーテーブルを作成し、material_orders に purchase_order_id を追加"""
    from app.db.models import engine, Base, MaterialPurchaseOrder
    from sqlalchemy import text
    Base.metadata.create_all(engine, tables=[MaterialPurchaseOrder.__table__])
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE material_orders ADD COLUMN IF NOT EXISTS purchase_order_id UUID"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "発注書テーブル作成完了"}


@app.get("/setup-po-breakdown")
def setup_po_breakdown():
    """発注書に内訳番号カラム（breakdown_no/breakdown_name）を追加し、po_no を80桁に拡張"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE material_purchase_orders ADD COLUMN IF NOT EXISTS breakdown_no VARCHAR(50)"))
            conn.execute(text("ALTER TABLE material_purchase_orders ADD COLUMN IF NOT EXISTS breakdown_name VARCHAR(500)"))
            conn.execute(text("ALTER TABLE material_purchase_orders ALTER COLUMN po_no TYPE VARCHAR(80)"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "発注書 内訳番号カラム追加完了"}


@app.get("/setup-user-department")
def setup_user_department():
    """ユーザーに所属部門(department)カラムを追加（スケジュール絞込・権限用）"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(50)"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "ユーザー部門カラム追加完了"}


@app.get("/setup-order-ticket-shipping")
def setup_order_ticket_shipping():
    """受注票に前受金3回(JSON)・出荷方法カラムを追加"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS advance_payments JSON"))
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS shipping_method VARCHAR(50)"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "受注票 前受金3回・出荷方法カラム追加完了"}


@app.get("/migrate-amounts-to-net")
def migrate_amounts_to_net(apply: bool = False):
    """既存の案件金額・受注票金額を税込→税抜（見積の subtotal+labor_total）へ再計算する。
    見積書の総額(total_amount)は税込のまま。?apply=true で実行、既定はドライラン。
    見積明細を正とするため再実行しても同じ結果になる。"""
    from app.db.models import (
        SessionLocal, QuotationHeader, OrderTicket, ProjectOrder,
        ProjectOrderQuotation, Project,
    )
    from sqlalchemy import func
    db = SessionLocal()
    try:
        nets = {
            q.id: int((q.subtotal or 0) + (q.labor_total or 0))
            for q in db.query(QuotationHeader).all()
        }
        by_no = {q.quotation_no: nets[q.id] for q in db.query(QuotationHeader).all() if q.quotation_no}
        changed = {"order_tickets": 0, "project_orders": 0, "order_quotations": 0, "projects": 0}
        samples = []

        # 受注票: 紐づく見積の税抜金額へ
        for t in db.query(OrderTicket).all():
            if t.quotation_id and t.quotation_id in nets:
                new = nets[t.quotation_id]
                if int(t.total_amount or 0) != new:
                    if len(samples) < 5:
                        samples.append({"受注票": t.ticket_no, "旧(税込)": int(t.total_amount or 0), "新(税抜)": new})
                    changed["order_tickets"] += 1
                    if apply:
                        t.total_amount = new

        # 案件子ID: 見積番号から税抜金額へ
        for o in db.query(ProjectOrder).all():
            new = by_no.get(o.quotation_no) if o.quotation_no else None
            if new is None:
                continue
            if int(o.quotation_total or 0) != new or int(o.quotation_amount or 0) != new:
                changed["project_orders"] += 1
                if apply:
                    o.quotation_total = new
                    o.quotation_amount = new

        for oq in db.query(ProjectOrderQuotation).all():
            new = by_no.get(oq.quotation_no) if oq.quotation_no else None
            if new is not None and int(oq.quotation_total or 0) != new:
                changed["order_quotations"] += 1
                if apply:
                    oq.quotation_total = new

        if apply:
            db.flush()
            # 親案件の最終受注金額を子ID合計で再計算
            for p in db.query(Project).all():
                total = db.query(func.sum(ProjectOrder.quotation_total)).filter(
                    ProjectOrder.project_id == p.id
                ).scalar() or 0
                if int(p.final_order_amount or 0) != int(total):
                    changed["projects"] += 1
                    p.final_order_amount = int(total)
            db.commit()
        else:
            db.rollback()

        return {
            "status": "ok",
            "mode": "適用" if apply else "ドライラン（?apply=true で実行）",
            "更新件数": changed,
            "例": samples,
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@app.get("/setup-quotation-cover-fields")
def setup_quotation_cover_fields():
    """見積書に御担当者・受渡場所・有効期限テキスト・税抜表示・除外事項・作成/検印カラムを追加"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            for sql in [
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS customer_contact VARCHAR(100)",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS delivery_place VARCHAR(300)",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS valid_until_text VARCHAR(50)",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS tax_display VARCHAR(20) DEFAULT 'included'",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS exclusions TEXT",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS created_by_name VARCHAR(100)",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS approver_name VARCHAR(100)",
            ]:
                conn.execute(text(sql))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "見積書 頭紙項目カラム追加完了"}


@app.get("/setup-approval-workflow")
def setup_approval_workflow():
    """会議2026-07-17対応のカラム/テーブル追加。
    - 見積: 承認ワークフロー（approval_status等）・出精値引（discount_amount）
    - 見積明細: 一式品の金額表示制御（hide_amount / amount_text）
    - 案件: 確度（probability）
    - 受注票: 関連書類テーブル（order_ticket_files, PDFをDB保管）"""
    from app.db.models import engine, Base, OrderTicketFile
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            for sql in [
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) DEFAULT 'none'",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS approval_requested_at TIMESTAMP",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP",
                "ALTER TABLE quotation_headers ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(15,0) DEFAULT 0",
                "ALTER TABLE quotation_line_items ADD COLUMN IF NOT EXISTS hide_amount BOOLEAN DEFAULT FALSE",
                "ALTER TABLE quotation_line_items ADD COLUMN IF NOT EXISTS amount_text VARCHAR(50)",
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS probability VARCHAR(20)",
            ]:
                conn.execute(text(sql))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    # 受注票 関連書類テーブル（存在しなければ作成）
    OrderTicketFile.__table__.create(bind=engine, checkfirst=True)
    return {"status": "ok", "message": "承認ワークフロー・出精値引・金額表示制御・確度・受注票ファイル 追加完了"}


@app.get("/setup-function-roles")
def setup_function_roles():
    """ユーザーに機能権限(function_roles)を追加し、検印承認者の初期設定を行う。

    2026-07-18: 検印者をハードコードからユーザーマスタ参照に変更。

    ★氏名は「完全一致」で照合する。当初は部分一致にしていたが、社名が井上電設で
    「井上」姓の社員が4名おり、意図しない3名にも権限が付いてしまった。
    照合できなかった人はユーザー管理画面で手動設定すること。

    approver 権限は毎回「洗い替え」する（全解除→対象者にのみ付与）ため、
    誤って付いた権限もこのエンドポイントを再実行すれば正される。
    ただし画面で手動追加した承認者も消えるため、初期設定時のみ使うこと。"""
    from app.db.models import engine, SessionLocal, User
    from sqlalchemy import text
    from app.roles import has_role
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS function_roles JSON"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # 会議2026-07-17で決定した検印承認者5名の正式氏名（完全一致で照合）。
    # ※「国立」は従業員マスタ上は旧字の「國立 信和」
    # ※「井上社長」は井上 嗣夫（同姓の社員が複数いるため部分一致は使わない）
    # 柴田・江里口・井上嗣夫は /setup-approver-users で登録する
    TARGETS_EXACT = ["後藤 宗人", "國立 信和", "柴田 忠春", "江里口 一博", "井上 嗣夫"]
    granted, revoked, unmatched = [], [], []
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        by_name = {(u.full_name or "").strip(): u for u in users}
        # 1) 既存の approver を全解除（誤付与の是正）
        for u in users:
            if has_role(u, "approver"):
                u.function_roles = [r for r in (u.function_roles or []) if r != "approver"]
                revoked.append(u.full_name)
        # 2) 完全一致した対象者にのみ付与
        for name in TARGETS_EXACT:
            u = by_name.get(name)
            if not u:
                unmatched.append(name)
                continue
            u.function_roles = (u.function_roles or []) + ["approver"]
            granted.append(u.full_name)
        db.commit()
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
    return {"status": "ok", "message": "検印承認者を洗い替えしました",
            "付与": granted, "解除（洗い替え前）": revoked,
            "ユーザー未登録（要手動設定）": unmatched + ["井上社長", "柴田", "江里口"]}


@app.get("/setup-approver-users")
def setup_approver_users():
    """検印承認者3名（柴田・江里口・井上社長）をテスト用に登録する。

    メールは一意制約があるため、Gmailのエイリアス（+付き）で分けている。
    いずれも matsuhisa27@gmail.com に配信される。
    既に同じメールのユーザーがいれば作らず、権限の付与だけ行う（冪等）。"""
    import bcrypt
    from app.db.models import SessionLocal, User
    from app.roles import has_role
    TARGETS = [
        {"email": "matsuhisa27+shibata@gmail.com", "full_name": "柴田 忠春"},
        {"email": "matsuhisa27+eriguchi@gmail.com", "full_name": "江里口 一博"},
        {"email": "matsuhisa27+inoue@gmail.com", "full_name": "井上 嗣夫"},
    ]
    created, granted, skipped = [], [], []
    db = SessionLocal()
    try:
        hashed = bcrypt.hashpw("user1234".encode(), bcrypt.gensalt()).decode()
        for t in TARGETS:
            u = db.query(User).filter(User.email == t["email"]).first()
            if not u:
                u = User(email=t["email"], full_name=t["full_name"], hashed_password=hashed,
                         role="user", function_roles=["approver"])
                db.add(u)
                created.append(f'{t["full_name"]} <{t["email"]}>')
                continue
            skipped.append(t["full_name"])
            if not has_role(u, "approver"):
                u.function_roles = (u.function_roles or []) + ["approver"]
                granted.append(t["full_name"])
        db.commit()
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
    return {"status": "ok", "message": "検印承認者のテストユーザーを登録（パスワード: user1234）",
            "新規作成": created, "既存に権限付与": granted, "既に存在": skipped}


@app.get("/setup-project-ticket-type")
def setup_project_ticket_type():
    """案件子IDに工番/単番の区分を追加し、既存データへ現在の判定結果を引き継ぐ。

    2026-07-18: 工番/単番は案件登録時の必須選択とし、税抜300万円による自動判定は廃止。
    既存データは ①受注票が発行済みならその区分 ②未発行なら見積の税抜金額で判定
    ③見積も無ければ単番 の順で埋める。冪等（既に値が入っている行は触らない）。"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE project_orders ADD COLUMN IF NOT EXISTS ticket_type VARCHAR(20)"))
            # ① 受注票が発行済みの子IDは、その受注票の区分を引き継ぐ（最新の有効な票を優先）
            r1 = conn.execute(text("""
                UPDATE project_orders po SET ticket_type = t.ticket_type
                FROM (
                    SELECT DISTINCT ON (project_order_id) project_order_id, ticket_type
                    FROM order_tickets
                    WHERE project_order_id IS NOT NULL AND ticket_type IS NOT NULL
                    ORDER BY project_order_id, is_active DESC, created_at DESC
                ) t
                WHERE po.id = t.project_order_id AND po.ticket_type IS NULL
            """))
            # ② 受注票が無い子IDは、見積の税抜金額（値引後）で判定
            r2 = conn.execute(text("""
                UPDATE project_orders po
                SET ticket_type = CASE WHEN COALESCE(po.quotation_total, 0) >= 3000000
                                       THEN 'koban' ELSE 'tanban' END
                WHERE po.ticket_type IS NULL
            """))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "案件子IDに工番/単番を追加",
            "受注票から引継ぎ": r1.rowcount, "金額から判定": r2.rowcount}


@app.get("/setup-bfq-patterns")
def setup_bfq_patterns():
    """BFQ見積パターン（系列/本体/排風型式/オプション）テーブル作成＋マスタ投入。
    出典: 「2026.2.9_BFQ見積パターン.xlsx」BFQシート。再実行時は洗い替え。"""
    from app.db.models import (
        engine, SessionLocal,
        EstimateBfqSeries, EstimateBfqBody, EstimateBfqFan, EstimateBfqOption,
    )
    EstimateBfqSeries.__table__.create(bind=engine, checkfirst=True)
    EstimateBfqBody.__table__.create(bind=engine, checkfirst=True)
    EstimateBfqFan.__table__.create(bind=engine, checkfirst=True)
    EstimateBfqOption.__table__.create(bind=engine, checkfirst=True)

    db = SessionLocal()
    try:
        for M in (EstimateBfqSeries, EstimateBfqBody, EstimateBfqFan, EstimateBfqOption):
            db.query(M).delete()

        # 系列ごとの『決まり』値・スイッチ・制御盤（標準=電動シェーキング）
        # (series, 制御盤標準価格, ケースブレーカ, 価格, 押しボタン, 価格)
        for i, (s, panel, cb, cbp, ps, psp) in enumerate([
            ("BFQ3", 146000, "NCD-30 3P15", 8000, "AS480", 3200),
            ("BFQ5", 146000, "NCD-30 3P25", 8000, "AS480", 3200),
            ("BFQ7", 161000, "NCD-30 3P30", 8000, "AS480", 3200),
            ("BFQ10", 175000, "NCD-50 3P40", 11000, "AS480", 3200),
            ("BFQ15", 255000, "なし(制御盤)", None, "なし(制御盤)", None),
        ]):
            db.add(EstimateBfqSeries(
                series=s, indoor_outdoor="屋内", flange_type="フランジ", maker="日立",
                slide_base="無", remarks="IE3", panel_price=panel,
                case_breaker=cb, case_breaker_price=cbp,
                push_switch=ps, push_switch_price=psp, sort_order=i,
            ))

        # 周波数 → 排風型式
        for s, hz, fm in [
            ("BFQ3", 50, "PLD2.2-2R54"), ("BFQ3", 60, "PLD2.2-2R65"),
            ("BFQ5", 50, "PLD3.7-2R53"), ("BFQ5", 60, "PLD3.7-2R64"),
            ("BFQ7", 50, "PLD5.5-2R52"), ("BFQ7", 60, "PLD5.5-4R63"),
            ("BFQ10", 50, "PLD7.5-4R50"), ("BFQ10", 60, "PLD7.5-4R60"),
            ("BFQ15", 50, "PLD11-4R52"), ("BFQ15", 60, "PLD11-4R62"),
        ]:
            db.add(EstimateBfqFan(series=s, hz=hz, fan_model=fm))

        # 本体（型式ごと）: (型式, 系列, 本体価格, 価格原文, kW, φ, ﾌｨﾙﾀｰ長, 本数, ｼｪｰｶｰ, 払落kW, ﾀﾞｽﾄ回収)
        bodies = [
            ("BFQ3",   "BFQ3", 510000, None, 2.2, 200, "1400L", 14, "なし", None, "袋受φ575"),
            ("BFQ3S",  "BFQ3", 570000, None, 2.2, 200, "1400L", 14, "手動", None, "袋受φ575"),
            ("BFQ3V",  "BFQ3", 600000, None, 2.2, 200, "1400L", 14, "電動", 0.2, "袋受φ575"),
            ("BFQ3HS", "BFQ3", 600000, None, 2.2, 200, "1400L", 14, "手動", None, "H:空送"),
            ("BFQ3HV", "BFQ3", 630000, None, 2.2, 200, "1400L", 14, "電動", 0.2, "H:空送"),
            ("BFQ3RV", "BFQ3", None, "600000+RV", 2.2, 200, "1400L", 14, "電動", 0.2, "RV"),
            ("BFQ5",   "BFQ5", 640000, None, 3.7, 200, "1400L", 25, "なし", None, "袋受φ700"),
            ("BFQ5S",  "BFQ5", 690000, None, 3.7, 200, "1400L", 25, "手動", None, "袋受φ700"),
            ("BFQ5V",  "BFQ5", 730000, None, 3.7, 200, "1400L", 25, "電動", 0.2, "袋受φ700"),
            ("BFQ5HS", "BFQ5", 720000, None, 3.7, 200, "1400L", 25, "手動", None, "H:空送"),
            ("BFQ5HV", "BFQ5", 760000, None, 3.7, 200, "1400L", 25, "電動", 0.2, "H:空送"),
            ("BFQ5RV", "BFQ5", None, "730000+RV", 3.7, 200, "1400L", 25, "電動", 0.2, "RV"),
            ("BFQ5VQ", "BFQ5", None, None, 3.7, 200, "1400L", 25, "電動", 0.2, "Qコンテナ"),
            ("BFQ7",   "BFQ7", None, None, 5.5, None, "1400L", 36, "なし", None, "袋受φ700"),
            ("BFQ7S",  "BFQ7", None, None, 5.5, None, "1400L", 36, "手動", None, "袋受φ700"),
            ("BFQ7V",  "BFQ7", None, None, 5.5, None, "1400L", 36, "電動", 0.2, "袋受φ700"),
            ("BFQ7HS", "BFQ7", None, None, 5.5, None, "1400L", 36, "手動", None, "H:空送"),
            ("BFQ7HV", "BFQ7", None, None, 5.5, None, "1400L", 36, "電動", 0.2, "H:空送"),
            ("BFQ7RV", "BFQ7", None, "1050000+RV", 5.5, None, "1400L", 36, "電動", 0.2, "RV"),
            ("BFQ7VQ", "BFQ7", None, None, 5.5, None, "1400L", 36, "電動", 0.2, "Qコンテナ"),
            ("BFQ7Vフレコン", "BFQ7", None, None, 5.5, None, "1400L", 36, "電動", 0.2, "フレコン受"),
            ("BFQ10V",  "BFQ10", 1140000, None, 7.5, None, "2000L", 36, "電動", 0.2, "袋受φ700"),
            ("BFQ10HV", "BFQ10", 1260000, None, 7.5, None, "2000L", 36, "電動", 0.2, "H:空送"),
            ("BFQ10RV", "BFQ10", None, "1140000+RV", 7.5, None, "2000L", 36, "電動", 0.2, "RV"),
            ("BFQ10VQ", "BFQ10", None, None, 7.5, None, "2000L", 36, "電動", 0.2, "Qコンテナ"),
            ("BFQ10Vフレコン", "BFQ10", None, None, 7.5, None, "2000L", 36, "電動", 0.2, "フレコン受"),
            ("BFQ15V",  "BFQ15", 1540000, None, 11, None, "2000L", 42, "電動", 0.4, "袋受φ700"),
            ("BFQ15HV", "BFQ15", 1570000, None, 11, None, "2000L", 42, "電動", 0.4, "H:空送"),
            ("BFQ15RV", "BFQ15", None, "1540000+RV", 11, None, "2000L", 42, "電動", 0.4, "RV"),
            ("BFQ15VQ", "BFQ15", None, "1540000+Qコンテナ", 11, None, "2000L", 42, "電動", 0.4, "Qコンテナ"),
            ("BFQ15Vフレコン", "BFQ15", None, None, 11, None, "2000L", 42, "電動", 0.4, "フレコン受"),
        ]
        for i, (mc, s, bp, note, kw, dia, fl, fc, sh, shkw, dr) in enumerate(bodies):
            db.add(EstimateBfqBody(
                model_code=mc, series=s, base_price=bp, price_note=note, fan_kw=kw,
                filter_dia=dia, filter_length=fl, filter_count=fc,
                shaker=sh, shaker_kw=shkw, dust_recovery=dr, sort_order=i,
            ))

        # オプション: 空送（H型）… price=径ごとの価格 / unit_price=H型単品価格
        for i, (s, dia, p, up) in enumerate([
            ("BFQ3", "φ150", 30000, 60000),
            ("BFQ5", "φ150", 30000, 64000),
            ("BFQ7", "φ150", 30000, 68000), ("BFQ7", "φ175", 30000, 68000),
            ("BFQ10", "φ175", 30000, 68000), ("BFQ10", "φ200", 30000, 68000),
            ("BFQ15", "φ175", 30000, 72000), ("BFQ15", "φ200", 30000, 72000),
        ]):
            db.add(EstimateBfqOption(category="空送", series=s, option_name=dia,
                                     spec=dia, price=p, unit_price=up, sort_order=i))

        # オプション: RV（全系列共通・xlsx上「価格(仮)」のため要確定）
        for i, (m, kw, p) in enumerate([
            ("RV20×35", 0.2, 250000), ("RV25×40", 0.2, 290000),
            ("RV25×60", 0.4, 320000), ("RV25×80", 0.75, 390000),
        ]):
            db.add(EstimateBfqOption(category="RV", option_name=m, spec=f"{kw}kW",
                                     price=p, is_provisional=True, sort_order=i))

        # オプション: フレコン受 / Qコンテナ / 制御盤の追加仕様（複数選択可）
        for i, (m, p) in enumerate([
            ("継脚長さ変更・サイレンサー短管延長", 50000),
            ("レベルスイッチ付(フレコン満杯)", 73000),
            ("改造なし", 0),
        ]):
            db.add(EstimateBfqOption(category="フレコン", option_name=m, price=p, sort_order=i))
        for i, (m, p) in enumerate([("Qコンテナ+予備タンク", 220000), ("Qコンテナ", 142000)]):
            db.add(EstimateBfqOption(category="Qコンテナ", option_name=m, price=p, sort_order=i))
        for i, (m, p) in enumerate([
            ("+外部ファン運転中", 6500), ("+空送ファン付(3.7kwまで)", 48000),
            ("+RV", 24000), ("+フレコン満杯", 45000),
            ("+遠隔スイッチ", 25000), ("+欠相保護", 6000),
        ]):
            db.add(EstimateBfqOption(category="制御盤追加", option_name=m, price=p, sort_order=i))

        db.commit()
        counts = {
            "series": db.query(EstimateBfqSeries).count(),
            "bodies": db.query(EstimateBfqBody).count(),
            "fans": db.query(EstimateBfqFan).count(),
            "options": db.query(EstimateBfqOption).count(),
            "本体価格が未設定の型式": db.query(EstimateBfqBody).filter(EstimateBfqBody.base_price.is_(None)).count(),
        }
        return {"status": "ok", "message": "BFQ見積パターン投入完了", "counts": counts}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@app.get("/setup-order-ticket-checks")
def setup_order_ticket_checks():
    """受注票に図面/契約書有無・部品手配/在庫マイナス（未・済）カラムを追加"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS has_drawing BOOLEAN"))
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS has_contract BOOLEAN"))
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS parts_input_status VARCHAR(10)"))
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS parts_order_status VARCHAR(10)"))
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS stock_minus_status VARCHAR(10)"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "受注票 図面/契約書・部品手配カラム追加完了"}


@app.get("/setup-customer-delivery-date")
def setup_customer_delivery_date():
    """案件子IDに顧客納期カラム（customer_delivery_date）を追加"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE project_orders ADD COLUMN IF NOT EXISTS customer_delivery_date DATE"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "顧客納期カラム追加完了"}


@app.get("/setup-plan-unit-fields")
def setup_plan_unit_fields():
    """製造計画に内訳番号・ユニット名カラムを追加（ユニット単位計画）"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE manufacturing_plans ADD COLUMN IF NOT EXISTS breakdown_no VARCHAR(50)"))
            conn.execute(text("ALTER TABLE manufacturing_plans ADD COLUMN IF NOT EXISTS unit_name VARCHAR(500)"))
            conn.execute(text("ALTER TABLE manufacturing_plans ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT TRUE"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "製造計画 ユニット項目カラム追加完了"}


@app.get("/setup-order-ticket-fields")
def setup_order_ticket_fields():
    """受注票に受注時項目（注文書有無・納期・前受金）カラムを追加"""
    from app.db.models import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS has_order_sheet BOOLEAN"))
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS delivery_date DATE"))
            conn.execute(text("ALTER TABLE order_tickets ADD COLUMN IF NOT EXISTS advance_payment NUMERIC(15,0)"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "受注票 受注時項目カラム追加完了"}


@app.get("/setup-child-no-letters")
def setup_child_no_letters():
    """既存の子ID枝番 _01/_02… を _A/_B… に変換し、child_noを参照する全テーブルを一括更新"""
    from app.db.models import engine, SessionLocal, ProjectOrder
    from app.api.projects import _num_to_letters
    from sqlalchemy import text
    db = SessionLocal()
    mapping = {}
    skipped = []
    try:
        orders = db.query(ProjectOrder).all()
        existing = {o.child_no for o in orders if o.child_no}
        targets = set()
        for o in orders:
            cn = o.child_no or ""
            if "_" not in cn:
                continue
            prefix, suffix = cn.rsplit("_", 1)
            if not suffix.isdigit():
                continue  # 既に英字などは対象外（冪等）
            new_cn = f"{prefix}_{_num_to_letters(int(suffix))}"
            if new_cn == cn:
                continue
            if new_cn in existing or new_cn in targets:
                skipped.append(cn)
                continue
            mapping[cn] = new_cn
            targets.add(new_cn)
    finally:
        db.close()

    if not mapping:
        return {"status": "ok", "message": "変換対象なし", "converted": 0, "skipped": skipped}

    # child_no（およびそれを保持する派生カラム）を持つ全テーブルを更新
    cols = [
        ("project_orders", "child_no"),
        ("quotation_headers", "child_no"),
        ("order_tickets", "child_no"),
        ("crane_arrangements", "child_no"), ("crane_arrangements", "order_no"),
        ("shipping_arrangements", "child_no"), ("shipping_arrangements", "order_no"),
        ("hotel_arrangements", "child_no"),
        ("material_purchase_orders", "seiban"),
        ("work_schedule_items", "work_no"),
    ]
    updated = {}
    with engine.connect() as conn:
        for table, col in cols:
            cnt = 0
            try:
                for old, new in mapping.items():
                    r = conn.execute(text(f"UPDATE {table} SET {col} = :new WHERE {col} = :old"), {"new": new, "old": old})
                    cnt += r.rowcount or 0
                conn.commit()
                updated[f"{table}.{col}"] = cnt
            except Exception as e:
                conn.rollback()
                updated[f"{table}.{col}"] = f"skip: {e}"
    return {"status": "ok", "converted": len(mapping), "mapping": mapping, "skipped": skipped, "updated": updated}


@app.get("/setup-bom-master-tables")
def setup_bom_master_tables():
    """製品BOM階層マスタ＋案件適用テーブルを作成し、material_orders に発注NO/ユニット紐付け列を追加"""
    from app.db.models import (
        engine, Base, ProductMaster, UnitMaster, ProductUnitBom,
        UnitMaterialBom, ProjectProduct, ProjectUnit,
    )
    from sqlalchemy import text
    Base.metadata.create_all(engine, tables=[
        ProductMaster.__table__, UnitMaster.__table__, ProductUnitBom.__table__,
        UnitMaterialBom.__table__, ProjectProduct.__table__, ProjectUnit.__table__,
    ])
    # 既存 material_orders に列追加（発注NO・ユニット紐付け）
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE material_orders ADD COLUMN IF NOT EXISTS order_no VARCHAR(100)"))
            conn.execute(text("ALTER TABLE material_orders ADD COLUMN IF NOT EXISTS project_unit_id UUID"))
            conn.commit()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "製品BOMマスタ・案件適用テーブル作成完了"}


@app.get("/setup-process-tables")
def setup_process_tables():
    from app.db.models import engine, Base, ProcessTemplate, ProcessTemplateStep, WorkSchedule, WorkScheduleItem
    Base.metadata.create_all(engine, tables=[
        ProcessTemplate.__table__, ProcessTemplateStep.__table__,
        WorkSchedule.__table__, WorkScheduleItem.__table__
    ])
    # 初期テンプレート投入
    from app.db.models import SessionLocal
    db = SessionLocal()
    try:
        if db.query(ProcessTemplate).count() == 0:
            templates = [
                {
                    "product_type": "SCA", "template_name": "SCA標準工程",
                    "steps": [
                        {"step_no":1,"step_name":"移動（行き）","offset_start_days":-10,"duration_days":1,"color":"#6b7280"},
                        {"step_no":2,"step_name":"搬入・機器据付","offset_start_days":-9,"duration_days":3,"color":"#3b82f6"},
                        {"step_no":3,"step_name":"ダクト配管","offset_start_days":-6,"duration_days":3,"color":"#0ea5e9"},
                        {"step_no":4,"step_name":"仕上げ・塗装","offset_start_days":-3,"duration_days":2,"color":"#8b5cf6"},
                        {"step_no":5,"step_name":"配管並び電気切替え","offset_start_days":-1,"duration_days":1,"color":"#f59e0b"},
                        {"step_no":6,"step_name":"試運転・調整","offset_start_days":0,"duration_days":1,"color":"#10b981"},
                        {"step_no":7,"step_name":"移動（帰り）","offset_start_days":1,"duration_days":1,"color":"#6b7280"},
                    ]
                },
                {
                    "product_type": "BFR", "template_name": "BFR標準工程",
                    "steps": [
                        {"step_no":1,"step_name":"移動（行き）","offset_start_days":-12,"duration_days":1,"color":"#6b7280"},
                        {"step_no":2,"step_name":"基礎・架台据付","offset_start_days":-11,"duration_days":2,"color":"#3b82f6"},
                        {"step_no":3,"step_name":"本体搬入・据付","offset_start_days":-9,"duration_days":3,"color":"#0ea5e9"},
                        {"step_no":4,"step_name":"ダクト・配管工事","offset_start_days":-6,"duration_days":3,"color":"#8b5cf6"},
                        {"step_no":5,"step_name":"仕上げ・塗装","offset_start_days":-3,"duration_days":2,"color":"#f97316"},
                        {"step_no":6,"step_name":"電気・試運転","offset_start_days":-1,"duration_days":2,"color":"#f59e0b"},
                        {"step_no":7,"step_name":"移動（帰り）","offset_start_days":1,"duration_days":1,"color":"#6b7280"},
                    ]
                },
            ]
            for td in templates:
                tmpl = ProcessTemplate(product_type=td["product_type"], template_name=td["template_name"])
                db.add(tmpl); db.flush()
                for sd in td["steps"]:
                    db.add(ProcessTemplateStep(template_id=tmpl.id, **{k:v for k,v in sd.items()}))
            db.commit()
        return {"status": "ok", "message": "工程管理テーブル作成完了"}
    finally:
        db.close()
