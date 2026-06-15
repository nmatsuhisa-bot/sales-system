import { useEffect, useState } from 'react';
import { estimateApi } from '../api';
import { Search, FileText, ShoppingCart } from 'lucide-react';

const TYPE_LABELS: Record<string, string> = { koban: '工番', tanban: '単番' };
const TYPE_COLORS: Record<string, string> = {
  koban: 'bg-purple-100 text-purple-700',
  tanban: 'bg-orange-100 text-orange-700',
};

export default function OrdersPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const load = () => {
    estimateApi.listOrderTickets({ search: search || undefined, ticket_type: typeFilter || undefined })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); })
      .catch(() => {});
  };

  useEffect(() => { load(); }, [search, typeFilter]);

  const handlePdf = (id: string) => {
    window.open(`${import.meta.env.VITE_API_URL}/estimate-quotations/order-ticket/${id}/pdf`, '_blank');
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">受注管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-4 mb-4 flex gap-3">
        <div className="flex items-center gap-2 flex-1 border border-gray-200 rounded-lg px-3 py-2">
          <Search size={16} className="text-gray-400" />
          <input placeholder="受注番号・顧客名・子IDで検索" value={search}
            onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        </div>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">全種別</option>
          <option value="koban">工番</option>
          <option value="tanban">単番</option>
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">種別</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">子ID</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">納入先</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">担当者</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">金額（税込）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">PDF</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(t => (
              <tr key={t.id} className="hover:bg-blue-50">
                <td className="px-4 py-3 font-medium text-blue-600 flex items-center gap-1">
                  <ShoppingCart size={14} /> {t.ticket_no}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${TYPE_COLORS[t.ticket_type] || 'bg-gray-100'}`}>
                    {TYPE_LABELS[t.ticket_type] || t.ticket_type}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600">{t.child_no || '—'}</td>
                <td className="px-4 py-3 text-gray-700">{t.customer_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{t.delivery_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{t.sales_person_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{t.order_date || '—'}</td>
                <td className="px-4 py-3 text-right font-medium text-gray-800">
                  ¥{(t.total_amount || 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-center">
                  <button onClick={() => handlePdf(t.id)}
                    className="text-green-600 hover:text-green-800">
                    <FileText size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            受注票がありません<br />
            <span className="text-xs mt-1 block">見積管理から「受注票」ボタンで発行してください</span>
          </div>
        )}
      </div>
    </div>
  );
}
