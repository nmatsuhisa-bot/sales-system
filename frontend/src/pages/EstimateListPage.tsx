import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { estimateApi } from '../api';
import { Plus, FileText, Search, Printer } from 'lucide-react';

const STATUS_LABELS: Record<string, string> = { draft: '下書き', submitted: '提出済', approved: '承認済' };
const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600', submitted: 'bg-blue-100 text-blue-700', approved: 'bg-green-100 text-green-700'
};

export default function EstimateListPage() {
  const [searchParams] = useSearchParams();
  const childNo = searchParams.get('child_no') || '';
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');

  const load = () => {
    estimateApi.list({ child_no: childNo || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); });
  };
  useEffect(() => { load(); }, [childNo]);

  const handlePdf = (id: string) => {
    const url = `${import.meta.env.VITE_API_URL}/estimate-quotations/${id}/pdf`;
    window.open(url, '_blank');
  };

  const handleAdopt = async (q: any) => {
    if (!q.project_order_id) {
      alert('この見積は子IDに紐付いていません。案件管理から見積を作成してください。');
      return;
    }
    const action = q.is_adopted ? '採用を解除' : '採用';
    if (!confirm(`この見積を${action}しますか？\n${q.quotation_no} ¥${(q.total_amount||0).toLocaleString()}`)) return;
    try {
      if (q.is_adopted) {
        await estimateApi.unadoptQuotation(q.id);
        alert('採用を解除しました');
      } else {
        const r = await estimateApi.adoptQuotation(q.id);
        alert(`採用しました！子ID: ${r.data.child_no} に反映されました`);
      }
      load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラーが発生しました');
    }
  };

  const handleIssueTicket = async (id: string, total: number) => {
    const type = total >= 3000000 ? '工番（300万円以上）' : '単番（300万円未満）';
    if (!confirm(`受注票を発行します。\n種別: ${type}\nよろしいですか？`)) return;
    try {
      const r = await estimateApi.issueOrderTicket(id);
      const { ticket_no, id: ticketId } = r.data;
      alert(`受注票発行: ${ticket_no}`);
      const url = `${import.meta.env.VITE_API_URL}/estimate-quotations/order-ticket/${ticketId}/pdf`;
      window.open(url, '_blank');
    } catch (e: any) {
      alert(e.response?.data?.detail || 'エラー');
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">見積管理</h1>
          {childNo && <p className="text-sm text-blue-600 mt-1">子ID: {childNo} の見積一覧</p>}
          <p className="text-sm text-gray-500 mt-1">全 {total} 件</p>
        </div>
        <Link
          to={`/estimates/new${childNo ? `?child_no=${childNo}` : ''}`}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> 新規見積作成
        </Link>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">子ID</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">顧客名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">件名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">合計金額（税込）</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">状態</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {items.map(q => (
              <tr key={q.id} className="hover:bg-blue-50">
                <td className="px-4 py-3">
                  <Link to={`/estimates/${q.id}/edit`} className="text-blue-600 font-medium hover:underline flex items-center gap-1">
                    <FileText size={13} /> {q.quotation_no}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-500 font-mono text-xs">{q.child_no || '—'}</td>
                <td className="px-4 py-3 text-gray-700">{q.customer_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{q.title || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{q.issue_date || '—'}</td>
                <td className="px-4 py-3 text-right font-bold text-gray-800">
                  ¥{(q.total_amount || 0).toLocaleString()}
                  <span className={`ml-2 text-xs ${q.total_amount >= 1000000 ? 'text-purple-600' : 'text-orange-600'}`}>
                    {q.total_amount >= 1000000 ? '工番' : '単番'}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[q.status] || 'bg-gray-100'}`}>
                    {STATUS_LABELS[q.status] || q.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <button onClick={() => handlePdf(q.id)}
                      className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1">
                      <Printer size={12} /> PDF
                    </button>
                    <button onClick={() => handleIssueTicket(q.id, q.total_amount)}
                      className="text-xs bg-purple-600 text-white px-2 py-0.5 rounded hover:bg-purple-700">
                      受注票
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">見積書がありません</div>}
      </div>
    </div>
  );
}
