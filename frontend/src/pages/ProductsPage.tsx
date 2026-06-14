// ============================================
// 商品管理ページ
// ============================================
import { useEffect, useState } from 'react';
import { productApi } from '../api';
import { Plus, Search, Edit2, Package } from 'lucide-react';

const PRODUCT_TYPES = ['BFQ', 'BFR', 'SCA', 'BFC', 'RV', '集塵ダクト', '部品', 'その他'];

export default function ProductsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [modal, setModal] = useState<any>(null);
  const [form, setForm] = useState<any>({});

  const load = () => {
    productApi.list({ search: search || undefined, product_type: typeFilter || undefined, per_page: 100 })
      .then(r => { setItems(r.data.items); setTotal(r.data.total); });
  };
  useEffect(() => { load(); }, [search, typeFilter]);

  const handleSave = async () => {
    try {
      if (!form.product_code || !form.name) { alert('商品コードと商品名は必須です'); return; }
      if (modal.id) {
        await productApi.update(modal.id, form);
      } else {
        await productApi.create(form);
      }
      setModal(null);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラー');
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">商品管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
        <button onClick={() => { setForm({}); setModal({}); }}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
          <Plus size={18} /> 新規商品登録
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-4 mb-4 flex gap-3">
        <div className="flex items-center gap-2 flex-1 border border-gray-200 rounded-lg px-3 py-2">
          <Search size={16} className="text-gray-400" />
          <input placeholder="商品コード・商品名で検索" value={search}
            onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        </div>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">全タイプ</option>
          {PRODUCT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">商品コード</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">商品名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">タイプ</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">標準価格</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">在庫数</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(p => (
              <tr key={p.id} className="hover:bg-blue-50">
                <td className="px-4 py-3 font-medium text-blue-600">{p.product_code}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Package size={14} className="text-gray-400" />
                    <span className="font-medium text-gray-800">{p.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">{p.product_type || '—'}</span>
                </td>
                <td className="px-4 py-3 text-right text-gray-800">¥{Number(p.standard_price || 0).toLocaleString()}</td>
                <td className="px-4 py-3 text-right">
                  <span className={`font-medium ${Number(p.stock_quantity) <= Number(p.min_stock_quantity) ? 'text-red-600' : 'text-gray-700'}`}>
                    {Number(p.stock_quantity || 0)}
                  </span>
                  <span className="text-gray-400 ml-1 text-xs">{p.unit}</span>
                </td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => { setForm({ ...p }); setModal(p); }} className="text-blue-500 hover:text-blue-700">
                    <Edit2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">商品データがありません</div>}
      </div>

      {modal !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-gray-800 mb-4">{modal.id ? '商品編集' : '新規商品登録'}</h2>
            <div className="space-y-3">
              {([
                ['product_code', '商品コード *', 'text'],
                ['name', '商品名 *', 'text'],
                ['category', 'カテゴリ', 'text'],
                ['unit', '単位', 'text'],
                ['standard_price', '標準価格', 'number'],
                ['cost_price', '仕入価格', 'number'],
                ['min_stock_quantity', '最低在庫数', 'number'],
              ] as [string, string, string][]).map(([key, label, type]) => (
                <div key={key}>
                  <label className="block text-xs text-gray-600 mb-1">{label}</label>
                  <input type={type} value={form[key] || ''}
                    onChange={e => setForm((f: any) => ({ ...f, [key]: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
              ))}
              <div>
                <label className="block text-xs text-gray-600 mb-1">製品タイプ</label>
                <select value={form.product_type || ''}
                  onChange={e => setForm((f: any) => ({ ...f, product_type: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">選択</option>
                  {PRODUCT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">説明・仕様</label>
                <textarea value={form.description || ''} rows={3}
                  onChange={e => setForm((f: any) => ({ ...f, description: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
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
