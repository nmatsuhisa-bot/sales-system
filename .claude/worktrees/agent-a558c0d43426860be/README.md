# 販売管理・見積管理システム
## 井上電設株式会社向け

---

## システム概要

| 機能 | 内容 |
|------|------|
| 顧客管理 | 顧客情報・連絡先の登録・編集 |
| 商品管理 | BFQ/BFR/SCA等の製品マスタ・価格管理 |
| 見積管理 | 見積書作成（オプション積み上げ対応）・PDF出力・受注変換 |
| 受注管理 | 受注ステータス管理（受注→製造中→出荷→納品→完了） |
| 発注管理 | 仕入先への発注・入荷管理 |
| 在庫管理 | 在庫数管理・入出庫履歴・不足アラート |
| ダッシュボード | 月別売上・受注状況・KPIサマリ |

---

## 技術スタック

- **フロントエンド**: React 18 + TypeScript + Vite + Tailwind CSS
- **バックエンド**: Python 3.11 + FastAPI
- **データベース**: PostgreSQL 15
- **コンテナ**: Docker / Docker Compose

---

## 起動手順

### 前提
- Docker Desktop がインストールされていること

### 1. リポジトリを配置
```bash
# このディレクトリ (sales-system/) を任意の場所に配置
```

### 2. 管理者パスワードを設定
```bash
# backend/migrations/init.sql の最下部を編集
# $2b$12$placeholder_hash を実際のbcryptハッシュに変更
# または起動後にAPIで作成:
# POST /api/auth/users
# { "email": "...", "password": "...", "full_name": "...", "role": "admin" }
```

### 3. 起動
```bash
cd sales-system/
docker-compose up --build
```

### 4. アクセス
| サービス | URL |
|---------|-----|
| フロントエンド | http://localhost:3000 |
| バックエンドAPI | http://localhost:8000 |
| API ドキュメント | http://localhost:8000/docs |

---

## 初期ユーザー作成（初回のみ）

```bash
# バックエンドコンテナに入る
docker-compose exec backend python

# Pythonシェルで実行
import bcrypt
print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())
```

生成されたハッシュを `init.sql` の `$2b$12$placeholder_hash` と置き換えてから `docker-compose up` を実行してください。

または起動後に API エンドポイント `POST /api/auth/users` でユーザーを作成できます。

---

## 見積番号・受注番号のルール

| 種別 | 形式 | 例 |
|------|------|-----|
| 見積番号 | Q{年}-{連番4桁} | Q2026-0001 |
| 受注番号 | SO{年}-{連番4桁} | SO2026-0001 |
| 発注番号 | PO{年}-{連番4桁} | PO2026-0001 |

---

## ディレクトリ構成

```
sales-system/
├── docker-compose.yml
├── docs/
│   └── 設計書.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── migrations/
│   │   └── init.sql          ← DB初期化SQL（全テーブル・初期データ）
│   └── app/
│       ├── main.py           ← FastAPIアプリ
│       ├── db/
│       │   └── models.py     ← SQLAlchemyモデル
│       └── api/
│           ├── auth.py       ← 認証（JWT）
│           ├── customers.py  ← 顧客管理
│           ├── products.py   ← 商品管理
│           ├── quotations.py ← 見積管理
│           ├── orders.py     ← 受注管理
│           ├── purchase_orders.py ← 発注管理
│           ├── inventory.py  ← 在庫管理
│           └── reports.py    ← ダッシュボード・レポート
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── App.tsx           ← ルーティング
        ├── api/index.ts      ← APIクライアント
        ├── components/common/
        │   └── Layout.tsx    ← サイドバーレイアウト
        └── pages/
            ├── LoginPage.tsx
            ├── DashboardPage.tsx
            ├── CustomersPage.tsx
            ├── ProductsPage.tsx
            ├── QuotationsPage.tsx
            ├── QuotationFormPage.tsx ← 見積書作成フォーム
            ├── OrdersPage.tsx
            ├── PurchaseOrdersPage.tsx
            └── InventoryPage.tsx
```

---

## 今後の拡張予定

- [ ] 見積書・請求書PDF自動生成（印鑑・社印対応）
- [ ] 案件管理（案件NOと受注NOのひも付け）
- [ ] 工程表機能
- [ ] メール送信（見積書PDF添付）
- [ ] ロール別アクセス制御の強化
- [ ] 作業指示書自動生成（BFQ/BFR/SCA対応）
