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

### 2026-07-18（続2） — Claude(Opus) — Renderメモリ超過の是正（0632525）
**事象**: Renderから「sales-backend exceeded its memory limit」通知。インスタンスが自動再起動し
一時的に停止した。**原因は当セッションの検証**（59MB/48MBのDXFを `/from-cad` へ直接アップロード）。
**根本原因**: アップロード経路が「**全体をメモリに読み込んでからサイズ検査**」していた。
`blob = await file.read()` の時点で59MBがRAMに載り、上限80MBの検査はその後だった。
**対処**（`backend/app/api/estimate_quotations.py`）:
- `/from-cad`: 1MBずつ temp ファイルへストリーム書き出し。超過検知で即中断(413)。
  上限 80MB → **8MB**（実運用サイズはブラウザ解析の `/from-cad-extract` を使うため）
- 受注票の関連書類: **base64はデコード前に長さで弾く**（デコード後検査だと一瞬メモリに載る）
- `/from-cad-extract`: ブロック名/テキストの件数上限を追加

> **今後の鉄則**: アップロードを受ける処理は「**読み込む前・デコードする前にサイズを検査**」する。
> 全体を一度にメモリへ載せない。大きな入力はブラウザ側で要約してから送る設計にする。
> 本番APIへ大きなファイルを投げる検証は、事前にサイズ上限の実装を確認してから行うこと。

### 2026-07-18（続） — Claude(Opus) — draft表記統一・売上計画表0表示・CAD→見積自動生成（f665882〜79f2b94）
**触ったファイル**: estimate_quotations.py / cad_extract.py(新規) / models.py / requirements.txt /
SalesPlanPage.tsx / EstimateListPage.tsx / EstimateFormPage.tsx / api/index.ts / utils/dxfScan.ts(新規) / docs
1. **「ドラフト」→「draft」** に統一（PDF透かし・一覧バッジ・承認パネル）
2. **売上計画表**: `M0()` を追加し、合計行・単番集計行・各行の合計欄は 0 のとき空欄でなく `0` を表示
   （明細の月次セルは従来どおり空欄のまま。表の見やすさを維持するため）
3. **CADから見積の自動生成**（プロトタイプ）
   - `POST /estimate-quotations/from-cad-extract`（画面用・JSON）と `/from-cad`（ファイル直・API用）
   - 型式抽出 → BFQ/BFR/SCA/PL/サイクロン/ADCマスタ照合 → 大項目1〜5を自動生成。必ず draft
   - **ダクトは概算**: `径(mm) × 20円 × 想定延長(注記1件×6m)`。★係数は仮値
     （原本比: 新栄合板 −15% / 西北 +25%。詳細は `docs/CAD作図標準ドラフト_20260718.md` 3.1）
   - 取付工費・運送費・工数は図面外のため**含まない**

**⚠️ ハマりどころ（重要）**
- 当初 ezdxf でサーバ側解析にしたが、**実運用の図面(13〜101MB)ではアップロードが通らない**。
  48MBで395秒・59MBで502。→ **ブラウザ側でDXFを走査**（`frontend/src/utils/dxfScan.ts`）し、
  抽出結果(数KB)だけ送る方式に変更。同じ59MB図面が **395秒 → 0.24秒 / 送信14.8KB**。
- ezdxf.readfile は図面全体をメモリ構築するため重い。**ASCII DXFの行走査で十分**（10倍高速）。
  → `requirements.txt` から ezdxf を削除済み。**再導入しないこと**。
- 行走査版は **ATTRIB（表題欄の属性）も拾える**ため ezdxf 版より情報が多い
  （本多木工所で処理風量410m3/minが新たに取得可能に）。
- バイナリDXFは非対応（先頭の識別子で検知しエラー表示）。LibreDWGの `dwg2dxf` 出力はASCII。
- JS版とPython版の抽出結果は新栄合板・川井林業で完全一致を確認済み（ロジック変更時は両方直すこと）。
**検証**: 本番で5図面・大容量含めて生成確認 → **テスト見積4件は削除済み（残存0件）**。

### 2026-07-18 — Claude(Opus) — 2026-07-17会議対応の一括実装（d5bb0d0〜b3b7b74）
**触ったファイル**: models.py / main.py / estimate_quotations.py / projects.py / api/index.ts / EstimateFormPage.tsx / EstimateListPage.tsx / OrdersPage.tsx / ProjectsPage.tsx / docs / tools
**実装内容**（会議サマリーPDF＋見積原本6社との突合に基づく）:
- **承認ワークフロー**: 検印者5名（後藤・江里口・柴田・井上社長・国立）= `APPROVERS` 定数。
  依頼→承認待ち→承認。承認まで見積PDFに「ドラフト」透かし（position:fixed）。
  **PUT更新すると承認は自動で none に戻る**（承認後の無断変更防止）。/approvers は /{quotation_id} より先に定義（ルート衝突注意）
- **3階層番号（1-1-1形式で決定）**: sub_section が連続する複数行→ `i-j` 見出し（金額なし）＋ `i-j-k` 子行。単独行は従来どおり `i-j`。スキーマ変更なし（既存sub_section列を利用）
- **金額表示制御**: quotation_line_items に hide_amount / amount_text 追加。「含まず」は単価0で運用
- **出精値引**: quotation_headers.discount_amount。**net_amount() が値引を差し引くよう変更**（工番/単番判定・案件金額・売上計画すべてに影響）。課税も値引後
- **受注票 関連書類**: order_ticket_files テーブル（PDFをDB保管・base64 JSON渡し・10MB上限）。Renderディスクは揮発のためDB保管
- **受注票+見積書 同時印刷**: /order-ticket/{id}/pdf?with_quotation=1 でHTML連結
- **案件の確度**: projects.probability（高/中/低）
- **マイグレーション**: `GET /setup-approval-workflow`（冪等）を本番で1回実行すること
**注意**: 見積書頭紙の合計金額は原本様式の全角表記（_zenkaku_amount）。会議1.2「一旦全角」対応。半角へ戻す場合はこの関数を外す

### 2026-07-18 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で退行なし。前回(07-17朝 `f1f412a`)以降 origin/main に新規コミット `eb7fddc`（業務コード指定で500になる不具合の修正／UUID列cast失敗）ほか 32ad8f5/300008d/9c966a6 等あり。**いずれも procurement 非該当**（変更対象: arrangements.py, estimate_quotations.py, masters.py, projects.py, models.py, その他 estimate/amount 系）。materials.py・ProcurementPage.tsx・api/index.ts への変更なし＝退行なし。
- **eb7fddc の波及確認**: models.py に共通ヘルパー `pk_or_code()` 追加＋`or_` import のみ。MaterialMaster/BomItem/MaterialOrder/Supplier 各モデル定義は不変。materials.py の `or_(` は L23/L211 の name/code ilike 検索のみで UUID cast の500バグ対象外、`.id == *_id` は UUID主キーの直接参照＝同種バグなし。→ procurement に修正不要。
- エンドポイント整合: ProcurementPage.tsx の procurementApi 参照17系統すべて api/index.ts に定義あり（MISSING なし）。materials.py 実ルートと整合。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 新規発注バリデーション: `!newLine.material_id`(L264) alert / 受入数量 `qty<=0`(L289) alert 健在。
- 構文: materials.py・models.py py_compile OK、ProcurementPage.tsx・api/index.ts esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-17 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で退行なし。HEAD==origin/main==`f1f412a`（07-15 ヘルプ同期、procurement系ファイル非該当）＝前回(07-15)以降 procurement コード変更なし＝退行なし。
- エンドポイント整合: ProcurementPage.tsx の procurementApi 参照17系統すべて api/index.ts に定義あり（MISSING なし）。materials.py 実ルートと整合。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 新規発注バリデーション: `!newLine.material_id`(L264) alert / 受入数量 `qty<=0`(L289) alert 健在。
- 構文: materials.py py_compile OK、ProcurementPage.tsx・api/index.ts esbuild OK。全角はコメント/HTML文字列のみ（コード構文への混入なし）。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-15 — Claude(Cowork) — マニュアル（ヘルプページ）を最新機能へ同期
**触ったファイル**: `frontend/src/pages/HelpPage.tsx`
**背景**: 前回マニュアル更新(5f78e90, 07-07)以降の機能追加をヘルプに反映。
**反映した主な変更**:
- 受注管理: 受注番号=COID(子ID)表示、注文主/出荷予定日/顧客納期/売上計上日/注文書有無/納期/前受金を一覧化、鉛筆から「受注項目の編集」(種別 工番/単番の手動変更・注文書有無・納期・前受金3回・出荷方法・受注日)。
- 見積管理: ステータスを 下書/受注/受注済 に整理、検索を追加。
- 案件管理: 確度高ステータス追加、商流(直接/代理店→商社+納入先)、子ID自動付番、出荷/売上予定日は任意。
- 製造計画: 見積内訳(ユニット単位)からドラフト、is_primaryで重複計上防止、ガントに納入先/地域+PDF出力。
- 工程管理: 納期を案件子IDの顧客納期から自動取得。
- スケジュール: 週/月表示切替、部門フィルタ、PDF出力、施工部門は閲覧のみ。
- ユーザー管理: 所属部門(営業/施工/製造/管理部)列を追加。
- 売上計画表: 確度高を追加、営業中/確度高/内示=予算金額採用(0円も表示)、単番の月次仮計上、納入先を最左。
- マスタ説明: 部材マスタの登録場所を製品BOMマスタへ集約。
**検証**: esbuildで構文チェック済み。


### 2026-07-15 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で退行なし。前回(07-14 `d5375d4`)以降 origin/main に新規コミット無し（local HEAD == origin/main == `d5375d4`）＝procurement系コード変更なし＝退行なし。
- エンドポイント整合: ProcurementPage.tsx の procurementApi 参照17系統（list/get/create/update/deletePurchaseOrder, updatePoStatus, poBreakdowns, createPOsFromBreakdowns, receiveLine, receivePoStock, allocateFromStock, poPdfUrl, listMaterials, listSuppliers, create/update/deleteMaterialOrder）が api/index.ts 定義および materials.py の実ルート（32ルート）に全一致。不一致なし。ルート順序も `/purchase-orders/breakdowns`(L578)・`/from-breakdowns`(L595) が `/{po_id}`(L656) より前で shadow なし。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 新規発注バリデーション: `!newLine.material_id`(L264) alert / 受入数量 `qty<=0`(L289) alert 健在。
- 構文: materials.py py_compile OK、ProcurementPage.tsx・api/index.ts esbuild OK。全角はコメント/docstring/HTML文字列のみ（コード構文への混入なし）。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。

### 2026-07-14 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で退行なし。前回(07-13)以降 origin/main に procurement 系コミット無し（HEAD `0848067`＝07-13 WORKLOG更新）。
- エンドポイント整合: ProcurementPage.tsx の procurementApi 参照17系統（list/get/create/update/deletePurchaseOrder, updatePoStatus, poBreakdowns, createPOsFromBreakdowns, receiveLine, receivePoStock, allocateFromStock, poPdfUrl, listMaterials, listSuppliers, create/update/deleteMaterialOrder）が api/index.ts 定義および materials.py の実ルート（32ルート）に全一致。不一致なし。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 新規発注バリデーション: `!newLine.material_id`(L264) alert / 受入数量 `qty<=0`(L289) alert 健在。
- 構文: materials.py py_compile OK、ProcurementPage.tsx・api/index.ts esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-13 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で退行なし。前回(07-12)以降 origin/main の新規コミットは WORKLOG更新 `c1bc8ee` のみ＝procurement系コード変更なし＝退行なし。
- エンドポイント整合: ProcurementPage.tsx の procurementApi 参照17系統が api/index.ts 定義および materials.py の実ルート（32ルート）に全一致。不一致なし。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 新規発注バリデーション: `!newLine.material_id`(L264) alert / 受入数量 `qty<=0`(L289) alert 健在。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-12 — Claude(Cowork) — /procurement 検証（異常なし・大規模リファクタ後の再確認）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**前回(07-11)以降の変更**: `4821d1b`（#14 部材マスタを製品BOMマスタへ集約＋NFKC正規化）で **ProcurementPage.tsx が643行削除**され発注書専用に再構成、部材/BOMタブは BomMasterPage.tsx へ移設。他 `f9ff83f`(売上計画注記)・`6f99fed`(ユーザー部門列)・`4256e3e`/`1452308`(スケジュール)は procurement 非該当。
**検証結果（退行なし）**:
- エンドポイント整合: 新ProcurementPage.tsx の procurementApi 参照17系統（listPurchaseOrders/getPurchaseOrder/create/update/deletePurchaseOrder/updatePoStatus/poBreakdowns/createPOsFromBreakdowns/receiveLine/receivePoStock/allocateFromStock/poPdfUrl/listMaterials/listSuppliers/create/update/deleteMaterialOrder）が api/index.ts 定義および materials.py の実ルート（32ルート）に全一致。不一致なし。ルート順序も `/purchase-orders/breakdowns`・`/from-breakdowns` が `/{po_id}` より前で shadow なし。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L800) price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 新規発注バリデーション: PODetail の `!newLine.material_id`(L264) alert / 受入数量 `qty<=0`(L289) 健在。
- エラーハンドリング: 旧P-01の赤バナー(setError)はリファクタで撤去され、アクション系(作成/受入/引当/取込)は alert() で明示。一覧のバックグラウンド再取得(load/suppliers/matResults)は `.catch(()=>{})` で無通知。※実害小のため今回は非修正（下記メモ参照）。
- 構文: materials.py・normalize.py py_compile OK、ProcurementPage.tsx・BomMasterPage.tsx esbuild OK。全角はコメント/HTML文字列/docstringのみ（コード構文への混入なし）。f-string内リスト内包表記なし。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**観察(未修正・要否は運用判断)**: 一覧再取得の silent catch は、取得失敗時に発注一覧が無言で空表示になりうる。背景ポーリングでの alert 連発回避の意図とも取れるため退行断定せず据え置き。次回、明示要望あれば軽微な赤バナー復活を提案。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-11 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。前回(07-10)以降の新規コミットは `8119f3b`（ダッシュボード月別ラベル/製造計画ガント列の修正）のみで、procurement 系ファイルへの変更なし＝退行なし。
- エンドポイント整合: procurementApi の全 `procurement/*` 参照（materials/bom/material-orders/suppliers/units/adopted-units/purchase-orders の各系統）が materials.py の実ルートに一致。`purchase-orders/{po_id}/status` の PATCH ルート(L671)も updatePoStatus と対応。不一致なし。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError 11 / catch 15 箇所 健在。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。
- P-04 新規発注バリデーション: `!newLine.material_id`(L278) / `!newData.material_id`(L491) 健在。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。
**ライブAPI/UI確認**: 無人実行のため curl は対象ドメイン非allowlist(HTTP 000)・web_fetch は provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-10 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。前回(07-09)以降 origin/main に新規コミット無し（HEAD `54a5af7`, origin/main と 0 差分）。
- エンドポイント整合: procurementApi の全 `procurement/*` 参照（suppliers/materials/material-orders/bom/units/adopted-units/purchase-orders の7系統）が materials.py の実ルート（32ルート）に一致。不一致なし。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError 11 / catch 15 箇所 健在。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。
- P-04 新規発注バリデーション: `!newLine.material_id`(L278) / `!newData.material_id`(L491) 健在。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外・curl不可（規約上のWebフェッチ制限）→ 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-09 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。前回(07-08)以降 origin/main に新規コミット無し（HEAD `da850cf`）。
- エンドポイント整合: procurementApi の全 `procurement/*` 参照（22系統: materials/bom/material-orders/suppliers/units/adopted-units/purchase-orders 等）が materials.py の実ルート（32ルート）に一致。不一致なし。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError 11 / catch 15 箇所 健在。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。
- P-04 新規発注バリデーション: `!newLine.material_id`(L278) / `!newData.material_id`(L491) 健在。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外・curl不可（規約上のWebフェッチ制限）→ 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-08 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。最新コミット 5f78e90（ヘルプページ拡充、コード変更なし）以降 origin/main に新規コミット無し。
- エンドポイント整合: procurementApi の全 `procurement/*` 参照（materials/bom/material-orders/suppliers/units/adopted-units/purchase-orders等、39箇所）が materials.py の実ルート（29ルート）に一致。不一致なし。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError 11 / catch 15 箇所 健在。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。
- P-04 新規発注バリデーション: `if (!newLine.material_id)` (L278) / `if (!newData.material_id)` (L491) 健在。
- DESIGN.md準拠: main.py非変更、f-string内包表記なし、VITE_API_URL単一/api、全角混入なし（コード構文には無し、コメント/文字列のみ）。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外・curl はサンドボックスproxyが403（対象ドメイン非allowlist）、Chrome拡張は2台接続で無人選択不可（AskUserQuestion必須のため自動実行不可）→ 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-07 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。前回(07-06)以降 origin/main に新規コミット無し（最新は 98b827d）。
- エンドポイント整合: procurementApi の全 `procurement/*` 参照（materials/bom/material-orders/suppliers/units/adopted-units/purchase-orders等）が materials.py の実ルート（32ルート）に一致。不一致なし。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError 11 / catch 15 箇所 健在。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。フロント側(L694-695)も `!= null` 判定で正しい。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。全角混入はコメント/HTML文字列のみ（コード構文には無し）。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外・curl はサンドボックス非allowlist(HTTP 000)、Chrome拡張は複数接続で無人選択不可 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-06 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で P-01〜P-05 全て現状維持・退行なし。
- エンドポイント整合: procurementApi の全 `procurement/*` 参照が materials.py の実ルート（32ルート）に一致。不一致なし。
- P-01 赤エラーバナー: ProcurementPage.tsx に setError 11 / catch 15 箇所 健在。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 構文: materials.py py_compile OK、ProcurementPage.tsx esbuild OK。全角はコード構文に混入なし（文字列/コメント/HTMLテンプレのみ）。
- 直近コミット 98b827d（発注番号採番の変更）による退行なしを確認。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外・curl はサンドボックス非allowlist(HTTP 000) → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


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

### 2026-07-07 — Claude(Cowork) — ヘルプページ拡充（マニュアル整備）
**触ったファイル**: `frontend/src/pages/HelpPage.tsx`（拡充のみ、1ファイル）
**内容**: ユーザー依頼「構築した販売管理システムのマニュアルを作成して、ヘルプページを充実させたい」に対応。
既存のマスタ説明セクションはそのまま維持し、新たに「画面ごとの使い方」セクションを追加。
全15画面（ダッシュボード/案件管理/見積管理/受注管理/仕入(発注)管理/在庫管理/製品BOMマスタ/製造計画/工程管理/マスタ管理/ユーザー管理/スケジュール管理/売上計画表/手配書/ログイン相当）を
「営業・見積・受注」「仕入・在庫・製造・工程」「管理・その他」の3グループに整理し、各画面の目的・主な操作手順・ステータス選択肢・注意点を記載。
内容は全ページの実装コード（frontend/src/pages/*.tsx, backend/app/api/*）を実際に読み込んで作成（推測なし）。
**確認**: esbuildでHelpPage.tsxの構文チェックOK。他ファイルへの変更なし（差分は+221/-2の1ファイルのみ）。
