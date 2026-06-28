# 申し送り（WORKLOG） — sales-system

複数セッション/作業者が **同じファイルを同時に触って上書き衝突しないため** の申し送りノート。
**ルール**: 着手前に必ず最新を pull → 「作業中」に自分が触るファイル/バグIDを記録 → 完了したら「完了ログ」へ移動。

---

## 作業中（着手したら追記、終わったら消す）

| 日時 | 作業者 | 対象ファイル | 対応バグ/内容 | 状態 |
|------|--------|-------------|--------------|------|
| — | — | — | — | — |

---

## 完了ログ（新しい順）

### 2026-06-28（夜） — Claude(Cowork) — 検証ラン（push後の動作確認）
- フロント修正(921e0dd)をpush済み→Render自動デプロイ。
- ライブAPI確認: `/suppliers`=[]（仕入先未登録）, `/material-orders`=10件OK, `/bom`=1件OK。**P-02は本番に影響なし**（order_no/project_unit_id 列は既に存在＝/setup-bom-master-tables 実行済み、ユニット取込データあり）。
- 注意: 匿名GET `/materials`(検索なし)が[]を返すが、`?search=208005167`では該当部材が返り、orders/bomも同部材を参照。`list_materials`のコードは全履歴で同一・正しい。未知クエリparamが手前で除去されており、**匿名エンドポイント前段のキャッシュによる stale [] の可能性が高い**（実バグではない見込み）。要・実UI（部材マスタタブ）での目視確認。毎朝タスクがChromeで確認する。


### 2026-06-28 — Claude(Cowork) — /procurement バグ検証・修正
**対象**: https://sales-frontend-ybzn.onrender.com/procurement
**触ったファイル**: `frontend/src/pages/ProcurementPage.tsx`, `backend/migrations/manufacturing_procurement.sql`, `WORKLOG.md`（新規）
**修正済（通常・push）**:
- **P-01** 発注/部材/BOMの3タブでAPIエラーを握りつぶし（`.catch(()=>{})`／catch無し）→ 失敗時に赤いエラーバナーを表示するよう修正。発注タブのエラーには `/setup-bom-master-tables 未実行の可能性` を明示。
- **P-04** 新規発注で部材未選択のままPOST→500 → 送信前バリデーション＋例外捕捉を追加。
- migration SQL の `material_orders` に `order_no` / `project_unit_id` を追記（新規構築時のスキーマdrift防止）。
**要運用対応（重大・未push＝提案）**:
- **P-02** 既存DBで `material_orders.order_no` / `project_unit_id` 列が無いと `GET /material-orders` が500→発注タブが空。**本番で `/setup-bom-master-tables` を1回実行**して列追加（ALTER）すること。コード変更ではなく運用作業のため自動pushしない。
**残（提案・未対応）**:
- **P-03** `_mo_dict` の `if mo.order_qty else None` 等で数量/単価=0 が「—」表示。要否確認のうえ別途。
**メモ**: 着手時 origin/main が6コミット先行していたため最新に合わせて再実装した。今後は着手前に必ず pull すること。

---

## 反映方針
- 通常バグ（非破壊的）= 修正してpush。重大バグ（セキュリティ/DBスキーマ変更/破壊的/認証）= 提案のみ。
- DESIGN.md 厳守（main.py非変更・1ファイルずつ・全角禁止・f-string内包表記禁止・CORS不変・VITE_API_URL二重/api禁止）。
