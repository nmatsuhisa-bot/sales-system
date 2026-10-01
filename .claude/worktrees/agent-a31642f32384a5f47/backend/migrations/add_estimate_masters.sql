-- =============================================
-- 見積パターンマスタ（BFR本体）
-- =============================================
CREATE TABLE estimate_bfr_bodies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_code VARCHAR(50) NOT NULL,        -- 型式 例: BFR3×4
    base_price DECIMAL(15,0),               -- 価格（仮）
    airflow INTEGER,                        -- 処理風量 m3/min
    filter_length VARCHAR(50),              -- フィルター長さ
    filter_type VARCHAR(50),                -- フィルター種類（標準/帯電防止品）
    filter_price DECIMAL(15,0),             -- フィルター価格
    filter_count INTEGER,                   -- フィルター本数
    is_active BOOLEAN DEFAULT TRUE
);

-- BFRターボファンマスタ
CREATE TABLE estimate_bfr_fans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bfr_model VARCHAR(50) NOT NULL,
    fan_model VARCHAR(50),                  -- 型式 例: TVS11kw
    price DECIMAL(15,0),
    quantity INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

-- BFR ロータリーバルブマスタ
CREATE TABLE estimate_bfr_rvs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bfr_model VARCHAR(50) NOT NULL,
    rv_model VARCHAR(50),                   -- 型式 例: RV25×40
    kw DECIMAL(5,2),
    price DECIMAL(15,0),
    quantity INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

-- SCA/SCDマスタ
CREATE TABLE estimate_sca_bodies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_code VARCHAR(50) NOT NULL,        -- 型式 例: SCA30
    diameter INTEGER,                       -- 円筒径 mm
    capacity DECIMAL(8,1),                  -- 収容量 m3
    base_price DECIMAL(15,0),
    ab_kw DECIMAL(5,2),                     -- アーチブレーカkW
    sc_count INTEGER DEFAULT 1,             -- スクリューコンベヤ台数
    sc1_kw DECIMAL(5,2),
    sc2_kw DECIMAL(5,2),
    rv1_model VARCHAR(50),
    rv1_kw DECIMAL(5,2),
    rv2_model VARCHAR(50),
    rv2_kw DECIMAL(5,2),
    rv2_price DECIMAL(15,0),
    slope_sc VARCHAR(20) DEFAULT '傾斜SCなし',  -- 傾斜SC 有/なし
    is_active BOOLEAN DEFAULT TRUE
);

-- 空送（プレートファン）マスタ
CREATE TABLE estimate_pl_fans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_code VARCHAR(50) NOT NULL,        -- 例: PL200
    kw DECIMAL(6,2),
    price DECIMAL(15,0),
    is_active BOOLEAN DEFAULT TRUE
);

-- 空送（サイクロン）マスタ
CREATE TABLE estimate_cyclones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_code VARCHAR(50) NOT NULL,
    shape VARCHAR(50),                      -- 標準/シュート式
    material VARCHAR(50),                   -- 鉄/SUS
    price DECIMAL(15,0),
    is_active BOOLEAN DEFAULT TRUE
);

-- オートダンパマスタ
CREATE TABLE estimate_auto_dampers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_code VARCHAR(50) NOT NULL,        -- 例: ADB200, ADC225
    voltage VARCHAR(50),
    price DECIMAL(15,0),
    is_active BOOLEAN DEFAULT TRUE
);

-- =============================================
-- 社内工数マスタ
-- =============================================
CREATE TABLE estimate_labor_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100),                  -- カテゴリ
    item_name VARCHAR(200) NOT NULL,        -- 作業項目
    unit VARCHAR(50) DEFAULT '人日',        -- 単位
    unit_price DECIMAL(15,0),              -- 単価
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- 初期データ：社内工数マスタ
INSERT INTO estimate_labor_items (category, item_name, unit, unit_price, sort_order) VALUES
('工事作業', '準備', '人日', 40000, 1),
('工事作業', '既設撤去', '人日', 40000, 2),
('工事作業', '組立', '人日', 40000, 3),
('工事作業', '屋外ダクト', '人日', 40000, 4),
('工事作業', '空気輸送', '人日', 40000, 5),
('工事作業', '屋内ダクト', '人日', 40000, 6),
('工事作業', '仕上げ', '人日', 40000, 7),
('工事作業', '帰社', '人日', 40000, 8),
('重機', 'レッカー(10t普)', '台', 100000, 10),
('重機', 'レッカー(10t低)', '台', 105000, 11),
('重機', '高所作業車', '台', 50000, 12),
('宿泊', '宿泊費', '泊', 7000, 20),
('運送', '運送交通費', '式', 1, 30),
('消耗品', '工事消耗品', '式', 1, 31),
('試運転', '試運転調整費', '式', 1, 32),
('諸経費', '諸経費', '式', 1, 33);

-- =============================================
-- 見積書テーブル（子IDに紐付け）
-- =============================================
CREATE TABLE quotation_headers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_no VARCHAR(50) UNIQUE NOT NULL,  -- 見積番号
    project_order_id UUID REFERENCES project_orders(id),
    child_no VARCHAR(100),                      -- 子ID

    -- ヘッダー情報（案件から参照）
    customer_name VARCHAR(200),
    delivery_name VARCHAR(300),               -- 納入先
    title VARCHAR(500),                       -- 件名
    delivery_terms VARCHAR(200),              -- 納期
    payment_terms VARCHAR(200),              -- 支払条件
    valid_until DATE,                         -- 有効期限
    issue_date DATE DEFAULT CURRENT_DATE,
    sales_person_name VARCHAR(100),

    -- 金額
    subtotal DECIMAL(15,0) DEFAULT 0,
    tax_rate DECIMAL(5,2) DEFAULT 10,
    tax_amount DECIMAL(15,0) DEFAULT 0,
    total_amount DECIMAL(15,0) DEFAULT 0,

    -- 社内工数合計
    labor_total DECIMAL(15,0) DEFAULT 0,

    status VARCHAR(50) DEFAULT 'draft',       -- draft/submitted/approved
    notes TEXT,
    internal_notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 見積明細（積み上げ）
CREATE TABLE quotation_line_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_id UUID NOT NULL REFERENCES quotation_headers(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    section VARCHAR(100),                     -- 大分類 例: 1.集塵装置
    sub_section VARCHAR(100),                 -- 小分類 例: 1.1 BFR本体
    item_name VARCHAR(500) NOT NULL,
    spec_detail TEXT,                         -- 仕様詳細
    quantity DECIMAL(10,2) DEFAULT 1,
    unit VARCHAR(50) DEFAULT '式',
    unit_price DECIMAL(15,0) DEFAULT 0,
    amount DECIMAL(15,0) DEFAULT 0,
    product_type VARCHAR(50),                 -- BFQ/BFR/SCA/空送/工事/他
    spec_json JSONB,                          -- 選択仕様JSON（kW・型式等）
    created_at TIMESTAMP DEFAULT NOW()
);

-- 社内工数明細
CREATE TABLE quotation_labor_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_id UUID NOT NULL REFERENCES quotation_headers(id) ON DELETE CASCADE,
    labor_item_id UUID REFERENCES estimate_labor_items(id),
    item_name VARCHAR(200) NOT NULL,
    quantity DECIMAL(10,2) DEFAULT 0,
    unit VARCHAR(50) DEFAULT '人日',
    unit_price DECIMAL(15,0) DEFAULT 0,
    amount DECIMAL(15,0) DEFAULT 0,
    crane_type VARCHAR(100),                  -- レッカー種別
    notes TEXT,
    sort_order INTEGER DEFAULT 0
);

-- =============================================
-- 受注票テーブル
-- =============================================
CREATE TABLE order_tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_no VARCHAR(50) UNIQUE NOT NULL,    -- 受注票番号
    ticket_type VARCHAR(20) NOT NULL,         -- koban（工番）/ tanban（単番）
    project_order_id UUID REFERENCES project_orders(id),
    child_no VARCHAR(100),
    quotation_id UUID REFERENCES quotation_headers(id),
    order_date DATE,
    total_amount DECIMAL(15,0),
    customer_name VARCHAR(200),
    delivery_name VARCHAR(300),
    sales_person_name VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- BFRデータ初期投入
INSERT INTO estimate_bfr_bodies (model_code, base_price, airflow, filter_length, filter_type, filter_price, filter_count) VALUES
('BFR3S×4', 4156000, 330, '2810L', '標準', 4000, 96),
('BFR3S×4', 4156000, 330, '2810L', '帯電防止品', 4400, 96),
('BFR3×4', 4328000, 370, '2810L', '標準', 4000, 108),
('BFR3×4', 4328000, 370, '2810L', '帯電防止品', 4400, 108),
('BFR3×5', 6120000, 460, '2810L', '標準', 4000, 135),
('BFR3×5', 6120000, 460, '2810L', '帯電防止品', 4400, 135),
('BFR3×6', 6892000, 550, '2810L', '標準', 4000, 162),
('BFR3×6', 6892000, 550, '2810L', '帯電防止品', 4400, 162),
('BFR3×6L', 6864800, 680, '3460L', '標準', 4600, 162),
('BFR3×6L', 6864800, 680, '3460L', '帯電防止品', 5200, 162),
('BFR4×6', 6936000, 730, '2810L', '標準', 4000, 216),
('BFR4×6', 6936000, 730, '2810L', '帯電防止品', 4400, 216),
('BFR5×6', 7630000, 920, '2810L', '標準', 4000, 270),
('BFR5×6', 7630000, 920, '2810L', '帯電防止品', 4400, 270);

INSERT INTO estimate_bfr_fans (bfr_model, fan_model, price, quantity) VALUES
('BFR3S×4', 'TVS11kw', 640000, 1), ('BFR3S×4', 'TVS15kw', 710000, 1),
('BFR3×4', 'TVS11kw', 640000, 2), ('BFR3×4', 'TVS15kw', 710000, 1),
('BFR3×4', 'TVS15kw', 710000, 2), ('BFR3×4', 'TVS22kw', 1100000, 1),
('BFR3×5', 'TVS11kw', 640000, 3), ('BFR3×5', 'TVS15kw', 710000, 2),
('BFR3×5', 'TVS18.5kw', 870000, 2),
('BFR3×6', 'TVS11kw', 640000, 3), ('BFR3×6', 'TVS15kw', 710000, 2),
('BFR3×6', 'TVS22kw', 1100000, 2);

INSERT INTO estimate_bfr_rvs (bfr_model, rv_model, kw, price, quantity) VALUES
('BFR3S×4', 'RV25×40', 0.2, 290000, 1), ('BFR3S×4', 'RV25×60', 0.2, 320000, 1),
('BFR3×4', 'RV25×40', 0.2, 290000, 1), ('BFR3×4', 'RV25×60', 0.2, 320000, 1),
('BFR3×5', 'RV25×60', 0.2, 320000, 1), ('BFR3×5', 'RV25×80', 0.4, 390000, 1),
('BFR3×5', 'RV30×80', 0.75, 480000, 1), ('BFR3×5', 'RV35×90', 2.2, 570000, 1),
('BFR3×6', 'RV25×60', 0.4, 320000, 1), ('BFR3×6', 'RV25×80', 0.4, 390000, 1),
('BFR3×6', 'RV30×80', 0.75, 480000, 1), ('BFR3×6', 'RV35×90', 2.2, 570000, 1);

INSERT INTO estimate_sca_bodies (model_code, diameter, capacity, base_price, ab_kw, sc_count, sc1_kw, rv1_model, rv1_kw) VALUES
('SCD4', 1145, 5, 1650000, 0.4, 1, 0.4, 'RV20×35', 0.2),
('SCD5', 2000, 10, 2200000, 0.4, 1, 0.4, 'RV20×35', 0.2),
('SCD6', 2265, 15, 2400000, 0.4, 1, 0.4, 'RV25×40', 0.2),
('SCA25', 2500, 15, 3000000, 1.5, 1, 0.75, 'RV25×40', 0.4),
('SCA30', 3000, 20, 3700000, 1.5, 1, 0.4, 'RV25×40', 0.4),
('SCA35', 3500, 30, 4200000, 1.5, 1, 0.75, 'RV25×40', 0.4),
('SCA400', 4000, 50, 5450000, 1.5, 1, 0.75, 'RV25×40', 0.4),
('SCA450', 4500, 60, 6000000, 2.2, 1, 0.4, 'RV25×40', 0.4),
('SCA500', 5000, 100, 8200000, 1.5, 1, 0.75, 'RV25×40', 0.4),
('SCA550', 5500, 120, 9600000, 3.7, 1, 0.75, 'RV25×60', 0.4),
('SCA590', 5900, 150, 11500000, 2.2, 1, 0.75, 'RV25×60', 0.4),
('SCA675', 6750, 200, 15700000, 3.7, 2, 1.5, 'RV25×60', 0.75),
('SCA760', 7600, 300, 18900000, 3.7, 1, 1.5, 'RV25×60', 0.4),
('SCA844', 8440, 400, 26000000, 5.5, 1, 1.5, 'RV30×60HP', 2.2);

INSERT INTO estimate_pl_fans (model_code, kw, price) VALUES
('PL25', 5.5, 430000), ('PL25', 7.5, 450000),
('PL30', 7.5, 480000), ('PL30', 11, 520000),
('PL35', 11, 610000), ('PL35', 15, 700000),
('PL40', 11, 690000), ('PL40', 15, 780000),
('PL45', 15, 880000), ('PL45', 18.5, 970000),
('PL50', 22, 1150000), ('PL55', 30, 1420000),
('PL200', 3.7, 390000), ('PL200', 5.5, 460000),
('PL250', 5.5, 480000), ('PL250', 7.5, 510000),
('PL300', 7.5, 520000), ('PL300', 11, 580000);

INSERT INTO estimate_cyclones (model_code, shape, material, price) VALUES
('CY500', '標準', '鉄', 280000),
('CY550', 'シュート式', '鉄', 330000),
('CY550', 'シュート式', 'SUS', 660000),
('CY600', '標準', '鉄', 330000),
('CY700', '標準', '鉄', 390000),
('CY800', '標準', '鉄', 450000),
('CY850', '標準', '鉄', 500000),
('CY900', '標準', '鉄', 500000);
