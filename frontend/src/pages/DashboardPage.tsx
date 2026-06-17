import { useEffect, useState } from 'react';
import { reportApi } from '../api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, FileText, ShoppingCart, AlertCircle } from 'lucide-react';

const STATUS_LABELS: Record<string, string> = {
  draft: '下書き', submitted: '提出済', approved: '承認済', rejected: '却下', converted: '受注変換済',
  received: '受注', in_progress: '製造中', shipped: '出荷済', delivered: '納品済', completed: '完了', cancelled: 'キャンセル'
};

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    reportApi.dashboard().then(r => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return (
    <div className="flex items-center justify-center h-full text-gray-400">
      <div className="text-center">
        <div className="text-lg mb-2">読み込み中...</div>
      </div>
    </div>
  );

  const monthNames = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
  const chartData = monthNames.map((name, i) => {
    const found = data.monthly_sales?.find((s: any) => s.month === i + 1);
    return { name, 売上: found ? found.total : 0 };
  });

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">ダッシュボード</h1>

      {/* KPIカード */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          icon={<TrendingUp className="text-blue-500" />}
          label="今月の受注金額"
          value={`¥${(data.order_amount || 0).toLocaleString()}`}
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
          color="orange"
        />
        <KpiCard
          icon={<AlertCircle className="text-purple-500" />}
          label="対応中の受注"
          value={`${data.order_statuses?.['in_progress'] || 0} 件`}
          color="purple"
        />
      </div>

      {/* グラフ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">月別売上推移</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => `${(v/10000).toFixed(0)}万`} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: any) => `¥${v.toLocaleString()}`} />
              <Bar dataKey="売上" fill="#3b82f6" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">受注ステータス別</h2>
          <div className="space-y-3">
            {Object.entries(data.order_statuses || {}).map(([status, count]: any) => (
              <div key={status} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{STATUS_LABELS[status] || status}</span>
                <div className="flex items-center gap-2">
                  <div className="h-2 bg-blue-200 rounded" style={{ width: `${Math.min(count * 20, 120)}px` }}>
                    <div className="h-full bg-blue-500 rounded" style={{ width: '100%' }} />
                  </div>
                  <span className="text-sm font-medium text-gray-800 w-8 text-right">{count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 見積ステータス */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">見積ステータス別</h2>
        <div className="flex flex-wrap gap-3">
          {Object.entries(data.quotation_statuses || {}).map(([status, count]: any) => (
            <div key={status} className="bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 text-center">
              <div className="text-2xl font-bold text-orange-600">{count}</div>
              <div className="text-xs text-gray-600 mt-1">{STATUS_LABELS[status] || status}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function KpiCard({ icon, label, value, color }: any) {
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
    </div>
  );
}
