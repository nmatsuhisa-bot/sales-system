import { useState } from 'react';
import {
  HelpCircle, Database, Boxes, GitBranch, FileText, Factory, ClipboardList, Truck,
  Building2, MapPin, Users, Package, ChevronDown, ChevronRight,
} from 'lucide-react';

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
      { name: '部材マスタ', icon: Boxes, use: '原材料・部品（部材コード／部材名／単位／優先仕入先／リードタイム）。', where: '仕入（発注）管理 → 部材マスタ', link: '在庫・発注・ユニット構成の基礎データ。' },
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
      { name: '社内工数（労務）', icon: FileText, use: '据付・試運転等の社内工数項目と単価。', where: '見積管理（社内工数タブ）', link: '見積の労務費計上に使用。' },
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
  { step: '見積', desc: '型式を選んで見積作成・受注採用' },
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

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center gap-2 mb-1">
        <HelpCircle size={24} className="text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-800">ヘルプ — マスタの説明</h1>
      </div>
      <p className="text-sm text-gray-500 mb-5">各マスタの「用途・登録場所・連携先」をまとめています。マスタを整えるほど、見積→発注→製造→手配が自動でつながります。</p>

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

      {/* マスタ各セクション */}
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
