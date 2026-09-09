-- 製品原価検証（管理者専用モジュール）
-- 本番では GET /api/costing/setup-tables（管理者ログイン必須）で create_all するため、
-- この SQL は新規構築・レビュー用の写し。既存テーブルは変更しない。

CREATE TABLE IF NOT EXISTS cost_material_ext (
    material_id UUID PRIMARY KEY REFERENCES material_masters(id) ON DELETE CASCADE,
    category VARCHAR(30),              -- 鋼板/面積材/形鋼/パイプ/購入品/外注加工/塗料
    price_unit VARCHAR(10) DEFAULT '個',
    steel_grade VARCHAR(50),
    thickness_mm NUMERIC(6,2),
    stock_size VARCHAR(30),
    piece_weight_kg NUMERIC(10,3),
    piece_length_m NUMERIC(10,3),
    sheet_area_m2 NUMERIC(10,4),
    density NUMERIC(6,3),
    code_source VARCHAR(20) DEFAULT '仮',   -- TECHS / 仮
    preferred_supplier_id UUID REFERENCES suppliers(id),
    price_policy VARCHAR(20) DEFAULT 'preferred',  -- preferred / cheapest
    basis_note TEXT,
    notes TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_material_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alias VARCHAR(300) UNIQUE NOT NULL,
    material_id UUID NOT NULL REFERENCES material_masters(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_material_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id UUID NOT NULL REFERENCES material_masters(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id),
    effective_date DATE NOT NULL,
    price NUMERIC(15,4) NOT NULL,
    price_unit VARCHAR(10),
    basis_expr TEXT,
    source VARCHAR(30) DEFAULT '手入力',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_price_adjustments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id UUID NOT NULL REFERENCES material_masters(id) ON DELETE CASCADE,
    party_type VARCHAR(20) DEFAULT 'supplier',
    party_id UUID,
    party_name VARCHAR(200),
    adjust_type VARCHAR(10) DEFAULT 'percent',
    value NUMERIC(15,4) NOT NULL,
    effective_from DATE,
    effective_to DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_bom_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id UUID NOT NULL REFERENCES unit_masters(id) ON DELETE CASCADE,
    section VARCHAR(100),
    label VARCHAR(300),
    line_type VARCHAR(20) NOT NULL,    -- weight / measure / count / subcontract / paint / subassembly
    material_id UUID REFERENCES material_masters(id),
    sub_unit_id UUID REFERENCES unit_masters(id),
    qty NUMERIC(14,4) NOT NULL DEFAULT 0,
    qty_expr TEXT,
    yield_basis JSON,
    markup_factor NUMERIC(6,3) DEFAULT 1,
    is_option BOOLEAN DEFAULT FALSE,
    source_ref VARCHAR(100),
    sort_order INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(50) NOT NULL,          -- labor_rate_per_hour / overhead_rate / target_margin_rate
    value NUMERIC(15,4),
    effective_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    adjustments JSON,
    notes TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id UUID NOT NULL REFERENCES unit_masters(id) ON DELETE CASCADE,
    price_date DATE NOT NULL,
    scenario_id UUID REFERENCES cost_scenarios(id),
    total NUMERIC(15,2),
    steel_total NUMERIC(15,2),
    purchased_total NUMERIC(15,2),
    manufacturing_cost NUMERIC(15,2),
    result JSON,
    label VARCHAR(200),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO cost_settings (key, value, effective_date, notes)
SELECT 'labor_rate_per_hour', 2500, '2020-01-01', '初期値（2026-09-08 井上電設様回答）'
WHERE NOT EXISTS (SELECT 1 FROM cost_settings WHERE key = 'labor_rate_per_hour');
