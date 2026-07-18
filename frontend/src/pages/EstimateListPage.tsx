import { useEffect, useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { estimateApi, API_BASE } from '../api';
import { Plus, FileText, Search, Printer, Copy, X } from 'lucide-react';
import OrderSearchInput from '../components/common/OrderSearchInput';

// 見積ステータス: 下書 / 受注（採用済）/ 受注済（受注票発行済）
const STATUS_LABELS: Record<string, string> = { draft: '下書', adopted: '受注', received: '受注済' };
const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600', adopted: 'bg-blue-100 text-blue-700', received: 'bg-green-100 text-green-700'
};

// 社内の管理金額は税抜（機器・工事 + 社内工数）で統一。工番/単番の判定も税抜。
export const KOBAN_THRESHOLD = 3000000;
// 税抜合計（機器・工事＋社内工数−出精値引）。APIのnet_amountを優先し、無ければ計算
export const netAmount = (q: any) =>
  q?.net_amount ?? ((q?.subtotal || 0) + (q?.labor_total || 0) - (q?.discount_amount || 0));

export default function EstimateListPage() {
  const [searchParams] = useSearchParams();
  const childNo = searchParams.get('child_no') || '';
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [dupFor, setDupFor] = useState<any>(null); // 複製対象の見積
  const navigate = useNavigate();

  const doDuplicate = async (order: any) => {
    if (!dupFor) return;
    try {
      const r = await estimateApi.duplicate(dupFor.id, order.id);
      setDupFor(null);
      alert(`複製しました: ${r.data.quotation_no}（子ID: ${r.data.child_no}）`);
      navigate(`/estimates/${r.data.id}/edit`);
    } catch (e: any) { alert(e.response?.data?.detail || '複製に失敗しました'); }
  };

  const load = () => {
    estimateApi.list({ child_no: childNo || undefined, search: search || undefined, per_page: 50 })
      .then(r => { setItems(r.data.items || []); setTotal(r.data.total || 0); });
  };
  useEffect(() => { load(); }, [childNo, search]);

  const handleAdopt = async (q: any) => {
    if (!q.project_order_id) { alert('この見積は子IDに紐付いていません'); return; }
    const isAdopted = q.is_adopted;
    if (!confirm(`${isAdopted ? '採用を解除' : '採用'}しますか？\n${q.quotation_no}`)) return;
    try {
      if (isAdopted) { await estimateApi.unadoptQuotation(q.id); alert('採用を解除しました'); }
      else { const r = await estimateApi.adoptQuotation(q.id); alert(`採用しました！\n子ID: ${r.data.child_no} に反映されました`); }
      load();
    } catch (e: any) { alert(e.response?.data?.detail || 'エラー'); }
  };

  const handlePdf = (id: string) => {
    const url = `${API_BASE}/estimate-quotations/${id}/pdf`;
    window.open(url, '_blank');
  };

  const handleFanInstruction = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/${id}/fan-instruction-pdf`, '_blank');
  };

  const handleFanInspection = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/${id}/fan-inspection-pdf`, '_blank');
  };

  const handleControlPanel = (id: string) => {
    window.open(`${API_BASE}/estimate-quotations/${id}/control-panel-pdf`, '_blank');
  };

  const handleIssueTicket = async (id: string, total: number) => {
    const type = total >= KOBAN_THRESHOLD ? '工番（税抜300万円以上）' : '単番（税抜300万円未満）';
    const confirmMsg = `受注票を発行します。\n種別: ${type}\nよろしいですか？`;
      if (!confirm(confirmMsg)) return;
    try {
      const r = await estimateApi.issueOrderTicket(id);
      const { ticket_no, id: ticketId } = r.data;
      if (r.data.has_previous) { alert(`受注票を再発行しました: ${ticket_no}\n旧受注票は非表示になりました`); } else { alert(`受注票発行: ${ticket_no}`); }
      const url = `${API_BASE}/estimate-quotations/order-ticket/${ticketId}/pdf`;
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

      <div className="bg-white rounded-xl shadow-sm p-3 mb-4 flex items-center gap-2 border border-gray-100">
        <Search size={16} className="text-gray-400" />
        <input placeholder="見積番号・注文主・件名・子IDで検索" value={search}
          onChange={e => setSearch(e.target.value)} className="flex-1 outline-none text-sm" />
        {search && <button onClick={() => setSearch('')} className="text-gray-400 hover:text-gray-600"><X size={15} /></button>}
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積番号</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">受注番号(COID)</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">注文主</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">件名</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">見積日</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">合計金額（税抜）</th>
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
                  ¥{netAmount(q).toLocaleString()}
                  <span className={`ml-2 text-xs ${netAmount(q) >= KOBAN_THRESHOLD ? 'text-purple-600' : 'text-orange-600'}`}>
                    {netAmount(q) >= KOBAN_THRESHOLD ? '工番' : '単番'}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex flex-col gap-1 items-center">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[q.status] || 'bg-gray-100'}`}>
                      {STATUS_LABELS[q.status] || q.status}
                    </span>
                    {q.approval_status === 'approved' ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-green-100 text-green-700">承認済</span>
                    ) : q.approval_status === 'pending' ? (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700">承認待ち</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-500">ドラフト</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex flex-col gap-1 items-center">
                    <div className="flex gap-1">
                      <button onClick={() => handlePdf(q.id)}
                        className="text-xs text-green-600 hover:text-green-800 flex items-center gap-1">
                        <Printer size={12} /> 見積PDF
                      </button>
                      <button onClick={() => handleIssueTicket(q.id, netAmount(q))}
                        className="text-xs bg-purple-600 text-white px-2 py-0.5 rounded hover:bg-purple-700">
                        受注票
                      </button>
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => handleFanInstruction(q.id)}
                        className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded hover:bg-blue-200">
                        ファン指示書
                      </button>
                      <button onClick={() => handleFanInspection(q.id)}
                        className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded hover:bg-orange-200">
                        検査記録
                      </button>
                      <button onClick={() => handleControlPanel(q.id)}
                        className="text-xs bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded hover:bg-gray-200">
                        制御盤
                      </button>
                      <button onClick={() => setDupFor(q)}
                        className="text-xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded hover:bg-emerald-200 flex items-center gap-0.5">
                        <Copy size={11} />複製
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <div className="text-center py-12 text-gray-400">見積書がありません</div>}
      </div>

      {/* 見積複製モーダル（案件子ID必須） */}
      {dupFor && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-gray-800">見積を複製</h2>
              <button onClick={() => setDupFor(null)} className="text-gray-400"><X size={18} /></button>
            </div>
            <p className="text-xs text-gray-500 mb-1">複製元: <span className="font-mono">{dupFor.quotation_no}</span> {dupFor.title || ''}</p>
            <p className="text-xs text-red-500 mb-2">複製先の案件子IDの選択は必須です。</p>
            <label className="block text-xs text-gray-500 mb-1">複製先 案件ID / 子ID</label>
            <OrderSearchInput onSelect={doDuplicate} placeholder="案件ID または 子ID で検索して選択" />
            <p className="text-[11px] text-gray-400 mt-3">※ 選択するとその子IDに紐付いた新しい見積（下書き）が作成され、編集画面が開きます。</p>
          </div>
        </div>
      )}
    </div>
  );
}
