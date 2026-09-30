import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { mastersApi, estimateApi, procurementApi } from '../api';
import UsersPage from './UsersPage';
import { Plus, Edit2, Trash2, Search, Building2, MapPin, Users, FileText, ShoppingBag } from 'lucide-react';

type Tab = 'agencies' | 'destinations' | 'suppliers' | 'users' | 'texts';
const TAB_KEYS: Tab[] = ['agencies', 'destinations', 'suppliers', 'users', 'texts'];
// 仕入先の区分（TECHSの支払先リストの備考に合わせる）
// クレーン業者・運送業者もここに含める（旧・手配業者マスタを統合した）
const SUPPLIER_CATEGORIES = ['運送(トラック)', 'クレーン・作業車', '購入品'];

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
// 営業所の入力欄。仕入先と同じく外で定義する（中で定義するとフォーカスが飛ぶ）
function BranchRow({ b, i, onChange, onRemove }: any) {
  const set = (k: string, v: string) => onChange(i, { ...b, [k]: v, _dirty: true });
  const cls = 'border border-gray-200 rounded px-2 py-1 text-sm';
  return (
    <div className="flex gap-2 items-center">
      <input value={b.name || ''} onChange={e => set('name', e.target.value)}
        placeholder="営業所名" className={cls + ' w-32'} />
      <input value={b.contact_person || ''} onChange={e => set('contact_person', e.target.value)}
        placeholder="担当" className={cls + ' w-24'} />
      <input value={b.phone || ''} onChange={e => set('phone', e.target.value)}
        placeholder="TEL" className={cls + ' flex-1 min-w-0'} />
      <input value={b.fax || ''} onChange={e => set('fax', e.target.value)}
        placeholder="FAX" className={cls + ' flex-1 min-w-0'} />
      <button onClick={() => onRemove(i)} className="text-red-300 hover:text-red-500 shrink-0"
        title="この営業所を消す"><Trash2 size={14} /></button>
    </div>
  );
}

// 入力欄。コンポーネントの外で定義する。
// 中で定義すると毎レンダーで別のコンポーネント扱いになり、入力欄が作り直されて
// 1文字ごとにフォーカス（カーソル位置）が失われる
function F({ label, name, type = 'text', form, setForm }: any) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input type={type} value={form[name] || ''}
        onChange={e => setForm((f: any) => ({ ...f, [name]: e.target.value }))}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
    </div>
  );
}

export default function MastersPage() {
  // ?tab=users のように URL で開くタブを指定できる（旧「ユーザー管理」メニューからの移動先）
  const [params] = useSearchParams();
  const initialTab = params.get('tab') as Tab | null;
  const [tab, setTab] = useState<Tab>(initialTab && TAB_KEYS.includes(initialTab) ? initialTab : 'agencies');
  const [usersOpenSignal, setUsersOpenSignal] = useState(0);
  const [agencies, setAgencies] = useState<any[]>([]);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [supplierCat, setSupplierCat] = useState('');
  // TECHS登録の有無での絞り込み（'' すべて / 'yes' 登録あり / 'no' 未登録）
  const [techsFilter, setTechsFilter] = useState('');
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
    procurementApi.listSuppliers(search || undefined, supplierCat || undefined)
      .then(r => setSuppliers(r.data)).catch(() => {});
  };

  useEffect(() => { loadAll(); }, [search, supplierCat]);

  const shownSuppliers = suppliers.filter(s =>
    techsFilter === '' || (techsFilter === 'yes' ? s.has_techs : !s.has_techs));

  const handleSave = async () => {
    try {
      if (tab === 'agencies') {
        if (modal.id) await mastersApi.updateAgency(modal.id, form);
        else await mastersApi.createAgency(form);
      } else if (tab === 'destinations') {
        if (modal.id) await mastersApi.updateDeliveryDestination(modal.id, form);
        else await mastersApi.createDeliveryDestination(form);
      } else if (tab === 'suppliers') {
        const { branches = [], _removed = [], ...body } = form;
        const saved = modal.id
          ? (await procurementApi.updateSupplier(modal.id, body)).data
          : (await procurementApi.createSupplier(body)).data;
        // 営業所は仕入先が確定してから。新規行・直した行・消した行だけを送る
        for (const id of _removed) await procurementApi.deleteBranch(id);
        for (const b of branches) {
          if (!(b.name || '').trim()) continue;
          const body2 = { name: b.name, contact_person: b.contact_person, phone: b.phone, fax: b.fax };
          if (b.id) { if (b._dirty) await procurementApi.updateBranch(b.id, body2); }
          else await procurementApi.createBranch(saved.id, body2);
        }
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
    else if (tab === 'suppliers') await procurementApi.deleteSupplier(item.id);
    loadAll();
  };

  const openNew = () => {
    if (tab === 'users') { setUsersOpenSignal(n => n + 1); return; }
    setForm(tab === 'suppliers' ? { branches: [], _removed: [] } : {});
    setModal({});
  };
  const openEdit = (item: any) => {
    setForm({ ...item, branches: (item.branches || []).map((b: any) => ({ ...b })), _removed: [] });
    setModal(item);
  };

  // モーダル内の営業所の編集
  const setBranch = (i: number, b: any) =>
    setForm((f: any) => ({ ...f, branches: f.branches.map((x: any, n: number) => (n === i ? b : x)) }));
  const addBranch = () =>
    setForm((f: any) => ({ ...f, branches: [...(f.branches || []), {}] }));
  const removeBranch = (i: number) =>
    setForm((f: any) => {
      const b = f.branches[i];
      return { ...f, branches: f.branches.filter((_: any, n: number) => n !== i),
               _removed: b.id ? [...f._removed, b.id] : f._removed };
    });

  const tabs = [
    { key: 'agencies', label: '商社マスタ', icon: Building2, count: agencies.length },
    { key: 'destinations', label: '納入先マスタ', icon: MapPin, count: destinations.length },
    { key: 'suppliers', label: '仕入先マスタ', icon: ShoppingBag, count: suppliers.length },
    { key: 'users', label: '従業員・ユーザー', icon: Users, count: null },
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

      {/* 仕入先マスタ（TECHSの仕入先CDで突合） */}
      {tab === 'suppliers' && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 bg-gray-50">
            <span className="text-xs text-gray-500">区分</span>
            <select value={supplierCat} onChange={e => setSupplierCat(e.target.value)}
              className="border border-gray-200 rounded px-2 py-1 text-xs">
              <option value="">すべて</option>
              {SUPPLIER_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <span className="text-xs text-gray-500 ml-2">TECHS</span>
            <select value={techsFilter} onChange={e => setTechsFilter(e.target.value)}
              className="border border-gray-200 rounded px-2 py-1 text-xs">
              <option value="">すべて</option>
              <option value="yes">登録あり</option>
              <option value="no">未登録（手配のみ）</option>
            </select>
            <span className="text-xs text-gray-400">
              コード・名称・略称・ふりがなで検索できます（TECHSコードでも可）。
              クレーン業者・運送業者もこのマスタで管理します
            </span>
          </div>
          <div className="overflow-auto max-h-[70vh]">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">TECHSコード</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">仕入先名</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">略称</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">区分</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">営業所</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">担当者</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">TEL</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-600">FAX</th>
                  <th className="px-3 py-2 text-center font-medium text-gray-600">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {shownSuppliers.map(s => (
                  <tr key={s.id} className="hover:bg-blue-50">
                    <td className="px-3 py-2 font-mono text-xs">
                      {s.has_techs
                        ? <span className="text-blue-600">{s.techs_code}</span>
                        : <span className="text-amber-600" title="TECHSには登録がありません（手配でのみ使う先）">
                            {s.supplier_code}<span className="ml-1 font-sans">未登録</span></span>}
                    </td>
                    <td className="px-3 py-2 text-gray-800">{s.name}</td>
                    <td className="px-3 py-2 text-gray-500 text-xs">{s.short_name || '—'}</td>
                    <td className="px-3 py-2 text-xs">
                      {s.category
                        ? <span className="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700">{s.category}</span>
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {s.branches?.length ? `${s.branches.length}か所` : '—'}
                    </td>
                    <td className="px-3 py-2 text-gray-500 text-xs">{s.contact_person || '—'}</td>
                    <td className="px-3 py-2 text-gray-500 text-xs">{s.phone || '—'}</td>
                    <td className="px-3 py-2 text-gray-500 text-xs">{s.fax || '—'}</td>
                    <td className="px-3 py-2 text-center flex items-center justify-center gap-2">
                      <button onClick={() => openEdit(s)} className="text-blue-400 hover:text-blue-600"><Edit2 size={14} /></button>
                      <button onClick={() => handleDelete(s)} className="text-red-300 hover:text-red-500" title="無効にする"><Trash2 size={14} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {shownSuppliers.length === 0 && <div className="text-center py-10 text-gray-400">該当する仕入先がありません</div>}
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

      {/* モーダル */}
      {modal !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-gray-800 mb-4">
              {modal.id ? '編集' : '新規登録'} — {tabs.find(t => t.key === tab)?.label}
            </h2>
            <div className="space-y-3">
              {tab === 'agencies' && (<>
                <F label="商社コード *" name="agency_code" form={form} setForm={setForm} />
                <F label="商社名 *" name="agency_name" form={form} setForm={setForm} />
                <F label="支店名" name="branch_name" form={form} setForm={setForm} />
                <F label="取引条件" name="trade_terms" form={form} setForm={setForm} />
                <F label="住所（請求先）" name="address" form={form} setForm={setForm} />
                <F label="担当者名" name="contact_person" form={form} setForm={setForm} />
                <F label="電話番号" name="phone" form={form} setForm={setForm} />
              </>)}
              {tab === 'destinations' && (<>
                <F label="顧客ID *" name="customer_id" form={form} setForm={setForm} />
                <F label="会社名 *" name="company_name" form={form} setForm={setForm} />
                <F label="工場名" name="factory_name" form={form} setForm={setForm} />
                <F label="会社名_工場名" name="company_factory_name" form={form} setForm={setForm} />
                <F label="郵便番号" name="postal_code" form={form} setForm={setForm} />
                <F label="都道府県" name="prefecture" form={form} setForm={setForm} />
                <F label="住所" name="address" form={form} setForm={setForm} />
                <F label="TEL" name="tel" form={form} setForm={setForm} />
                <F label="FAX" name="fax" form={form} setForm={setForm} />
                <F label="ご担当者（送り状・依頼書に出ます）" name="contact_person" form={form} setForm={setForm} />
                <F label="顧客ランク" name="customer_rank" form={form} setForm={setForm} />
                <div>
                  <label className="block text-xs text-gray-500 mb-1">備考</label>
                  <textarea value={form.notes || ''} rows={2}
                    onChange={e => setForm((f: any) => ({ ...f, notes: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </>)}
              {tab === 'suppliers' && (<>
                <F label="仕入先コード（TECHS仕入先CD）*" name="supplier_code" form={form} setForm={setForm} />
                <F label="TECHSコード" name="techs_code" form={form} setForm={setForm} />
                <F label="仕入先名 *" name="name" form={form} setForm={setForm} />
                <F label="略称" name="short_name" form={form} setForm={setForm} />
                <F label="ふりがな" name="name_kana" form={form} setForm={setForm} />
                <div>
                  <label className="block text-xs text-gray-500 mb-1">区分</label>
                  <select value={form.category || ''} onChange={e => setForm((f: any) => ({ ...f, category: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">（なし）</option>
                    {SUPPLIER_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <F label="担当者" name="contact_person" form={form} setForm={setForm} />
                <F label="郵便番号" name="postal_code" form={form} setForm={setForm} />
                <F label="住所" name="address" form={form} setForm={setForm} />
                <F label="TEL" name="phone" form={form} setForm={setForm} />
                <F label="FAX" name="fax" form={form} setForm={setForm} />
                <F label="工程（運賃/材料 等）" name="process" form={form} setForm={setForm} />
                <F label="材料補助科目" name="material_account" form={form} setForm={setForm} />
                <F label="支払(10万円未満)" name="payment_small" form={form} setForm={setForm} />
                <F label="支払(10万円以上)" name="payment_large" form={form} setForm={setForm} />
                <F label="締め日" name="closing_day" type="number" form={form} setForm={setForm} />
                <F label="税区分" name="tax_type" form={form} setForm={setForm} />
                <div>
                  <label className="block text-xs text-gray-500 mb-1">備考</label>
                  <textarea value={form.notes || ''} rows={2}
                    onChange={e => setForm((f: any) => ({ ...f, notes: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div className="pt-3 border-t border-gray-100">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-medium text-gray-600">
                      営業所
                      <span className="ml-2 font-normal text-gray-400">
                        営業所ごとに連絡先が違う場合に登録します。手配書ではここから選べます
                      </span>
                    </label>
                    <button onClick={addBranch}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800">
                      <Plus size={12} />営業所を追加
                    </button>
                  </div>
                  <div className="space-y-2">
                    {(form.branches || []).map((b: any, i: number) => (
                      <BranchRow key={b.id || `new-${i}`} b={b} i={i} onChange={setBranch} onRemove={removeBranch} />
                    ))}
                    {!(form.branches || []).length &&
                      <div className="text-xs text-gray-400">登録なし（会社のTEL・FAXを使います）</div>}
                  </div>
                </div>
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
