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
