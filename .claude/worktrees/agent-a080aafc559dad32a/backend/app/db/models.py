from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Date, Numeric, Integer, Text, ForeignKey, JSON
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

    status = Column(String(50))                                     # ステータス（親参照）

    quotation_amount = Column(Numeric(15, 0))                       # 見積金額（見積書引用）
    budget_amount = Column(Numeric(15, 0))                          # 予算金額（親参照）

    sales_date = Column(Date)                                       # 顧客納期/売上計上日
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
    delivery_name = Column(String(300))
    title = Column(String(500))
    delivery_terms = Column(String(200))
    payment_terms = Column(String(200))
    valid_until = Column(Date)
    issue_date = Column(Date)
    sales_person_name = Column(String(100))
    subtotal = Column(Numeric(15, 0), default=0)
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
    notes = Column(Text)
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime, server_default=func.now())

    quotation = relationship("QuotationHeader", foreign_keys=[quotation_id])


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
