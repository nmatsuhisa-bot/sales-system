import { useEffect, useState } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'https://sales-backend-7nzg.onrender.com';

const MONTHS = ['3','4','5','6','7','8','9','10','11','12','1','2'];
const STATUS_OPTIONS = ['営業中','見積発行','受注','失注','請求済'];
const STATUS_COLORS: Record<string,string> = {
  '営業中': 'bg-blue-100 text-blue-700',
  '見積発行': 'bg-yellow-100 text-yellow-700',
  '受注': 'bg-green-100 text-green-700',
  '失注': 'bg-red-100 text-red-700',
  '請求済': 'bg-gray-100 text-gray-700',
};

interface Row {
  child_no: string; project_no: string; customer_name: string;
  agency_name: string; status: string; sales_date: string; month: number; amount: number;
}

function getFiscalYear(month: number, year: number): number {
  return month >= 3 ? year : year - 1;
}
function getFiscalMonth(month: number): string {
  return String(month);
}

export default function SalesPlanPage() {
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;
  const fiscalYear = currentMonth >= 3 ? currentYear : currentYear - 1;

  const [year, setYear] = useState(fiscalYear);
  const [rows, setRows] = useState<Row[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>(['営業中','見積発行','受注','請求済']);
  const [groupBy, setGroupBy] = useState<'customer'|'project'>('customer');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    const token = localStorage.getItem('access_token') || localStorage.getItem('token');
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    axios.get(`${API_BASE}/reports/sales-plan?year=${year}`, { headers })
      .then(r => setRows(r.data.rows || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [year]);

  const filtered = rows.filter(r => selectedStatuses.includes(r.status));

  // 月リスト（3月始まり）
  const monthList = [...Array(12)].map((_, i) => {
    const m = ((i + 2) % 12) + 1;
    return m;
  });

  // グループ集計
  const grouped: Record<string, { name: string; status: string; months: Record<number,number>; total: number }> = {};
  for (const r of filtered) {
    const key = groupBy === 'customer' ? r.customer_name : r.child_no;
    const name = groupBy === 'customer' ? r.customer_name : `${r.child_no}`;
    if (!grouped[key]) grouped[key] = { name, status: r.status, months: {}, total: 0 };
    grouped[key].months[r.month] = (grouped[key].months[r.month] || 0) + r.amount;
    grouped[key].total += r.amount;
  }

  // 月別合計
  const monthTotals: Record<number, number> = {};
  for (const r of filtered) {
    monthTotals[r.month] = (monthTotals[r.month] || 0) + r.amount;
  }
  const grandTotal = filtered.reduce((s, r) => s + r.amount, 0);

  function toggleStatus(s: string) {
    setSelectedStatuses(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  }

  const groupedEntries = Object.entries(grouped).sort((a, b) => b[1].total - a[1].total);

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-800">売上計画表</h1>
        <div className="flex gap-2 items-center flex-wrap">
          <select value={year} onChange={e => setYear(Number(e.target.value))}
            className="border rounded px-2 py-1 text-sm">
            {[currentYear-1, currentYear, currentYear+1].map(y => (
              <option key={y} value={y}>{y}年度</option>
            ))}
          </select>
          <div className="flex gap-1">
            <button onClick={() => setGroupBy('customer')}
              className={`px-3 py-1 text-sm rounded border ${groupBy==='customer' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100'}`}>
              顧客別
            </button>
            <button onClick={() => setGroupBy('project')}
              className={`px-3 py-1 text-sm rounded border ${groupBy==='project' ? 'bg-blue-600 text-white' : 'hover:bg-gray-100'}`}>
              案件別
            </button>
          </div>
        </div>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {STATUS_OPTIONS.map(s => (
          <label key={s} className="flex items-center gap-1 cursor-pointer text-sm">
            <input type="checkbox" checked={selectedStatuses.includes(s)} onChange={() => toggleStatus(s)} />
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[s] || 'bg-gray-100'}`}>{s}</span>
          </label>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">読み込み中...</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="border-collapse text-xs w-full">
            <thead>
              <tr className="bg-gray-100">
                <th className="border border-gray-300 px-2 py-2 text-left sticky left-0 bg-gray-100 z-10" style={{minWidth:'120px'}}>
                  {groupBy === 'customer' ? '顧客名' : '案件番号'}
                </th>
                {groupBy === 'project' && (
                  <th className="border border-gray-300 px-2 py-2 text-left" style={{minWidth:'80px'}}>ステータス</th>
                )}
                {monthList.map(m => (
                  <th key={m} className={`border border-gray-300 px-2 py-2 text-right ${m === currentMonth ? 'bg-blue-50' : ''}`} style={{minWidth:'60px'}}>
                    {m}月
                  </th>
                ))}
                <th className="border border-gray-300 px-2 py-2 text-right bg-gray-200" style={{minWidth:'80px'}}>合計</th>
              </tr>
            </thead>
            <tbody>
              {groupedEntries.map(([key, g]) => (
                <tr key={key} className="hover:bg-blue-50">
                  <td className="border border-gray-300 px-2 py-1 sticky left-0 bg-white z-10 font-medium">
                    {g.name || '—'}
                  </td>
                  {groupBy === 'project' && (
                    <td className="border border-gray-300 px-2 py-1">
                      <span className={`px-1 py-0.5 rounded text-xs ${STATUS_COLORS[g.status] || 'bg-gray-100'}`}>{g.status}</span>
                    </td>
                  )}
                  {monthList.map(m => (
                    <td key={m} className={`border border-gray-300 px-2 py-1 text-right ${m === currentMonth ? 'bg-blue-50' : ''}`}>
                      {g.months[m] ? (g.months[m] / 1000000).toFixed(1) + 'M' : ''}
                    </td>
                  ))}
                  <td className="border border-gray-300 px-2 py-1 text-right font-medium bg-gray-50">
                    {g.total ? (g.total / 1000000).toFixed(1) + 'M' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-gray-100 font-bold">
                <td className="border border-gray-300 px-2 py-2 sticky left-0 bg-gray-100 z-10">合計</td>
                {groupBy === 'project' && <td className="border border-gray-300 px-2 py-2"></td>}
                {monthList.map(m => (
                  <td key={m} className={`border border-gray-300 px-2 py-2 text-right ${m === currentMonth ? 'bg-blue-100' : ''}`}>
                    {monthTotals[m] ? (monthTotals[m] / 1000000).toFixed(1) + 'M' : ''}
                  </td>
                ))}
                <td className="border border-gray-300 px-2 py-2 text-right bg-gray-200">
                  {(grandTotal / 1000000).toFixed(1)}M
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <div className="mt-4 text-xs text-gray-400">
        ※ 売上計上日（sales_date）が設定されている案件のみ表示。金額は百万円単位（M）。
      </div>
    </div>
  );
}
