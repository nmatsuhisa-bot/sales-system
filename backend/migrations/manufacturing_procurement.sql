-- ① 仕入（発注）管理
CREATE TABLE IF NOT EXISTS material_masters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_code VARCHAR(50) UNIQUE NOT NULL,
    material_name VARCHAR(300) NOT NULL,
    unit VARCHAR(20) DEFAULT '個',
    default_supplier_id UUID REFERENCES suppliers(id),
    standard_lead_days INTEGER DEFAULT 14,
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bom_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_type VARCHAR(50) NOT NULL,
    model_no VARCHAR(100) NOT NULL,
    material_id UUID NOT NULL REFERENCES material_masters(id),
    quantity NUMERIC(10,3) NOT NULL DEFAULT 1,
    unit VARCHAR(20),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS material_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_order_id UUID REFERENCES project_orders(id),
    material_id UUID NOT NULL REFERENCES material_masters(id),
    supplier_id UUID REFERENCES suppliers(id),
    order_qty NUMERIC(10,3),
    unit_price NUMERIC(15,2),
    order_date DATE,
    due_date DATE,
    received_date DATE,
    status VARCHAR(20) DEFAULT '未発注',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ② 製造計画
CREATE TABLE IF NOT EXISTS production_capacity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    factory VARCHAR(100) DEFAULT '小牧',
    fiscal_year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    work_days INTEGER DEFAULT 20,
    regular_workers INTEGER DEFAULT 8,
    temp_workers INTEGER DEFAULT 5,
    hours_per_day INTEGER DEFAULT 8,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(factory, fiscal_year, month)
);

CREATE TABLE IF NOT EXISTS product_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_type VARCHAR(50) NOT NULL,
    model_no VARCHAR(100) NOT NULL,
    required_hours NUMERIC(10,1) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS manufacturing_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_order_id UUID NOT NULL REFERENCES project_orders(id),
    product_type VARCHAR(50),
    model_no VARCHAR(100),
    planned_start DATE,
    planned_end DATE,
    actual_start DATE,
    actual_end DATE,
    assigned_to VARCHAR(100),
    status VARCHAR(20) DEFAULT '未着手',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 初期データ: 生産能力指数.xlsxから製品所要工数
INSERT INTO product_hours (product_type, model_no, required_hours) VALUES
('BFR', '3X6', 240), ('BFR', '4X6', 272), ('BFR', '5X6', 358),
('BFR', '3X6L', 242), ('BFR', '4X6L', 352), ('BFR', '5X6L', 410),
('BFR', '5WX6L', 403), ('BFR', '5WWX6L', 424),
('BFP', '84', 212), ('BFP', '180', 361),
('SCA', '500', 433), ('SCA', '590', 455), ('SCA', '675', 485), ('SCA', '844', 744),
('SRR', '2000X2(架台)', 962), ('SRR', '2000X3(架台)', 1284), ('SRR', '2000X2(ﾋﾟｯﾄ)', 591),
('FLT', '800上送り', 447),
('CY', '1000(架台含)', 112), ('CY', '1350(架台含)', 122),
('LRG', '120', 872)
ON CONFLICT DO NOTHING;

-- 初期データ: 2025年度 生産能力（小牧）
INSERT INTO production_capacity (factory, fiscal_year, month, work_days, regular_workers, temp_workers, hours_per_day) VALUES
('小牧', 2025, 3, 21, 8, 5, 8), ('小牧', 2025, 4, 22, 8, 5, 8),
('小牧', 2025, 5, 21, 8, 5, 8), ('小牧', 2025, 6, 21, 8, 5, 8),
('小牧', 2025, 7, 23, 8, 5, 8), ('小牧', 2025, 8, 17, 8, 5, 8),
('小牧', 2025, 9, 22, 8, 5, 8), ('小牧', 2025, 10, 24, 8, 5, 8),
('小牧', 2025, 11, 20, 8, 5, 8), ('小牧', 2025, 12, 20, 8, 5, 8),
('小牧', 2026, 1, 20, 8, 5, 8), ('小牧', 2026, 2, 20, 8, 5, 8),
('小牧', 2026, 3, 21, 8, 5, 8), ('小牧', 2026, 4, 22, 8, 5, 8),
('小牧', 2026, 5, 21, 8, 5, 8), ('小牧', 2026, 6, 21, 8, 5, 8),
('小牧', 2026, 7, 23, 8, 5, 8), ('小牧', 2026, 8, 17, 8, 5, 8),
('小牧', 2026, 9, 22, 8, 5, 8), ('小牧', 2026, 10, 24, 8, 5, 8),
('小牧', 2026, 11, 20, 8, 5, 8), ('小牧', 2026, 12, 20, 8, 5, 8),
('小牧', 2027, 1, 20, 8, 5, 8), ('小牧', 2027, 2, 20, 8, 5, 8)
ON CONFLICT DO NOTHING;
