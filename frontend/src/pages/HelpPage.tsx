import { useState } from 'react';
import {
  HelpCircle, Database, Boxes, GitBranch, FileText, Factory, ClipboardList, Truck,
  Building2, MapPin, Users, Package, ChevronDown, ChevronRight,
  LayoutDashboard, ShoppingCart, BarChart3, Briefcase, UserCog, Calendar, ShoppingBag,
} from 'lucide-react';

// 画面ごとの使い方データ
const PAGE_GROUPS = [
  {
    key: 'sales', title: '営業・見積・受注', icon: Briefcase, color: 'text-blue-600',
    desc: '引き合いから受注・出荷までの営業フローに関わる画面です。',
    pages: [
      {
        name: 'ダッシュボード', icon: LayoutDashboard, route: '/',
        purpose: '今月の受注・見積状況や月別売上を確認する経営指標画面（閲覧専用）。',
        steps: [
          '年度セレクトで表示年度を切替（会計年度は3月始まり、2/21〜翌2/20）。',
          '上部KPIカードで今月の受注金額・件数、見積件数、受注中の案件を確認。',
          '月別売上グラフは「受注月／納品月」で表示を切替できる。',
          '案件ステータス別・見積ステータス別の内訳も一覧で確認できる。',
        ],
        note: '入力・編集はできません。数値を修正したい場合は元データ（案件・見積・受注）側で行います。',
      },
      {
        name: '案件管理', icon: Briefcase, route: '/projects',
        purpose: '引き合い〜売上計上までの「案件」と、見積・受注の単位となる「案件子ID」を管理する起点画面。',
        steps: [
          '「新規案件登録」で親案件を作成（案件IDは自動採番）。商流判定（直接／代理店）を選び、直接なら納入先、代理店なら商社＋納入先を指定し、営業担当・予算金額等を入力。',
          '新規登録時に「工番／単番」の区分を必須選択（受注票の種別になります。金額による自動判定は廃止）。「確度（高／中／低）」も任意で設定でき、案件一覧にバッジ表示され見込み管理に使えます。',
          '案件の行を開き「子ID追加」で子ID（見積・受注の単位）を作成（子IDも自動採番。1件目は「_A」等を自動付番）。子IDごとにも工番／単番を指定できます。',
          '子ID行の操作アイコンから「見積作成」「発注」「手配（クレーン／送り状／宿泊）」へ直接遷移できる。',
        ],
        status: ['営業中', '確度高', '内示', '受注', '検収済', '請求済', '入金済', '失注'],
        note: '案件ID・子IDは自動採番のため手入力不可。工番／単番が未設定の子IDは一覧で「未設定」と赤表示され、見積からの受注票発行ができません。出荷予定日・売上予定日は任意入力（未定でも登録可）。最終受注金額は発行済みの受注票から自動集計されます。',
      },
      {
        name: '見積管理', icon: FileText, route: '/estimates',
        purpose: 'BFR／SCA・SCD等の型式パターンを組み合わせて見積書を作成する画面（一覧＋作成フォーム）。承認ワークフロー付き。',
        steps: [
          '一覧上部の検索ボックスで見積番号・注文主・件名・子IDから既存見積を絞り込める。',
          'ログイン中のユーザー宛に承認依頼が届いている場合、一覧の上部に「◯◯さん宛の承認依頼が◯件あります」と黄色い通知が出ます。「確認して承認」からその見積を開けます。',
          '「新規見積作成」で案件子IDを検索・選択すると、件名・納入先・注文主・営業担当が自動入力される。',
          '「BFRパターン追加」「SCA/SCDパターン追加」ボタンで型式・オプションを選ぶだけで、本体＋関連オプションの明細を一括追加できる（手動追加も可）。明細には中分類を入力でき、同名が連続すると「1-1-1」形式で自動的に階層化されます。',
          '明細ごとに金額の表示方法（金額表示／非表示（一式内訳）／「含まず」）を選べます。「出精値引」に金額を入れると税抜小計から差し引かれ、値引後に課税されます。',
          '「作成（作成者）」はログインユーザーの一覧から選択します。支払条件は候補から選択（自由入力も可）。',
          '「社内工数」タブで据付・試運転などの社内工数（原価）を試算できます。※社内工数は見積金額には含まれません（社内原価の試算専用）。取付工費などを客先見積に載せる場合は明細行として入力してください。',
          '「検印（承認者）」を選んで「承認依頼を送る」と、承認者へ承認依頼メールが送信されます。承認者はメール内のリンクからワンクリックで、または画面の承認待ち通知の「承認する」から承認できます。承認までPDFには「draft」透かしが入ります（承認後に内容を保存し直すと承認は解除され再依頼が必要）。',
          '「CADから見積作成」でDXF図面をアップロードすると、型式を抽出して見積の骨格をdraftで自動生成できます（プロトタイプ）。',
          '保存後に「PDF出力」（見積書＋社内工数試算を1ファイルで出力）「受注票」発行（種別は案件の工番／単番区分に従う）「複製」が行える。',
        ],
        status: ['下書（下書き）', '承認待ち／承認済', '受注（採用済）', '受注済（受注票発行済）'],
        note: 'PDF出力は保存後のみ可能。受注票は案件子IDに工番／単番が設定されていないと発行できません。検印者はユーザー管理の機能権限「検印承認者」を持つ人から選べます。複製時は複製先の案件子IDの指定が必須です。受注票を発行するとステータスが「受注済」になります。承認依頼メールが送信できない環境では、承認者はログイン後の画面上部の承認待ち通知から承認できます。案件子IDは見積書・社内工数試算・承認依頼メールにも表示されます。CADからの自動生成はダクトが概算で、取付工費・運送費・工数は含まれないため必ず内容を確認してください。',
      },
      {
        name: '受注管理', icon: ShoppingCart, route: '/orders',
        purpose: '見積管理から発行された受注票の一覧と、受注に関わる項目（注文書有無・納期・前受金・出荷方法等）の管理画面（受注票そのものの新規作成は見積管理で行います）。',
        steps: [
          '受注番号・注文主・案件子IDで検索、種別（工番／単番）・状態（最新のみ／過去／全件）で絞り込み。',
          '受注番号はCOID（案件子ID）で表示され、票No.も併記される。一覧では注文主・納入先・受注日・出荷予定日・顧客納期・売上計上日・金額・注文書有無・納期・前受金を確認できる。',
          '各行の鉛筆アイコン「受注項目の編集」で、種別（工番/単番）・注文書の有無・納期・前受金（最大3回の分割入金）・出荷方法・受注日を登録・修正できる。ここで種別を変えると案件側にも反映されます。',
          '編集画面では元の見積書を「見積書を開く」で確認でき、注文書・契約書・図面等のPDF（1件10MBまで）を関連書類として保管・削除できます。',
          '各行の「PDF」アイコンで受注票PDFを表示。「＋見積書」ボタンで受注票と見積書をまとめて印刷できます。',
        ],
        status: ['工番（紫）', '単番（オレンジ）'],
        note: '種別は案件登録時に選択した工番／単番の区分に従います（この画面でも変更可・変更は案件側に反映）。見積を受注票として再発行すると、旧受注票は自動的に「過去」扱いとなり一覧から隠れます（「過去」フィルタで表示可能）。',
      },
    ],
  },
  {
    key: 'supply', title: '仕入・在庫・製造・工程', icon: Factory, color: 'text-orange-600',
    desc: '受注後の部材調達・在庫・製造スケジュールに関わる画面です。',
    pages: [
      {
        name: '仕入（発注）管理', icon: ShoppingBag, route: '/procurement',
        purpose: '発注書の作成・発注・入荷を扱う仕入業務の画面。',
        steps: [
          '「見積内訳から発注書作成」で受注採用済みの見積内訳をチェックして選び、納期を指定すると発注書を一括作成できる（発注番号は「子ID-内訳番号」）。',
          '発注書ごとにヘッダー（発注先・注文日・納入場所等）と明細（部材・数量・単価・納期）を編集。',
          '明細行の「入荷」「在庫引当」ボタンで在庫管理に反映される。',
          '部材の台帳やユニット構成の管理は「製品BOMマスタ」画面に集約。',
        ],
        status: ['作成中', '発注済', '一部入荷', '入荷済', 'キャンセル'],
        note: '発注書は「作成中」の間だけヘッダー・明細を編集できます。旧「発注・仕入管理」画面（発注書一覧のみの簡易版）も残っていますが、実務ではこちらを使用してください。',
      },
      {
        name: '在庫管理', icon: Boxes, route: '/inventory',
        purpose: '部材単位の在庫（在庫数＝入荷累計－利用累計）を管理する画面。',
        steps: [
          '「入出庫を登録」で部材を選び、区分（入荷／利用／引当／調整）・数量・日付を入力して登録。',
          '在庫が0以下の部材は赤字で警告表示される。',
          '各行の履歴アイコンから入出庫履歴（日付・区分・数量・関連案件）を確認できる。',
        ],
        note: '仕入（発注）管理での「入荷」「在庫引当」操作もこの画面の入荷累計・利用累計に反映されます。',
      },
      {
        name: '製品BOMマスタ', icon: GitBranch, route: '/bom-master',
        purpose: '「製品→ユニット→部材」の3階層で製品構成を定義するマスタ画面。部材の台帳（部材マスタ）もここに集約。',
        steps: [
          '「製品マスタ」「ユニットマスタ」タブでそれぞれの型式・標準単価等を登録。',
          '「製品構成（製品→ユニット）」「ユニット構成（ユニット→部品）」タブで、員数付きの構成を紐付ける。',
          '「部材マスタ」タブで部材の台帳（コード・名称・単位・優先仕入先・リードタイム）を管理。',
          '「見積パターンから取込」ボタンで既存の見積パターン（BFR・SCA等）を製品／ユニットマスタへ一括登録できる。',
        ],
        note: 'ユニットに部材まで紐付けておくと、仕入（発注）管理の「見積内訳から発注書作成」で部材が自動展開されます。',
      },
      {
        name: '製造計画', icon: Factory, route: '/manufacturing',
        purpose: '年度単位（3月始まり）で製造の工数負荷を計画・可視化する画面。',
        steps: [
          '「見積からドラフト作成」で受注採用済み見積の内訳行（ユニット単位）から製造計画を自動生成、または「計画追加」で手動登録。',
          '「ガント」タブで旬（月×週）単位の工数按分と、使用可能時間に対する超過（赤字表示）を確認。ガントは案件ID・納入先・地域も表示され、「PDF出力」で印刷できる。',
          '「生産能力マスタ」「製品所要工数マスタ」タブで、稼働可能時間や型番ごとの所要工数の基礎データを管理。',
        ],
        status: ['未着手', '製造中', '完了'],
        note: 'ユニット単位の計画では、同じ案件の負荷が重複計上されないよう代表行（is_primary）で集計されます。',
      },
      {
        name: '工程管理', icon: ClipboardList, route: '/process',
        purpose: '現場工事の日程をガントチャート形式で作成する工程表管理画面。',
        steps: [
          '案件子IDを検索するとヘッダー（顧客名・工事名・工番等）が自動入力される。納期は案件子IDの顧客納期から自動取得される。',
          '「テンプレートから自動生成」で、納期を基準にテンプレートの各工程を一括配置できる（既存の行は上書きされる点に注意）。',
          'ガントは日／週／月表示を切替でき、セルをクリックして工程バーの開始・終了日を指定。',
          '「テンプレート管理」タブで製品種別ごとの標準工程（工程名・納期からのオフセット日数・作業日数）を編集できる。',
          '「印刷」で日／週／月単位のPDFを出力できる。',
        ],
        status: ['作成中', '確定', '発行済'],
      },
    ],
  },
  {
    key: 'admin', title: '管理・その他', icon: Database, color: 'text-slate-600',
    desc: '社内の基礎データ・スケジュール・帳票類を管理する画面です。',
    pages: [
      {
        name: 'マスタ管理', icon: Database, route: '/masters',
        purpose: '商社・納入先・従業員・手配業者の基本マスタを登録する画面（詳細は下記「マスタの説明」を参照）。',
        steps: ['4タブ（商社／納入先／従業員／手配業者）を切替え、「新規登録」から追加、行の編集アイコンから修正。'],
      },
      {
        name: 'ユーザー管理', icon: UserCog, route: '/users',
        purpose: 'システムにログインするアカウントと権限を管理する画面。',
        steps: [
          '「新規ユーザー追加」で氏名・メール・権限・所属部門（営業／施工／製造／管理部）を登録（初期パスワードは user1234）。',
          '一覧には部門列が表示される。部門はスケジュールの絞込・閲覧権限に使われる（施工部門はスケジュール閲覧のみ）。',
          '「機能権限」（複数選択可）で担当する業務機能を指定できる。現在は「検印承認者」があり、付与すると見積管理の承認依頼先・検印者として選べるようになる。一覧に機能権限列が表示される。',
          '鍵アイコンからパスワード変更、編集アイコンから氏名・部門・機能権限等の修正、不要なアカウントは無効化できる。',
        ],
        status: ['user（一般）', 'admin（管理者）'],
        note: '管理者（admin）アカウントは誤って無効化しないよう削除ボタンが表示されません。見積の承認機能を使うには、機能権限「検印承認者」を持つユーザーを1名以上登録してください。',
      },
      {
        name: 'スケジュール管理', icon: Calendar, route: '/schedule',
        purpose: '全社員の予定（午前／午後）をガント風に登録する画面。全ユーザーが対象。',
        steps: [
          '「週」／「月」表示を切替でき、前週/次週（前月/次月）ボタンで期間を移動。空いているセルをクリックして予定を登録。',
          '対象者は複数選択可、終日／午前／午後・色（6色）を指定できる。',
          '部門フィルタ（全部門／営業／施工／製造／管理部）で表示を絞り込める。',
          '既存の予定はドラッグ＆ドロップで別の担当者・日時へ移動できる。',
          '「PDF出力」で表示中の予定表を印刷できる。',
        ],
        note: '施工部門のユーザーは閲覧のみ（「閲覧のみ」表示）。編集は管理者と他部門のみ可能です。',
      },
      {
        name: '売上計画表', icon: BarChart3, route: '/sales-plan',
        purpose: '案件の月別・年度別の売上見込みを一覧化し、印刷できるレポート画面。納入先を最左列に表示。',
        steps: [
          '年度・ステータス（複数選択。確度高を含む）で表示対象を絞り込み。',
          '「PDF出力」でA3横のレポートを生成し印刷できる。',
        ],
        note: '営業中・確度高・内示は案件の予算金額を採用（受注以降は見積金額）。これらは0円でも一覧に個別表示されます。税抜合計金額300万円未満（単番）の案件は個別表示せず最下部に集計します。単番の集計は経過月（先月まで）が実数、今月以降は個別の見積が出揃わないため25M/月の見込みで計上します。合計行・単番集計・各行の合計欄は、該当データが無くても空欄にせず「0」と表示します。',
      },
      {
        name: '手配書（クレーン／送り状／宿泊）', icon: Truck, route: '案件管理の子ID行から作成',
        purpose: 'クレーン依頼書・送り状・宿泊手配書を作成する機能。専用ページはなく、案件管理の子ID行のボタンから開きます。',
        steps: [
          '案件管理で対象の子IDを開き、手配ボタン（クレーン／送り状／宿泊）をクリック。',
          '手配業者マスタから業者を選ぶと、連絡先が自動転記される。',
        ],
      },
    ],
  },
];

// マスタ説明データ
const SECTIONS = [
  {
    key: 'basic', title: '基本マスタ（マスタ管理）', icon: Database, color: 'text-blue-600',
    desc: '取引先や担当者など、各種書類・案件で繰り返し使う基本情報です。「マスタ管理」メニューで登録・編集します。',
    items: [
      { name: '商社マスタ', icon: Building2, use: '代理店・商社の情報（コード／名称／支店／担当／電話／取引条件）。', where: 'マスタ管理 → 商社マスタ', link: '案件の代理店、見積・請求の宛先に利用。' },
      { name: '納入先マスタ', icon: MapPin, use: '製品の納入先（会社名／工場名／住所／TEL／FAX）。', where: 'マスタ管理 → 納入先マスタ', link: '案件・手配書（送り状/依頼書）の納入先住所の補完に利用。' },
      { name: '従業員マスタ', icon: Users, use: '自社の従業員（ID／氏名／部署）。', where: 'マスタ管理 → 従業員マスタ', link: '見積・案件の「営業担当」の選択肢に利用。' },
      { name: '手配業者マスタ', icon: Truck, use: 'クレーン業者・運送業者（区分／業者名／営業所／担当／TEL／FAX）。', where: 'マスタ管理 → 手配業者マスタ', link: '手配書（クレーン依頼書／送り状）で選択すると連絡先を自動補完。' },
    ],
  },
  {
    key: 'product', title: '製品・部材マスタ（製品BOMマスタ／仕入管理）', icon: GitBranch, color: 'text-indigo-600',
    desc: '「型式 → ユニット → 部材」の階層で製品構成を定義します。見積で選んだ型式から、必要なユニット・部材を仕入・在庫へ展開する土台です。',
    items: [
      { name: '部材マスタ', icon: Boxes, use: '原材料・部品（部材コード／部材名／単位／優先仕入先／リードタイム）。', where: '製品BOMマスタ → 部材マスタ', link: '在庫・発注・ユニット構成の基礎データ。' },
      { name: '製品マスタ', icon: Package, use: '本体系の製品（製品コード／製品名／種別／標準販売単価）。', where: '製品BOMマスタ → 製品マスタ', link: '見積パターンから取込可能。製品構成BOMの親。' },
      { name: 'ユニットマスタ（型式）', icon: Boxes, use: 'ファン・RV・サイクロン等のユニット（型式／標準販売単価）。', where: '製品BOMマスタ → ユニットマスタ', link: '仕入の「ユニットから発注書作成」で選択。部材を紐付ける親。' },
      { name: '製品構成BOM', icon: GitBranch, use: '「製品にどのユニットを何個」を員数つきで定義。', where: '製品BOMマスタ → 製品構成（製品→ユニット）', link: '見積/発注でユニット候補を出す。' },
      { name: 'ユニット構成BOM', icon: GitBranch, use: '「ユニットにどの部材を何個」を員数つきで定義。', where: '製品BOMマスタ → ユニット構成（ユニット→部品）', link: '仕入の「ユニットから取込」で部材を自動セット。' },
    ],
  },
  {
    key: 'estimate', title: '見積パターンマスタ（見積管理）', icon: FileText, color: 'text-green-600',
    desc: '見積作成時に型式を選ぶための価格・仕様の定義です。製品BOMマスタへ「見積パターンから取込」で連携できます。',
    items: [
      { name: 'BFR本体／ファン／RV', icon: FileText, use: 'BFR集塵機の本体・ターボファン・ロータリーバルブの型式と価格。', where: '見積管理（パターン選択時）', link: '見積の「BFRパターン追加」で使用。製品/ユニットマスタへ取込可。' },
      { name: 'SCA本体／PLファン／サイクロン', icon: FileText, use: 'SCA定量排出装置の本体・付属の型式と価格。', where: '見積管理（パターン選択時）', link: '見積の「SCA/SCDパターン追加」で使用。' },
      { name: '社内工数（労務）', icon: FileText, use: '据付・試運転等の社内工数項目と単価。', where: '見積管理（社内工数タブ）', link: '社内工数（原価）の試算に使用。見積金額には含まれません。' },
    ],
  },
  {
    key: 'manufacturing', title: '製造・工程マスタ', icon: Factory, color: 'text-orange-600',
    desc: '製造の負荷計算や工程表の自動生成に使うマスタです。',
    items: [
      { name: '生産能力マスタ', icon: Factory, use: '工場の月別 稼働日数・人員・1日工数（＝使用可能時間）。', where: '製造計画 → 生産能力マスタ', link: '製造計画の月別/週別「使用可能時間」と超過判定に利用。' },
      { name: '製品所要工数マスタ', icon: Factory, use: '製品種別×型番ごとの所要工数(h)。', where: '製造計画 → 製品所要工数マスタ', link: '製造計画の「計画工数」算定に利用（型番は表記ゆれを正規化して突合）。' },
      { name: '工程テンプレート', icon: ClipboardList, use: '製品種別ごとの標準工程（工程名・納期からのオフセット・日数）。', where: '工程管理 → テンプレート管理', link: '工程表の「テンプレートから自動生成」で利用。' },
    ],
  },
];

const FLOW = [
  { step: '案件', desc: '引き合い→案件子IDを起票' },
  { step: '見積', desc: '型式を選んで見積作成・検印承認・受注採用' },
  { step: '受注', desc: '受注票発行・最終受注金額確定' },
  { step: '発注／在庫', desc: 'ユニットから発注書作成・在庫引当/入荷' },
  { step: '製造計画', desc: '所要工数で負荷・ガント' },
  { step: '工程', desc: '工程表を自動生成・印刷' },
  { step: '手配', desc: 'クレーン/送り状を業者選択で作成' },
];

export default function HelpPage() {
  const [open, setOpen] = useState<Record<string, boolean>>(
    Object.fromEntries(SECTIONS.map(s => [s.key, true]))
  );
  const toggle = (k: string) => setOpen(o => ({ ...o, [k]: !o[k] }));

  const [openPages, setOpenPages] = useState<Record<string, boolean>>({ sales: true, supply: false, admin: false });
  const togglePages = (k: string) => setOpenPages(o => ({ ...o, [k]: !o[k] }));

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center gap-2 mb-1">
        <HelpCircle size={24} className="text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-800">ヘルプ — 使い方・マスタの説明</h1>
      </div>
      <p className="text-sm text-gray-500 mb-5">「業務の流れ」「画面ごとの使い方」「マスタの説明」の3つに分けてまとめています。マスタを整えるほど、見積→発注→製造→手配が自動でつながります。</p>

      {/* 全体の流れ */}
      <div className="bg-white border rounded-xl p-4 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">業務の流れとマスタの関係</h2>
        <div className="flex items-stretch gap-1 flex-wrap">
          {FLOW.map((f, i) => (
            <div key={i} className="flex items-center">
              <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 min-w-[110px]">
                <div className="text-sm font-bold text-blue-700">{f.step}</div>
                <div className="text-[11px] text-gray-500 leading-tight mt-0.5">{f.desc}</div>
              </div>
              {i < FLOW.length - 1 && <ChevronRight size={16} className="text-gray-300 mx-0.5" />}
            </div>
          ))}
        </div>
      </div>

      {/* 画面ごとの使い方 */}
      <h2 className="text-base font-bold text-gray-800 mt-2 mb-3">画面ごとの使い方</h2>
      <div className="space-y-4 mb-8">
        {PAGE_GROUPS.map(group => {
          const GroupIcon = group.icon;
          return (
            <div key={group.key} className="bg-white border rounded-xl overflow-hidden">
              <button onClick={() => togglePages(group.key)}
                className="w-full flex items-center gap-2 px-4 py-3 hover:bg-gray-50 text-left">
                <GroupIcon size={18} className={group.color} />
                <span className="font-semibold text-gray-800">{group.title}</span>
                <span className="ml-auto text-gray-400">{openPages[group.key] ? <ChevronDown size={18} /> : <ChevronRight size={18} />}</span>
              </button>
              {openPages[group.key] && (
                <div className="px-4 pb-4">
                  <p className="text-xs text-gray-500 mb-3">{group.desc}</p>
                  <div className="space-y-3">
                    {group.pages.map((p, i) => {
                      const PIcon = p.icon;
                      return (
                        <div key={i} className="border border-gray-200 rounded-lg p-3">
                          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                            <PIcon size={15} className="text-gray-400 shrink-0" />
                            <span className="font-medium text-gray-800 text-sm">{p.name}</span>
                            <span className="ml-auto text-[11px] text-gray-400">{p.route}</span>
                          </div>
                          <p className="text-xs text-gray-600 mb-2">{p.purpose}</p>
                          {p.steps && (
                            <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5 mb-2">
                              {p.steps.map((s, j) => <li key={j}>{s}</li>)}
                            </ul>
                          )}
                          {p.status && (
                            <div className="flex flex-wrap gap-1 mb-2">
                              {p.status.map((s, j) => (
                                <span key={j} className="text-[11px] px-2 py-0.5 bg-gray-100 text-gray-600 rounded">{s}</span>
                              ))}
                            </div>
                          )}
                          {p.note && (
                            <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1">{p.note}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* マスタ各セクション */}
      <h2 className="text-base font-bold text-gray-800 mb-3">マスタの説明</h2>
      <div className="space-y-4">
        {SECTIONS.map(sec => {
          const SecIcon = sec.icon;
          return (
            <div key={sec.key} className="bg-white border rounded-xl overflow-hidden">
              <button onClick={() => toggle(sec.key)}
                className="w-full flex items-center gap-2 px-4 py-3 hover:bg-gray-50 text-left">
                <SecIcon size={18} className={sec.color} />
                <span className="font-semibold text-gray-800">{sec.title}</span>
                <span className="ml-auto text-gray-400">{open[sec.key] ? <ChevronDown size={18} /> : <ChevronRight size={18} />}</span>
              </button>
              {open[sec.key] && (
                <div className="px-4 pb-4">
                  <p className="text-xs text-gray-500 mb-3">{sec.desc}</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr className="bg-gray-50 text-gray-600 text-xs">
                          <th className="border border-gray-200 px-3 py-2 text-left w-48">マスタ</th>
                          <th className="border border-gray-200 px-3 py-2 text-left">用途</th>
                          <th className="border border-gray-200 px-3 py-2 text-left w-56">登録場所</th>
                          <th className="border border-gray-200 px-3 py-2 text-left">連携・使われ方</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sec.items.map((it, i) => {
                          const ItIcon = it.icon;
                          return (
                            <tr key={i} className="hover:bg-gray-50 align-top">
                              <td className="border border-gray-200 px-3 py-2">
                                <div className="flex items-center gap-1.5 font-medium text-gray-800">
                                  <ItIcon size={14} className="text-gray-400 shrink-0" />{it.name}
                                </div>
                              </td>
                              <td className="border border-gray-200 px-3 py-2 text-gray-600">{it.use}</td>
                              <td className="border border-gray-200 px-3 py-2 text-gray-500 whitespace-nowrap text-xs">{it.where}</td>
                              <td className="border border-gray-200 px-3 py-2 text-gray-600 text-xs">{it.link}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="text-xs text-gray-400 mt-6">
        ※ マスタの「取込」機能：製品BOMマスタの「見積パターンから取込」、手配業者マスタ・部材マスタの一括取込など、既存データから素早く初期登録できます。
      </p>
    </div>
  );
}
