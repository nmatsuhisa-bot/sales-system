import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { mastersApi, arrangementApi, estimateApi } from '../api';
import UsersPage from './UsersPage';
import { Plus, Edit2, Trash2, Search, Building2, MapPin, Users, Truck, FileText } from 'lucide-react';

type Tab = 'agencies' | 'destinations' | 'users' | 'vendors' | 'texts';
const TAB_KEYS: Tab[] = ['agencies', 'destinations', 'users', 'vendors', 'texts'];

// 見積書の定型文。キーと画面に出す名前
const TEXT_LABELS: [string, string][] = [
  ['title', '表題'],
  ['label_delivery_terms', '納入期限のラベル'],
  ['label_delivery_place', '受渡場所のラベル'],
  ['label_valid_until', '見積有効期限のラベル'],
  ['label_payment_terms', '御支払条件のラベル'],
  ['label_subtotal', '小計のラベル'],
  ['label_discount', '値引のラベル'],
  ['label_total', '合計のラベル'],
  ['label_section_subtotal', '大分類の小計ラベル'],
  ['th_no', '表の見出し: 番号'],
  ['th_name', '表の見出し: 品名・仕様'],
  ['th_qty', '表の見出し: 数量'],
  ['th_price', '表の見出し: 単価'],
  ['th_amount', '表の見出し: 金額'],
  ['detail_suffix', '内訳ページの表題に付ける語'],
  ['tax_note_excluded', '税抜表示のときの注記'],
  ['exclusions_title', '除外事項の見出し'],
  ['company_name', '会社名'],
  ['company_address', '住所'],
  ['company_tel', 'TEL・FAX'],
  ['company_email', 'E-mail'],
];
const VENDOR_CATEGORIES = ['クレーン・作業車', '運送（トラック）', 'その他'];

export default function MastersPage() {
  // ?tab=users のように URL で開くタブを指定できる（旧「ユーザー管理」メニューからの移動先）
  const [params] = useSearchParams();
  const initialTab = params.get('tab') as Tab | null;
  const [tab, setTab] = useState<Tab>(initialTab && TAB_KEYS.includes(initialTab) ? initialTab : 'agencies');
  const [usersOpenSignal, setUsersOpenSignal] = useState(0);
  const [agencies, setAgencies] = useState<any[]>([]);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [vendors, setVendors] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [modal, setModal] = useState<any>(null);
  const [form, setForm] = useState<any>({});

  // 見積書の定型文
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [textDefaults, setTextDefaults] = useState<Record<string, string>>({});
  const [savingTexts, setSavingTexts] = useState(false);
  const [textMsg, setTextMsg] = useState('');

  useEffect(() => {
    estimateApi.getTexts()
      .then(r => { setTextDefaults(r.data.defaults || {}); setTexts(r.data.values || {}); })
      .catch(() => {});
  }, []);

  const saveTexts = async () => {
    setSavingTexts(true); setTextMsg('');
    try {
      const r = await estimateApi.saveTexts(texts);
      setTexts(r.data.values || texts);
      setTextMsg('保存しました');
      setTimeout(() => setTextMsg(''), 3000);
    } catch (e: any) {
      alert(e.response?.data?.detail || '保存に失敗しました');
    } finally { setSavingTexts(false); }
  };

  const loadAll = () => {
    mastersApi.listAgencies(search || undefined).then(r => setAgencies(r.data));
    mastersApi.listDeliveryDestinations(search || undefined).then(r => setDestinations(r.data));
    arrangementApi.listVendors(undefined, search || undefined).then(r => setVendors(r.data));
  };

  useEffect(() => { loadAll(); }, [search]);

  const F = ({ label, name, type = 'text' }: any) => (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input type={type} value={form[name] || ''}
        onChange={e => setForm((f: any) => ({ ...f, [name]: e.target.value }))}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
    </div>
  );

  const handleSave = async () => {
    try {
      if (tab === 'agencies') {
        if (modal.id) await mastersApi.updateAgency(modal.id, form);
        else await mastersApi.createAgency(form);
      } else if (tab === 'destinations') {
        if (modal.id) await mastersApi.updateDeliveryDestination(modal.id, form);
        else await mastersApi.createDeliveryDestination(form);
      } else {
        if (modal.id) await arrangementApi.updateVendor(modal.id, form);
        else await arrangementApi.createVendor(form);
      }
      setModal(null);
      loadAll();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラーが発生しました');
    }
  };

  const handleDelete = async (item: any) => {
    if (!confirm('削除しますか？')) return;
    if (tab === 'agencies') await mastersApi.deleteAgency(item.id);
    else if (tab === 'destinations') await mastersApi.deleteDeliveryDestination(item.id);
    else await arrangementApi.deleteVendor(item.id);
    loadAll();
  };

  const openNew = () => { if (tab === 'users') { setUsersOpenSignal(n => n + 1); return; } setForm({}); setModal({}); };
  const openEdit = (item: any) => { setForm({ ...item }); setModal(item); };

  const tabs = [
    { key: 'agencies', label: '商社マスタ', icon: Building2, count: agencies.length },
    { key: 'destinations', label: '納入先マスタ', icon: MapPin, count: destinations.length },
    { key: 'users', label: '従業員・ユーザー', icon: Users, count: null },
    { key: 'vendors', label: '手配業者マスタ', icon: Truck, count: vendors.length },
    { key: 'texts', label: '見積書の文言', icon: FileText, count: TEXT_LABELS.length },
  ];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">マスタ管理</h1>
        {tab !== 'texts' && (
          <button onClick={openNew}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
            <Plus size={16} /> 新規登録
          </button>
        )}
      </div>

      {/* タブ */}
      <div className="flex gap-2 mb-4">
        {tabs.map(({ key, label, icon: Icon, count }) => (
          <button key={key} onClick={() => setTab(key as Tab)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === key ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
            }`}>
            <Icon size={15} /> {label}
            {count !== null && <span className={`px-1.5 py-0.5 rounded-full text-xs ${tab === key ? 'bg-blue-500' : 'bg-gray-100 text-gray-500'}`}>
              {count}
            </span>}
          </button>
        ))}
      </div>

      {/* 検索（文言タブでは使わない） */}
      {tab !== 'texts' && (
        <div className="bg-white rounded-xl shadow-sm p-3 mb-4 flex items-center gap-2">
          <Search size={15} className="text-gray-400" />
          <input placeholder="名称・コードで検索" value={search}
            onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        </div>
      )}

      {/* 見積書の文言（全社共通。空欄にすると初期値に戻る） */}
      {tab === 'texts' && (
        <div className="bg-white rounded-xl shadow-sm p-4">
          <p className="text-xs text-gray-500 mb-3">
            見積書に印字される固定の文言です。変更すると、以後に作る見積書・印刷・PDFすべてに反映されます
            （保存済みの見積の金額や明細は変わりません）。空欄にして保存すると初期値に戻ります。
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {TEXT_LABELS.map(([key, label]) => (
              <div key={key}>
                <label className="block text-xs text-gray-500 mb-1">
                  {label}
                  {texts[key] !== textDefaults[key] && <span className="ml-1 text-blue-500">（変更済み）</span>}
                </label>
                <input value={texts[key] ?? ''}
                  onChange={e => setTexts(t => ({ ...t, [key]: e.target.value }))}
                  placeholder={textDefaults[key]}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-3 mt-4">
            <button onClick={saveTexts} disabled={savingTexts}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
              {savingTexts ? '保存中…' : '文言を保存'}
            </button>
            <button onClick={() => setTexts({ ...textDefaults })}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">
              すべて初期値に戻す
            </button>
            {textMsg && <span className="text-sm text-green-600">{textMsg}</span>}
          </div>
        </div>
      )}

      {/* 商社マスタ */}
      {tab === 'agencies' && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">商社コード</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">商社名</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">支店名</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">担当者</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">電話番号</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">取引条件</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {agencies.map(a => (
                <tr key={a.id} className="hover:bg-blue-50">
                  <td className="px-4 py-3 font-medium text-blue-600">{a.agency_code}</td>
                  <td className="px-4 py-3 font-medium text-gray-800">{a.agency_name}</td>
                  <td className="px-4 py-3 text-gray-500">{a.branch_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{a.contact_person || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{a.phone || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{a.trade_terms || '—'}</td>
                  <td className="px-4 py-3 text-center flex items-center justify-center gap-2">
                    <button onClick={() => openEdit(a)} className="text-blue-400 hover:text-blue-600"><Edit2 size={14} /></button>
                    <button onClick={() => handleDelete(a)} className="text-red-300 hover:text-red-500"><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {agencies.length === 0 && <div className="text-center py-10 text-gray-400">データがありません</div>}
        </div>
      )}

      {/* 納入先マスタ */}
      {tab === 'destinations' && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">顧客ID</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">会社名</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">工場名</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">住所</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">TEL</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">ランク</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {destinations.map(d => (
                <tr key={d.id} className="hover:bg-blue-50">
                  <td className="px-4 py-3 font-medium text-blue-600">{d.customer_id}</td>
                  <td className="px-4 py-3 font-medium text-gray-800">{d.company_name}</td>
                  <td className="px-4 py-3 text-gray-500">{d.factory_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{d.address || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{d.tel || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{d.customer_rank || '—'}</td>
                  <td className="px-4 py-3 text-center flex items-center justify-center gap-2">
                    <button onClick={() => openEdit(d)} className="text-blue-400 hover:text-blue-600"><Edit2 size={14} /></button>
                    <button onClick={() => handleDelete(d)} className="text-red-300 hover:text-red-500"><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {destinations.length === 0 && <div className="text-center py-10 text-gray-400">データがありません</div>}
        </div>
      )}

      {/* 従業員・ユーザー（旧・従業員マスタとユーザー管理を統合） */}
      {tab === 'users' && <UsersPage search={search} openSignal={usersOpenSignal} />}
      {/* 手配業者マスタ */}
      {tab === 'vendors' && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">区分</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">業者名</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">営業所</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">担当</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">TEL</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">FAX</th>
                <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {vendors.map(v => (
                <tr key={v.id} className="hover:bg-blue-50">
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{v.category || '—'}</td>
                  <td className="px-4 py-3 font-medium text-gray-800">{v.name}</td>
                  <td className="px-4 py-3 text-gray-500">{v.branch || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{v.contact_person || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{v.phone || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{v.fax || '—'}</td>
                  <td className="px-4 py-3 text-center flex items-center justify-center gap-2">
                    <button onClick={() => openEdit(v)} className="text-blue-400 hover:text-blue-600"><Edit2 size={14} /></button>
                    <button onClick={() => handleDelete(v)} className="text-red-300 hover:text-red-500"><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {vendors.length === 0 && <div className="text-center py-10 text-gray-400">該当なし（検索で絞り込み／最大50件表示）</div>}
          <div className="px-4 py-2 text-xs text-gray-400 border-t">※ 多数登録のため検索で絞り込み表示（最大50件）</div>
        </div>
      )}

      {/* モーダル */}
      {modal !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-gray-800 mb-4">
              {modal.id ? '編集' : '新規登録'} — {tabs.find(t => t.key === tab)?.label}
            </h2>
            <div className="space-y-3">
              {tab === 'agencies' && (<>
                <F label="商社コード *" name="agency_code" />
                <F label="商社名 *" name="agency_name" />
                <F label="支店名" name="branch_name" />
                <F label="取引条件" name="trade_terms" />
                <F label="住所（請求先）" name="address" />
                <F label="担当者名" name="contact_person" />
                <F label="電話番号" name="phone" />
              </>)}
              {tab === 'destinations' && (<>
                <F label="顧客ID *" name="customer_id" />
                <F label="会社名 *" name="company_name" />
                <F label="工場名" name="factory_name" />
                <F label="会社名_工場名" name="company_factory_name" />
                <F label="郵便番号" name="postal_code" />
                <F label="都道府県" name="prefecture" />
                <F label="住所" name="address" />
                <F label="TEL" name="tel" />
                <F label="FAX" name="fax" />
                <F label="顧客ランク" name="customer_rank" />
                <div>
                  <label className="block text-xs text-gray-500 mb-1">備考</label>
                  <textarea value={form.notes || ''} rows={2}
                    onChange={e => setForm((f: any) => ({ ...f, notes: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </>)}
              {tab === 'vendors' && (<>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">区分</label>
                  <select value={form.category || ''} onChange={e => setForm((f: any) => ({ ...f, category: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">選択</option>
                    {VENDOR_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <F label="業者名 *" name="name" />
                <F label="営業所/支店" name="branch" />
                <F label="担当" name="contact_person" />
                <F label="TEL" name="phone" />
                <F label="FAX" name="fax" />
                <F label="郵便番号" name="postal_code" />
                <F label="住所" name="address" />
              </>)}
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 text-sm">キャンセル</button>
              <button onClick={handleSave} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
