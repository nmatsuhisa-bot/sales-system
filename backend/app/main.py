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
