// ============================================
// 受注管理ページ
// ============================================
import { useEffect, useState } from 'react';
import { orderApi } from '../api';
import { Search, ShoppingCart } from 'lucide-react';

const ORDER_STATUS_LABELS: Record<string, string> = {
  received: '受注', in_progress: '製造中', shipped: '出荷済',
  delivered: '納品済', completed: '完了', cancelled: 'キャンセル'
};
const ORDER_STATUS_COLORS: Record<string, string> = {
  received: 'bg-blue-100 text-blue-700',
  in_progress: 'bg-yellow-100 text-yellow-700',
  shipped: 'bg-purple-100 text-purple-700',
  delivered: 'bg-green-100 text-green-700',
  completed: 'bg-gray-100 text-gray-600',
  cancelled: 'bg-red-100 text-red-700',
};
const NEXT_STATUS: Record<string, string> = {
  received: 'in_progress', in_progress: 'shipped', shipped: 'delivered', delivered: 'completed'
};
const NEXT_STATUS_LABEL: Record<string, string> = {
  received: '製造開始', in_progress: '出荷処理', shipped: '納品完了', delivered: '完了にする'
};

export default function OrdersPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const load = () => {
    orderApi.list({ search: search || undefined, status: statusFilter || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items); setTotal(r.data.total); });
  };
  useEffect(() => { load(); }, [search, statusFilter]);

  const handleStatusChange = async (id: string, nextStatus: string) => {
    await orderApi.updateStatus(id, nextStatus);
    load();
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
          <input placeholder="受注番号・顧客名で検索" value={search}
            onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">全ステータス</option>
          {Object.entries(ORDER_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">件名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注日</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">納期</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">金額（税込）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">ステータス</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(o => (
              <tr key={o.id} className="hover:bg-blue-50">
                <td className="px-4 py-3 font-medium text-blue-600 flex items-center gap-1">
                  <ShoppingCart size={14} /> {o.order_no}
                </td>
                <td className="px-4 py-3 text-gray-700">{o.customer_name}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{o.title || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{o.order_date}</td>
                <td className="px-4 py-3 text-gray-500">{o.delivery_date || '—'}</td>
                <td className="px-4 py-3 text-right font-medium text-gray-800">
                  ¥{(o.total_amount || 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${ORDER_STATUS_COLORS[o.status] || 'bg-gray-100'}`}>
                    {ORDER_STATUS_LABELS[o.status] || o.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  {NEXT_STATUS[o.status] && (
                    <button
                      onClick={() => handleStatusChange(o.id, NEXT_STATUS[o.status])}
                      className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700"
                    >
                      {NEXT_STATUS_LABEL[o.status]}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">受注データがありません<br /><span className="text-xs mt-1 block">見積管理から「受注化」して追加してください</span></div>}
      </div>
    </div>
  );
}
