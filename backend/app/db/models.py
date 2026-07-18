from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Date, Numeric, Integer, Text, ForeignKey, JSON, UniqueConstraint, or_, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import uuid
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sales_user:sales_pass@localhost:5432/sales_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def pk_or_code(id_col, code_col, value):
    """UUID主キー・業務コード（案件ID/子ID/見積番号 等）のどちらでも引けるフィルタ。

    or_(Model.id == v, Model.code == v) と素直に書くと、v が非UUID文字列のとき
    PostgreSQLが id(UUID列) へのキャストに失敗して InvalidTextRepresentation となり
    500になる。UUIDとして解釈できるときだけ主キー条件を含めることで回避する。
    """
    conds = [code_col == value]
    try:
        conds.append(id_col == uuid.UUID(str(value)))
    except (ValueError, TypeError):
        pass
    return or_(*conds)

# =============================================
# モデル定義
# =============================================

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(50), default="staff")
    department = Column(String(50))            # 所属部門（営業/施工 等）。スケジュール絞込・権限用
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Customer(Base):
    __tablename__ = "customers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    name_kana = Column(String(200))
    postal_code = Column(String(10))
    prefecture = Column(String(50))
    address = Column(String(500))
    phone = Column(String(50))
    fax = Column(String(50))
    email = Column(String(255))
    contact_person = Column(String(100))
    payment_terms = Column(String(200))
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    quotations = relationship("Quotation", back_populates="customer")
    orders = relationship("Order", back_populates="customer")


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    name_kana = Column(String(200))
    postal_code = Column(String(10))
    address = Column(String(500))
    phone = Column(String(50))
    email = Column(String(255))
    contact_person = Column(String(100))
    payment_terms = Column(String(200))
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Product(Base):
    __tablename__ = "products"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_code = Column(String(100), unique=True, nullable=False)
    name = Column(String(300), nullable=False)
    product_type = Column(String(50))
    category = Column(String(100))
    unit = Column(String(50), default="式")
    standard_price = Column(Numeric(15, 0), default=0)
    cost_price = Column(Numeric(15, 0), default=0)
    description = Column(Text)
    spec_json = Column(JSON)
    stock_quantity = Column(Numeric(10, 2), default=0)
    min_stock_quantity = Column(Numeric(10, 2), default=0)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProductOption(Base):
    __tablename__ = "product_options"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    option_code = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    option_type = Column(String(100))
    applicable_product_type = Column(String(50))
    price = Column(Numeric(15, 0), default=0)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Quotation(Base):
    __tablename__ = "quotations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_no = Column(String(50), unique=True, nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    title = Column(String(500))
    issue_date = Column(Date, nullable=False)
    valid_until = Column(Date)
    status = Column(String(50), default="draft")
    subtotal = Column(Numeric(15, 0), default=0)
    tax_rate = Column(Numeric(5, 2), default=10.00)
    tax_amount = Column(Numeric(15, 0), default=0)
    total_amount = Column(Numeric(15, 0), default=0)
    delivery_terms = Column(String(500))
    payment_terms = Column(String(500))
    delivery_location = Column(String(500))
    notes = Column(Text)
    internal_notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    submitted_at = Column(DateTime)
    approved_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer", back_populates="quotations")
    items = relationship("QuotationItem", back_populates="quotation", cascade="all, delete-orphan")


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False)
    line_no = Column(Integer, nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    item_name = Column(String(500), nullable=False)
    description = Column(Text)
    quantity = Column(Numeric(10, 2), default=1)
    unit = Column(String(50), default="式")
    unit_price = Column(Numeric(15, 0), default=0)
    amount = Column(Numeric(15, 0), default=0)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    quotation = relationship("Quotation", back_populates="items")
    options = relationship("QuotationItemOption", back_populates="quotation_item", cascade="all, delete-orphan")


class QuotationItemOption(Base):
    __tablename__ = "quotation_item_options"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_item_id = Column(UUID(as_uuid=True), ForeignKey("quotation_items.id", ondelete="CASCADE"), nullable=False)
    option_id = Column(UUID(as_uuid=True), ForeignKey("product_options.id"))
    option_name = Column(String(200), nullable=False)
    price = Column(Numeric(15, 0), default=0)
    notes = Column(Text)

    quotation_item = relationship("QuotationItem", back_populates="options")


class Order(Base):
    __tablename__ = "orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_no = Column(String(50), unique=True, nullable=False)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotations.id"))
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    title = Column(String(500))
    order_date = Column(Date, nullable=False)
    delivery_date = Column(Date)
    status = Column(String(50), default="received")
    subtotal = Column(Numeric(15, 0), default=0)
    tax_rate = Column(Numeric(5, 2), default=10.00)
    tax_amount = Column(Numeric(15, 0), default=0)
    total_amount = Column(Numeric(15, 0), default=0)
    delivery_location = Column(String(500))
    payment_terms = Column(String(500))
    notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    line_no = Column(Integer, nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    item_name = Column(String(500), nullable=False)
    description = Column(Text)
    quantity = Column(Numeric(10, 2), default=1)
    unit = Column(String(50), default="式")
    unit_price = Column(Numeric(15, 0), default=0)
    amount = Column(Numeric(15, 0), default=0)
    notes = Column(Text)

    order = relationship("Order", back_populates="items")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_no = Column(String(50), unique=True, nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    issue_date = Column(Date, nullable=False)
    expected_date = Column(Date)
    status = Column(String(50), default="draft")
    subtotal = Column(Numeric(15, 0), default=0)
    tax_rate = Column(Numeric(5, 2), default=10.00)
    tax_amount = Column(Numeric(15, 0), default=0)
    total_amount = Column(Numeric(15, 0), default=0)
    notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    line_no = Column(Integer, nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    item_name = Column(String(500), nullable=False)
    quantity = Column(Numeric(10, 2), default=1)
    unit = Column(String(50), default="式")
    unit_price = Column(Numeric(15, 0), default=0)
    amount = Column(Numeric(15, 0), default=0)
    received_quantity = Column(Numeric(10, 2), default=0)
    notes = Column(Text)

    purchase_order = relationship("PurchaseOrder", back_populates="items")


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_no = Column(String(50), unique=True, nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date)
    status = Column(String(50), default="draft")
    subtotal = Column(Numeric(15, 0), default=0)
    tax_rate = Column(Numeric(5, 2), default=10.00)
    tax_amount = Column(Numeric(15, 0), default=0)
    total_amount = Column(Numeric(15, 0), default=0)
    paid_amount = Column(Numeric(15, 0), default=0)
    paid_at = Column(DateTime)
    notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    order = relationship("Order", back_populates="invoices")


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    movement_type = Column(String(50), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(15, 0))
    reference_type = Column(String(50))
    reference_id = Column(UUID(as_uuid=True))
    notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())


# =============================================
# 案件管理（親）
# =============================================
class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    project_no = Column(String(50), unique=True, nullable=False)   # 案件ID_親
    seq_no = Column(String(10))                                     # 連番

    project_name = Column(String(500))                              # 案件名
    project_summary = Column(Text)                                  # 案件概要

    customer_code_1 = Column(String(50))                            # 顧客ID_1（代理店）
    customer_name_1 = Column(String(200))                           # 顧客名_1（代理店）
    customer_code_2 = Column(String(50))                            # 顧客ID_2（エンドユーザー）
    customer_name_2 = Column(String(200))                           # 顧客名_2（エンドユーザー）

    sales_person_name = Column(String(100))                         # 自社営業担当
    sales_person_code = Column(String(50))                          # 自社営業担当者ID

    status = Column(String(50), default="営業中")                  # 案件ステータス
    probability = Column(String(20))                                # 確度（高/中/低。見込み数字を入れる案件の管理用）
    distribution_type = Column(String(50))                          # 商流判定: 直接/代理店

    budget_amount = Column(Numeric(15, 0))                          # 予算金額
    estimated_sales_total = Column(Numeric(15, 0))                  # 見込売上合計
    final_order_amount = Column(Numeric(15, 0))                     # 最終受注金額
    cost_price = Column(Numeric(15, 0))                             # 案件原価
    profit_amount = Column(Numeric(15, 0))                          # 利益額
    profit_rate = Column(Numeric(7, 4))                             # 利益率

    inquiry_date = Column(Date)                                     # 引き合い日
    sales_date = Column(Date)                                       # 顧客納期/売上計上日
    drawing_request_date = Column(Date)                             # 社内出図希望日
    order_date = Column(Date)                                       # 受注日
    expected_order_date = Column(Date)                              # 受注予定日
    expected_shipment_date = Column(Date)                           # 出荷予定日
    created_date = Column(Date)                                     # 作成日

    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    project_orders = relationship("ProjectOrder", back_populates="project", cascade="all, delete-orphan")


# =============================================
# 案件管理（子）: 案件ID_子 単位
# =============================================
class ProjectOrder(Base):
    __tablename__ = "project_orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    child_no = Column(String(100), unique=True, nullable=False)     # 案件ID_子
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    project_no = Column(String(50), nullable=False)                 # 案件ID_親

    project_name = Column(String(500))                              # 案件名
    project_summary = Column(Text)                                  # 案件概要

    customer_code = Column(String(50))                              # 顧客ID
    customer_name = Column(String(200))                             # 顧客名（エンドユーザー）
    agency_code = Column(String(50))                                # 代理店ID
    agency_name = Column(String(200))                               # 代理店名

    sales_person_name = Column(String(100))                         # 自社営業担当
    sales_person_code = Column(String(50))                          # 自社営業担当ID

    # 工番/単番の区分（koban/tanban）。2026-07-18より登録時の必須選択とし、金額による
    # 自動判定は廃止。受注票発行時はこの値を引き継ぐ
    ticket_type = Column(String(20))

    status = Column(String(50))                                     # ステータス（親参照）

    quotation_amount = Column(Numeric(15, 0))                       # 見積金額（見積書引用）
    budget_amount = Column(Numeric(15, 0))                          # 予算金額（親参照）

    sales_date = Column(Date)                                       # 売上計上日（売上予定日）
    customer_delivery_date = Column(Date)                           # 顧客納期
    inquiry_date = Column(Date)                                     # 引き合い日（親参照）
    order_date = Column(Date)                                       # 受注日
    expected_order_date = Column(Date)                              # 受注予定日
    shipment_date = Column(Date)                                    # 出荷日
    expected_shipment_date = Column(Date)                           # 出荷予定日

    quotation_no = Column(String(50))                               # 見積NO（主）
    quotation_total = Column(Numeric(15, 0))                        # 見積総計（主）
    quotation_issue_date = Column(Date)                             # 見積発行日（主）

    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotations.id"))
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))

    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="project_orders")
    linked_quotations = relationship("ProjectOrderQuotation", back_populates="project_order", cascade="all, delete-orphan")


# 見積紐付け（子に複数の見積が紐づく場合）
class ProjectOrderQuotation(Base):
    __tablename__ = "project_order_quotations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id", ondelete="CASCADE"), nullable=False)
    quotation_no = Column(String(50))
    quotation_total = Column(Numeric(15, 0))
    quotation_issue_date = Column(Date)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotations.id"))
    created_at = Column(DateTime, server_default=func.now())

    project_order = relationship("ProjectOrder", back_populates="linked_quotations")


# =============================================
# 商社マスタ（代理店）
# =============================================
class Agency(Base):
    __tablename__ = "agencies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_code = Column(String(50), unique=True, nullable=False)
    agency_name = Column(String(200), nullable=False)
    branch_name = Column(String(200))
    trade_terms = Column(String(200))
    address = Column(String(500))
    contact_person = Column(String(100))
    phone = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# =============================================
# 納入先マスタ
# =============================================
class DeliveryDestination(Base):
    __tablename__ = "delivery_destinations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(String(50), unique=True, nullable=False)
    company_name = Column(String(200), nullable=False)
    factory_name = Column(String(200))
    company_factory_name = Column(String(300))
    address = Column(String(500))
    prefecture = Column(String(50))
    postal_code = Column(String(20))
    tel = Column(String(50))
    fax = Column(String(50))
    customer_rank = Column(String(50))
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# =============================================
# 従業員マスタ
# =============================================
class Employee(Base):
    __tablename__ = "employees"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_code = Column(String(50), unique=True, nullable=False)
    employee_name = Column(String(100), nullable=False)
    department = Column(String(100))
    role = Column(String(50), default="staff")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# =============================================
# 見積パターンマスタ
# =============================================
class EstimateBfrBody(Base):
    __tablename__ = "estimate_bfr_bodies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_code = Column(String(50), nullable=False)
    base_price = Column(Numeric(15, 0))
    airflow = Column(Integer)
    filter_length = Column(String(50))
    filter_type = Column(String(50))
    filter_price = Column(Numeric(15, 0))
    filter_count = Column(Integer)
    is_active = Column(Boolean, default=True)

class EstimateBfrFan(Base):
    __tablename__ = "estimate_bfr_fans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bfr_model = Column(String(50), nullable=False)
    fan_model = Column(String(50))
    price = Column(Numeric(15, 0))
    quantity = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

class EstimateBfrRv(Base):
    __tablename__ = "estimate_bfr_rvs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bfr_model = Column(String(50), nullable=False)
    rv_model = Column(String(50))
    kw = Column(Numeric(5, 2))
    price = Column(Numeric(15, 0))
    quantity = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

# ----- BFQ（型式別パターン。xlsx「BFQ見積パターン」準拠）-----
class EstimateBfqSeries(Base):
    """BFQ系列（BFQ3/5/7/10/15）ごとの『決まり』値とスイッチ・制御盤価格"""
    __tablename__ = "estimate_bfq_series"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series = Column(String(20), nullable=False)        # BFQ3 / BFQ5 / BFQ7 / BFQ10 / BFQ15
    indoor_outdoor = Column(String(20))                # 屋内/屋外
    flange_type = Column(String(20))                   # フランジ/脚取付
    maker = Column(String(50))                         # メーカ
    slide_base = Column(String(20))                    # スライドベース
    remarks = Column(String(100))                      # 備考（IE3 等）
    panel_price = Column(Numeric(15, 0))               # 制御盤：電動シェーキング（標準）
    case_breaker = Column(String(50))                  # ケースブレーカ型式
    case_breaker_price = Column(Numeric(15, 0))
    push_switch = Column(String(50))                   # 押しボタンスイッチ型式
    push_switch_price = Column(Numeric(15, 0))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class EstimateBfqBody(Base):
    """BFQ本体（型式ごと）"""
    __tablename__ = "estimate_bfq_bodies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_code = Column(String(50), nullable=False)    # BFQ3 / BFQ3S / BFQ3V ...
    series = Column(String(20), nullable=False)        # BFQ3
    base_price = Column(Numeric(15, 0))                # 本体価格（NULL=マスタ未確定）
    price_note = Column(String(100))                   # '600000+RV' 等、価格が式表記の場合の原文
    fan_kw = Column(Numeric(5, 2))                     # 排風機kW
    filter_dia = Column(Integer)                       # フィルター径φ
    filter_length = Column(String(20))                 # 1400L / 2000L
    filter_count = Column(Integer)                     # フィルター本数
    shaker = Column(String(20))                        # なし / 手動 / 電動
    shaker_kw = Column(Numeric(5, 2))                  # 払い落しギヤモータkW（なし=NULL）
    dust_recovery = Column(String(50))                 # 袋受φ575 / H:空送 / RV / Qコンテナ / フレコン受
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class EstimateBfqFan(Base):
    """BFQ 周波数 → 排風型式（系列×Hzで決まる）"""
    __tablename__ = "estimate_bfq_fans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series = Column(String(20), nullable=False)
    hz = Column(Integer, nullable=False)               # 50 / 60
    fan_model = Column(String(50))                     # PLD2.2-2R54
    is_active = Column(Boolean, default=True)

class EstimateBfqOption(Base):
    """BFQ オプション（ダスト回収方式・制御盤追加仕様ごとの選択肢）"""
    __tablename__ = "estimate_bfq_options"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(30), nullable=False)      # 空送 / RV / フレコン / Qコンテナ / 制御盤追加
    series = Column(String(20))                        # 対象系列（NULL=全系列共通）
    option_name = Column(String(100))                  # 選択肢名
    spec = Column(String(50))                          # 径・kW 等
    price = Column(Numeric(15, 0))                     # 価格
    unit_price = Column(Numeric(15, 0))                # 空送のH型単品価格 等の副次価格
    is_provisional = Column(Boolean, default=False)    # 仮価格（要確定）
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class EstimateScaBody(Base):
    __tablename__ = "estimate_sca_bodies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_code = Column(String(50), nullable=False)
    diameter = Column(Integer)
    capacity = Column(Numeric(8, 1))
    base_price = Column(Numeric(15, 0))
    ab_kw = Column(Numeric(5, 2))
    sc_count = Column(Integer, default=1)
    sc1_kw = Column(Numeric(5, 2))
    sc2_kw = Column(Numeric(5, 2))
    rv1_model = Column(String(50))
    rv1_kw = Column(Numeric(5, 2))
    rv2_model = Column(String(50))
    rv2_kw = Column(Numeric(5, 2))
    rv2_price = Column(Numeric(15, 0))
    slope_sc = Column(String(20), default='傾斜SCなし')
    is_active = Column(Boolean, default=True)

class EstimatePlFan(Base):
    __tablename__ = "estimate_pl_fans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_code = Column(String(50), nullable=False)
    kw = Column(Numeric(6, 2))
    price = Column(Numeric(15, 0))
    is_active = Column(Boolean, default=True)

class EstimateCyclone(Base):
    __tablename__ = "estimate_cyclones"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_code = Column(String(50), nullable=False)
    shape = Column(String(50))
    material = Column(String(50))
    price = Column(Numeric(15, 0))
    is_active = Column(Boolean, default=True)

class EstimateAutoDamper(Base):
    __tablename__ = "estimate_auto_dampers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_code = Column(String(50), nullable=False)
    voltage = Column(String(50))
    price = Column(Numeric(15, 0))
    is_active = Column(Boolean, default=True)

class EstimateLaborItem(Base):
    __tablename__ = "estimate_labor_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(100))
    item_name = Column(String(200), nullable=False)
    unit = Column(String(50), default='人日')
    unit_price = Column(Numeric(15, 0))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


# =============================================
# 見積書
# =============================================
class QuotationHeader(Base):
    __tablename__ = "quotation_headers"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_no = Column(String(50), unique=True, nullable=False)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    child_no = Column(String(100))
    customer_name = Column(String(200))
    customer_contact = Column(String(100))     # 注文主の御担当者（例: 大江課長）
    delivery_name = Column(String(300))
    delivery_place = Column(String(300))       # 受渡場所（未入力時は納入先を流用）
    title = Column(String(500))
    delivery_terms = Column(String(200))       # 納入期限（御協議 等）
    payment_terms = Column(String(200))
    valid_until = Column(Date)
    valid_until_text = Column(String(50))      # 見積有効期限の相対表記（3ヶ月 等）。優先して表示
    tax_display = Column(String(20), default='included')  # included=税込表示 / excluded=税抜表示
    exclusions = Column(Text)                  # 御見積除外事項（1行1項目）
    issue_date = Column(Date)
    sales_person_name = Column(String(100))
    created_by_name = Column(String(100))      # 作成者（帳票の「作成」欄）
    approver_name = Column(String(100))        # 検印者（帳票の「検印」欄）
    # 承認ワークフロー（会議2026-07-17: 承認前は「draft」透かし・承認後に正式発行）
    approval_status = Column(String(20), default='none')  # none=未依頼 / pending=承認待ち / approved=承認済
    approval_requested_at = Column(DateTime)
    approved_at = Column(DateTime)
    subtotal = Column(Numeric(15, 0), default=0)
    discount_amount = Column(Numeric(15, 0), default=0)   # 出精値引（正の値で保持し、印字はマイナス表記）
    tax_rate = Column(Numeric(5, 2), default=10)
    tax_amount = Column(Numeric(15, 0), default=0)
    total_amount = Column(Numeric(15, 0), default=0)
    labor_total = Column(Numeric(15, 0), default=0)
    status = Column(String(50), default='draft')
    notes = Column(Text)
    internal_notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    line_items = relationship("QuotationLineItem", back_populates="quotation", cascade="all, delete-orphan")
    labor_details = relationship("QuotationLaborDetail", back_populates="quotation", cascade="all, delete-orphan")
    # 工番/単番の区分を引くために参照（区分の正は案件子ID側）
    project_order = relationship("ProjectOrder", foreign_keys=[project_order_id])


class QuotationLineItem(Base):
    __tablename__ = "quotation_line_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotation_headers.id", ondelete="CASCADE"), nullable=False)
    line_no = Column(Integer, nullable=False)
    section = Column(String(100))
    sub_section = Column(String(100))
    item_name = Column(String(500), nullable=False)
    spec_detail = Column(Text)
    quantity = Column(Numeric(10, 2), default=1)
    unit = Column(String(50), default='式')
    unit_price = Column(Numeric(15, 0), default=0)
    amount = Column(Numeric(15, 0), default=0)
    # 一式品の金額表示制御（会議2026-07-17: 構成部品は項目名のみ・金額非表示）
    hide_amount = Column(Boolean, default=False)   # True=金額欄を空欄で印字（合計には算入）
    amount_text = Column(String(50))               # 「含まず」等の文字列表示（設定時は単価0で運用）
    product_type = Column(String(50))
    spec_json = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

    quotation = relationship("QuotationHeader", back_populates="line_items")


class QuotationLaborDetail(Base):
    __tablename__ = "quotation_labor_details"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotation_headers.id", ondelete="CASCADE"), nullable=False)
    labor_item_id = Column(UUID(as_uuid=True), ForeignKey("estimate_labor_items.id"))
    item_name = Column(String(200), nullable=False)
    quantity = Column(Numeric(10, 2), default=0)
    unit = Column(String(50), default='人日')
    unit_price = Column(Numeric(15, 0), default=0)
    amount = Column(Numeric(15, 0), default=0)
    crane_type = Column(String(100))
    notes = Column(Text)
    sort_order = Column(Integer, default=0)

    quotation = relationship("QuotationHeader", back_populates="labor_details")


# =============================================
# 受注票
# =============================================
class OrderTicket(Base):
    __tablename__ = "order_tickets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_no = Column(String(50), unique=True, nullable=False)
    ticket_type = Column(String(20), nullable=False)  # koban / tanban
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    child_no = Column(String(100))
    quotation_id = Column(UUID(as_uuid=True), ForeignKey("quotation_headers.id"))
    order_date = Column(Date)
    total_amount = Column(Numeric(15, 0))
    customer_name = Column(String(200))
    delivery_name = Column(String(300))
    sales_person_name = Column(String(100))
    # 受注時項目（会議「次の手配」項目11）
    has_order_sheet = Column(Boolean)          # 注文書有無（True=有 / False=無 / NULL=未確認）
    has_drawing = Column(Boolean)              # 図面有無（True=有 / False=無 / NULL=未確認）
    has_contract = Column(Boolean)             # 契約書有無（True=有 / False=無 / NULL=未確認）
    delivery_date = Column(Date)               # 納期
    advance_payment = Column(Numeric(15, 0))   # 前受金額（旧・単一。NULL/0=なし）
    advance_payments = Column(JSON)            # 前受金 [{date, amount}] 最大3回（分割入金）
    shipping_method = Column(String(50))       # 出荷方法（トラック出荷/宅配出荷/井上納品/引取）
    # 部品手配・在庫マイナス（未 / 済 / NULL=未入力）
    parts_input_status = Column(String(10))    # 部品入力
    parts_order_status = Column(String(10))    # 注文
    stock_minus_status = Column(String(10))    # 在庫マイナス
    notes = Column(Text)
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime, server_default=func.now())

    quotation = relationship("QuotationHeader", foreign_keys=[quotation_id])
    project_order = relationship("ProjectOrder", foreign_keys=[project_order_id])


class OrderTicketFile(Base):
    """受注票の関連書類（注文書・契約書等のPDF）。
    Renderのディスクは再デプロイで消えるため、DBに直接保管する（1件10MBまで）。"""
    __tablename__ = "order_ticket_files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_ticket_id = Column(UUID(as_uuid=True), ForeignKey("order_tickets.id", ondelete="CASCADE"), nullable=False)
    file_kind = Column(String(30))             # 注文書 / 契約書 / 図面 / その他
    filename = Column(String(300), nullable=False)
    content_type = Column(String(100), default="application/pdf")
    file_size = Column(Integer, default=0)
    data = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now())


# =============================================
# 手配書（子IDに紐づく）
# =============================================
class CraneArrangement(Base):
    """クレーン・作業車等 手配書"""
    __tablename__ = "crane_arrangements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    child_no = Column(String(100))
    site_name = Column(String(300))       # 現場名
    site_address = Column(String(500))    # 住所
    site_tel = Column(String(50))         # TEL
    site_contact = Column(String(100))    # 現場ご担当者
    vendor_name = Column(String(200))     # 依頼業者
    vendor_branch = Column(String(100))   # 営業所
    vendor_contact = Column(String(100))  # 業者担当
    vendor_tel = Column(String(50))
    vendor_fax = Column(String(50))
    order_no = Column(String(100))        # 注番
    items_json = Column(JSON)             # 明細行リスト
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ShippingArrangement(Base):
    """送り状（トラック手配）"""
    __tablename__ = "shipping_arrangements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    child_no = Column(String(100))
    dest_name = Column(String(300))       # 送り先
    dest_address = Column(String(500))
    dest_tel = Column(String(50))
    carrier_name = Column(String(200))    # 運送業者
    carrier_contact = Column(String(100))
    carrier_tel = Column(String(50))
    order_no = Column(String(100))
    items_json = Column(JSON)             # 明細行リスト
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ArrangementVendor(Base):
    """手配業者マスタ（クレーン業者・運送業者等）"""
    __tablename__ = "arrangement_vendors"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(50))              # クレーン・作業車 / 運送（トラック） / その他
    name = Column(String(200), nullable=False) # 業者名
    branch = Column(String(100))               # 営業所/支店
    contact_person = Column(String(100))       # 担当
    phone = Column(String(50))                 # TEL
    fax = Column(String(50))                   # FAX
    postal_code = Column(String(20))
    address = Column(String(500))
    notes = Column(Text)
    source_tag = Column(String(50))            # 取込元タグ（一括削除用）
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class HotelArrangement(Base):
    """宿泊予約票"""
    __tablename__ = "hotel_arrangements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    child_no = Column(String(100))
    site_name = Column(String(300))       # 現場
    site_address = Column(String(500))
    items_json = Column(JSON)             # 明細行リスト（ホテルごと）
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# =============================================
# ① 仕入（発注）管理
# =============================================

class MaterialMaster(Base):
    """部材マスタ"""
    __tablename__ = "material_masters"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_code = Column(String(50), unique=True, nullable=False)
    material_name = Column(String(300), nullable=False)
    unit = Column(String(20), default="個")
    default_supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    standard_lead_days = Column(Integer, default=14)
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    default_supplier = relationship("Supplier", foreign_keys=[default_supplier_id])

class BomItem(Base):
    """BOMマスタ（製品型番→必要部材）"""
    __tablename__ = "bom_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_type = Column(String(50), nullable=False)   # BFR, SCA, SRR, FLT, CY, LRG etc.
    model_no = Column(String(100), nullable=False)       # 3X6, 675, 2000X2 etc.
    material_id = Column(UUID(as_uuid=True), ForeignKey("material_masters.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False, default=1)
    unit = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    material = relationship("MaterialMaster")

class MaterialPurchaseOrder(Base):
    """発注書ヘッダー（発注番号単位。1案件子IDに複数発注。仕入先ごとに1発注書）"""
    __tablename__ = "material_purchase_orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_no = Column(String(80), unique=True, nullable=False)          # 発注番号（= 子ID-内訳番号）
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))  # 案件子ID
    breakdown_no = Column(String(50))                               # 見積内訳番号（例: 1-1）
    breakdown_name = Column(String(500))                            # 内訳品名（発注書件名の元）
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"))            # 発注先
    order_date = Column(Date)                                        # 注文日
    delivery_place = Column(String(300))                            # 納入場所
    seiban = Column(String(100))                                    # 製番
    title = Column(String(500))                                     # 件名
    status = Column(String(20), default="作成中")                  # 作成中/発注済/一部入荷/入荷済/キャンセル
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    project_order = relationship("ProjectOrder")
    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    lines = relationship("MaterialOrder", back_populates="purchase_order", cascade="all, delete-orphan")


class MaterialOrder(Base):
    """部材発注（明細）"""
    __tablename__ = "material_orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_no = Column(String(100))                                  # 発注NO（採番・旧）
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("material_purchase_orders.id"))  # 発注書ヘッダー
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    project_unit_id = Column(UUID(as_uuid=True), ForeignKey("project_units.id"))  # 案件ユニット紐付け
    material_id = Column(UUID(as_uuid=True), ForeignKey("material_masters.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"))
    order_qty = Column(Numeric(10, 3))
    unit_price = Column(Numeric(15, 2))
    order_date = Column(Date)
    due_date = Column(Date)
    received_date = Column(Date)
    status = Column(String(20), default="未発注")  # 未発注/発注済/入荷済
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    project_order = relationship("ProjectOrder")
    material = relationship("MaterialMaster")
    supplier = relationship("Supplier", foreign_keys=[supplier_id])
    purchase_order = relationship("MaterialPurchaseOrder", back_populates="lines")


class MaterialStockMovement(Base):
    """部材在庫の入出庫履歴（在庫数 = quantityの合計。入荷=+ / 利用・引当=- / 調整=±）"""
    __tablename__ = "material_stock_movements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(UUID(as_uuid=True), ForeignKey("material_masters.id"), nullable=False)
    movement_type = Column(String(20), nullable=False)   # 入荷 / 利用 / 引当 / 調整
    quantity = Column(Numeric(12, 3), nullable=False)     # 符号付き（+入庫 / -出庫）
    movement_date = Column(Date)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("material_purchase_orders.id"))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    material = relationship("MaterialMaster")
    project_order = relationship("ProjectOrder")

# =============================================
# ② 製造計画
# =============================================

class ProductionCapacity(Base):
    """生産能力マスタ（月別）"""
    __tablename__ = "production_capacity"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    factory = Column(String(100), default="小牧")
    fiscal_year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    work_days = Column(Integer, default=20)
    regular_workers = Column(Integer, default=8)
    temp_workers = Column(Integer, default=5)
    hours_per_day = Column(Integer, default=8)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ProductHours(Base):
    """製品所要工数マスタ"""
    __tablename__ = "product_hours"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_type = Column(String(50), nullable=False)
    model_no = Column(String(100), nullable=False)
    required_hours = Column(Numeric(10, 1), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ManufacturingPlan(Base):
    """製造計画"""
    __tablename__ = "manufacturing_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"), nullable=False)
    breakdown_no = Column(String(50))          # 見積内訳番号（例: 1-1）。ユニット単位計画の識別
    unit_name = Column(String(500))            # ユニット品名（見積内訳の品名）
    is_primary = Column(Boolean, default=True) # 本体ユニット（工数の種別平均フォールバック対象）。副ユニット=False
    product_type = Column(String(50))
    model_no = Column(String(100))
    planned_start = Column(Date)
    planned_end = Column(Date)
    actual_start = Column(Date)
    actual_end = Column(Date)
    assigned_to = Column(String(100))
    status = Column(String(20), default="未着手")  # 未着手/製造中/完了
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    project_order = relationship("ProjectOrder")


# =============================================
# ③ 工程管理
# =============================================

class ProcessTemplate(Base):
    """工程テンプレート（製品種別ごとの標準工程）"""
    __tablename__ = "process_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_type = Column(String(50))          # BFR, SCA, SRR, FLT, CY, LRG etc.
    template_name = Column(String(200), nullable=False)
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    steps = relationship("ProcessTemplateStep", back_populates="template", cascade="all, delete-orphan", order_by="ProcessTemplateStep.step_no")

class ProcessTemplateStep(Base):
    """工程テンプレートステップ"""
    __tablename__ = "process_template_steps"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("process_templates.id", ondelete="CASCADE"), nullable=False)
    step_no = Column(Integer, nullable=False)
    step_name = Column(String(200), nullable=False)
    offset_start_days = Column(Integer, default=-7)   # 納期からの開始オフセット（負=前）
    duration_days = Column(Integer, default=1)
    equipment = Column(String(200))                    # 使用機材（レッカー車等）
    color = Column(String(20), default="#3b82f6")
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    template = relationship("ProcessTemplate", back_populates="steps")

class WorkSchedule(Base):
    """工程表ヘッダー"""
    __tablename__ = "work_schedules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id"))
    customer_name = Column(String(300))        # 納入先
    delivery_name = Column(String(300))        # 御担当者
    work_name = Column(String(500))            # 工事名
    work_no = Column(String(100))              # 工番
    responsible_person = Column(String(100))   # 担当者
    work_year = Column(Integer)                # 工程年
    work_month = Column(Integer)               # 工程月
    delivery_date = Column(Date)               # 納期
    created_date = Column(Date)                # 作成日
    notes = Column(Text)
    status = Column(String(20), default="作成中")   # 作成中/確定/発行済
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    project_order = relationship("ProjectOrder")
    items = relationship("WorkScheduleItem", back_populates="schedule", cascade="all, delete-orphan", order_by="WorkScheduleItem.step_no")

class WorkScheduleItem(Base):
    """工程表明細（ガントバー1行）"""
    __tablename__ = "work_schedule_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("work_schedules.id", ondelete="CASCADE"), nullable=False)
    step_no = Column(Integer, nullable=False)
    row_type = Column(String(20), default="task")    # task / equipment / note / blank
    step_name = Column(String(300), nullable=False)
    start_day = Column(Integer)                       # 開始日（旧・月内の日）
    end_day = Column(Integer)                         # 終了日（旧・月内の日）
    start_date = Column(Date)                         # 開始日（絶対日付・複数月対応）
    end_date = Column(Date)                           # 終了日（絶対日付・複数月対応）
    equipment = Column(String(200))                   # 機材情報
    color = Column(String(20), default="#3b82f6")
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    schedule = relationship("WorkSchedule", back_populates="items")


# =============================================
# ④ 製品BOM階層マスタ（製品 → ユニット(型式) → 部品(原材料)）
# =============================================

class ProductMaster(Base):
    """製品マスタ（本体系。BFR本体・SCA本体 等）"""
    __tablename__ = "product_masters"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_code = Column(String(50), unique=True, nullable=False)   # 製品コード
    product_name = Column(String(300), nullable=False)               # 製品名
    product_type = Column(String(50))                                # 種別 BFR/SCA/SRR/FLT/CY/LRG
    model_no = Column(String(100))                                   # 代表型式
    standard_price = Column(Numeric(15, 0))                          # 標準販売単価（見積パターン由来）
    standard_hours = Column(Numeric(10, 1))                          # 標準所要工数
    spec_json = Column(JSON)                                         # 仕様（風量・フィルタ等）
    estimate_ref = Column(String(100))                               # 既存見積パターン紐付（model_code）
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    units = relationship("ProductUnitBom", back_populates="product", cascade="all, delete-orphan")


class UnitMaster(Base):
    """ユニットマスタ（型式。ファン・RV・サイクロン・ダンパー 等）"""
    __tablename__ = "unit_masters"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_code = Column(String(50), unique=True, nullable=False)      # ユニットコード
    unit_name = Column(String(300), nullable=False)                  # ユニット名
    unit_type = Column(String(50))                                   # 種別 ファン/RV/サイクロン/本体...
    model_no = Column(String(100))                                   # 型式
    standard_price = Column(Numeric(15, 0))                          # 標準販売単価（見積パターン由来）
    standard_hours = Column(Numeric(10, 1))                          # 標準所要工数
    spec_json = Column(JSON)
    estimate_ref = Column(String(100))                               # 既存見積パターン紐付
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    materials = relationship("UnitMaterialBom", back_populates="unit", cascade="all, delete-orphan")


class ProductUnitBom(Base):
    """製品構成BOM（製品 → ユニット, 員数）"""
    __tablename__ = "product_unit_boms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("product_masters.id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("unit_masters.id"), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False, default=1)     # 員数
    sort_order = Column(Integer, default=0)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    product = relationship("ProductMaster", back_populates="units")
    unit = relationship("UnitMaster")


class UnitMaterialBom(Base):
    """ユニット構成BOM（ユニット → 部品, 員数）"""
    __tablename__ = "unit_material_boms"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("unit_masters.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("material_masters.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False, default=1)     # 員数
    sort_order = Column(Integer, default=0)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    unit = relationship("UnitMaster", back_populates="materials")
    material = relationship("MaterialMaster")


# ---- 案件適用層（案件子IDごとの実体・NO採番）----

class ProjectProduct(Base):
    """案件製品（製品NO）"""
    __tablename__ = "project_products"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_no = Column(String(100), unique=True, nullable=False)    # 製品NO
    project_order_id = Column(UUID(as_uuid=True), ForeignKey("project_orders.id", ondelete="CASCADE"), nullable=False)
    product_master_id = Column(UUID(as_uuid=True), ForeignKey("product_masters.id"))
    product_name = Column(String(300))
    product_type = Column(String(50))
    model_no = Column(String(100))
    quantity = Column(Numeric(10, 2), default=1)
    status = Column(String(20), default="計画")     # 計画/製造中/完了
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    project_order = relationship("ProjectOrder")
    product_master = relationship("ProductMaster")
    units = relationship("ProjectUnit", back_populates="project_product", cascade="all, delete-orphan")


class ProjectUnit(Base):
    """案件ユニット（ユニットNO）"""
    __tablename__ = "project_units"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_no = Column(String(100), unique=True, nullable=False)       # ユニットNO
    project_product_id = Column(UUID(as_uuid=True), ForeignKey("project_products.id", ondelete="CASCADE"), nullable=False)
    unit_master_id = Column(UUID(as_uuid=True), ForeignKey("unit_masters.id"))
    unit_name = Column(String(300))
    unit_type = Column(String(50))
    model_no = Column(String(100))
    quantity = Column(Numeric(10, 2), default=1)
    status = Column(String(20), default="計画")     # 計画/製造中/完了
    assigned_to = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    project_product = relationship("ProjectProduct", back_populates="units")
    unit_master = relationship("UnitMaster")


class TeamSchedule(Base):
    """週間スケジュール（従業員×日付×午前/午後の予定）"""
    __tablename__ = "team_schedules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100))           # 従業員/ユーザーのID（文字列保持）
    full_name = Column(String(100))         # 表示名
    date = Column(Date, nullable=False)
    slot = Column(String(10), nullable=False)  # am / pm
    title = Column(String(500))
    color = Column(String(120))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
