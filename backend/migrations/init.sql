-- =============================================
-- 販売管理・見積管理システム DB初期化
-- 井上電設株式会社向け
-- =============================================

-- 拡張機能
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- ユーザー・権限
-- =============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'staff', -- admin, manager, staff
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- 顧客マスタ
-- =============================================
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    name_kana VARCHAR(200),
    postal_code VARCHAR(10),
    prefecture VARCHAR(50),
    address VARCHAR(500),
    phone VARCHAR(50),
    fax VARCHAR(50),
    email VARCHAR(255),
    contact_person VARCHAR(100),
    payment_terms VARCHAR(200), -- 支払条件
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- 仕入先マスタ
-- =============================================
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supplier_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    name_kana VARCHAR(200),
    postal_code VARCHAR(10),
    address VARCHAR(500),
    phone VARCHAR(50),
    email VARCHAR(255),
    contact_person VARCHAR(100),
    payment_terms VARCHAR(200),
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- 商品・製品マスタ
-- =============================================
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(300) NOT NULL,
    product_type VARCHAR(50),      -- BFQ, BFR, SCA, BFC, RV, 集塵ダクト, 他
    category VARCHAR(100),
    unit VARCHAR(50) DEFAULT '式',
    standard_price DECIMAL(15,0) DEFAULT 0,
    cost_price DECIMAL(15,0) DEFAULT 0,
    description TEXT,
    spec_json JSONB,               -- 仕様情報（kW, Hz, 風量等）
    stock_quantity DECIMAL(10,2) DEFAULT 0,
    min_stock_quantity DECIMAL(10,2) DEFAULT 0,
    supplier_id UUID REFERENCES suppliers(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 製品オプションマスタ（シェーカー・制御盤・RV等）
CREATE TABLE product_options (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    option_code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    option_type VARCHAR(100),      -- シェーカー, 制御盤, スイッチ, RV, etc
    applicable_product_type VARCHAR(50), -- BFQ, BFR, SCA, etc
    price DECIMAL(15,0) DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- 在庫管理
-- =============================================
CREATE TABLE inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id),
    quantity DECIMAL(10,2) DEFAULT 0,
    location VARCHAR(200),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id),
    movement_type VARCHAR(50) NOT NULL, -- in(入庫), out(出庫), adjust(調整)
    quantity DECIMAL(10,2) NOT NULL,
    unit_price DECIMAL(15,0),
    reference_type VARCHAR(50),         -- order, purchase_order, manual
    reference_id UUID,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- 見積管理
-- =============================================
CREATE TABLE quotations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_no VARCHAR(50) UNIQUE NOT NULL, -- 見積番号 例: Q2026-0001
    customer_id UUID NOT NULL REFERENCES customers(id),
    title VARCHAR(500),                        -- 件名
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_until DATE,                          -- 有効期限
    status VARCHAR(50) DEFAULT 'draft',        -- draft, submitted, approved, rejected, converted
    subtotal DECIMAL(15,0) DEFAULT 0,
    tax_rate DECIMAL(5,2) DEFAULT 10.00,
    tax_amount DECIMAL(15,0) DEFAULT 0,
    total_amount DECIMAL(15,0) DEFAULT 0,
    delivery_terms VARCHAR(500),               -- 納期
    payment_terms VARCHAR(500),                -- 支払条件
    delivery_location VARCHAR(500),            -- 納入場所
    notes TEXT,
    internal_notes TEXT,                       -- 社内メモ
    created_by UUID REFERENCES users(id),
    updated_by UUID REFERENCES users(id),
    submitted_at TIMESTAMP,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE quotation_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_id UUID NOT NULL REFERENCES quotations(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,                  -- 行番号
    product_id UUID REFERENCES products(id),
    item_name VARCHAR(500) NOT NULL,
    description TEXT,                          -- 仕様詳細
    quantity DECIMAL(10,2) DEFAULT 1,
    unit VARCHAR(50) DEFAULT '式',
    unit_price DECIMAL(15,0) DEFAULT 0,
    amount DECIMAL(15,0) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE quotation_item_options (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_item_id UUID NOT NULL REFERENCES quotation_items(id) ON DELETE CASCADE,
    option_id UUID REFERENCES product_options(id),
    option_name VARCHAR(200) NOT NULL,
    price DECIMAL(15,0) DEFAULT 0,
    notes TEXT
);

-- =============================================
-- 受注管理
-- =============================================
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_no VARCHAR(50) UNIQUE NOT NULL,      -- 受注番号 例: SO2026-0001
    quotation_id UUID REFERENCES quotations(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    title VARCHAR(500),
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    delivery_date DATE,
    status VARCHAR(50) DEFAULT 'received',     -- received, in_progress, shipped, delivered, completed, cancelled
    subtotal DECIMAL(15,0) DEFAULT 0,
    tax_rate DECIMAL(5,2) DEFAULT 10.00,
    tax_amount DECIMAL(15,0) DEFAULT 0,
    total_amount DECIMAL(15,0) DEFAULT 0,
    delivery_location VARCHAR(500),
    payment_terms VARCHAR(500),
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    product_id UUID REFERENCES products(id),
    item_name VARCHAR(500) NOT NULL,
    description TEXT,
    quantity DECIMAL(10,2) DEFAULT 1,
    unit VARCHAR(50) DEFAULT '式',
    unit_price DECIMAL(15,0) DEFAULT 0,
    amount DECIMAL(15,0) DEFAULT 0,
    notes TEXT
);

-- =============================================
-- 発注管理（仕入）
-- =============================================
CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_order_no VARCHAR(50) UNIQUE NOT NULL, -- 発注番号 例: PO2026-0001
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    order_id UUID REFERENCES orders(id),           -- 関連受注
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_date DATE,
    status VARCHAR(50) DEFAULT 'draft',            -- draft, sent, partial, received, cancelled
    subtotal DECIMAL(15,0) DEFAULT 0,
    tax_rate DECIMAL(5,2) DEFAULT 10.00,
    tax_amount DECIMAL(15,0) DEFAULT 0,
    total_amount DECIMAL(15,0) DEFAULT 0,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE purchase_order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    product_id UUID REFERENCES products(id),
    item_name VARCHAR(500) NOT NULL,
    quantity DECIMAL(10,2) DEFAULT 1,
    unit VARCHAR(50) DEFAULT '式',
    unit_price DECIMAL(15,0) DEFAULT 0,
    amount DECIMAL(15,0) DEFAULT 0,
    received_quantity DECIMAL(10,2) DEFAULT 0,
    notes TEXT
);

-- =============================================
-- 請求書
-- =============================================
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_no VARCHAR(50) UNIQUE NOT NULL,    -- 請求番号 例: INV2026-0001
    order_id UUID NOT NULL REFERENCES orders(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    issue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    due_date DATE,
    status VARCHAR(50) DEFAULT 'draft',        -- draft, sent, paid, overdue, cancelled
    subtotal DECIMAL(15,0) DEFAULT 0,
    tax_rate DECIMAL(5,2) DEFAULT 10.00,
    tax_amount DECIMAL(15,0) DEFAULT 0,
    total_amount DECIMAL(15,0) DEFAULT 0,
    paid_amount DECIMAL(15,0) DEFAULT 0,
    paid_at TIMESTAMP,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- インデックス
-- =============================================
CREATE INDEX idx_quotations_customer ON quotations(customer_id);
CREATE INDEX idx_quotations_status ON quotations(status);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_purchase_orders_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_stock_movements_product ON stock_movements(product_id);
CREATE INDEX idx_invoices_order ON invoices(order_id);

-- =============================================
-- 初期データ（管理者ユーザー）
-- パスワード: admin1234 (本番では必ず変更)
-- =============================================
INSERT INTO users (email, hashed_password, full_name, role)
VALUES ('admin@inoue-densen.co.jp', '$2b$12$placeholder_hash', '管理者', 'admin');

-- 製品タイプ初期データ
INSERT INTO products (product_code, name, product_type, unit, standard_price, description) VALUES
('BFQ3', 'バグフィルタ集塵機 BFQ3', 'BFQ', '台', 510000, '排風機2.2kW 1400Lホッパ フィルター14本'),
('BFQ5', 'バグフィルタ集塵機 BFQ5', 'BFQ', '台', 640000, '排風機3.7kW 1400Lホッパ フィルター25本'),
('BFQ7', 'バグフィルタ集塵機 BFQ7', 'BFQ', '台', 0, '排風機5.5kW 1400Lホッパ フィルター36本'),
('BFQ10V', 'バグフィルタ集塵機 BFQ10V', 'BFQ', '台', 1140000, '排風機7.5kW 2000Lホッパ フィルター36本'),
('BFQ15V', 'バグフィルタ集塵機 BFQ15V', 'BFQ', '台', 1540000, '排風機11kW 2000Lホッパ フィルター42本'),
('SCA30', '定量排出装置 SCA30 φ3000', 'SCA', '式', 3700000, '円筒型φ3000 収容量約20m3'),
('SCA400', '定量排出装置 SCA400 φ4000', 'SCA', '式', 5450000, '円筒型φ4000 収容量約50m3'),
('SCA500', '定量排出装置 SCA500 φ5000', 'SCA', '式', 8200000, '円筒型φ5000 収容量約100m3');

INSERT INTO product_options (option_code, name, option_type, applicable_product_type, price) VALUES
('OPT-SHAKER-BFQ3', '電動シェーキング BFQ3', 'シェーカー', 'BFQ', 146000),
('OPT-SHAKER-BFQ5', '電動シェーキング BFQ5', 'シェーカー', 'BFQ', 146000),
('OPT-RV-20x35', 'ロータリーバルブ RV20×35 0.2kW', 'RV', 'BFQ', 250000),
('OPT-RV-25x40', 'ロータリーバルブ RV25×40 0.2kW', 'RV', 'BFQ', 290000),
('OPT-RV-25x60', 'ロータリーバルブ RV25×60 0.4kW', 'RV', 'BFQ', 320000),
('OPT-CB-BFQ3', 'ケースブレーカ NCD-30 3P15', '制御盤', 'BFQ', 8000),
('OPT-FAN-EXT', '外部ファン運転中信号', '追加オプション', 'BFQ', 6500);



-- =============================================
-- 案件管理（親）DROP & RECREATE
-- =============================================
DROP TABLE IF EXISTS project_orders CASCADE;
DROP TABLE IF EXISTS projects CASCADE;

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- 識別
    project_no VARCHAR(50) UNIQUE NOT NULL,   -- 案件ID_親 例: 260010
    seq_no VARCHAR(10),                        -- 連番 例: 0010

    -- 基本情報
    project_name VARCHAR(500),                 -- 案件名
    project_summary TEXT,                      -- 案件概要

    -- 顧客（親は2軸）
    customer_code_1 VARCHAR(50),               -- 顧客ID_1（代理店ID）
    customer_name_1 VARCHAR(200),              -- 顧客名_1（代理店名）
    customer_code_2 VARCHAR(50),               -- 顧客ID_2（エンドユーザーID）
    customer_name_2 VARCHAR(200),              -- 顧客名_2（エンドユーザー名）

    -- 営業担当
    sales_person_name VARCHAR(100),            -- 自社営業担当
    sales_person_code VARCHAR(50),             -- 自社営業担当者ID

    -- ステータス・商流
    status VARCHAR(50) DEFAULT '営業中',       -- 営業中, 受注, 受注済, 失注
    distribution_type VARCHAR(50),             -- 商流判定: 直接, 代理店

    -- 金額
    budget_amount DECIMAL(15,0),               -- 予算金額
    estimated_sales_total DECIMAL(15,0),       -- 見込売上合計（仕切りベース）
    final_order_amount DECIMAL(15,0),          -- 最終受注金額
    cost_price DECIMAL(15,0),                  -- 案件原価
    profit_amount DECIMAL(15,0),               -- 利益額
    profit_rate DECIMAL(7,4),                  -- 利益率

    -- 日程
    inquiry_date DATE,                         -- 引き合い日
    sales_date DATE,                           -- 顧客納期/売上計上日
    drawing_request_date DATE,                 -- 社内出図希望日
    order_date DATE,                           -- 受注日
    expected_order_date DATE,                  -- 受注予定日
    expected_shipment_date DATE,               -- 出荷予定日
    created_date DATE,                         -- 作成日

    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- 案件管理（子）: 受注NO_子 単位
-- =============================================
CREATE TABLE project_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- 識別
    child_no VARCHAR(100) UNIQUE NOT NULL,     -- 案件ID_子 例: 260010_02
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    project_no VARCHAR(50) NOT NULL,           -- 案件ID_親（検索用）

    -- 基本情報
    project_name VARCHAR(500),                 -- 案件名
    project_summary TEXT,                      -- 案件概要

    -- 顧客（子は顧客1件＋代理店）
    customer_code VARCHAR(50),                 -- 顧客ID
    customer_name VARCHAR(200),                -- 顧客名（エンドユーザー）
    agency_code VARCHAR(50),                   -- 代理店ID
    agency_name VARCHAR(200),                  -- 代理店名

    -- 営業担当
    sales_person_name VARCHAR(100),            -- 自社営業担当
    sales_person_code VARCHAR(50),             -- 自社営業担当ID

    -- ステータス（親から参照・子でも持つ）
    status VARCHAR(50),                        -- 案件ステータス（親参照）

    -- 金額
    quotation_amount DECIMAL(15,0),            -- 見積金額（見積書引用）
    budget_amount DECIMAL(15,0),               -- 予算金額（親参照）

    -- 日程
    sales_date DATE,                           -- 顧客納期/売上計上日
    inquiry_date DATE,                         -- 引き合い日（親参照）
    order_date DATE,                           -- 受注日
    expected_order_date DATE,                  -- 受注予定日
    shipment_date DATE,                        -- 出荷日
    expected_shipment_date DATE,               -- 出荷予定日

    -- 見積紐付け（複数行対応のため別テーブル推奨だが、まず主要1件）
    quotation_no VARCHAR(50),                  -- 見積NO（主）
    quotation_total DECIMAL(15,0),             -- 見積総計（主）
    quotation_issue_date DATE,                 -- 見積発行日（主）

    -- 受注紐付け（内部）
    quotation_id UUID REFERENCES quotations(id),
    order_id UUID REFERENCES orders(id),

    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 見積紐付け（子に複数の見積が紐づく場合用）
CREATE TABLE project_order_quotations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_order_id UUID NOT NULL REFERENCES project_orders(id) ON DELETE CASCADE,
    quotation_no VARCHAR(50),
    quotation_total DECIMAL(15,0),
    quotation_issue_date DATE,
    quotation_id UUID REFERENCES quotations(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_project_orders_project ON project_orders(project_id);
CREATE INDEX idx_project_orders_status ON project_orders(status);
CREATE INDEX idx_project_orders_customer ON project_orders(customer_code);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_sales_person ON projects(sales_person_code);
