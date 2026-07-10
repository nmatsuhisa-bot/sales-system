import { useEffect, useState } from 'react';
import { reportApi } from '../api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList } from 'recharts';
import { TrendingUp, FileText, ShoppingCart, AlertCircle } from 'lucide-react';

const STATUS_LABELS: Record<string, string> = {
  draft: '下書', adopted: '受注', received: '受注済',
  submitted: '提出済', approved: '承認済', rejected: '却下', converted: '受注変換済',
  in_progress: '製造中', shipped: '出荷済', delivered: '納品済', completed: '完了', cancelled: 'キャンセル'
};

function currentFiscalYear(): number {
  const today = new Date();
  const m = today.getMonth() + 1;
  const d = today.getDate();
  return (m > 2 || (m === 2 && d > 20)) ? today.getFullYear() : today.getFullYear() - 1;
}

// 3月始まり月順
const FISCAL_MONTHS = [3,4,5,6,7,8,9,10,11,12,1,2];

export default function DashboardPage() {
  const [fiscalYear, setFiscalYear] = useState(currentFiscalYear());
  const [chartMode, setChartMode] = useState<'order'|'delivery'>('order');
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    setData(null);
    reportApi.dashboard(fiscalYear).then(r => setData(r.data)).catch(() => {});
  }, [fiscalYear]);

  const thisYear = new Date().getFullYear();
  const yearOptions = [thisYear - 2, thisYear - 1, thisYear, thisYear + 1];

  const chartData = FISCAL_MONTHS.map(m => {
    const list = chartMode === 'order' ? data?.monthly_orders : data?.monthly_orders_by_delivery;
    const found = list?.find((s: any) => s.month === m);
    return { name: `${m}月`, 売上: found ? found.total : 0 };
  });

  const fmt = (v: number) => `${(v / 1000000).toFixed(1)}M`;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
        <h1 className="text-2xl font-bold text-gray-800">ダッシュボード</h1>
        <select
          value={fiscalYear}
          onChange={e => setFiscalYear(Number(e.target.value))}
          className="border rounded px-3 py-1.5 text-sm"
        >
          {yearOptions.map(y => (
            <option key={y} value={y}>{y}年度（{y}/2/21〜{y+1}/2/20）</option>
          ))}
        </select>
      </div>

      {!data ? (
        <div className="flex items-center justify-center h-40 text-gray-400">読み込み中...</div>
      ) : (
        <>
          {/* KPIカード */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <KpiCard
              icon={<TrendingUp className="text-blue-500" />}
              label="今月の受注金額"
              value={`¥${(data.order_amount || 0).toLocaleString()}`}
              sub={fmt(data.order_amount || 0)}
              color="blue"
            />
            <KpiCard
              icon={<ShoppingCart className="text-green-500" />}
              label="今月の受注件数"
              value={`${data.order_count || 0} 件`}
              color="green"
            />
            <KpiCard
              icon={<FileText className="text-orange-500" />}
              label="今月の見積件数"
              value={`${data.monthly_quotations_count || 0} 件`}
              sub={fmt(data.monthly_quotations_amount || 0)}
              color="orange"
            />
            <KpiCard
              icon={<AlertCircle className="text-purple-500" />}
              label="受注中の案件"
              value={`${data.active_orders_count || 0} 件`}
              sub={fmt(data.active_orders_amount || 0)}
              color="purple"
            />
          </div>

          {/* グラフ */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-700">月別売上推移</h2>
                <div className="flex gap-1">
                  <button
                    onClick={() => setChartMode('order')}
                    className={`px-3 py-1 text-xs rounded border ${chartMode === 'order' ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-gray-100'}`}
                  >
                    受注月
                  </button>
                  <button
                    onClick={() => setChartMode('delivery')}
                    className={`px-3 py-1 text-xs rounded border ${chartMode === 'delivery' ? 'bg-blue-600 text-white border-blue-600' : 'hover:bg-gray-100'}`}
                  >
                    納品月
                  </button>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={v => `${(v/1000000).toFixed(0)}M`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: any) => [`¥${v.toLocaleString()}`, '金額']} />
                  <Bar dataKey="売上" fill={chartMode === 'order' ? '#3b82f6' : '#10b981'} radius={[4,4,0,0]}>
                    <LabelList dataKey="売上" position="top"
                      formatter={(v: any) => (v ? `${(v / 1000000).toFixed(1)}M` : '')}
                      style={{ fontSize: 10, fill: '#374151' }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="text-xs text-gray-400 mt-1">
                {fiscalYear}年度（{fiscalYear}/2/21〜{fiscalYear+1}/2/20）・{chartMode === 'order' ? '受注日' : '納品日（売上計上日）'}ベース
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-700 mb-4">案件ステータス別</h2>
              <div className="space-y-2">
                {Object.entries(data.project_status_counts || {}).map(([status, count]: any) => {
                  const amount = data.project_status_amounts?.[status] || 0;
                  return (
                    <div key={status} className="flex items-center justify-between gap-2">
                      <span className="text-sm text-gray-600 w-20 shrink-0">{STATUS_LABELS[status] || status}</span>
                      <div className="flex-1 h-2 bg-blue-100 rounded overflow-hidden">
                        <div className="h-full bg-blue-400 rounded" style={{ width: `${Math.min(count * 10, 100)}%` }} />
                      </div>
                      <span className="text-sm font-medium text-gray-800 w-8 text-right shrink-0">{count}</span>
                      <span className="text-xs text-gray-500 w-16 text-right shrink-0">
                        {amount > 0 ? fmt(amount) : '—'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* 見積ステータス */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-700 mb-4">見積ステータス別</h2>
            <div className="flex flex-wrap gap-3">
              {Object.entries(data.quotation_status_counts || {}).map(([status, count]: any) => (
                <div key={status} className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 text-center">
                  <div className="text-2xl font-bold text-orange-600">{count}</div>
                  <div className="text-xs text-gray-600 mt-1">{STATUS_LABELS[status] || status}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function KpiCard({ icon, label, value, sub, color }: any) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-100',
    green: 'bg-green-50 border-green-100',
    orange: 'bg-orange-50 border-orange-100',
    purple: 'bg-purple-50 border-purple-100',
  };
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-sm text-gray-600">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-800">{value}</div>
      {sub && <div className="text-sm text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}
