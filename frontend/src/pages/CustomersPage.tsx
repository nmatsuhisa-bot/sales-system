import { useEffect, useState } from 'react';
import { customerApi } from '../api';
import { Plus, Search, Edit2, Building2 } from 'lucide-react';

export default function CustomersPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [modal, setModal] = useState<any>(null); // null=閉じる, {}=新規, {...}=編集
  const [form, setForm] = useState<any>({});

  const load = () => {
    customerApi.list({ search: search || undefined, per_page: 100 })
      .then(r => { setItems(r.data.items); setTotal(r.data.total); });
  };

  useEffect(() => { load(); }, [search]);

  const openNew = () => { setForm({}); setModal({}); };
  const openEdit = (c: any) => { setForm({ ...c }); setModal(c); };

  const handleSave = async () => {
    try {
      if (!form.customer_code || !form.name) { alert('顧客コードと顧客名は必須です'); return; }
      if (modal.id) {
        await customerApi.update(modal.id, form);
      } else {
        await customerApi.create(form);
      }
      setModal(null);
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラーが発生しました');
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">顧客管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
        <button
          onClick={openNew}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          <Plus size={18} /> 新規顧客登録
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-4 mb-4 flex items-center gap-2">
        <Search size={16} className="text-gray-400" />
        <input
          placeholder="顧客名・顧客コードで検索"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 outline-none text-sm"
        />
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客コード</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">担当者</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">電話番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">住所</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(c => (
              <tr key={c.id} className="hover:bg-blue-50 transition-colors">
                <td className="px-4 py-3 font-medium text-blue-600">{c.customer_code}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Building2 size={14} className="text-gray-400" />
                    <span className="font-medium text-gray-800">{c.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-600">{c.contact_person || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{c.phone || '—'}</td>
                <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{c.address || '—'}</td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => openEdit(c)} className="text-blue-500 hover:text-blue-700">
                    <Edit2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">顧客データがありません</div>}
      </div>

      {/* モーダル */}
      {modal !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <h2 className="text-lg font-bold text-gray-800 mb-4">{modal.id ? '顧客編集' : '新規顧客登録'}</h2>
            <div className="space-y-3">
              {[
                ['customer_code', '顧客コード *', 'text', 'C-001'],
                ['name', '顧客名 *', 'text', '株式会社〇〇'],
                ['name_kana', 'フリガナ', 'text', ''],
                ['postal_code', '郵便番号', 'text', '000-0000'],
                ['prefecture', '都道府県', 'text', ''],
                ['address', '住所', 'text', ''],
                ['phone', '電話番号', 'text', ''],
                ['fax', 'FAX', 'text', ''],
                ['email', 'メールアドレス', 'email', ''],
                ['contact_person', '担当者名', 'text', ''],
                ['payment_terms', '支払条件', 'text', ''],
              ].map(([key, label, type, ph]) => (
                <div key={key as string}>
                  <label className="block text-xs text-gray-600 mb-1">{label as string}</label>
                  <input
                    type={type as string}
                    placeholder={ph as string}
                    value={form[key as string] || ''}
                    onChange={e => setForm((f: any) => ({ ...f, [key as string]: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              ))}
              <div>
                <label className="block text-xs text-gray-600 mb-1">備考</label>
                <textarea
                  value={form.notes || ''}
                  onChange={e => setForm((f: any) => ({ ...f, notes: e.target.value }))}
                  rows={2}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                />
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
