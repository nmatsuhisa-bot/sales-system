-- 工場機械・図面管理（eq_*）
-- 本番では GET /api/equipment/setup-tables（管理者ログイン必須）で create_all するため、
-- この SQL は新規構築・レビュー用の写し。既存テーブルは変更しない。
-- 仕様: docs/工場機械・図面管理_要件整理と実装方針_20260915.md

CREATE TABLE IF NOT EXISTS eq_sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 図面画像は Render のディスクが再デプロイで消えるため DB に保管する
CREATE TABLE IF NOT EXISTS eq_drawings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES eq_sites(id),
    name VARCHAR(200) NOT NULL,
    version_no INTEGER DEFAULT 1,
    width_px INTEGER NOT NULL,
    height_px INTEGER NOT NULL,
    image BYTEA NOT NULL,                  -- 背景用（機械番号を消した図面）
    image_type VARCHAR(50) DEFAULT 'image/png',
    original BYTEA,                        -- 番号入りの元図面（任意）
    original_type VARCHAR(50),
    source_filename VARCHAR(300),
    scale_note VARCHAR(100),
    valid_from DATE,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 機械マスタ。code = 管理ID（機械一覧表の管理番号をそのまま使う）
CREATE TABLE IF NOT EXISTS eq_machines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    category1 VARCHAR(50),
    category2 VARCHAR(50),
    maker VARCHAR(100),
    dealer VARCHAR(100),
    model VARCHAR(200),
    made_year VARCHAR(20),
    electric_spec VARCHAR(100),
    notes TEXT,
    work_content VARCHAR(200),
    legal_inspection VARCHAR(200),
    inspector VARCHAR(200),
    repair_log TEXT,
    list_site VARCHAR(30),                 -- 一覧表の「工場」列（参考）
    price NUMERIC(15,0),
    price_raw VARCHAR(100),
    asset_flag_raw VARCHAR(50),            -- 一覧表の「決算資産記載」列
    depreciation_raw VARCHAR(50),          -- 一覧表の「償却資」列
    status VARCHAR(20) DEFAULT 'active',   -- active / removed / disposed / unknown
    extra_rows JSON,                       -- 同一番号の付帯行（電気工事・移設費）
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 固定資産台帳のスナップショット（期ごと。機械以外の資産も含む）
CREATE TABLE IF NOT EXISTS eq_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period VARCHAR(10) NOT NULL,           -- 例 2026-02
    asset_key VARCHAR(60) NOT NULL,        -- 台帳の管理番号。空欄の資産は名称・取得日・価額から生成した仮キー
    asset_no VARCHAR(30),
    name VARCHAR(300) NOT NULL,
    account VARCHAR(50),
    acquired_on DATE,
    in_service_on DATE,
    price NUMERIC(15,0),
    quantity VARCHAR(30),
    department VARCHAR(50),
    method VARCHAR(30),
    useful_life VARCHAR(10),
    ending_balance NUMERIC(15,0),
    site_note VARCHAR(100),                -- 仕訳摘要
    remarks VARCHAR(200),                  -- 摘要
    disposed_on DATE,
    sold_on DATE,
    raw JSON,
    imported_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_eq_assets_period_key UNIQUE (period, asset_key)
);

-- 機械 ⇄ 固定資産（多対多）
CREATE TABLE IF NOT EXISTS eq_machine_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id UUID NOT NULL REFERENCES eq_machines(id) ON DELETE CASCADE,
    asset_key VARCHAR(60) NOT NULL,
    link_type VARCHAR(30) DEFAULT '本体',      -- 本体 / 付帯工事 / 移設費 / 親資産に含む / リース / その他
    confidence VARCHAR(20) DEFAULT 'candidate', -- confirmed / candidate
    note TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_eq_machine_assets UNIQUE (machine_id, asset_key)
);

-- 図面ごとの確定
CREATE TABLE IF NOT EXISTS eq_commits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drawing_id UUID NOT NULL REFERENCES eq_drawings(id) ON DELETE CASCADE,
    committed_at TIMESTAMP NOT NULL,
    user_id UUID,
    user_name VARCHAR(100),
    memo TEXT,
    move_count INTEGER DEFAULT 0
);

-- 配置（有効期間付き。valid_to IS NULL が現在。座標は画像に対する 0〜1 の比率）
CREATE TABLE IF NOT EXISTS eq_placements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_id UUID NOT NULL REFERENCES eq_machines(id) ON DELETE CASCADE,
    drawing_id UUID NOT NULL REFERENCES eq_drawings(id) ON DELETE CASCADE,
    x NUMERIC(9,6) NOT NULL,
    y NUMERIC(9,6) NOT NULL,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP,
    commit_id UUID REFERENCES eq_commits(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 移動 1 件ごとの履歴（commit_id IS NULL = 下書き、undone_at あり = 取り消し済み）
CREATE TABLE IF NOT EXISTS eq_moves (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drawing_id UUID NOT NULL REFERENCES eq_drawings(id) ON DELETE CASCADE,
    machine_id UUID NOT NULL REFERENCES eq_machines(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    kind VARCHAR(10) NOT NULL,             -- place / move / remove
    from_x NUMERIC(9,6),
    from_y NUMERIC(9,6),
    to_x NUMERIC(9,6),
    to_y NUMERIC(9,6),
    moved_at TIMESTAMP NOT NULL,
    user_id UUID,
    user_name VARCHAR(100),
    commit_id UUID REFERENCES eq_commits(id),
    undone_at TIMESTAMP
);
