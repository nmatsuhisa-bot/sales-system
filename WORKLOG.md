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

### 2026-07-20 — Claude(Cowork) — マニュアルを最新機能へ同期（見積: 承認待ち通知・承認メール・社内工数の扱い変更）
**触ったファイル**: `frontend/src/pages/HelpPage.tsx`・`WORKLOG.md`
**基準**: HelpPage 最終更新 f8e869a〜HEAD のユーザー向けページ変更を反映。
**反映した主な変更**:
- 見積管理: ログイン中ユーザー宛の「承認待ち通知」バナー（EstimateListPage）と「確認して承認」導線を追記。
- 見積管理: 承認依頼のメール通知＋メールからのワンクリック承認を承認フロー手順に反映。
- 見積フォーム: 社内工数は見積金額に含めない方針変更（社内原価の試算専用）を steps と 社内工数マスタ説明・note に明記。
- 見積フォーム: 「作成（作成者）」がログインユーザー選択になった点を追記。
- PDF出力が「見積書＋社内工数試算を1ファイル」出力である点、案件子IDが見積書・工数試算・承認依頼メールに表示される点を note に追記。
**対象外**: ProcurementPage の発注書一覧エラーバナー（退行修正・使い方に影響なし）、tools/dwg2dxf.sh・backend(mailer/pdf/models/main) は内部/設定のためヘルプ非対象。
**静的検査**: esbuild で HelpPage.tsx 構文チェック成功。
**方針**: HelpPage.tsx と WORKLOG.md のみ変更（非破壊）。

### 2026-07-20 — Claude(Cowork) — /procurement 発注書リストのエラー握り潰しを是正
**触ったファイル**: `frontend/src/pages/ProcurementPage.tsx`・`WORKLOG.md`
**内容**: `PurchaseOrdersTab` の発注書一覧 `load()` が `.catch(() => {})` でエラーを握り潰しており、
GET /purchase-orders が500等で失敗すると画面が無言で「発注書なし」表示になっていた（退行）。
`loadError` state を追加し、失敗時に赤バナーで通知、成功時にクリアするよう修正（非破壊・フロントのみ）。
**静的検査**: 全 procurementApi 32系統 = api/index.ts 定義 = materials.py 実ルートに一致（不一致なし）。
route順序も breakdowns/from-units 等が `{po_id}` より前で安全。P-03/P-05 の0値表示（_mo_dict L439-440、
発注書HTML L799-801）は `is not None` 維持でOK。total_amount は常に int で NaN 表示リスクなし。
新規発注バリデーション（部材未選択 alert / 受入数量 <=0 alert）健在。
**検証**: esbuild で ProcurementPage.tsx 構文チェック成功。
**ライブAPI/UI**: 無人実行のため web_fetch は対象ドメインが provenance 外で不可 → 静的解析で対応。
**バグ検出**: P-06(新規) 発注書一覧のエラー握り潰し → 修正push済。他は異常なし。

### 2026-07-19 — Claude(Cowork) — マニュアル（ヘルプ）を最新機能へ同期
**触ったファイル**: `frontend/src/pages/HelpPage.tsx`・`WORKLOG.md`
**基準**: HelpPage 最終更新 `a465227`(07-18) 〜 HEAD。反映した主なユーザー向け変更:
- 案件管理: 工番/単番を登録時の必須選択に（金額自動判定廃止）、確度(高/中/低)追加、未設定子IDの赤表示。
- 見積管理: 承認ワークフロー（検印依頼→承認、承認までdraft透かし）、出精値引、明細の中分類(1-1-1階層)・金額表示制御(非表示/含まず)、支払条件候補、CADから見積作成(プロトタイプ)。列/検索を「顧客名→注文主」。受注票発行は案件の工番/単番区分に従う。
- 受注管理: 受注票+見積書の同時印刷(+見積書)、元見積プレビュー、関連書類PDF(注文書/契約書等・10MB)保管。種別は案件区分に従う。
- ユーザー管理: 機能権限(複数選択・現状「検印承認者」)を追加。
- 売上計画表: 合計/単番集計/各行合計欄は0でも「0」表示。
**検証**: esbuild で HelpPage.tsx の構文チェック成功。HelpPage.tsx と WORKLOG.md のみ変更（機能コードは不変）。


### 2026-07-19 — Claude(Cowork) — /procurement 検証（異常なし）
**触ったファイル**: `WORKLOG.md` のみ（コード変更なし）
**検証結果**: 静的解析で退行なし。前回検証(07-18)以降 origin/main の新規コミットは `0632525`(メモリ上限/estimate_quotations.py)・`8851302`(projects.py 工番/単番必須)・`eb7b2f4`(見積合計半角)・`e1b7b68`/`1be0b4b`/`2a3cddf`(検印承認者=機能権限化 users/roles) 等。**うち procurement 関連ファイルの実質変更は無し**。
- models.py の差分は `users.function_roles`(JSON列)追加のみ＝MaterialMaster/BomItem/MaterialOrder/Supplier 各定義は不変。api/index.ts の差分は function-roles/approvers 系の追加のみ＝procurementApi 17系統に変更なし。
- エンドポイント整合: ProcurementPage.tsx の procurementApi 参照17系統すべて api/index.ts 定義および materials.py 実ルートに一致（MISSING なし）。
- P-03/P-05 0値表示: `_mo_dict`(L439-440) order_qty/unit_price、発注書HTML(L799-800) qty/price ともに `is not None` 維持。amount は `or 0` で¥0正常。
- 新規発注バリデーション: `!newLine.material_id`(L264) alert / 受入数量 `qty<=0`(L289) alert 健在。
- 構文: materials.py・models.py py_compile OK、ProcurementPage.tsx・api/index.ts esbuild OK。
**ライブAPI/UI確認**: 無人実行のため web_fetch は対象ドメイン provenance外 → 静的解析で対応。
**運用メモ**: P-02（既存DBに material_orders.order_no/project_unit_id 列が無い場合 GET /material-orders が500）は `/setup-bom-master-tables` 実行済み前提で本番影響なし。
**バグ検出**: なし（異常なし）。push はWORKLOG更新のみ。


### 2026-07-18（続5） — Claude(Opus) — 検印承認者を機能権限化（e1b7b68）
**変更**: 検印者のハードコード（`APPROVERS = [...]`）を廃止し、ユーザーマスタの
**機能権限**で管理する方式へ。1ユーザーが複数の役割を担える設計。
- `users.function_roles`（JSON配列）を追加。**基本権限(admin/staff)とは別軸**
- `backend/app/roles.py` に定義を集約（`FUNCTION_ROLES`）

> **機能権限を追加する手順（重要）**
> 1. `app/roles.py` の `FUNCTION_ROLES` に1件追加する（key/label/description）
> 2. 使う側で `has_role(user,"key")` か `users_with_role(db,"key")` を呼ぶ
>
> **DBマイグレーション不要**（JSON配列のため）。ユーザー管理画面のチェックボックスも
> `GET /auth/function-roles` 経由で自動生成されるため、画面側の改修も不要。

- `GET /estimate-quotations/approvers` はユーザーマスタから `approver` 権限保持者を返す
- 承認依頼時に権限を検証（権限を外された人は指定できない → 400）
- マイグレーション: `GET /setup-function-roles`（会議決定の5名に氏名の部分一致で自動付与）
- **注意**: 承認者の判定は `full_name` の一致で行っている。ユーザーの氏名を変更すると
  既存見積の `approver_name` と一致しなくなる（表示は残るが再承認時に弾かれる）

### 2026-07-18（続4） — Claude(Opus) — 許可プロンプト削減の調査（コード変更なし）
**結論**: 設定では解決できないため、**作業の書き方を変える**方針にした。
- Bashの確認発生源は実測で `curl`(542回) と `python3`(399回) の2つのみ
- **MCPツール（Claude_Browser系）は元々確認なしで通っている**（200回以上使用しても
  `settings.local.json` に一切蓄積されていない）。当初これを許可リストに追加したが
  無意味と判明したため `.claude/settings.json` は**削除済み**
- `curl` の全面許可は不可（前方一致のため `-X DELETE` を付けた呼び出しも通る。
  本番APIには削除系と、GETでDBを変更する `/setup-*` がある）
- `python3` の全面許可も不可（任意コード実行）
- 既存 `settings.local.json` は420件あるが大半が完全一致の使い捨てルールで再利用されない

### 2026-07-18（続3） — Claude(Opus) — 数字の全角化を撤回・会議資料作成
**訂正**: 会議録の「数字の表記は一旦全角に統一」は**誤り**。ユーザーより
「数字ではなくテキスト（案件名・取引先名など）の全角半角の話。数字は半角で問題なし」と訂正。
- `_zenkaku_amount()` と頭紙合計金額の全角表記を**撤回**（`￥91,500,000-` の半角表示に戻した）
- テキストの正規化は既存の NFKC（`app/normalize.py`）で対応済み＝英数字は半角・半角カナは全角
- `docs/0807会議資料_要件と実装状況.md` を新規作成（先方共有用。実装15項目・未実装9項目）
> **注意**: 会議サマリーPDFは音声起こしのため誤りが混じる（他にも「ご教義」→「御協議」、
> 「牽引」→「検印」の誤変換あり）。**原本の見積・図面と突き合わせて確認すること**。

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
**注意**: 頭紙の合計金額を全角表記にしていたが、2026-07-18に**撤回済み**（数字は半角が正。上の「続3」参照）

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
