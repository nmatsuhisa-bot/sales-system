// ============================================
// 見積一覧ページ
// ============================================
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { quotationApi } from '../api';
import { Plus, Search, FileText, ArrowRight, Trash2 } from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  submitted: 'bg-blue-100 text-blue-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  converted: 'bg-purple-100 text-purple-700',
};
const STATUS_LABELS: Record<string, string> = {
  draft: '下書き', submitted: '提出済', approved: '承認済', rejected: '却下', converted: '受注変換済'
};

export default function QuotationsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const navigate = useNavigate();

  const load = () => {
    quotationApi.list({ search: search || undefined, status: statusFilter || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items); setTotal(r.data.total); });
  };

  useEffect(() => { load(); }, [search, statusFilter]);

  const handleConvert = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    if (!confirm('受注に変換しますか？')) return;
    try {
      const r = await quotationApi.convertToOrder(id);
      alert(`受注番号: ${r.data.order_no} で受注しました`);
      load();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'エラーが発生しました');
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    if (!confirm('削除しますか？')) return;
    await quotationApi.delete(id);
    load();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">見積管理</h1>
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
        <Link
          to="/quotations/new"
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          <Plus size={18} /> 新規見積作成
        </Link>
      </div>

      {/* フィルタ */}
      <div className="bg-white rounded-xl shadow-sm p-4 mb-4 flex gap-3">
        <div className="flex items-center gap-2 flex-1 border border-gray-200 rounded-lg px-3 py-2">
          <Search size={16} className="text-gray-400" />
          <input
            placeholder="見積番号・件名・顧客名で検索"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1 outline-none text-sm"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">全ステータス</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {/* テーブル */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">件名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">金額（税込）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">ステータス</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(q => (
              <tr key={q.id} className="hover:bg-blue-50 transition-colors">
                <td className="px-4 py-3">
                  <Link to={`/quotations/${q.id}/edit`} className="text-blue-600 font-medium hover:underline flex items-center gap-1">
                    <FileText size={14} /> {q.quotation_no}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-700">{q.customer_name}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{q.title || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{q.issue_date}</td>
                <td className="px-4 py-3 text-right font-medium text-gray-800">
                  ¥{(q.total_amount || 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[q.status] || 'bg-gray-100'}`}>
                    {STATUS_LABELS[q.status] || q.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    {q.status !== 'converted' && (
                      <button
                        onClick={(e) => handleConvert(q.id, e)}
                        className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1"
                      >
                        <ArrowRight size={12} /> 受注化
                      </button>
                    )}
                    <button
                      onClick={(e) => handleDelete(q.id, e)}
                      className="text-red-400 hover:text-red-600"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <div className="text-center py-12 text-gray-400">見積書がありません</div>
        )}
      </div>
    </div>
  );
}
