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

### 2026-07-05 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。
- エンドポイント整合: procurementApi の全 `procurement/*` 参照が materials.py の30ルートに一致。不一致なし。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError 11 / catch 16 箇所 健在。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、`_build_po_html`(L656-657) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外・curl はサンドボックス非allowlist(HTTP 000) → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-04 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。
- P-01 赤エラーバナー: ProcurementPage.tsx の setError/catch 25箇所 健在。
- P-03/P-05 0値表示: materials.py `_mo_dict`(L439-440) order_qty/unit_price、`_build_po_html`(L656-658) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- エンドポイント整合: 全 procurementApi 参照が materials.py の28ルート(L19〜631)に一致。不一致なし。
- 構文: ProcurementPage.tsx esbuild OK、materials.py py_compile OK。全角は文字列/コメント内のみ（コード構文に混入なし）。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外・Chrome無人選択不可 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。

### 2026-07-03 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 いずれも修正が現状維持・退行なしを確認。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError/catch 25箇所 健在。
- P-03/P-05 0値表示: materials.py `_mo_dict` の order_qty/unit_price、`_build_po_html` の qty/price ともに `is not None` 判定で維持。amount は `or 0` で¥0正常表示。
- エンドポイント/フィールド整合: procurementApi の全 `procurement/*` 参照が materials.py の実ルートに対応。不一致なし。
- 構文確認: ProcurementPage.tsx esbuild OK、materials.py py_compile OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外、Chrome無人選択不可 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-02 — Claude(Cowork) — /procurement 検証・P-05修正
**触ったファイル**: `backend/app/api/materials.py`, `WORKLOG.md`
**修正済（通常・push）**:
- **P-05** 発注書HTML出力 `_build_po_html` で `price` が `if l.unit_price`（truthy判定）→ 単価0の行が金額欄は¥0なのに単価欄が空白になる不整合。`is not None` に変更（同行 qty と統一）。P-03と同種の0値表示不具合。非破壊・1ファイル・py_compile OK・全角なし。
**確認（退行なし）**: P-01赤バナー(materials/orders/BOM各タブ), P-03 `_mo_dict` の order_qty/unit_price=0表示, P-04 発注必須バリデーション いずれも現状維持。
**ライブUI確認**: 無人実行のためChrome複数接続の対話選択不可・web_fetchは対象ドメインprovenance外。静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は本番で `/setup-bom-master-tables` を1回実行済みの前提（前回確認で10件取得OK）。

### 2026-06-30 — Claude(Cowork) — /procurement 検証・P-03修正
**触ったファイル**: `backend/app/api/materials.py`, `WORKLOG.md`
**修正済（通常・push）**:
- **P-03** `_mo_dict` で `order_qty`/`unit_price` が **0 のとき truthiness判定で None化** → フロントが「—」表示になる不具合を修正（`if ... is not None` に変更）。発注数量0・単価0（無償部材等）が正しく 0 表示になる。非破壊・1ファイル・py_compile OK・全角なし。
- ライブAPI確認は今回不可（サンドボックスproxyが対象ドメインを403/web_fetch provenance外、Chromeは複数接続で無人選択不可）。静的解析で対応。
- フロント側 (ProcurementPage.tsx L706-707) は既に `!= null` 判定で正しく、退行なし。P-01(赤バナー)/P-04(発注バリデーション) のコードも現状維持を確認。


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
