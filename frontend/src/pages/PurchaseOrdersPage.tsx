// ============================================
// 発注管理ページ
// ============================================
import { useEffect, useState } from 'react';
import { purchaseOrderApi } from '../api';
import { Truck, Search } from 'lucide-react';

const PO_STATUS_LABELS: Record<string, string> = {
  draft: '下書き', sent: '発注済', partial: '一部入荷', received: '入荷完了', cancelled: 'キャンセル'
};
const PO_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600', sent: 'bg-blue-100 text-blue-700',
  partial: 'bg-yellow-100 text-yellow-700', received: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-700',
};

export default function PurchaseOrdersPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');

  const load = () => {
    purchaseOrderApi.list({ status: statusFilter || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); });
  };
  useEffect(() => { load(); }, [statusFilter]);

  const handleStatus = async (id: string, status: string) => {
    await purchaseOrderApi.updateStatus(id, status);
    load();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">発注・仕入管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-4 mb-4 flex gap-3">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">全ステータス</option>
          {Object.entries(PO_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">発注番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">仕入先</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">発注日</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">入荷予定日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">発注金額（税込）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">ステータス</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(p => (
              <tr key={p.id} className="hover:bg-blue-50">
                <td className="px-4 py-3 font-medium text-blue-600 flex items-center gap-1">
                  <Truck size={14} /> {p.purchase_order_no}
                </td>
                <td className="px-4 py-3 text-gray-700">{p.supplier_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{p.issue_date}</td>
                <td className="px-4 py-3 text-gray-500">{p.expected_date || '—'}</td>
                <td className="px-4 py-3 text-right font-medium text-gray-800">
                  ¥{(p.total_amount || 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${PO_STATUS_COLORS[p.status] || 'bg-gray-100'}`}>
                    {PO_STATUS_LABELS[p.status] || p.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  {p.status === 'draft' && (
                    <button onClick={() => handleStatus(p.id, 'sent')}
                      className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700">発注確定</button>
                  )}
                  {p.status === 'sent' && (
                    <button onClick={() => handleStatus(p.id, 'received')}
                      className="text-xs bg-green-600 text-white px-2 py-1 rounded hover:bg-green-700">入荷完了</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">発注データがありません</div>}
      </div>
    </div>
  );
}
