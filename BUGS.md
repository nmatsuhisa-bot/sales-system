# 井上電設 販売管理システム バグ調査レポート

作成日: 2026-06-20

---

## 重要度「高」（即時対応必須）

### B001 — FK参照先が廃止テーブル
**ファイル**: `backend/app/db/models.py`（374行目）  
**問題**: `project_orders.quotation_id` の外部キーが廃止済みの旧テーブル `quotations` を参照している。`OrderTicket`（623行目）は正しく `quotation_headers.id` を参照しており不整合がある。  
**修正**: `ForeignKey("quotations.id")` → `ForeignKey("quotation_headers.id")` に変更（Alembicマイグレーション必須）

---

### B003 — link_quotationが旧モデルにクエリ
**ファイル**: `backend/app/api/projects.py`（280〜296行目）  
**問題**: `link_quotation` エンドポイントが廃止済みの旧 `Quotation` モデル（`quotations` テーブル）にクエリしている。新見積は `QuotationHeader`（`quotation_headers`）に保存されるため常に `None` になる。  
**修正**: `db.query(Quotation)` → `db.query(QuotationHeader)` に変更

---

### B004 — 見積番号採番が文字列ソート
**ファイル**: `backend/app/api/estimate_quotations.py`（119〜124行目）  
**問題**: 採番ロジックが `order_by(desc(QuotationHeader.quotation_no))` の辞書順ソート。`Q2025-0009` の次に `Q2025-0010` が来ると `"9" > "1"` となり採番が破綻する。並行リクエスト時の競合防止ロックもない。  
**修正**: 番号部分を数値でキャストしてソート。採番に `pg_advisory_xact_lock` を追加。

---

### B005 — 受注票発行時にquotation_id=Noneをセット
**ファイル**: `backend/app/api/estimate_quotations.py`（541行目付近）  
**問題**: 受注票発行処理で `quotation_id=None` を明示セットしているため、受注票と見積書の紐付けが保存されない。受注票PDFは `t.quotation` リレーションから品名・金額を取得するが常に空になる。  
**修正**: `quotation_id=None` を発行元の見積IDで上書きする。

---

### B008 — ダッシュボード受注集計に月フィルタ欠落
**ファイル**: `backend/app/api/reports.py`（32〜41行目）  
**問題**: 「今月の受注件数・金額」KPIのクエリが年フィルタのみ。見積の月次集計には月フィルタがあるのに受注だけ今年累計になっている。  
**修正**: `extract('month', OrderTicket.order_date) == month` のフィルタを追加。

---

### B009 — ユーザー管理APIに認証なし
**ファイル**: `backend/app/api/auth.py`（73〜119行目）  
**問題**: ユーザー作成・更新・削除・一覧取得の全エンドポイントに `Depends(get_current_user)` がなく、認証なしでアクセス可能。  
**修正**: 全エンドポイントに `Depends(get_current_user)` + adminロールチェックを追加。

---

### B010 — seedエンドポイントが認証なしで公開
**ファイル**: `backend/app/main.py`（33〜52行目）  
**問題**: `/seed-users`（デフォルトパスワード `user1234` でユーザー生成）、`/setup-add-is-active`、`/setup-fix-duplicate-tickets` 等が認証なしで公開されている。  
**修正**: 本番環境ではこれらのエンドポイントを削除またはIPアクセス制限。

---

### B013 — 見積採用APIエンドポイントが存在しない
**ファイル**: `frontend/src/api/index.ts`（152〜153行目）  
**問題**: `adoptQuotation` / `unadoptQuotation` が呼ぶ `POST /estimate-quotations/{id}/adopt` と `DELETE /estimate-quotations/{id}/adopt` がバックエンドのルーターに存在しない。  
**修正**: `estimate_quotations.py` に `/adopt` エンドポイントを実装（既存の採用ロジックを確認して移植）。

---

### B014 — ダッシュボードのレスポンスキー名不一致
**ファイル**: `frontend/src/pages/DashboardPage.tsx`（59行目、82行目、101行目）  
**問題**: フロントが参照する `data.order_statuses`、`data.quotation_statuses` 等のキーがバックエンドの実際のレスポンス（`project_status_counts` 等）と不一致。  
**修正**: `DashboardPage.tsx` のキー参照をAPIレスポンスの実際の構造に合わせて修正。

---

## 重要度「中」

| ID | ファイル | 問題内容 |
|----|---------|----------|
| B002 | `backend/app/api/projects.py`（213〜217行目） | `pg_advisory_xact_lock` の二重実行（コピペ重複） |
| B006 | `backend/app/api/estimate_quotations.py`（286行目） | UUID文字列を `setattr` でセット時の型変換エラーリスク |
| B007 | `backend/app/api/estimate_quotations.py`（872行目） | 検査記録書HTMLのrowspan値が `"X"` リテラルのまま・cat_cellが未挿入 |
| B011 | `backend/app/main.py` | CORS全オリジン解放（本番移行時に要見直し） |
| B012 | `frontend/src/api/index.ts`（130〜132行目） | PDF URL生成でVITE_API_URL未設定時のフォールバックなし |
| B015 | `frontend/src/pages/ProjectsPage.tsx`（132行目） | 子ID採番のゼロパディングなし（フロントとバックで形式不一致） |
| B016 | `frontend/src/pages/ProjectsPage.tsx`（415〜418行目） | モデルに存在しないフィールド（`shipment_date`等）をフォームで使用 |

---

## 重要度「低」

| ID | ファイル | 問題内容 |
|----|---------|----------|
| B017 | `frontend/src/pages/EstimateFormPage.tsx`（87行目） | 案件情報の自動補完コードが空振り（戻り値未使用） |
| B018 | `frontend/src/pages/EstimateFormPage.tsx`（145行目） | フィルター価格計算ロジックの仕様確認要 |
| B019 | `backend/app/api/estimate_quotations.py`（126〜131行目） | 税計算のフロント/バック間で浮動小数点誤差リスク |
| B020 | `backend/app/api/estimate_quotations.py`（333〜336行目） | ドラフト透かし未実装（パラメータを受け取るが処理なし） |

---

## 対応優先順序

1. **B001 + B003 + B005**（連動バグ）FK修正 → 見積紐付け・受注票PDF復旧
2. **B009 + B010**（セキュリティ）認証ガード追加・管理エンドポイント保護
3. **B013 + B014**（機能不全）採用API実装・ダッシュボードキー名修正
4. **B004**（採番）数値ソートへ変更・競合ロック追加
5. **B008**（集計）月フィルタ追加
6. **B007**（PDF）検査記録書rowspan修正
7. B002、B006、B011〜B016（中優先度）
8. B017〜B020（低優先度・仕様確認後）
